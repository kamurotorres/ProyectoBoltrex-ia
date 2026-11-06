"""Facturas (mantenimiento fase 3): lecturas y escrituras de `invoices` que se repetían entre ventas,
devoluciones, Fios y tickets. Todas aceptan `session` para trabajar dentro de una transacción."""
from typing import Optional

from core.database import db


async def get(invoice_number: str, session=None, projection: Optional[dict] = None) -> Optional[dict]:
    return await db.invoices.find_one({"invoice_number": invoice_number},
                                      projection if projection is not None else {"_id": 0}, session=session)


async def insert(invoice: dict, session=None) -> None:
    await db.invoices.insert_one(dict(invoice), session=session)   # copia: insert_one agrega _id al dict


async def update(invoice_number: str, fields: dict, session=None) -> None:
    await db.invoices.update_one({"invoice_number": invoice_number}, {"$set": fields}, session=session)


async def returns_of(invoice_number: str, session=None) -> list:
    return await db.returns.find({"invoice_number": invoice_number}, {"_id": 0}, session=session) \
        .sort("created_at", 1).to_list(None)
