from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from core.dates import now_utc, as_datetime
from core.database import db
from core.permissions import require_permission
from core.transactions import run_in_transaction
from core.counters import PURCHASE_COUNTER, ensure_counter, next_number
from models.auth import User
from models.entities import Purchase, PurchaseCreate, PurchaseUpdate

from core import audit
from core.pagination import page_params, paginate, search_filter, combine
from core.sales import created_at_range

router = APIRouter(tags=["Inventory"])
# ==================== PURCHASES ====================

@router.post("/purchases", response_model=Purchase)
async def create_purchase(purchase_data: PurchaseCreate, current_user: User = Depends(require_permission("purchases", "create"))):
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
                                   f"({len(purchase_dict['items'])} producto(s), total {total:,.0f})",
                           after=purchase_dict, session=session)
        return purchase_dict

    purchase_dict = await run_in_transaction(_create)
    return Purchase(**{**purchase_dict, "created_at": as_datetime(purchase_dict["created_at"])})

@router.get("/purchases/{purchase_number}", response_model=Purchase)
async def get_purchase(purchase_number: str, current_user: User = Depends(require_permission("purchases", "read"))):
    purchase = await db.purchases.find_one({"purchase_number": purchase_number}, {"_id": 0})
    if not purchase:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    if isinstance(purchase.get('created_at'), str):
        purchase['created_at'] = as_datetime(purchase['created_at'])
    return Purchase(**purchase)

@router.put("/purchases/{purchase_number}", response_model=Purchase)
async def update_purchase(purchase_number: str, update_data: PurchaseUpdate, current_user: User = Depends(require_permission("purchases", "update"))):
    purchase = await db.purchases.find_one({"purchase_number": purchase_number})
    if not purchase:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    if purchase.get("status") != "borrador":
        raise HTTPException(status_code=400, detail="No se puede editar una compra confirmada")

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
    return Purchase(**updated)

@router.post("/purchases/{purchase_number}/confirm", response_model=Purchase)
async def confirm_purchase(purchase_number: str, current_user: User = Depends(require_permission("purchases", "update"))):
    async def _confirm(session):
        purchase = await db.purchases.find_one({"purchase_number": purchase_number}, session=session)
        if not purchase:
            raise HTTPException(status_code=404, detail="Compra no encontrada")

        # Cambio de estado condicionado: si dos confirmaciones llegan a la vez, solo una
        # encuentra la compra en "borrador" y suma el stock.
        result = await db.purchases.update_one(
            {"purchase_number": purchase_number, "status": "borrador"},
            {"$set": {"status": "confirmado"}},
            session=session,
        )
        if result.modified_count == 0:
            raise HTTPException(status_code=400, detail="Esta compra ya está confirmada")

        now = now_utc()
        for item in purchase["items"]:
            await db.products.update_one(
                {"barcode": item["barcode"]},
                {"$inc": {"stock": item["quantity"]}},
                session=session,
            )
            await db.inventory_movements.insert_one({
                "barcode": item["barcode"],
                "product_name": item["product_name"],
                "movement_type": "purchase",
                "quantity": item["quantity"],
                "reference": purchase_number,
                "created_by": current_user.email,
                "created_at": now
            }, session=session)

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
    return Purchase(**updated)


@router.get("/purchases")
async def get_purchases(search: Optional[str] = None, status: Optional[str] = None, pg: dict = Depends(page_params),
                        current_user: User = Depends(require_permission("purchases", "read"))):
    """Compras paginadas, más recientes primero (P1.18)."""
    query = combine(search_filter(search, ["purchase_number", "supplier_name"]), {"status": status} if status else None)
    return await paginate(db.purchases, query, [("created_at", -1)], **pg)

# ==================== INVENTORY ====================

# P2.34: el mínimo es el del producto (`min_stock`) o el general de Config. Sistema (core/alerts).
LOW_STOCK_THRESHOLD = 10   # valor inicial del general (compatibilidad)


async def inventory_summary(query: Optional[dict] = None) -> dict:
    """Totales de inventario sobre TODOS los productos (P1.18), calculados en la base."""
    from core.alerts import get_inventory_settings, low_stock_expr
    threshold = (await get_inventory_settings())["low_stock_threshold"]
    rows = await db.products.aggregate([
        {"$match": query or {}},
        {"$group": {
            "_id": None,
            "total_products": {"$sum": 1},
            "total_units": {"$sum": {"$ifNull": ["$stock", 0]}},
            "total_value": {"$sum": {"$multiply": [{"$ifNull": ["$purchase_price", 0]}, {"$ifNull": ["$stock", 0]}]}},
            "low_stock_count": {"$sum": {"$cond": [low_stock_expr(threshold), 1, 0]}},
            "out_of_stock_count": {"$sum": {"$cond": [{"$lte": [{"$ifNull": ["$stock", 0]}, 0]}, 1, 0]}},
        }},
    ]).to_list(1)
    r = rows[0] if rows else {}
    return {
        "total_products": r.get("total_products", 0),
        "total_units": r.get("total_units", 0),
        "total_value": round(r.get("total_value", 0) or 0, 2),
        "low_stock_count": r.get("low_stock_count", 0),
        "out_of_stock_count": r.get("out_of_stock_count", 0),
        "low_stock_threshold": threshold,
    }


def _stock_filter(stock: Optional[str], threshold: int = LOW_STOCK_THRESHOLD) -> Optional[dict]:
    if stock == "low":
        from core.alerts import low_stock_filter
        return low_stock_filter(threshold)
    if stock == "out":
        return {"stock": {"$lte": 0}}
    return None


@router.get("/inventory")
async def get_inventory(search: Optional[str] = None, stock: Optional[str] = Query(None, description="low | out"),
                        tz_offset_minutes: int = 0,
                        pg: dict = Depends(page_params), current_user: User = Depends(require_permission("inventory", "read"))):
    """Inventario paginado + totales sobre todos los productos (P1.18) + ajustes del mes (P2.32)."""
    from core.alerts import effective_min, get_inventory_settings, stock_status
    threshold = (await get_inventory_settings())["low_stock_threshold"]
    query = combine(search_filter(search, ["barcode", "name", "category"]), _stock_filter(stock, threshold))
    page = await paginate(db.products, query, [("name", 1)], **pg)
    for p in page["items"]:   # P2.34: mínimo efectivo y estado de cada producto
        p["min_stock_effective"] = effective_min(p, threshold)
        p["stock_status"] = stock_status(p, threshold)
    page["summary"] = await inventory_summary()
    from routers.adjustments import month_adjustments_summary  # import diferido: evita ciclos
    page["adjustments_month"] = await month_adjustments_summary(tz_offset_minutes)
    return page

@router.get("/inventory/movements")
async def get_inventory_movements(
    barcode: Optional[str] = None,
    search: Optional[str] = None,
    movement_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    tz_offset_minutes: int = 0,
    pg: dict = Depends(page_params),
    current_user: User = Depends(require_permission("inventory", "read"))
):
    """Movimientos de inventario paginados, más recientes primero (P1.18)."""
    rng = created_at_range(start_date, end_date, tz_offset_minutes)
    query = combine(
        {"barcode": barcode} if barcode else None,
        {"movement_type": movement_type} if movement_type else None,
        {"created_at": rng} if rng else None,
        search_filter(search, ["barcode", "product_name", "reference", "created_by"]),
    )
    return await paginate(db.inventory_movements, query, [("created_at", -1)], **pg)

