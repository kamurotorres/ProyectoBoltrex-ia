"""core/dates.py (P1.19), core/sales.py (rangos de fechas de reportes) y core/pagination.py (P1.18)."""
import re
from datetime import datetime, timedelta, timezone

import pytest

from core.dates import as_datetime, parse_date_text
from core.errors import BusinessError
from core.pagination import _with_tiebreak, combine, envelope, search_filter
from core.sales import SALE_STATUSES, created_at_range, invoices_query

UTC = timezone.utc


# ---------------------------------------------------------------- fechas guardadas como texto (datos antiguos)
@pytest.mark.parametrize("text, expected", [
    ("2026-11-06", datetime(2026, 11, 6, tzinfo=UTC)),
    ("2026-11-06T10:00:00Z", datetime(2026, 11, 6, 10, tzinfo=UTC)),
    ("2026-11-06T10:00:00", datetime(2026, 11, 6, 10, tzinfo=UTC)),                  # sin zona = UTC
    ("2026-11-06 10:00:00.123456", datetime(2026, 11, 6, 10, 0, 0, 123456, tzinfo=UTC)),
    ("2026-11-06T10:00:00-05:00", datetime(2026, 11, 6, 15, tzinfo=UTC)),             # se pasa a UTC
    ("  2026-11-06T10:00:00+00:00 ", datetime(2026, 11, 6, 10, tzinfo=UTC)),
])
def test_textos_de_fecha_validos(text, expected):
    assert parse_date_text(text) == expected
    assert parse_date_text(text).tzinfo is not None


@pytest.mark.parametrize("text", ["", "   ", None, "ayer", "2026-13-01", "06/11/2026"])
def test_textos_de_fecha_invalidos(text):
    assert parse_date_text(text) is None


def test_as_datetime():
    naive = datetime(2026, 11, 6, 10)
    assert as_datetime(naive) == datetime(2026, 11, 6, 10, tzinfo=UTC)
    aware = datetime(2026, 11, 6, 10, tzinfo=timezone(timedelta(hours=-5)))
    assert as_datetime(aware) is aware                    # ya tiene zona: no se toca
    assert as_datetime("2026-11-06") == datetime(2026, 11, 6, tzinfo=UTC)
    assert as_datetime("sin fecha") == "sin fecha"        # lo que no es fecha se devuelve igual
    assert as_datetime(None) is None and as_datetime(5) == 5


# ---------------------------------------------------------------- rango de días LOCALES completos
def test_rango_de_dias_locales_en_utc():
    rng = created_at_range("2026-11-01", "2026-11-06", 300)
    assert rng == {"$gte": datetime(2026, 11, 1, 5, 0, tzinfo=UTC),
                   "$lte": datetime(2026, 11, 7, 4, 59, 59, 999999, tzinfo=UTC)}
    assert created_at_range("2026-11-06", None, 0) == {"$gte": datetime(2026, 11, 6, tzinfo=UTC)}
    assert created_at_range(None, "2026-11-06T23:00", 0) == {"$lte": datetime(2026, 11, 6, 23, 59, 59, 999999, tzinfo=UTC)}
    assert created_at_range(None, None) is None and created_at_range("", "") is None


def test_rango_invalido():
    with pytest.raises(BusinessError, match="no puede ser posterior"):
        created_at_range("2026-11-07", "2026-11-06")
    with pytest.raises(BusinessError) as e:
        created_at_range("06/11/2026", None)
    assert e.value.message == "Fecha inválida '06/11/2026': usa el formato AAAA-MM-DD."


def test_consulta_de_ventas():
    assert invoices_query() == {"status": {"$in": SALE_STATUSES}}
    q = invoices_query("2026-11-06", "2026-11-06", 300)
    assert set(q) == {"status", "created_at"} and q["status"] == {"$in": ["completed", "partial_return", "returned"]}


# ---------------------------------------------------------------- paginación y búsqueda
def test_busqueda_escapa_caracteres_especiales():
    f = search_filter("  a.b(c*  ", ["name", "barcode"])
    rx = {"$regex": re.escape("a.b(c*"), "$options": "i"}
    assert f == {"$or": [{"name": rx}, {"barcode": rx}]}
    assert re.search(rx["$regex"], "xa.b(c*y") and not re.search(rx["$regex"], "aXb(c")
    assert search_filter("   ", ["name"]) is None and search_filter(None, ["name"]) is None


def test_combinar_filtros():
    assert combine() == {} and combine(None, {}) == {}
    assert combine({"a": 1}, None) == {"a": 1}
    assert combine({"a": 1}, {"b": 2}) == {"$and": [{"a": 1}, {"b": 2}]}


def test_orden_estable_con_desempate_por_id():
    assert _with_tiebreak([("name", 1)]) == [("name", 1), ("_id", 1)]
    assert _with_tiebreak([("created_at", -1)]) == [("created_at", -1), ("_id", -1)]
    assert _with_tiebreak([("_id", -1)]) == [("_id", -1)]
    assert _with_tiebreak([]) == [("_id", 1)]


@pytest.mark.parametrize("total, size, pages", [(0, 50, 1), (50, 50, 1), (51, 50, 2), (101, 50, 3), (5, 0, 1)])
def test_sobre_de_paginacion(total, size, pages):
    assert envelope(["x"], total, 2, size) == {"items": ["x"], "total": total, "page": 2, "page_size": size, "pages": pages}
