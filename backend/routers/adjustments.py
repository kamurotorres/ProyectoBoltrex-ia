"""Ajustes de inventario (backlog P2.32) y su catálogo «Motivos de ajuste». Reglas en core/adjustments.py.

Permisos: catálogo → módulo `adjustment-reasons`; ajustes → módulo `inventory` (ver = leer, hacer un
ajuste = crear; por defecto solo el Administrador lo tiene). Un ajuste no se edita ni se borra.
"""
import csv
import io
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core import audit
from core.adjustments import ADJUSTMENT_COUNTER, KINDS, MAX_ITEMS
from core.counters import ensure_counter, next_number
from core.database import db
from core.dates import as_datetime, now_utc
from core.pagination import combine, page_params, paginate, search_filter
from core.permissions import require_any_permission, require_permission
from core.sales import created_at_range
from core.transactions import run_in_transaction
from models.auth import User

router = APIRouter(tags=["Ajustes de inventario"])


# ==================================================================== MOTIVOS (catálogo)

class ReasonIn(BaseModel):
    name: str
    description: Optional[str] = None
    applies_to: List[str] = Field(default_factory=lambda: ["entrada", "salida", "conteo"])
    requires_note: bool = False
    is_active: bool = True


def _clean_reason(body: ReasonIn) -> dict:
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="El nombre del motivo no puede estar vacío.")
    applies = [k for k in KINDS if k in set(body.applies_to or [])]
    unknown = sorted(set(body.applies_to or []) - set(KINDS))
    if unknown:
        raise HTTPException(status_code=400, detail=f"Tipo de ajuste inválido: {', '.join(unknown)}. Usa entrada, salida o conteo.")
    if not applies:
        raise HTTPException(status_code=400, detail="Marca al menos un tipo de ajuste (entrada, salida o conteo) para el motivo.")
    return {"name": name, "description": (body.description or "").strip() or None, "applies_to": applies,
            "requires_note": bool(body.requires_note), "is_active": bool(body.is_active)}


@router.post("/adjustment-reasons")
async def create_reason(body: ReasonIn, current_user: User = Depends(require_permission("adjustment-reasons", "create"))):
    doc = _clean_reason(body)
    if await db.adjustment_reasons.find_one({"name": doc["name"]}, {"_id": 1}):
        raise HTTPException(status_code=400, detail=f"Ya existe un motivo de ajuste llamado '{doc['name']}'.")
    doc["created_at"] = now_utc()
    await db.adjustment_reasons.insert_one(dict(doc))
    await audit.record("adjustment-reasons", "create", entity_id=doc["name"], entity_name=doc["name"],
                       summary=f"Creó el motivo de ajuste '{doc['name']}'", after=doc)
    return doc


@router.get("/adjustment-reasons")
async def list_reasons(paginated: bool = False, search: Optional[str] = None, kind: Optional[str] = None,
                       active_only: bool = False, pg: dict = Depends(page_params),
                       current_user: User = Depends(require_any_permission(("adjustment-reasons", "read"), ("inventory", "read")))):
    query = combine(search_filter(search, ["name", "description"]),
                    {"applies_to": kind} if kind else None,
                    {"is_active": True} if active_only else None)
    if paginated:
        return await paginate(db.adjustment_reasons, query, [("name", 1)], **pg)
    return await db.adjustment_reasons.find(query, {"_id": 0}).sort([("name", 1), ("_id", 1)]).to_list(None)


@router.put("/adjustment-reasons/{name}")
async def update_reason(name: str, body: ReasonIn, current_user: User = Depends(require_permission("adjustment-reasons", "update"))):
    before = await db.adjustment_reasons.find_one({"name": name}, {"_id": 0})
    if not before:
        raise HTTPException(status_code=404, detail=f"No existe el motivo de ajuste '{name}'.")
    doc = _clean_reason(body)
    if doc["name"] != name and await db.adjustment_reasons.find_one({"name": doc["name"]}, {"_id": 1}):
        raise HTTPException(status_code=400, detail=f"Ya existe un motivo de ajuste llamado '{doc['name']}'.")
    # Los ajustes ya hechos guardan el nombre que tenía el motivo en ese momento (son un registro histórico).
    await db.adjustment_reasons.update_one({"name": name}, {"$set": doc})
    after = {**before, **doc}
    changes = audit.diff(before, after)
    if changes:
        await audit.record("adjustment-reasons", "update", entity_id=doc["name"], entity_name=doc["name"],
                           summary=f"Modificó el motivo de ajuste '{name}': {audit.describe_changes(changes)}",
                           before=before, after=after)
    return after


