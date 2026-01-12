from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, UploadFile, File, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from ticket_generator import TicketPDFGenerator
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from passlib.context import CryptContext
from jose import JWTError, jwt
import re
import pandas as pd
import io
import csv
from server_rbac import create_rbac_router

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Security
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "boltrex-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440

security = HTTPBearer()

# Create the main app
app = FastAPI(title="Boltrex API")
api_router = APIRouter(prefix="/api")

# ==================== MODELS ====================

class UserRole(BaseModel):
    name: str  # admin, vendedor, supervisor
    permissions: List[str] = []

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    email: EmailStr
    full_name: str
    role: str  # admin, vendedor, supervisor
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: str = "vendedor"

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: User

class Category(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None

class PriceList(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    description: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PriceListCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True

class ProductPrice(BaseModel):
    price_list_name: str
    price: float

class Product(BaseModel):
    model_config = ConfigDict(extra="ignore")
    barcode: str
    name: str
    description: Optional[str] = None
    category: str
    purchase_price: float
    tax_rate: float  # IVA percentage
    prices: List[ProductPrice] = []  # Multiple prices
    stock: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ProductCreate(BaseModel):
    barcode: str
    name: str
    description: Optional[str] = None
    category: str
    purchase_price: float
    tax_rate: float
    prices: List[ProductPrice] = []

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    purchase_price: Optional[float] = None
    tax_rate: Optional[float] = None
    prices: Optional[List[ProductPrice]] = None

class DocumentType(BaseModel):
    model_config = ConfigDict(extra="ignore")
    code: str
    name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class DocumentTypeCreate(BaseModel):
    code: str
    name: str

class Client(BaseModel):
    model_config = ConfigDict(extra="ignore")
    document_type: str
    document_number: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    price_list: str = "default"  # Assigned price list
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ClientCreate(BaseModel):
    document_type: str
    document_number: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    price_list: str = "default"

class ClientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    price_list: Optional[str] = None

class Supplier(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SupplierCreate(BaseModel):
    name: str
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None

class TaxRate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    rate: float  # Percentage
    is_active: bool = False
    effective_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class TaxRateCreate(BaseModel):
    name: str
    rate: float
    is_active: bool = False
    effective_date: Optional[datetime] = None

class InvoiceItem(BaseModel):
    barcode: str
    product_name: str
    quantity: int
    unit_price: float
    tax_rate: float
    subtotal: float
    tax_amount: float
    total: float

# ==================== PAYMENT METHODS MODELS ====================

class PaymentMethod(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    description: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PaymentMethodCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True

class PaymentMethodUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

# ==================== INVOICE MODELS (UPDATED) ====================

class Invoice(BaseModel):
    model_config = ConfigDict(extra="ignore")
    invoice_number: str
    client_document: str
    client_name: str
    items: List[InvoiceItem]
    subtotal: float
    total_tax: float
    total: float
    created_by: str  # email of user
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "completed"  # completed, returned
    payment_status: str = "pagado"  # pagado, por_cobrar
    payment_method: Optional[str] = None  # Name of payment method
    amount_paid: float = 0  # Amount paid so far
    balance: float = 0  # Remaining balance

class InvoiceCreate(BaseModel):
    client_document: str
    items: List[InvoiceItem]
    payment_status: str = "pagado"  # pagado, por_cobrar
    payment_method: Optional[str] = None  # Required if payment_status is "pagado"

# ==================== FIOS (CREDITS/PAYMENTS) MODELS ====================

class FioPayment(BaseModel):
    """Individual payment record for a credit invoice"""
    model_config = ConfigDict(extra="ignore")
    payment_id: str
    invoice_number: str
    amount: float
    payment_method: str
    notes: Optional[str] = None
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class FioPaymentCreate(BaseModel):
    amount: float
    payment_method: str
    notes: Optional[str] = None

class FioAccount(BaseModel):
    """Credit account summary for a client"""
    model_config = ConfigDict(extra="ignore")
    client_document: str
    client_name: str
    total_credit: float  # Total amount on credit
    total_paid: float  # Total amount paid
    balance: float  # Remaining balance
    invoices_count: int  # Number of pending invoices

class PurchaseItem(BaseModel):
    barcode: str
    product_name: str
    quantity: int
    unit_cost: float
    total: float

class Purchase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    supplier_name: str
    items: List[PurchaseItem]
    total: float
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PurchaseCreate(BaseModel):
    supplier_name: str
    items: List[PurchaseItem]

class InventoryMovement(BaseModel):
    model_config = ConfigDict(extra="ignore")
    barcode: str
    product_name: str
    movement_type: str  # purchase, sale, return, adjustment
    quantity: int  # positive for in, negative for out
    reference: Optional[str] = None  # invoice/purchase number
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ReturnItem(BaseModel):
    barcode: str
    product_name: str
    quantity: int
    unit_price: float
    total: float

class Return(BaseModel):
    model_config = ConfigDict(extra="ignore")
    invoice_number: str
    items: List[ReturnItem]
    total: float
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ReturnCreate(BaseModel):
    invoice_number: str
    items: List[ReturnItem]

# ==================== TICKET CONFIG MODELS ====================

class TicketConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    company_name: str
    nit: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    ticket_width: int = 80  # 58 or 80 mm
    footer_message: str = "¡Gracias por su compra!"
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class TicketConfigUpdate(BaseModel):
    company_name: Optional[str] = None
    nit: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    ticket_width: Optional[int] = None
    footer_message: Optional[str] = None

# ==================== AUTH UTILITIES ====================

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Search in users_extended first
    user = await db.users_extended.find_one({"email": email}, {"_id": 0, "hashed_password": 0})
    
    # If not found in users_extended, try old users table for backward compatibility
    if user is None:
        user = await db.users.find_one({"email": email}, {"_id": 0, "hashed_password": 0})
    
    if user is None:
        raise credentials_exception
    
    # Return User format for compatibility
    return User(
        email=user["email"],
        full_name=user.get("full_name") or f"{user.get('first_name', '')} {user.get('last_name', '')}",
        role=user.get("role", "vendedor"),
        is_active=user.get("is_active", True),
        created_at=datetime.fromisoformat(user["created_at"]) if isinstance(user.get("created_at"), str) else user.get("created_at", datetime.now(timezone.utc))
    )

# ==================== AUTH ROUTES ====================

@api_router.post("/auth/register", response_model=User)
async def register(user_data: UserCreate):
    # Check in users_extended
    existing = await db.users_extended.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = get_password_hash(user_data.password)
    
    # Create user in users_extended
    user_dict = {
        "email": user_data.email,
        "first_name": user_data.full_name.split()[0] if user_data.full_name else "Usuario",
        "last_name": " ".join(user_data.full_name.split()[1:]) if user_data.full_name and len(user_data.full_name.split()) > 1 else "",
        "phone": None,
        "is_active": True,
        "roles": ["Vendedor"],  # Default role
        "hashed_password": hashed_password,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.users_extended.insert_one(user_dict)
    
    # Return User format for compatibility
    return User(
        email=user_dict["email"],
        full_name=user_data.full_name,
        role=user_data.role,
        is_active=True,
        created_at=datetime.now(timezone.utc)
    )

@api_router.post("/auth/login")
async def login(credentials: UserLogin):
    # Try users_extended first
    user = await db.users_extended.find_one({"email": credentials.email})
    
    if not user or not verify_password(credentials.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="User account is inactive")
    
    access_token = create_access_token(data={"sub": user["email"]})
    
    # Get user permissions from server_rbac module
    from server_rbac import get_user_permissions
    user_permissions = await get_user_permissions(db, user["email"])
    
    # Convert permissions to simple dict
    permissions_dict = {}
    for module_slug, perms in user_permissions.items():
        permissions_dict[module_slug] = {
            "read": perms.read,
            "create": perms.create,
            "update": perms.update,
            "delete": perms.delete
        }
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "email": user["email"],
            "full_name": f"{user['first_name']} {user['last_name']}",
            "first_name": user["first_name"],
            "last_name": user["last_name"],
            "roles": user.get("roles", []),
            "is_active": user.get("is_active", True),
            "permissions": permissions_dict
        }
    }

@api_router.get("/auth/me")
async def get_me(current_user: User = Depends(get_current_user)):
    # Get full user data from users_extended
    user = await db.users_extended.find_one({"email": current_user.email}, {"_id": 0, "hashed_password": 0})
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get permissions
    from server_rbac import get_user_permissions
    user_permissions = await get_user_permissions(db, user["email"])
    
    permissions_dict = {}
    for module_slug, perms in user_permissions.items():
        permissions_dict[module_slug] = {
            "read": perms.read,
            "create": perms.create,
            "update": perms.update,
            "delete": perms.delete
        }
    
    return {
        "email": user["email"],
        "full_name": f"{user['first_name']} {user['last_name']}",
        "first_name": user["first_name"],
        "last_name": user["last_name"],
        "roles": user.get("roles", []),
        "is_active": user.get("is_active", True),
        "permissions": permissions_dict
    }

# ==================== CATEGORIES ====================

@api_router.post("/categories", response_model=Category)
async def create_category(category: CategoryCreate, current_user: User = Depends(get_current_user)):
    existing = await db.categories.find_one({"name": category.name})
    if existing:
        raise HTTPException(status_code=400, detail="Category already exists")
    
    cat_dict = category.model_dump()
    cat_dict["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.categories.insert_one(cat_dict)
    return Category(**cat_dict)

@api_router.get("/categories", response_model=List[Category])
async def get_categories(current_user: User = Depends(get_current_user)):
    categories = await db.categories.find({}, {"_id": 0}).to_list(1000)
    for cat in categories:
        if isinstance(cat.get('created_at'), str):
            cat['created_at'] = datetime.fromisoformat(cat['created_at'])
    return categories

@api_router.put("/categories/{name}", response_model=Category)
async def update_category(name: str, category: CategoryCreate, current_user: User = Depends(get_current_user)):
    result = await db.categories.update_one(
        {"name": name},
        {"$set": category.model_dump()}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Category not found")
    
    updated = await db.categories.find_one({"name": name}, {"_id": 0})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = datetime.fromisoformat(updated['created_at'])
    return Category(**updated)

@api_router.delete("/categories/{name}")
async def delete_category(name: str, current_user: User = Depends(get_current_user)):
    result = await db.categories.delete_one({"name": name})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Category not found")
    return {"message": "Category deleted"}

# ==================== PRICE LISTS ====================

@api_router.post("/price-lists", response_model=PriceList)
async def create_price_list(price_list: PriceListCreate, current_user: User = Depends(get_current_user)):
    pl_dict = price_list.model_dump()
    pl_dict["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.price_lists.insert_one(pl_dict)
    return PriceList(**pl_dict)

@api_router.get("/price-lists", response_model=List[PriceList])
async def get_price_lists(current_user: User = Depends(get_current_user)):
    price_lists = await db.price_lists.find({}, {"_id": 0}).to_list(1000)
    for pl in price_lists:
        if isinstance(pl.get('created_at'), str):
            pl['created_at'] = datetime.fromisoformat(pl['created_at'])
    return price_lists

# ==================== PRODUCTS ====================

@api_router.post("/products", response_model=Product)
async def create_product(product: ProductCreate, current_user: User = Depends(get_current_user)):
    existing = await db.products.find_one({"barcode": product.barcode})
    if existing:
        raise HTTPException(status_code=400, detail="Barcode already exists")
    
    prod_dict = product.model_dump()
    prod_dict["stock"] = 0
    prod_dict["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.products.insert_one(prod_dict)
    return Product(**prod_dict)

@api_router.get("/products", response_model=List[Product])
async def get_products(search: Optional[str] = None, current_user: User = Depends(get_current_user)):
    query = {}
    if search:
        query = {"$or": [
            {"barcode": {"$regex": search, "$options": "i"}},
            {"name": {"$regex": search, "$options": "i"}}
        ]}
    
    products = await db.products.find(query, {"_id": 0}).to_list(1000)
    for prod in products:
        if isinstance(prod.get('created_at'), str):
            prod['created_at'] = datetime.fromisoformat(prod['created_at'])
    return products

@api_router.get("/products/{barcode}", response_model=Product)
async def get_product(barcode: str, current_user: User = Depends(get_current_user)):
    product = await db.products.find_one({"barcode": barcode}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if isinstance(product.get('created_at'), str):
        product['created_at'] = datetime.fromisoformat(product['created_at'])
    return Product(**product)

@api_router.put("/products/{barcode}", response_model=Product)
async def update_product(barcode: str, product_update: ProductUpdate, current_user: User = Depends(get_current_user)):
    update_data = {k: v for k, v in product_update.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No data to update")
    
    result = await db.products.update_one({"barcode": barcode}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    
    updated = await db.products.find_one({"barcode": barcode}, {"_id": 0})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = datetime.fromisoformat(updated['created_at'])
    return Product(**updated)

@api_router.delete("/products/{barcode}")
async def delete_product(barcode: str, current_user: User = Depends(get_current_user)):
    result = await db.products.delete_one({"barcode": barcode})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"message": "Product deleted"}

# ==================== DOCUMENT TYPES ====================

@api_router.post("/document-types", response_model=DocumentType)
async def create_document_type(doc_type: DocumentTypeCreate, current_user: User = Depends(get_current_user)):
    existing = await db.document_types.find_one({"code": doc_type.code})
    if existing:
        raise HTTPException(status_code=400, detail="Document type already exists")
    
    dt_dict = doc_type.model_dump()
    dt_dict["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.document_types.insert_one(dt_dict)
    return DocumentType(**dt_dict)

@api_router.get("/document-types", response_model=List[DocumentType])
async def get_document_types(current_user: User = Depends(get_current_user)):
    doc_types = await db.document_types.find({}, {"_id": 0}).to_list(1000)
    for dt in doc_types:
        if isinstance(dt.get('created_at'), str):
            dt['created_at'] = datetime.fromisoformat(dt['created_at'])
    return doc_types

# ==================== CLIENTS ====================

@api_router.post("/clients", response_model=Client)
async def create_client(client: ClientCreate, current_user: User = Depends(get_current_user)):
    existing = await db.clients.find_one({
        "document_type": client.document_type,
        "document_number": client.document_number
    })
    if existing:
        raise HTTPException(status_code=400, detail="Client already exists")
    
    client_dict = client.model_dump()
    client_dict["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.clients.insert_one(client_dict)
    return Client(**client_dict)

@api_router.get("/clients", response_model=List[Client])
async def get_clients(search: Optional[str] = None, current_user: User = Depends(get_current_user)):
    query = {}
    if search:
        query = {"$or": [
            {"document_number": {"$regex": search, "$options": "i"}},
            {"first_name": {"$regex": search, "$options": "i"}},
            {"last_name": {"$regex": search, "$options": "i"}}
        ]}
    
    clients = await db.clients.find(query, {"_id": 0}).to_list(1000)
    for client in clients:
        if isinstance(client.get('created_at'), str):
            client['created_at'] = datetime.fromisoformat(client['created_at'])
    return clients

@api_router.get("/clients/{document_number}", response_model=Client)
async def get_client(document_number: str, current_user: User = Depends(get_current_user)):
    client = await db.clients.find_one({"document_number": document_number}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if isinstance(client.get('created_at'), str):
        client['created_at'] = datetime.fromisoformat(client['created_at'])
    return Client(**client)

@api_router.put("/clients/{document_number}", response_model=Client)
async def update_client(document_number: str, client_update: ClientUpdate, current_user: User = Depends(get_current_user)):
    update_data = {k: v for k, v in client_update.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No data to update")
    
    result = await db.clients.update_one({"document_number": document_number}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Client not found")
    
    updated = await db.clients.find_one({"document_number": document_number}, {"_id": 0})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = datetime.fromisoformat(updated['created_at'])
    return Client(**updated)

# ==================== SUPPLIERS ====================

@api_router.post("/suppliers", response_model=Supplier)
async def create_supplier(supplier: SupplierCreate, current_user: User = Depends(get_current_user)):
    supp_dict = supplier.model_dump()
    supp_dict["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.suppliers.insert_one(supp_dict)
    return Supplier(**supp_dict)

@api_router.get("/suppliers", response_model=List[Supplier])
async def get_suppliers(current_user: User = Depends(get_current_user)):
    suppliers = await db.suppliers.find({}, {"_id": 0}).to_list(1000)
    for supp in suppliers:
        if isinstance(supp.get('created_at'), str):
            supp['created_at'] = datetime.fromisoformat(supp['created_at'])
    return suppliers

# ==================== TAX RATES ====================

@api_router.post("/tax-rates", response_model=TaxRate)
async def create_tax_rate(tax_rate: TaxRateCreate, current_user: User = Depends(get_current_user)):
    if tax_rate.is_active:
        await db.tax_rates.update_many({"is_active": True}, {"$set": {"is_active": False}})
    
    tr_dict = tax_rate.model_dump()
    if tr_dict.get("effective_date"):
        tr_dict["effective_date"] = tr_dict["effective_date"].isoformat()
    else:
        tr_dict["effective_date"] = datetime.now(timezone.utc).isoformat()
    tr_dict["created_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.tax_rates.insert_one(tr_dict)
    return TaxRate(**{**tr_dict, "effective_date": datetime.fromisoformat(tr_dict["effective_date"]), "created_at": datetime.fromisoformat(tr_dict["created_at"])})

@api_router.get("/tax-rates", response_model=List[TaxRate])
async def get_tax_rates(current_user: User = Depends(get_current_user)):
    tax_rates = await db.tax_rates.find({}, {"_id": 0}).to_list(1000)
    for tr in tax_rates:
        if isinstance(tr.get('effective_date'), str):
            tr['effective_date'] = datetime.fromisoformat(tr['effective_date'])
        if isinstance(tr.get('created_at'), str):
            tr['created_at'] = datetime.fromisoformat(tr['created_at'])
    return tax_rates

@api_router.patch("/tax-rates/{name}/activate")
async def activate_tax_rate(name: str, current_user: User = Depends(get_current_user)):
    await db.tax_rates.update_many({"is_active": True}, {"$set": {"is_active": False}})
    result = await db.tax_rates.update_one({"name": name}, {"$set": {"is_active": True}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Tax rate not found")
    return {"message": "Tax rate activated"}

# ==================== INVOICES (POS) ====================

@api_router.post("/invoices", response_model=Invoice)
async def create_invoice(invoice_data: InvoiceCreate, current_user: User = Depends(get_current_user)):
    # Get next invoice number
    last_invoice = await db.invoices.find_one({}, {"_id": 0, "invoice_number": 1}, sort=[("created_at", -1)])
    if last_invoice:
        last_num = int(last_invoice["invoice_number"].split("-")[1])
        invoice_number = f"INV-{last_num + 1:06d}"
    else:
        invoice_number = "INV-000001"
    
    # Get client
    client = await db.clients.find_one({"document_number": invoice_data.client_document}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    client_name = f"{client['first_name']} {client['last_name']}"
    
    # Calculate totals
    subtotal = sum(item.subtotal for item in invoice_data.items)
    total_tax = sum(item.tax_amount for item in invoice_data.items)
    total = sum(item.total for item in invoice_data.items)
    
    invoice_dict = {
        "invoice_number": invoice_number,
        "client_document": invoice_data.client_document,
        "client_name": client_name,
        "items": [item.model_dump() for item in invoice_data.items],
        "subtotal": subtotal,
        "total_tax": total_tax,
        "total": total,
        "created_by": current_user.email,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed"
    }
    
    await db.invoices.insert_one(invoice_dict)
    
    # Update inventory and create movements
    for item in invoice_data.items:
        await db.products.update_one(
            {"barcode": item.barcode},
            {"$inc": {"stock": -item.quantity}}
        )
        
        movement_dict = {
            "barcode": item.barcode,
            "product_name": item.product_name,
            "movement_type": "sale",
            "quantity": -item.quantity,
            "reference": invoice_number,
            "created_by": current_user.email,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.inventory_movements.insert_one(movement_dict)
    
    return Invoice(**{**invoice_dict, "created_at": datetime.fromisoformat(invoice_dict["created_at"])})

@api_router.get("/invoices", response_model=List[Invoice])
async def get_invoices(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    query = {}
    if start_date or end_date:
        query["created_at"] = {}
        if start_date:
            query["created_at"]["$gte"] = start_date
        if end_date:
            query["created_at"]["$lte"] = end_date
    
    invoices = await db.invoices.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    for inv in invoices:
        if isinstance(inv.get('created_at'), str):
            inv['created_at'] = datetime.fromisoformat(inv['created_at'])
    return invoices

@api_router.get("/invoices/{invoice_number}", response_model=Invoice)
async def get_invoice(invoice_number: str, current_user: User = Depends(get_current_user)):
    invoice = await db.invoices.find_one({"invoice_number": invoice_number}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if isinstance(invoice.get('created_at'), str):
        invoice['created_at'] = datetime.fromisoformat(invoice['created_at'])
    return Invoice(**invoice)

# ==================== RETURNS ====================

@api_router.post("/returns", response_model=Return)
async def create_return(return_data: ReturnCreate, current_user: User = Depends(get_current_user)):
    # Verify invoice exists
    invoice = await db.invoices.find_one({"invoice_number": return_data.invoice_number})
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    total = sum(item.total for item in return_data.items)
    
    return_dict = {
        "invoice_number": return_data.invoice_number,
        "items": [item.model_dump() for item in return_data.items],
        "total": total,
        "created_by": current_user.email,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.returns.insert_one(return_dict)
    
    # Update invoice status
    await db.invoices.update_one(
        {"invoice_number": return_data.invoice_number},
        {"$set": {"status": "returned"}}
    )
    
    # Update inventory and create movements
    for item in return_data.items:
        await db.products.update_one(
            {"barcode": item.barcode},
            {"$inc": {"stock": item.quantity}}
        )
        
        movement_dict = {
            "barcode": item.barcode,
            "product_name": item.product_name,
            "movement_type": "return",
            "quantity": item.quantity,
            "reference": return_data.invoice_number,
            "created_by": current_user.email,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.inventory_movements.insert_one(movement_dict)
    
    return Return(**{**return_dict, "created_at": datetime.fromisoformat(return_dict["created_at"])})

@api_router.get("/returns", response_model=List[Return])
async def get_returns(current_user: User = Depends(get_current_user)):
    returns = await db.returns.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    for ret in returns:
        if isinstance(ret.get('created_at'), str):
            ret['created_at'] = datetime.fromisoformat(ret['created_at'])
    return returns

# ==================== PURCHASES ====================

@api_router.post("/purchases", response_model=Purchase)
async def create_purchase(purchase_data: PurchaseCreate, current_user: User = Depends(get_current_user)):
    total = sum(item.total for item in purchase_data.items)
    
    purchase_dict = {
        "supplier_name": purchase_data.supplier_name,
        "items": [item.model_dump() for item in purchase_data.items],
        "total": total,
        "created_by": current_user.email,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.purchases.insert_one(purchase_dict)
    
    # Update inventory and create movements
    for item in purchase_data.items:
        await db.products.update_one(
            {"barcode": item.barcode},
            {"$inc": {"stock": item.quantity}}
        )
        
        movement_dict = {
            "barcode": item.barcode,
            "product_name": item.product_name,
            "movement_type": "purchase",
            "quantity": item.quantity,
            "reference": purchase_data.supplier_name,
            "created_by": current_user.email,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.inventory_movements.insert_one(movement_dict)
    
    return Purchase(**{**purchase_dict, "created_at": datetime.fromisoformat(purchase_dict["created_at"])})

@api_router.get("/purchases", response_model=List[Purchase])
async def get_purchases(current_user: User = Depends(get_current_user)):
    purchases = await db.purchases.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    for purch in purchases:
        if isinstance(purch.get('created_at'), str):
            purch['created_at'] = datetime.fromisoformat(purch['created_at'])
    return purchases

# ==================== INVENTORY ====================

@api_router.get("/inventory", response_model=List[Product])
async def get_inventory(current_user: User = Depends(get_current_user)):
    products = await db.products.find({}, {"_id": 0}).to_list(1000)
    for prod in products:
        if isinstance(prod.get('created_at'), str):
            prod['created_at'] = datetime.fromisoformat(prod['created_at'])
    return products

@api_router.get("/inventory/movements", response_model=List[InventoryMovement])
async def get_inventory_movements(
    barcode: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    query = {}
    if barcode:
        query["barcode"] = barcode
    if start_date or end_date:
        query["created_at"] = {}
        if start_date:
            query["created_at"]["$gte"] = start_date
        if end_date:
            query["created_at"]["$lte"] = end_date
    
    movements = await db.inventory_movements.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    for mov in movements:
        if isinstance(mov.get('created_at'), str):
            mov['created_at'] = datetime.fromisoformat(mov['created_at'])
    return movements

# ==================== REPORTS ====================

@api_router.get("/reports/sales")
async def get_sales_report(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    query = {"status": "completed"}
    if start_date or end_date:
        query["created_at"] = {}
        if start_date:
            query["created_at"]["$gte"] = start_date
        if end_date:
            query["created_at"]["$lte"] = end_date
    
    invoices = await db.invoices.find(query, {"_id": 0}).to_list(1000)
    
    total_sales = sum(inv["total"] for inv in invoices)
    total_tax = sum(inv["total_tax"] for inv in invoices)
    
    return {
        "invoices": invoices,
        "summary": {
            "total_invoices": len(invoices),
            "total_sales": total_sales,
            "total_tax": total_tax
        }
    }

@api_router.get("/reports/inventory")
async def get_inventory_report(current_user: User = Depends(get_current_user)):
    products = await db.products.find({}, {"_id": 0}).to_list(1000)
    
    total_value = sum(p["purchase_price"] * p["stock"] for p in products)
    low_stock = [p for p in products if p["stock"] < 10]
    
    return {
        "products": products,
        "summary": {
            "total_products": len(products),
            "total_value": total_value,
            "low_stock_count": len(low_stock)
        }
    }

# ==================== DASHBOARD STATS ====================

@api_router.get("/dashboard/stats")
async def get_dashboard_stats(current_user: User = Depends(get_current_user)):
    # Count documents
    total_products = await db.products.count_documents({})
    total_clients = await db.clients.count_documents({})
    total_invoices = await db.invoices.count_documents({"status": "completed"})
    
    # Calculate total sales
    invoices = await db.invoices.find({"status": "completed"}, {"_id": 0, "total": 1}).to_list(10000)
    total_sales = sum(inv["total"] for inv in invoices)
    
    # Low stock products
    low_stock = await db.products.count_documents({"stock": {"$lt": 10}})
    
    return {
        "total_products": total_products,
        "total_clients": total_clients,
        "total_invoices": total_invoices,
        "total_sales": total_sales,
        "low_stock_products": low_stock
    }

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

@api_router.post("/import/categories", response_model=ImportResult)
async def import_categories(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
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
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            await db.categories.insert_one(category_data)
            success_count += 1
        except Exception as e:
            errors.append({"row": index + 2, "error": str(e)})
    
    return ImportResult(success=success_count, errors=errors, total=len(df))

@api_router.post("/import/products", response_model=ImportResult)
async def import_products(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    """
    Importar productos desde CSV o Excel
    Columnas requeridas: barcode, name, category, purchase_price, tax_rate
    Columnas opcionales: description, price_default, price_mayorista, price_minorista
    """
    df = read_file(file)
    
    required_columns = ['barcode', 'name', 'category', 'purchase_price', 'tax_rate']
    if not all(col in df.columns for col in required_columns):
        raise HTTPException(status_code=400, detail=f"Columnas requeridas: {', '.join(required_columns)}")
    
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
            for price_col in ['price_default', 'price_mayorista', 'price_minorista']:
                if price_col in df.columns and pd.notna(row.get(price_col)):
                    price_list_name = price_col.replace('price_', '')
                    prices.append({
                        "price_list_name": price_list_name,
                        "price": float(row[price_col])
                    })
            
            product_data = {
                "barcode": str(row['barcode']),
                "name": str(row['name']),
                "description": str(row.get('description', '')) if pd.notna(row.get('description')) else '',
                "category": str(row['category']),
                "purchase_price": float(row['purchase_price']),
                "tax_rate": float(row['tax_rate']),
                "prices": prices,
                "stock": 0,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            await db.products.insert_one(product_data)
            success_count += 1
        except Exception as e:
            errors.append({"row": index + 2, "error": str(e)})
    
    return ImportResult(success=success_count, errors=errors, total=len(df))

@api_router.post("/import/clients", response_model=ImportResult)
async def import_clients(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
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
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            await db.clients.insert_one(client_data)
            success_count += 1
        except Exception as e:
            errors.append({"row": index + 2, "error": str(e)})
    
    return ImportResult(success=success_count, errors=errors, total=len(df))

@api_router.post("/import/suppliers", response_model=ImportResult)
async def import_suppliers(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
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
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            await db.suppliers.insert_one(supplier_data)
            success_count += 1
        except Exception as e:
            errors.append({"row": index + 2, "error": str(e)})
    
    return ImportResult(success=success_count, errors=errors, total=len(df))

@api_router.get("/import/templates/{module_name}")
async def download_template(module_name: str, current_user: User = Depends(get_current_user)):
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

@api_router.get("/ticket-config")
async def get_ticket_config(current_user: User = Depends(get_current_user)):
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

@api_router.put("/ticket-config")
async def update_ticket_config(config: TicketConfigUpdate, current_user: User = Depends(get_current_user)):
    """Actualizar o crear la configuración del ticket"""
    update_data = {k: v for k, v in config.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    # Check if config exists
    existing = await db.ticket_config.find_one({})
    
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
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        default_config.update(update_data)
        await db.ticket_config.insert_one(default_config)
    
    updated = await db.ticket_config.find_one({}, {"_id": 0})
    return updated

# ==================== INVOICES ENHANCED (WITH PDF TICKETS) ====================

@api_router.get("/pos/invoices")
async def get_pos_invoices(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    client_document: Optional[str] = None,
    user_email: Optional[str] = None,
    invoice_number: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user)
):
    """Listar facturas POS con filtros y paginación"""
    query = {}
    
    # Apply filters
    if start_date:
        if "created_at" not in query:
            query["created_at"] = {}
        query["created_at"]["$gte"] = start_date
    
    if end_date:
        if "created_at" not in query:
            query["created_at"] = {}
        query["created_at"]["$lte"] = end_date + "T23:59:59"
    
    if client_document:
        query["client_document"] = {"$regex": client_document, "$options": "i"}
    
    if user_email:
        query["created_by"] = {"$regex": user_email, "$options": "i"}
    
    if invoice_number:
        query["invoice_number"] = {"$regex": invoice_number, "$options": "i"}
    
    if status:
        query["status"] = status
    
    # Get total count for pagination
    total = await db.invoices.count_documents(query)
    
    # Calculate skip
    skip = (page - 1) * limit
    
    # Get invoices
    invoices = await db.invoices.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    
    # Parse dates
    for inv in invoices:
        if isinstance(inv.get('created_at'), str):
            inv['created_at'] = inv['created_at']
    
    return {
        "invoices": invoices,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit
        }
    }

@api_router.get("/pos/invoices/{invoice_number}")
async def get_pos_invoice_detail(invoice_number: str, current_user: User = Depends(get_current_user)):
    """Obtener detalle de una factura específica"""
    invoice = await db.invoices.find_one({"invoice_number": invoice_number}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    return invoice

@api_router.get("/pos/invoices/{invoice_number}/ticket")
async def get_invoice_ticket(invoice_number: str, current_user: User = Depends(get_current_user)):
    """Generar y descargar ticket PDF de una factura"""
    # Get invoice
    invoice = await db.invoices.find_one({"invoice_number": invoice_number}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    
    # Get ticket config
    config = await db.ticket_config.find_one({}, {"_id": 0})
    if not config:
        config = {
            "company_name": "Mi Empresa",
            "nit": "",
            "phone": "",
            "email": "",
            "address": "",
            "ticket_width": 80,
            "footer_message": "¡Gracias por su compra!"
        }
    
    # Create PDF generator
    generator = TicketPDFGenerator(ticket_width=config.get("ticket_width", 80))
    
    # Prepare invoice data for the generator
    invoice_data = {
        "invoice_number": invoice["invoice_number"],
        "client_name": invoice.get("client_name", "Cliente General"),
        "client_document": invoice.get("client_document", ""),
        "items": invoice.get("items", []),
        "subtotal": invoice.get("subtotal", 0),
        "total_tax": invoice.get("total_tax", 0),
        "total": invoice.get("total", 0),
        "created_at": invoice.get("created_at"),
        "created_by": invoice.get("created_by", "")
    }
    
    # Generate PDF
    pdf_buffer = generator.generate_ticket(invoice_data, config)
    
    # Return as downloadable PDF
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=ticket_{invoice_number}.pdf"
        }
    )

# Include the routers
app.include_router(api_router)

# Include RBAC router
rbac_router = create_rbac_router(db)
app.include_router(rbac_router, prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()