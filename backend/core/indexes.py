"""Índices de MongoDB: unicidad garantizada por la base de datos y consultas rápidas.

- `ensure_indexes()` se ejecuta al arrancar el backend (ver main.py). Es idempotente.
- Si una colección YA tiene datos duplicados, ese índice único no se puede crear: el backend
  NO se cae, registra en el log qué valores están duplicados y sigue arrancando. Al corregir
  los datos y reiniciar, el índice se crea.
- `duplicate_key_message()` traduce un DuplicateKeyError (cuando la base rechaza un duplicado,
  p. ej. dos peticiones simultáneas) a un mensaje en español para el usuario.

Al añadir una colección con clave natural nueva, declarar aquí su índice único y su mensaje.
"""
import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError, OperationFailure

from core.database import db
from core.config import AUDIT_RETENTION_DAYS

logger = logging.getLogger("boltrex")


@dataclass(frozen=True)
class IndexSpec:
    collection: str
    keys: Tuple[Tuple[str, int], ...]
    name: str
    unique: bool = False
    # Mensaje para el usuario si la base rechaza un duplicado. Se formatea con los valores
    # del documento duplicado ({barcode}, {email}, ...).
    message: Optional[str] = None
    # Índice TTL: MongoDB borra el documento cuando pasa la fecha del campo (expireAfterSeconds=0).
    # Va al final y se pasa siempre por nombre (si se intercala, los argumentos posicionales se corren).
    ttl: bool = False
    # TTL relativo: MongoDB borra el documento cuando el campo tiene más de ttl_seconds de antigüedad.
    ttl_seconds: Optional[int] = None


def _u(collection: str, fields: List[str], message: str) -> IndexSpec:
    return IndexSpec(collection=collection, keys=tuple((f, ASCENDING) for f in fields),
                     name=f"uniq_{collection}_{'_'.join(f.replace('.', '_') for f in fields)}",
                     unique=True, message=message)


def _i(collection: str, keys: List[Tuple[str, int]]) -> IndexSpec:
    return IndexSpec(collection=collection, keys=tuple(keys),
                     name=f"idx_{collection}_{'_'.join(k.replace('.', '_') for k, _ in keys)}")


INDEXES: List[IndexSpec] = [
    # ---- Unicidad (claves naturales) ----
    _u("products", ["barcode"], "Ya existe un producto con el código de barras '{barcode}'"),
    _u("clients", ["document_type", "document_number"], "Ya existe un cliente con el documento {document_type} {document_number}"),
    _u("users_extended", ["email"], "Ya existe un usuario con el email '{email}'"),
    _u("users", ["email"], "Ya existe un usuario con el email '{email}'"),
    _u("invoices", ["invoice_number"], "El número de factura {invoice_number} ya existe. Intenta registrar la venta de nuevo."),
    _u("purchases", ["purchase_number"], "El número de compra {purchase_number} ya existe. Intenta registrar la compra de nuevo."),
    _u("fio_payments", ["payment_id"], "Conflicto al generar el número del abono. Intenta registrarlo de nuevo."),
    _u("categories", ["name"], "Ya existe una categoría llamada '{name}'"),
    _u("price_lists", ["name"], "Ya existe una lista de precios llamada '{name}'"),
    _u("suppliers", ["name"], "Ya existe un proveedor llamado '{name}'"),
    _u("payment_methods", ["name"], "Ya existe una forma de pago llamada '{name}'"),
    _u("document_types", ["code"], "Ya existe un tipo de documento con el código '{code}'"),
    _u("tax_rates", ["name"], "Ya existe una tarifa de IVA llamada '{name}'"),
    _u("roles", ["name"], "Ya existe un rol llamado '{name}'"),
    _u("system_modules", ["slug"], "Ya existe un módulo con el identificador '{slug}'"),
    _u("role_permissions", ["role_name", "module_slug"], "Ya existen permisos del rol '{role_name}' sobre el módulo '{module_slug}'"),
    # ---- Rendimiento (consultas frecuentes) ----
    _i("inventory_movements", [("barcode", ASCENDING), ("created_at", DESCENDING)]),
    _i("inventory_movements", [("created_at", DESCENDING)]),
    _i("invoices", [("created_at", DESCENDING)]),
    _i("invoices", [("client_document", ASCENDING)]),
    _i("invoices", [("payment_status", ASCENDING), ("balance", ASCENDING)]),
    _i("invoices", [("payment_method", ASCENDING)]),
    _i("returns", [("invoice_number", ASCENDING)]),
    _i("fio_payments", [("invoice_number", ASCENDING)]),
    _i("purchases", [("supplier_name", ASCENDING), ("status", ASCENDING)]),
    _i("products", [("category", ASCENDING)]),
    _i("products", [("prices.price_list_name", ASCENDING)]),
    _i("clients", [("document_number", ASCENDING)]),
    _i("clients", [("price_list", ASCENDING)]),
    # ---- Caducidad automática ----
    IndexSpec(collection="login_attempts", keys=(("expires_at", ASCENDING),), name="ttl_login_attempts_expires_at", ttl=True),
    # ---- Caja (P2.31) ----
    _u("cash_sessions", ["session_id"], "Ya existe una caja con el número {session_id}."),
    # open_key = email mientras la caja está abierta y = session_id al cerrarla: una sola abierta por cajero
    # (aunque lleguen dos aperturas a la vez).
    _u("cash_sessions", ["open_key"], "Ya tienes una caja abierta: ciérrala antes de abrir otra."),
    _i("cash_sessions", [("cashier_email", ASCENDING), ("opened_at", DESCENDING)]),
    _i("cash_movements", [("session_id", ASCENDING), ("created_at", ASCENDING)]),
    _i("cash_movements", [("created_by", ASCENDING), ("session_id", ASCENDING)]),
    # ---- Alertas (P2.34): lo «visto» por usuario ----
    _u("alerts_seen", ["email"], "Conflicto al guardar las alertas vistas. Intenta de nuevo."),
    _i("products", [("stock", ASCENDING)]),
    # ---- Ajustes de inventario (P2.32) ----
    _u("inventory_adjustments", ["adjustment_number"], "El número de ajuste {adjustment_number} ya existe. Intenta guardarlo de nuevo."),
    _u("adjustment_reasons", ["name"], "Ya existe un motivo de ajuste llamado '{name}'"),
    _i("inventory_adjustments", [("created_at", DESCENDING)]),
    _i("inventory_adjustments", [("reason", ASCENDING), ("created_at", DESCENDING)]),
    IndexSpec(collection="sessions", keys=(("expires_at", ASCENDING),), name="ttl_sessions_expires_at", ttl=True),
    _i("sessions", [("email", ASCENDING)]),
    # Bitácora de auditoría (P1.12): retención por AUDIT_RETENTION_DAYS (0 = índice normal, sin borrado).
    IndexSpec(collection="audit_log", keys=(("at", DESCENDING),), name="ttl_audit_log_at",
              ttl_seconds=AUDIT_RETENTION_DAYS * 86400 if AUDIT_RETENTION_DAYS > 0 else None),
    _i("audit_log", [("actor_email", ASCENDING), ("at", DESCENDING)]),
    _i("audit_log", [("module", ASCENDING), ("at", DESCENDING)]),
    _i("audit_log", [("entity_id", ASCENDING)]),
]

