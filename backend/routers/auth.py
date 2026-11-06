from fastapi import APIRouter, HTTPException, Depends, Request
from datetime import datetime, timezone
from pydantic import BaseModel
from core.dates import now_utc
from core.database import db
from core.security import get_current_user_pending_password, current_session_id, get_password_hash, verify_password, create_access_token
from core import sessions
from core import audit
from core.config import LOGIN_MAX_ATTEMPTS
from core.config import ACCESS_TOKEN_EXPIRE_MINUTES, SESSION_IDLE_MINUTES, SESSION_WARNING_MINUTES
from core.passwords import password_problem
from core.config import ALLOW_PUBLIC_REGISTRATION
from core import login_throttle
from core.login_throttle import client_ip
from core.permissions import get_user_permissions
from models.auth import User, UserCreate, UserLogin

router = APIRouter(tags=["Auth"])


def session_settings() -> dict:
    """Tiempos de sesión que el frontend necesita para el aviso y el cierre por inactividad."""
    return {
        "idle_minutes": SESSION_IDLE_MINUTES,
        "warning_minutes": SESSION_WARNING_MINUTES,
        "max_minutes": ACCESS_TOKEN_EXPIRE_MINUTES,
    }
# ==================== AUTH ROUTES ====================

@router.post("/auth/register", response_model=User)
async def register(user_data: UserCreate, request: Request):
    if not ALLOW_PUBLIC_REGISTRATION:
        raise HTTPException(
            status_code=403,
            detail="El registro público está desactivado. Pide a un administrador que cree tu usuario.",
        )

    # Check in users_extended
    existing = await db.users_extended.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail=f"Ya existe un usuario con el email '{user_data.email}'")
    
    problem = password_problem(user_data.password)
    if problem:
        raise HTTPException(status_code=400, detail=problem)

    hashed_password = get_password_hash(user_data.password)
    
    # Create user in users_extended
    user_dict = {
        "email": user_data.email,
        "first_name": user_data.full_name.split()[0] if user_data.full_name else "Usuario",
        "last_name": " ".join(user_data.full_name.split()[1:]) if user_data.full_name and len(user_data.full_name.split()) > 1 else "",
        "phone": None,
        "is_active": True,
        "roles": ["Vendedor"],  # Default role
        "hashed_password": hashed_password,
        "created_at": now_utc(),
        "updated_at": now_utc()
    }
    
    await db.users_extended.insert_one(user_dict)
    audit.set_request_context(request, actor_email=user_data.email)
    await audit.record("users", "create", entity_id=user_data.email, entity_name=user_data.full_name,
                       summary="Registro público de usuario (rol Vendedor)", after=user_dict)
    
    # Return User format for compatibility
    return User(
        email=user_dict["email"],
        full_name=user_data.full_name,
        role=user_data.role,
        is_active=True,
        created_at=datetime.now(timezone.utc)
    )

@router.post("/auth/login")
async def login(credentials: UserLogin, request: Request):
    # Límite de intentos (P1.9): si la cuenta o el equipo están bloqueados, ni se comprueba la contraseña.
    ip = client_ip(request)
    audit.set_request_context(request, actor_email=credentials.email)
    # Los intentos rechazados por bloqueo (429) no se registran uno a uno: quedaría expuesto a
    # llenar la bitácora a fuerza de reintentos. Sí se registra el fallo que provoca el bloqueo.
    await login_throttle.check_not_locked(credentials.email, ip)
    # El intento se reserva antes de comprobar la contraseña: ráfagas en paralelo no superan el límite.
    attempt = await login_throttle.reserve_attempt(credentials.email)

    user = await db.users_extended.find_one({"email": credentials.email})

    if not user or not verify_password(credentials.password, user["hashed_password"]):
        # Mismo mensaje exista o no el email: no se revela qué cuentas existen.
        message = await login_throttle.register_failure(ip, attempt)
        reason = "Email inexistente" if not user else "Contraseña incorrecta"
        await audit.record("auth", "login_failed", entity_id=credentials.email, entity_name=credentials.email,
                           summary=f"{reason} (intento {attempt} de {LOGIN_MAX_ATTEMPTS})", success=False)
        if attempt >= LOGIN_MAX_ATTEMPTS:
            await audit.record("auth", "login_blocked", entity_id=credentials.email, entity_name=credentials.email,
                               summary="Cuenta bloqueada temporalmente por intentos fallidos", success=False)
        raise HTTPException(status_code=401, detail=message)

    # Contraseña correcta: se libera la reserva (aunque la cuenta esté desactivada, no fue un intento fallido).
    await login_throttle.register_success(credentials.email)

    if not user.get("is_active", True):
        await audit.record("auth", "login_failed", entity_id=credentials.email, entity_name=credentials.email,
                           summary="Cuenta desactivada", success=False)
        raise HTTPException(status_code=403, detail="Tu cuenta está desactivada. Contacta a un administrador.")
    
    # P1.11: cada login abre una sesión en el servidor; el token lleva su id.
    sid = await sessions.create_session(user["email"], request)
    access_token = create_access_token(data={"sub": user["email"], "sid": sid})
    audit.set_request_context(session_id=sid)
    await audit.record("auth", "login", entity_id=user["email"], entity_name=f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
                       summary="Inicio de sesión correcto")
    
    # Get user permissions from rbac module
    user_permissions = await get_user_permissions(db, user["email"])
    
    # Convert permissions to simple dict
    permissions_dict = {}
    for module_slug, perms in user_permissions.items():
        permissions_dict[module_slug] = {
            "read": perms.read,
            "create": perms.create,
            "update": perms.update,
            "delete": perms.delete
        }
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "session": session_settings(),
        "user": {
            "email": user["email"],
            "full_name": f"{user['first_name']} {user['last_name']}",
            "first_name": user["first_name"],
            "last_name": user["last_name"],
            "roles": user.get("roles", []),
            "is_active": user.get("is_active", True),
            "must_change_password": bool(user.get("must_change_password")),
            "permissions": permissions_dict
        }
    }

