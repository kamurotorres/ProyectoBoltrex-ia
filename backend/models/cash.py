"""Esquemas de entrada de la caja (P2.31; movidos del router en la fase 3)."""
from typing import Dict, Optional

from pydantic import BaseModel, Field


class CashSettings(BaseModel):
    require_open_session: bool


class OpenCash(BaseModel):
    opening_amount: float = Field(..., ge=0, description="Base inicial en efectivo")
    notes: Optional[str] = Field(None, max_length=300)


class ManualMovement(BaseModel):
    kind: str = Field(..., pattern="^(income|expense)$", description="income = ingreso · expense = egreso")
    amount: float = Field(..., gt=0)
    reason: str = Field(..., min_length=3, max_length=200)


class CloseCash(BaseModel):
    counted_cash: Optional[float] = None
    denominations: Optional[Dict[str, int]] = None
    notes: Optional[str] = Field(None, max_length=500)
    reconciled: Optional[Dict[str, bool]] = None   # otras formas de pago conciliadas con sus comprobantes