@router.delete("/adjustment-reasons/{name}")
async def delete_reason(name: str, current_user: User = Depends(require_permission("adjustment-reasons", "delete"))):
    before = await db.adjustment_reasons.find_one({"name": name}, {"_id": 0})
    if not before:
        raise HTTPException(status_code=404, detail=f"No existe el motivo de ajuste '{name}'.")
    used = await db.inventory_adjustments.count_documents({"reason": name})
    if used:
        raise HTTPException(status_code=400, detail=f"No se puede eliminar el motivo '{name}': se usó en {used} ajuste(s). "
                                                    f"Desactívalo para que no se pueda elegir más.")
    await db.adjustment_reasons.delete_one({"name": name})
    await audit.record("adjustment-reasons", "delete", entity_id=name, entity_name=name,
                       summary=f"Eliminó el motivo de ajuste '{name}'", before=before)
    return {"message": f"Motivo '{name}' eliminado"}


# ==================================================================== AJUSTES

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


def _money(v: float) -> str:
    return ("−" if v < 0 else "") + "$" + f"{abs(v):,.0f}".replace(",", ".")


async def _validate(body: AdjustmentIn) -> dict:
    if body.kind not in KINDS:
        raise HTTPException(status_code=400, detail="Tipo de ajuste inválido: usa entrada, salida o conteo.")
    reason = await db.adjustment_reasons.find_one({"name": body.reason}, {"_id": 0})
    if not reason:
        raise HTTPException(status_code=400, detail=f"El motivo '{body.reason}' no existe. Elige uno de la lista.")
    if not reason.get("is_active", True):
        raise HTTPException(status_code=400, detail=f"El motivo '{body.reason}' está desactivado. Elige otro o actívalo en Motivos de ajuste.")
    if body.kind not in reason.get("applies_to", []):
        raise HTTPException(status_code=400, detail=f"El motivo '{body.reason}' no aplica a «{KINDS[body.kind]}». "
                                                    f"Elige otro o cámbialo en Motivos de ajuste.")
    if reason.get("requires_note") and not (body.notes or "").strip():
        raise HTTPException(status_code=400, detail=f"El motivo '{body.reason}' exige una observación: explica qué pasó.")
    if not body.items:
        raise HTTPException(status_code=400, detail="Agrega al menos un producto al ajuste.")
    if len(body.items) > MAX_ITEMS:
        raise HTTPException(status_code=400, detail=f"Un ajuste admite máximo {MAX_ITEMS} productos: divídelo en varios.")
    seen = set()
    for it in body.items:
        if it.barcode in seen:
            raise HTTPException(status_code=400, detail=f"El producto {it.barcode} está repetido en el ajuste: déjalo una sola vez.")
        seen.add(it.barcode)
        if body.kind == "conteo":
            if it.counted is None or it.counted < 0:
                raise HTTPException(status_code=400, detail=f"Cantidad contada inválida para {it.barcode}: debe ser 0 o más.")
            if it.expected_stock is None:
                raise HTTPException(status_code=400, detail=f"Falta el stock que tenía el sistema al contar {it.barcode}. Recarga e intenta de nuevo.")
        elif it.quantity is None or it.quantity <= 0:
            raise HTTPException(status_code=400, detail=f"Cantidad inválida para {it.barcode}: debe ser mayor a 0.")
    return reason


@router.post("/inventory/adjustments")
async def create_adjustment(body: AdjustmentIn, current_user: User = Depends(require_permission("inventory", "create"))):
    await _validate(body)
    await ensure_counter(ADJUSTMENT_COUNTER)
    notes = (body.notes or "").strip() or None

    async def _work(session):
        now = now_utc()
        number = await next_number(ADJUSTMENT_COUNTER, session=session)
        items = []
        for it in body.items:
            product = await db.products.find_one({"barcode": it.barcode}, {"_id": 0, "barcode": 1, "name": 1, "stock": 1, "purchase_price": 1},
                                                 session=session)
            if not product:
                raise HTTPException(status_code=400, detail=f"Producto con código {it.barcode} no encontrado.")
            stock = int(product.get("stock") or 0)
            name = product["name"]
            if body.kind == "entrada":
                delta = it.quantity
                await db.products.update_one({"barcode": it.barcode}, {"$inc": {"stock": delta}}, session=session)
            elif body.kind == "salida":
                delta = -it.quantity
                res = await db.products.update_one({"barcode": it.barcode, "stock": {"$gte": it.quantity}},
                                                   {"$inc": {"stock": delta}}, session=session)
                if res.modified_count == 0:
                    raise HTTPException(status_code=400, detail=f"Stock insuficiente de {name}: hay {stock} y quieres sacar {it.quantity}.")
            else:
                if stock != it.expected_stock:
                    raise HTTPException(status_code=409, detail=f"El stock de {name} cambió mientras contabas (era {it.expected_stock}, "
                                                                f"ahora es {stock}, quizás por una venta): vuelve a contarlo.")
                delta = it.counted - stock
                if delta:
                    res = await db.products.update_one({"barcode": it.barcode, "stock": stock}, {"$set": {"stock": it.counted}}, session=session)
                    if res.modified_count == 0:
                        raise HTTPException(status_code=409, detail=f"El stock de {name} cambió mientras contabas: vuelve a contarlo.")
            unit_cost = float(product.get("purchase_price") or 0)
            item = {"barcode": it.barcode, "product_name": name, "stock_before": stock, "quantity": delta,
                    "stock_after": stock + delta, "unit_cost": unit_cost, "value": round(delta * unit_cost, 2)}
            if body.kind == "conteo":
                item["counted"] = it.counted
            items.append(item)
            if delta:
                await db.inventory_movements.insert_one({
                    "barcode": it.barcode, "product_name": name, "movement_type": "adjustment", "quantity": delta,
                    "reference": number, "reason": body.reason, "adjustment_kind": body.kind,
                    "created_by": current_user.email, "created_at": now,
                }, session=session)
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
                                   f"valor {_money(doc['total_value'])}", after=doc, session=session)
        return doc

    return await run_in_transaction(_work)


