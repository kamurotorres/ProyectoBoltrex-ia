import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import DuplicateKeyError

from core.database import db
from core.config import CORS_ORIGINS
from core.indexes import ensure_indexes, duplicate_key_message
from core.security import flag_default_passwords
from core.clients import backfill_invoice_document_types
from core.pricing import warn_products_without_price
from core.dates import migrate_text_dates
from core.modules_sync import ensure_new_modules
from core.credit import backfill_due_dates
from core.adjustments import ensure_default_reasons

# Import routers
from routers import auth, products, clients, rbac, invoices, inventory, reports, system, audit as audit_router, cash as cash_router, credit as credit_router, adjustments as adjustments_router, alerts as alerts_router, exports as exports_router

# Los avisos de la app (logger "boltrex") salen en la consola / `docker compose logs backend`.
logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")

app = FastAPI(title="Boltrex API")


@app.on_event("startup")
async def create_indexes():
    # Nunca impide el arranque: si hay datos duplicados, lo registra en el log.
    # P1.19: fechas guardadas como texto → fecha nativa (idempotente, antes de todo lo demás).
    await migrate_text_dates(db)
    await ensure_indexes()
    # P1.10: administradores con contraseña por defecto → cambio obligatorio al entrar.
    await flag_default_passwords(db)
    # P1.15: tipo de documento del cliente en facturas antiguas (solo cuando no es ambiguo).
    await backfill_invoice_document_types()
    # P1.17: productos sin precio 'default' no se pueden vender: se avisa en el log.
    await warn_products_without_price()
    # P2.31: módulos nuevos (p. ej. Caja) y sus permisos por defecto en bases ya existentes.
    await ensure_new_modules()
    # P2.30: facturas a crédito antiguas sin vencimiento → fecha de venta + plazo.
    await backfill_due_dates()
    # P2.32: motivos de ajuste de inventario por defecto (si el catálogo está vacío).
    await ensure_default_reasons()


@app.exception_handler(DuplicateKeyError)
async def handle_duplicate_key(request: Request, exc: DuplicateKeyError):
    # La base rechazó un duplicado (p. ej. dos peticiones simultáneas que pasaron la
    # validación previa a la vez): se responde 400 con un mensaje claro, no un 500.
    return JSONResponse(status_code=400, content={"detail": duplicate_key_message(exc)})

# Setup CORS: solo los orígenes configurados. La autenticación va en la cabecera
# Authorization (Bearer), no en cookies, así que no hacen falta credenciales CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
# P2.33: primero, para que /purchases/export no lo capture /purchases/{purchase_number}.
app.include_router(exports_router.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(clients.router, prefix="/api")
app.include_router(invoices.router, prefix="/api")
app.include_router(inventory.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(system.router, prefix="/api")
app.include_router(audit_router.router, prefix="/api")
app.include_router(cash_router.router, prefix="/api")
app.include_router(credit_router.router, prefix="/api")
app.include_router(adjustments_router.router, prefix="/api")
app.include_router(alerts_router.router, prefix="/api")

# rbac was prefixed with /rbac in the original file
if hasattr(rbac, 'router'):
    app.include_router(rbac.router, prefix="/api")
elif hasattr(rbac, 'create_rbac_router'):
    app.include_router(rbac.create_rbac_router(db), prefix="/api")

@app.get("/")
def read_root():
    return {"message": "Welcome to Boltrex API"}
