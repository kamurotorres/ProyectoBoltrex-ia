"""Productos y su stock (mantenimiento fase 3). Las operaciones de stock que se repetían en ventas,
devoluciones, compras y ajustes viven aquí, junto con el registro del movimiento de inventario.

Reglas que garantiza:
- `take_stock` descuenta SOLO si hay suficiente en ese instante (condición atómica en la base): con
  ventas o salidas simultáneas el stock nunca baja de 0.
- `set_stock_if` cambia el stock solo si sigue siendo el que se vio (conteo físico sin pisar ventas).
Todas aceptan `session` para trabajar dentro de una transacción.
"""
from datetime import datetime
from typing import Optional

from core.database import db


async def get(barcode: str, session=None, projection: Optional[dict] = None) -> Optional[dict]:
    return await db.products.find_one({"barcode": barcode}, projection if projection is not None else {"_id": 0},
                                      session=session)


async def take_stock(barcode: str, quantity: int, session=None) -> bool:
    """Descuenta `quantity` si hay stock suficiente. False si no alcanzó (no se cambió nada)."""
    result = await db.products.update_one({"barcode": barcode, "stock": {"$gte": quantity}},
                                          {"$inc": {"stock": -quantity}}, session=session)
    return result.modified_count == 1


async def add_stock(barcode: str, quantity: int, session=None) -> None:
    await db.products.update_one({"barcode": barcode}, {"$inc": {"stock": quantity}}, session=session)


async def set_stock_if(barcode: str, expected: int, new_stock: int, session=None) -> bool:
    """Deja el stock en `new_stock` solo si todavía es `expected`. False si cambió mientras tanto."""
    result = await db.products.update_one({"barcode": barcode, "stock": expected}, {"$set": {"stock": new_stock}},
                                          session=session)
    return result.modified_count == 1


async def set_purchase_price(barcode: str, cost: float, session=None) -> None:
    """Costo (precio de compra) del producto: lo actualiza la confirmación de una compra."""
    await db.products.update_one({"barcode": barcode}, {"$set": {"purchase_price": cost}}, session=session)


async def record_movement(*, barcode: str, product_name: str, movement_type: str, quantity: int, reference: str,
                          created_by: str, created_at: datetime, session=None, **extra) -> None:
    """Movimiento de inventario (sale, return, purchase, adjustment): cantidad con signo."""
    await db.inventory_movements.insert_one({
        "barcode": barcode, "product_name": product_name, "movement_type": movement_type, "quantity": quantity,
        "reference": reference, **extra, "created_by": created_by, "created_at": created_at,
    }, session=session)
