"""Cartera / cuentas por cobrar con vencimientos (backlog P2.30).

Decisiones del usuario:
- Plazo por defecto PARAMETRIZABLE en Config. Sistema (inicial: 7 días); cada cliente puede
  tener su propio plazo (`clients.credit_days`); en el POS se puede cambiar la fecha de esa venta.
- "Por vencer" = vence en los próximos N días, PARAMETRIZABLE (inicial: 5).
- Cliente con facturas vencidas: el POS solo AVISA (opción A), no bloquea.
- Cupo de crédito por cliente (`clients.credit_limit`; vacío/0 = sin límite): una venta a crédito
  que lo supere se rechaza con el motivo.

Vencimiento (`invoices.due_date`): fin del día local de vencimiento, guardado en UTC. Una factura
está vencida cuando ya pasó ese instante; los días de atraso cuentan desde el día siguiente.
Tramos de antigüedad por días de atraso: al día · 1–30 · 31–60 · 61–90 · +90.
"""
import logging
import math
from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, Optional

from core.errors import BusinessError

from core.config import settings
from core.database import db
from core.dates import as_datetime, now_utc
from core.money import money

logger = logging.getLogger("boltrex")

SETTINGS_ID = "credit"
DEFAULT_SETTINGS = {"default_term_days": 7, "due_soon_days": 5}
MAX_TERM_DAYS = 3650
# Zona del negocio para cálculos del servidor sin navegador (p. ej. al arrancar): Colombia = 300.
BUSINESS_TZ_OFFSET_MINUTES = settings.business_tz_offset_minutes

DAY_MS = 86_400_000
BUCKETS = [
    ("current", "Al día", None, 0),
    ("1_30", "1–30 días", 1, 30),
    ("31_60", "31–60 días", 31, 60),
    ("61_90", "61–90 días", 61, 90),
    ("90_plus", "+90 días", 91, None),
]
BUCKET_LABELS = {k: label for k, label, _, _ in BUCKETS}


# ---------------------------------------------------------------- configuración

async def get_settings() -> Dict:
    doc = await db.system_settings.find_one({"_id": SETTINGS_ID}, {"_id": 0, "updated_at": 0, "updated_by": 0})
    return {**DEFAULT_SETTINGS, **(doc or {})}


def validate_settings(default_term_days: int, due_soon_days: int) -> None:
    if default_term_days < 0 or default_term_days > MAX_TERM_DAYS:
        raise BusinessError(f"El plazo de crédito debe estar entre 0 y {MAX_TERM_DAYS} días.")
    if due_soon_days < 0 or due_soon_days > 365:
        raise BusinessError("Los días para «Por vencer» deben estar entre 0 y 365.")


async def set_settings(default_term_days: int, due_soon_days: int, actor: str) -> Dict:
    validate_settings(default_term_days, due_soon_days)
    await db.system_settings.update_one(
        {"_id": SETTINGS_ID},
        {"$set": {"default_term_days": int(default_term_days), "due_soon_days": int(due_soon_days),
                  "updated_at": now_utc(), "updated_by": actor}},
        upsert=True,
    )
    return await get_settings()


# ---------------------------------------------------------------- fechas

def local_today(offset_minutes: int) -> date:
    return (now_utc() - timedelta(minutes=offset_minutes)).date()


def end_of_local_day(d: date, offset_minutes: int) -> datetime:
    """Último instante del día local `d`, expresado en UTC."""
    return datetime.combine(d, time.max, tzinfo=timezone.utc) + timedelta(minutes=offset_minutes)


def due_date_from(sale_at: datetime, term_days: int, offset_minutes: int) -> datetime:
    sale_local = (as_datetime(sale_at) - timedelta(minutes=offset_minutes)).date()
    return end_of_local_day(sale_local + timedelta(days=int(term_days)), offset_minutes)


def parse_due_date(value: str, offset_minutes: int) -> datetime:
    try:
        d = datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
    except (ValueError, AttributeError):
        raise BusinessError(f"Fecha de vencimiento inválida '{value}': usa AAAA-MM-DD.")
    today = local_today(offset_minutes)
    if d < today:
        raise BusinessError("La fecha de vencimiento no puede ser anterior a hoy.")
    if d > today + timedelta(days=MAX_TERM_DAYS):
        raise BusinessError("La fecha de vencimiento es demasiado lejana (máximo 10 años).")
    return end_of_local_day(d, offset_minutes)


