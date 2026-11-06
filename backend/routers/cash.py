"""Control de caja (backlog P2.31): apertura, movimientos, cierre con arqueo, historial y el
interruptor "Exigir caja abierta para vender". Reglas en core/cash.py."""
from datetime import datetime
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import audit
from core.cash import (BILLS, COINS, CASH_COUNTER, CASH_METHOD, attach_pending_movements, add_movement, counted_from,
                       get_settings, money, open_session_of, set_settings, summarize)
from core.counters import ensure_counter, next_number
from core.database import db
from core.dates import now_utc
from core.pagination import combine, page_params, paginate
from core.permissions import require_permission
from core.sales import created_at_range
from core.security import get_current_user
from core.transactions import run_in_transaction
from core.user_protection import actor_is_admin
from models.auth import User

router = APIRouter(tags=["Caja"])
MONEY_EPS = 0.005


# ---------------------------------------------------------------- configuración (interruptor)

class CashSettings(BaseModel):
    require_open_session: bool


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

def _name(user: User) -> str:
    return (user.full_name or "").strip() or user.email


async def _load(session_id: str, current_user: User) -> dict:
    doc = await db.cash_sessions.find_one({"session_id": session_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Caja no encontrada")
    if doc["cashier_email"] != current_user.email and not await actor_is_admin(current_user.email):
        raise HTTPException(status_code=403, detail="Solo puedes ver tus propias cajas.")
    return doc


async def _detail(doc: dict) -> dict:
    movements = await db.cash_movements.find({"session_id": doc["session_id"]}, {"_id": 0}).sort("created_at", 1).to_list(None)
    summary = doc.get("closing_summary") if doc["status"] == "closed" else await summarize(doc)
    return {**doc, "summary": summary, "movements": movements}


# ---------------------------------------------------------------- apertura y estado

class OpenCash(BaseModel):
    opening_amount: float = Field(..., ge=0, description="Base inicial en efectivo")
    notes: Optional[str] = Field(None, max_length=300)


@router.get("/cash/current")
async def current_cash(current_user: User = Depends(require_permission("cash", "read"))):
    """Mi caja abierta (con su resumen) o null, más la configuración y los pendientes sin caja."""
    doc = await open_session_of(current_user.email)
    pending = await db.cash_movements.count_documents({"session_id": None, "created_by": current_user.email})
    return {"session": await _detail(doc) if doc else None, "settings": await get_settings(), "pending_movements": pending}


@router.post("/cash/open")
async def open_cash(body: OpenCash, current_user: User = Depends(require_permission("cash", "create"))):
    if await open_session_of(current_user.email):
        raise HTTPException(status_code=400, detail="Ya tienes una caja abierta: ciérrala antes de abrir otra.")
    await ensure_counter(CASH_COUNTER)

    async def _open(session):
        number = await next_number(CASH_COUNTER, session=session)
        doc = {
            "session_id": number,
            "open_key": current_user.email,          # índice único: una sola caja abierta por cajero
            "cashier_email": current_user.email,
            "cashier_name": _name(current_user),
            "status": "open",
            "opening_amount": round(body.opening_amount, 2),
            "opening_notes": (body.notes or "").strip() or None,
            "opened_at": now_utc(),
        }
        await db.cash_sessions.insert_one(dict(doc), session=session)
        attached = await attach_pending_movements(number, current_user.email, session=session)
        await audit.record("cash", "create", entity_id=number, entity_name=_name(current_user),
                           summary=f"Abrió la caja {number} con base {money(body.opening_amount)}"
                                   + (f"; se asociaron {attached} movimiento(s) pendientes" if attached else ""),
                           after=doc, session=session)
        return doc, attached

    doc, attached = await run_in_transaction(_open)
    return {**await _detail(doc), "attached_pending": attached}


# ---------------------------------------------------------------- movimientos manuales

class ManualMovement(BaseModel):
    kind: str = Field(..., pattern="^(income|expense)$", description="income = ingreso · expense = egreso")
    amount: float = Field(..., gt=0)
    reason: str = Field(..., min_length=3, max_length=200)


@router.post("/cash/movements")
async def add_manual_movement(body: ManualMovement, current_user: User = Depends(require_permission("cash", "create"))):
    current = await open_session_of(current_user.email)
    if not current:
        raise HTTPException(status_code=400, detail="Abre tu caja antes de registrar ingresos o egresos de efectivo.")
    reason = body.reason.strip()
    if len(reason) < 3:
        raise HTTPException(status_code=400, detail="Escribe el motivo del movimiento (mínimo 3 caracteres).")
    if body.kind == "expense":
        expected = (await summarize(current))["expected_cash"]
        if body.amount - expected > MONEY_EPS:
            raise HTTPException(status_code=400, detail=f"No hay suficiente efectivo en la caja: se esperan {money(expected)} "
                                                        f"y el egreso es de {money(body.amount)}.")
    mov = await add_movement(current["session_id"], body.kind, "in" if body.kind == "income" else "out", CASH_METHOD,
                             body.amount, current_user.email, reason=reason)
    await audit.record("cash", "update", entity_id=current["session_id"], entity_name=_name(current_user),
                       summary=f"{mov['kind_label']} de {money(body.amount)} en la caja {current['session_id']}: {reason}",
                       details=mov)
    return {"movement": {k: v for k, v in mov.items() if k != "_id"}, "summary": await summarize(current)}


# ---------------------------------------------------------------- cierre con arqueo

class CloseCash(BaseModel):
    counted_cash: Optional[float] = None
    denominations: Optional[Dict[str, int]] = None
    notes: Optional[str] = Field(None, max_length=500)
    reconciled: Optional[Dict[str, bool]] = None   # otras formas de pago conciliadas con sus comprobantes


@router.post("/cash/sessions/{session_id}/close")
async def close_cash(session_id: str, body: CloseCash, current_user: User = Depends(require_permission("cash", "update"))):
    doc = await _load(session_id, current_user)
    if doc["status"] != "open":
        raise HTTPException(status_code=400, detail=f"La caja {session_id} ya está cerrada.")
    forced = doc["cashier_email"] != current_user.email     # solo un admin llega aquí (ver _load)
    counted, denoms = counted_from(body.denominations, body.counted_cash)
    notes = (body.notes or "").strip()
    if forced and not notes:
        raise HTTPException(status_code=400, detail="Para cerrar la caja de otro cajero escribe el motivo en observaciones.")

    async def _close(session):
        summary = await summarize(doc, session=session)
        difference = round(counted - summary["expected_cash"], 2)
        if abs(difference) > MONEY_EPS and not notes:
            raise HTTPException(status_code=400, detail=f"Hay una diferencia de {money(difference)} "
                                                        f"({'sobrante' if difference > 0 else 'faltante'}): escribe una observación para cerrar.")
        update = {
            "status": "closed",
            "open_key": session_id,
            "closed_at": now_utc(),
            "closed_by": current_user.email,
            "forced_close": forced,
            "counted_cash": round(counted, 2),
            "denominations": denoms,
            "difference": difference,
            "closing_notes": notes or None,
            "reconciled": {k: bool(v) for k, v in (body.reconciled or {}).items()},
            "closing_summary": summary,      # foto del cierre: no cambia aunque luego lleguen movimientos
        }
        res = await db.cash_sessions.update_one({"session_id": session_id, "status": "open"}, {"$set": update}, session=session)
        if res.modified_count == 0:
            raise HTTPException(status_code=400, detail=f"La caja {session_id} ya está cerrada.")
        label = "Cerró" + (" (forzado, caja de " + doc["cashier_email"] + ")" if forced else "")
        result = "cuadrada" if abs(difference) <= MONEY_EPS else ("sobrante " if difference > 0 else "faltante ") + money(abs(difference))
        await audit.record("cash", "update", entity_id=session_id, entity_name=doc["cashier_name"],
                           summary=f"{label} la caja {session_id}: esperado {money(summary['expected_cash'])}, "
                                   f"contado {money(counted)} → {result}",
                           before={"status": "open"}, after={k: v for k, v in update.items() if k != "closing_summary"},
                           session=session)
        return update

    await run_in_transaction(_close)
    return await _detail(await db.cash_sessions.find_one({"session_id": session_id}, {"_id": 0}))


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
        page["cashiers"] = sorted(c for c in await db.cash_sessions.distinct("cashier_email") if c)
    page["is_admin"] = is_admin
    return page


@router.get("/cash/sessions/{session_id}")
async def get_cash_session(session_id: str, current_user: User = Depends(require_permission("cash", "read"))):
    doc = await _load(session_id, current_user)
    doc.pop("open_key", None)
    return await _detail(doc)
