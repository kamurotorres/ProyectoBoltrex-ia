#!/usr/bin/env python3
"""Inicializar módulos y roles del sistema RBAC"""
import asyncio
import sys
import os
sys.path.append('/app/backend')

from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
from dotenv import load_dotenv
from pathlib import Path
from passlib.context import CryptContext
from rbac import DEFAULT_MODULES, DEFAULT_ROLES

# Load environment
ROOT_DIR = Path('/app/backend')
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
db_name = os.environ['DB_NAME']

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def initialize_rbac():
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    now = datetime.now(timezone.utc).isoformat()
    
    print("Inicializando sistema RBAC...")
    
    # === 1. System Modules ===
    print("\nVerificando modulos del sistema...")
    modules_created = 0
    for mod in DEFAULT_MODULES:
        existing = await db.system_modules.find_one({"slug": mod["slug"]})
        if not existing:
            mod_dict = mod.copy()
            mod_dict["is_active"] = True
            mod_dict["created_at"] = now
            await db.system_modules.insert_one(mod_dict)
            print(f"  Creado modulo: {mod['name']}")
            modules_created += 1
    print(f"  Modulos: {modules_created} creados, {len(DEFAULT_MODULES) - modules_created} existentes")
    
    # === 2. Roles & Permissions ===
    print("\nVerificando roles...")
    for role_data in DEFAULT_ROLES:
        existing_role = await db.roles.find_one({"name": role_data["name"]})
        if not existing_role:
            role = {
                "name": role_data["name"],
                "description": role_data["description"],
                "is_active": True,
                "created_at": now
            }
            await db.roles.insert_one(role)
            print(f"  Creado rol: {role_data['name']}")
        
        for module_slug, permissions in role_data["permissions"].items():
            existing_perm = await db.role_permissions.find_one({
                "role_name": role_data["name"],
                "module_slug": module_slug
            })
            if not existing_perm:
                perm_doc = {
                    "role_name": role_data["name"],
                    "module_slug": module_slug,
                    "permissions": {
                        "read": permissions.read,
                        "create": permissions.create,
                        "update": permissions.update,
                        "delete": permissions.delete
                    },
                    "created_at": now
                }
                await db.role_permissions.insert_one(perm_doc)
                print(f"    Permisos '{module_slug}' asignados a {role_data['name']}")
    
    # === 3. Admin User ===
    print("\nVerificando usuario admin...")
    admin_exists = await db.users_extended.find_one({"email": "admin@boltrex.com"})
    if not admin_exists:
        hashed_pw = pwd_context.hash("admin")
        admin_user = {
            "email": "admin@boltrex.com",
            "first_name": "Admin",
            "last_name": "Boltrex",
            "phone": None,
            "is_active": True,
            "roles": ["Administrador"],
            "hashed_password": hashed_pw,
            "created_at": now,
            "updated_at": now
        }
        await db.users_extended.insert_one(admin_user)
        legacy_user = {
            "email": "admin@boltrex.com",
            "full_name": "Admin Boltrex",
            "role": "admin",
            "hashed_password": hashed_pw,
            "is_active": True,
            "created_at": now
        }
        await db.users.insert_one(legacy_user)
        print("  Creado usuario admin: admin@boltrex.com / admin")
    else:
        print("  Usuario admin ya existe")
    
    # === 4. Migrate legacy users ===
    print("\nVerificando migracion de usuarios legacy...")
    old_users = await db.users.find({}, {"_id": 0}).to_list(1000)
    migrated = 0
    for old_user in old_users:
        existing_extended = await db.users_extended.find_one({"email": old_user["email"]})
        if not existing_extended:
            extended_user = {
                "email": old_user["email"],
                "first_name": old_user.get("full_name", "").split()[0] if old_user.get("full_name") else "Usuario",
                "last_name": " ".join(old_user.get("full_name", "").split()[1:]) if old_user.get("full_name") and len(old_user.get("full_name", "").split()) > 1 else "",
                "phone": None,
                "is_active": old_user.get("is_active", True),
                "roles": ["Administrador"] if old_user.get("role") == "admin" else ["Vendedor"],
                "hashed_password": old_user.get("hashed_password"),
                "created_at": old_user.get("created_at", now),
                "updated_at": now
            }
            await db.users_extended.insert_one(extended_user)
            print(f"  Migrado usuario: {old_user['email']}")
            migrated += 1
    if migrated == 0:
        print("  No hay usuarios para migrar")
    
    client.close()
    print(f"\nSistema RBAC inicializado correctamente!")
    print(f"  Total modulos: {len(DEFAULT_MODULES)}")
    print(f"  Total roles: {len(DEFAULT_ROLES)}")

if __name__ == "__main__":
    asyncio.run(initialize_rbac())
