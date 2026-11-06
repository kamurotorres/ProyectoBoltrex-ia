from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query, Request, Response, BackgroundTasks
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument
from core.database import db
from core.database import get_db
from core.security import get_current_user, get_password_hash, verify_password, create_access_token
from core.permissions import require_permission, require_any_permission
from core.sales import invoices_query, sales_summary, SALE_STATUSES
from core.pagination import page_params, paginate, search_filter, combine
from routers.inventory import inventory_summary, LOW_STOCK_THRESHOLD
from core.dashboard import build_dashboard
from core.user_protection import actor_is_admin
from models.auth import *
from models.billing import *
from models.inventory import *
from models.entities import *
import io
import csv
from fastapi.responses import StreamingResponse
from ticket_generator import TicketPDFGenerator

router = APIRouter(tags=["Reports"])
db_dep = Depends(get_db)
# ==================== REPORTS ====================

STATUS_LABELS = {"completed": "Completada", "partial_return": "Devolución parcial", "returned": "Devuelta"}


def _csv_response(filename: str, header: list, rows):
    """CSV completo generado en el servidor (P1.18). Con BOM para que Excel lea bien las tildes."""
    async def agen():
        # `rows` es un generador asíncrono: se vuelca fila a fila sin cargar todo en memoria.
        buf = io.StringIO()
        writer = csv.writer(buf)
        buf.write("\ufeff")
        writer.writerow(header)
        yield buf.getvalue()
        async for row in rows:
            buf.seek(0)
            buf.truncate(0)
            writer.writerow(row)
            yield buf.getvalue()

    return StreamingResponse(agen(), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def _local(value, tz_offset_minutes: int) -> str:
    """Fecha (nativa o texto antiguo) → hora local del usuario 'AAAA-MM-DD HH:MM'."""
    from core.dates import as_datetime
    dt = as_datetime(value)
    if not isinstance(dt, datetime):
        return str(value or "")
    return (dt - timedelta(minutes=tz_offset_minutes or 0)).strftime("%Y-%m-%d %H:%M")


@router.get("/reports/sales")
async def get_sales_report(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    tz_offset_minutes: int = Query(0, description="getTimezoneOffset() del navegador, para filtrar por días locales"),
    pg: dict = Depends(page_params),
    current_user: User = Depends(require_permission("reports", "read"))
):
    """Ventas del periodo (P1.14): incluye devoluciones parciales con su valor neto y
    las devueltas por completo (total 0). Totales sobre TODO el periodo; detalle paginado (P1.18)."""
    query = invoices_query(start_date, end_date, tz_offset_minutes)
    page = await paginate(db.invoices, query, [("created_at", -1)], **pg)
    page["summary"] = await sales_summary(query)
    return page


@router.get("/reports/sales/export")
async def export_sales_report(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    tz_offset_minutes: int = 0,
    format: str = "csv",
    current_user: User = Depends(require_permission("reports", "read"))
):
    """TODAS las facturas del periodo (P1.18). P2.33: format = csv (por defecto) · xlsx · pdf."""
    from core.exporting import check_format
    if check_format(format) != "csv":
        from routers.exports import sales_report
        return await sales_report(start_date, end_date, tz_offset_minutes, current_user, format)
    query = invoices_query(start_date, end_date, tz_offset_minutes)

    async def rows():
        async for inv in db.invoices.find(query, {"_id": 0}).sort([("created_at", -1), ("_id", -1)]):
            yield [inv.get("invoice_number"), _local(inv.get("created_at"), tz_offset_minutes),
                   inv.get("client_document_type") or "", inv.get("client_document"), inv.get("client_name"),
                   STATUS_LABELS.get(inv.get("status"), inv.get("status")), inv.get("payment_status"),
                   inv.get("payment_method") or "", round(inv.get("subtotal", 0) or 0, 2),
                   round(inv.get("total_tax", 0) or 0, 2), round(inv.get("total", 0) or 0, 2), inv.get("created_by")]

    name = f"ventas_{start_date or 'inicio'}_{end_date or 'hoy'}.csv"
    return _csv_response(name, ["factura", "fecha", "tipo_documento", "documento", "cliente", "estado", "estado_pago",
                                "forma_pago", "subtotal_neto", "iva_neto", "total_neto", "vendedor"], rows())


@router.get("/reports/inventory")
async def get_inventory_report(search: Optional[str] = None, pg: dict = Depends(page_params),
                               current_user: User = Depends(require_permission("reports", "read"))):
    """Inventario: totales sobre TODOS los productos (calculados en la base) + detalle paginado (P1.18)."""
    query = search_filter(search, ["barcode", "name", "category"]) or {}
    page = await paginate(db.products, query, [("name", 1)], **pg)
    page["summary"] = await inventory_summary()
    return page


@router.get("/reports/inventory/export")
async def export_inventory_report(format: str = "csv", tz_offset_minutes: int = 0,
                                  current_user: User = Depends(require_permission("reports", "read"))):
    """TODOS los productos (P1.18). P2.33: format = csv (por defecto) · xlsx · pdf."""
    from core.exporting import check_format
    if check_format(format) != "csv":
        from routers.exports import inventory_report
        return await inventory_report(current_user, format, tz_offset_minutes)
    async def rows():
        from core.alerts import effective_min, get_inventory_settings
        threshold = (await get_inventory_settings())["low_stock_threshold"]
        async for p in db.products.find({}, {"_id": 0}).sort([("name", 1), ("_id", 1)]):
            stock = p.get("stock", 0) or 0
            cost = p.get("purchase_price", 0) or 0
            default = next((x.get("price") for x in (p.get("prices") or []) if x.get("price_list_name") == "default"), "")
            yield [p.get("barcode"), p.get("name"), p.get("category"), stock, cost, round(cost * stock, 2),
                   p.get("tax_rate", 0), default, effective_min(p, threshold), "sí" if stock < effective_min(p, threshold) else "no"]

    return _csv_response("inventario.csv", ["codigo", "nombre", "categoria", "stock", "costo", "valor_inventario",
                                            "iva", "precio_default", "stock_minimo", "bajo_stock"], rows())

# ==================== DASHBOARD STATS ====================

@router.get("/dashboard/summary")
async def get_dashboard_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    tz_offset_minutes: int = 0,
    seller: Optional[str] = None,
    current_user: User = Depends(require_permission("dashboard", "read")),
):
    """Dashboard del periodo (P2.29): KPIs con comparación, ventas por día, formas de pago,
    top productos, ventas por hora, cartera y alertas de stock.
    Visibilidad (opción B): un vendedor ve solo sus ventas; el Administrador ve todo y puede
    filtrar por vendedor (`seller`)."""
    is_admin = await actor_is_admin(current_user.email)
    effective_seller = (seller or None) if is_admin else current_user.email
    data = await build_dashboard(start_date, end_date, tz_offset_minutes, effective_seller)
    data["scope"] = {"is_admin": is_admin, "seller": effective_seller}
    if is_admin:
        data["sellers"] = sorted(s for s in await db.invoices.distinct("created_by") if s)
    return data

@router.get("/dashboard/stats")
async def get_dashboard_stats(current_user: User = Depends(require_permission("dashboard", "read"))):
    total_products = await db.products.count_documents({})
    total_clients = await db.clients.count_documents({})

    # P1.14: ventas netas de todas las facturas (las devoluciones parciales ya no desaparecen).
    summary = await sales_summary(invoices_query())

    low_stock = await db.products.count_documents({"stock": {"$lt": 10}})

    return {
        "total_products": total_products,
        "total_clients": total_clients,
        "total_invoices": summary["total_invoices"],
        "total_sales": summary["total_sales"],
        "gross_sales": summary["gross_sales"],
        "returns_total": summary["returns_total"],
        "low_stock_products": low_stock
    }
