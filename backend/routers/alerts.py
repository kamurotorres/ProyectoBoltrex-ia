"""Alertas (backlog P2.34): campana del encabezado y stock mínimo general (Config. Sistema).
Reglas en core/alerts.py. Cada usuario ve las alertas de lo que su rol puede ver:
stock → Inventario o Productos (ver); créditos → Fios (ver)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core import audit
from core.alerts import build_alerts, get_inventory_settings, mark_seen, set_inventory_settings
from core.database import db
from core.permissions import get_user_permissions
from core.security import get_current_user
from core.user_protection import actor_is_admin
from models.auth import User

router = APIRouter(tags=["Alertas"])


async def _scope(user: User):
    perms = await get_user_permissions(db, user.email)
    can = lambda m: bool(perms.get(m) and perms[m].read)
    return can("inventory") or can("products"), can("fios")


@router.get("/alerts")
async def get_alerts(current_user: User = Depends(get_current_user)):
    can_stock, can_credit = await _scope(current_user)
    return await build_alerts(current_user.email, can_stock, can_credit)


@router.post("/alerts/seen")
async def alerts_seen(current_user: User = Depends(get_current_user)):
    """«Marcar como visto»: apaga el número rojo hasta que haya una alerta nueva o una empeore."""
    can_stock, can_credit = await _scope(current_user)
    n = await mark_seen(current_user.email, can_stock, can_credit)
    return {"seen": n}


class InventorySettings(BaseModel):
    low_stock_threshold: int


@router.get("/inventory/settings")
async def read_inventory_settings(current_user: User = Depends(get_current_user)):
    return await get_inventory_settings()


@router.put("/inventory/settings")
async def update_inventory_settings(body: InventorySettings, current_user: User = Depends(get_current_user)):
    if not await actor_is_admin(current_user.email):
        raise HTTPException(status_code=403, detail="Solo los administradores pueden cambiar el stock mínimo general.")
    before = await get_inventory_settings()
    after = await set_inventory_settings(body.low_stock_threshold, current_user.email)
    if before["low_stock_threshold"] != after["low_stock_threshold"]:
        await audit.record("inventory", "update", entity_id="configuracion", entity_name="Stock mínimo general",
                           summary=f"Cambió el stock mínimo general de {before['low_stock_threshold']} a {after['low_stock_threshold']}",
                           before=before, after=after)
    return after
