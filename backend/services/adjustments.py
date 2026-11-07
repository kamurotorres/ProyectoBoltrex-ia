"""Ajustes de inventario: validar y crear un ajuste, filtros y totales (P2.32; fase 3)."""
from datetime import timedelta


from core.errors import BusinessError, ConflictError
from core import audit
from core.adjustments import ADJUSTMENT_COUNTER, KINDS
from core.counters import ensure_counter, next_number
from core.database import db
from repositories import products as products_repo
from core.dates import now_utc
from core.pagination import combine, search_filter
from core.transactions import run_in_transaction
from models.auth import User

from models.adjustments import AdjustmentIn

from datetime import datetime, timezone


from core.adjustments import MAX_ITEMS
from core.sales import created_at_range
from core.money import money



money_text = money   # formato único del sistema (core/money.py)


async def validate_adjustment(body: AdjustmentIn) -> dict:
    if body.kind not in KINDS:
        raise BusinessError("Tipo de ajuste inválido: usa entrada, salida o conteo.")
    reason = await db.adjustment_reasons.find_one({"name": body.reason}, {"_id": 0})
    if not reason:
        raise BusinessError(f"El motivo '{body.reason}' no existe. Elige uno de la lista.")
    if not reason.get("is_active", True):
        raise BusinessError(f"El motivo '{body.reason}' está desactivado. Elige otro o actívalo en Motivos de ajuste.")
    if body.kind not in reason.get("applies_to", []):
        raise BusinessError(f"El motivo '{body.reason}' no aplica a «{KINDS[body.kind]}». "
                                                    f"Elige otro o cámbialo en Motivos de ajuste.")
    if reason.get("requires_note") and not (body.notes or "").strip():
        raise BusinessError(f"El motivo '{body.reason}' exige una observación: explica qué pasó.")
    if not body.items:
        raise BusinessError("Agrega al menos un producto al ajuste.")
    if len(body.items) > MAX_ITEMS:
        raise BusinessError(f"Un ajuste admite máximo {MAX_ITEMS} productos: divídelo en varios.")
    seen = set()
    for it in body.items:
        if it.barcode in seen:
            raise BusinessError(f"El producto {it.barcode} está repetido en el ajuste: déjalo una sola vez.")
        seen.add(it.barcode)
        if body.kind == "conteo":
            if it.counted is None or it.counted < 0:
                raise BusinessError(f"Cantidad contada inválida para {it.barcode}: debe ser 0 o más.")
            if it.expected_stock is None:
                raise BusinessError(f"Falta el stock que tenía el sistema al contar {it.barcode}. Recarga e intenta de nuevo.")
        elif it.quantity is None or it.quantity <= 0:
            raise BusinessError(f"Cantidad inválida para {it.barcode}: debe ser mayor a 0.")
    return reason


def adjustments_query(kind, reason, start_date, end_date, tz_offset_minutes, search) -> dict:
    if kind and kind not in KINDS:
        raise BusinessError("Tipo de ajuste inválido: usa entrada, salida o conteo.")
    rng = created_at_range(start_date, end_date, tz_offset_minutes)
    return combine({"kind": kind} if kind else None, {"reason": reason} if reason else None,
                   {"created_at": rng} if rng else None,
                   search_filter(search, ["adjustment_number", "notes", "created_by", "items.product_name", "items.barcode"]))


async def adjustments_totals(query: dict) -> dict:
    rows = await db.inventory_adjustments.aggregate([
        {"$match": query},
        {"$group": {"_id": None, "loss": {"$sum": "$loss_value"}, "gain": {"$sum": "$gain_value"}, "n": {"$sum": 1},
                    "out": {"$sum": "$units_out"}, "in": {"$sum": "$units_in"}}},
    ]).to_list(1)
    r = rows[0] if rows else {}
    return {"adjustments": r.get("n", 0), "loss_value": round(r.get("loss", 0) or 0, 2), "gain_value": round(r.get("gain", 0) or 0, 2),
            "net_value": round((r.get("gain", 0) or 0) - (r.get("loss", 0) or 0), 2),
            "units_out": r.get("out", 0) or 0, "units_in": r.get("in", 0) or 0}