def term_for_client(client: dict, settings: Dict) -> int:
    days = client.get("credit_days")
    return int(days) if days is not None else int(settings["default_term_days"])


def invoice_status(due_date, due_soon_days: int, now: Optional[datetime] = None) -> Dict:
    """Estado de una factura pendiente: al día / por vencer / vencida (con días de atraso)."""
    now = now or now_utc()
    due = as_datetime(due_date) if due_date else None
    if not isinstance(due, datetime):
        return {"credit_status": "current", "credit_status_label": "Sin vencimiento", "days_overdue": 0, "days_left": None}
    if now > due:
        days = math.ceil((now - due).total_seconds() / 86400)
        return {"credit_status": "overdue", "credit_status_label": f"Vencida hace {days} día{'s' if days != 1 else ''}",
                "days_overdue": days, "days_left": None}
    # Días calendario que faltan: 0 = vence hoy (el vencimiento es el fin del día local).
    left = math.ceil((due - now).total_seconds() / 86400) - 1
    if left <= due_soon_days:
        label = "Vence hoy" if left == 0 else ("Vence mañana" if left == 1 else f"Vence en {left} días")
        return {"credit_status": "due_soon", "credit_status_label": label, "days_overdue": 0, "days_left": left}
    return {"credit_status": "current", "credit_status_label": "Al día", "days_overdue": 0, "days_left": left}


# ---------------------------------------------------------------- agregaciones de antigüedad

def overdue_stages(now: datetime) -> list:
    """Etapas que añaden a cada factura `_od` (días de atraso) y `_bucket` (tramo)."""
    od = {"$cond": [
        {"$and": [{"$ne": [{"$ifNull": ["$due_date", None]}, None]}, {"$gt": [now, "$due_date"]}]},
        {"$ceil": {"$divide": [{"$subtract": [now, "$due_date"]}, DAY_MS]}},
        0,
    ]}
    branches = [{"case": {"$lte": ["$_od", 0]}, "then": "current"},
                {"case": {"$lte": ["$_od", 30]}, "then": "1_30"},
                {"case": {"$lte": ["$_od", 60]}, "then": "31_60"},
                {"case": {"$lte": ["$_od", 90]}, "then": "61_90"}]
    return [{"$addFields": {"_od": od}}, {"$addFields": {"_bucket": {"$switch": {"branches": branches, "default": "90_plus"}}}}]


def due_soon_expr(now: datetime, due_soon_days: int) -> dict:
    """Factura no vencida que vence dentro de `due_soon_days` días calendario (0 = hoy)."""
    return {"$and": [{"$lte": ["$_od", 0]}, {"$ne": [{"$ifNull": ["$due_date", None]}, None]},
                     {"$lte": [{"$subtract": ["$due_date", now]}, (due_soon_days + 1) * DAY_MS]}]}


def pending_match(seller: Optional[str] = None) -> dict:
    m = {"payment_status": "por_cobrar", "balance": {"$gt": 0}}
    if seller:
        m["created_by"] = seller
    return m


async def aging_summary(seller: Optional[str] = None, settings: Optional[Dict] = None) -> Dict:
    now = now_utc()
    settings = settings or await get_settings()
    rows = await db.invoices.aggregate([
        {"$match": pending_match(seller)}, *overdue_stages(now),
        {"$group": {"_id": "$_bucket", "balance": {"$sum": "$balance"}, "invoices": {"$sum": 1},
                    "soon_balance": {"$sum": {"$cond": [due_soon_expr(now, settings["due_soon_days"]), "$balance", 0]}},
                    "soon_invoices": {"$sum": {"$cond": [due_soon_expr(now, settings["due_soon_days"]), 1, 0]}}}},
    ]).to_list(None)
    by = {r["_id"]: r for r in rows}
    soon = by.get("current", {})
    buckets = [{"key": k, "label": label, "balance": round(by.get(k, {}).get("balance", 0) or 0, 2),
                "invoices": by.get(k, {}).get("invoices", 0)} for k, label, _, _ in BUCKETS]
    overdue = [b for b in buckets if b["key"] != "current"]
    clients = await db.invoices.aggregate([
        {"$match": pending_match(seller)}, *overdue_stages(now), {"$match": {"_od": {"$gt": 0}}},
        {"$group": {"_id": {"d": "$client_document", "t": "$client_document_type"}}}, {"$count": "n"},
    ]).to_list(1)
    return {
        "buckets": buckets,
        "total_balance": round(sum(b["balance"] for b in buckets), 2),
        "overdue_balance": round(sum(b["balance"] for b in overdue), 2),
        "overdue_invoices": sum(b["invoices"] for b in overdue),
        "overdue_clients": clients[0]["n"] if clients else 0,
        "due_soon_balance": round(soon.get("soon_balance", 0) or 0, 2),
        "due_soon_invoices": soon.get("soon_invoices", 0) or 0,
        "due_soon_days": settings["due_soon_days"],
    }


