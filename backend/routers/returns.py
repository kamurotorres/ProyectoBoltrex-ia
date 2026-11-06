"""Devoluciones (mantenimiento fase 3: separado de routers/invoices.py)."""
from fastapi import APIRouter, Depends
from typing import Optional
from core.database import db
from core.permissions import require_permission
from models.auth import User
from models.billing import Return, ReturnCreate

from core.pagination import page_params, paginate, search_filter, combine

from services import returns as returns_service

router = APIRouter(tags=["Devoluciones"])




@router.post("/returns", response_model=Return)
async def create_return(return_data: ReturnCreate, current_user: User = Depends(require_permission("returns", "create"))):
    """Registrar una devolución validada contra la factura original.

    - Cada producto debe estar en la factura y la cantidad debe ser > 0 y no superar
      lo vendido menos lo ya devuelto en devoluciones anteriores.
    - Precio unitario e IVA se toman de la factura; el importe lo calcula el servidor.
    - Se recalculan subtotal, IVA y total de la factura (y el saldo si es a crédito).
    """
    return Return(**await returns_service.create_return(return_data=return_data, current_user=current_user))


@router.get("/returns")
async def get_returns(search: Optional[str] = None, invoice_number: Optional[str] = None, pg: dict = Depends(page_params),
                      current_user: User = Depends(require_permission("returns", "read"))):
    """Devoluciones paginadas, más recientes primero (P1.18)."""
    query = combine({"invoice_number": invoice_number} if invoice_number else None,
                    search_filter(search, ["invoice_number", "created_by"]))
    return await paginate(db.returns, query, [("created_at", -1)], **pg)