async def month_adjustments_summary(tz_offset_minutes: int = 0) -> dict:
    """Pérdidas y sobrantes por ajustes del mes local en curso (tarjeta de Inventario)."""
    offset = timedelta(minutes=tz_offset_minutes or 0)
    local = now_utc() - offset
    start = datetime(local.year, local.month, 1, tzinfo=timezone.utc) + offset
    return {**await adjustments_totals({"created_at": {"$gte": start}}), "month": local.strftime("%Y-%m")}


async def create_adjustment(body: AdjustmentIn, current_user: User):
    await validate_adjustment(body)
    await ensure_counter(ADJUSTMENT_COUNTER)
    notes = (body.notes or "").strip() or None

    async def _work(session):
        now = now_utc()
        number = await next_number(ADJUSTMENT_COUNTER, session=session)
        items = []
        for it in body.items:
            product = await products_repo.get(it.barcode, session=session,
                                              projection={"_id": 0, "barcode": 1, "name": 1, "stock": 1, "purchase_price": 1})
            if not product:
                raise BusinessError(f"Producto con código {it.barcode} no encontrado.")
            stock = int(product.get("stock") or 0)
            name = product["name"]
            if body.kind == "entrada":
                delta = it.quantity
                await products_repo.add_stock(it.barcode, delta, session=session)
            elif body.kind == "salida":
                delta = -it.quantity
                if not await products_repo.take_stock(it.barcode, it.quantity, session=session):
                    raise BusinessError(f"Stock insuficiente de {name}: hay {stock} y quieres sacar {it.quantity}.")
            else:
                if stock != it.expected_stock:
                    raise ConflictError(f"El stock de {name} cambió mientras contabas (era {it.expected_stock}, "
                                                                f"ahora es {stock}, quizás por una venta): vuelve a contarlo.")
                delta = it.counted - stock
                if delta:
                    if not await products_repo.set_stock_if(it.barcode, stock, it.counted, session=session):
                        raise ConflictError(f"El stock de {name} cambió mientras contabas: vuelve a contarlo.")
            unit_cost = float(product.get("purchase_price") or 0)
            item = {"barcode": it.barcode, "product_name": name, "stock_before": stock, "quantity": delta,
                    "stock_after": stock + delta, "unit_cost": unit_cost, "value": round(delta * unit_cost, 2)}
            if body.kind == "conteo":
                item["counted"] = it.counted
            items.append(item)
            if delta:
                await products_repo.record_movement(barcode=it.barcode, product_name=name, movement_type="adjustment",
                                                    quantity=delta, reference=number, reason=body.reason,
                                                    adjustment_kind=body.kind, created_by=current_user.email,
                                                    created_at=now, session=session)
        doc = {
            "adjustment_number": number, "kind": body.kind, "kind_label": KINDS[body.kind], "reason": body.reason, "notes": notes,
            "items": items, "products_count": len(items),
            "units_in": sum(i["quantity"] for i in items if i["quantity"] > 0),
            "units_out": -sum(i["quantity"] for i in items if i["quantity"] < 0),
            "gain_value": round(sum(i["value"] for i in items if i["value"] > 0), 2),
            "loss_value": round(-sum(i["value"] for i in items if i["value"] < 0), 2),
            "total_value": round(sum(i["value"] for i in items), 2),
            "created_by": current_user.email, "created_by_name": (current_user.full_name or "").strip() or current_user.email,
            "created_at": now,
        }
        await db.inventory_adjustments.insert_one(dict(doc), session=session)
        detail = ", ".join(f"{i['product_name']} {i['quantity']:+d}" for i in items[:5]) + ("…" if len(items) > 5 else "")
        await audit.record("inventory", "create", entity_id=number, entity_name=f"{KINDS[body.kind]} · {body.reason}",
                           summary=f"Ajuste {number} ({KINDS[body.kind]}, {body.reason}): {detail or 'sin diferencias'} · "
                                   f"valor {money_text(doc['total_value'])}", after=doc, session=session)
        return doc

    return await run_in_transaction(_work)
