"""Pruebas del factory reset (backlog P0.4). ⚠️ BORRA TODOS LOS DATOS de la BD a la que apunta.

Uso (SOLO contra una BD de PRUEBA sembrada con init_rbac.py + seed_data.py):
    DB_NAME=boltrex_resettest backend/.venv/bin/uvicorn main:app --app-dir backend --port 8001
    BOLTREX_API=http://localhost:8001/api DB_NAME=boltrex_resettest \
        backend/.venv/bin/python tests/factory_reset_check.py
"""
import os
# Contraseña del admin de la BD de prueba (ver tests/prepare_test_db.sh). Ya no existe admin123 (P1.10).
ADMIN_PASSWORD = os.environ.get("BOLTREX_ADMIN_PASSWORD", "Prueba-Admin-2026")
import os
import sys
import time

import pymongo
import requests


B = os.environ.get("BOLTREX_API", "http://localhost:8001/api")
DB_NAME = os.environ["DB_NAME"]
if DB_NAME == "boltrex":
    sys.exit("Negado: este test borra todo; usa una BD de prueba (DB_NAME distinto de 'boltrex').")
mongo = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017/?directConnection=true"))[DB_NAME]
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


def login(email, pw):
    r = requests.post(f"{B}/auth/login", json={"email": email, "password": pw})
    return {"Authorization": f"Bearer {r.json()['access_token']}"} if r.ok else None


H = login("admin@boltrex.com", ADMIN_PASSWORD)
assert H, "no se pudo entrar como admin"

print("== Generar datos ==")
requests.post(f"{B}/clients", headers=H, json={"document_type": "CC", "document_number": "555", "first_name": "R", "last_name": "S"})
requests.post(f"{B}/products", headers=H, json={"barcode": "RS1", "name": "P", "category": "Otros", "purchase_price": 10,
                                                "tax_rate": 0, "prices": [{"price_list_name": "default", "price": 20}]})
pn = requests.post(f"{B}/purchases", headers=H, json={"supplier_name": "Prov", "items": [
    {"barcode": "RS1", "product_name": "P", "quantity": 5, "unit_cost": 10, "total": 50}]}).json()["purchase_number"]
requests.post(f"{B}/purchases/{pn}/confirm", headers=H)
line = {"barcode": "RS1", "product_name": "P", "quantity": 1, "unit_price": 0, "tax_rate": 0, "subtotal": 0, "tax_amount": 0, "total": 0}
for _ in range(3):
    inv = requests.post(f"{B}/invoices", headers=H, json={"client_document": "555", "payment_status": "por_cobrar", "items": [line]}).json()
requests.post(f"{B}/fios/{inv['invoice_number']}/payment", headers=H, json={"amount": 5, "payment_method": "Efectivo"})
requests.post(f"{B}/returns", headers=H, json={"invoice_number": inv["invoice_number"], "items": [{"barcode": "RS1", "quantity": 1}]})
pre_reset_number = int(inv["invoice_number"].split("-")[1])
check("antes del reset la numeración va por encima de INV-000002", pre_reset_number >= 3, inv["invoice_number"])
check("hay abonos y contadores antes del reset", mongo.fio_payments.count_documents({}) > 0 and mongo.counters.count_documents({}) > 0)

# Un segundo administrador (será quien ejecute el reset) y un vendedor (debe desaparecer).
for email, role in [("admin2@test.com", "Administrador"), ("vend@test.com", "Vendedor")]:
    requests.post(f"{B}/rbac/users", headers=H, json={"email": email, "password": "Pass-1234", "first_name": role, "last_name": "T"})
    requests.post(f"{B}/rbac/users/{email}/roles", headers=H, json=[role])
# Simula que admin@boltrex.com perdió su rol de administrador antes del reset.
requests.post(f"{B}/rbac/users/admin@boltrex.com/roles", headers=H, json=["Vendedor"])

print("== Ejecutar reset como admin2 ==")
H2 = login("admin2@test.com", "Pass-1234")
check("vendedor no puede ejecutar el reset (403)",
      requests.post(f"{B}/system/factory-reset", headers=login("vend@test.com", "Pass-1234"), json={"password": "Pass-1234"}).status_code == 403)
check("contraseña incorrecta rechazada (401)",
      requests.post(f"{B}/system/factory-reset", headers=H2, json={"password": "mala"}).status_code == 401)
r = requests.post(f"{B}/system/factory-reset", headers=H2, json={"password": "Pass-1234"})
check("reset ejecutado", r.ok, r.text)

print("== Estado tras el reset ==")
for col in ["products", "clients", "suppliers", "purchases", "returns", "invoices", "inventory_movements", "fio_payments", "counters"]:
    n = mongo[col].count_documents({})
    check(f"{col} vacía", n == 0, n)
emails = sorted(u["email"] for u in mongo.users_extended.find({}, {"email": 1}))
check("solo quedan admin@boltrex.com y quien ejecutó el reset", emails == ["admin2@test.com", "admin@boltrex.com"], emails)
check("catálogos re-sembrados (6 formas de pago, 4 tipos doc, 3 listas)",
      mongo.payment_methods.count_documents({}) == 6 and mongo.document_types.count_documents({}) == 4 and mongo.price_lists.count_documents({}) == 3)
check("RBAC re-sembrado (3 roles)", mongo.roles.count_documents({}) == 3)

H = login("admin@boltrex.com", ADMIN_PASSWORD)
check("admin@boltrex.com sigue entrando", H is not None)
perms = requests.get(f"{B}/auth/me", headers=H).json().get("permissions", {}) if H else {}
check("admin@boltrex.com recuperó el rol Administrador", perms.get("users", {}).get("delete") is True, perms.get("users"))
H2 = login("admin2@test.com", "Pass-1234")
check("quien ejecutó el reset sigue entrando", H2 is not None)
check("el vendedor fue eliminado", login("vend@test.com", "Pass-1234") is None)

print("== La numeración vuelve a empezar ==")
requests.post(f"{B}/clients", headers=H, json={"document_type": "CC", "document_number": "556", "first_name": "N", "last_name": "N"})
requests.post(f"{B}/products", headers=H, json={"barcode": "RS2", "name": "P2", "category": "Otros", "purchase_price": 10,
                                                "tax_rate": 0, "prices": [{"price_list_name": "default", "price": 20}]})
pr = requests.post(f"{B}/purchases", headers=H, json={"supplier_name": "Prov", "items": [
    {"barcode": "RS2", "product_name": "P2", "quantity": 2, "unit_cost": 10, "total": 20}]}).json()
check("primera compra tras reset = PUR-000001", pr.get("purchase_number") == "PUR-000001", pr.get("purchase_number"))
requests.post(f"{B}/purchases/{pr['purchase_number']}/confirm", headers=H)
r = requests.post(f"{B}/invoices", headers=H, json={"client_document": "556", "payment_status": "pagado", "payment_method": "Efectivo",
                                                    "items": [dict(line, barcode="RS2")]})
check("primera factura tras reset = INV-000001", r.ok and r.json()["invoice_number"] == "INV-000001", r.json().get("invoice_number") if r.ok else r.text)

print(f"\n{sum(results)}/{len(results)} pruebas OK")
sys.exit(0 if all(results) else 1)
