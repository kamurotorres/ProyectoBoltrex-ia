from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from core.dates import as_datetime
from core.database import db
from core.permissions import require_permission
from models.auth import User
from models.entities import Purchase, PurchaseConfirmed, PurchaseCreate, PurchaseUpdate

from core.pagination import page_params, paginate, search_filter, combine
from core.sales import created_at_range

from services.inventory import inventory_summary, stock_filter

from services import purchases as purchases_service

router = APIRouter(tags=["Inventory"])
# ==================== PURCHASES ====================

@router.post("/purchases", response_model=Purchase)
async def create_purchase(purchase_data: PurchaseCreate, current_user: User = Depends(require_permission("purchases", "create"))):
    return Purchase(**await purchases_service.create_purchase(purchase_data=purchase_data, current_user=current_user))

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
    return Purchase(**await purchases_service.update_purchase(purchase_number=purchase_number, update_data=update_data, current_user=current_user))

@router.post("/purchases/{purchase_number}/confirm", response_model=PurchaseConfirmed)
async def confirm_purchase(purchase_number: str, current_user: User = Depends(require_permission("purchases", "update"))):
    return PurchaseConfirmed(**await purchases_service.confirm_purchase(purchase_number=purchase_number, current_user=current_user))


@router.get("/purchases")
async def get_purchases(search: Optional[str] = None, status: Optional[str] = None, pg: dict = Depends(page_params),
                        current_user: User = Depends(require_permission("purchases", "read"))):
    """Compras paginadas, más recientes primero (P1.18)."""
    query = combine(search_filter(search, ["purchase_number", "supplier_name"]), {"status": status} if status else None)
    return await paginate(db.purchases, query, [("created_at", -1)], **pg)

# ==================== INVENTORY ====================

# P2.34: el mínimo es el del producto (`min_stock`) o el general de Config. Sistema (core/alerts).


@router.get("/inventory")
async def get_inventory(search: Optional[str] = None, stock: Optional[str] = Query(None, description="low | out"),
                        tz_offset_minutes: int = 0,
                        pg: dict = Depends(page_params), current_user: User = Depends(require_permission("inventory", "read"))):
    """Inventario paginado + totales sobre todos los productos (P1.18) + ajustes del mes (P2.32)."""
    from core.alerts import effective_min, get_inventory_settings, stock_status
    threshold = (await get_inventory_settings())["low_stock_threshold"]
    query = combine(search_filter(search, ["barcode", "name", "category"]), stock_filter(stock, threshold))
    page = await paginate(db.products, query, [("name", 1)], **pg)
    for p in page["items"]:   # P2.34: mínimo efectivo y estado de cada producto
        p["min_stock_effective"] = effective_min(p, threshold)
        p["stock_status"] = stock_status(p, threshold)
    page["summary"] = await inventory_summary()
    from services.adjustments import month_adjustments_summary  # import diferido: evita ciclos
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

