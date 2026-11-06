"""Caja: abrir, movimientos, cerrar con arqueo y cargar una caja (P2.31; fase 3). Reglas base en core/cash.py."""


from core.errors import BusinessError, ForbiddenError, NotFoundError
from core import audit
from core.cash import (CASH_COUNTER, CASH_METHOD, attach_pending_movements, add_movement, counted_from,
                       money, open_session_of, summarize)
from core.counters import ensure_counter, next_number
from repositories import cash as cash_repo
from core.dates import now_utc
from core.transactions import run_in_transaction
from core.user_protection import actor_is_admin
from models.auth import User

from models.cash import OpenCash, ManualMovement, CloseCash






MONEY_EPS = 0.005


def user_display_name(user: User) -> str:
    return (user.full_name or "").strip() or user.email


async def load_cash_session(session_id: str, current_user: User) -> dict:
    doc = await cash_repo.get_session(session_id)
    if not doc:
        raise NotFoundError("Caja no encontrada")
    if doc["cashier_email"] != current_user.email and not await actor_is_admin(current_user.email):
        raise ForbiddenError("Solo puedes ver tus propias cajas.")
    return doc


async def cash_session_detail(doc: dict) -> dict:
    movements = await cash_repo.movements_of(doc["session_id"])
    summary = doc.get("closing_summary") if doc["status"] == "closed" else await summarize(doc)
    return {**doc, "summary": summary, "movements": movements}


async def open_cash(body: OpenCash, current_user: User):
    if await open_session_of(current_user.email):
        raise BusinessError("Ya tienes una caja abierta: ciérrala antes de abrir otra.")
    await ensure_counter(CASH_COUNTER)

    async def _open(session):
        number = await next_number(CASH_COUNTER, session=session)
        doc = {
            "session_id": number,
            "open_key": current_user.email,          # índice único: una sola caja abierta por cajero
            "cashier_email": current_user.email,
            "cashier_name": user_display_name(current_user),
            "status": "open",
            "opening_amount": round(body.opening_amount, 2),
            "opening_notes": (body.notes or "").strip() or None,
            "opened_at": now_utc(),
        }
        await cash_repo.insert_session(doc, session=session)
        attached = await attach_pending_movements(number, current_user.email, session=session)
        await audit.record("cash", "create", entity_id=number, entity_name=user_display_name(current_user),
                           summary=f"Abrió la caja {number} con base {money(body.opening_amount)}"
                                   + (f"; se asociaron {attached} movimiento(s) pendientes" if attached else ""),
                           after=doc, session=session)
        return doc, attached

    doc, attached = await run_in_transaction(_open)
    return {**await cash_session_detail(doc), "attached_pending": attached}


async def add_manual_movement(body: ManualMovement, current_user: User):
    current = await open_session_of(current_user.email)
    if not current:
        raise BusinessError("Abre tu caja antes de registrar ingresos o egresos de efectivo.")
    reason = body.reason.strip()
    if len(reason) < 3:
        raise BusinessError("Escribe el motivo del movimiento (mínimo 3 caracteres).")
    if body.kind == "expense":
        expected = (await summarize(current))["expected_cash"]
        if body.amount - expected > MONEY_EPS:
            raise BusinessError(f"No hay suficiente efectivo en la caja: se esperan {money(expected)} "
                                                        f"y el egreso es de {money(body.amount)}.")
    mov = await add_movement(current["session_id"], body.kind, "in" if body.kind == "income" else "out", CASH_METHOD,
                             body.amount, current_user.email, reason=reason)
    await audit.record("cash", "update", entity_id=current["session_id"], entity_name=user_display_name(current_user),
                       summary=f"{mov['kind_label']} de {money(body.amount)} en la caja {current['session_id']}: {reason}",
                       details=mov)
    return {"movement": {k: v for k, v in mov.items() if k != "_id"}, "summary": await summarize(current)}


async def close_cash(session_id: str, body: CloseCash, current_user: User):
    doc = await load_cash_session(session_id, current_user)
    if doc["status"] != "open":
        raise BusinessError(f"La caja {session_id} ya está cerrada.")
    forced = doc["cashier_email"] != current_user.email     # solo un admin llega aquí (ver load_cash_session)
    counted, denoms = counted_from(body.denominations, body.counted_cash)
    notes = (body.notes or "").strip()
    if forced and not notes:
        raise BusinessError("Para cerrar la caja de otro cajero escribe el motivo en observaciones.")

    async def _close(session):
        summary = await summarize(doc, session=session)
        difference = round(counted - summary["expected_cash"], 2)
        if abs(difference) > MONEY_EPS and not notes:
            raise BusinessError(f"Hay una diferencia de {money(difference)} "
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
        if not await cash_repo.close_if_open(session_id, update, session=session):
            raise BusinessError(f"La caja {session_id} ya está cerrada.")
        label = "Cerró" + (" (forzado, caja de " + doc["cashier_email"] + ")" if forced else "")
        result = "cuadrada" if abs(difference) <= MONEY_EPS else ("sobrante " if difference > 0 else "faltante ") + money(abs(difference))
        await audit.record("cash", "update", entity_id=session_id, entity_name=doc["cashier_name"],
                           summary=f"{label} la caja {session_id}: esperado {money(summary['expected_cash'])}, "
                                   f"contado {money(counted)} → {result}",
                           before={"status": "open"}, after={k: v for k, v in update.items() if k != "closing_summary"},
                           session=session)
        return update

    await run_in_transaction(_close)
    return await cash_session_detail(await cash_repo.get_session(session_id))
