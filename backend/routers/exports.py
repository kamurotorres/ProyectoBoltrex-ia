"""Reportes exportables a Excel / PDF / CSV (backlog P2.33). Motor en core/exporting.py.

Los endpoints de exportación que ya existían (`/reports/sales/export`, `/reports/inventory/export`,
`/fios/export`, `/inventory/adjustments/export`) aceptan `format=xlsx|pdf` y llaman a estos
constructores; con `format=csv` (o sin formato) siguen respondiendo el CSV de siempre.
Endpoints nuevos aquí: compras, estado de cuenta del cliente y cierre de caja.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from core.database import db
from core.dates import now_utc
from core.exporting import Col, Report, Sheet, export_response, local, money, period_label
from core.pagination import combine, search_filter
from core.permissions import require_permission
from core.sales import created_at_range, invoices_query, sales_summary
from models.auth import User

router = APIRouter(tags=["Exportaciones"])

STATUS_LABELS = {"completed": "Completada", "partial_return": "Devolución parcial", "returned": "Devuelta"}
PAY_LABELS = {"pagado": "Pagado", "por_cobrar": "Crédito"}
PURCHASE_LABELS = {"borrador": "Borrador", "confirmado": "Confirmada"}


# ==================================================================== VENTAS

async def sales_report(start_date, end_date, tz, user, fmt):
    query = invoices_query(start_date, end_date, tz)
    invoices = await db.invoices.find(query, {"_id": 0}).sort([("created_at", -1), ("_id", -1)]).to_list(None)
    s = await sales_summary(query)
    by_method = await db.invoices.aggregate([
        {"$match": query},
        {"$group": {"_id": {"$cond": [{"$eq": ["$payment_status", "por_cobrar"]}, "Crédito (Fios)", {"$ifNull": ["$payment_method", "—"]}]},
                    "total": {"$sum": "$total"}, "n": {"$sum": 1}}},
        {"$sort": {"total": -1}},
    ]).to_list(None)
    rows, detail = [], []
    for inv in invoices:
        when = local(inv.get("created_at"), tz)
        rows.append({"n": inv.get("invoice_number"), "date": when, "dt": inv.get("client_document_type") or "",
                     "doc": inv.get("client_document"), "client": inv.get("client_name"),
                     "status": STATUS_LABELS.get(inv.get("status"), inv.get("status")),
                     "pay": PAY_LABELS.get(inv.get("payment_status"), inv.get("payment_status")),
                     "method": inv.get("payment_method") or ("Crédito" if inv.get("payment_status") == "por_cobrar" else ""),
                     "subtotal": round(inv.get("subtotal") or 0, 2), "tax": round(inv.get("total_tax") or 0, 2),
                     "total": round(inv.get("total") or 0, 2), "seller": inv.get("created_by")})
        for it in inv.get("items", []):
            detail.append({"n": inv.get("invoice_number"), "date": when, "barcode": it.get("barcode"), "product": it.get("product_name"),
                           "qty": it.get("quantity"), "price": it.get("unit_price"), "rate": it.get("tax_rate"),
                           "subtotal": round(it.get("subtotal") or 0, 2), "tax": round(it.get("tax_amount") or 0, 2),
                           "total": round(it.get("total") or 0, 2)})
    sheets = [
        Sheet("Facturas", [Col("n", "Factura", width=11), Col("date", "Fecha", "datetime"), Col("dt", "Tipo doc.", width=7),
                           Col("doc", "Documento", width=12), Col("client", "Cliente", width=22), Col("status", "Estado", width=13),
                           Col("pay", "Pago", width=8), Col("method", "Forma de pago", width=13), Col("subtotal", "Subtotal", "money"),
                           Col("tax", "IVA", "money"), Col("total", "Total", "money"), Col("seller", "Vendedor", width=20)],
              rows, totals={"subtotal": s["net_subtotal"], "tax": s["total_tax"], "total": s["total_sales"]}),
        Sheet("Detalle por producto", [Col("n", "Factura", width=11), Col("date", "Fecha", "datetime"), Col("barcode", "Código", width=12),
                                       Col("product", "Producto", width=24), Col("qty", "Cant.", "int"), Col("price", "Precio unit.", "money"),
                                       Col("rate", "IVA %", "percent"), Col("subtotal", "Subtotal", "money"), Col("tax", "IVA", "money"),
                                       Col("total", "Total", "money")],
              detail, totals={"qty": sum(d["qty"] or 0 for d in detail), "subtotal": round(sum(d["subtotal"] for d in detail), 2),
                              "tax": round(sum(d["tax"] for d in detail), 2), "total": round(sum(d["total"] for d in detail), 2)},
              in_pdf=False),
    ]
    summary = [("Ventas netas", money(s["total_sales"])), ("Facturas (vigentes)", str(s["total_invoices"])),
               ("Ventas brutas", money(s["gross_sales"])), ("Devoluciones", f"{money(s['returns_total'])} ({s['returns_count']})"),
               ("Subtotal neto (sin IVA)", money(s["net_subtotal"])), ("IVA neto", money(s["total_tax"])),
               ("Facturas devueltas por completo", str(s["returned_invoices"]))]
    summary += [(f"Por forma de pago: {m['_id']}", f"{money(m['total'])} ({m['n']})") for m in by_method]
    report = Report(title="Reporte de ventas", filename=f"ventas_{start_date or 'inicio'}_{end_date or 'hoy'}",
                    filters=[period_label(start_date, end_date)], summary=summary, sheets=sheets,
                    notes=["Valores netos: las devoluciones ya están descontadas de cada factura."])
    return await export_response(report, fmt, user, module="reports", tz_offset_minutes=tz)


# ==================================================================== INVENTARIO

async def inventory_report(user, fmt, tz):
    from core.alerts import effective_min, get_inventory_settings, stock_status
    from routers.inventory import inventory_summary
    threshold = (await get_inventory_settings())["low_stock_threshold"]
    labels = {"ok": "Normal", "low": "Bajo", "out": "Agotado"}
    rows = []
    async for p in db.products.find({}, {"_id": 0}).sort([("name", 1), ("_id", 1)]):
        stock = int(p.get("stock") or 0)
        cost = float(p.get("purchase_price") or 0)
        default = next((x.get("price") for x in (p.get("prices") or []) if x.get("price_list_name") == "default"), None)
        rows.append({"barcode": p.get("barcode"), "name": p.get("name"), "category": p.get("category"), "stock": stock,
                     "min": effective_min(p, threshold), "status": labels[stock_status(p, threshold)], "cost": cost,
                     "value": round(cost * stock, 2), "tax": p.get("tax_rate", 0), "price": default})
    s = await inventory_summary()
    sheet = Sheet("Inventario", [Col("barcode", "Código", width=12), Col("name", "Producto", width=26), Col("category", "Categoría", width=13),
                                 Col("stock", "Stock", "int"), Col("min", "Mínimo", "int"), Col("status", "Estado", width=8),
                                 Col("cost", "Costo", "money"), Col("value", "Valor", "money"), Col("tax", "IVA %", "percent"),
                                 Col("price", "Precio default", "money")],
                  rows, totals={"stock": sum(r["stock"] for r in rows), "value": round(sum(r["value"] for r in rows), 2)})
    report = Report(title="Inventario valorizado", filename=f"inventario_{now_utc().strftime('%Y%m%d')}",
                    filters=[f"Todos los productos · stock mínimo general {threshold}"],
                    summary=[("Productos", str(s["total_products"])), ("Unidades", f"{s['total_units']:,}".replace(",", ".")),
                             ("Valor al costo", money(s["total_value"])), ("Bajo stock", str(s["low_stock_count"])),
                             ("Agotados", str(s["out_of_stock_count"]))],
                    sheets=[sheet])
    return await export_response(report, fmt, user, module="reports", tz_offset_minutes=tz)


# ==================================================================== COMPRAS (nuevo)

@router.get("/purchases/export")
async def export_purchases(format: str = "xlsx", search: Optional[str] = None, status: Optional[str] = None,
                           start_date: Optional[str] = None, end_date: Optional[str] = None, tz_offset_minutes: int = 0,
                           current_user: User = Depends(require_permission("purchases", "read"))):
    if status and status not in PURCHASE_LABELS:
        raise HTTPException(status_code=400, detail="Estado inválido: usa borrador o confirmado.")
    rng = created_at_range(start_date, end_date, tz_offset_minutes)
    query = combine(search_filter(search, ["purchase_number", "supplier_name"]), {"status": status} if status else None,
                    {"created_at": rng} if rng else None)
    rows, detail = [], []
    async for p in db.purchases.find(query, {"_id": 0}).sort([("created_at", -1), ("_id", -1)]):
        when = local(p.get("created_at"), tz_offset_minutes)
        items = p.get("items", [])
        rows.append({"n": p["purchase_number"], "date": when, "supplier": p.get("supplier_name"),
                     "status": PURCHASE_LABELS.get(p.get("status"), p.get("status")), "products": len(items),
                     "units": sum(int(i.get("quantity") or 0) for i in items), "total": round(p.get("total") or 0, 2),
                     "user": p.get("created_by")})
        for i in items:
            detail.append({"n": p["purchase_number"], "date": when, "supplier": p.get("supplier_name"), "barcode": i.get("barcode"),
                           "product": i.get("product_name"), "qty": i.get("quantity"), "cost": i.get("unit_cost"),
                           "total": round(i.get("total") or 0, 2)})
    confirmed = [r for r in rows if r["status"] == "Confirmada"]
    filters = [period_label(start_date, end_date)]
    if status:
        filters.append(f"Estado: {PURCHASE_LABELS[status]}")
    if search:
        filters.append(f"Búsqueda: {search}")
    report = Report(
        title="Reporte de compras", filename=f"compras_{start_date or 'inicio'}_{end_date or 'hoy'}", filters=filters,
        summary=[("Compras", str(len(rows))), ("Total", money(sum(r["total"] for r in rows))),
                 ("Confirmadas", f"{len(confirmed)} · {money(sum(r['total'] for r in confirmed))}"),
                 ("Borradores", str(len(rows) - len(confirmed))), ("Unidades", str(sum(r["units"] for r in rows)))],
        sheets=[
            Sheet("Compras", [Col("n", "Compra", width=11), Col("date", "Fecha", "datetime"), Col("supplier", "Proveedor", width=24),
                              Col("status", "Estado", width=10), Col("products", "Productos", "int"), Col("units", "Unidades", "int"),
                              Col("total", "Total", "money"), Col("user", "Usuario", width=22)],
                  rows, totals={"units": sum(r["units"] for r in rows), "total": round(sum(r["total"] for r in rows), 2)}),
            Sheet("Detalle", [Col("n", "Compra", width=11), Col("date", "Fecha", "datetime"), Col("supplier", "Proveedor", width=20),
                              Col("barcode", "Código", width=12), Col("product", "Producto", width=24), Col("qty", "Cant.", "int"),
                              Col("cost", "Costo unit.", "money"), Col("total", "Total", "money")],
                  detail, totals={"qty": sum(int(d["qty"] or 0) for d in detail), "total": round(sum(d["total"] for d in detail), 2)},
                  in_pdf=False),
        ])
    return await export_response(report, format, current_user, module="purchases", tz_offset_minutes=tz_offset_minutes)


# ==================================================================== CARTERA

async def fios_report(search, status, user, fmt, tz):
    from core import credit
    from routers.invoices import FIOS_FILTERS, _account_status_label, _fios_pipeline
    settings = await credit.get_settings()
    accounts = await db.invoices.aggregate(
        _fios_pipeline(search, status, now_utc(), settings) + [{"$sort": {"max_days_overdue": -1, "balance": -1}}]
    ).to_list(None)
    bucket_cols = [(k, label) for k, label, *_ in credit.BUCKETS if k != "current"]
    rows = [{"dt": a.get("client_document_type") or "", "doc": a["client_document"], "client": a.get("client_name"),
             "inv": a["invoices_count"], "credit": round(a["total_credit"], 2), "paid": round(a["total_paid"], 2),
             "balance": round(a["balance"], 2), "overdue": round(a["overdue_balance"], 2), "soon": round(a["due_soon_balance"], 2),
             "days": int(a.get("max_days_overdue") or 0), "next": local(a.get("next_due_date"), tz),
             "status": _account_status_label(a), **{f"b_{k}": round(a["buckets"].get(k, 0), 2) for k, _ in bucket_cols}}
            for a in accounts]
    aging = await credit.aging_summary(settings=settings)
    cols = [Col("dt", "Tipo", width=6), Col("doc", "Documento", width=12), Col("client", "Cliente", width=22), Col("inv", "Fact.", "int"),
            Col("balance", "Saldo", "money"), Col("overdue", "Vencido", "money"), Col("soon", "Por vencer", "money"),
            Col("days", "Días atraso", "int"), Col("next", "Próx. vence", "date"), Col("status", "Estado", width=14)]
    cols += [Col(f"b_{k}", label, "money") for k, label in bucket_cols]
    totals = {k: round(sum(r[k] for r in rows), 2) for k in ("balance", "overdue", "soon")}
    totals.update({f"b_{k}": round(sum(r[f"b_{k}"] for r in rows), 2) for k, _ in bucket_cols})
    labels = {"overdue": "Vencidas", "due_soon": "Por vencer", "current": "Sin vencidas",
              **{k: f"Vencido {label}" for k, label in bucket_cols}}
    filters = [f"Filtro: {labels.get(status, 'Todas las cuentas')}"] + ([f"Búsqueda: {search}"] if search else [])
    summary = [("Saldo total de la cartera", money(aging["total_balance"])), ("Vencido", money(aging["overdue_balance"])),
               ("Clientes con vencidas", str(aging["overdue_clients"])),
               (f"Por vencer ({aging['due_soon_days']} días)", money(aging["due_soon_balance"]))]
    summary += [(f"Tramo {b['label']}", f"{money(b['balance'])} ({b['invoices']})") for b in aging["buckets"]]
    assert FIOS_FILTERS  # el filtro ya se validó en _fios_pipeline
    report = Report(title="Cartera (cuentas por cobrar)", filename=f"cartera_{now_utc().strftime('%Y%m%d')}", filters=filters,
                    summary=summary, sheets=[Sheet("Cartera", cols, rows, totals=totals)])
    return await export_response(report, fmt, user, module="fios", tz_offset_minutes=tz)


@router.get("/fios/statement/{client_document}")
async def client_statement(client_document: str, document_type: Optional[str] = None, format: str = "pdf",
                           tz_offset_minutes: int = 0, current_user: User = Depends(require_permission("fios", "read"))):
    """Estado de cuenta del cliente: facturas pendientes (vencimiento y estado) y sus abonos."""
    from core import credit
    from core.clients import invoices_of_client_query, resolve_client
    client = await resolve_client(client_document, document_type)
    settings = await credit.get_settings()
    now = now_utc()
    invoices = await db.invoices.find({**invoices_of_client_query(client), "payment_status": "por_cobrar", "balance": {"$gt": 0}},
                                      {"_id": 0}).to_list(None)
    for inv in invoices:
        inv.update(credit.invoice_status(inv.get("due_date"), settings["due_soon_days"], now))
    invoices.sort(key=lambda i: (i.get("due_date") or now, i["invoice_number"]))
    payments = await db.fio_payments.find({"invoice_number": {"$in": [i["invoice_number"] for i in invoices]}}, {"_id": 0}) \
        .sort("created_at", 1).to_list(None)
    name = f"{client.get('first_name', '')} {client.get('last_name', '')}".strip()
    balance = round(sum(i["balance"] for i in invoices), 2)
    overdue = round(sum(i["balance"] for i in invoices if i["credit_status"] == "overdue"), 2)
    inv_rows = [{"n": i["invoice_number"], "date": local(i.get("created_at"), tz_offset_minutes), "due": local(i.get("due_date"), tz_offset_minutes),
                 "status": i["credit_status_label"], "total": round(i["total"], 2), "paid": round(i["amount_paid"], 2),
                 "balance": round(i["balance"], 2)} for i in invoices]
    pay_rows = [{"date": local(p.get("created_at"), tz_offset_minutes), "n": p["invoice_number"], "method": p.get("payment_method"),
                 "amount": round(p["amount"], 2), "notes": p.get("notes") or ""} for p in payments]
    summary = [("Cliente", name), ("Documento", f"{client.get('document_type', '')} {client['document_number']}".strip()),
               ("Saldo pendiente", money(balance)), ("Vencido", money(overdue)), ("Facturas pendientes", str(len(invoices)))]
    if client.get("phone"):
        summary.append(("Teléfono", client["phone"]))
    if client.get("credit_limit"):
        summary.append(("Cupo / disponible", f"{money(client['credit_limit'])} / {money(max(0.0, client['credit_limit'] - balance))}"))
    report = Report(
        title=f"Estado de cuenta — {name}", filename=f"estado_cuenta_{client['document_number']}_{now.strftime('%Y%m%d')}",
        filters=[f"Corte al {local(now, tz_offset_minutes).strftime('%d/%m/%Y')}"], summary=summary, landscape=False,
        sheets=[
            Sheet("Facturas pendientes", [Col("n", "Factura", width=11), Col("date", "Fecha", "date"), Col("due", "Vence", "date"),
                                          Col("status", "Estado", width=17), Col("total", "Total", "money"), Col("paid", "Abonado", "money"),
                                          Col("balance", "Saldo", "money")],
                  inv_rows, totals={"total": round(sum(r["total"] for r in inv_rows), 2), "paid": round(sum(r["paid"] for r in inv_rows), 2),
                                    "balance": balance}),
            Sheet("Abonos", [Col("date", "Fecha", "datetime"), Col("n", "Factura", width=11), Col("method", "Forma de pago", width=14),
                             Col("amount", "Monto", "money"), Col("notes", "Notas", width=24)],
                  pay_rows, totals={"amount": round(sum(r["amount"] for r in pay_rows), 2)}),
        ])
    return await export_response(report, format, current_user, module="fios", tz_offset_minutes=tz_offset_minutes)


# ==================================================================== AJUSTES

async def adjustments_report(query, filters, user, fmt, tz):
    from core.adjustments import KINDS
    rows, detail = [], []
    async for a in db.inventory_adjustments.find(query, {"_id": 0}).sort([("created_at", -1), ("_id", -1)]):
        when = local(a.get("created_at"), tz)
        rows.append({"n": a["adjustment_number"], "date": when, "kind": KINDS.get(a["kind"], a["kind"]), "reason": a["reason"],
                     "notes": a.get("notes") or "", "products": a.get("products_count", len(a.get("items", []))),
                     "loss": a.get("loss_value", 0), "gain": a.get("gain_value", 0), "net": a.get("total_value", 0),
                     "user": a.get("created_by_name") or a.get("created_by")})
        for i in a.get("items", []):
            detail.append({"n": a["adjustment_number"], "date": when, "kind": KINDS.get(a["kind"], a["kind"]), "reason": a["reason"],
                           "barcode": i["barcode"], "product": i["product_name"], "before": i["stock_before"], "counted": i.get("counted"),
                           "qty": i["quantity"], "after": i["stock_after"], "cost": i["unit_cost"], "value": i["value"]})
    loss, gain = round(sum(r["loss"] for r in rows), 2), round(sum(r["gain"] for r in rows), 2)
    report = Report(
        title="Ajustes de inventario", filename=f"ajustes_{now_utc().strftime('%Y%m%d')}", filters=filters,
        summary=[("Ajustes", str(len(rows))), ("Pérdidas (al costo)", money(loss)), ("Sobrantes (al costo)", money(gain)),
                 ("Neto", money(gain - loss))],
        sheets=[
            Sheet("Ajustes", [Col("n", "Ajuste", width=11), Col("date", "Fecha", "datetime"), Col("kind", "Tipo", width=11),
                              Col("reason", "Motivo", width=16), Col("notes", "Observación", width=24), Col("products", "Prod.", "int"),
                              Col("loss", "Pérdida", "money"), Col("gain", "Sobrante", "money"), Col("net", "Neto", "money"),
                              Col("user", "Usuario", width=18)],
                  rows, totals={"loss": loss, "gain": gain, "net": round(gain - loss, 2)}),
            Sheet("Detalle", [Col("n", "Ajuste", width=11), Col("date", "Fecha", "datetime"), Col("kind", "Tipo", width=10),
                              Col("reason", "Motivo", width=14), Col("barcode", "Código", width=12), Col("product", "Producto", width=22),
                              Col("before", "Antes", "int"), Col("counted", "Contado", "int"), Col("qty", "Diferencia", "int"),
                              Col("after", "Después", "int"), Col("cost", "Costo", "money"), Col("value", "Valor", "money")],
                  detail, totals={"value": round(sum(d["value"] for d in detail), 2)}),
        ])
    return await export_response(report, fmt, user, module="inventory", tz_offset_minutes=tz)


# ==================================================================== CIERRE DE CAJA (A4)

KIND_LABELS = {"sale": "Venta", "fio_payment": "Abono", "refund": "Reembolso", "income": "Ingreso", "expense": "Egreso"}


@router.get("/cash/sessions/{session_id}/export")
async def export_cash_session(session_id: str, format: str = "pdf", tz_offset_minutes: int = 0,
                              current_user: User = Depends(require_permission("cash", "read"))):
    from routers.cash import _detail, _load
    doc = await _detail(await _load(session_id, current_user))
    tz = tz_offset_minutes
    s = doc.get("summary") or {}
    closed = doc["status"] == "closed"
    fmt_dt = lambda v: local(v, tz).strftime("%d/%m/%Y %H:%M") if local(v, tz) else "—"
    summary = [("Caja", doc["session_id"]), ("Cajero", doc.get("cashier_name") or doc["cashier_email"]),
               ("Apertura", fmt_dt(doc.get("opened_at"))), ("Cierre", fmt_dt(doc.get("closed_at")) if closed else "Abierta"),
               ("Base inicial", money(doc.get("opening_amount"))), ("Efectivo esperado", money(s.get("expected_cash")))]
    if closed:
        diff = float(doc.get("difference") or 0)
        summary += [("Efectivo contado", money(doc.get("counted_cash"))),
                    ("Diferencia", "Cuadrada" if abs(diff) < 0.005 else f"{'Sobrante' if diff > 0 else 'Faltante'} {money(abs(diff))}")]
        if doc.get("forced_close"):
            summary.append(("Cierre forzado por", doc.get("closed_by") or ""))
    notes = [f"Observaciones: {doc['closing_notes']}"] if doc.get("closing_notes") else []
    methods = [{"method": m["method"], "opening": m["opening"], "sales": m["sales"], "fio": m["fio_payments"], "income": m["income"],
                "refunds": m["refunds"], "expense": m["expense"], "expected": m["expected"],
                "rec": ("Sí" if (doc.get("reconciled") or {}).get(m["method"]) else ("—" if m["is_cash"] else "No"))}
               for m in s.get("methods", [])]
    moves = [{"date": local(m.get("created_at"), tz), "kind": KIND_LABELS.get(m.get("kind"), m.get("kind")), "method": m.get("method"),
              "amount": round(m["amount"] if m.get("direction") == "in" else -m["amount"], 2),
              "ref": m.get("reference") or m.get("reason") or "", "user": m.get("created_by")} for m in doc.get("movements", [])]
    sheets = [
        Sheet("Por forma de pago", [Col("method", "Forma de pago", width=16), Col("opening", "Base", "money"), Col("sales", "Ventas", "money"),
                                    Col("fio", "Abonos", "money"), Col("income", "Ingresos", "money"), Col("refunds", "Reembolsos", "money"),
                                    Col("expense", "Egresos", "money"), Col("expected", "Esperado", "money"), Col("rec", "Conciliada", width=9)],
              methods, totals={"expected": round(sum(m["expected"] for m in methods), 2)}),
        Sheet("Movimientos", [Col("date", "Fecha", "datetime"), Col("kind", "Tipo", width=10), Col("method", "Forma de pago", width=14),
                              Col("amount", "Monto", "money"), Col("ref", "Referencia / motivo", width=26), Col("user", "Usuario", width=20)],
              moves, totals={"amount": round(sum(m["amount"] for m in moves), 2)}),
    ]
    if doc.get("denominations"):
        den = [{"value": int(k), "qty": int(v), "total": int(k) * int(v)} for k, v in sorted(doc["denominations"].items(), key=lambda x: -int(x[0])) if int(v)]
        sheets.append(Sheet("Arqueo", [Col("value", "Denominación", "money"), Col("qty", "Cantidad", "int"), Col("total", "Total", "money")],
                            den, totals={"qty": sum(d["qty"] for d in den), "total": sum(d["total"] for d in den)}))
    report = Report(title=f"Cierre de caja {doc['session_id']}", filename=f"caja_{doc['session_id']}", summary=summary, notes=notes,
                    sheets=sheets, landscape=False,
                    filters=[f"Cajero: {doc.get('cashier_name') or doc['cashier_email']}"])
    return await export_response(report, format, current_user, module="cash", tz_offset_minutes=tz)
