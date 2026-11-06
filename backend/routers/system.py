from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query, Request, Response, BackgroundTasks
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument
from core.dates import now_utc, as_datetime
from core.database import db
from core.database import get_db
from core.security import get_current_user, get_password_hash, verify_password, create_access_token
from core.permissions import require_permission, require_any_permission
from core.indexes import duplicate_key_message
from pymongo.errors import DuplicateKeyError
from core import audit
from core.pricing import pricing_problem, price_lists_catalog, price_lists_problem
from models.auth import *
from models.billing import *
from models.inventory import *
from models.entities import *
import pandas as pd
import io
import csv
from fastapi.responses import StreamingResponse
from ticket_generator import TicketPDFGenerator

router = APIRouter(tags=["System"])
db_dep = Depends(get_db)
# ==================== IMPORT ENDPOINTS ====================

class ImportResult(BaseModel):
    success: int
    errors: List[Dict[str, Any]]
    total: int

def read_file(file: UploadFile) -> pd.DataFrame:
    """Read CSV or Excel file and return DataFrame"""
    try:
        if file.filename.endswith('.csv'):
            content = file.file.read()
            df = pd.read_csv(io.BytesIO(content))
        elif file.filename.endswith(('.xlsx', '.xls')):
            content = file.file.read()
            df = pd.read_excel(io.BytesIO(content))
        else:
            raise HTTPException(status_code=400, detail="Formato de archivo no soportado. Use CSV o Excel")
        return df
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al leer archivo: {str(e)}")

async def _audit_import(kind: str, label: str, file, success: int, errors: list, total: int) -> None:
    await audit.record("import", "import", entity_id=kind, entity_name=getattr(file, "filename", None),
                       summary=f"Importó {label} desde '{getattr(file, 'filename', '')}': {success} de {total} fila(s) "
                               f"creadas, {len(errors)} con error",
                       details={"success": success, "total": total, "errors": errors[:50]})


@router.post("/import/categories", response_model=ImportResult)
async def import_categories(file: UploadFile = File(...), current_user: User = Depends(require_permission("import", "create"))):
    """
    Importar categorías desde CSV o Excel
    Columnas requeridas: name, description
    """
    df = read_file(file)

    required_columns = ['name']
    if not all(col in df.columns for col in required_columns):
        raise HTTPException(status_code=400, detail=f"Columnas requeridas: {', '.join(required_columns)}")

    success_count = 0
    errors = []

    for index, row in df.iterrows():
        try:
            # Check if category already exists
            existing = await db.categories.find_one({"name": str(row['name'])})
            if existing:
                errors.append({"row": index + 2, "error": f"Categoría '{row['name']}' ya existe"})
                continue

            category_data = {
                "name": str(row['name']),
                "description": str(row.get('description', '')) if pd.notna(row.get('description')) else '',
                "created_at": now_utc()
            }

            await db.categories.insert_one(category_data)
            success_count += 1
        except DuplicateKeyError as e:
            errors.append({"row": index + 2, "error": duplicate_key_message(e)})
        except Exception as e:
            errors.append({"row": index + 2, "error": str(e)})

    await _audit_import("categories", "categorías", file, success_count, errors, len(df))
    return ImportResult(success=success_count, errors=errors, total=len(df))

