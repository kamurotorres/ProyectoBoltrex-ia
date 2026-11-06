"""IVA (tarifas) (mantenimiento fase 3: separado de routers/invoices.py)."""
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from core.dates import now_utc, as_datetime
from core.database import db
from core.security import get_current_user
from core.permissions import require_permission
from models.auth import User
from models.billing import TaxRate, TaxRateCreate

from core import audit

router = APIRouter(tags=["IVA"])


@router.post("/tax-rates", response_model=TaxRate)
async def create_tax_rate(tax_rate: TaxRateCreate, current_user: User = Depends(require_permission("permissions", "update"))):
    if tax_rate.is_active:
        await db.tax_rates.update_many({"is_active": True}, {"$set": {"is_active": False}})

    tr_dict = tax_rate.model_dump()
    if tr_dict.get("effective_date"):
        tr_dict["effective_date"] = as_datetime(tr_dict["effective_date"])
    else:
        tr_dict["effective_date"] = now_utc()
    tr_dict["created_at"] = now_utc()

    await db.tax_rates.insert_one(tr_dict)
    await audit.record("tax-rates", "create", entity_id=tr_dict.get("name"), entity_name=tr_dict.get("name"),
                       summary=f"Creó la tarifa de IVA '{tr_dict.get('name')}' ({tr_dict.get('rate')})"
                               + (" y la dejó activa" if tax_rate.is_active else ""), after=tr_dict)
    return TaxRate(**{**tr_dict, "effective_date": as_datetime(tr_dict["effective_date"]), "created_at": as_datetime(tr_dict["created_at"])})


@router.get("/tax-rates", response_model=List[TaxRate])
async def get_tax_rates(current_user: User = Depends(get_current_user)):
    tax_rates = await db.tax_rates.find({}, {"_id": 0}).to_list(None)
    for tr in tax_rates:
        if isinstance(tr.get('effective_date'), str):
            tr['effective_date'] = as_datetime(tr['effective_date'])
        if isinstance(tr.get('created_at'), str):
            tr['created_at'] = as_datetime(tr['created_at'])
    return tax_rates


@router.patch("/tax-rates/{name}/activate")
async def activate_tax_rate(name: str, current_user: User = Depends(require_permission("permissions", "update"))):
    if not await db.tax_rates.find_one({"name": name}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Tarifa de IVA no encontrada")
    previous = await db.tax_rates.find_one({"is_active": True}, {"_id": 0, "name": 1})
    await db.tax_rates.update_many({"is_active": True}, {"$set": {"is_active": False}})
    result = await db.tax_rates.update_one({"name": name}, {"$set": {"is_active": True}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Tarifa de IVA no encontrada")
    prev_name = (previous or {}).get("name")
    await audit.record("tax-rates", "activate", entity_id=name, entity_name=name,
                       summary=f"Activó la tarifa de IVA '{name}'" + (f" (antes: '{prev_name}')" if prev_name else ""),
                       before={"tarifa_activa": prev_name}, after={"tarifa_activa": name})
    return {"message": "Tax rate activated"}
