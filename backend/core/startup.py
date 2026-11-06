"""Tareas de arranque del backend, en orden (mantenimiento fase 2: `lifespan` en vez de `on_event`).

Cada tarea es idempotente y NUNCA impide el arranque: si una falla, se registra en el log y se sigue
con la siguiente (antes, una excepción en una tarea cortaba las que venían después).
Para agregar una tarea nueva: añadirla a STARTUP_TASKS en el lugar que le corresponde.
"""
import logging
import time
from typing import Awaitable, Callable, List, Tuple

logger = logging.getLogger("boltrex")


def _tasks() -> List[Tuple[str, Callable[[], Awaitable]]]:
    from core.adjustments import ensure_default_reasons
    from core.clients import backfill_invoice_document_types
    from core.credit import backfill_due_dates
    from core.database import db
    from core.dates import migrate_text_dates
    from core.indexes import ensure_indexes
    from core.modules_sync import ensure_new_modules
    from core.pricing import warn_products_without_price
    from core.security import flag_default_passwords
    return [
        # P1.19: fechas guardadas como texto → fecha nativa (antes de todo lo demás).
        ("fechas en texto → nativas", lambda: migrate_text_dates(db)),
        # Índices únicos y de rendimiento; si hay duplicados lo informa en el log.
        ("índices", ensure_indexes),
        # P1.10: administradores con contraseña por defecto → cambio obligatorio al entrar.
        ("contraseñas por defecto", lambda: flag_default_passwords(db)),
        # P1.15: tipo de documento del cliente en facturas antiguas (solo cuando no es ambiguo).
        ("tipo de documento en facturas antiguas", backfill_invoice_document_types),
        # P1.17: productos sin precio 'default' no se pueden vender: aviso en el log.
        ("productos sin precio default", warn_products_without_price),
        # P2.31: módulos RBAC nuevos y sus permisos por defecto en bases existentes.
        ("módulos nuevos", ensure_new_modules),
        # P2.30: facturas a crédito antiguas sin vencimiento → fecha de venta + plazo.
        ("vencimientos de créditos antiguos", backfill_due_dates),
        # P2.32: motivos de ajuste por defecto (si el catálogo está vacío).
        ("motivos de ajuste por defecto", ensure_default_reasons),
    ]


STARTUP_TASK_NAMES = [name for name, _ in _tasks()]


async def run_startup_tasks() -> List[str]:
    """Ejecuta las tareas en orden. Devuelve los nombres de las que fallaron."""
    failed = []
    start = time.monotonic()
    for name, task in _tasks():
        t0 = time.monotonic()
        try:
            await task()
        except Exception as exc:  # pragma: no cover - cada tarea ya maneja sus errores esperados
            failed.append(name)
            logger.error("Tarea de arranque «%s» falló (el backend sigue): %s", name, exc)
        else:
            elapsed = time.monotonic() - t0
            if elapsed > 2:
                logger.info("Tarea de arranque «%s» tardó %.1f s", name, elapsed)
    logger.info("Arranque listo en %.1f s%s", time.monotonic() - start,
                f" ({len(failed)} tarea(s) con error: {', '.join(failed)})" if failed else "")
    return failed