def _adjustments_query(kind, reason, start_date, end_date, tz_offset_minutes, search) -> dict:
    if kind and kind not in KINDS:
        raise HTTPException(status_code=400, detail="Tipo de ajuste inválido: usa entrada, salida o conteo.")
    rng = created_at_range(start_date, end_date, tz_offset_minutes)
    return combine({"kind": kind} if kind else None, {"reason": reason} if reason else None,
                   {"created_at": rng} if rng else None,
                   search_filter(search, ["adjustment_number", "notes", "created_by", "items.product_name", "items.barcode"]))


async def _totals(query: dict) -> dict:
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
    return {**await _totals({"created_at": {"$gte": start}}), "month": local.strftime("%Y-%m")}


@router.get("/inventory/adjustments")
async def list_adjustments(kind: Optional[str] = None, reason: Optional[str] = None, start_date: Optional[str] = None,
                           end_date: Optional[str] = None, tz_offset_minutes: int = 0, search: Optional[str] = None,
                           pg: dict = Depends(page_params), current_user: User = Depends(require_permission("inventory", "read"))):
    """Ajustes paginados, más recientes primero, con totales del filtro (pérdidas / sobrantes al costo)."""
    query = _adjustments_query(kind, reason, start_date, end_date, tz_offset_minutes, search)
    # El listado no trae los productos (pueden ser cientos en un conteo); el detalle sí.
    page = await paginate(db.inventory_adjustments, query, [("created_at", -1)], projection={"_id": 0, "items": 0}, **pg)
    page["summary"] = await _totals(query)
    return page


@router.get("/inventory/adjustments/export")
async def export_adjustments(kind: Optional[str] = None, reason: Optional[str] = None, start_date: Optional[str] = None,
                             end_date: Optional[str] = None, tz_offset_minutes: int = 0, search: Optional[str] = None,
                             format: str = "csv", current_user: User = Depends(require_permission("inventory", "read"))):
    """Export completo del filtro (CSV: una fila por producto ajustado). P2.33: csv · xlsx · pdf."""
    from core.exporting import check_format, period_label
    query = _adjustments_query(kind, reason, start_date, end_date, tz_offset_minutes, search)
    if check_format(format) != "csv":
        from routers.exports import adjustments_report
        filters = [period_label(start_date, end_date)] + ([f"Tipo: {KINDS[kind]}"] if kind else []) \
            + ([f"Motivo: {reason}"] if reason else []) + ([f"Búsqueda: {search}"] if search else [])
        return await adjustments_report(query, filters, current_user, format, tz_offset_minutes)
    out = io.StringIO()
    w = csv.writer(out, delimiter=";")
    w.writerow(["Ajuste", "Fecha", "Tipo", "Motivo", "Observación", "Usuario", "Código", "Producto", "Stock antes",
                "Contado", "Diferencia", "Stock después", "Costo unitario", "Valor"])
    offset = timedelta(minutes=tz_offset_minutes or 0)
    async for a in db.inventory_adjustments.find(query, {"_id": 0}).sort([("created_at", -1), ("_id", -1)]):
        when = (as_datetime(a["created_at"]) - offset).strftime("%Y-%m-%d %H:%M")
        for i in a.get("items", []):
            w.writerow([a["adjustment_number"], when, a.get("kind_label", a["kind"]), a["reason"], a.get("notes") or "", a["created_by"],
                        i["barcode"], i["product_name"], i["stock_before"], i.get("counted", ""), i["quantity"], i["stock_after"],
                        i["unit_cost"], i["value"]])
    data = "﻿" + out.getvalue()
    return StreamingResponse(iter([data]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f"attachment; filename=ajustes_{now_utc().strftime('%Y%m%d')}.csv"})


@router.get("/inventory/adjustments/{number}")
async def get_adjustment(number: str, current_user: User = Depends(require_permission("inventory", "read"))):
    doc = await db.inventory_adjustments.find_one({"adjustment_number": number}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail=f"No existe el ajuste {number}.")
    return doc
