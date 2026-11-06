"""Inventario: totales sobre todos los productos y filtros de stock (fase 3; lo usan Inventario, Reportes, Dashboard y Exportar)."""
from typing import Optional
from core.database import db



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


def stock_filter(stock: Optional[str], threshold: int = LOW_STOCK_THRESHOLD) -> Optional[dict]:
    if stock == "low":
        from core.alerts import low_stock_filter
        return low_stock_filter(threshold)
    if stock == "out":
        return {"stock": {"$lte": 0}}
    return None
