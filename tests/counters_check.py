"""Pruebas de consecutivos atómicos (backlog P0.5): PUR- e INV- sin duplicados ni huecos.

Uso (contra una BD de PRUEBA sembrada con init_rbac.py + seed_data.py):
    DB_NAME=boltrex_cnttest backend/.venv/bin/uvicorn main:app --app-dir backend --port 8001
    BOLTREX_API=http://localhost:8001/api DB_NAME=boltrex_cnttest \
        backend/.venv/bin/python tests/counters_check.py
"""
import os
# Contraseña del admin de la BD de prueba (ver tests/prepare_test_db.sh). Ya no existe admin123 (P1.10).
ADMIN_PASSWORD = os.environ.get("BOLTREX_ADMIN_PASSWORD", "Prueba-Admin-2026")
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import pymongo
import requests


B = os.environ.get("BOLTREX_API", "http://localhost:8001/api")
DB_NAME = os.environ["DB_NAME"]
if DB_NAME == "boltrex":
    sys.exit("Negado: este test manipula `counters`; usa una BD de prueba.")
mongo = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017/?directConnection=true"))[DB_NAME]
N = 20
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"{'OK ' if ok else 'FAIL'} {name}" + ("" if ok else f" -> {detail}"))


def consecutive(nums):
    return len(set(nums)) == len(nums) and sorted(nums) == list(range(min(nums), min(nums) + len(nums)))


for _ in range(30):
    try:
        requests.get(B.rsplit("/api", 1)[0] + "/", timeout=1)
        break
    except Exception:
        time.sleep(0.5)

r = requests.post(f"{B}/auth/login", json={"email": "admin@boltrex.com", "password": ADMIN_PASSWORD})
assert r.ok, r.text
H = {"Authorization": f"Bearer {r.json()['access_token']}"}

requests.post(f"{B}/clients", headers=H, json={"document_type": "CC", "document_number": "4444", "first_name": "C", "last_name": "T"})
requests.post(f"{B}/products", headers=H, json={"barcode": "CNT1", "name": "P", "category": "Otros", "purchase_price": 1,
                                                "tax_rate": 0, "prices": [{"price_list_name": "default", "price": 2}]})
item = {"barcode": "CNT1", "product_name": "P", "quantity": 100, "unit_cost": 1, "total": 100}


def purchase(_=None):
    r = requests.post(f"{B}/purchases", headers=H, json={"supplier_name": "Prov", "items": [item]})
    return r.json()["purchase_number"] if r.ok else f"ERROR {r.status_code}"


print(f"== {N} compras simultáneas ==")
with ThreadPoolExecutor(max_workers=N) as pool:
    numbers = list(pool.map(purchase, range(N)))
check(f"las {N} compras se crearon", all(n.startswith("PUR-") for n in numbers), numbers)
nums = [int(n.split("-")[1]) for n in numbers if n.startswith("PUR-")]
check(f"{N} números distintos y consecutivos", consecutive(nums), sorted(nums))

print("== Continuidad con datos previos al contador ==")
last = max(nums)
mongo.counters.delete_one({"_id": "purchase_id"})  # simula una BD creada antes de existir el contador
n = purchase()
check(f"sin contador, continúa desde la última compra (PUR-{last + 1:06d})", n == f"PUR-{last + 1:06d}", n)
check("el contador quedó creado", mongo.counters.find_one({"_id": "purchase_id"}) is not None)

print(f"== {N} ventas simultáneas ==")
requests.post(f"{B}/purchases/{n}/confirm", headers=H)  # stock suficiente para todas
line = {"barcode": "CNT1", "product_name": "P", "quantity": 1, "unit_price": 0, "tax_rate": 0, "subtotal": 0, "tax_amount": 0, "total": 0}


def sale(_):
    r = requests.post(f"{B}/invoices", headers=H, json={"client_document": "4444", "payment_status": "pagado",
                                                        "payment_method": "Efectivo", "items": [line]})
    return r.json()["invoice_number"] if r.ok else f"ERROR {r.status_code}"


counter_doc = mongo.counters.find_one({"_id": "invoice_id"})
last_invoice = mongo.invoices.find_one({}, sort=[("invoice_number", -1)])
expected_first = (counter_doc["seq"] if counter_doc else (int(last_invoice["invoice_number"].split("-")[1]) if last_invoice else 0)) + 1
with ThreadPoolExecutor(max_workers=N) as pool:
    inv_numbers = list(pool.map(sale, range(N)))
check(f"las {N} ventas se crearon", all(x.startswith("INV-") for x in inv_numbers), inv_numbers)
inv_nums = [int(x.split("-")[1]) for x in inv_numbers if x.startswith("INV-")]
check(f"{N} facturas con números distintos y consecutivos", consecutive(inv_nums), sorted(inv_nums))
check(f"la numeración continúa justo después de la última (INV-{expected_first:06d})", min(inv_nums) == expected_first, (min(inv_nums), expected_first))
dups = list(mongo.purchases.aggregate([{"$group": {"_id": "$purchase_number", "n": {"$sum": 1}}}, {"$match": {"n": {"$gt": 1}}}]))
check("ningún purchase_number duplicado en la BD", not dups, dups)

print(f"\n{sum(results)}/{len(results)} pruebas OK")
sys.exit(0 if all(results) else 1)
