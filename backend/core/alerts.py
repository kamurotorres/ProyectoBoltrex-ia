"""Alertas de stock bajo y créditos (backlog P2.34) + reglas de stock mínimo.

Decisiones del usuario:
- Solo dentro de la app (campana en el encabezado, aviso al vender y resumen al entrar): opción A.
- Stock mínimo: umbral GENERAL en Config. Sistema (inicial 10) + `products.min_stock` opcional que
  manda sobre el general. Bajo stock = stock < mínimo; agotado = stock ≤ 0.
- «Marcar como visto» apaga el número rojo de ESE usuario hasta que aparezca una alerta nueva o
  empeore una existente (bajo → agotado; un crédito que pasa a un tramo de atraso mayor; una factura
  por vencer que se vence).
- Créditos: vencidos y por vencer, por separado.

Las alertas se calculan al consultar (nunca quedan desactualizadas). Cada una tiene una clave
(p. ej. `stock:PAN1:out`, `overdue:INV-000045:31_60`, `soon:INV-000046`); lo «visto» es el conjunto de
claves que el usuario tenía al marcar, podado a las que siguen vigentes (así una alerta que se
resolvió y vuelve a aparecer avisa de nuevo).
"""
from typing import Dict, List, Optional

from fastapi import HTTPException

from core.database import db
from core.dates import now_utc

SETTINGS_ID = "inventory"
DEFAULT_LOW_STOCK_THRESHOLD = 10
PANEL_LIMIT = 5          # elementos por grupo en la campana
MAX_KEYS = 2000          # tope de claves evaluadas por grupo


# ---------------------------------------------------------------- stock mínimo

async def get_inventory_settings() -> Dict:
    doc = await db.system_settings.find_one({"_id": SETTINGS_ID}, {"_id": 0, "updated_at": 0, "updated_by": 0})
    return {"low_stock_threshold": DEFAULT_LOW_STOCK_THRESHOLD, **(doc or {})}


async def set_inventory_settings(low_stock_threshold: int, actor: str) -> Dict:
    if low_stock_threshold < 0 or low_stock_threshold > 1_000_000:
        raise HTTPException(status_code=400, detail="El stock mínimo general debe ser un número entero de 0 o más.")
    await db.system_settings.update_one(
        {"_id": SETTINGS_ID},
        {"$set": {"low_stock_threshold": int(low_stock_threshold), "updated_at": now_utc(), "updated_by": actor}},
        upsert=True,
    )
    return await get_inventory_settings()


def min_expr(threshold: int) -> dict:
    """Mínimo efectivo de cada producto: el suyo o el general."""
    return {"$ifNull": ["$min_stock", threshold]}


def low_stock_expr(threshold: int) -> dict:
    return {"$lt": [{"$ifNull": ["$stock", 0]}, min_expr(threshold)]}


def low_stock_filter(threshold: int) -> dict:
    return {"$expr": low_stock_expr(threshold)}


def effective_min(product: dict, threshold: int) -> int:
    m = product.get("min_stock")
    return int(m) if m is not None else int(threshold)


def stock_status(product: dict, threshold: int) -> str:
    stock = int(product.get("stock") or 0)
    if stock <= 0:
        return "out"
    return "low" if stock < effective_min(product, threshold) else "ok"


async def stock_warnings(barcodes: List[str]) -> List[Dict]:
    """Productos que quedaron en bajo stock o agotados (aviso del POS tras una venta)."""
    if not barcodes:
        return []
    threshold = (await get_inventory_settings())["low_stock_threshold"]
    out = []
    async for p in db.products.find({"barcode": {"$in": list(set(barcodes))}}, {"_id": 0, "barcode": 1, "name": 1, "stock": 1, "min_stock": 1}):
        status = stock_status(p, threshold)
        if status != "ok":
            out.append({"barcode": p["barcode"], "name": p["name"], "stock": int(p.get("stock") or 0),
                        "min_stock": effective_min(p, threshold), "status": status})
    return sorted(out, key=lambda x: (x["status"] != "out", x["name"]))


# ---------------------------------------------------------------- alertas

async def _stock_alerts(threshold: int) -> Dict:
    rows = await db.products.find(low_stock_filter(threshold), {"_id": 0, "barcode": 1, "name": 1, "stock": 1, "min_stock": 1}) \
        .sort([("stock", 1), ("name", 1)]).limit(MAX_KEYS).to_list(MAX_KEYS)
    items = [{"barcode": p["barcode"], "name": p["name"], "stock": int(p.get("stock") or 0),
              "min_stock": effective_min(p, threshold), "status": stock_status(p, threshold)} for p in rows]
    total = await db.products.count_documents(low_stock_filter(threshold))
    return {"count": total, "out_count": sum(1 for i in items if i["status"] == "out"),
            "low_count": sum(1 for i in items if i["status"] == "low"), "threshold": threshold,
            "_entries": [(i, [f"stock:{i['barcode']}:{i['status']}"]) for i in items]}


