"""Reglas de precios e IVA de los productos (backlog P1.16 y P1.17, decisiones del usuario).

P1.16 · IVA: lo define cada producto (campo `tax_rate`), entre 0 y 100 % (ambos incluidos).
         La venta usa el IVA del producto. Valor inicial en el formulario: 0.
P1.17 · Precios de venta:
         - obligatorios: no hay productos sin precio (y la lista "default" es obligatoria,
           porque es la que se usa cuando el producto no tiene precio para la lista del cliente);
         - cada precio debe ser mayor que 0 y mayor o igual al precio de compra;
         - en la venta: precio de la lista del cliente → si no hay, el de "default".
           Se eliminó el precio inventado "costo × 1,3".
"""
import math
from typing import Iterable, List, Optional

from core.errors import BusinessError, DomainError
from core.money import money

DEFAULT_PRICE_LIST = "default"


def _number(value, field: str) -> float:
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise BusinessError(f"El {field} debe ser un número.")
    if math.isnan(n) or math.isinf(n):
        raise BusinessError(f"El {field} debe ser un número.")
    return n


def _price_list_of(p) -> str:
    return (p.get("price_list_name") if isinstance(p, dict) else getattr(p, "price_list_name", "")) or ""


def _price_of(p):
    return p.get("price") if isinstance(p, dict) else getattr(p, "price", None)


def pricing_problem(purchase_price, tax_rate, prices: Optional[Iterable]) -> Optional[str]:
    """Devuelve el motivo (en español) por el que el producto no es válido, o None."""
    try:
        cost = _number(purchase_price, "precio de compra")
        if cost < 0:
            return "El precio de compra no puede ser negativo."
        iva = _number(tax_rate, "IVA")
        if iva < 0 or iva > 100:
            return "El IVA debe estar entre 0 y 100 %."
        prices = list(prices or [])
        if not prices:
            return "No se puede crear un producto sin precios de venta. Agrega al menos el precio de la lista 'default'."
        seen = set()
        for p in prices:
            name = _price_list_of(p).strip()
            if not name:
                return "Cada precio de venta debe tener su lista de precios."
            if name in seen:
                return f"La lista de precios '{name}' está repetida."
            seen.add(name)
            price = _number(_price_of(p), f"precio de la lista '{name}'")
            if price <= 0:
                return f"El precio de la lista '{name}' debe ser mayor a 0."
            if price < cost:
                return (f"El precio de venta de la lista '{name}' ({money(price)}) no puede ser menor que el "
                        f"precio de compra ({money(cost)}).")
        if DEFAULT_PRICE_LIST not in seen:
            return (f"El precio de la lista '{DEFAULT_PRICE_LIST}' es obligatorio: es el que se cobra cuando el "
                    f"cliente tiene una lista para la que el producto no tiene precio.")
    except DomainError as exc:
        return exc.detail
    return None


async def price_lists_catalog() -> dict:
    """{nombre: activa} de las listas de precios parametrizadas."""
    from core.database import db
    rows = await db.price_lists.find({}, {"_id": 0, "name": 1, "is_active": 1}).to_list(None)
    return {r["name"]: r.get("is_active", True) is not False for r in rows}


def price_lists_problem(prices, catalog: dict, previous_lists: Optional[set] = None) -> Optional[str]:
    """Cada precio debe ser de una lista que EXISTA; no se agregan precios nuevos en listas inactivas
    (un precio que el producto ya tenía en una lista luego desactivada se conserva — opción A).
    Con listas sin repetir y existentes, el máximo de precios = número de listas parametrizadas."""
    previous_lists = previous_lists or set()
    for p in prices or []:
        name = _price_list_of(p).strip()
        if name not in catalog:
            return f"La lista de precios '{name}' no existe. Créala en Listas de Precios o quita ese precio."
        if not catalog[name] and name not in previous_lists:
            return (f"La lista de precios '{name}' está inactiva: no se le pueden agregar precios nuevos. "
                    f"Actívala en Listas de Precios o elige otra.")
    return None


async def validate_price_lists(prices, previous_prices=None) -> None:
    previous = {_price_list_of(p) for p in (previous_prices or [])}
    problem = price_lists_problem(prices, await price_lists_catalog(), previous)
    if problem:
        raise BusinessError(problem)


def validate_pricing(purchase_price, tax_rate, prices) -> None:
    problem = pricing_problem(purchase_price, tax_rate, prices)
    if problem:
        raise BusinessError(problem)


def unit_price_for(product: dict, price_list: Optional[str]) -> float:
    """Precio de venta para la lista del cliente; si el producto no la tiene, el de 'default'."""
    prices: List[dict] = product.get("prices") or []
    by_list = {p.get("price_list_name"): p.get("price") for p in prices}
    for name in (price_list, DEFAULT_PRICE_LIST):
        if name and by_list.get(name) is not None:
            return float(by_list[name])
    raise BusinessError(f"El producto '{product.get('name', product.get('barcode'))}' no tiene precio de venta "
               f"(ni para la lista '{price_list or DEFAULT_PRICE_LIST}' ni para '{DEFAULT_PRICE_LIST}'). "
               f"Agrégale un precio en Productos.")


async def warn_products_without_price() -> int:
    """Al arrancar: avisa en el log de productos sin precio 'default' (no se podrán vender). Nunca falla."""
    import logging
    from core.database import db
    log = logging.getLogger("boltrex")
    try:
        cursor = db.products.find({"prices.price_list_name": {"$ne": DEFAULT_PRICE_LIST}}, {"_id": 0, "barcode": 1, "name": 1})
        items = await cursor.to_list(1000)
        if items:
            sample = ", ".join(f"{p.get('name')} ({p.get('barcode')})" for p in items[:10])
            log.warning("%d producto(s) sin precio de la lista '%s': no se podrán vender hasta agregarlo en Productos. %s",
                        len(items), DEFAULT_PRICE_LIST, sample)
        return len(items)
    except Exception as exc:  # pragma: no cover
        log.error("No se pudo revisar productos sin precio: %s", exc)
        return 0
