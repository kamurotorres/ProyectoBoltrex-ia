import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'boltrex')

DEFAULT_SECRET_KEY = "boltrex-secret-key-change-in-production"
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", DEFAULT_SECRET_KEY)
ALGORITHM = "HS256"

if SECRET_KEY == DEFAULT_SECRET_KEY:
    import logging
    logging.getLogger("boltrex").warning(
        "JWT_SECRET_KEY no está definido: se usa el secreto por defecto y cualquiera puede falsificar tokens. "
        "Defínelo en backend/.env."
    )

# Registro público (/api/auth/register). Desactivado por defecto: los usuarios los crea un
# administrador desde Usuarios. Poner ALLOW_PUBLIC_REGISTRATION=true para reactivarlo.
ALLOW_PUBLIC_REGISTRATION = os.environ.get("ALLOW_PUBLIC_REGISTRATION", "false").strip().lower() in ("1", "true", "yes")

# Orígenes permitidos por CORS, separados por comas. En Docker el frontend y la API comparten
# origen (nginx hace proxy de /api), así que CORS solo importa en desarrollo local.
CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]

# Usuario administrador protegido: el factory reset nunca lo borra y no se puede eliminar,
# desactivar ni quitarle el rol Administrador (core/user_protection.py).
PROTECTED_ADMIN_EMAIL = os.environ.get("PROTECTED_ADMIN_EMAIL", "admin@boltrex.com")

# Límite de intentos de login (backlog P1.9). Valores en minutos (admiten decimales, útil en tests).
#  - Bloqueo por cuenta: LOGIN_MAX_ATTEMPTS fallos dentro de LOGIN_WINDOW_MINUTES → bloqueo LOGIN_LOCK_MINUTES.
#  - Bloqueo por IP: LOGIN_IP_MAX_ATTEMPTS fallos (contra cualquier email) en la misma ventana.
def _env_number(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return float(default)


LOGIN_MAX_ATTEMPTS = int(_env_number("LOGIN_MAX_ATTEMPTS", 5))
LOGIN_IP_MAX_ATTEMPTS = int(_env_number("LOGIN_IP_MAX_ATTEMPTS", 20))
LOGIN_WINDOW_MINUTES = _env_number("LOGIN_WINDOW_MINUTES", 15)
LOGIN_LOCK_MINUTES = _env_number("LOGIN_LOCK_MINUTES", 15)

# Sesiones (backlog P1.11). Cada login crea un registro en `sessions` (core/sessions.py).
#  - ACCESS_TOKEN_EXPIRE_MINUTES: duración máxima de una sesión aunque haya actividad (12 h).
#  - SESSION_IDLE_MINUTES: sin ninguna acción en ese tiempo la sesión se cierra (1 h).
#  - SESSION_WARNING_MINUTES: el frontend avisa este tiempo antes del cierre por inactividad.
ACCESS_TOKEN_EXPIRE_MINUTES = _env_number("ACCESS_TOKEN_EXPIRE_MINUTES", 720)
SESSION_IDLE_MINUTES = _env_number("SESSION_IDLE_MINUTES", 60)
SESSION_WARNING_MINUTES = min(_env_number("SESSION_WARNING_MINUTES", 5), SESSION_IDLE_MINUTES / 2)
# La última actividad se guarda como máximo cada SESSION_TOUCH_SECONDS (no en cada petición).
SESSION_TOUCH_SECONDS = min(60.0, SESSION_IDLE_MINUTES * 60 / 10)

# Bitácora de auditoría (backlog P1.12): días que se conservan los registros (0 = para siempre).
# Por defecto 6 meses. Al cambiarlo, el backend ajusta el índice TTL al arrancar.
AUDIT_RETENTION_DAYS = int(_env_number("AUDIT_RETENTION_DAYS", 180))