async def _credit_alerts() -> Dict:
    from core import credit
    settings = await credit.get_settings()
    now = now_utc()
    base = [{"$match": credit.pending_match()}, *credit.overdue_stages(now)]
    # Vencidas, por cliente (la clave lleva el tramo del atraso máximo: empeorar = alerta nueva).
    overdue = await db.invoices.aggregate(base + [
        {"$match": {"_od": {"$gt": 0}}},
        {"$group": {"_id": {"d": "$client_document", "t": "$client_document_type"}, "client_name": {"$last": "$client_name"},
                    "balance": {"$sum": "$balance"}, "invoices": {"$sum": 1}, "max_days": {"$max": "$_od"},
                    "keys": {"$push": {"$concat": ["overdue:", "$invoice_number", ":", "$_bucket"]}}}},
        {"$sort": {"max_days": -1, "balance": -1}}, {"$limit": MAX_KEYS},
    ]).to_list(MAX_KEYS)

    # Clave por factura y tramo: una factura que se vence o pasa a un tramo peor = alerta nueva;
    # pagar una factura no hace «nuevas» las demás del cliente.
    o_entries = [({"client_document": r["_id"]["d"], "client_document_type": r["_id"].get("t"), "client_name": r.get("client_name", ""),
                   "balance": round(r["balance"], 2), "invoices": r["invoices"], "max_days_overdue": int(r["max_days"])}, r["keys"])
                 for r in overdue]
    # Por vencer, por factura (cuando se vence pasa a «vencidas» con otra clave).
    soon = await db.invoices.aggregate(base + [
        {"$match": {"$expr": credit.due_soon_expr(now, settings["due_soon_days"])}},
        {"$sort": {"due_date": 1}}, {"$limit": MAX_KEYS},
        {"$project": {"_id": 0, "invoice_number": 1, "client_name": 1, "client_document": 1, "client_document_type": 1,
                      "balance": 1, "due_date": 1}},
    ]).to_list(MAX_KEYS)
    s_entries = []
    for r in soon:
        st = credit.invoice_status(r.get("due_date"), settings["due_soon_days"], now)
        s_entries.append(({**r, "balance": round(r["balance"], 2), "days_left": st["days_left"], "label": st["credit_status_label"]},
                          [f"soon:{r['invoice_number']}"]))
    return {
        "overdue": {"count": len(o_entries), "balance": round(sum(i["balance"] for i, _ in o_entries), 2),
                    "invoices": sum(i["invoices"] for i, _ in o_entries), "_entries": o_entries},
        "due_soon": {"count": len(s_entries), "balance": round(sum(i["balance"] for i, _ in s_entries), 2),
                     "due_soon_days": settings["due_soon_days"], "_entries": s_entries},
    }


async def build_alerts(email: str, can_stock: bool, can_credit: bool) -> Dict:
    groups: Dict[str, Dict] = {}
    if can_stock:
        groups["stock"] = await _stock_alerts((await get_inventory_settings())["low_stock_threshold"])
    if can_credit:
        groups.update(await _credit_alerts())

    current = {k for g in groups.values() for _, keys in g["_entries"] for k in keys}
    seen_doc = await db.alerts_seen.find_one({"email": email}) or {}
    seen = set(seen_doc.get("keys", []))
    pruned = seen & current
    if pruned != seen:   # lo resuelto se olvida: si vuelve a pasar, avisa de nuevo
        await db.alerts_seen.update_one({"email": email}, {"$set": {"keys": sorted(pruned)}})
    new_total = 0
    for g in groups.values():
        entries = g.pop("_entries")
        for item, keys in entries:
            item["is_new"] = any(k not in pruned for k in keys)
        g["new"] = sum(1 for item, _ in entries if item["is_new"])
        g["items"] = [item for item, _ in entries[:PANEL_LIMIT]]
        new_total += g["new"]
    return {
        "groups": groups,
        "total": sum(g["count"] for g in groups.values()),
        "new": new_total,
        "can": {"stock": can_stock, "credit": can_credit},
        "generated_at": now_utc(),
    }


async def mark_seen(email: str, can_stock: bool, can_credit: bool) -> int:
    groups = []
    if can_stock:
        groups.append(await _stock_alerts((await get_inventory_settings())["low_stock_threshold"]))
    if can_credit:
        groups.extend((await _credit_alerts()).values())
    keys = {k for g in groups for _, ks in g["_entries"] for k in ks}
    await db.alerts_seen.update_one({"email": email}, {"$set": {"email": email, "keys": sorted(keys), "seen_at": now_utc()}}, upsert=True)
    return len(keys)
