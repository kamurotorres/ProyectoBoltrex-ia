"""Ajustes de inventario (backlog P2.32) y su catálogo «Motivos de ajuste». Reglas en core/adjustments.py.

Permisos: catálogo → módulo `adjustment-reasons`; ajustes → módulo `inventory` (ver = leer, hacer un
ajuste = crear; por defecto solo el Administrador lo tiene). Un ajuste no se edita ni se borra.
"""
import csv
import io
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from core import audit
from core.adjustments import KINDS
from core.database import db
from core.dates import as_datetime, now_utc
from core.pagination import combine, page_params, paginate, search_filter
from core.permissions import require_any_permission, require_permission
from models.auth import User

from models.adjustments import ReasonIn, AdjustmentIn

from services.adjustments import adjustments_query, adjustments_totals

from services import adjustments as adjustments_service

router = APIRouter(tags=["Ajustes de inventario"])


# ==================================================================== MOTIVOS (catálogo)


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


@router.post("/inventory/adjustments")
async def create_adjustment(body: AdjustmentIn, current_user: User = Depends(require_permission("inventory", "create"))):
    return await adjustments_service.create_adjustment(body=body, current_user=current_user)


@router.get("/inventory/adjustments")
async def list_adjustments(kind: Optional[str] = None, reason: Optional[str] = None, start_date: Optional[str] = None,
                           end_date: Optional[str] = None, tz_offset_minutes: int = 0, search: Optional[str] = None,
                           pg: dict = Depends(page_params), current_user: User = Depends(require_permission("inventory", "read"))):
    """Ajustes paginados, más recientes primero, con totales del filtro (pérdidas / sobrantes al costo)."""
    query = adjustments_query(kind, reason, start_date, end_date, tz_offset_minutes, search)
    # El listado no trae los productos (pueden ser cientos en un conteo); el detalle sí.
    page = await paginate(db.inventory_adjustments, query, [("created_at", -1)], projection={"_id": 0, "items": 0}, **pg)
    page["summary"] = await adjustments_totals(query)
    return page


@router.get("/inventory/adjustments/export")
async def export_adjustments(kind: Optional[str] = None, reason: Optional[str] = None, start_date: Optional[str] = None,
                             end_date: Optional[str] = None, tz_offset_minutes: int = 0, search: Optional[str] = None,
                             format: str = "csv", current_user: User = Depends(require_permission("inventory", "read"))):
    """Export completo del filtro (CSV: una fila por producto ajustado). P2.33: csv · xlsx · pdf."""
    from core.exporting import check_format, period_label
    query = adjustments_query(kind, reason, start_date, end_date, tz_offset_minutes, search)
    if check_format(format) != "csv":
        from services.exports import adjustments_report
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
