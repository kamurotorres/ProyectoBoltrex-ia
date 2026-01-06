"""Endpoints para el sistema RBAC"""
from fastapi import APIRouter, HTTPException, Depends, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Dict, Any
from datetime import datetime, timezone
from rbac import (
    SystemModule, SystemModuleCreate,
    Role, RoleCreate, RoleUpdate,
    RolePermission, RolePermissionCreate, Permission,
    UserExtended, UserExtendedCreate, UserExtendedUpdate,
    UserRoleAssignment, PermissionCheck, Actions,
    DEFAULT_MODULES, DEFAULT_ROLES
)
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ==================== PERMISSION HELPERS ====================

async def get_user_permissions(db: AsyncIOMotorDatabase, user_email: str) -> Dict[str, Permission]:
    """Obtener todos los permisos de un usuario basado en sus roles"""
    # Get user roles
    user = await db.users_extended.find_one({"email": user_email}, {"_id": 0})
    if not user:
        return {}
    
    user_roles = user.get("roles", [])
    if not user_roles:
        return {}
    
    # Get permissions for all roles
    permissions_by_module = {}
    
    for role_name in user_roles:
        role_permissions = await db.role_permissions.find(
            {"role_name": role_name},
            {"_id": 0}
        ).to_list(1000)
        
        for rp in role_permissions:
            module_slug = rp["module_slug"]
            perms = rp["permissions"]
            
            if module_slug not in permissions_by_module:
                permissions_by_module[module_slug] = Permission(
                    read=perms.get("read", False),
                    create=perms.get("create", False),
                    update=perms.get("update", False),
                    delete=perms.get("delete", False)
                )
            else:
                # Merge permissions (OR logic - if any role has permission, user has it)
                current = permissions_by_module[module_slug]
                permissions_by_module[module_slug] = Permission(
                    read=current.read or perms.get("read", False),
                    create=current.create or perms.get("create", False),
                    update=current.update or perms.get("update", False),
                    delete=current.delete or perms.get("delete", False)
                )
    
    return permissions_by_module

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

