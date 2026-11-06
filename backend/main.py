"""Boltrex API — punto de entrada (FastAPI).

Arranque con `lifespan` (mantenimiento fase 2): las tareas de arranque están en orden en
core/startup.py; los errores de dominio y los duplicados se traducen a respuestas en core/errors.py.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import CORS_ORIGINS, settings
from core.errors import register_error_handlers
from core.startup import run_startup_tasks

# Import routers
from routers import auth, products, clients, rbac, invoices, inventory, reports, system, audit as audit_router, cash as cash_router, credit as credit_router, adjustments as adjustments_router, alerts as alerts_router, exports as exports_router

# Los avisos de la app (logger "boltrex") salen en la consola / `docker compose logs backend`.
logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("boltrex")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Boltrex arrancando · %s", settings.summary())
    await run_startup_tasks()   # nunca impide el arranque (ver core/startup.py)
    yield
    from core.database import client
    client.close()


app = FastAPI(title="Boltrex API", lifespan=lifespan)
register_error_handlers(app)

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

app.include_router(rbac.router, prefix="/api")

@app.get("/")
def read_root():
    return {"message": "Welcome to Boltrex API"}
