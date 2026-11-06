from pydantic import BaseModel, Field, EmailStr, ConfigDict, validator
from datetime import datetime, timezone
from typing import Optional, List

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
    price_list: str = "default"
    credit_days: Optional[int] = None      # P2.30: plazo propio (vacío = el de Config. Sistema)
    credit_limit: Optional[float] = None   # P2.30: cupo de crédito (vacío/0 = sin límite)
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
    credit_days: Optional[int] = Field(default=None, ge=0, le=3650)
    credit_limit: Optional[float] = Field(default=None, ge=0)

    @validator('email', 'phone', 'address', pre=True)
    def empty_str_to_none(cls, v):
        if v == '':
            return None
        return v

class ClientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    price_list: Optional[str] = None
    credit_days: Optional[int] = Field(default=None, ge=0, le=3650)
    credit_limit: Optional[float] = Field(default=None, ge=0)

    @validator('email', 'phone', 'address', pre=True)
    def empty_str_to_none(cls, v):
        if v == '':
            return None
        return v

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

    @validator('email', 'phone', 'address', 'contact_name', pre=True)
    def empty_str_to_none(cls, v):
        if v == '':
            return None
        return v

class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None

    @validator('email', 'phone', 'address', 'contact_name', pre=True)
    def empty_str_to_none(cls, v):
        if v == '':
            return None
        return v

class PurchaseItem(BaseModel):
    barcode: str
    product_name: str
    quantity: int
    unit_cost: float
    total: float

class Purchase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    purchase_number: str
    supplier_name: str
    items: List[PurchaseItem]
    total: float
    status: str = "borrador"
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PurchaseCreate(BaseModel):
    supplier_name: str
    items: List[PurchaseItem]

class PurchaseUpdate(BaseModel):
    supplier_name: Optional[str] = None
    items: Optional[List[PurchaseItem]] = None

class TicketConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    company_name: str
    nit: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    ticket_width: int = 80
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
