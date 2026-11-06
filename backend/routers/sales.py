"""Ventas: crear factura (POS), facturas, detalle, listado del POS y ticket (mantenimiento fase 3: separado de routers/invoices.py)."""
import re
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from core.database import db
from core.permissions import require_permission, require_any_permission
from models.auth import User
from models.billing import Invoice, InvoiceCreate
from fastapi.responses import StreamingResponse

from core.sales import created_at_range
from core.pagination import page_params, paginate, search_filter, combine

from services import sales as sales_service

from services import tickets as tickets_service

router = APIRouter(tags=["Ventas"])


@router.post("/invoices", response_model=Invoice)
async def create_invoice(invoice_data: InvoiceCreate, current_user: User = Depends(require_permission("pos", "create"))):
    """Venta del POS (contado o crédito). Reglas en services/sales.create_sale."""
    return Invoice(**await sales_service.create_sale(invoice_data=invoice_data, current_user=current_user))


@router.get("/invoices")
async def get_invoices(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    tz_offset_minutes: int = 0,
    search: Optional[str] = None,
    exclude_status: Optional[str] = None,
    pg: dict = Depends(page_params),
    current_user: User = Depends(require_any_permission(("invoices", "read"), ("returns", "read")))
):
    """Facturas paginadas, más recientes primero (P1.18). `search`: número, cliente o documento."""
    rng = created_at_range(start_date, end_date, tz_offset_minutes)
    query = combine(
        {"created_at": rng} if rng else None,
        {"status": {"$ne": exclude_status}} if exclude_status else None,
        search_filter(search, ["invoice_number", "client_name", "client_document"]),
    )
    return await paginate(db.invoices, query, [("created_at", -1)], **pg)


@router.get("/invoices/{invoice_number}")
async def get_invoice(invoice_number: str, current_user: User = Depends(require_any_permission(("invoices", "read"), ("returns", "read")))):
    invoice = await db.invoices.find_one({"invoice_number": invoice_number}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if isinstance(invoice.get('created_at'), str):
        invoice['created_at'] = invoice['created_at']

    # Get payment history (abonos)
    payments = await db.fio_payments.find(
        {"invoice_number": invoice_number},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)

    # Get returns history (devoluciones)
    returns = await db.returns.find(
        {"invoice_number": invoice_number},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)

    return {
        **invoice,
        "payments_history": payments,
        "returns_history": returns
    }


@router.get("/pos/invoices")
async def get_pos_invoices(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    client_document: Optional[str] = None,
    user_email: Optional[str] = None,
    invoice_number: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    page_size: Optional[int] = Query(None, ge=1, le=200),
    tz_offset_minutes: int = 0,
    current_user: User = Depends(require_any_permission(("invoices", "read"), ("pos", "read")))
):
    """Listar facturas POS con filtros y paginación"""
    query = {}

    # P1.14: días locales completos (antes se cortaba a las 23:59:59 UTC = 6:59 p. m. en Colombia).
    rng = created_at_range(start_date, end_date, tz_offset_minutes)
    if rng:
        query["created_at"] = rng

    if client_document:
        query["client_document"] = {"$regex": re.escape(client_document), "$options": "i"}

    if user_email:
        query["created_by"] = {"$regex": re.escape(user_email), "$options": "i"}

    if invoice_number:
        query["invoice_number"] = {"$regex": re.escape(invoice_number), "$options": "i"}

    if status:
        query["status"] = status

    # P1.18: formato común {items, total, page, page_size, pages} (como el resto de listados).
    # `page_size` reemplaza a `limit`; se conservan "invoices" y "pagination" por compatibilidad.
    size = page_size or limit
    result = await paginate(db.invoices, query, [("created_at", -1)], page=page, page_size=size)
    result["invoices"] = result["items"]
    result["pagination"] = {"page": page, "limit": size, "total": result["total"], "pages": result["pages"]}
    return result


@router.get("/pos/invoices/{invoice_number}")
async def get_pos_invoice_detail(invoice_number: str, current_user: User = Depends(require_any_permission(("invoices", "read"), ("pos", "read")))):
    """Obtener detalle de una factura específica"""
    invoice = await db.invoices.find_one({"invoice_number": invoice_number}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    return invoice


@router.get("/pos/invoices/{invoice_number}/ticket")
async def get_invoice_ticket(invoice_number: str, current_user: User = Depends(require_any_permission(("invoices", "read"), ("pos", "read")))):
    """Generar y descargar ticket PDF de una factura"""
    pdf_buffer = await tickets_service.invoice_ticket_pdf(invoice_number=invoice_number, current_user=current_user)
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=ticket_{invoice_number}.pdf"
        }
    )
