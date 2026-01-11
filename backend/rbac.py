"""
Sistema de Control de Acceso Basado en Roles (RBAC)
"""
from fastapi import HTTPException, Depends
from typing import List, Optional, Dict, Any
from functools import wraps
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from datetime import datetime, timezone

# ==================== MODELS ====================

class SystemModule(BaseModel):
    """Módulo del sistema"""
    model_config = ConfigDict(extra="ignore")
    name: str
    slug: str  # Identificador único
    description: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SystemModuleCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    is_active: bool = True

class Role(BaseModel):
    """Rol del sistema"""
    model_config = ConfigDict(extra="ignore")
    name: str
    description: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class RoleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True

class RoleUpdate(BaseModel):
    description: Optional[str] = None
    is_active: Optional[bool] = None

class Permission(BaseModel):
    """Permisos CRUD"""
    read: bool = False
    create: bool = False
    update: bool = False
    delete: bool = False

class RolePermission(BaseModel):
    """Permisos de un rol sobre un módulo"""
    model_config = ConfigDict(extra="ignore")
    role_name: str
    module_slug: str
    permissions: Permission
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class RolePermissionCreate(BaseModel):
    role_name: str
    module_slug: str
    permissions: Permission

class UserExtended(BaseModel):
    """Usuario extendido con más campos"""
    model_config = ConfigDict(extra="ignore")
    email: EmailStr
    first_name: str
    last_name: str
    phone: Optional[str] = None
    is_active: bool = True
    roles: List[str] = []  # Lista de nombres de roles
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserExtendedCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    is_active: bool = True

class UserExtendedUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None

class UserRoleAssignment(BaseModel):
    user_email: str
    role_names: List[str]

class PermissionCheck(BaseModel):
    """Resultado de validación de permisos"""
    has_permission: bool
    user_email: str
    module_slug: str
    action: str
    roles_checked: List[str]

# ==================== PERMISSION CONSTANTS ====================

class Actions:
    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"

# ==================== DEFAULT MODULES ====================

DEFAULT_MODULES = [
    {"name": "Dashboard", "slug": "dashboard", "description": "Panel principal de estadísticas"},
    {"name": "Productos", "slug": "products", "description": "Gestión de productos"},
    {"name": "Categorías", "slug": "categories", "description": "Gestión de categorías"},
    {"name": "Clientes", "slug": "clients", "description": "Gestión de clientes"},
    {"name": "Proveedores", "slug": "suppliers", "description": "Gestión de proveedores"},
    {"name": "Compras", "slug": "purchases", "description": "Registro de compras"},
    {"name": "Devoluciones", "slug": "returns", "description": "Gestión de devoluciones"},
    {"name": "POS", "slug": "pos", "description": "Punto de venta"},
    {"name": "Facturas", "slug": "invoices", "description": "Listado y consulta de facturas"},
    {"name": "Config. Tickets", "slug": "ticket-config", "description": "Configuración de tickets de impresión"},
    {"name": "Inventario", "slug": "inventory", "description": "Control de inventario"},
    {"name": "Reportes", "slug": "reports", "description": "Reportes y estadísticas"},
    {"name": "Importar", "slug": "import", "description": "Importación de datos"},
    {"name": "Usuarios", "slug": "users", "description": "Gestión de usuarios"},
    {"name": "Roles", "slug": "roles", "description": "Gestión de roles"},
    {"name": "Permisos", "slug": "permissions", "description": "Gestión de permisos"}
]

# ==================== DEFAULT ROLES ====================

DEFAULT_ROLES = [
    {
        "name": "Administrador",
        "description": "Acceso total al sistema",
        "permissions": {module["slug"]: Permission(read=True, create=True, update=True, delete=True) for module in DEFAULT_MODULES}
    },
    {
        "name": "Vendedor",
        "description": "Acceso a ventas y consultas",
        "permissions": {
            "dashboard": Permission(read=True),
            "products": Permission(read=True),
            "categories": Permission(read=True),
            "clients": Permission(read=True, create=True, update=True),
            "pos": Permission(read=True, create=True),
            "invoices": Permission(read=True),
            "inventory": Permission(read=True),
            "reports": Permission(read=True)
        }
    },
    {
        "name": "Supervisor",
        "description": "Supervisión de operaciones",
        "permissions": {
            "dashboard": Permission(read=True),
            "products": Permission(read=True, create=True, update=True),
            "categories": Permission(read=True, create=True, update=True),
            "clients": Permission(read=True, create=True, update=True),
            "suppliers": Permission(read=True, create=True, update=True),
            "purchases": Permission(read=True, create=True),
            "returns": Permission(read=True, create=True),
            "pos": Permission(read=True, create=True),
            "invoices": Permission(read=True),
            "ticket-config": Permission(read=True, update=True),
            "inventory": Permission(read=True),
            "reports": Permission(read=True)
        }
    }
]
