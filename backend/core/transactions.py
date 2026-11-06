"""Transacciones multi-documento de MongoDB.

Las operaciones de negocio que escriben en varias colecciones (venta, confirmación de
compra, devolución, abono) deben ser todo-o-nada. Uso:

    async def _work(session):
        await db.invoices.insert_one(doc, session=session)
        await db.products.update_one(..., session=session)
        return doc

    result = await run_in_transaction(_work)

- `with_transaction` reintenta automáticamente ante errores transitorios
  (p. ej. WriteConflict cuando dos ventas tocan el mismo producto a la vez).
- Cualquier excepción dentro de `_work` (incluida HTTPException) aborta la transacción
  y no queda ninguna escritura aplicada.
- MongoDB solo soporta transacciones en replica set o sharded cluster. Si el servidor es
  standalone (p. ej. un mongod local sin --replSet), se ejecuta SIN transacción y se
  registra un aviso: así el modo de desarrollo sigue funcionando, pero sin garantía
  de atomicidad. En Docker, MongoDB corre como replica set `rs0` (ver docker-compose.yml).
"""
import logging
from typing import Any, Awaitable, Callable, Optional

from motor.motor_asyncio import AsyncIOMotorClientSession

from core.database import client

logger = logging.getLogger("boltrex")

_supported: Optional[bool] = None


async def transactions_supported() -> bool:
    """True si el servidor MongoDB admite transacciones (replica set o mongos). Se cachea."""
    global _supported
    if _supported is None:
        hello = await client.admin.command("hello")
        _supported = bool(hello.get("setName")) or hello.get("msg") == "isdbgrid"
        if not _supported:
            logger.warning(
                "MongoDB es standalone: las operaciones de venta/compra/devolución/abono se ejecutan "
                "SIN transacción (sin atomicidad). Arranca mongod como replica set para producción."
            )
    return _supported


async def run_in_transaction(work: Callable[[Optional[AsyncIOMotorClientSession]], Awaitable[Any]]) -> Any:
    """Ejecuta `work(session)` dentro de una transacción y devuelve su resultado.

    `work` debe pasar `session=session` a TODAS las lecturas y escrituras de Mongo que haga.
    """
    if not await transactions_supported():
        return await work(None)

    async with await client.start_session() as session:
        return await session.with_transaction(work)
