"""Fios (cuentas por cobrar y abonos) (mantenimiento fase 3: separado de routers/invoices.py)."""
from fastapi import APIRouter, HTTPException, Depends
from datetime import timedelta
from typing import Optional
from core.dates import now_utc, as_datetime
from core.database import db
from core.permissions import require_permission, require_any_permission
from models.auth import User
from models.billing import FioPaymentCreate
import io
import csv
from fastapi.responses import StreamingResponse

from core import credit
from core.pagination import page_params
from services.fios import account_status_label as _account_status_label, fios_pipeline as _fios_pipeline

from services import fios as fios_service

router = APIRouter(tags=["Fios"])


@router.get("/fios")
async def get_fios_accounts(search: Optional[str] = None, status: Optional[str] = None, pg: dict = Depends(page_params),
                            current_user: User = Depends(require_permission("fios", "read"))):
    """Cuentas por cobrar agrupadas por cliente (tipo + número), paginadas (P1.18), con vencimientos
    y antigüedad (P2.30). Primero las más atrasadas, luego por saldo. `status`: overdue · due_soon ·
    current · 1_30 · 31_60 · 61_90 · 90_plus."""
    return await fios_service.accounts_page(search=search, status=status, pg=pg, current_user=current_user)


@router.get("/fios/export")
async def export_fios_accounts(search: Optional[str] = None, status: Optional[str] = None, format: str = "csv",
                               tz_offset_minutes: int = 0, current_user: User = Depends(require_permission("fios", "read"))):
    """P2.30: cartera completa (con el filtro activo), con antigüedad por tramo. P2.33: csv · xlsx · pdf."""
    from core.exporting import check_format
    if check_format(format) != "csv":
        from services.exports import fios_report
        return await fios_report(search, status, current_user, format, tz_offset_minutes)
    now = now_utc()
    settings = await credit.get_settings()
    rows = await db.invoices.aggregate(
        _fios_pipeline(search, status, now, settings) + [{"$sort": {"max_days_overdue": -1, "balance": -1}}]
    ).to_list(None)
    out = io.StringIO()
    w = csv.writer(out, delimiter=";")
    labels = [label for key, label, *_ in credit.BUCKETS if key != "current"]
    w.writerow(["Tipo doc.", "Documento", "Cliente", "Facturas", "Total crédito", "Abonado", "Saldo", "Vencido",
                "Por vencer", "Días máx. de atraso", "Próximo vencimiento", "Estado", *labels])
    for a in rows:
        nd = a.get("next_due_date")
        w.writerow([a.get("client_document_type") or "", a["client_document"], a.get("client_name", ""), a["invoices_count"],
                    round(a["total_credit"], 2), round(a["total_paid"], 2), round(a["balance"], 2),
                    round(a["overdue_balance"], 2), round(a["due_soon_balance"], 2), int(a.get("max_days_overdue") or 0),
                    (as_datetime(nd) - timedelta(minutes=credit.BUSINESS_TZ_OFFSET_MINUTES)).strftime("%Y-%m-%d") if nd else "",
                    _account_status_label(a),
                    *[round(a["buckets"].get(key, 0), 2) for key, *_ in credit.BUCKETS if key != "current"]])
    data = "\ufeff" + out.getvalue()   # BOM: Excel abre bien las tildes
    return StreamingResponse(iter([data]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f"attachment; filename=cartera_{now.strftime('%Y%m%d')}.csv"})


@router.get("/fios/{client_document}")
async def get_fios_client_detail(client_document: str, document_type: Optional[str] = None,
                                 current_user: User = Depends(require_permission("fios", "read"))):
    """Obtener detalle de cuentas por cobrar de un cliente específico (tipo + número, P1.15)"""
    return await fios_service.client_detail(client_document=client_document, document_type=document_type, current_user=current_user)


@router.get("/fios/invoice/{invoice_number}")
async def get_fios_invoice_detail(invoice_number: str, current_user: User = Depends(require_permission("fios", "read"))):
    """Obtener detalle de una factura por cobrar específica"""
    invoice = await db.invoices.find_one({"invoice_number": invoice_number}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    if invoice.get("payment_status") != "por_cobrar":
        raise HTTPException(status_code=400, detail="Esta factura no es una cuenta por cobrar")

    # Get payment history for this invoice
    payments = await db.fio_payments.find({
        "invoice_number": invoice_number
    }, {"_id": 0}).sort("created_at", -1).to_list(None)

    return {
        "invoice": invoice,
        "payments": payments
    }


@router.post("/fios/{invoice_number}/payment")
async def register_fio_payment(
    invoice_number: str,
    payment: FioPaymentCreate,
    current_user: User = Depends(require_permission("fios", "create"))
):
    """Registrar un abono a una factura por cobrar"""
    return await fios_service.register_payment(invoice_number=invoice_number, payment=payment, current_user=current_user)


@router.get("/fios/payments/{invoice_number}")
async def get_invoice_payments(invoice_number: str, current_user: User = Depends(require_any_permission(("fios", "read"), ("invoices", "read")))):
    """Obtener historial de pagos de una factura"""
    payments = await db.fio_payments.find({
        "invoice_number": invoice_number
    }, {"_id": 0}).sort("created_at", -1).to_list(None)

    return payments
