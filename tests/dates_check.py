"""Pruebas de fechas nativas y conversión de fechas en texto (backlog P1.19).

    DB_NAME=boltrex_dttest tests/prepare_test_db.sh
    DB_NAME=boltrex_dttest backend/.venv/bin/uvicorn main:app --app-dir backend --port 8001
    BOLTREX_API=http://localhost:8001/api DB_NAME=boltrex_dttest backend/.venv/bin/python tests/dates_check.py
"""
import asyncio
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pymongo
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

ADMIN_PASSWORD = os.environ.get("BOLTREX_ADMIN_PASSWORD", "Prueba-Admin-2026")
DB_NAME = os.environ["DB_NAME"]
if DB_NAME == "boltrex":
    sys.exit("Negado: usa una BD de prueba.")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017/?directConnection=true")
mongo = pymongo.MongoClient(MONGO_URL, tz_aware=True)[DB_NAME]
B = os.environ.get("BOLTREX_API", "http://localhost:8001/api")
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"{'OK ' if ok else 'FAIL'} {name}" + ("" if ok else f" -> {detail}"))


for _ in range(30):
    try:
        requests.get(B.rsplit("/api", 1)[0] + "/", timeout=1)
        break
    except Exception:
        time.sleep(0.5)

r = requests.post(f"{B}/auth/login", json={"email": "admin@boltrex.com", "password": ADMIN_PASSWORD},
                  headers={"X-Real-IP": f"10.5.{uuid.uuid4().int % 250}.1"})
assert r.ok, r.text
H = {"Authorization": f"Bearer {r.json()['access_token']}"}
tag = uuid.uuid4().hex[:6].upper()

# --- 1. Los seeders ya guardan fechas nativas ---
check("seed: usuarios con fecha nativa", isinstance(mongo.users_extended.find_one({"email": "admin@boltrex.com"})["created_at"], datetime))
check("seed: módulos y roles con fecha nativa", isinstance(mongo.system_modules.find_one({})["created_at"], datetime)
      and isinstance(mongo.roles.find_one({})["created_at"], datetime))
check("arranque: no queda ninguna fecha en texto", all(
    mongo[c].count_documents({f: {"$type": "string"}}) == 0
    for c in mongo.list_collection_names() for f in ("created_at", "updated_at", "effective_date")))

# --- 2. Todo lo nuevo se guarda como fecha nativa y la API la entrega con zona horaria ---
cat = f"CatDt{tag}"
requests.post(f"{B}/categories", headers=H, json={"name": cat, "description": "x"})
check("crear categoría → fecha nativa en la BD", isinstance(mongo.categories.find_one({"name": cat})["created_at"], datetime))
api_cat = next(c for c in requests.get(f"{B}/categories", headers=H).json() if c["name"] == cat)
check("la API entrega la fecha con zona horaria (el navegador la convierte bien)",
      api_cat["created_at"].endswith(("Z", "+00:00")), api_cat["created_at"])
bc, doc = f"DT{tag}", f"3{int(tag, 16)}"
requests.post(f"{B}/products", headers=H, json={"barcode": bc, "name": "Prod Dt", "category": cat, "purchase_price": 100, "tax_rate": 0,
                                                "prices": [{"price_list_name": "default", "price": 200}]})
requests.post(f"{B}/clients", headers=H, json={"document_type": "CC", "document_number": doc, "first_name": "Dt", "last_name": "Test"})
pn = requests.post(f"{B}/purchases", headers=H, json={"supplier_name": "Prov Dt", "items": [
    {"barcode": bc, "product_name": "x", "quantity": 5, "unit_cost": 100, "total": 500}]}).json()["purchase_number"]
requests.post(f"{B}/purchases/{pn}/confirm", headers=H)
r = requests.post(f"{B}/invoices", headers=H, json={"client_document": doc, "client_document_type": "CC", "payment_status": "por_cobrar",
                                                    "items": [{"barcode": bc, "product_name": "x", "quantity": 2, "unit_price": 0, "tax_rate": 0,
                                                               "subtotal": 0, "tax_amount": 0, "total": 0}]})
