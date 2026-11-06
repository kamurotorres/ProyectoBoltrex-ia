"""Pruebas de identidad de clientes por tipo + número y bloqueo al eliminar (backlog P1.15).

    DB_NAME=boltrex_citest tests/prepare_test_db.sh
    DB_NAME=boltrex_citest backend/.venv/bin/uvicorn main:app --app-dir backend --port 8001
    BOLTREX_API=http://localhost:8001/api DB_NAME=boltrex_citest backend/.venv/bin/python tests/client_identity_check.py
"""
import asyncio
import os
import sys
import time
import uuid
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
mongo = pymongo.MongoClient(MONGO_URL)[DB_NAME]
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
                  headers={"X-Real-IP": f"10.8.{uuid.uuid4().int % 250}.1"})
assert r.ok, r.text
H = {"Authorization": f"Bearer {r.json()['access_token']}"}

tag = uuid.uuid4().hex[:6].upper()
NUM = f"7{int(tag, 16)}"
PL = f"Mayor{tag}"
bc = f"CI{tag}"

# --- Preparación: dos clientes con el MISMO número y distinto tipo y lista de precios ---
for code, name in (("CC", "Cédula de Ciudadanía"), ("NIT", "NIT")):
    if not mongo.document_types.find_one({"code": code}):
        requests.post(f"{B}/document-types", headers=H, json={"code": code, "name": name})
requests.post(f"{B}/price-lists", headers=H, json={"name": PL, "description": "x", "is_active": True})
requests.post(f"{B}/products", headers=H, json={"barcode": bc, "name": "Prod CI", "category": "Otros", "purchase_price": 100, "tax_rate": 0,
                                                "prices": [{"price_list_name": "default", "price": 200}, {"price_list_name": PL, "price": 150}]})
pn = requests.post(f"{B}/purchases", headers=H, json={"supplier_name": "Prov CI", "items": [
    {"barcode": bc, "product_name": "Prod CI", "quantity": 50, "unit_cost": 100, "total": 5000}]}).json()["purchase_number"]
requests.post(f"{B}/purchases/{pn}/confirm", headers=H)
r1 = requests.post(f"{B}/clients", headers=H, json={"document_type": "CC", "document_number": NUM, "first_name": "Persona", "last_name": "Natural"})
r2 = requests.post(f"{B}/clients", headers=H, json={"document_type": "NIT", "document_number": NUM, "first_name": "Empresa", "last_name": "SAS", "price_list": PL})
check("se pueden crear CC y NIT con el mismo número", r1.ok and r2.ok, (r1.text, r2.text))
r = requests.post(f"{B}/clients", headers=H, json={"document_type": "NIT", "document_number": NUM, "first_name": "Otra", "last_name": "X"})
check("pero no dos NIT iguales (400 con mensaje)", r.status_code == 400 and "NIT" in r.json()["detail"], r.text)

stock = lambda: mongo.products.find_one({"barcode": bc})["stock"]

# --- Consultar ---
r = requests.get(f"{B}/clients/{NUM}", headers=H)
check("GET sin tipo con número repetido → 400 'Hay 2 clientes … Indica el tipo'",
      r.status_code == 400 and "Hay 2 clientes" in r.json()["detail"] and "CC, NIT" in r.json()["detail"], r.text)
r = requests.get(f"{B}/clients/{NUM}", headers=H, params={"document_type": "NIT"})
check("GET con tipo NIT → la empresa", r.ok and r.json()["first_name"] == "Empresa", r.text)
r = requests.get(f"{B}/clients/{NUM}", headers=H, params={"document_type": "CE"})
check("GET con tipo inexistente → 404 en español", r.status_code == 404 and f"CE {NUM}" in r.json()["detail"], r.text)

# --- Vender ---
item = {"barcode": bc, "product_name": "x", "quantity": 1, "unit_price": 0, "tax_rate": 0, "subtotal": 0, "tax_amount": 0, "total": 0}
s0 = stock()
r = requests.post(f"{B}/invoices", headers=H, json={"client_document": NUM, "payment_status": "por_cobrar", "items": [item]})
check("venta sin tipo con número repetido → 400 con mensaje (no adivina)", r.status_code == 400 and "Indica el tipo" in r.json()["detail"], r.text)
check("…y no descuenta stock", stock() == s0)
r = requests.post(f"{B}/invoices", headers=H, json={"client_document": NUM, "client_document_type": "NIT", "payment_status": "por_cobrar", "items": [item]})
inv_nit = r.json()
check("venta a NIT → a nombre de la empresa", r.ok and inv_nit["client_name"] == "Empresa SAS", r.text)
check("…con SU lista de precios (150, no 200)", r.ok and abs(inv_nit["total"] - 150) < 0.01, inv_nit.get("total"))
check("…y la factura guarda el tipo de documento", mongo.invoices.find_one({"invoice_number": inv_nit["invoice_number"]}).get("client_document_type") == "NIT")
r = requests.post(f"{B}/invoices", headers=H, json={"client_document": NUM, "client_document_type": "CC", "payment_status": "por_cobrar", "items": [item, item]})
inv_cc = r.json()
check("venta a CC → persona, precio default (2 × 200)", r.ok and inv_cc["client_name"] == "Persona Natural" and abs(inv_cc["total"] - 400) < 0.01, r.text)

# --- Fios ---
accts = [a for a in requests.get(f"{B}/fios", headers=H, params={"search": NUM}).json()["items"] if a["client_document"] == NUM]
by_type = {a.get("client_document_type"): a for a in accts}
check("Fios: dos cuentas separadas (CC y NIT)", set(by_type) == {"CC", "NIT"}, accts)
check("Fios: cada cuenta con su saldo (CC 400, NIT 150)",
      abs(by_type.get("CC", {}).get("balance", 0) - 400) < 0.01 and abs(by_type.get("NIT", {}).get("balance", 0) - 150) < 0.01, accts)
