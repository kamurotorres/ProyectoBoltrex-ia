"""Reglas que impiden la escalada de privilegios y dejar el sistema sin administrador (backlog P1.8).

Se aplican ADEMÁS del permiso RBAC del endpoint: tener `users:update` permite gestionar
usuarios, pero no convertirse en Administrador ni tomar la cuenta de uno.

Reglas:
  1. Solo un Administrador asigna o quita el rol Administrador.
  2. Solo un Administrador modifica (datos, contraseña, estado, roles) o elimina a otro Administrador.
  3. Nadie se desactiva, se elimina ni se quita el rol Administrador a sí mismo;
     un usuario que no es Administrador tampoco puede cambiar sus propios roles.
  4. Nunca queda el sistema sin ningún Administrador activo.
  5. PROTECTED_ADMIN_EMAIL no se elimina, no se desactiva y siempre conserva el rol Administrador.
  6. El rol Administrador no se elimina, no se desactiva y sus permisos no se modifican.
  7. Quien no es Administrador no modifica los permisos de un rol que él mismo tiene.

Cada violación lanza HTTPException con un mensaje en español para mostrar al usuario.
"""
from typing import Iterable, Optional

from fastapi import HTTPException, status

from core.config import PROTECTED_ADMIN_EMAIL
from core.database import db

ADMIN_ROLE = "Administrador"


def _deny(message: str, code: int = status.HTTP_400_BAD_REQUEST):
    raise HTTPException(status_code=code, detail=message)


async def _user(email: str) -> Optional[dict]:
    return await db.users_extended.find_one({"email": email}, {"_id": 0, "email": 1, "roles": 1, "is_active": 1})


def _is_admin(user: Optional[dict]) -> bool:
    return bool(user) and ADMIN_ROLE in (user.get("roles") or [])


async def actor_is_admin(actor_email: str) -> bool:
    return _is_admin(await _user(actor_email))


async def _other_active_admins(exclude_email: str) -> int:
    return await db.users_extended.count_documents(
        {"roles": ADMIN_ROLE, "is_active": {"$ne": False}, "email": {"$ne": exclude_email}}
    )


async def _ensure_not_last_admin(target: dict, action: str):
    """`action`: texto para el mensaje, p. ej. 'desactivar', 'eliminar', 'quitar el rol Administrador a'."""
    if _is_admin(target) and target.get("is_active", True) and await _other_active_admins(target["email"]) == 0:
        _deny(f"No se puede {action} '{target['email']}': es el único Administrador activo del sistema. "
              f"Asigna el rol Administrador a otro usuario activo primero.")


async def _load_target(target_email: str) -> dict:
    target = await _user(target_email)
    if not target:
        _deny("Usuario no encontrado", status.HTTP_404_NOT_FOUND)
    return target


async def _ensure_can_manage(actor_email: str, target: dict):
    """Regla 2: solo un Administrador gestiona a otro Administrador."""
    if _is_admin(target) and target["email"] != actor_email and not await actor_is_admin(actor_email):
        _deny("Solo un Administrador puede modificar la cuenta de otro Administrador.", status.HTTP_403_FORBIDDEN)


# ==================== USUARIOS ====================

async def check_user_update(actor_email: str, target_email: str, changes: dict):
    target = await _load_target(target_email)
    await _ensure_can_manage(actor_email, target)

    if changes.get("is_active") is False and target.get("is_active", True):
        if target_email == actor_email:
            _deny("No puedes desactivar tu propia cuenta.")
        if target_email == PROTECTED_ADMIN_EMAIL:
            _deny(f"El usuario {PROTECTED_ADMIN_EMAIL} está protegido: no se puede desactivar.")
        await _ensure_not_last_admin(target, "desactivar")


async def check_user_delete(actor_email: str, target_email: str):
    target = await _load_target(target_email)
    if target_email == actor_email:
        _deny("No puedes eliminar tu propia cuenta.")
    if target_email == PROTECTED_ADMIN_EMAIL:
        _deny(f"El usuario {PROTECTED_ADMIN_EMAIL} está protegido: no se puede eliminar.")
    await _ensure_can_manage(actor_email, target)
    await _ensure_not_last_admin(target, "eliminar")


async def check_role_assignment(actor_email: str, target_email: str, new_roles: Iterable[str]):
    target = await _load_target(target_email)
    new_roles = set(new_roles)
    old_roles = set(target.get("roles") or [])
    if new_roles == old_roles:
        return

    is_admin_actor = await actor_is_admin(actor_email)
    await _ensure_can_manage(actor_email, target)

    if target_email == actor_email and not is_admin_actor:
        _deny("No puedes modificar tus propios roles. Pídeselo a un Administrador.", status.HTTP_403_FORBIDDEN)

    admin_added = ADMIN_ROLE in new_roles and ADMIN_ROLE not in old_roles
    admin_removed = ADMIN_ROLE in old_roles and ADMIN_ROLE not in new_roles
    if (admin_added or admin_removed) and not is_admin_actor:
        _deny("Solo un Administrador puede asignar o quitar el rol Administrador.", status.HTTP_403_FORBIDDEN)

    if admin_removed:
        if target_email == actor_email:
            _deny("No puedes quitarte tu propio rol de Administrador.")
        if target_email == PROTECTED_ADMIN_EMAIL:
            _deny(f"El usuario {PROTECTED_ADMIN_EMAIL} está protegido: siempre conserva el rol Administrador.")
        await _ensure_not_last_admin(target, "quitar el rol Administrador a")


# ==================== ROLES Y PERMISOS ====================

_ADMIN_ROLE_LOCKED = f"El rol {ADMIN_ROLE} siempre tiene acceso total: no se puede desactivar, eliminar ni cambiar sus permisos."


def check_role_update(role_name: str, changes: dict):
    if role_name == ADMIN_ROLE and changes.get("is_active") is False:
        _deny(_ADMIN_ROLE_LOCKED)


def check_role_delete(role_name: str):
    if role_name == ADMIN_ROLE:
        _deny(_ADMIN_ROLE_LOCKED)


async def check_permission_change(actor_email: str, role_name: str):
    if role_name == ADMIN_ROLE:
        _deny(_ADMIN_ROLE_LOCKED)
    actor = await _user(actor_email)
    if not _is_admin(actor) and role_name in (actor or {}).get("roles", []):
        _deny("No puedes modificar los permisos de un rol que tienes asignado. Pídeselo a un Administrador.",
              status.HTTP_403_FORBIDDEN)
