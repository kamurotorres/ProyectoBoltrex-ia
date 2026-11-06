"""Consecutivos atómicos (INV-000001, PUR-000001, ...) en la colección `counters`.

Uso dentro de una transacción (ver core/transactions.py):

    await ensure_counter(INVOICE_COUNTER)                      # fuera de la transacción
    number = await next_number(INVOICE_COUNTER, session=session)  # dentro

- `$inc` sobre un único documento es atómico: dos peticiones simultáneas nunca obtienen
  el mismo número.
- Dentro de una transacción, si la operación falla el incremento se revierte, así que
  la numeración no deja huecos.
- La primera vez, el contador arranca desde el último documento existente para continuar
  la numeración que ya hubiera (bases creadas antes de existir el contador).
"""
from dataclasses import dataclass
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClientSession
from pymongo import ReturnDocument

from core.database import db


@dataclass(frozen=True)
class Counter:
    counter_id: str   # _id del documento en `counters`
    prefix: str       # prefijo del número, p. ej. "INV"
    collection: str   # colección de la que leer el último número existente
    field: str        # campo con el número en esa colección


INVOICE_COUNTER = Counter("invoice_id", "INV", "invoices", "invoice_number")
PURCHASE_COUNTER = Counter("purchase_id", "PUR", "purchases", "purchase_number")


def _parse(number: str) -> int:
    try:
        return int(str(number).split("-")[-1])
    except (ValueError, IndexError):
        return 0


async def ensure_counter(counter: Counter) -> None:
    """Crea el contador si no existe, continuando desde el mayor número ya emitido.

    Debe llamarse ANTES de la transacción: crear documentos con upsert dentro de una
    transacción concurrente produce conflictos innecesarios.
    """
    if await db.counters.find_one({"_id": counter.counter_id}, {"_id": 1}):
        return
    # Los números tienen ancho fijo (6 dígitos), así que el orden de texto coincide con el numérico.
    last = await db[counter.collection].find_one(
        {counter.field: {"$regex": f"^{counter.prefix}-"}}, {"_id": 0, counter.field: 1},
        sort=[(counter.field, -1)],
    )
    seq = _parse(last[counter.field]) if last else 0
    # $setOnInsert + upsert: si dos peticiones llegan a la vez, solo una crea el documento.
    await db.counters.update_one({"_id": counter.counter_id}, {"$setOnInsert": {"seq": seq}}, upsert=True)


async def next_number(counter: Counter, session: Optional[AsyncIOMotorClientSession] = None) -> str:
    """Incrementa el contador y devuelve el número formateado, p. ej. 'PUR-000042'."""
    doc = await db.counters.find_one_and_update(
        {"_id": counter.counter_id},
        {"$inc": {"seq": 1}},
        upsert=True,  # por si ensure_counter no se llamó: arranca en 1
        return_document=ReturnDocument.AFTER,
        session=session,
    )
    return f"{counter.prefix}-{doc['seq']:06d}"
