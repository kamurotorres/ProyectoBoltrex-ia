"""Reglas de la compra al confirmarla (rama compras-estilo-pos, decisión 2.A del usuario).

Al confirmar una compra el costo (precio de compra) de cada producto pasa a ser el de la compra, así la
ganancia de las ventas siguientes y la regla «precio de venta ≥ costo» usan el costo real.
- Una línea con costo 0 (regalo / bonificación del proveedor) NO cambia el costo.
- Si un producto viene en varias líneas, cuenta la última.
- Si el costo nuevo queda por encima de algún precio de venta, se avisa (no se bloquea: la mercancía ya
  llegó); el usuario ajusta los precios en Productos.
Funciones puras: se prueban en tests/unit/test_purchasing.py.
"""
from typing import Dict, Iterable, List

EPS = 0.005   # diferencias menores a medio centavo no cuentan como cambio


def cost_changes(items: Iterable[dict], products: Dict[str, dict]) -> List[dict]:
    """[{barcode, name, old_cost, new_cost}] de los productos cuyo costo cambia con esta compra."""
    last: Dict[str, float] = {}
    for item in items:
        last[item["barcode"]] = float(item.get("unit_cost") or 0)
    changes = []
    for barcode, new_cost in last.items():
        product = products.get(barcode)
        if product is None or new_cost <= 0:
            continue
        old_cost = float(product.get("purchase_price") or 0)
        if abs(new_cost - old_cost) > EPS:
            changes.append({"barcode": barcode, "name": product.get("name", barcode),
                            "old_cost": old_cost, "new_cost": round(new_cost, 2)})
    return changes


def price_warnings(changes: Iterable[dict], products: Dict[str, dict]) -> List[dict]:
    """[{barcode, name, new_cost, prices: [{price_list_name, price}]}]: precios de venta por debajo del costo nuevo."""
    out = []
    for c in changes:
        below = [{"price_list_name": p.get("price_list_name"), "price": float(p.get("price") or 0)}
                 for p in (products.get(c["barcode"], {}).get("prices") or [])
                 if p.get("price") is not None and float(p["price"]) + EPS < c["new_cost"]]
        if below:
            out.append({"barcode": c["barcode"], "name": c["name"], "new_cost": c["new_cost"], "prices": below})
    return out
