"""Límite de intentos de login (backlog P1.9).

Dos contadores en la colección `login_attempts` (un documento por clave):
  - "email:<email>" → LOGIN_MAX_ATTEMPTS fallos en la ventana bloquean esa cuenta.
  - "ip:<ip>"       → LOGIN_IP_MAX_ATTEMPTS fallos (contra cualquier email) bloquean ese equipo.

- Durante el bloqueo se rechaza incluso la contraseña correcta.
- Los fallos contra emails inexistentes cuentan igual y reciben el mismo mensaje
  (no se revela qué cuentas existen).
- Un login correcto borra el contador de la cuenta (no el de la IP: si no, quien tenga una
  cuenta válida podría reiniciar el contador de IP entre intentos).
- Cambiar la contraseña de un usuario desde Usuarios desbloquea su cuenta (`unlock_email`).
- Los documentos caducan solos: índice TTL sobre `expires_at` (ver core/indexes.py).
- El intento de la cuenta se RESERVA (incremento atómico con pipeline) antes de comprobar la
  contraseña: con ráfagas en paralelo solo LOGIN_MAX_ATTEMPTS llegan a probarla.
  El contador de IP cuenta solo fallos (si contara aciertos, una oficina con muchos usuarios
  detrás de la misma IP se bloquearía).

La IP se toma de X-Real-IP (la pone nginx). Si alguien llega directo al puerto 8000 del
backend puede falsearla y evitar el bloqueo por IP; el bloqueo por cuenta se mantiene siempre.
"""
import math
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, Request
from pymongo import ReturnDocument

from core.config import LOGIN_IP_MAX_ATTEMPTS, LOGIN_LOCK_MINUTES, LOGIN_MAX_ATTEMPTS, LOGIN_WINDOW_MINUTES
from core.database import db


def _email_key(email: str) -> str:
    return f"email:{(email or '').strip().lower()}"


def _ip_key(ip: str) -> str:
    return f"ip:{ip}"


def client_ip(request: Request) -> str:
    return (request.headers.get("x-real-ip") or (request.client.host if request.client else "") or "desconocida").strip()


def _minutes_left(until: datetime, now: datetime) -> int:
    return max(1, math.ceil((until - now).total_seconds() / 60))


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)  # Mongo devuelve fechas naive en UTC
    return value


def _locked(detail: str, until: datetime, now: datetime):
    raise HTTPException(
        status_code=429,
        detail=detail,
        headers={"Retry-After": str(max(1, math.ceil((until - now).total_seconds())))},
    )


async def check_not_locked(email: str, ip: str) -> None:
    """Lanza 429 con un mensaje claro si la cuenta o el equipo están bloqueados."""
    now = datetime.now(timezone.utc)
    account = await db.login_attempts.find_one({"_id": _email_key(email)}, {"locked_until": 1})
    until = _as_utc((account or {}).get("locked_until"))
    if until and until > now:
        _locked(f"Demasiados intentos fallidos. Por seguridad, el acceso a esta cuenta está bloqueado. "
                f"Intenta de nuevo en {_minutes_left(until, now)} minuto(s).", until, now)

    device = await db.login_attempts.find_one({"_id": _ip_key(ip)}, {"locked_until": 1})
    until = _as_utc((device or {}).get("locked_until"))
    if until and until > now:
        _locked(f"Demasiados intentos fallidos desde este equipo. "
                f"Intenta de nuevo en {_minutes_left(until, now)} minuto(s).", until, now)


async def _register(key: str, limit: int, now: datetime) -> dict:
    window_start = now - timedelta(minutes=LOGIN_WINDOW_MINUTES)
    lock_until = now + timedelta(minutes=LOGIN_LOCK_MINUTES)
    window_ms = int(LOGIN_WINDOW_MINUTES * 60 * 1000)
    locked_until = {"$ifNull": ["$locked_until", None]}
    pipeline = [
        # ¿Empieza una ventana nueva? (sin fallos previos, ventana vencida o bloqueo ya cumplido)
        {"$set": {"_fresh": {"$or": [
            {"$not": ["$first_failure_at"]},
            {"$lte": ["$first_failure_at", window_start]},
            {"$and": [{"$ne": [locked_until, None]}, {"$lte": [locked_until, now]}]},
        ]}}},
        {"$set": {
            "failures": {"$cond": ["$_fresh", 1, {"$add": ["$failures", 1]}]},
            "first_failure_at": {"$cond": ["$_fresh", now, "$first_failure_at"]},
            "locked_until": {"$cond": ["$_fresh", None, locked_until]},
        }},
        {"$set": {"locked_until": {"$cond": [{"$gte": ["$failures", limit]}, lock_until, "$locked_until"]}}},
        {"$set": {"expires_at": {"$max": [{"$add": ["$first_failure_at", window_ms]},
                                          {"$ifNull": ["$locked_until", now]}]}}},
        {"$unset": "_fresh"},
    ]
    return await db.login_attempts.find_one_and_update(
        {"_id": key}, pipeline, upsert=True, return_document=ReturnDocument.AFTER
    )


async def reserve_attempt(email: str) -> int:
    """Reserva un intento de la cuenta ANTES de comprobar la contraseña y devuelve su número.

    Así, con peticiones simultáneas, solo las LOGIN_MAX_ATTEMPTS primeras llegan a comprobar
    la contraseña; las demás reciben el bloqueo sin probarla. Un login correcto borra la reserva.
    """
    now = datetime.now(timezone.utc)
    account = await _register(_email_key(email), LOGIN_MAX_ATTEMPTS, now)
    if account["failures"] > LOGIN_MAX_ATTEMPTS:
        until = _as_utc(account["locked_until"]) or now
        _locked(f"Demasiados intentos fallidos. Por seguridad, el acceso a esta cuenta está bloqueado. "
                f"Intenta de nuevo en {_minutes_left(until, now)} minuto(s).", until, now)
    return account["failures"]


async def register_failure(ip: str, attempt: int) -> str:
    """Registra el fallo para la IP y devuelve el mensaje para el usuario.

    `attempt` es el número devuelto por reserve_attempt (el fallo de la cuenta ya está contado).
    """
    await _register(_ip_key(ip), LOGIN_IP_MAX_ATTEMPTS, datetime.now(timezone.utc))

    lock = int(LOGIN_LOCK_MINUTES) if float(LOGIN_LOCK_MINUTES).is_integer() else LOGIN_LOCK_MINUTES
    remaining = LOGIN_MAX_ATTEMPTS - attempt
    if remaining <= 0:
        return (f"Email o contraseña incorrectos. Por seguridad, el acceso a esta cuenta quedó bloqueado "
                f"{lock} minuto(s).")
    if remaining == 1:
        return f"Email o contraseña incorrectos. Si vuelves a fallar, la cuenta se bloqueará {lock} minuto(s)."
    return f"Email o contraseña incorrectos. Te quedan {remaining} intentos antes del bloqueo temporal."


async def register_success(email: str) -> None:
    await db.login_attempts.delete_one({"_id": _email_key(email)})


async def unlock_email(email: str) -> None:
    """Quita el bloqueo y el contador de una cuenta (p. ej. cuando un admin cambia su contraseña)."""
    await db.login_attempts.delete_one({"_id": _email_key(email)})
