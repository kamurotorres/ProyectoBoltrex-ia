"""core/purchasing.py — el costo del producto al confirmar una compra (rama compras-estilo-pos, decisión 2.A)."""
from core.purchasing import cost_changes, price_warnings

PRODUCTS = {
    "A": {"barcode": "A", "name": "Gaseosa", "purchase_price": 1000, "prices": [{"price_list_name": "default", "price": 1500},
                                                                                 {"price_list_name": "mayorista", "price": 1200}]},
    "B": {"barcode": "B", "name": "Pan", "purchase_price": 500, "prices": [{"price_list_name": "default", "price": 800}]},
    "C": {"barcode": "C", "name": "Leche", "purchase_price": None, "prices": []},
}


def test_el_costo_pasa_a_ser_el_de_la_compra():
    items = [{"barcode": "A", "unit_cost": 1300}, {"barcode": "B", "unit_cost": 500}, {"barcode": "C", "unit_cost": 2000.456}]
    assert cost_changes(items, PRODUCTS) == [
        {"barcode": "A", "name": "Gaseosa", "old_cost": 1000.0, "new_cost": 1300.0},
        {"barcode": "C", "name": "Leche", "old_cost": 0.0, "new_cost": 2000.46},
    ]   # B no cambia (mismo costo)


def test_costo_cero_es_regalo_y_no_cambia_el_costo():
    assert cost_changes([{"barcode": "A", "unit_cost": 0}, {"barcode": "B", "unit_cost": None}], PRODUCTS) == []


def test_si_el_producto_se_repite_cuenta_la_ultima_linea():
    items = [{"barcode": "A", "unit_cost": 1300}, {"barcode": "A", "unit_cost": 1100}]
    assert cost_changes(items, PRODUCTS) == [{"barcode": "A", "name": "Gaseosa", "old_cost": 1000.0, "new_cost": 1100.0}]


def test_diferencias_de_centavo_no_cuentan_y_producto_inexistente_se_ignora():
    assert cost_changes([{"barcode": "A", "unit_cost": 1000.004}, {"barcode": "X", "unit_cost": 5}], PRODUCTS) == []


def test_aviso_de_precios_por_debajo_del_costo_nuevo():
    changes = cost_changes([{"barcode": "A", "unit_cost": 1300}, {"barcode": "B", "unit_cost": 600}], PRODUCTS)
    assert price_warnings(changes, PRODUCTS) == [
        {"barcode": "A", "name": "Gaseosa", "new_cost": 1300.0, "prices": [{"price_list_name": "mayorista", "price": 1200.0}]},
    ]   # Pan: $800 ≥ $600, sin aviso
    assert price_warnings(cost_changes([{"barcode": "A", "unit_cost": 1200}], PRODUCTS), PRODUCTS) == []   # igual al precio: sin aviso