d = requests.get(f"{B}/fios/{NUM}", headers=H, params={"document_type": "NIT"}).json()
check("Fios detalle NIT: solo sus facturas", [i["invoice_number"] for i in d["invoices"]] == [inv_nit["invoice_number"]]
      and d["client"]["document_type"] == "NIT", d.get("invoices"))
r = requests.get(f"{B}/fios/{NUM}", headers=H)
check("Fios detalle sin tipo con número repetido → 400 con mensaje", r.status_code == 400 and "Indica el tipo" in r.json()["detail"], r.text)

# --- Editar ---
r = requests.put(f"{B}/clients/{NUM}", headers=H, params={"document_type": "NIT"}, json={"phone": "3000000000"})
cc = mongo.clients.find_one({"document_type": "CC", "document_number": NUM})
nit = mongo.clients.find_one({"document_type": "NIT", "document_number": NUM})
check("editar NIT cambia solo la empresa", r.ok and nit.get("phone") == "3000000000" and not cc.get("phone"), r.text)
r = requests.put(f"{B}/clients/{NUM}", headers=H, json={"phone": "1"})
check("editar sin tipo con número repetido → 400, sin tocar a nadie",
      r.status_code == 400 and mongo.clients.count_documents({"document_number": NUM, "phone": "1"}) == 0, r.text)
rec = mongo.audit_log.find_one({"module": "clients", "action": "update"}, sort=[("at", -1)])
check("auditoría identifica al cliente con tipo + número", rec and rec["entity_id"] == f"NIT {NUM}", rec and rec.get("entity_id"))

# --- Eliminar: bloqueo con facturas ---
r = requests.delete(f"{B}/clients/{NUM}", headers=H, params={"document_type": "CC"})
det = r.json().get("detail", "")
check("eliminar cliente con facturas → 400 con motivo (facturas y saldo pendiente)",
      r.status_code == 400 and "1 factura" in det and "saldo pendiente" in det and "400" in det, det)
check("…y el cliente sigue existiendo", mongo.clients.count_documents({"document_type": "CC", "document_number": NUM}) == 1)
requests.post(f"{B}/fios/{inv_nit['invoice_number']}/payment", headers=H, json={"amount": 150, "payment_method": "Efectivo"})
r = requests.delete(f"{B}/clients/{NUM}", headers=H, params={"document_type": "NIT"})
det = r.json().get("detail", "")
check("con la deuda pagada sigue bloqueado por historial (sin mencionar saldo)",
      r.status_code == 400 and "factura" in det and "saldo" not in det, det)
r = requests.delete(f"{B}/clients/{NUM}", headers=H)
check("eliminar sin tipo con número repetido → 400", r.status_code == 400 and "Indica el tipo" in r.json()["detail"], r.text)

# --- Compatibilidad: número único sin tipo sigue funcionando ---
U = f"6{int(tag, 16)}"
requests.post(f"{B}/clients", headers=H, json={"document_type": "CC", "document_number": U, "first_name": "Unico", "last_name": "Cliente"})
check("GET sin tipo con número único → OK", requests.get(f"{B}/clients/{U}", headers=H).ok)
check("PUT sin tipo con número único → OK", requests.put(f"{B}/clients/{U}", headers=H, json={"phone": "2"}).ok)
r = requests.post(f"{B}/invoices", headers=H, json={"client_document": U, "payment_status": "pagado", "payment_method": "Efectivo", "items": [item]})
check("venta sin tipo con número único → OK y guarda el tipo", r.ok and mongo.invoices.find_one({"invoice_number": r.json()["invoice_number"]})["client_document_type"] == "CC", r.text)
F = f"5{int(tag, 16)}"
requests.post(f"{B}/clients", headers=H, json={"document_type": "CC", "document_number": F, "first_name": "Sin", "last_name": "Ventas"})
r = requests.delete(f"{B}/clients/{F}", headers=H)
check("eliminar cliente sin facturas → OK", r.ok and mongo.clients.count_documents({"document_number": F}) == 0, r.text)

# --- Facturas antiguas sin tipo ---
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
import core.database as cdb  # noqa: E402

legacy_u = f"LEG{tag}-U"
legacy_a = f"LEG{tag}-A"
mongo.invoices.insert_many([
    {"invoice_number": legacy_u, "client_document": U, "client_name": "Unico Cliente", "status": "completed", "total": 1, "created_at": "2001-01-01T00:00:00+00:00"},
    {"invoice_number": legacy_a, "client_document": NUM, "client_name": "?", "status": "completed", "total": 1, "created_at": "2001-01-01T00:00:00+00:00"},
])
cdb.db = AsyncIOMotorClient(MONGO_URL)[DB_NAME]
import core.clients as cc_mod  # noqa: E402
cc_mod.db = cdb.db
rep = asyncio.run(cc_mod.backfill_invoice_document_types())
check("arranque: completa el tipo en facturas antiguas sin ambigüedad",
      mongo.invoices.find_one({"invoice_number": legacy_u}).get("client_document_type") == "CC", rep)
check("…y deja sin tocar las ambiguas (las informa)",
      "client_document_type" not in mongo.invoices.find_one({"invoice_number": legacy_a}) and NUM in rep["ambiguous"], rep)
mongo.invoices.delete_many({"invoice_number": {"$in": [legacy_u, legacy_a]}})

print(f"\n{sum(results)}/{len(results)} pruebas OK")
sys.exit(0 if all(results) else 1)
