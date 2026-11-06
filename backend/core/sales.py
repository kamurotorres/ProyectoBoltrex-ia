"""Cálculos de ventas para reportes y dashboard (backlog P1.14).

Reglas (decisión del usuario, opción A):
- Cuentan las facturas `completed`, `partial_return` y `returned`. El `total` de una factura
  ya es NETO: cada devolución lo rebaja (routers/invoices.create_return). Una factura devuelta
  por completo queda con total 0.
- Las devoluciones se descuentan en el periodo de la VENTA (no en el de la devolución).
  Ventas brutas = netas + devoluciones de esas mismas facturas.
- Los totales se calculan en MongoDB (aggregate), sin tope de documentos.
- Fechas nativas (P1.19). Rango de fechas por días LOCALES del navegador: `tz_offset_minutes` = getTimezoneOffset()
  (Colombia = 300). "Hasta" incluye el día completo.
"""
from datetime import datetime, time, timedelta, timezone
from typing import Optional

from core.errors import BusinessError

from core.database import db

SALE_STATUSES = ["completed", "partial_return", "returned"]


def _parse_day(value: str) -> datetime.date:
    try:
        return datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
    except (ValueError, AttributeError):
        raise BusinessError(f"Fecha inválida '{value}': usa el formato AAAA-MM-DD.")


def created_at_range(start_date: Optional[str], end_date: Optional[str], tz_offset_minutes: int = 0) -> Optional[dict]:
    """Filtro Mongo para `created_at` (texto ISO en UTC) que cubre días locales completos."""
    if not start_date and not end_date:
        return None
    offset = timedelta(minutes=tz_offset_minutes or 0)
    start = _parse_day(start_date) if start_date else None
    end = _parse_day(end_date) if end_date else None
    if start and end and start > end:
        raise BusinessError("La fecha 'desde' no puede ser posterior a la fecha 'hasta'.")
    cond = {}
    if start:
        # Medianoche local → UTC (hora local + desfase). P1.19: se compara con fechas nativas.
        cond["$gte"] = datetime.combine(start, time.min, tzinfo=timezone.utc) + offset
    if end:
        cond["$lte"] = datetime.combine(end, time.max, tzinfo=timezone.utc) + offset
    return cond


def invoices_query(start_date=None, end_date=None, tz_offset_minutes: int = 0) -> dict:
    query = {"status": {"$in": SALE_STATUSES}}
    rng = created_at_range(start_date, end_date, tz_offset_minutes)
    if rng:
        query["created_at"] = rng
    return query


async def sales_summary(query: dict) -> dict:
    """Totales netos, devoluciones y brutos de las facturas que cumplen `query`."""
    pipeline = [
        {"$match": query},
        {"$lookup": {"from": "returns", "localField": "invoice_number", "foreignField": "invoice_number", "as": "_ret"}},
        {"$group": {
            "_id": None,
            "invoices": {"$sum": 1},
            "completed": {"$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}},
            "partial_return": {"$sum": {"$cond": [{"$eq": ["$status", "partial_return"]}, 1, 0]}},
            "returned": {"$sum": {"$cond": [{"$eq": ["$status", "returned"]}, 1, 0]}},
            "net_sales": {"$sum": {"$ifNull": ["$total", 0]}},
            "net_tax": {"$sum": {"$ifNull": ["$total_tax", 0]}},
            "net_subtotal": {"$sum": {"$ifNull": ["$subtotal", 0]}},
            "returns_total": {"$sum": {"$sum": "$_ret.total"}},
            "returns_tax": {"$sum": {"$sum": "$_ret.total_tax"}},
            "returns_count": {"$sum": {"$size": "$_ret"}},
        }},
    ]
    rows = await db.invoices.aggregate(pipeline).to_list(1)
    r = rows[0] if rows else {}
    net_sales = round(r.get("net_sales", 0) or 0, 2)
    returns_total = round(r.get("returns_total", 0) or 0, 2)
    return {
        # Facturas que siguen siendo venta (no devueltas por completo).
        "total_invoices": (r.get("completed", 0) or 0) + (r.get("partial_return", 0) or 0),
        "completed_invoices": r.get("completed", 0) or 0,
        "partial_return_invoices": r.get("partial_return", 0) or 0,
        "returned_invoices": r.get("returned", 0) or 0,
        "all_invoices": r.get("invoices", 0) or 0,
        "gross_sales": round(net_sales + returns_total, 2),
        "returns_total": returns_total,
        "returns_count": r.get("returns_count", 0) or 0,
        "total_sales": net_sales,                       # ventas NETAS (compatibilidad con la pantalla)
        "total_tax": round(r.get("net_tax", 0) or 0, 2),  # IVA neto
        "gross_tax": round((r.get("net_tax", 0) or 0) + (r.get("returns_tax", 0) or 0), 2),
        "net_subtotal": round(r.get("net_subtotal", 0) or 0, 2),
    }