@router.post("/import/products", response_model=ImportResult)
async def import_products(file: UploadFile = File(...), current_user: User = Depends(require_permission("import", "create"))):
    """
    Importar productos desde CSV o Excel
    Columnas requeridas: barcode, name, category, purchase_price, tax_rate, price_default
    Columnas opcionales: description y una columna price_<lista> por cada lista de precios existente
    (IVA entre 0 y 100; cada precio > 0 y >= purchase_price; price_default obligatorio)
    """
    df = read_file(file)

    required_columns = ['barcode', 'name', 'category', 'purchase_price', 'tax_rate']
    if not all(col in df.columns for col in required_columns):
        raise HTTPException(status_code=400, detail=f"Columnas requeridas: {', '.join(required_columns)}")

    # Columnas de precio dinámicas: una por lista parametrizada (no solo default/mayorista/minorista).
    catalog = await price_lists_catalog()
    price_columns = [c for c in df.columns if str(c).startswith('price_')]
    unknown = [c for c in price_columns if c[len('price_'):] not in catalog]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Columna(s) de precio sin lista de precios: {', '.join(unknown)}. "
                   f"Listas existentes: {', '.join('price_' + n for n in sorted(catalog))}.",
        )

    success_count = 0
    errors = []

    for index, row in df.iterrows():
        try:
            # Check if product already exists
            existing = await db.products.find_one({"barcode": str(row['barcode'])})
            if existing:
                errors.append({"row": index + 2, "error": f"Producto con código '{row['barcode']}' ya existe"})
                continue

            # Check if category exists
            category_exists = await db.categories.find_one({"name": str(row['category'])})
            if not category_exists:
                errors.append({"row": index + 2, "error": f"Categoría '{row['category']}' no existe"})
                continue

            # Build prices array
            prices = []
            for price_col in price_columns:
                if pd.notna(row.get(price_col)) and str(row.get(price_col)).strip() != '':
                    price_list_name = price_col.replace('price_', '')
                    prices.append({
                        "price_list_name": price_list_name,
                        "price": float(row[price_col])
                    })

            # P1.16/P1.17: mismas reglas que al crear desde la pantalla (la fila se rechaza con su motivo).
            problem = pricing_problem(row.get('purchase_price'), row.get('tax_rate'), prices) \
                or price_lists_problem(prices, catalog)
            if problem:
                errors.append({"row": index + 2, "error": problem})
                continue

            product_data = {
                "barcode": str(row['barcode']),
                "name": str(row['name']),
                "description": str(row.get('description', '')) if pd.notna(row.get('description')) else '',
                "category": str(row['category']),
                "purchase_price": float(row['purchase_price']),
                "tax_rate": float(row['tax_rate']),
                "prices": prices,
                "stock": 0,
                "created_at": now_utc()
            }

            await db.products.insert_one(product_data)
            success_count += 1
        except DuplicateKeyError as e:
            errors.append({"row": index + 2, "error": duplicate_key_message(e)})
        except Exception as e:
            errors.append({"row": index + 2, "error": str(e)})

    await _audit_import("products", "productos", file, success_count, errors, len(df))
    return ImportResult(success=success_count, errors=errors, total=len(df))

@router.post("/import/clients", response_model=ImportResult)
async def import_clients(file: UploadFile = File(...), current_user: User = Depends(require_permission("import", "create"))):
    """
    Importar clientes desde CSV o Excel
    Columnas requeridas: document_type, document_number, first_name, last_name
    Columnas opcionales: phone, email, address, latitude, longitude, price_list
    """
    df = read_file(file)

    required_columns = ['document_type', 'document_number', 'first_name', 'last_name']
    if not all(col in df.columns for col in required_columns):
        raise HTTPException(status_code=400, detail=f"Columnas requeridas: {', '.join(required_columns)}")

    success_count = 0
    errors = []

    for index, row in df.iterrows():
        try:
            # Check if client already exists
            existing = await db.clients.find_one({
                "document_type": str(row['document_type']),
                "document_number": str(row['document_number'])
            })
            if existing:
                errors.append({"row": index + 2, "error": f"Cliente con documento '{row['document_number']}' ya existe"})
                continue

            # Check if document type exists
            doc_type_exists = await db.document_types.find_one({"code": str(row['document_type'])})
            if not doc_type_exists:
                errors.append({"row": index + 2, "error": f"Tipo de documento '{row['document_type']}' no existe"})
                continue

            client_data = {
                "document_type": str(row['document_type']),
                "document_number": str(row['document_number']),
                "first_name": str(row['first_name']),
                "last_name": str(row['last_name']),
                "phone": str(row.get('phone', '')) if pd.notna(row.get('phone')) else None,
                "email": str(row.get('email', '')) if pd.notna(row.get('email')) else None,
                "address": str(row.get('address', '')) if pd.notna(row.get('address')) else None,
                "latitude": float(row['latitude']) if pd.notna(row.get('latitude')) else None,
                "longitude": float(row['longitude']) if pd.notna(row.get('longitude')) else None,
                "price_list": str(row.get('price_list', 'default')) if pd.notna(row.get('price_list')) else 'default',
                "created_at": now_utc()
            }

            await db.clients.insert_one(client_data)
            success_count += 1
        except DuplicateKeyError as e:
            errors.append({"row": index + 2, "error": duplicate_key_message(e)})
        except Exception as e:
            errors.append({"row": index + 2, "error": str(e)})

    await _audit_import("clients", "clientes", file, success_count, errors, len(df))
    return ImportResult(success=success_count, errors=errors, total=len(df))

