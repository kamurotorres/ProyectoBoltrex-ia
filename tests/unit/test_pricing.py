"""core/pricing.py — precios por lista e IVA (P1.16/P1.17)."""
from types import SimpleNamespace

import pytest

from core.errors import BusinessError
from core.pricing import price_lists_problem, pricing_problem, unit_price_for, validate_pricing

OK_PRICES = [{"price_list_name": "default", "price": 1500}, {"price_list_name": "mayorista", "price": 1200}]


def test_producto_valido():
    assert pricing_problem(1000, 19, OK_PRICES) is None
    assert pricing_problem("1000", "0", OK_PRICES) is None          # números que llegan como texto
    assert pricing_problem(0, 100, [{"price_list_name": "default", "price": 1}]) is None   # límites


def test_precios_como_objetos_pydantic():
    prices = [SimpleNamespace(price_list_name="default", price=1500)]
    assert pricing_problem(1000, 19, prices) is None


@pytest.mark.parametrize("cost, iva, prices, message", [
    ("abc", 19, OK_PRICES, "El precio de compra debe ser un número."),
    (float("nan"), 19, OK_PRICES, "El precio de compra debe ser un número."),
    (-1, 19, OK_PRICES, "El precio de compra no puede ser negativo."),
    (1000, -0.5, OK_PRICES, "El IVA debe estar entre 0 y 100 %."),
    (1000, 100.1, OK_PRICES, "El IVA debe estar entre 0 y 100 %."),
    (1000, None, OK_PRICES, "El IVA debe ser un número."),
    (1000, 19, [], "No se puede crear un producto sin precios de venta. Agrega al menos el precio de la lista 'default'."),
    (1000, 19, None, "No se puede crear un producto sin precios de venta. Agrega al menos el precio de la lista 'default'."),
    (1000, 19, [{"price_list_name": " ", "price": 1500}], "Cada precio de venta debe tener su lista de precios."),
    (1000, 19, [{"price_list_name": "default", "price": 1500}, {"price_list_name": "default", "price": 1600}],
     "La lista de precios 'default' está repetida."),
    (1000, 19, [{"price_list_name": "default", "price": 0}], "El precio de la lista 'default' debe ser mayor a 0."),
    (1000, 19, [{"price_list_name": "default", "price": "x"}], "El precio de la lista 'default' debe ser un número."),
    (1000, 19, [{"price_list_name": "default", "price": 999.99}],
     "El precio de venta de la lista 'default' ($999,99) no puede ser menor que el precio de compra ($1.000)."),
    (1000, 19, [{"price_list_name": "mayorista", "price": 1500}],
     "El precio de la lista 'default' es obligatorio: es el que se cobra cuando el cliente tiene una lista para la que el producto no tiene precio."),
])
def test_problemas_de_precio(cost, iva, prices, message):
    assert pricing_problem(cost, iva, prices) == message


def test_validate_pricing_lanza_error_de_negocio():
    with pytest.raises(BusinessError) as e:
        validate_pricing(1000, 19, [])
    assert e.value.status_code == 400
    validate_pricing(1000, 19, OK_PRICES)   # válido: no lanza


CATALOG = {"default": True, "mayorista": True, "vieja": False}


def test_listas_de_precios_existentes_y_activas():
    assert price_lists_problem(OK_PRICES, CATALOG) is None
    assert price_lists_problem([{"price_list_name": "vip", "price": 1}], CATALOG) == \
        "La lista de precios 'vip' no existe. Créala en Listas de Precios o quita ese precio."
    # Lista inactiva: no se agregan precios nuevos…
    assert price_lists_problem([{"price_list_name": "vieja", "price": 1}], CATALOG) == \
        "La lista de precios 'vieja' está inactiva: no se le pueden agregar precios nuevos. Actívala en Listas de Precios o elige otra."
    # …pero se conserva el que el producto ya tenía (opción A).
    assert price_lists_problem([{"price_list_name": "vieja", "price": 1}], CATALOG, previous_lists={"vieja"}) is None


PRODUCT = {"barcode": "770", "name": "Gaseosa", "prices": [{"price_list_name": "default", "price": 1500},
                                                          {"price_list_name": "mayorista", "price": 1200},
                                                          {"price_list_name": "vip", "price": None}]}


def test_precio_de_venta_segun_lista_del_cliente():
    assert unit_price_for(PRODUCT, "mayorista") == 1200.0
    assert unit_price_for(PRODUCT, "minorista") == 1500.0      # sin precio en su lista → default
    assert unit_price_for(PRODUCT, "vip") == 1500.0            # precio vacío en su lista → default
    assert unit_price_for(PRODUCT, None) == 1500.0
    assert isinstance(unit_price_for({"prices": [{"price_list_name": "default", "price": 7}]}, None), float)


def test_sin_precio_nunca_inventa_uno():
    with pytest.raises(BusinessError) as e:
        unit_price_for({"barcode": "1", "name": "Sin precio", "prices": [{"price_list_name": "vip", "price": 9}]}, "mayorista")
    assert e.value.message == ("El producto 'Sin precio' no tiene precio de venta (ni para la lista 'mayorista' ni para "
                               "'default'). Agrégale un precio en Productos.")
    with pytest.raises(BusinessError, match="El producto '9' no tiene precio"):
        unit_price_for({"barcode": "9"}, None)
