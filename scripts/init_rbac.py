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
    
    # Create system modules
    existing_modules = await db.system_modules.count_documents({})
    if existing_modules == 0:
        modules = []
        for mod in DEFAULT_MODULES:
            mod_dict = mod.copy()
            mod_dict["is_active"] = True
            mod_dict["created_at"] = datetime.now(timezone.utc).isoformat()
            modules.append(mod_dict)
        
        await db.system_modules.insert_many(modules)
        print(f"✅ Creados {len(modules)} módulos del sistema")
    else:
        print(f"⚠️  Ya existen {existing_modules} módulos. Omitiendo creación.")
    
    # Create default roles
    existing_roles = await db.roles.count_documents({})
    if existing_roles == 0:
        for role_data in DEFAULT_ROLES:
            # Create role
            role = {
                "name": role_data["name"],
                "description": role_data["description"],
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.roles.insert_one(role)
            
            # Create permissions
            for module_slug, permissions in role_data["permissions"].items():
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
            
            print(f"✅ Creado rol: {role_data['name']}")
    else:
        print(f"⚠️  Ya existen {existing_roles} roles. Omitiendo creación.")
    
    # Migrate existing users to extended format if needed
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
            print(f"✅ Migrado usuario: {old_user['email']}")
    
    client.close()
    print("🎉 Sistema RBAC inicializado correctamente!")

if __name__ == "__main__":
    asyncio.run(initialize_rbac())