@router.post("/import/suppliers", response_model=ImportResult)
async def import_suppliers(file: UploadFile = File(...), current_user: User = Depends(require_permission("import", "create"))):
    """
    Importar proveedores desde CSV o Excel
    Columnas requeridas: name
    Columnas opcionales: contact_name, phone, email, address
    """
    df = read_file(file)

    required_columns = ['name']
    if not all(col in df.columns for col in required_columns):
        raise HTTPException(status_code=400, detail=f"Columnas requeridas: {', '.join(required_columns)}")

    success_count = 0
    errors = []

    for index, row in df.iterrows():
        try:
            supplier_data = {
                "name": str(row['name']),
                "contact_name": str(row.get('contact_name', '')) if pd.notna(row.get('contact_name')) else None,
                "phone": str(row.get('phone', '')) if pd.notna(row.get('phone')) else None,
                "email": str(row.get('email', '')) if pd.notna(row.get('email')) else None,
                "address": str(row.get('address', '')) if pd.notna(row.get('address')) else None,
                "created_at": now_utc()
            }

            await db.suppliers.insert_one(supplier_data)
            success_count += 1
        except DuplicateKeyError as e:
            errors.append({"row": index + 2, "error": duplicate_key_message(e)})
        except Exception as e:
            errors.append({"row": index + 2, "error": str(e)})

    await _audit_import("suppliers", "proveedores", file, success_count, errors, len(df))
    return ImportResult(success=success_count, errors=errors, total=len(df))

@router.get("/import/templates/{module_name}")
async def download_template(module_name: str, current_user: User = Depends(require_permission("import", "read"))):
    """
    Descargar plantilla CSV para importación
    Módulos disponibles: categories, products, clients, suppliers
    """
    templates = {
        "categories": {
            "columns": ["name", "description"],
            "sample": [
                ["Electrónica", "Dispositivos electrónicos y accesorios"],
                ["Alimentos", "Productos alimenticios"]
            ]
        },
        "products": {
            "columns": ["barcode", "name", "description", "category", "purchase_price", "tax_rate", "price_default", "price_mayorista", "price_minorista"],
            "sample": [
                ["001", "Producto 1", "Descripción producto 1", "Electrónica", "100.00", "19", "150.00", "140.00", "160.00"],
                ["002", "Producto 2", "Descripción producto 2", "Alimentos", "50.00", "19", "70.00", "65.00", "75.00"]
            ]
        },
        "clients": {
            "columns": ["document_type", "document_number", "first_name", "last_name", "phone", "email", "address", "latitude", "longitude", "price_list"],
            "sample": [
                ["CC", "123456789", "Juan", "Pérez", "3001234567", "juan@example.com", "Calle 123", "4.6097", "-74.0817", "default"],
                ["NIT", "987654321", "Empresa", "S.A.S", "3009876543", "info@empresa.com", "Carrera 45", "", "", "mayorista"]
            ]
        },
        "suppliers": {
            "columns": ["name", "contact_name", "phone", "email", "address"],
            "sample": [
                ["Proveedor ABC", "María López", "3001111111", "maria@abc.com", "Avenida 1"],
                ["Distribuidora XYZ", "Carlos García", "3002222222", "carlos@xyz.com", "Calle 2"]
            ]
        }
    }

    if module_name not in templates:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")

    if module_name == "products":
        # Una columna de precio por cada lista ACTIVA ('default' primero).
        catalog = await price_lists_catalog()
        lists = sorted((n for n, active in catalog.items() if active), key=lambda n: (n != "default", n))
        base = ["barcode", "name", "description", "category", "purchase_price", "tax_rate"]
        templates["products"] = {
            "columns": base + [f"price_{n}" for n in lists],
            "sample": [
                ["001", "Producto 1", "Descripción producto 1", "Electrónica", "100.00", "19"] + ["150.00"] * len(lists),
                ["002", "Producto 2", "Descripción producto 2", "Alimentos", "50.00", "0"] + ["70.00"] * len(lists),
            ],
        }

    template = templates[module_name]

    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(template["columns"])
    for row in template["sample"]:
        writer.writerow(row)

    # Return as downloadable file
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=plantilla_{module_name}.csv"
        }
    )