def create_rbac_router(db: AsyncIOMotorDatabase) -> APIRouter:
    router = APIRouter(prefix="/rbac", tags=["RBAC"])
    
    # ==================== SYSTEM MODULES ====================
    
    @router.post("/modules", response_model=SystemModule)
    async def create_module(module: SystemModuleCreate):
        """Crear un módulo del sistema"""
        existing = await db.system_modules.find_one({"slug": module.slug})
        if existing:
            raise HTTPException(status_code=400, detail="Módulo ya existe")
        
        module_dict = module.model_dump()
        module_dict["created_at"] = datetime.now(timezone.utc).isoformat()
        
        await db.system_modules.insert_one(module_dict)
        return SystemModule(**module_dict)
    
    @router.get("/modules", response_model=List[SystemModule])
    async def get_modules():
        """Listar todos los módulos del sistema"""
        modules = await db.system_modules.find({}, {"_id": 0}).to_list(1000)
        for mod in modules:
            if isinstance(mod.get('created_at'), str):
                mod['created_at'] = datetime.fromisoformat(mod['created_at'])
        return modules
    
    @router.put("/modules/{slug}", response_model=SystemModule)
    async def update_module(slug: str, module: SystemModuleCreate):
        """Actualizar un módulo del sistema"""
        result = await db.system_modules.update_one(
            {"slug": slug},
            {"$set": module.model_dump()}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Módulo no encontrado")
        
        updated = await db.system_modules.find_one({"slug": slug}, {"_id": 0})
        if isinstance(updated.get('created_at'), str):
            updated['created_at'] = datetime.fromisoformat(updated['created_at'])
        return SystemModule(**updated)
    
    @router.delete("/modules/{slug}")
    async def delete_module(slug: str):
        """Eliminar un módulo del sistema"""
        result = await db.system_modules.delete_one({"slug": slug})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Módulo no encontrado")
        return {"message": "Módulo eliminado"}
    
    # ==================== ROLES ====================
    
    @router.post("/roles", response_model=Role)
    async def create_role(role: RoleCreate):
        """Crear un rol"""
        existing = await db.roles.find_one({"name": role.name})
        if existing:
            raise HTTPException(status_code=400, detail="Rol ya existe")
        
        role_dict = role.model_dump()
        role_dict["created_at"] = datetime.now(timezone.utc).isoformat()
        
        await db.roles.insert_one(role_dict)
        return Role(**role_dict)
    
    @router.get("/roles", response_model=List[Role])
    async def get_roles():
        """Listar todos los roles"""
        roles = await db.roles.find({}, {"_id": 0}).to_list(1000)
        for role in roles:
            if isinstance(role.get('created_at'), str):
                role['created_at'] = datetime.fromisoformat(role['created_at'])
        return roles
    
    @router.get("/roles/{name}", response_model=Role)
    async def get_role(name: str):
        """Obtener un rol por nombre"""
        role = await db.roles.find_one({"name": name}, {"_id": 0})
        if not role:
            raise HTTPException(status_code=404, detail="Rol no encontrado")
        if isinstance(role.get('created_at'), str):
            role['created_at'] = datetime.fromisoformat(role['created_at'])
        return Role(**role)
    
    @router.put("/roles/{name}", response_model=Role)
    async def update_role(name: str, role_update: RoleUpdate):
        """Actualizar un rol"""
        update_data = {k: v for k, v in role_update.model_dump().items() if v is not None}
        if not update_data:
            raise HTTPException(status_code=400, detail="No hay datos para actualizar")
        
        result = await db.roles.update_one(
            {"name": name},
            {"$set": update_data}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Rol no encontrado")
        
        updated = await db.roles.find_one({"name": name}, {"_id": 0})
        if isinstance(updated.get('created_at'), str):
            updated['created_at'] = datetime.fromisoformat(updated['created_at'])
        return Role(**updated)
    
    @router.delete("/roles/{name}")
    async def delete_role(name: str):
        """Eliminar un rol"""
        result = await db.roles.delete_one({"name": name})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Rol no encontrado")
        
        # Also delete role permissions and user assignments
        await db.role_permissions.delete_many({"role_name": name})
        await db.users_extended.update_many(
            {"roles": name},
            {"$pull": {"roles": name}}
        )
        
        return {"message": "Rol eliminado"}
    
    # ==================== PERMISSIONS ====================
    
    @router.post("/permissions", response_model=RolePermission)
    async def assign_permission(perm: RolePermissionCreate):
        """Asignar permisos a un rol sobre un módulo"""
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
        perm_dict["created_at"] = datetime.now(timezone.utc).isoformat()
        
        await db.role_permissions.update_one(
            {"role_name": perm.role_name, "module_slug": perm.module_slug},
            {"$set": perm_dict},
            upsert=True
        )
        
        return RolePermission(**perm_dict)
    
    @router.get("/permissions/{role_name}", response_model=List[RolePermission])
    async def get_role_permissions(role_name: str):
        """Obtener todos los permisos de un rol"""
        permissions = await db.role_permissions.find(
            {"role_name": role_name},
            {"_id": 0}
        ).to_list(1000)
        
        for perm in permissions:
            if isinstance(perm.get('created_at'), str):
                perm['created_at'] = datetime.fromisoformat(perm['created_at'])
        
        return permissions
    
    @router.delete("/permissions/{role_name}/{module_slug}")
    async def delete_permission(role_name: str, module_slug: str):
        """Eliminar permisos de un rol sobre un módulo"""
        result = await db.role_permissions.delete_one({
            "role_name": role_name,
            "module_slug": module_slug
        })
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Permiso no encontrado")
        return {"message": "Permiso eliminado"}
    
    # ==================== USERS EXTENDED ====================
    
    @router.post("/users", response_model=UserExtended)
    async def create_user_extended(user: UserExtendedCreate):
        """Crear un usuario"""
        existing = await db.users_extended.find_one({"email": user.email})
        if existing:
            raise HTTPException(status_code=400, detail="Usuario ya existe")
        
        hashed_password = pwd_context.hash(user.password)
        user_dict = user.model_dump(exclude={"password"})
        user_dict["hashed_password"] = hashed_password
        user_dict["roles"] = []
        user_dict["created_at"] = datetime.now(timezone.utc).isoformat()
        user_dict["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        await db.users_extended.insert_one(user_dict)
        
        return UserExtended(**{k: v for k, v in user_dict.items() if k != "hashed_password"})
    
    @router.get("/users", response_model=List[UserExtended])
    async def get_users_extended(search: str = None):
        """Listar todos los usuarios"""
        query = {}
        if search:
            query = {"$or": [
                {"email": {"$regex": search, "$options": "i"}},
                {"first_name": {"$regex": search, "$options": "i"}},
                {"last_name": {"$regex": search, "$options": "i"}}
            ]}
        
        users = await db.users_extended.find(query, {"_id": 0, "hashed_password": 0}).to_list(1000)
        
        for user in users:
            if isinstance(user.get('created_at'), str):
                user['created_at'] = datetime.fromisoformat(user['created_at'])
            if isinstance(user.get('updated_at'), str):
                user['updated_at'] = datetime.fromisoformat(user['updated_at'])
        
        return users
    
    @router.get("/users/{email}", response_model=UserExtended)
    async def get_user_extended(email: str):
        """Obtener un usuario por email"""
        user = await db.users_extended.find_one({"email": email}, {"_id": 0, "hashed_password": 0})
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        if isinstance(user.get('created_at'), str):
            user['created_at'] = datetime.fromisoformat(user['created_at'])
        if isinstance(user.get('updated_at'), str):
            user['updated_at'] = datetime.fromisoformat(user['updated_at'])
        
        return UserExtended(**user)
    
    @router.put("/users/{email}", response_model=UserExtended)
    async def update_user_extended(email: str, user_update: UserExtendedUpdate):
        """Actualizar un usuario"""
        update_data = {k: v for k, v in user_update.model_dump().items() if v is not None}
        
        if "password" in update_data:
            update_data["hashed_password"] = pwd_context.hash(update_data.pop("password"))
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No hay datos para actualizar")
        
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        result = await db.users_extended.update_one(
            {"email": email},
            {"$set": update_data}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        updated = await db.users_extended.find_one({"email": email}, {"_id": 0, "hashed_password": 0})
        if isinstance(updated.get('created_at'), str):
            updated['created_at'] = datetime.fromisoformat(updated['created_at'])
        if isinstance(updated.get('updated_at'), str):
            updated['updated_at'] = datetime.fromisoformat(updated['updated_at'])
        
        return UserExtended(**updated)
    
    @router.delete("/users/{email}")
    async def delete_user_extended(email: str):
        """Eliminar un usuario"""
        result = await db.users_extended.delete_one({"email": email})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        return {"message": "Usuario eliminado"}
    
    # ==================== USER ROLE ASSIGNMENT ====================
    
    @router.post("/users/{email}/roles")
    async def assign_roles_to_user(email: str, assignment: List[str]):
        """Asignar roles a un usuario"""
        # Verify user exists
        user = await db.users_extended.find_one({"email": email})
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # Verify all roles exist
        for role_name in assignment:
            role = await db.roles.find_one({"name": role_name})
            if not role:
                raise HTTPException(status_code=404, detail=f"Rol '{role_name}' no encontrado")
        
        # Update user roles
        await db.users_extended.update_one(
            {"email": email},
            {"$set": {"roles": assignment, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        
        return {"message": "Roles asignados", "roles": assignment}
    
    @router.get("/users/{email}/permissions")
    async def get_user_all_permissions(email: str):
        """Obtener todos los permisos de un usuario"""
        permissions = await get_user_permissions(db, email)
        return {"email": email, "permissions": {k: v.model_dump() for k, v in permissions.items()}}
    
    @router.post("/users/check-permission", response_model=PermissionCheck)
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
    
    return router
