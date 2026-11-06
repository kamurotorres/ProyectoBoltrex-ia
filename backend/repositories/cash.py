"""Cajas y movimientos de dinero (mantenimiento fase 3). Las reglas (esperado por forma de pago, interruptor
«exigir caja», arqueo) están en core/cash.py y services/cash.py; aquí solo el acceso a datos.
Todas aceptan `session` para trabajar dentro de una transacción."""
from typing import List, Optional

from core.database import db


async def get_session(session_id: str, session=None) -> Optional[dict]:
    return await db.cash_sessions.find_one({"session_id": session_id}, {"_id": 0}, session=session)


async def open_session_of(email: str, session=None) -> Optional[dict]:
    return await db.cash_sessions.find_one({"cashier_email": email, "status": "open"}, {"_id": 0}, session=session)


async def insert_session(doc: dict, session=None) -> None:
    await db.cash_sessions.insert_one(dict(doc), session=session)


async def close_if_open(session_id: str, fields: dict, session=None) -> bool:
    """Cierra la caja solo si sigue abierta (dos cierres simultáneos: solo uno gana). False si ya estaba cerrada."""
    res = await db.cash_sessions.update_one({"session_id": session_id, "status": "open"}, {"$set": fields}, session=session)
    return res.modified_count == 1


async def cashiers() -> List[str]:
    return sorted(c for c in await db.cash_sessions.distinct("cashier_email") if c)


async def insert_movement(doc: dict, session=None) -> None:
    await db.cash_movements.insert_one(dict(doc), session=session)


async def movements_of(session_id: str, session=None) -> List[dict]:
    return await db.cash_movements.find({"session_id": session_id}, {"_id": 0}, session=session) \
        .sort("created_at", 1).to_list(None)


async def attach_pending(session_id: str, email: str, session=None) -> int:
    """Los movimientos que `email` registró sin caja pasan a `session_id`."""
    res = await db.cash_movements.update_many({"session_id": None, "created_by": email},
                                              {"$set": {"session_id": session_id, "attached_on_open": True}}, session=session)
    return res.modified_count


async def pending_count(email: str) -> int:
    return await db.cash_movements.count_documents({"session_id": None, "created_by": email})