async def client_credit_status(document_number: str, document_type: Optional[str]) -> Dict:
    """Saldo, vencido y cupo de un cliente (para el aviso del POS y la validación del cupo)."""
    from repositories.clients import invoices_of_client_query, resolve_client
    client = await resolve_client(document_number, document_type)
    settings = await get_settings()
    now = now_utc()
    rows = await db.invoices.aggregate([
        {"$match": {**invoices_of_client_query(client), **pending_match()}}, *overdue_stages(now),
        {"$group": {"_id": None, "balance": {"$sum": "$balance"},
                    "overdue": {"$sum": {"$cond": [{"$gt": ["$_od", 0]}, "$balance", 0]}},
                    "overdue_invoices": {"$sum": {"$cond": [{"$gt": ["$_od", 0]}, 1, 0]}},
                    "max_days": {"$max": "$_od"}}},
    ]).to_list(1)
    r = rows[0] if rows else {}
    limit = float(client.get("credit_limit") or 0)
    balance = round(r.get("balance", 0) or 0, 2)
    return {
        "client_name": f"{client.get('first_name', '')} {client.get('last_name', '')}".strip(),
        "balance": balance,
        "overdue_balance": round(r.get("overdue", 0) or 0, 2),
        "overdue_invoices": r.get("overdue_invoices", 0) or 0,
        "max_days_overdue": int(r.get("max_days", 0) or 0),
        "credit_limit": limit or None,
        "available": round(limit - balance, 2) if limit else None,
        "term_days": term_for_client(client, settings),
        "default_term_days": settings["default_term_days"],
    }


async def check_credit_limit(client: dict, new_total: float, session=None) -> None:
    """Rechaza una venta a crédito que supere el cupo del cliente (si tiene cupo)."""
    from repositories.clients import invoices_of_client_query
    limit = float(client.get("credit_limit") or 0)
    if not limit:
        return
    rows = await db.invoices.aggregate([
        {"$match": {**invoices_of_client_query(client), **pending_match()}},
        {"$group": {"_id": None, "balance": {"$sum": "$balance"}}},
    ], session=session).to_list(1)
    balance = float(rows[0]["balance"]) if rows else 0.0
    if balance + new_total - limit > 0.005:
        fmt = money
        name = f"{client.get('first_name', '')} {client.get('last_name', '')}".strip()
        raise BusinessError(f"La venta supera el cupo de crédito de {name}: debe {fmt(balance)}, esta venta es de {fmt(new_total)} "
                   f"y el cupo es {fmt(limit)} (disponible {fmt(max(0.0, limit - balance))}). Véndele de contado o pide "
                   f"a un administrador que amplíe el cupo.")


# ---------------------------------------------------------------- arranque

async def backfill_due_dates() -> int:
    """Facturas a crédito sin vencimiento (anteriores a P2.30): fecha de venta + plazo del cliente o el
    plazo por defecto. Nunca impide el arranque."""
    updated = 0
    try:
        settings = await get_settings()
        cursor = db.invoices.find({"payment_status": "por_cobrar", "due_date": {"$exists": False}},
                                  {"invoice_number": 1, "created_at": 1, "client_document": 1, "client_document_type": 1})
        async for inv in cursor:
            client = await db.clients.find_one({"document_number": inv.get("client_document"),
                                                **({"document_type": inv["client_document_type"]} if inv.get("client_document_type") else {})},
                                               {"credit_days": 1}) or {}
            term = term_for_client(client, settings)
            created = as_datetime(inv.get("created_at")) if inv.get("created_at") else now_utc()
            due = due_date_from(created if isinstance(created, datetime) else now_utc(), term, BUSINESS_TZ_OFFSET_MINUTES)
            await db.invoices.update_one({"_id": inv["_id"]}, {"$set": {"due_date": due, "credit_term_days": term}})
            updated += 1
        if updated:
            logger.info("Facturas a crédito antiguas: se calculó el vencimiento de %d factura(s).", updated)
    except Exception as exc:  # pragma: no cover
        logger.error("No se pudo calcular el vencimiento de facturas antiguas: %s", exc)
    return updated
