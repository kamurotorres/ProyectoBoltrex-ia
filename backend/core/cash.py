"""Control de caja (backlog P2.31).

Decisiones del usuario:
- Interruptor "Exigir caja abierta para vender" (system_settings._id="cash"):
  activado  → ventas (incluso a crédito) y abonos exigen la caja abierta de quien los registra;
              una devolución que entrega efectivo también. Sin caja → 400 con el motivo.
  desactivado → se registran igual; sus movimientos quedan "pendientes" y se asocian a la
              PRÓXIMA caja que abra ese usuario.
- Una caja por cajero (como máximo una abierta a la vez).
- Devoluciones: de contado → reembolso en EFECTIVO desde la caja; a crédito → baja la deuda
  (no se mueve dinero); a crédito con abonos de más → el excedente se devuelve en efectivo
  (resuelve P1.40).
- Arqueo por denominaciones colombianas (opcional) o total contado.

Colecciones: cash_sessions (una por turno) y cash_movements (dinero que entra/sale de un turno).
El efectivo esperado = base + entradas en efectivo − salidas en efectivo.
"""
from typing import Dict, List, Optional

from core.errors import BusinessError

from core.counters import Counter
from core.database import db
from repositories import cash as cash_repo
from core.dates import now_utc

CASH_METHOD = "Efectivo"
CASH_COUNTER = Counter("cash_session_id", "CAJ", "cash_sessions", "session_id")
SETTINGS_ID = "cash"
DEFAULT_SETTINGS = {"require_open_session": False}

BILLS = [100000, 50000, 20000, 10000, 5000, 2000]
COINS = [1000, 500, 200, 100, 50]
DENOMINATIONS = BILLS + COINS

KIND_LABELS = {
    "sale": "Venta",
    "fio_payment": "Abono (Fios)",
    "refund": "Reembolso por devolución",
    "income": "Ingreso de efectivo",
    "expense": "Egreso de efectivo",
}


def is_cash(method: Optional[str]) -> bool:
    return (method or "").strip().lower() == CASH_METHOD.lower()


def money(v: float) -> str:
    return "$" + f"{float(v or 0):,.0f}".replace(",", ".")


# ---------------------------------------------------------------- configuración

async def get_settings(session=None) -> Dict:
    doc = await db.system_settings.find_one({"_id": SETTINGS_ID}, {"_id": 0}, session=session)
    return {**DEFAULT_SETTINGS, **(doc or {})}


async def set_settings(require_open_session: bool, actor: str) -> Dict:
    await db.system_settings.update_one(
        {"_id": SETTINGS_ID},
        {"$set": {"require_open_session": bool(require_open_session), "updated_at": now_utc(), "updated_by": actor}},
        upsert=True,
    )
    return await get_settings()


# ---------------------------------------------------------------- sesión del cajero

async def open_session_of(email: str, session=None) -> Optional[dict]:
    return await cash_repo.open_session_of(email, session=session)


async def session_for_money(email: str, action: str, amount: Optional[float] = None, session=None) -> Optional[str]:
    """Caja abierta de `email` para asociar un movimiento. Si el interruptor exige caja y no hay,
    lanza 400 con el motivo; si no lo exige, devuelve None (el movimiento queda pendiente)."""
    current = await open_session_of(email, session=session)
    if current:
        return current["session_id"]
    if (await get_settings(session=session))["require_open_session"]:
        extra = f": esta devolución entrega {money(amount)} en efectivo" if action == "refund" else ""
        what = {"sale": "vender", "fio_payment": "recibir abonos", "refund": "registrar la devolución"}.get(action, "continuar")
        raise BusinessError(f"Abre tu caja antes de {what}{extra}. La configuración del sistema exige una caja abierta (menú Caja).")
    return None


async def add_movement(session_id: Optional[str], kind: str, direction: str, method: Optional[str], amount: float,
                       actor: str, reference: Optional[str] = None, reason: Optional[str] = None, session=None) -> dict:
    """Registra dinero que entra ('in') o sale ('out'). session_id None = pendiente de asociar."""
    doc = {
        "session_id": session_id,
        "kind": kind,
        "kind_label": KIND_LABELS.get(kind, kind),
        "direction": direction,
        "method": method or CASH_METHOD,
        "amount": round(float(amount), 2),
        "reference": reference,
        "reason": reason,
        "created_by": actor,
        "created_at": now_utc(),
    }
    await cash_repo.insert_movement(doc, session=session)
    return doc


async def attach_pending_movements(session_id: str, email: str, session=None) -> int:
    """Al abrir la caja: los movimientos registrados sin caja por ese usuario pasan a esta caja."""
    return await cash_repo.attach_pending(session_id, email, session=session)


async def summarize(cash_session: dict, session=None) -> Dict:
    """Esperado por forma de pago: base (solo efectivo) + entradas − salidas, por tipo."""
    rows = await db.cash_movements.aggregate([
        {"$match": {"session_id": cash_session["session_id"]}},
        {"$group": {"_id": {"method": "$method", "kind": "$kind", "direction": "$direction"},
                    "amount": {"$sum": "$amount"}, "count": {"$sum": 1}}},
    ], session=session).to_list(None)
    methods: Dict[str, Dict] = {}

    def entry(method: str) -> Dict:
        return methods.setdefault(method, {"method": method, "is_cash": is_cash(method), "opening": 0.0, "sales": 0.0,
                                           "fio_payments": 0.0, "refunds": 0.0, "income": 0.0, "expense": 0.0, "count": 0})

    cash = entry(CASH_METHOD)
    cash["opening"] = round(float(cash_session.get("opening_amount") or 0), 2)
    field = {"sale": "sales", "fio_payment": "fio_payments", "refund": "refunds", "income": "income", "expense": "expense"}
    for r in rows:
        e = entry(r["_id"]["method"])
        e[field.get(r["_id"]["kind"], "income")] += float(r["amount"] or 0)
        e["count"] += r["count"]
    out: List[Dict] = []
    for e in methods.values():
        e["expected"] = round(e["opening"] + e["sales"] + e["fio_payments"] + e["income"] - e["refunds"] - e["expense"], 2)
        for k in ("sales", "fio_payments", "refunds", "income", "expense"):
            e[k] = round(e[k], 2)
        out.append(e)
    out.sort(key=lambda e: (not e["is_cash"], e["method"]))
    return {"methods": out, "expected_cash": next(e["expected"] for e in out if e["is_cash"])}


def counted_from(denominations: Optional[Dict], counted_cash: Optional[float]) -> (float, Optional[Dict]):
    """Total contado: por denominaciones (si vienen) o el total escrito."""
    if denominations:
        clean = {}
        for k, v in denominations.items():
            try:
                value, qty = int(k), int(v or 0)
            except (TypeError, ValueError):
                raise BusinessError(f"Denominación inválida: {k}")
            if value not in DENOMINATIONS:
                raise BusinessError(f"Denominación no válida en Colombia: {money(value)}")
            if qty < 0:
                raise BusinessError(f"La cantidad de {money(value)} no puede ser negativa.")
            if qty:
                clean[str(value)] = qty
        return float(sum(int(k) * q for k, q in clean.items())), clean
    if counted_cash is None:
        raise BusinessError("Indica el efectivo contado (total o por denominaciones).")
    if counted_cash < 0:
        raise BusinessError("El efectivo contado no puede ser negativo.")
    return float(counted_cash), None
