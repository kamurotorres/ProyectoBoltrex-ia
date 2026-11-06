"""Endpoints para el sistema RBAC"""
from fastapi import APIRouter, HTTPException, Depends, Request
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List
from rbac import (
    SystemModule, SystemModuleCreate,
    Role, RoleCreate, RoleUpdate,
    RolePermission, RolePermissionCreate, UserExtended, UserExtendedCreate, UserExtendedUpdate,
    PermissionCheck, Actions
)
from core.database import db
from core.dates import now_utc, as_datetime
from core.permissions import get_user_permissions, require_permission, require_any_permission
from core import user_protection as guard
from models.auth import User
from core.login_throttle import unlock_email
from core.passwords import hash_password, password_problem
from core.sessions import revoke_user_sessions
from core.security import current_session_id
from core import audit
from core.pagination import page_params, paginate, search_filter


# ==================== PERMISSION HELPERS ====================

async def check_permission(
    db: AsyncIOMotorDatabase,
    user_email: str,
    module_slug: str,
    action: str
) -> bool:
    """Verificar si un usuario tiene permiso para una acción en un módulo"""
    permissions = await get_user_permissions(db, user_email)

    if module_slug not in permissions:
        return False

    module_perms = permissions[module_slug]

    if action == Actions.READ:
        return module_perms.read
    elif action == Actions.CREATE:
        return module_perms.create
    elif action == Actions.UPDATE:
        return module_perms.update
    elif action == Actions.DELETE:
        return module_perms.delete

    return False

# ==================== ROUTER ====================
# Mantenimiento fase 2: router normal de módulo (antes se creaba dentro de create_rbac_router(db)).

router = APIRouter(prefix="/rbac", tags=["RBAC"])

# ==================== SYSTEM MODULES ====================

@router.post("/modules", response_model=SystemModule, dependencies=[Depends(require_permission("permissions", "create"))])
async def create_module(module: SystemModuleCreate):
    """Crear un módulo del sistema"""
    existing = await db.system_modules.find_one({"slug": module.slug})
    if existing:
        raise HTTPException(status_code=400, detail=f"Ya existe un módulo con el identificador '{module.slug}'")

    module_dict = module.model_dump()
    module_dict["created_at"] = now_utc()

    await db.system_modules.insert_one(module_dict)
    await audit.record("modules", "create", entity_id=module.slug, entity_name=module_dict.get("name"),
                       summary=f"Creó el módulo '{module.slug}'", after=module_dict)
    return SystemModule(**module_dict)

@router.get("/modules", response_model=List[SystemModule], dependencies=[Depends(require_any_permission(("permissions", "read"), ("roles", "read")))])
async def get_modules():
    """Listar todos los módulos del sistema"""
    modules = await db.system_modules.find({}, {"_id": 0}).to_list(None)
    for mod in modules:
        if isinstance(mod.get('created_at'), str):
            mod['created_at'] = as_datetime(mod['created_at'])
    return modules