# ==================== TICKET CONFIGURATION ====================

@router.get("/ticket-config")
async def get_ticket_config(current_user: User = Depends(require_permission("ticket-config", "read"))):
    """Obtener la configuración del ticket"""
    config = await db.ticket_config.find_one({}, {"_id": 0})
    if not config:
        # Return default config if none exists
        return {
            "company_name": "Mi Empresa",
            "nit": "",
            "phone": "",
            "email": "",
            "address": "",
            "ticket_width": 80,
            "footer_message": "¡Gracias por su compra!"
        }
    return config

@router.put("/ticket-config")
async def update_ticket_config(config: TicketConfigUpdate, current_user: User = Depends(require_permission("ticket-config", "update"))):
    """Actualizar o crear la configuración del ticket"""
    update_data = {k: v for k, v in config.model_dump().items() if v is not None}
    update_data["updated_at"] = now_utc()

    # Check if config exists
    existing = await db.ticket_config.find_one({})
    before_cfg = await db.ticket_config.find_one({}, {"_id": 0})

    if existing:
        await db.ticket_config.update_one({}, {"$set": update_data})
    else:
        # Create new config with defaults
        default_config = {
            "company_name": "Mi Empresa",
            "nit": "",
            "phone": "",
            "email": "",
            "address": "",
            "ticket_width": 80,
            "footer_message": "¡Gracias por su compra!",
            "updated_at": now_utc()
        }
        default_config.update(update_data)
        await db.ticket_config.insert_one(default_config)

    updated = await db.ticket_config.find_one({}, {"_id": 0})
    changes = audit.diff(before_cfg, updated)
    if changes:
        await audit.record("ticket-config", "update", entity_id="ticket", entity_name=updated.get("company_name"),
                           summary=f"Modificó la configuración del ticket: {audit.describe_changes(changes)}",
                           before=before_cfg, after=updated)
    return updated

# ==================== FACTORY RESET ====================

class FactoryResetRequest(BaseModel):
    password: str


from core.config import PROTECTED_ADMIN_EMAIL  # usuario que el factory reset nunca borra

