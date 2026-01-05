#!/usr/bin/env python3
"""Seed initial data for Boltrex"""
import asyncio
import sys
import os
sys.path.append('/app/backend')

from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
from dotenv import load_dotenv
from pathlib import Path

# Load environment
ROOT_DIR = Path('/app/backend')
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
db_name = os.environ['DB_NAME']

async def seed_database():
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    print("🌱 Seeding database...")
    
    # Check if data already exists
    existing_categories = await db.categories.count_documents({})
    if existing_categories > 0:
        print("⚠️  Database already has data. Skipping seed.")
        client.close()
        return
    
    # Seed Categories
    categories = [
        {"name": "Electrónica", "description": "Dispositivos electrónicos y accesorios", "created_at": datetime.now(timezone.utc).isoformat()},
        {"name": "Alimentos", "description": "Productos alimenticios", "created_at": datetime.now(timezone.utc).isoformat()},
        {"name": "Bebidas", "description": "Bebidas y refrescos", "created_at": datetime.now(timezone.utc).isoformat()},
        {"name": "Hogar", "description": "Artículos para el hogar", "created_at": datetime.now(timezone.utc).isoformat()},
        {"name": "Otros", "description": "Otros productos", "created_at": datetime.now(timezone.utc).isoformat()}
    ]
    await db.categories.insert_many(categories)
    print(f"✅ Created {len(categories)} categories")
    
    # Seed Document Types
    doc_types = [
        {"code": "CC", "name": "Cédula de Ciudadanía", "created_at": datetime.now(timezone.utc).isoformat()},
        {"code": "NIT", "name": "NIT", "created_at": datetime.now(timezone.utc).isoformat()},
        {"code": "CE", "name": "Cédula de Extranjería", "created_at": datetime.now(timezone.utc).isoformat()},
        {"code": "PAS", "name": "Pasaporte", "created_at": datetime.now(timezone.utc).isoformat()}
    ]
    await db.document_types.insert_many(doc_types)
    print(f"✅ Created {len(doc_types)} document types")
    
    # Seed Price Lists
    price_lists = [
        {"name": "default", "description": "Lista de precios por defecto", "is_active": True, "created_at": datetime.now(timezone.utc).isoformat()},
        {"name": "mayorista", "description": "Precios para mayoristas", "is_active": True, "created_at": datetime.now(timezone.utc).isoformat()},
        {"name": "minorista", "description": "Precios para minoristas", "is_active": True, "created_at": datetime.now(timezone.utc).isoformat()}
    ]
    await db.price_lists.insert_many(price_lists)
    print(f"✅ Created {len(price_lists)} price lists")
    
    # Seed Tax Rates
    tax_rates = [
        {
            "name": "IVA 19%",
            "rate": 19.0,
            "is_active": True,
            "effective_date": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
    ]
    await db.tax_rates.insert_many(tax_rates)
    print(f"✅ Created {len(tax_rates)} tax rates")
    
    client.close()
    print("🎉 Database seeded successfully!")

if __name__ == "__main__":
    asyncio.run(seed_database())
