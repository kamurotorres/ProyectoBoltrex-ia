"""Pruebas de compras (rama compras-estilo-pos): crear, editar, confirmar (stock + costo + avisos) y lector.

    BOLTREX_API=http://localhost:8001/api DB_NAME=boltrex_cimaintest backend/.venv/bin/python tests/purchases_check.py
    (o scripts/run_all_tests.sh purchases)
"""
import os
import sys
import time
import uuid

import pymongo
import requests

ADMIN_PASSWORD = os.environ.get("BOLTREX_ADMIN_PASSWORD", "Prueba-Admin-2026")
DB_NAME = os.environ["DB_NAME"]
if DB_NAME == "boltrex":
    sys.exit("Negado: usa una BD de prueba.")
mongo = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017/?directConnection=true"), tz_aware=True)[DB_NAME]
B = os.environ.get("BOLTREX_API", "http://localhost:8001/api")
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"{'OK ' if ok else 'FAIL'} {name}" + ("" if ok else f" -> {detail}"))


def login(email, pw):
    r = requests.post(f"{B}/auth/login", json={"email": email, "password": pw},
                      headers={"X-Real-IP": f"10.7.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"})
    assert r.ok, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


for _ in range(30):
    try:
        requests.get(B.rsplit("/api", 1)[0] + "/", timeout=1)
        break
    except Exception:
        time.sleep(0.5)

A = login("admin@boltrex.com", ADMIN_PASSWORD)
tag = uuid.uuid4().hex[:6].upper()
GAS, PAN, REG = f"GAS{tag}", f"PAN{tag}", f"REG{tag}"
for code, name, cost, prices in ((GAS, "Gaseosa", 1000, [{"price_list_name": "default", "price": 1500}]),
                                 (PAN, "Pan", 500, [{"price_list_name": "default", "price": 800}]),
                                 (REG, "Regalo", 300, [{"price_list_name": "default", "price": 400}])):
    r = requests.post(f"{B}/products", headers=A, json={"barcode": code, "name": name, "category": "Otros", "purchase_price": cost,
                                                       "tax_rate": 0, "prices": prices})
    assert r.ok, r.text


def product(code):
    return mongo.products.find_one({"barcode": code}, {"_id": 0})


# --- 1. Lector de código de barras: búsqueda por código EXACTO ---
r = requests.get(f"{B}/products", headers=A, params={"barcode": GAS})
check("lector: código exacto encuentra 1 producto", r.ok and [p["barcode"] for p in r.json()["items"]] == [GAS], r.text[:200])
r = requests.get(f"{B}/products", headers=A, params={"barcode": GAS[:-1]})
check("lector: código parcial no encuentra nada (no agrega el producto equivocado)", r.ok and r.json()["items"] == [], r.text[:200])
r = requests.get(f"{B}/products/NOEXISTE{tag}", headers=A)
check("producto inexistente: mensaje en español", r.status_code == 404 and r.json()["detail"] == "Producto no encontrado", r.text)

# --- 2. Crear y editar el borrador (no toca stock ni costo) ---
items = [{"barcode": GAS, "product_name": "Gaseosa", "quantity": 10, "unit_cost": 1200, "total": 12000},
         {"barcode": PAN, "product_name": "Pan", "quantity": 5, "unit_cost": 500, "total": 2500}]
r = requests.post(f"{B}/purchases", headers=A, json={"supplier_name": "Postobón", "items": items})
check("crear compra: queda en borrador", r.ok and r.json()["status"] == "borrador" and r.json()["total"] == 14500, r.text[:200])
pn = r.json()["purchase_number"]
check("borrador: no cambia stock ni costo", product(GAS)["stock"] == 0 and product(GAS)["purchase_price"] == 1000)
items.append({"barcode": REG, "product_name": "Regalo", "quantity": 2, "unit_cost": 0, "total": 0})
r = requests.put(f"{B}/purchases/{pn}", headers=A, json={"items": items})
check("editar borrador: agrega una línea de regalo", r.ok and len(r.json()["items"]) == 3, r.text[:200])

# --- 3. Confirmar: stock, movimientos, costo y avisos ---
r = requests.post(f"{B}/purchases/{pn}/confirm", headers=A)
check("confirmar: responde 200", r.ok, r.text[:300])
body = r.json() if r.ok else {}
check("confirmar: stock sumado", (product(GAS)["stock"], product(PAN)["stock"], product(REG)["stock"]) == (10, 5, 2))
check("confirmar: un movimiento de compra por línea",
      mongo.inventory_movements.count_documents({"reference": pn, "movement_type": "purchase"}) == 3)
check("confirmar: el costo de Gaseosa pasa a $1.200", product(GAS)["purchase_price"] == 1200, product(GAS)["purchase_price"])
check("confirmar: Pan con el mismo costo no cambia", product(PAN)["purchase_price"] == 500)
check("confirmar: la línea de regalo ($0) no cambia el costo", product(REG)["purchase_price"] == 300)
check("respuesta: costos cambiados", body.get("cost_changes") == [{"barcode": GAS, "name": "Gaseosa", "old_cost": 1000.0, "new_cost": 1200.0}],
      body.get("cost_changes"))
check("respuesta: sin avisos de precio (1.500 ≥ 1.200)", body.get("price_warnings") == [], body.get("price_warnings"))
log = mongo.audit_log.find_one({"module": "purchases", "action": "confirm", "entity_id": pn})
check("auditoría: registra el cambio de costo", log and "costo actualizado en 1 producto(s): Gaseosa $1.000 → $1.200" in log.get("summary", ""),
      log and log.get("summary"))

# --- 4. Costo nuevo por encima del precio de venta: avisa (no bloquea) ---
r = requests.post(f"{B}/purchases", headers=A, json={"supplier_name": "Postobón", "items": [
    {"barcode": GAS, "product_name": "Gaseosa", "quantity": 1, "unit_cost": 1600, "total": 1600}]})
pn2 = r.json()["purchase_number"]
r = requests.post(f"{B}/purchases/{pn2}/confirm", headers=A)
body = r.json() if r.ok else {}
check("costo > precio de venta: se confirma igual", r.ok and product(GAS)["purchase_price"] == 1600 and product(GAS)["stock"] == 11, r.text[:200])
check("costo > precio de venta: avisa la lista a revisar",
      body.get("price_warnings") == [{"barcode": GAS, "name": "Gaseosa", "new_cost": 1600.0, "prices": [{"price_list_name": "default", "price": 1500.0}]}],
      body.get("price_warnings"))

# --- 5. No se confirma dos veces ---
r = requests.post(f"{B}/purchases/{pn2}/confirm", headers=A)
check("confirmar dos veces: 400 y el stock no cambia", r.status_code == 400 and r.json()["detail"] == "Esta compra ya está confirmada"
      and product(GAS)["stock"] == 11, r.text)
r = requests.put(f"{B}/purchases/{pn2}", headers=A, json={"supplier_name": "Otro"})
check("compra confirmada: no se edita", r.status_code == 400, r.text)

total = len(results)
passed = sum(results)
print(f"\n{passed}/{total} pruebas OK")
sys.exit(0 if passed == total else 1)
