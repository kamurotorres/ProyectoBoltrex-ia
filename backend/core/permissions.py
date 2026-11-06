"""Autorización RBAC para endpoints.

Uso en un endpoint:

    current_user: User = Depends(require_permission("products", "update"))

o, cuando una pantalla necesita leer datos de otro módulo (p. ej. el POS lee
clientes y productos), aceptar cualquiera de varios permisos:

    current_user: User = Depends(require_any_permission(("clients", "read"), ("pos", "read")))

Los permisos efectivos son la unión (OR) de los permisos de todos los roles del
usuario, guardados en `role_permissions` (ver routers/rbac.get_user_permissions).
"""
from typing import Dict, Tuple

from fastapi import Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from core.database import db
from core.security import get_current_user
from models.auth import User
from rbac import Actions, Permission

VALID_ACTIONS = {Actions.READ, Actions.CREATE, Actions.UPDATE, Actions.DELETE}

PermissionPair = Tuple[str, str]


async def get_user_permissions(database: AsyncIOMotorDatabase, user_email: str) -> Dict[str, Permission]:
    """Permisos efectivos de un usuario: unión (OR) de los permisos de todos sus roles activos."""
    user = await database.users_extended.find_one({"email": user_email}, {"_id": 0, "roles": 1})
    if not user:
        return {}

    role_names = user.get("roles", [])
    if not role_names:
        return {}

    # Un rol desactivado no concede permisos.
    active_roles = await database.roles.find(
        {"name": {"$in": role_names}, "is_active": {"$ne": False}}, {"_id": 0, "name": 1}
    ).to_list(1000)
    active_role_names = [r["name"] for r in active_roles]
    if not active_role_names:
        return {}

    permissions_by_module: Dict[str, Permission] = {}
    role_permissions = await database.role_permissions.find(
        {"role_name": {"$in": active_role_names}}, {"_id": 0}
    ).to_list(10000)

    for rp in role_permissions:
        perms = rp.get("permissions", {})
        current = permissions_by_module.get(rp["module_slug"], Permission())
        permissions_by_module[rp["module_slug"]] = Permission(
            read=current.read or perms.get("read", False),
            create=current.create or perms.get("create", False),
            update=current.update or perms.get("update", False),
            delete=current.delete or perms.get("delete", False),
        )

    return permissions_by_module


def require_any_permission(*checks: PermissionPair):
    """Dependencia que deja pasar si el usuario tiene AL MENOS UNO de los (módulo, acción)."""
    if not checks:
        raise ValueError("require_any_permission necesita al menos un (módulo, acción)")
    for _, action in checks:
        if action not in VALID_ACTIONS:
            raise ValueError(f"Acción RBAC inválida: {action}")

    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        permissions = await get_user_permissions(db, current_user.email)
        for module_slug, action in checks:
            module_perms = permissions.get(module_slug)
            if module_perms is not None and getattr(module_perms, action, False):
                return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para realizar esta acción",
        )

    return dependency


def require_permission(module_slug: str, action: str):
    """Dependencia que exige un permiso concreto sobre un módulo."""
    return require_any_permission((module_slug, action))
