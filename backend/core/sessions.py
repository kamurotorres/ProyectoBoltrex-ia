"""Sesiones de usuario en el servidor (backlog P1.11).

Cada login crea un documento en `sessions` y el JWT lleva su id (`sid`). En cada
petición se comprueba que la sesión exista y no lleve más de SESSION_IDLE_MINUTES
sin actividad. Así una sesión se puede cerrar al instante (salir, cambiar contraseña,
cambiar roles, desactivar) aunque el token aún no haya vencido.

Documento:
    {_id: sid, email, created_at, last_activity, expires_at, ip, user_agent}
`expires_at` = fin de la duración máxima; el índice TTL borra las sesiones vencidas.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, Request, status

from core.config import ACCESS_TOKEN_EXPIRE_MINUTES, SESSION_IDLE_MINUTES, SESSION_TOUCH_SECONDS
from core.database import db

COLLECTION = "sessions"

MSG_IDLE = "Tu sesión se cerró por inactividad. Inicia sesión de nuevo."
MSG_EXPIRED = "Tu sesión expiró. Inicia sesión de nuevo."
MSG_CLOSED = "Tu sesión fue cerrada. Inicia sesión de nuevo."


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    # Mongo devuelve fechas sin zona (UTC).
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def session_error(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"})


async def _audit_close(email: str, sid: str, action: str, summary: str) -> None:
    from core import audit
    audit.set_request_context(session_id=sid)
    await audit.record("auth", action, entity_id=email, entity_name=email, summary=summary, actor_email=email)


async def create_session(email: str, request: Optional[Request] = None) -> str:
    from core.login_throttle import client_ip

    now = _now()
    sid = uuid.uuid4().hex
    await db[COLLECTION].insert_one({
        "_id": sid,
        "email": email,
        "created_at": now,
        "last_activity": now,
        "expires_at": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "ip": client_ip(request) if request is not None else None,
        "user_agent": (request.headers.get("user-agent", "")[:200] if request is not None else None),
    })
    return sid


async def validate_session(sid: Optional[str], email: str) -> None:
    """Lanza 401 con el motivo si la sesión no es válida; si lo es, registra la actividad."""
    if not sid:
        # Tokens emitidos antes de P1.11 (sin sesión): hay que volver a entrar.
        raise session_error(MSG_EXPIRED)
    session = await db[COLLECTION].find_one({"_id": sid})
    if session is None or session.get("email") != email:
        raise session_error(MSG_CLOSED)

    now = _now()
    if _aware(session["expires_at"]) <= now:
        await db[COLLECTION].delete_one({"_id": sid})
        await _audit_close(email, sid, "session_expired", "La sesión alcanzó su duración máxima")
        raise session_error(MSG_EXPIRED)
    # Margen de SESSION_TOUCH_SECONDS: la última actividad guardada puede ir hasta ese tiempo
    # por detrás de la real, y el servidor nunca debe cerrar antes de lo que muestra la pantalla.
    if now - _aware(session["last_activity"]) > timedelta(minutes=SESSION_IDLE_MINUTES, seconds=SESSION_TOUCH_SECONDS):
        await db[COLLECTION].delete_one({"_id": sid})
        await _audit_close(email, sid, "session_idle",
                           f"Sesión cerrada por {SESSION_IDLE_MINUTES:g} minuto(s) de inactividad")
        raise session_error(MSG_IDLE)

    # Se escribe como máximo una vez por SESSION_TOUCH_SECONDS por sesión.
    if now - _aware(session["last_activity"]) >= timedelta(seconds=SESSION_TOUCH_SECONDS):
        await db[COLLECTION].update_one({"_id": sid}, {"$set": {"last_activity": now}})


async def revoke_session(sid: Optional[str]) -> None:
    if sid:
        await db[COLLECTION].delete_one({"_id": sid})


async def revoke_user_sessions(email: str, except_sid: Optional[str] = None) -> int:
    """Cierra todas las sesiones de un usuario (opcionalmente menos la actual)."""
    query = {"email": email}
    if except_sid:
        query["_id"] = {"$ne": except_sid}
    result = await db[COLLECTION].delete_many(query)
    return result.deleted_count


async def touch_session(sid: Optional[str]) -> None:
    """Registra actividad ya mismo (sin el límite de una escritura por minuto)."""
    if sid:
        await db[COLLECTION].update_one({"_id": sid}, {"$set": {"last_activity": _now()}})


async def close_expired(sid: Optional[str], email: Optional[str], request: Optional[Request] = None) -> None:
    """Token vencido: borra la sesión y deja constancia en la bitácora (solo la primera vez)."""
    if not sid or not email:
        return
    result = await db[COLLECTION].delete_one({"_id": sid})
    if result.deleted_count:
        from core import audit
        if request is not None:
            audit.set_request_context(request)
        await _audit_close(email, sid, "session_expired", "La sesión alcanzó su duración máxima")