_BY_NAME: Dict[str, IndexSpec] = {spec.name: spec for spec in INDEXES}


@dataclass
class IndexReport:
    created_or_present: List[str] = field(default_factory=list)
    failed: Dict[str, str] = field(default_factory=dict)


async def _duplicates_sample(spec: IndexSpec, limit: int = 5) -> List[dict]:
    group_id = {k.replace(".", "_"): f"${k}" for k, _ in spec.keys}
    pipeline = [
        {"$group": {"_id": group_id, "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 1}}},
        {"$limit": limit},
    ]
    return await db[spec.collection].aggregate(pipeline).to_list(limit)


async def ensure_indexes() -> IndexReport:
    """Crea todos los índices declarados. Nunca lanza: los fallos se registran y se devuelven."""
    report = IndexReport()
    for spec in INDEXES:
        try:
            if spec.ttl:
                options = {"expireAfterSeconds": 0}
            elif spec.ttl_seconds:
                options = {"expireAfterSeconds": int(spec.ttl_seconds)}
            else:
                options = {}
            try:
                await db[spec.collection].create_index(list(spec.keys), name=spec.name, unique=spec.unique, **options)
            except OperationFailure as exc:
                # 85 IndexOptionsConflict / 86 IndexKeySpecsConflict: ya existe con otra definición
                # (p. ej. creado por una versión anterior). Se recrea con la definición actual.
                if getattr(exc, "code", None) not in (85, 86):
                    raise
                logger.warning("Índice %s existía con otra definición: se recrea.", spec.name)
                await db[spec.collection].drop_index(spec.name)
                await db[spec.collection].create_index(list(spec.keys), name=spec.name, unique=spec.unique, **options)
            report.created_or_present.append(spec.name)
        except (DuplicateKeyError, OperationFailure) as exc:
            if spec.unique and getattr(exc, "code", None) == 11000:
                sample = await _duplicates_sample(spec)
                reason = f"hay datos duplicados en '{spec.collection}', p. ej.: {sample}"
                logger.error(
                    "No se pudo crear el índice único %s: %s. Corrige los duplicados y reinicia el backend.",
                    spec.name, reason,
                )
            else:
                reason = str(exc)
                logger.error("No se pudo crear el índice %s: %s", spec.name, reason)
            report.failed[spec.name] = reason
    if report.failed:
        logger.warning("Índices: %d OK, %d con problemas: %s",
                       len(report.created_or_present), len(report.failed), ", ".join(report.failed))
    else:
        logger.info("Índices verificados: %d", len(report.created_or_present))
    return report


def duplicate_key_message(exc: DuplicateKeyError) -> str:
    """Mensaje en español para el usuario a partir de un DuplicateKeyError de MongoDB."""
    details = exc.details or {}
    values = {k.replace(".", "_"): v for k, v in (details.get("keyValue") or {}).items()}
    match = re.search(r"index: (\S+)", details.get("errmsg", "") or str(exc))
    spec = _BY_NAME.get(match.group(1)) if match else None
    if spec and spec.message:
        try:
            return spec.message.format(**values)
        except (KeyError, IndexError):
            pass
    shown = ", ".join(f"{k}={v}" for k, v in values.items())
    return f"Ya existe un registro con esos datos ({shown})" if shown else "Ya existe un registro con esos datos"