@router.get("/auth/me")
async def get_me(current_user: User = Depends(get_current_user_pending_password)):
    # Get full user data from users_extended
    user = await db.users_extended.find_one({"email": current_user.email}, {"_id": 0, "hashed_password": 0})
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get permissions
    user_permissions = await get_user_permissions(db, user["email"])
    
    permissions_dict = {}
    for module_slug, perms in user_permissions.items():
        permissions_dict[module_slug] = {
            "read": perms.read,
            "create": perms.create,
            "update": perms.update,
            "delete": perms.delete
        }
    
    return {
        "email": user["email"],
        "full_name": f"{user['first_name']} {user['last_name']}",
        "first_name": user["first_name"],
        "last_name": user["last_name"],
        "roles": user.get("roles", []),
        "is_active": user.get("is_active", True),
        "must_change_password": bool(user.get("must_change_password")),
        "permissions": permissions_dict,
        "session": session_settings(),
    }


class ChangeOwnPassword(BaseModel):
    current_password: str
    new_password: str


@router.post("/auth/change-password")
async def change_own_password(data: ChangeOwnPassword, request: Request, current_user: User = Depends(get_current_user_pending_password)):
    """Cambiar la contraseña propia (P1.10). Es lo único que puede hacer quien tiene el cambio pendiente."""
    user = await db.users_extended.find_one({"email": current_user.email})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if not verify_password(data.current_password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="La contraseña actual no es correcta.")
    problem = password_problem(data.new_password)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    if verify_password(data.new_password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="La nueva contraseña debe ser distinta de la actual.")

    hashed = get_password_hash(data.new_password)
    now = now_utc()
    await db.users_extended.update_one(
        {"email": current_user.email},
        {"$set": {"hashed_password": hashed, "must_change_password": False, "updated_at": now}},
    )
    # Colección antigua `users` (compatibilidad): se mantiene en sincronía si existe el registro.
    await db.users.update_one({"email": current_user.email}, {"$set": {"hashed_password": hashed}})
    await login_throttle.unlock_email(current_user.email)
    # P1.11: se cierran las sesiones de los otros equipos; la actual sigue abierta.
    closed = await sessions.revoke_user_sessions(current_user.email, except_sid=current_session_id(request))
    await audit.record("users", "change_password", entity_id=current_user.email, entity_name=current_user.full_name,
                       summary=f"Cambió su propia contraseña; se cerraron {closed} sesión(es) en otros equipos")
    return {"message": "Contraseña actualizada correctamente.", "closed_sessions": closed}


@router.post("/auth/ping")
async def ping_session(request: Request, current_user: User = Depends(get_current_user_pending_password)):
    """Señal de "sigo aquí" del frontend cuando hay actividad (teclado/mouse) sin peticiones."""
    await sessions.touch_session(current_session_id(request))
    return {"ok": True, "session": session_settings()}


@router.post("/auth/logout")
async def logout(request: Request, current_user: User = Depends(get_current_user_pending_password)):
    """Cerrar la sesión actual en el servidor (el token deja de servir)."""
    await sessions.revoke_session(current_session_id(request))
    await audit.record("auth", "logout", entity_id=current_user.email, entity_name=current_user.full_name, summary="Cerró sesión")
    return {"message": "Sesión cerrada."}


@router.post("/auth/logout-all")
async def logout_all(current_user: User = Depends(get_current_user_pending_password)):
    """Cerrar todas las sesiones del usuario, en todos los equipos (incluida la actual)."""
    closed = await sessions.revoke_user_sessions(current_user.email)
    await audit.record("auth", "logout_all", entity_id=current_user.email, entity_name=current_user.full_name,
                       summary=f"Cerró sesión en todos los equipos ({closed} sesión(es))")
    return {"message": f"Se cerraron {closed} sesión(es) en todos los equipos.", "closed_sessions": closed}

