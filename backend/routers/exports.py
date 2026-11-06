"""Reportes exportables a Excel / PDF / CSV (backlog P2.33). Motor en core/exporting.py.

Los endpoints de exportación que ya existían (`/reports/sales/export`, `/reports/inventory/export`,
`/fios/export`, `/inventory/adjustments/export`) aceptan `format=xlsx|pdf` y llaman a estos
constructores; con `format=csv` (o sin formato) siguen respondiendo el CSV de siempre.
Endpoints nuevos aquí: compras, estado de cuenta del cliente y cierre de caja.
"""
from typing import Optional

from fastapi import APIRouter, Depends

from core.permissions import require_permission
from models.auth import User


from services import exports as exports_service

router = APIRouter(tags=["Exportaciones"])


# ==================================================================== VENTAS


# ==================================================================== INVENTARIO


# ==================================================================== COMPRAS (nuevo)

@router.get("/purchases/export")
async def export_purchases(format: str = "xlsx", search: Optional[str] = None, status: Optional[str] = None,
                           start_date: Optional[str] = None, end_date: Optional[str] = None, tz_offset_minutes: int = 0,
                           current_user: User = Depends(require_permission("purchases", "read"))):
    return await exports_service.purchases_export(format=format, search=search, status=status, start_date=start_date, end_date=end_date, tz_offset_minutes=tz_offset_minutes, current_user=current_user)


# ==================================================================== CARTERA


@router.get("/fios/statement/{client_document}")
async def client_statement(client_document: str, document_type: Optional[str] = None, format: str = "pdf",
                           tz_offset_minutes: int = 0, current_user: User = Depends(require_permission("fios", "read"))):
    """Estado de cuenta del cliente: facturas pendientes (vencimiento y estado) y sus abonos."""
    return await exports_service.client_statement(client_document=client_document, document_type=document_type, format=format, tz_offset_minutes=tz_offset_minutes, current_user=current_user)


# ==================================================================== AJUSTES


# ==================================================================== CIERRE DE CAJA (A4)


@router.get("/cash/sessions/{session_id}/export")
async def export_cash_session(session_id: str, format: str = "pdf", tz_offset_minutes: int = 0,
                              current_user: User = Depends(require_permission("cash", "read"))):
    return await exports_service.cash_session_export(session_id=session_id, format=format, tz_offset_minutes=tz_offset_minutes, current_user=current_user)
