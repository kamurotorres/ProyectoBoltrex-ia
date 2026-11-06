from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone
from typing import List, Optional

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

class PriceListUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

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
    tax_rate: float
    prices: List[ProductPrice] = []
    stock: int = 0
    min_stock: Optional[int] = None   # P2.34: vacío = el stock mínimo general (Config. Sistema)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ProductCreate(BaseModel):
    barcode: str
    name: str
    description: Optional[str] = None
    category: str
    purchase_price: float
    tax_rate: float
    prices: List[ProductPrice] = []
    min_stock: Optional[int] = Field(default=None, ge=0, le=1_000_000)

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    purchase_price: Optional[float] = None
    tax_rate: Optional[float] = None
    prices: Optional[List[ProductPrice]] = None
    min_stock: Optional[int] = Field(default=None, ge=0, le=1_000_000)   # null = volver al general

class InventoryMovement(BaseModel):
    model_config = ConfigDict(extra="ignore")
    barcode: str
    product_name: str
    movement_type: str
    quantity: int
    reference: Optional[str] = None
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
