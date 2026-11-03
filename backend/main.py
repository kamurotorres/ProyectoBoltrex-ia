from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.database import db

# Import routers
from routers import auth, products, clients, rbac, invoices, inventory, reports, system

app = FastAPI(title="Boltrex API")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Include routers
app.include_router(auth.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(clients.router, prefix="/api")
app.include_router(invoices.router, prefix="/api")
app.include_router(inventory.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(system.router, prefix="/api")

# rbac was prefixed with /rbac in the original file
if hasattr(rbac, 'router'):
    app.include_router(rbac.router, prefix="/api")
elif hasattr(rbac, 'create_rbac_router'):
    app.include_router(rbac.create_rbac_router(db), prefix="/api")

@app.get("/")
def read_root():
    return {"message": "Welcome to Boltrex API"}
