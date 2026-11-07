"""core/audit.py — qué se guarda y cómo se describe en la auditoría (P1.12)."""
from datetime import datetime, timezone

import pytest

from core.audit import SENSITIVE_KEYS, _clean, describe_changes, diff, field_label, format_value, parse_user_agent


@pytest.mark.parametrize("field, label", [
    ("prices.Detal.price", "precio Detal"),
    ("permissions.read", "permiso ver"),
    ("permissions.delete", "permiso eliminar"),
    ("purchase_price", "costo"),
    ("credit_days", "plazo de crédito (días)"),
    ("campo_nuevo", "campo_nuevo"),
    ("items.770.quantity", "productos / 770 / quantity"),
])
def test_etiquetas_de_campos(field, label):
    assert field_label(field) == label


@pytest.mark.parametrize("value, text", [
    (None, "—"), ("", "—"), (True, "sí"), (False, "no"),
    (2500.0, "2.500"), (2.5, "2.50"), (12345, "12.345"), (9999, "9999"),
    ([1, "a"], "1, a"), ([{"x": 1}], "1 elemento(s)"), ("texto", "texto"),
])
def test_formato_de_valores(value, text):
    assert format_value(value) == text


def test_nunca_se_guardan_contrasenas_ni_ids():
    when = datetime(2026, 11, 6, 10, tzinfo=timezone.utc)
    doc = {"_id": "x", "email": "a@b.co", "password": "p", "hashed_password": "h", "access_token": "t",
           "created_at": when, "nested": {"new_password": "n", "ok": 1}, "list": [{"token": "t", "v": 2}]}
    assert _clean(doc) == {"email": "a@b.co", "created_at": "2026-11-06T10:00:00+00:00", "nested": {"ok": 1}, "list": [{"v": 2}]}
    assert {"password", "hashed_password", "token"} <= SENSITIVE_KEYS


def test_diferencias_campo_por_campo():
    before = {"name": "Gaseosa", "updated_at": "ayer", "prices": [{"price_list_name": "default", "price": 1500}],
              "password": "vieja"}
    after = {"name": "Gaseosa 400", "updated_at": "hoy", "prices": [{"price_list_name": "default", "price": 1600},
                                                                     {"price_list_name": "vip", "price": 1400}],
             "password": "nueva"}
    changes = diff(before, after)
    assert changes == [
        {"field": "name", "label": "nombre", "before": "Gaseosa", "after": "Gaseosa 400"},
        {"field": "prices.default.price", "label": "precio default", "before": 1500, "after": 1600},
        {"field": "prices.vip.price", "label": "precio vip", "before": None, "after": 1400},
    ]   # updated_at se ignora; la contraseña nunca aparece
    assert diff({"a": 1}, {"a": 1}) == []
    assert diff(None, {"name": "x"})[0]["before"] is None


def test_resumen_de_cambios():
    changes = [{"field": f"f{i}", "label": f"campo {i}", "before": i, "after": i + 1} for i in range(6)]
    assert describe_changes(changes[:2]) == "campo 0: 0 → 1; campo 1: 1 → 2"
    assert describe_changes(changes).endswith("; y 2 cambio(s) más")
    assert describe_changes([]) == "sin cambios"
    assert describe_changes([{"field": "is_active", "before": True, "after": False}]) == "activo: sí → no"


@pytest.mark.parametrize("ua, browser, device", [
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
     "Chrome 120", "PC (Windows)"),
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.2210.91",
     "Edge 120", "PC (Windows)"),
    ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
     "Safari 17", "Celular (iOS)"),
    ("Mozilla/5.0 (Linux; Android 13; SM-X200) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
     "Chrome 119", "Tablet (Android)"),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14.1; rv:121.0) Gecko/20100101 Firefox/121.0", "Firefox 121", "PC (macOS)"),
    ("python-requests/2.32.5", "Script (Python)", "Otro (API)"),
    ("", "Desconocido", "Desconocido"),
    (None, "Desconocido", "Desconocido"),
])
def test_navegador_y_dispositivo(ua, browser, device):
    assert parse_user_agent(ua) == {"browser": browser, "device": device}