inv = r.json()
check("venta OK y responde la fecha con zona", r.ok and inv["created_at"].endswith(("Z", "+00:00")), r.text[:200])
requests.post(f"{B}/fios/{inv['invoice_number']}/payment", headers=H, json={"amount": 100, "payment_method": "Efectivo"})
requests.post(f"{B}/returns", headers=H, json={"invoice_number": inv["invoice_number"], "items": [
    {"barcode": bc, "product_name": "x", "quantity": 1, "unit_price": 200, "total": 200}]})
native = {
    "factura": mongo.invoices.find_one({"invoice_number": inv["invoice_number"]})["created_at"],
    "compra": mongo.purchases.find_one({"purchase_number": pn})["created_at"],
    "movimiento": mongo.inventory_movements.find_one({"barcode": bc})["created_at"],
    "abono": mongo.fio_payments.find_one({"invoice_number": inv["invoice_number"]})["created_at"],
    "devolución": mongo.returns.find_one({"invoice_number": inv["invoice_number"]})["created_at"],
    "producto": mongo.products.find_one({"barcode": bc})["created_at"],
    "cliente": mongo.clients.find_one({"document_number": doc})["created_at"],
}
check("factura, compra, movimiento, abono, devolución, producto y cliente con fecha nativa",
      all(isinstance(v, datetime) for v in native.values()), {k: type(v).__name__ for k, v in native.items()})
now = datetime.now(timezone.utc)
check("la fecha guardada es la hora actual en UTC", abs((native["factura"] - now).total_seconds()) < 120, native["factura"])

# --- 3. Filtros por día local con fechas nativas ---
local_today = (now.astimezone(timezone.utc).timestamp() - 300 * 60)
day = datetime.fromtimestamp(local_today, timezone.utc).strftime("%Y-%m-%d")
d = requests.get(f"{B}/invoices", headers=H, params={"start_date": day, "end_date": day, "tz_offset_minutes": 300, "search": inv["invoice_number"]}).json()
check("filtro por día local (Colombia) encuentra la venta de hoy", d["total"] == 1, d["total"])
d = requests.get(f"{B}/invoices", headers=H, params={"start_date": "2000-01-01", "end_date": "2000-01-01", "search": inv["invoice_number"]}).json()
check("un día sin ventas → 0", d["total"] == 0)
m = requests.get(f"{B}/inventory/movements", headers=H, params={"barcode": bc, "start_date": day, "end_date": day, "tz_offset_minutes": 300}).json()
check("movimientos filtrados por día local", m["total"] >= 2, m["total"])

# --- 4. Ticket PDF y CSV siguen funcionando con fechas nativas ---
pay = requests.post(f"{B}/invoices", headers=H, json={"client_document": doc, "client_document_type": "CC", "payment_status": "pagado",
                                                      "payment_method": "Efectivo", "items": [{"barcode": bc, "product_name": "x", "quantity": 1,
                                                      "unit_price": 0, "tax_rate": 0, "subtotal": 0, "tax_amount": 0, "total": 0}]}).json()
r = requests.get(f"{B}/pos/invoices/{pay['invoice_number']}/ticket", headers=H)
check("ticket PDF se genera", r.ok and r.content[:4] == b"%PDF", r.status_code)
r = requests.get(f"{B}/reports/sales/export", headers=H, params={"start_date": day, "end_date": day, "tz_offset_minutes": 300})
row = next((l for l in r.content.decode("utf-8-sig").splitlines() if l.startswith(pay["invoice_number"])), "")
local = datetime.fromtimestamp(local_today, timezone.utc).strftime("%Y-%m-%d")
check("CSV con la fecha en hora local (AAAA-MM-DD HH:MM)", f",{local} " in row, row[:80])

# --- 5. Conversión de datos antiguos en texto ---
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from core.dates import migrate_text_dates, parse_date_text  # noqa: E402

