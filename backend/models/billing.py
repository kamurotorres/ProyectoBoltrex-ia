from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone
from typing import List, Optional

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

class TaxRate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    rate: float
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

class Invoice(BaseModel):
    model_config = ConfigDict(extra="ignore")
    invoice_number: str
    client_document: str
    client_name: str
    items: List[InvoiceItem]
    subtotal: float
    total_tax: float
    total: float
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "completed"
    payment_status: str = "pagado"
    payment_method: Optional[str] = None
    amount_paid: float = 0
    balance: float = 0

class InvoiceCreate(BaseModel):
    client_document: str
    items: List[InvoiceItem]
    payment_status: str = "pagado"
    payment_method: Optional[str] = None

class FioPayment(BaseModel):
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
    model_config = ConfigDict(extra="ignore")
    client_document: str
    client_name: str
    total_credit: float
    total_paid: float
    balance: float
    invoices_count: int

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