@router.put("/modules/{slug}", response_model=SystemModule, dependencies=[Depends(require_permission("permissions", "update"))])
async def update_module(slug: str, module: SystemModuleCreate):
    """Actualizar un módulo del sistema"""
    before = await db.system_modules.find_one({"slug": slug}, {"_id": 0})
    result = await db.system_modules.update_one(
        {"slug": slug},
        {"$set": module.model_dump()}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Módulo no encontrado")

    updated = await db.system_modules.find_one({"slug": slug}, {"_id": 0})
    await audit.record("modules", "update", entity_id=slug, entity_name=updated.get("name"),
                       summary=f"Modificó el módulo '{slug}': {audit.describe_changes(audit.diff(before, updated))}",
                       before=before, after=updated)
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = as_datetime(updated['created_at'])
    return SystemModule(**updated)

@router.delete("/modules/{slug}", dependencies=[Depends(require_permission("permissions", "delete"))])
async def delete_module(slug: str):
    """Eliminar un módulo del sistema"""
    before = await db.system_modules.find_one({"slug": slug}, {"_id": 0})
    result = await db.system_modules.delete_one({"slug": slug})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Módulo no encontrado")
    await audit.record("modules", "delete", entity_id=slug, entity_name=(before or {}).get("name"),
                       summary=f"Eliminó el módulo '{slug}'", before=before)
    return {"message": "Módulo eliminado"}

# ==================== ROLES ====================

@router.post("/roles", response_model=Role, dependencies=[Depends(require_any_permission(("permissions", "create"), ("roles", "create")))])
async def create_role(role: RoleCreate):
    """Crear un rol"""
    existing = await db.roles.find_one({"name": role.name})
    if existing:
        raise HTTPException(status_code=400, detail=f"Ya existe un rol llamado '{role.name}'")

    role_dict = role.model_dump()
    role_dict["created_at"] = now_utc()

    await db.roles.insert_one(role_dict)
    await audit.record("roles", "create", entity_id=role.name, entity_name=role.name,
                       summary=f"Creó el rol '{role.name}'", after=role_dict)
    return Role(**role_dict)

@router.get("/roles", response_model=List[Role], dependencies=[Depends(require_any_permission(("permissions", "read"), ("roles", "read"), ("users", "read")))])
async def get_roles():
    """Listar todos los roles"""
    roles = await db.roles.find({}, {"_id": 0}).to_list(None)
    for role in roles:
        if isinstance(role.get('created_at'), str):
            role['created_at'] = as_datetime(role['created_at'])
    return roles

@router.get("/roles/{name}", response_model=Role, dependencies=[Depends(require_any_permission(("permissions", "read"), ("roles", "read"), ("users", "read")))])
async def get_role(name: str):
    """Obtener un rol por nombre"""
    role = await db.roles.find_one({"name": name}, {"_id": 0})
    if not role:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    if isinstance(role.get('created_at'), str):
        role['created_at'] = as_datetime(role['created_at'])
    return Role(**role)

@router.put("/roles/{name}", response_model=Role)
async def update_role(name: str, role_update: RoleUpdate, current_user: User = Depends(require_any_permission(("permissions", "update"), ("roles", "update")))):
    """Actualizar un rol"""
    update_data = {k: v for k, v in role_update.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No hay datos para actualizar")
    guard.check_role_update(name, update_data)
    before = await db.roles.find_one({"name": name}, {"_id": 0})
    result = await db.roles.update_one(
        {"name": name},
        {"$set": update_data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Rol no encontrado")

    updated = await db.roles.find_one({"name": name}, {"_id": 0})
    await audit.record("roles", "update", entity_id=name, entity_name=name,
                       summary=f"Modificó el rol '{name}': {audit.describe_changes(audit.diff(before, updated))}",
                       before=before, after=updated)
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = as_datetime(updated['created_at'])
    return Role(**updated)

@router.delete("/roles/{name}")
async def delete_role(name: str, current_user: User = Depends(require_any_permission(("permissions", "delete"), ("roles", "delete")))):
    """Eliminar un rol"""
    guard.check_role_delete(name)
    before = await db.roles.find_one({"name": name}, {"_id": 0})
    users_with_role = await db.users_extended.count_documents({"roles": name})
    result = await db.roles.delete_one({"name": name})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    await audit.record("roles", "delete", entity_id=name, entity_name=name,
                       summary=f"Eliminó el rol '{name}' (se quitó a {users_with_role} usuario(s))", before=before)

    # Also delete role permissions and user assignments
    await db.role_permissions.delete_many({"role_name": name})
    await db.users_extended.update_many(
        {"roles": name},
        {"$pull": {"roles": name}}
    )

    return {"message": "Rol eliminado"}

# ==================== PERMISSIONS ====================

@router.post("/permissions", response_model=RolePermission)
async def assign_permission(perm: RolePermissionCreate, current_user: User = Depends(require_permission("permissions", "update"))):
    """Asignar permisos a un rol sobre un módulo"""
    await guard.check_permission_change(current_user.email, perm.role_name)
    # Verify role exists
    role = await db.roles.find_one({"name": perm.role_name})
    if not role:
        raise HTTPException(status_code=404, detail="Rol no encontrado")

    # Verify module exists
    module = await db.system_modules.find_one({"slug": perm.module_slug})
    if not module:
        raise HTTPException(status_code=404, detail="Módulo no encontrado")

    # Update or insert permission
    perm_dict = perm.model_dump()
    perm_dict["created_at"] = now_utc()
    before_perm = await db.role_permissions.find_one(
        {"role_name": perm.role_name, "module_slug": perm.module_slug}, {"_id": 0, "permissions": 1})

    await db.role_permissions.update_one(
        {"role_name": perm.role_name, "module_slug": perm.module_slug},
        {"$set": perm_dict},
        upsert=True
    )
    old = (before_perm or {}).get("permissions") or {}
    new = audit._clean(perm_dict.get("permissions") or {})
    labels = {"read": "ver", "create": "crear", "update": "editar", "delete": "eliminar"}
    granted = [labels.get(k, k) for k, v in new.items() if v and not old.get(k)]
    revoked = [labels.get(k, k) for k, v in old.items() if v and not new.get(k)]
    parts = ([f"concedió {', '.join(granted)}"] if granted else []) + ([f"quitó {', '.join(revoked)}"] if revoked else [])
    if parts:
        await audit.record("permissions", "update", entity_id=f"{perm.role_name} / {perm.module_slug}",
                           entity_name=perm.role_name,
                           summary=f"Permisos del rol '{perm.role_name}' en '{perm.module_slug}': {'; '.join(parts)}",
                           before={"permissions": old}, after={"permissions": new})
    return RolePermission(**perm_dict)

@router.get("/permissions/{role_name}", response_model=List[RolePermission], dependencies=[Depends(require_any_permission(("permissions", "read"), ("roles", "read")))])
async def get_role_permissions(role_name: str):
    """Obtener todos los permisos de un rol"""
    permissions = await db.role_permissions.find(
        {"role_name": role_name},
        {"_id": 0}
    ).to_list(None)

    for perm in permissions:
        if isinstance(perm.get('created_at'), str):
            perm['created_at'] = as_datetime(perm['created_at'])

    return permissions

@router.delete("/permissions/{role_name}/{module_slug}")
async def delete_permission(role_name: str, module_slug: str, current_user: User = Depends(require_permission("permissions", "update"))):
    """Eliminar permisos de un rol sobre un módulo"""
    await guard.check_permission_change(current_user.email, role_name)
    before = await db.role_permissions.find_one({"role_name": role_name, "module_slug": module_slug}, {"_id": 0})
    result = await db.role_permissions.delete_one({
        "role_name": role_name,
        "module_slug": module_slug
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Permiso no encontrado")
    await audit.record("permissions", "delete", entity_id=f"{role_name} / {module_slug}", entity_name=role_name,
                       summary=f"Quitó todos los permisos del rol '{role_name}' en '{module_slug}'", before=before)
    return {"message": "Permiso eliminado"}

# ==================== USERS EXTENDED ====================

@router.post("/users", response_model=UserExtended, dependencies=[Depends(require_permission("users", "create"))])
async def create_user_extended(user: UserExtendedCreate):
    """Crear un usuario"""
    existing = await db.users_extended.find_one({"email": user.email})
    if existing:
        raise HTTPException(status_code=400, detail=f"Ya existe un usuario con el email '{user.email}'")

    problem = password_problem(user.password)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    hashed_password = hash_password(user.password)
    user_dict = user.model_dump(exclude={"password"})
    user_dict["hashed_password"] = hashed_password
    user_dict["roles"] = []
    user_dict["created_at"] = now_utc()
    user_dict["updated_at"] = now_utc()

    await db.users_extended.insert_one(user_dict)
    await audit.record("users", "create", entity_id=user.email, entity_name=f"{user.first_name} {user.last_name}".strip(),
                       summary=f"Creó el usuario {user.email}", after=user_dict)
    return UserExtended(**{k: v for k, v in user_dict.items() if k != "hashed_password"})

@router.get("/users", dependencies=[Depends(require_permission("users", "read"))])
async def get_users_extended(search: str = None, pg: dict = Depends(page_params)):
    """Usuarios paginados (P1.18). Nunca devuelve el hash de la contraseña."""
    query = search_filter(search, ["email", "first_name", "last_name"]) or {}
    return await paginate(db.users_extended, query, [("email", 1)], projection={"_id": 0, "hashed_password": 0}, **pg)

@router.get("/users/{email}", response_model=UserExtended, dependencies=[Depends(require_permission("users", "read"))])
async def get_user_extended(email: str):
    """Obtener un usuario por email"""
    user = await db.users_extended.find_one({"email": email}, {"_id": 0, "hashed_password": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if isinstance(user.get('created_at'), str):
        user['created_at'] = as_datetime(user['created_at'])
    if isinstance(user.get('updated_at'), str):
        user['updated_at'] = as_datetime(user['updated_at'])

    return UserExtended(**user)

@router.put("/users/{email}", response_model=UserExtended)
async def update_user_extended(email: str, user_update: UserExtendedUpdate, request: Request, current_user: User = Depends(require_permission("users", "update"))):
    """Actualizar un usuario"""
    update_data = {k: v for k, v in user_update.model_dump().items() if v is not None}
    # El formulario de edición envía password "" cuando no se quiere cambiar: antes se
    # guardaba como contraseña vacía y cualquiera podía entrar a la cuenta sin contraseña.
    if not (update_data.get("password") or "").strip():
        update_data.pop("password", None)
    # Reglas anti-escalada: no tomar la cuenta de un admin, no auto-desactivarse, no dejar el sistema sin admin.
    await guard.check_user_update(current_user.email, email, update_data)

    password_changed = "password" in update_data
    before = await db.users_extended.find_one({"email": email}, {"_id": 0, "hashed_password": 0})
    if password_changed:
        problem = password_problem(update_data["password"])
        if problem:
            raise HTTPException(status_code=400, detail=problem)
        update_data["hashed_password"] = hash_password(update_data.pop("password"))

    if not update_data:
        raise HTTPException(status_code=400, detail="No hay datos para actualizar")

    update_data["updated_at"] = now_utc()

    result = await db.users_extended.update_one(
        {"email": email},
        {"$set": update_data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if password_changed:
        # Contraseña nueva: se levanta el bloqueo por intentos fallidos de esa cuenta (P1.9).
        await unlock_email(email)
    if password_changed or update_data.get("is_active") is False:
        # P1.11: contraseña nueva o usuario desactivado → se cierran sus sesiones abiertas
        # (si se edita a sí mismo, conserva la sesión desde la que lo hizo).
        await revoke_user_sessions(email, except_sid=current_session_id(request) if email == current_user.email else None)

    updated = await db.users_extended.find_one({"email": email}, {"_id": 0, "hashed_password": 0})
    changes = audit.diff(before, updated)
    parts = []
    if changes:
        parts.append(audit.describe_changes(changes))
    if password_changed:
        parts.append("cambió la contraseña" + (" (sesiones del usuario cerradas)" if email != current_user.email else ""))
    if update_data.get("is_active") is False and (before or {}).get("is_active", True):
        parts.append("usuario desactivado (sesiones cerradas)")
    if parts:
        full = f"{updated.get('first_name', '')} {updated.get('last_name', '')}".strip()
        await audit.record("users", "change_password" if password_changed and not changes else "update",
                           entity_id=email, entity_name=full,
                           summary=f"Modificó el usuario {email}: " + "; ".join(parts),
                           before=before, after=updated, details={"password_changed": password_changed})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = as_datetime(updated['created_at'])
    if isinstance(updated.get('updated_at'), str):
        updated['updated_at'] = as_datetime(updated['updated_at'])

    return UserExtended(**updated)

@router.delete("/users/{email}")
async def delete_user_extended(email: str, current_user: User = Depends(require_permission("users", "delete"))):
    """Eliminar un usuario"""
    await guard.check_user_delete(current_user.email, email)
    before = await db.users_extended.find_one({"email": email}, {"_id": 0, "hashed_password": 0})
    result = await db.users_extended.delete_one({"email": email})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    await revoke_user_sessions(email)
    await audit.record("users", "delete", entity_id=email,
                       entity_name=f"{(before or {}).get('first_name', '')} {(before or {}).get('last_name', '')}".strip(),
                       summary=f"Eliminó el usuario {email}", before=before)
    return {"message": "Usuario eliminado"}

# ==================== USER ROLE ASSIGNMENT ====================

@router.post("/users/{email}/roles")
async def assign_roles_to_user(email: str, assignment: List[str], request: Request, current_user: User = Depends(require_permission("users", "update"))):
    """Asignar roles a un usuario"""
    # Verify user exists
    user = await db.users_extended.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    assignment = list(dict.fromkeys(assignment))  # sin duplicados, conservando el orden

    # Verify all roles exist
    for role_name in assignment:
        role = await db.roles.find_one({"name": role_name})
        if not role:
            raise HTTPException(status_code=404, detail=f"Rol '{role_name}' no encontrado")

    # Reglas anti-escalada: solo un admin da/quita Administrador, nadie se quita su propio rol admin, etc.
    await guard.check_role_assignment(current_user.email, email, assignment)

    # Update user roles
    await db.users_extended.update_one(
        {"email": email},
        {"$set": {"roles": assignment, "updated_at": now_utc()}}
    )

    # P1.11: si los roles cambiaron, el usuario debe volver a entrar para ver su menú nuevo.
    if sorted(user.get("roles", [])) != sorted(assignment):
        await revoke_user_sessions(email, except_sid=current_session_id(request) if email == current_user.email else None)
        old_roles = user.get("roles", [])
        added = [r for r in assignment if r not in old_roles]
        removed = [r for r in old_roles if r not in assignment]
        parts = ([f"+{', +'.join(added)}"] if added else []) + ([f"-{', -'.join(removed)}"] if removed else [])
        await audit.record("users", "assign_roles", entity_id=email,
                           entity_name=f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
                           summary=f"Roles de {email}: {' '.join(parts)} (sesiones del usuario cerradas)",
                           before={"roles": old_roles}, after={"roles": assignment})

    return {"message": "Roles asignados", "roles": assignment}

@router.get("/users/{email}/permissions", dependencies=[Depends(require_permission("users", "read"))])
async def get_user_all_permissions(email: str):
    """Obtener todos los permisos de un usuario"""
    permissions = await get_user_permissions(db, email)
    return {"email": email, "permissions": {k: v.model_dump() for k, v in permissions.items()}}

@router.post("/users/check-permission", response_model=PermissionCheck, dependencies=[Depends(require_permission("users", "read"))])
async def check_user_permission(user_email: str, module_slug: str, action: str):
    """Verificar si un usuario tiene permiso para una acción"""
    user = await db.users_extended.find_one({"email": user_email}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    has_perm = await check_permission(db, user_email, module_slug, action)

    return PermissionCheck(
        has_permission=has_perm,
        user_email=user_email,
        module_slug=module_slug,
        action=action,
        roles_checked=user.get("roles", [])
    )

