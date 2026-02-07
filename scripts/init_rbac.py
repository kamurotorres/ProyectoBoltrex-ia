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
from rbac import DEFAULT_MODULES, DEFAULT_ROLES

# Load environment
ROOT_DIR = Path('/app/backend')
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
db_name = os.environ['DB_NAME']

async def initialize_rbac():
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    print("🔐 Inicializando sistema RBAC...")
    
    # Create or update system modules
    print("\n📦 Verificando módulos del sistema...")
    modules_created = 0
    modules_existing = 0
    for mod in DEFAULT_MODULES:
        existing = await db.system_modules.find_one({"slug": mod["slug"]})
        if not existing:
            mod_dict = mod.copy()
            mod_dict["is_active"] = True
            mod_dict["created_at"] = datetime.now(timezone.utc).isoformat()
            await db.system_modules.insert_one(mod_dict)
            print(f"  ✅ Creado módulo: {mod['name']}")
            modules_created += 1
        else:
            modules_existing += 1
    
    print(f"  📊 Módulos: {modules_created} creados, {modules_existing} existentes")
    
    # Create default roles if they don't exist
    print("\n👥 Verificando roles...")
    for role_data in DEFAULT_ROLES:
        existing_role = await db.roles.find_one({"name": role_data["name"]})
        if not existing_role:
            # Create role
            role = {
                "name": role_data["name"],
                "description": role_data["description"],
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.roles.insert_one(role)
            print(f"  ✅ Creado rol: {role_data['name']}")
        
        # Create or update permissions for this role
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
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                await db.role_permissions.insert_one(perm_doc)
                print(f"    ✅ Permisos '{module_slug}' asignados a {role_data['name']}")
    
    # Migrate existing users to extended format if needed
    print("\n👤 Verificando usuarios...")
    old_users = await db.users.find({}, {"_id": 0}).to_list(1000)
    for old_user in old_users:
        existing_extended = await db.users_extended.find_one({"email": old_user["email"]})
        if not existing_extended:
            # Migrate to extended format
            extended_user = {
                "email": old_user["email"],
                "first_name": old_user.get("full_name", "").split()[0] if old_user.get("full_name") else "Usuario",
                "last_name": " ".join(old_user.get("full_name", "").split()[1:]) if old_user.get("full_name") and len(old_user.get("full_name", "").split()) > 1 else "",
                "phone": None,
                "is_active": old_user.get("is_active", True),
                "roles": ["Administrador"] if old_user.get("role") == "admin" else ["Vendedor"],
                "hashed_password": old_user.get("hashed_password"),
                "created_at": old_user.get("created_at", datetime.now(timezone.utc).isoformat()),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            await db.users_extended.insert_one(extended_user)
            print(f"  ✅ Migrado usuario: {old_user['email']}")
    
    client.close()
    print("\n🎉 Sistema RBAC inicializado correctamente!")
    print(f"   Total módulos configurados: {len(DEFAULT_MODULES)}")
    print(f"   Total roles configurados: {len(DEFAULT_ROLES)}")

if __name__ == "__main__":
    asyncio.run(initialize_rbac())
