"""Ajustes de inventario (backlog P2.32).

Decisiones del usuario:
- Solo el Administrador ajusta por defecto (permiso `inventory` → crear); se puede dar a otro rol en Roles.
- Los motivos son un catálogo propio («Motivos de ajuste», como Categorías), cada uno dice a qué tipos
  aplica (entrada / salida / conteo) y si exige observación.
- Sin aprobación. Las pérdidas por ajustes se muestran aparte (no tocan la ganancia de ventas).

Tipos: entrada (suma) · salida (resta; nunca deja stock negativo) · conteo físico (deja el stock en lo
contado; si el stock cambió mientras se contaba, se pide volver a contar). Un ajuste no se edita ni se
borra: los errores se corrigen con otro ajuste. Valor = diferencia × precio de compra del momento.
"""
import logging

from core.counters import Counter
from core.database import db
from core.dates import now_utc

logger = logging.getLogger("boltrex")

ADJUSTMENT_COUNTER = Counter("adjustment_id", "AJU", "inventory_adjustments", "adjustment_number")
KINDS = {"entrada": "Entrada", "salida": "Salida", "conteo": "Conteo físico"}
MAX_ITEMS = 500

DEFAULT_REASONS = [
    ("Inventario inicial", "Stock con el que arranca un producto", ["entrada"], False),
    ("Sobrante encontrado", "Mercancía que apareció y no estaba en el sistema", ["entrada", "conteo"], False),
    ("Corrección", "Corregir un error de registro", ["entrada", "salida", "conteo"], True),
    ("Merma", "Pérdida natural del producto", ["salida", "conteo"], False),
    ("Daño", "Producto dañado o roto", ["salida"], False),
    ("Vencido", "Producto vencido", ["salida"], False),
    ("Consumo interno", "Usado por el negocio", ["salida"], False),
    ("Robo o pérdida", "Faltante sin explicación", ["salida", "conteo"], False),
    ("Conteo físico periódico", "Conteo programado del inventario", ["conteo"], False),
    ("Otro", "Cualquier otro motivo (explicar en la observación)", ["entrada", "salida", "conteo"], True),
]


async def ensure_default_reasons() -> int:
    """Crea los motivos por defecto si el catálogo está vacío (arranque y factory reset)."""
    try:
        if await db.adjustment_reasons.count_documents({}):
            return 0
        now = now_utc()
        await db.adjustment_reasons.insert_many([
            {"name": n, "description": d, "applies_to": a, "requires_note": r, "is_active": True, "created_at": now}
            for n, d, a, r in DEFAULT_REASONS
        ])
        logger.info("Motivos de ajuste de inventario creados por defecto: %d", len(DEFAULT_REASONS))
        return len(DEFAULT_REASONS)
    except Exception as exc:  # pragma: no cover
        logger.error("No se pudieron crear los motivos de ajuste por defecto: %s", exc)
        return 0
