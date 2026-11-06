"""Control de caja (backlog P2.31): apertura, movimientos, cierre con arqueo, historial y el
interruptor "Exigir caja abierta para vender". Reglas en core/cash.py."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from core import audit
from core.cash import (BILLS, COINS, CASH_METHOD, get_settings, open_session_of, set_settings)
from core.database import db
from core.pagination import combine, page_params, paginate
from core.permissions import require_permission
from core.sales import created_at_range
from core.security import get_current_user
from core.user_protection import actor_is_admin
from models.auth import User

from models.cash import CashSettings, OpenCash, ManualMovement, CloseCash

from services.cash import cash_session_detail, load_cash_session

from services import cash as cash_service

from repositories import cash as cash_repo

router = APIRouter(tags=["Caja"])


# ---------------------------------------------------------------- configuración (interruptor)


@router.get("/cash/settings")
async def read_cash_settings(current_user: User = Depends(get_current_user)):
    """Cualquier usuario con sesión la lee (el POS necesita saber si debe exigir caja)."""
    return {**await get_settings(), "denominations": {"bills": BILLS, "coins": COINS}, "cash_method": CASH_METHOD}


@router.put("/cash/settings")
async def update_cash_settings(body: CashSettings, current_user: User = Depends(get_current_user)):
    if not await actor_is_admin(current_user.email):
        raise HTTPException(status_code=403, detail="Solo los administradores pueden cambiar la configuración de caja.")
    before = await get_settings()
    after = await set_settings(body.require_open_session, current_user.email)
    if before["require_open_session"] != after["require_open_session"]:
        await audit.record("cash", "update", entity_id="configuracion", entity_name="Exigir caja abierta para vender",
                           summary=("Activó" if after["require_open_session"] else "Desactivó") + " «Exigir caja abierta para vender»",
                           before={"require_open_session": before["require_open_session"]},
                           after={"require_open_session": after["require_open_session"]})
    return after


# ---------------------------------------------------------------- helpers


# ---------------------------------------------------------------- apertura y estado


@router.get("/cash/current")
async def current_cash(current_user: User = Depends(require_permission("cash", "read"))):
    """Mi caja abierta (con su resumen) o null, más la configuración y los pendientes sin caja."""
    doc = await open_session_of(current_user.email)
    pending = await cash_repo.pending_count(current_user.email)
    return {"session": await cash_session_detail(doc) if doc else None, "settings": await get_settings(), "pending_movements": pending}


@router.post("/cash/open")
async def open_cash(body: OpenCash, current_user: User = Depends(require_permission("cash", "create"))):
    return await cash_service.open_cash(body=body, current_user=current_user)


# ---------------------------------------------------------------- movimientos manuales


@router.post("/cash/movements")
async def add_manual_movement(body: ManualMovement, current_user: User = Depends(require_permission("cash", "create"))):
    return await cash_service.add_manual_movement(body=body, current_user=current_user)


# ---------------------------------------------------------------- cierre con arqueo


@router.post("/cash/sessions/{session_id}/close")
async def close_cash(session_id: str, body: CloseCash, current_user: User = Depends(require_permission("cash", "update"))):
    return await cash_service.close_cash(session_id=session_id, body=body, current_user=current_user)


# ---------------------------------------------------------------- historial

@router.get("/cash/sessions")
async def list_cash_sessions(cashier: Optional[str] = None, status: Optional[str] = None,
                             start_date: Optional[str] = None, end_date: Optional[str] = None, tz_offset_minutes: int = 0,
                             pg: dict = Depends(page_params), current_user: User = Depends(require_permission("cash", "read"))):
    """Historial paginado. Un cajero ve las suyas; el Administrador todas (filtro por cajero)."""
    is_admin = await actor_is_admin(current_user.email)
    rng = created_at_range(start_date, end_date, tz_offset_minutes)
    query = combine(
        {"cashier_email": (cashier or None) if is_admin else current_user.email} if (cashier or not is_admin) else None,
        {"status": status} if status in ("open", "closed") else None,
        {"opened_at": rng} if rng else None,
    )
    page = await paginate(db.cash_sessions, query, [("opened_at", -1)], projection={"_id": 0, "open_key": 0, "closing_summary": 0}, **pg)
    if is_admin:
        page["cashiers"] = await cash_repo.cashiers()
    page["is_admin"] = is_admin
    return page


@router.get("/cash/sessions/{session_id}")
async def get_cash_session(session_id: str, current_user: User = Depends(require_permission("cash", "read"))):
    doc = await load_cash_session(session_id, current_user)
    doc.pop("open_key", None)
    return await cash_session_detail(doc)
