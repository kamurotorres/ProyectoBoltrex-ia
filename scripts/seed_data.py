#!/usr/bin/env python3
"""Seed initial data for Boltrex"""
import asyncio
import sys
import os
from pathlib import Path

# Dynamic path resolution (works on Linux, Windows, Docker)
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent / 'backend'
sys.path.insert(0, str(BACKEND_DIR))

from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
from dotenv import load_dotenv
from passlib.context import CryptContext

# Load environment
load_dotenv(BACKEND_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
db_name = os.environ['DB_NAME']

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def seed_database():
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    print("Seeding database...")
    now = datetime.now(timezone.utc).isoformat()
    
    # === 1. Admin User ===
    admin_exists = await db.users_extended.find_one({"email": "admin@boltrex.com"})
    if not admin_exists:
        hashed_pw = pwd_context.hash("admin123")
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
        print("  Created admin user: admin@boltrex.com / admin123")
    else:
        print("  Admin user already exists")
    
    # === 2. Categories ===
    if await db.categories.count_documents({}) == 0:
        categories = [
            {"name": "Electrónica", "description": "Dispositivos electrónicos y accesorios", "created_at": now},
            {"name": "Alimentos", "description": "Productos alimenticios", "created_at": now},
            {"name": "Bebidas", "description": "Bebidas y refrescos", "created_at": now},
            {"name": "Hogar", "description": "Artículos para el hogar", "created_at": now},
            {"name": "Otros", "description": "Otros productos", "created_at": now}
        ]
        await db.categories.insert_many(categories)
        print(f"  Created {len(categories)} categories")
    else:
        print("  Categories already exist")
    
    # === 3. Document Types ===
    if await db.document_types.count_documents({}) == 0:
        doc_types = [
            {"code": "CC", "name": "Cédula de Ciudadanía", "created_at": now},
            {"code": "NIT", "name": "NIT", "created_at": now},
            {"code": "CE", "name": "Cédula de Extranjería", "created_at": now},
            {"code": "PAS", "name": "Pasaporte", "created_at": now}
        ]
        await db.document_types.insert_many(doc_types)
        print(f"  Created {len(doc_types)} document types")
    else:
        print("  Document types already exist")
    
    # === 4. Price Lists ===
    if await db.price_lists.count_documents({}) == 0:
        price_lists = [
            {"name": "default", "description": "Lista de precios por defecto", "is_active": True, "created_at": now},
            {"name": "mayorista", "description": "Precios para mayoristas", "is_active": True, "created_at": now},
            {"name": "minorista", "description": "Precios para minoristas", "is_active": True, "created_at": now}
        ]
        await db.price_lists.insert_many(price_lists)
        print(f"  Created {len(price_lists)} price lists")
    else:
        print("  Price lists already exist")
    
    # === 5. Tax Rates ===
    if await db.tax_rates.count_documents({}) == 0:
        tax_rates = [
            {"name": "IVA 19%", "rate": 19.0, "is_active": True, "effective_date": now, "created_at": now}
        ]
        await db.tax_rates.insert_many(tax_rates)
        print(f"  Created {len(tax_rates)} tax rates")
    else:
        print("  Tax rates already exist")
    
    # === 6. Payment Methods ===
    if await db.payment_methods.count_documents({}) == 0:
        payment_methods = [
            {"name": "Efectivo", "description": "Pago en efectivo", "is_active": True, "created_at": now},
            {"name": "Tarjeta de Crédito", "description": "Pago con tarjeta de crédito", "is_active": True, "created_at": now},
            {"name": "Tarjeta de Débito", "description": "Pago con tarjeta débito", "is_active": True, "created_at": now},
            {"name": "Transferencia", "description": "Transferencia bancaria", "is_active": True, "created_at": now},
            {"name": "Nequi", "description": "Pago por Nequi", "is_active": True, "created_at": now},
            {"name": "Daviplata", "description": "Pago por Daviplata", "is_active": True, "created_at": now}
        ]
        await db.payment_methods.insert_many(payment_methods)
        print(f"  Created {len(payment_methods)} payment methods")
    else:
        print("  Payment methods already exist")
    
    # === 7. Ticket Config ===
    if await db.ticket_config.count_documents({}) == 0:
        ticket_config = {
            "company_name": "Mi Empresa",
            "nit": "",
            "phone": "",
            "email": "",
            "address": "",
            "ticket_width": 80,
            "footer_message": "Gracias por su compra!",
            "updated_at": now
        }
        await db.ticket_config.insert_one(ticket_config)
        print("  Created default ticket config")
    else:
        print("  Ticket config already exists")
    
    client.close()
    print("Database seeded successfully!")

if __name__ == "__main__":
    asyncio.run(seed_database())