@router.post("/system/factory-reset")
async def factory_reset(request: FactoryResetRequest, current_user: User = Depends(get_current_user)):
    # 1. Verify user has Administrador role
    user_doc = await db.users_extended.find_one({"email": current_user.email})
    if not user_doc or "Administrador" not in user_doc.get("roles", []):
        raise HTTPException(status_code=403, detail="Solo los administradores pueden restablecer el sistema")

    # 2. Verify password
    if not verify_password(request.password, user_doc["hashed_password"]):
        await audit.record("system", "factory_reset", entity_id="sistema", entity_name="Restablecer sistema",
                           summary="Intento de restablecer el sistema con contraseña incorrecta", success=False)
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")

    # 3. Clear all data collections.
    # Al añadir una colección de datos nueva al sistema, agregarla aquí también.
    # (Usuarios y RBAC se tratan aparte en los pasos 4 y 5.)
    collections_to_clear = [
        "products", "categories", "clients", "suppliers",
        "purchases", "returns", "invoices", "payment_methods",
        "inventory_movements", "ticket_config", "tax_rates",
        "price_lists", "document_types",
        "fio_payments",  # abonos de créditos (antes quedaban huérfanos)
        "counters",      # consecutivos INV-/PUR-: la numeración vuelve a empezar
        "login_attempts",  # contadores y bloqueos de intentos de login
        "cash_sessions", "cash_movements",  # cajas y sus movimientos (P2.31)
        "inventory_adjustments", "adjustment_reasons",  # ajustes de inventario y su catálogo (P2.32)
        "alerts_seen",   # alertas marcadas como vistas (P2.34)
    ]
    # La bitácora de auditoría (audit_log) NO se borra: deja constancia del propio reset.
    deleted_counts = {}
    for col in collections_to_clear:
        deleted_counts[col] = (await db[col].delete_many({})).deleted_count

    # 4. Clear users EXCEPT the protected admin AND whoever runs the reset.
    # Antes solo se conservaba admin@boltrex.com: si el reset lo ejecutaba otro administrador
    # se borraba a sí mismo, y si admin@boltrex.com no existía el sistema quedaba sin usuarios.
    kept_emails = sorted({PROTECTED_ADMIN_EMAIL, current_user.email})
    await db.users_extended.delete_many({"email": {"$nin": kept_emails}})
    await db.users.delete_many({"email": {"$nin": kept_emails}})
    # Sesiones de los usuarios borrados (P1.11); las de los conservados siguen abiertas.
    await db.sessions.delete_many({"email": {"$nin": kept_emails}})
    # Los roles se re-siembran desde cero: los usuarios conservados quedan como
    # Administrador activo para que nunca se pierda el acceso tras el reset.
    await db.users_extended.update_many(
        {"email": {"$in": kept_emails}},
        {"$set": {"roles": ["Administrador"], "is_active": True, "updated_at": now_utc()}},
    )

    # 5. Clear RBAC (roles, permissions, modules) to re-seed cleanly
    await db.roles.delete_many({})
    await db.role_permissions.delete_many({})
    await db.system_modules.delete_many({})

    # 6. Re-seed: RBAC
    from rbac import DEFAULT_MODULES, DEFAULT_ROLES
    for mod in DEFAULT_MODULES:
        mod_dict = mod.copy()
        mod_dict["is_active"] = True
        mod_dict["created_at"] = now_utc()
        await db.system_modules.insert_one(mod_dict)

    for role_data in DEFAULT_ROLES:
        role = {
            "name": role_data["name"],
            "description": role_data["description"],
            "is_active": True,
            "created_at": now_utc()
        }
        await db.roles.insert_one(role)
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
                "created_at": now_utc()
            }
            await db.role_permissions.insert_one(perm_doc)

    # 7. Re-seed: Data
    now = now_utc()
    await db.categories.insert_many([
        {"name": "Electrónica", "description": "Dispositivos electrónicos y accesorios", "created_at": now},
        {"name": "Alimentos", "description": "Productos alimenticios", "created_at": now},
        {"name": "Bebidas", "description": "Bebidas y refrescos", "created_at": now},
        {"name": "Hogar", "description": "Artículos para el hogar", "created_at": now},
        {"name": "Otros", "description": "Otros productos", "created_at": now}
    ])
    await db.document_types.insert_many([
        {"code": "CC", "name": "Cédula de Ciudadanía", "created_at": now},
        {"code": "NIT", "name": "NIT", "created_at": now},
        {"code": "CE", "name": "Cédula de Extranjería", "created_at": now},
        {"code": "PAS", "name": "Pasaporte", "created_at": now}
    ])
    await db.price_lists.insert_many([
        {"name": "default", "description": "Lista de precios por defecto", "is_active": True, "created_at": now},
        {"name": "mayorista", "description": "Precios para mayoristas", "is_active": True, "created_at": now},
        {"name": "minorista", "description": "Precios para minoristas", "is_active": True, "created_at": now}
    ])
    await db.tax_rates.insert_many([
        {"name": "IVA 19%", "rate": 19.0, "is_active": True, "effective_date": now, "created_at": now}
    ])
    await db.payment_methods.insert_many([
        {"name": "Efectivo", "description": "Pago en efectivo", "is_active": True, "created_at": now},
        {"name": "Tarjeta de Crédito", "description": "Pago con tarjeta de crédito", "is_active": True, "created_at": now},
        {"name": "Tarjeta de Débito", "description": "Pago con tarjeta débito", "is_active": True, "created_at": now},
        {"name": "Transferencia", "description": "Transferencia bancaria", "is_active": True, "created_at": now},
        {"name": "Nequi", "description": "Pago por Nequi", "is_active": True, "created_at": now},
        {"name": "Daviplata", "description": "Pago por Daviplata", "is_active": True, "created_at": now}
    ])
    from core.adjustments import ensure_default_reasons
    await ensure_default_reasons()
    await db.ticket_config.insert_one({
        "company_name": "Mi Empresa", "nit": "", "phone": "", "email": "",
        "address": "", "ticket_width": 80, "footer_message": "¡Gracias por su compra!", "updated_at": now
    })

    await audit.record("system", "factory_reset", entity_id="sistema", entity_name="Restablecer sistema",
                       summary="Restableció el sistema a valores de fábrica. Registros borrados: "
                               + (", ".join(f"{k} {v}" for k, v in deleted_counts.items() if v) or "ninguno"),
                       details={"deleted": deleted_counts, "kept_users": kept_emails})
    return {"message": "Sistema restablecido a valores de fábrica exitosamente"}

