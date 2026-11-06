"""Formas de pago (mantenimiento fase 3: separado de routers/invoices.py)."""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from core.dates import now_utc, as_datetime
from core.database import db
from core.permissions import require_permission, require_any_permission
from models.auth import User
from models.billing import PaymentMethod, PaymentMethodCreate, PaymentMethodUpdate

from core import audit
from core.pagination import page_params, paginate, search_filter

router = APIRouter(tags=["Formas de pago"])


@router.post("/payment-methods", response_model=PaymentMethod)
async def create_payment_method(payment_method: PaymentMethodCreate, current_user: User = Depends(require_permission("payment-methods", "create"))):
    """Crear una nueva forma de pago"""
    existing = await db.payment_methods.find_one({"name": payment_method.name})
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe una forma de pago con ese nombre")

    pm_dict = payment_method.model_dump()
    pm_dict["created_at"] = now_utc()
    await db.payment_methods.insert_one(pm_dict)
    await audit.record("payment-methods", "create", entity_id=payment_method.name, entity_name=payment_method.name,
                       summary=f"Creó la forma de pago '{payment_method.name}'", after=pm_dict)
    return PaymentMethod(**pm_dict)


@router.get("/payment-methods")
async def get_payment_methods(paginated: bool = False, search: Optional[str] = None, pg: dict = Depends(page_params),
                              current_user: User = Depends(require_permission("payment-methods", "read"))):
    """Listar formas de pago"""
    # P1.18: con `paginated=true` (pantalla de administración) responde paginado y con búsqueda en el
    # servidor; sin él, la lista completa para los selectores de otras pantallas (son catálogos pequeños).
    query = search_filter(search, ["name", "description"]) or {}
    if paginated:
        return await paginate(db.payment_methods, query, [("name", 1)], **pg)
    return await db.payment_methods.find(query, {"_id": 0}).sort([("name", 1), ("_id", 1)]).to_list(None)


@router.get("/payment-methods/active", response_model=List[PaymentMethod])
async def get_active_payment_methods(current_user: User = Depends(require_any_permission(("payment-methods", "read"), ("pos", "read"), ("fios", "read")))):
    """Listar solo formas de pago activas (para POS y Fios)"""
    payment_methods = await db.payment_methods.find({"is_active": True}, {"_id": 0}).to_list(None)
    for pm in payment_methods:
        if isinstance(pm.get('created_at'), str):
            pm['created_at'] = as_datetime(pm['created_at'])
    return payment_methods


@router.put("/payment-methods/{name}", response_model=PaymentMethod)
async def update_payment_method(name: str, payment_method: PaymentMethodUpdate, current_user: User = Depends(require_permission("payment-methods", "update"))):
    """Actualizar una forma de pago"""
    update_data = {k: v for k, v in payment_method.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No hay datos para actualizar")

    # Check if new name already exists (if changing name)
    if "name" in update_data and update_data["name"] != name:
        existing = await db.payment_methods.find_one({"name": update_data["name"]})
        if existing:
            raise HTTPException(status_code=400, detail="Ya existe una forma de pago con ese nombre")

    before = await db.payment_methods.find_one({"name": name}, {"_id": 0})
    result = await db.payment_methods.update_one({"name": name}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Forma de pago no encontrada")
    after = {**before, **update_data}
    await audit.record("payment-methods", "update", entity_id=update_data.get("name", name), entity_name=update_data.get("name", name),
                       summary=f"Modificó la forma de pago '{name}': {audit.describe_changes(audit.diff(before, after))}",
                       before=before, after=after)

    # Get updated (use new name if changed)
    new_name = update_data.get("name", name)
    updated = await db.payment_methods.find_one({"name": new_name}, {"_id": 0})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = as_datetime(updated['created_at'])
    return PaymentMethod(**updated)


@router.delete("/payment-methods/{name}")
async def delete_payment_method(name: str, current_user: User = Depends(require_permission("payment-methods", "delete"))):
    """Eliminar una forma de pago"""
    # Check if payment method is being used in any invoice
    usage = await db.invoices.find_one({"payment_method": name})
    if usage:
        raise HTTPException(status_code=400, detail="No se puede eliminar: esta forma de pago está siendo utilizada en facturas")

    before = await db.payment_methods.find_one({"name": name}, {"_id": 0})
    result = await db.payment_methods.delete_one({"name": name})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Forma de pago no encontrada")
    await audit.record("payment-methods", "delete", entity_id=name, entity_name=name,
                       summary=f"Eliminó la forma de pago '{name}'", before=before)
    return {"message": "Forma de pago eliminada"}
