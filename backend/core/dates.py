"""Fechas nativas (backlog P1.19).

Todas las fechas se guardan como `datetime` de MongoDB en UTC (antes: texto ISO). El cliente
de Mongo se abre con `tz_aware=True`, así que al leer vuelven con zona horaria y la API las
entrega como hoy ("2026-11-04T15:30:00+00:00"): el frontend no cambia.

- `now_utc()`     → fecha/hora actual para guardar.
- `as_datetime()` → acepta texto ISO (datos antiguos) o datetime y devuelve datetime con zona.
- `migrate_text_dates()` → al arrancar convierte a fecha nativa las fechas guardadas como texto.
"""
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger("boltrex")

# Campos de fecha que pueden haber quedado como texto en datos antiguos.
DATE_FIELDS = ("created_at", "updated_at", "effective_date")
# Colecciones que ya nacieron con fechas nativas (no hace falta revisarlas).
NATIVE_COLLECTIONS = {"audit_log", "sessions", "login_attempts"}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def parse_date_text(value: str) -> Optional[datetime]:
    """Texto de fecha en los formatos que ha usado el sistema → datetime UTC; None si no se entiende.

    Acepta ISO con o sin microsegundos, con 'Z' o desfase (+00:00, -05:00), con espacio en vez
    de 'T', y fecha sola (AAAA-MM-DD). Sin zona se asume UTC (así se guardaban)."""
    text = (value or "").strip()
    if not text:
        return None
    text = re.sub(r"Z$", "+00:00", text)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        text += "T00:00:00"
    try:
        dt = datetime.fromisoformat(text.replace(" ", "T", 1))
    except ValueError:
        return None
    return _aware(dt).astimezone(timezone.utc)


def as_datetime(value: Any) -> Any:
    """datetime con zona a partir de datetime o texto ISO; otros valores se devuelven igual."""
    if isinstance(value, datetime):
        return _aware(value)
    if isinstance(value, str):
        parsed = parse_date_text(value)
        return parsed if parsed is not None else value
    return value


async def migrate_text_dates(database) -> Dict[str, Any]:
    """Convierte a fecha nativa las fechas guardadas como texto, en todas las colecciones.

    Idempotente (solo toca valores de tipo texto) y reanudable. Lo que no se puede interpretar
    se deja como estaba y se informa en el log. Nunca impide el arranque."""
    report: Dict[str, Any] = {"converted": 0, "unparseable": [], "by_collection": {}}
    try:
        names = await database.list_collection_names()
        for name in sorted(n for n in names if n not in NATIVE_COLLECTIONS and not n.startswith("system.")):
            coll = database[name]
            for field in DATE_FIELDS:
                cursor = coll.find({field: {"$type": "string"}}, {field: 1})
                batch = []
                async for doc in cursor:
                    parsed = parse_date_text(doc.get(field))
                    if parsed is None:
                        report["unparseable"].append(f"{name}.{field}={doc.get(field)!r} (_id {doc['_id']})")
                        continue
                    batch.append((doc["_id"], parsed))
                    if len(batch) >= 500:
                        report["converted"] += await _apply(coll, field, batch)
                        batch = []
                if batch:
                    report["converted"] += await _apply(coll, field, batch)
                done = report["converted"] - sum(report["by_collection"].values())
                if done:
                    report["by_collection"][f"{name}.{field}"] = done
        if report["converted"]:
            logger.info("Fechas convertidas de texto a fecha nativa: %d (%s)", report["converted"],
                        ", ".join(f"{k}: {v}" for k, v in report["by_collection"].items()))
        if report["unparseable"]:
            logger.warning("Fechas en texto que no se pudieron interpretar (se dejaron igual): %s",
                           "; ".join(report["unparseable"][:20]))
    except Exception as exc:  # pragma: no cover - solo registro
        logger.error("No se pudo completar la conversión de fechas: %s", exc)
    return report


async def _apply(coll, field: str, batch) -> int:
    from pymongo import UpdateOne
    # El filtro exige que siga siendo texto: si otra petición ya lo cambió, no se pisa.
    ops = [UpdateOne({"_id": _id, field: {"$type": "string"}}, {"$set": {field: value}}) for _id, value in batch]
    result = await coll.bulk_write(ops, ordered=False)
    return result.modified_count
