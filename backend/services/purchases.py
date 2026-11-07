"""Compras: crear, editar y confirmar (la confirmación suma stock en una transacción) (fase 3)."""
from core.errors import BusinessError, NotFoundError
from core.dates import now_utc, as_datetime
from core.database import db
from repositories import products as products_repo
from core.transactions import run_in_transaction
from core.counters import PURCHASE_COUNTER, ensure_counter, next_number
from models.auth import User
from models.entities import PurchaseCreate, PurchaseUpdate

from core import audit
from core.money import money



async def create_purchase(purchase_data: PurchaseCreate, current_user: User):
    total = sum(item.total for item in purchase_data.items)

    # Consecutivo atómico: compras simultáneas nunca reciben el mismo número.
    await ensure_counter(PURCHASE_COUNTER)

    async def _create(session):
        purchase_dict = {
            "purchase_number": await next_number(PURCHASE_COUNTER, session=session),
            "supplier_name": purchase_data.supplier_name,
            "items": [item.model_dump() for item in purchase_data.items],
            "total": total,
            "status": "borrador",
            "created_by": current_user.email,
            "created_at": now_utc()
        }
        await db.purchases.insert_one(dict(purchase_dict), session=session)
        await audit.record("purchases", "create", entity_id=purchase_dict["purchase_number"],
                           entity_name=purchase_data.supplier_name,
                           summary=f"Creó la compra {purchase_dict['purchase_number']} a '{purchase_data.supplier_name}' "
                                   f"({len(purchase_dict['items'])} producto(s), total {money(total)})",
                           after=purchase_dict, session=session)
        return purchase_dict

    purchase_dict = await run_in_transaction(_create)
    return {**purchase_dict, "created_at": as_datetime(purchase_dict["created_at"])}


async def update_purchase(purchase_number: str, update_data: PurchaseUpdate, current_user: User):
    purchase = await db.purchases.find_one({"purchase_number": purchase_number})
    if not purchase:
        raise NotFoundError("Compra no encontrada")
    if purchase.get("status") != "borrador":
        raise BusinessError("No se puede editar una compra confirmada")

    update_fields = {}
    if update_data.supplier_name is not None:
        update_fields["supplier_name"] = update_data.supplier_name
    if update_data.items is not None:
        items_dump = [item.model_dump() for item in update_data.items]
        update_fields["items"] = items_dump
        update_fields["total"] = sum(item.total for item in update_data.items)

    if update_fields:
        await db.purchases.update_one({"purchase_number": purchase_number}, {"$set": update_fields})
        after = {**purchase, **update_fields}
        await audit.record("purchases", "update", entity_id=purchase_number, entity_name=after.get("supplier_name"),
                           summary=f"Modificó la compra {purchase_number}: {audit.describe_changes(audit.diff(purchase, after))}",
                           before=purchase, after=after)

    updated = await db.purchases.find_one({"purchase_number": purchase_number}, {"_id": 0})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = as_datetime(updated['created_at'])
    return updated


async def confirm_purchase(purchase_number: str, current_user: User):
    async def _confirm(session):
        purchase = await db.purchases.find_one({"purchase_number": purchase_number}, session=session)
        if not purchase:
            raise NotFoundError("Compra no encontrada")

        # Cambio de estado condicionado: si dos confirmaciones llegan a la vez, solo una
        # encuentra la compra en "borrador" y suma el stock.
        result = await db.purchases.update_one(
            {"purchase_number": purchase_number, "status": "borrador"},
            {"$set": {"status": "confirmado"}},
            session=session,
        )
        if result.modified_count == 0:
            raise BusinessError("Esta compra ya está confirmada")

        now = now_utc()
        for item in purchase["items"]:
            await products_repo.add_stock(item["barcode"], item["quantity"], session=session)
            await products_repo.record_movement(barcode=item["barcode"], product_name=item["product_name"], movement_type="purchase",
                                                quantity=item["quantity"], reference=purchase_number,
                                                created_by=current_user.email, created_at=now, session=session)

        units = sum(i["quantity"] for i in purchase["items"])
        await audit.record("purchases", "confirm", entity_id=purchase_number, entity_name=purchase.get("supplier_name"),
                           summary=f"Confirmó la compra {purchase_number}: entraron {units} unidad(es) de "
                                   f"{len(purchase['items'])} producto(s) al inventario",
                           details={"items": [{"barcode": i["barcode"], "product_name": i["product_name"],
                                               "quantity": i["quantity"]} for i in purchase["items"]],
                                    "total": purchase.get("total")},
                           session=session)

    await run_in_transaction(_confirm)

    updated = await db.purchases.find_one({"purchase_number": purchase_number}, {"_id": 0})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = as_datetime(updated['created_at'])
    return updated
