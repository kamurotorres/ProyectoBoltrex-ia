"""Reglas sueltas de core/: alertas de stock (P2.34), contadores, configuración (fase 2), errores de dominio
(fase 2), índices únicos y protección del rol Administrador."""
import asyncio
import json

import pytest
from fastapi import FastAPI
from pymongo.errors import DuplicateKeyError

from core import config
from core.alerts import effective_min, low_stock_expr, low_stock_filter, stock_status
from core.counters import _parse
from core.errors import BusinessError, ConflictError, DomainError, ForbiddenError, NotFoundError, register_error_handlers
from core.indexes import duplicate_key_message
from core.user_protection import ADMIN_ROLE, check_role_delete, check_role_update


# ---------------------------------------------------------------- stock mínimo
@pytest.mark.parametrize("product, threshold, minimum, status", [
    ({"stock": 0}, 10, 10, "out"),
    ({"stock": -2}, 10, 10, "out"),
    ({}, 10, 10, "out"),
    ({"stock": 9}, 10, 10, "low"),
    ({"stock": 10}, 10, 10, "ok"),                          # «bajo» es MENOS que el mínimo
    ({"stock": 3, "min_stock": 2}, 10, 2, "ok"),            # el mínimo propio manda sobre el general
    ({"stock": 1, "min_stock": 0}, 10, 0, "ok"),            # 0 = nunca avisa (no es «vacío»)
    ({"stock": 4, "min_stock": None}, 5, 5, "low"),         # null = usa el general
])
def test_estado_del_stock(product, threshold, minimum, status):
    assert effective_min(product, threshold) == minimum
    assert stock_status(product, threshold) == status


def test_consulta_de_bajo_stock_usa_el_minimo_de_cada_producto():
    assert low_stock_expr(10) == {"$lt": [{"$ifNull": ["$stock", 0]}, {"$ifNull": ["$min_stock", 10]}]}
    assert low_stock_filter(7) == {"$expr": low_stock_expr(7)}


def test_numero_de_consecutivo():
    assert _parse("INV-000123") == 123 and _parse("AJU-000001") == 1
    assert _parse("raro") == 0 and _parse(None) == 0 and _parse("") == 0


# ---------------------------------------------------------------- configuración desde variables de entorno
def test_configuracion_por_defecto(monkeypatch):
    for name in ("LOGIN_MAX_ATTEMPTS", "SESSION_IDLE_MINUTES", "SESSION_WARNING_MINUTES", "ALLOW_PUBLIC_REGISTRATION",
                 "CORS_ORIGINS", "AUDIT_RETENTION_DAYS"):
        monkeypatch.delenv(name, raising=False)
    s = config.load_settings()
    assert (s.login_max_attempts, s.session_idle_minutes, s.session_warning_minutes) == (5, 60, 5)
    assert s.allow_public_registration is False and s.cors_origins == ("http://localhost:3000",)
    assert s.audit_retention_days == 180 and s.problems == ()
    assert "clave-solo-para-pruebas" not in s.summary()          # el resumen del log nunca muestra secretos
    assert not s.uses_default_secret


def test_configuracion_invalida_usa_el_valor_por_defecto_y_avisa(monkeypatch):
    monkeypatch.setenv("LOGIN_MAX_ATTEMPTS", "cinco")
    monkeypatch.setenv("SESSION_IDLE_MINUTES", "0")
    monkeypatch.setenv("AUDIT_RETENTION_DAYS", "-1")
    s = config.load_settings()
    assert s.login_max_attempts == 5 and s.session_idle_minutes == 60 and s.audit_retention_days == 180
    assert set(s.problems) == {"LOGIN_MAX_ATTEMPTS='cinco' no es un número: se usa 5.",
                               "SESSION_IDLE_MINUTES='0' debe ser mayor que 0: se usa 60.",
                               "AUDIT_RETENTION_DAYS='-1' debe ser mayor o igual a 0: se usa 180."}


def test_configuracion_personalizada(monkeypatch):
    monkeypatch.setenv("SESSION_IDLE_MINUTES", "6")
    monkeypatch.setenv("SESSION_WARNING_MINUTES", "5")             # más de la mitad: se limita a 3
    monkeypatch.setenv("ALLOW_PUBLIC_REGISTRATION", "Sí")
    monkeypatch.setenv("CORS_ORIGINS", " https://boltrex.online , ,http://localhost:3000")
    s = config.load_settings()
    assert s.session_warning_minutes == 3 and s.session_touch_seconds == 36
    assert s.allow_public_registration is True
    assert s.cors_origins == ("https://boltrex.online", "http://localhost:3000")


# ---------------------------------------------------------------- errores de dominio → respuesta HTTP
@pytest.mark.parametrize("error, code", [(BusinessError, 400), (ForbiddenError, 403), (NotFoundError, 404), (ConflictError, 409)])
def test_codigo_http_de_cada_error(error, code):
    e = error("mensaje")
    assert isinstance(e, DomainError) and e.status_code == code and e.message == e.detail == "mensaje" and str(e) == "mensaje"
    assert BusinessError("x", status_code=422).status_code == 422


def _handle(exc):
    app = FastAPI()
    register_error_handlers(app)
    handler = app.exception_handlers[DomainError if isinstance(exc, DomainError) else type(exc)]
    response = asyncio.run(handler(None, exc))
    return response.status_code, json.loads(response.body)


def test_manejador_global_responde_detail_en_espanol():
    assert _handle(NotFoundError("Factura no encontrada")) == (404, {"detail": "Factura no encontrada"})
    assert _handle(ConflictError("El stock cambió")) == (409, {"detail": "El stock cambió"})


def test_duplicado_de_mongo_es_400_con_mensaje_claro():
    exc = DuplicateKeyError("E11000 duplicate key error collection: boltrex.products index: uniq_products_barcode",
                            11000, {"errmsg": "E11000 duplicate key error index: uniq_products_barcode dup key",
                                    "keyValue": {"barcode": "770123"}})
    assert _handle(exc) == (400, {"detail": "Ya existe un producto con el código de barras '770123'"})
    unknown = DuplicateKeyError("E11000", 11000, {"errmsg": "index: otro_indice", "keyValue": {"a": 1}})
    assert duplicate_key_message(unknown) == "Ya existe un registro con esos datos (a=1)"
    assert duplicate_key_message(DuplicateKeyError("E11000", 11000, {})) == "Ya existe un registro con esos datos"


# ---------------------------------------------------------------- rol Administrador
def test_el_rol_administrador_no_se_desactiva_ni_se_borra():
    with pytest.raises(BusinessError, match="siempre tiene acceso total"):
        check_role_update(ADMIN_ROLE, {"is_active": False})
    with pytest.raises(BusinessError, match="siempre tiene acceso total"):
        check_role_delete(ADMIN_ROLE)
    check_role_update(ADMIN_ROLE, {"description": "otra"})        # otros cambios sí
    check_role_update("Cajero", {"is_active": False})
    check_role_delete("Cajero")
