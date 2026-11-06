from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from jose import JWTError, ExpiredSignatureError, jwt
from datetime import datetime, timezone, timedelta
from core.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from core.database import get_db
from core.passwords import PASSWORD_CHANGE_REQUIRED
from models.auth import User
from motor.motor_asyncio import AsyncIOMotorDatabase

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def _load_user(credentials: HTTPAuthorizationCredentials, db: AsyncIOMotorDatabase, request: Request = None) -> dict:
    from core import sessions

    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        # Token vencido (duración máxima): se registra el cierre una sola vez, mientras la sesión exista.
        try:
            claims = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
            await sessions.close_expired(claims.get("sid"), claims.get("sub"), request)
        except JWTError:
            pass
        raise sessions.session_error(sessions.MSG_EXPIRED)
    except JWTError:
        raise sessions.session_error("Sesión no válida. Inicia sesión de nuevo.")
    email: str = payload.get("sub")
    if email is None:
        raise sessions.session_error("Sesión no válida. Inicia sesión de nuevo.")
    credentials_exception = sessions.session_error(sessions.MSG_CLOSED)

    # P1.12: IP y navegador de la petición para la bitácora de auditoría.
    from core import audit
    if request is not None:
        audit.set_request_context(request)

    # P1.11: la sesión debe existir en el servidor y no estar inactiva (registra la actividad).
    sid = payload.get("sid")
    await sessions.validate_session(sid, email)
    if request is not None:
        request.state.session_id = sid
    # P1.12: autor de las acciones que se registren durante esta petición.
    audit.set_request_context(actor_email=email, session_id=sid)
    
    # Search in users_extended first
    user = await db.users_extended.find_one({"email": email}, {"_id": 0, "hashed_password": 0})
    
    # If not found in users_extended, try old users table for backward compatibility
    if user is None:
        user = await db.users.find_one({"email": email}, {"_id": 0, "hashed_password": 0})
    
    if user is None:
        raise credentials_exception

    # Un usuario desactivado pierde el acceso aunque su token siga vigente.
    if not user.get("is_active", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="La cuenta de usuario está inactiva")
    return user


def _to_user(user: dict) -> User:
    # Return User format for compatibility
    return User(
        email=user["email"],
        full_name=user.get("full_name") or f"{user.get('first_name', '')} {user.get('last_name', '')}",
        role=user.get("role", "vendedor"),
        is_active=user.get("is_active", True),
        created_at=datetime.fromisoformat(user["created_at"]) if isinstance(user.get("created_at"), str) else user.get("created_at", datetime.now(timezone.utc))
    )


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncIOMotorDatabase = Depends(get_db)
) -> User:
    user = await _load_user(credentials, db, request)
    # P1.10: con la contraseña pendiente de cambio solo se permite /auth/me y /auth/change-password
    # (que usan get_current_user_pending_password). Todo lo demás se rechaza con un mensaje claro.
    if user.get("must_change_password"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=PASSWORD_CHANGE_REQUIRED)
    return _to_user(user)


async def get_current_user_pending_password(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncIOMotorDatabase = Depends(get_db)
) -> User:
    """Como get_current_user, pero deja pasar a quien aún debe cambiar su contraseña."""
    return _to_user(await _load_user(credentials, db, request))


def current_session_id(request: Request):
    """Id de la sesión de la petición actual (lo fija get_current_user)."""
    return getattr(request.state, "session_id", None)


async def flag_default_passwords(database: AsyncIOMotorDatabase) -> int:
    """Al arrancar (P1.10): marca para cambio obligatorio a los administradores que aún usan
    una contraseña por defecto (p. ej. admin123 de instalaciones antiguas). Nunca impide el arranque."""
    import asyncio
    import logging
    from core.config import PROTECTED_ADMIN_EMAIL
    from core.passwords import LEGACY_DEFAULT_PASSWORD

    log = logging.getLogger("boltrex")
    flagged = 0
    try:
        candidates = await database.users_extended.find(
            {"$or": [{"email": PROTECTED_ADMIN_EMAIL}, {"roles": "Administrador"}],
             "must_change_password": {"$ne": True}},
            {"_id": 0, "email": 1, "hashed_password": 1},
        ).to_list(200)
        for user in candidates:
            hashed = user.get("hashed_password")
            if not hashed:
                continue
            # bcrypt es lento: se ejecuta fuera del event loop.
            if await asyncio.to_thread(pwd_context.verify, LEGACY_DEFAULT_PASSWORD, hashed):
                await database.users_extended.update_one(
                    {"email": user["email"]}, {"$set": {"must_change_password": True}}
                )
                flagged += 1
                log.warning("El usuario %s usa la contraseña por defecto: se le pedirá cambiarla al entrar.", user["email"])
    except Exception as exc:  # pragma: no cover - solo registro
        log.error("No se pudo revisar contraseñas por defecto: %s", exc)
    return flagged