formats = {
    "iso_micro": ("2026-11-04T15:30:00.123456+00:00", datetime(2026, 11, 4, 15, 30, 0, 123456, timezone.utc)),
    "iso_z": ("2026-11-04T15:30:00Z", datetime(2026, 11, 4, 15, 30, tzinfo=timezone.utc)),
    "iso_offset_col": ("2026-11-04T10:30:00-05:00", datetime(2026, 11, 4, 15, 30, tzinfo=timezone.utc)),
    "sin_zona": ("2026-11-04T15:30:00", datetime(2026, 11, 4, 15, 30, tzinfo=timezone.utc)),
    "con_espacio": ("2026-11-04 15:30:00", datetime(2026, 11, 4, 15, 30, tzinfo=timezone.utc)),
    "solo_fecha": ("2026-11-04", datetime(2026, 11, 4, tzinfo=timezone.utc)),
}
for name, (text, expected) in formats.items():
    check(f"interpreta formato {name}", parse_date_text(text) == expected, parse_date_text(text))
check("texto basura → None (no inventa fechas)", parse_date_text("ayer por la tarde") is None and parse_date_text("") is None)

legacy = [{"invoice_number": f"LG{tag}-{k}", "status": "completed", "total": 1, "total_tax": 0, "client_name": "Legacy",
           "client_document": "0", "created_at": text} for k, (text, _) in formats.items()]
legacy.append({"invoice_number": f"LG{tag}-basura", "status": "completed", "total": 1, "client_document": "0", "created_at": "ayer"})
mongo.invoices.insert_many(legacy)
mongo.categories.insert_one({"name": f"LegCat{tag}", "created_at": "2025-01-01T00:00:00+00:00"})
mongo.ticket_config.update_one({}, {"$set": {"updated_at": "2025-02-02T10:00:00+00:00"}})


async def run_migration():
    return await migrate_text_dates(AsyncIOMotorClient(MONGO_URL, tz_aware=True)[DB_NAME])

rep = asyncio.run(run_migration())
conv = {d["invoice_number"]: d["created_at"] for d in mongo.invoices.find({"invoice_number": {"$regex": f"^LG{tag}"}})}
# MongoDB guarda fechas con precisión de milisegundos (123456 µs → 123000 µs).
ms = lambda dt: dt.replace(microsecond=dt.microsecond // 1000 * 1000)
check("conversión: las 6 facturas antiguas quedan con fecha nativa y valor correcto (a milisegundos)",
      all(conv[f"LG{tag}-{k}"] == ms(exp) for k, (_, exp) in formats.items()), {k: v for k, v in conv.items()})
check("conversión: la fecha ilegible se deja igual y se informa", conv[f"LG{tag}-basura"] == "ayer"
      and any("ayer" in u for u in rep["unparseable"]), rep["unparseable"][:2])
check("conversión: también otras colecciones (categorías, config. ticket)",
      isinstance(mongo.categories.find_one({"name": f"LegCat{tag}"})["created_at"], datetime)
      and isinstance(mongo.ticket_config.find_one({})["updated_at"], datetime))
check("conversión: informa cuántas convirtió", rep["converted"] >= 8, rep["converted"])
rep2 = asyncio.run(run_migration())
check("conversión idempotente: la segunda vez no cambia nada", rep2["converted"] == 0, rep2["converted"])
d = requests.get(f"{B}/invoices", headers=H, params={"start_date": "2026-11-04", "end_date": "2026-11-04", "search": f"LG{tag}"}).json()
check("las facturas convertidas aparecen en el filtro por día", d["total"] == 6, d["total"])
d = requests.get(f"{B}/invoices", headers=H, params={"search": f"LG{tag}", "page_size": 20}).json()
check("orden cronológico correcto tras convertir (más reciente primero; la ilegible queda aparte)",
      [i["invoice_number"] for i in d["items"] if i["invoice_number"] != f"LG{tag}-basura"][0] == f"LG{tag}-iso_micro", [i["invoice_number"] for i in d["items"]])

mongo.invoices.delete_many({"invoice_number": {"$regex": f"^LG{tag}"}})
mongo.categories.delete_many({"name": f"LegCat{tag}"})
print(f"\n{sum(results)}/{len(results)} pruebas OK")
sys.exit(0 if all(results) else 1)
