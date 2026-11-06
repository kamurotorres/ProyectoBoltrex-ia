"""Configuración del backend (mantenimiento fase 2: `Settings` tipado y validado).

Todo sale de variables de entorno (o de `backend/.env`). Se lee UNA vez al importar el módulo:
- `settings` es el objeto tipado (inmutable) para el código nuevo: `from core.config import settings`.
- Los nombres sueltos de siempre (`SECRET_KEY`, `LOGIN_MAX_ATTEMPTS`, …) se conservan como alias,
  así ningún import existente cambia.
- Un valor inválido (texto donde va un número, negativo, cero donde no se puede) NO detiene el
  arranque: se usa el valor por defecto y el log dice qué variable revisar.
"""
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / ".env")

logger = logging.getLogger("boltrex")

DEFAULT_SECRET_KEY = "boltrex-secret-key-change-in-production"
_PROBLEMS: List[str] = []


def _env_number(name: str, default: float, minimum: Optional[float] = None, positive: bool = False) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return float(default)
    try:
        value = float(raw)
    except ValueError:
        _PROBLEMS.append(f"{name}={raw!r} no es un número: se usa {default}.")
        return float(default)
    if (positive and value <= 0) or (minimum is not None and value < minimum):
        rule = "mayor que 0" if positive else f"mayor o igual a {minimum:g}"
        _PROBLEMS.append(f"{name}={raw!r} debe ser {rule}: se usa {default}.")
        return float(default)
    return value


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "si", "sí")


def _env_list(name: str, default: str) -> Tuple[str, ...]:
    return tuple(o.strip() for o in os.environ.get(name, default).split(",") if o.strip())


@dataclass(frozen=True)
class Settings:
    # Base de datos
    mongo_url: str
    db_name: str
    # Seguridad / tokens
    secret_key: str
    algorithm: str
    allow_public_registration: bool
    cors_origins: Tuple[str, ...]
    protected_admin_email: str
    # Límite de intentos de login (P1.9), minutos con decimales (útil en pruebas)
    login_max_attempts: int
    login_ip_max_attempts: int
    login_window_minutes: float
    login_lock_minutes: float
    # Sesiones (P1.11)
    access_token_expire_minutes: float
    session_idle_minutes: float
    session_warning_minutes: float
    session_touch_seconds: float
    # Auditoría (P1.12): días que se conservan los registros (0 = para siempre)
    audit_retention_days: int
    # Zona del negocio para cálculos del servidor sin navegador (Colombia = 300)
    business_tz_offset_minutes: int
    problems: Tuple[str, ...] = field(default=())

    @property
    def uses_default_secret(self) -> bool:
        return self.secret_key == DEFAULT_SECRET_KEY

    def summary(self) -> str:
        """Resumen para el log de arranque, SIN secretos."""
        return (f"BD «{self.db_name}» · CORS {', '.join(self.cors_origins) or '—'} · registro público "
                f"{'sí' if self.allow_public_registration else 'no'} · sesión máx. {self.access_token_expire_minutes:g} min, "
                f"inactividad {self.session_idle_minutes:g} min · login {self.login_max_attempts} intentos / "
                f"{self.login_window_minutes:g} min, bloqueo {self.login_lock_minutes:g} min · auditoría "
                f"{self.audit_retention_days or 'sin límite'} días")


def load_settings() -> Settings:
    _PROBLEMS.clear()
    idle = _env_number("SESSION_IDLE_MINUTES", 60, positive=True)
    s = Settings(
        mongo_url=os.environ.get("MONGO_URL", "mongodb://localhost:27017"),
        db_name=os.environ.get("DB_NAME", "boltrex"),
        secret_key=os.environ.get("JWT_SECRET_KEY", DEFAULT_SECRET_KEY),
        algorithm="HS256",
        # Registro público (/api/auth/register): desactivado; los usuarios los crea un administrador.
        allow_public_registration=_env_bool("ALLOW_PUBLIC_REGISTRATION", False),
        # En Docker el frontend y la API comparten origen (nginx hace proxy de /api): CORS solo importa en desarrollo.
        cors_origins=_env_list("CORS_ORIGINS", "http://localhost:3000"),
        # El factory reset nunca lo borra; no se puede eliminar, desactivar ni quitarle el rol Administrador.
        protected_admin_email=os.environ.get("PROTECTED_ADMIN_EMAIL", "admin@boltrex.com"),
        login_max_attempts=int(_env_number("LOGIN_MAX_ATTEMPTS", 5, positive=True)),
        login_ip_max_attempts=int(_env_number("LOGIN_IP_MAX_ATTEMPTS", 20, positive=True)),
        login_window_minutes=_env_number("LOGIN_WINDOW_MINUTES", 15, positive=True),
        login_lock_minutes=_env_number("LOGIN_LOCK_MINUTES", 15, positive=True),
        access_token_expire_minutes=_env_number("ACCESS_TOKEN_EXPIRE_MINUTES", 720, positive=True),
        session_idle_minutes=idle,
        # El frontend avisa este tiempo antes del cierre por inactividad (máximo la mitad de la inactividad).
        session_warning_minutes=min(_env_number("SESSION_WARNING_MINUTES", 5, positive=True), idle / 2),
        # La última actividad se guarda como máximo cada N segundos (no en cada petición).
        session_touch_seconds=min(60.0, idle * 60 / 10),
        audit_retention_days=int(_env_number("AUDIT_RETENTION_DAYS", 180, minimum=0)),
        business_tz_offset_minutes=int(_env_number("BUSINESS_TZ_OFFSET_MINUTES", 300)),
        problems=tuple(_PROBLEMS),
    )
    return s


settings = load_settings()

for _p in settings.problems:
    logger.warning("Configuración: %s", _p)
if settings.uses_default_secret:
    logger.warning("JWT_SECRET_KEY no está definido: se usa el secreto por defecto y cualquiera puede falsificar tokens. "
                   "Defínelo en backend/.env.")

# ---- Alias de compatibilidad (los imports de siempre siguen funcionando) ----
MONGO_URL = settings.mongo_url
DB_NAME = settings.db_name
SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm
ALLOW_PUBLIC_REGISTRATION = settings.allow_public_registration
CORS_ORIGINS = list(settings.cors_origins)
PROTECTED_ADMIN_EMAIL = settings.protected_admin_email
LOGIN_MAX_ATTEMPTS = settings.login_max_attempts
LOGIN_IP_MAX_ATTEMPTS = settings.login_ip_max_attempts
LOGIN_WINDOW_MINUTES = settings.login_window_minutes
LOGIN_LOCK_MINUTES = settings.login_lock_minutes
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes
SESSION_IDLE_MINUTES = settings.session_idle_minutes
SESSION_WARNING_MINUTES = settings.session_warning_minutes
SESSION_TOUCH_SECONDS = settings.session_touch_seconds
AUDIT_RETENTION_DAYS = settings.audit_retention_days
BUSINESS_TZ_OFFSET_MINUTES = settings.business_tz_offset_minutes
