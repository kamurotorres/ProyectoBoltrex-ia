"""Esquemas de entrada de ajustes de inventario y motivos (P2.32; movidos del router en la fase 3)."""
from typing import List, Optional

from pydantic import BaseModel, Field


class ReasonIn(BaseModel):
    name: str
    description: Optional[str] = None
    applies_to: List[str] = Field(default_factory=lambda: ["entrada", "salida", "conteo"])
    requires_note: bool = False
    is_active: bool = True


class AdjustmentItemIn(BaseModel):
    barcode: str
    quantity: Optional[int] = None        # entrada / salida: unidades (> 0)
    counted: Optional[int] = None         # conteo: unidades contadas (≥ 0)
    expected_stock: Optional[int] = None  # conteo: stock que mostraba el sistema al contar


class AdjustmentIn(BaseModel):
    kind: str
    reason: str
    notes: Optional[str] = None
    items: List[AdjustmentItemIn]
