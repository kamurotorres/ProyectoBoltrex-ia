"""core/cash.py — conteo de efectivo del cierre de caja (P2.31)."""
import pytest

from core.cash import DENOMINATIONS, counted_from, is_cash, money
from core.errors import BusinessError


def test_formato_de_dinero_colombiano():
    # Regla única del sistema (core/money.py): centavos solo si existen.
    assert money(1234567) == "$1.234.567"
    assert money(1234567.4) == "$1.234.567,40"
    assert money(0) == "$0"
    assert money(None) == "$0"
    assert money(999.5) == "$999,50"


def test_es_efectivo():
    assert is_cash("Efectivo") and is_cash("  efectivo ")
    assert not is_cash("Nequi") and not is_cash(None) and not is_cash("")


def test_billetes_y_monedas_de_colombia():
    assert DENOMINATIONS == [100000, 50000, 20000, 10000, 5000, 2000, 1000, 500, 200, 100, 50]


def test_conteo_por_denominaciones():
    total, detail = counted_from({"50000": "2", "1000": 3, "500": 0, "100": None}, None)
    assert total == 103000.0
    assert detail == {"50000": 2, "1000": 3}            # las que van en 0 no se guardan
    total, detail = counted_from({50: 1}, 999999)        # con denominaciones se ignora el total escrito
    assert (total, detail) == (50.0, {"50": 1})


def test_conteo_por_total_escrito():
    assert counted_from(None, 50500.5) == (50500.5, None)
    assert counted_from({}, 0) == (0.0, None)


@pytest.mark.parametrize("denominations, counted, message", [
    ({"300": 1}, None, "Denominación no válida en Colombia: $300"),
    ({"abc": 1}, None, "Denominación inválida: abc"),
    ({"1000": "x"}, None, "Denominación inválida: 1000"),
    ({"1000": -1}, None, "La cantidad de $1.000 no puede ser negativa."),
    (None, None, "Indica el efectivo contado (total o por denominaciones)."),
    (None, -1, "El efectivo contado no puede ser negativo."),
])
def test_conteos_invalidos(denominations, counted, message):
    with pytest.raises(BusinessError) as e:
        counted_from(denominations, counted)
    assert e.value.message == message
