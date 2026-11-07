"""core/credit.py — plazos, vencimientos y estado de la cartera (P2.30). Colombia: desfase 300 min (UTC−5)."""
from datetime import date, datetime, timedelta, timezone

import pytest

from core.credit import (MAX_TERM_DAYS, due_date_from, end_of_local_day, invoice_status, local_today, parse_due_date,
                         term_for_client, validate_settings)
from core.errors import BusinessError

CO = 300
UTC = timezone.utc


def test_fin_del_dia_local_en_utc():
    # 6 nov 23:59:59.999999 en Colombia = 7 nov 04:59:59.999999 UTC.
    assert end_of_local_day(date(2026, 11, 6), CO) == datetime(2026, 11, 7, 4, 59, 59, 999999, tzinfo=UTC)
    assert end_of_local_day(date(2026, 11, 6), 0) == datetime(2026, 11, 6, 23, 59, 59, 999999, tzinfo=UTC)


def test_vencimiento_cuenta_desde_el_dia_local_de_la_venta():
    # Venta a las 22:00 del 5 nov en Colombia (03:00 UTC del 6): el plazo cuenta desde el 5.
    sale = datetime(2026, 11, 6, 3, 0, tzinfo=UTC)
    assert due_date_from(sale, 7, CO) == end_of_local_day(date(2026, 11, 12), CO)
    assert due_date_from(sale, 0, CO) == end_of_local_day(date(2026, 11, 5), CO)
    assert due_date_from("2026-11-06T03:00:00Z", 7, CO) == end_of_local_day(date(2026, 11, 12), CO)   # texto antiguo


def test_plazo_del_cliente_o_el_general():
    settings = {"default_term_days": 7}
    assert term_for_client({"credit_days": 30}, settings) == 30
    assert term_for_client({"credit_days": 0}, settings) == 0          # 0 = contado a fin del día, NO el general
    assert term_for_client({"credit_days": None}, settings) == 7
    assert term_for_client({}, settings) == 7


@pytest.mark.parametrize("term, soon, message", [
    (-1, 5, f"El plazo de crédito debe estar entre 0 y {MAX_TERM_DAYS} días."),
    (MAX_TERM_DAYS + 1, 5, f"El plazo de crédito debe estar entre 0 y {MAX_TERM_DAYS} días."),
    (7, -1, "Los días para «Por vencer» deben estar entre 0 y 365."),
    (7, 366, "Los días para «Por vencer» deben estar entre 0 y 365."),
])
def test_configuracion_invalida(term, soon, message):
    with pytest.raises(BusinessError) as e:
        validate_settings(term, soon)
    assert e.value.message == message


def test_configuracion_valida_en_los_limites():
    validate_settings(0, 0)
    validate_settings(MAX_TERM_DAYS, 365)


def test_fecha_de_vencimiento_escrita():
    today = local_today(CO)
    assert parse_due_date(today.isoformat(), CO) == end_of_local_day(today, CO)
    assert parse_due_date(f" {today.isoformat()}T10:00 ", CO) == end_of_local_day(today, CO)
    with pytest.raises(BusinessError, match="no puede ser anterior a hoy"):
        parse_due_date((today - timedelta(days=1)).isoformat(), CO)
    with pytest.raises(BusinessError, match="demasiado lejana"):
        parse_due_date((today + timedelta(days=MAX_TERM_DAYS + 1)).isoformat(), CO)
    for bad in ("2026-13-01", "mañana", None):
        with pytest.raises(BusinessError, match="usa AAAA-MM-DD"):
            parse_due_date(bad, CO)


# Ahora: 6 nov 10:00 en Colombia (15:00 UTC).
NOW = datetime(2026, 11, 6, 15, 0, tzinfo=UTC)


@pytest.mark.parametrize("due_day, soon, status, label, left", [
    (date(2026, 11, 6), 5, "due_soon", "Vence hoy", 0),
    (date(2026, 11, 7), 5, "due_soon", "Vence mañana", 1),
    (date(2026, 11, 10), 5, "due_soon", "Vence en 4 días", 4),
    (date(2026, 11, 10), 3, "current", "Al día", 4),
    (date(2026, 11, 6), 0, "due_soon", "Vence hoy", 0),
])
def test_estado_de_una_factura_no_vencida(due_day, soon, status, label, left):
    s = invoice_status(end_of_local_day(due_day, CO), soon, now=NOW)
    assert (s["credit_status"], s["credit_status_label"], s["days_left"], s["days_overdue"]) == (status, label, left, 0)


def test_estado_de_una_factura_vencida():
    due = end_of_local_day(date(2026, 11, 5), CO)          # venció anoche (fin del 5 nov)
    s = invoice_status(due, 5, now=due + timedelta(seconds=1))
    assert (s["credit_status"], s["credit_status_label"], s["days_overdue"]) == ("overdue", "Vencida hace 1 día", 1)
    s = invoice_status(due, 5, now=due + timedelta(days=1, seconds=1))
    assert s["credit_status_label"] == "Vencida hace 2 días" and s["days_overdue"] == 2
    assert invoice_status(due.isoformat(), 5, now=NOW)["credit_status"] == "overdue"   # fecha como texto


def test_factura_sin_vencimiento():
    assert invoice_status(None, 5, now=NOW) == {"credit_status": "current", "credit_status_label": "Sin vencimiento",
                                                "days_overdue": 0, "days_left": None}
    assert invoice_status("no es fecha", 5, now=NOW)["credit_status_label"] == "Sin vencimiento"
