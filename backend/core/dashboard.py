"""Cálculos del Dashboard (backlog P2.29).

Decisiones del usuario:
- Visibilidad (opción B): cada vendedor ve SOLO sus ventas (`created_by`); el rol Administrador
  ve toda la tienda y puede filtrar por vendedor.
- Periodo por defecto: hoy (lo envía el frontend). Días locales con `tz_offset_minutes` (P1.14).
- Ganancia = (precio de venta − precio de compra) × cantidad, con el precio de venta SIN IVA
  (el IVA no es ganancia) y el precio de compra guardado en cada venta (`items[].unit_cost`).
  Las devoluciones descuentan la ganancia de lo devuelto. Ventas anteriores a P2.29 no tienen
  costo registrado: se excluyen de la ganancia y se informan aparte.
- Mismas reglas de "venta" que Reportes (`core/sales`): ventas netas por fecha de la venta.
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from core.database import db
from core.sales import created_at_range, invoices_query, sales_summary

CREDIT_LABEL = "Crédito (Fios)"


def tz_string(offset_minutes: int) -> str:
    """getTimezoneOffset() → zona de MongoDB. Colombia (300) → '-05:00'."""
    total = -(offset_minutes or 0)
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    return f"{sign}{total // 60:02d}:{total % 60:02d}"


def _bucket_unit(days: int) -> str:
    if days <= 31:
        return "day"
    if days <= 180:
        return "week"
    return "month"


def _local_date(dt: datetime, offset_minutes: int):
    return (dt - timedelta(minutes=offset_minutes or 0)).date()


def _buckets(start_local, end_local, unit: str) -> List:
    out, d = [], start_local
    if unit == "week":
        d = d - timedelta(days=d.weekday())
    if unit == "month":
        d = d.replace(day=1)
    while d <= end_local:
        out.append(d)
        if unit == "day":
            d += timedelta(days=1)
        elif unit == "week":
            d += timedelta(days=7)
        else:
            d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    return out


async def _items_stats(query: dict) -> Dict:
    """Unidades y ganancia netas (vendido − devuelto) de las facturas de `query`."""
    sold = await db.invoices.aggregate([
        {"$match": query},
        {"$unwind": "$items"},
        {"$group": {
            "_id": None,
            "units": {"$sum": "$items.quantity"},
            "profit": {"$sum": {"$cond": [
                {"$ne": [{"$ifNull": ["$items.unit_cost", None]}, None]},
                {"$multiply": [{"$subtract": ["$items.unit_price", "$items.unit_cost"]}, "$items.quantity"]}, 0]}},
            "lines_without_cost": {"$sum": {"$cond": [{"$eq": [{"$ifNull": ["$items.unit_cost", None]}, None]}, 1, 0]}},
            "invoices_without_cost": {"$addToSet": {"$cond": [
                {"$eq": [{"$ifNull": ["$items.unit_cost", None]}, None]}, "$invoice_number", "$$REMOVE"]}},
        }},
    ]).to_list(1)
    returned = await db.invoices.aggregate([
        {"$match": query},
        {"$lookup": {"from": "returns", "localField": "invoice_number", "foreignField": "invoice_number", "as": "r"}},
        {"$unwind": "$r"},
        {"$unwind": "$r.items"},
        {"$group": {
            "_id": None,
            "units": {"$sum": "$r.items.quantity"},
            "profit": {"$sum": {"$cond": [
                {"$ne": [{"$ifNull": ["$r.items.unit_cost", None]}, None]},
                {"$multiply": [{"$subtract": ["$r.items.unit_price", "$r.items.unit_cost"]}, "$r.items.quantity"]}, 0]}},
        }},
    ]).to_list(1)
    s = sold[0] if sold else {}
    r = returned[0] if returned else {}
    return {
        "units": (s.get("units") or 0) - (r.get("units") or 0),
        "profit": round((s.get("profit") or 0) - (r.get("profit") or 0), 2),
        "invoices_without_cost": len(s.get("invoices_without_cost") or []),
    }


async def _kpis(query: dict) -> Dict:
    summary = await sales_summary(query)
    items = await _items_stats(query)
    count = summary["total_invoices"]
    return {
        "net_sales": summary["total_sales"],
        "gross_sales": summary["gross_sales"],
        "returns_total": summary["returns_total"],
        "invoices": count,
        "avg_ticket": round(summary["total_sales"] / count, 2) if count else 0,
        "units": items["units"],
        "profit": items["profit"],
        "invoices_without_cost": items["invoices_without_cost"],
    }


def _change(current: float, previous: float) -> Optional[float]:
    """Variación % frente al periodo anterior (None si antes era 0: no hay base de comparación)."""
    if not previous:
        return None
    return round((current - previous) / abs(previous) * 100, 1)


async def build_dashboard(start_date: Optional[str], end_date: Optional[str], tz_offset_minutes: int,
                          seller: Optional[str]) -> Dict:
    offset = tz_offset_minutes or 0
    if not start_date or not end_date:
        today = _local_date(datetime.now(timezone.utc), offset).isoformat()
        start_date, end_date = start_date or today, end_date or today
    rng = created_at_range(start_date, end_date, offset)          # valida formato y orden
    start, end = rng["$gte"], rng["$lte"]
    length = (end - start) + timedelta(microseconds=1)
    prev_start, prev_end = start - length, start - timedelta(microseconds=1)

    seller_filter = {"created_by": seller} if seller else {}
    query = {**invoices_query(start_date, end_date, offset), **seller_filter}
    prev_query = {**invoices_query(), "created_at": {"$gte": prev_start, "$lte": prev_end}, **seller_filter}

    current = await _kpis(query)
    previous = await _kpis(prev_query)
    comparison = {k: _change(current[k], previous[k]) for k in ("net_sales", "invoices", "avg_ticket", "units", "profit")}

    tz = tz_string(offset)
    start_local, end_local = _local_date(start, offset), _local_date(end, offset)
    unit = _bucket_unit((end_local - start_local).days + 1)

    # --- Ventas por día / semana / mes
    trunc = {"date": "$created_at", "unit": unit, "timezone": tz}
    if unit == "week":
        trunc["startOfWeek"] = "monday"
    rows = await db.invoices.aggregate([
        {"$match": query},
        {"$group": {"_id": {"$dateTrunc": trunc}, "net": {"$sum": "$total"},
                    "invoices": {"$sum": {"$cond": [{"$in": ["$status", ["completed", "partial_return"]]}, 1, 0]}}}},
    ]).to_list(None)
    by_bucket = {_local_date(r["_id"], offset): r for r in rows}
    series = [{"date": d.isoformat(), "net": round(by_bucket.get(d, {}).get("net", 0) or 0, 2),
               "invoices": by_bucket.get(d, {}).get("invoices", 0)} for d in _buckets(start_local, end_local, unit)]

    # --- Formas de pago (crédito aparte)
    pay_rows = await db.invoices.aggregate([
        {"$match": query},
        {"$group": {"_id": {"$cond": [{"$eq": ["$payment_status", "por_cobrar"]}, CREDIT_LABEL,
                                      {"$ifNull": ["$payment_method", "Sin forma de pago"]}]},
                    "net": {"$sum": "$total"}, "invoices": {"$sum": 1}}},
    ]).to_list(None)
    pay_total = sum(r["net"] or 0 for r in pay_rows)
    payments = sorted(({"method": r["_id"], "net": round(r["net"] or 0, 2), "invoices": r["invoices"],
                        "share": round((r["net"] or 0) / pay_total * 100, 1) if pay_total else 0}
                       for r in pay_rows if (r["net"] or 0) > 0), key=lambda x: -x["net"])

    # --- Top productos (netos de devoluciones)
    sold = await db.invoices.aggregate([
        {"$match": query}, {"$unwind": "$items"},
        {"$group": {"_id": "$items.barcode", "name": {"$last": "$items.product_name"},
                    "units": {"$sum": "$items.quantity"}, "net": {"$sum": "$items.total"}}},
    ]).to_list(None)
    ret = await db.invoices.aggregate([
        {"$match": query},
        {"$lookup": {"from": "returns", "localField": "invoice_number", "foreignField": "invoice_number", "as": "r"}},
        {"$unwind": "$r"}, {"$unwind": "$r.items"},
        {"$group": {"_id": "$r.items.barcode", "units": {"$sum": "$r.items.quantity"}, "net": {"$sum": "$r.items.total"}}},
    ]).to_list(None)
    ret_by = {r["_id"]: r for r in ret}
    products = []
    for p in sold:
        r = ret_by.get(p["_id"], {})
        units, net = p["units"] - (r.get("units") or 0), round((p["net"] or 0) - (r.get("net") or 0), 2)
        if units > 0 or net > 0:
            products.append({"barcode": p["_id"], "name": p["name"], "units": units, "net": net})
    top_by_net = sorted(products, key=lambda x: (-x["net"], x["name"]))[:10]
    top_by_units = sorted(products, key=lambda x: (-x["units"], x["name"]))[:10]

    # --- Ventas por hora del día (hora local)
    hour_rows = await db.invoices.aggregate([
        {"$match": query},
        {"$group": {"_id": {"$hour": {"date": "$created_at", "timezone": tz}}, "net": {"$sum": "$total"}, "invoices": {"$sum": 1}}},
    ]).to_list(None)
    by_hour = {r["_id"]: r for r in hour_rows}
    hours = [{"hour": h, "net": round(by_hour.get(h, {}).get("net", 0) or 0, 2), "invoices": by_hour.get(h, {}).get("invoices", 0)}
             for h in range(24)]

    # --- Cartera pendiente (no depende del periodo)
    credit = await db.invoices.aggregate([
        {"$match": {"payment_status": "por_cobrar", "balance": {"$gt": 0}, **seller_filter}},
        {"$group": {"_id": {"d": "$client_document", "t": "$client_document_type"}, "balance": {"$sum": "$balance"}}},
        {"$group": {"_id": None, "balance": {"$sum": "$balance"}, "clients": {"$sum": 1}}},
    ]).to_list(1)

    from core.credit import aging_summary
    aging = await aging_summary(seller)

    from services.inventory import inventory_summary  # import diferido: evita ciclos
    stock = await inventory_summary()

    return {
        "range": {"start_date": start_date, "end_date": end_date, "bucket": unit,
                  "previous": {"start": prev_start.isoformat(), "end": prev_end.isoformat()}},
        "kpis": current,
        "previous": previous,
        "comparison": comparison,
        "series": series,
        "payments": payments,
        "top_products": {"by_net": top_by_net, "by_units": top_by_units},
        "hours": hours,
        "credit": {"balance": round(credit[0]["balance"], 2) if credit else 0, "clients": credit[0]["clients"] if credit else 0,
                   # P2.30: cartera vencida y por vencer (misma visibilidad: el vendedor ve la de sus ventas)
                   "overdue_balance": aging["overdue_balance"], "overdue_invoices": aging["overdue_invoices"],
                   "overdue_clients": aging["overdue_clients"], "due_soon_balance": aging["due_soon_balance"],
                   "due_soon_invoices": aging["due_soon_invoices"], "due_soon_days": aging["due_soon_days"],
                   "buckets": aging["buckets"]},
        "stock": {"low_stock_count": stock["low_stock_count"], "out_of_stock_count": stock["out_of_stock_count"],
                  "threshold": stock["low_stock_threshold"]},
    }
