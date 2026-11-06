"""Pruebas de stock atómico (backlog P0.2): ventas concurrentes nunca dejan stock negativo.

Uso (contra una BD de PRUEBA sembrada con init_rbac.py + seed_data.py):
    DB_NAME=boltrex_stocktest backend/.venv/bin/uvicorn main:app --app-dir backend --port 8001
    BOLTREX_API=http://localhost:8001/api backend/.venv/bin/python tests/stock_concurrency_check.py
"""
import os
# Contraseña del admin de la BD de prueba (ver tests/prepare_test_db.sh). Ya no existe admin123 (P1.10).
ADMIN_PASSWORD = os.environ.get("BOLTREX_ADMIN_PASSWORD", "Prueba-Admin-2026")
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import requests


B = os.environ.get("BOLTREX_API", "http://localhost:8001/api")
STOCK, BUYERS = 5, 20
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

r = requests.post(f"{B}/auth/login", json={"email": "admin@boltrex.com", "password": ADMIN_PASSWORD})
assert r.ok, r.text
H = {"Authorization": f"Bearer {r.json()['access_token']}"}

tag = uuid.uuid4().hex[:6].upper()
barcode, doc = f"ST{tag}", f"8{int(tag, 16)}"
requests.post(f"{B}/clients", headers=H, json={"document_type": "CC", "document_number": doc, "first_name": "St", "last_name": "Test"})
requests.post(f"{B}/products", headers=H, json={"barcode": barcode, "name": "Prod Stock", "category": "Otros",
                                                "purchase_price": 100, "tax_rate": 0, "prices": [{"price_list_name": "default", "price": 150}]})
pn = requests.post(f"{B}/purchases", headers=H, json={"supplier_name": "Prov", "items": [
    {"barcode": barcode, "product_name": "Prod Stock", "quantity": STOCK, "unit_cost": 100, "total": 100 * STOCK}]}).json()["purchase_number"]
requests.post(f"{B}/purchases/{pn}/confirm", headers=H)


def stock():
    return requests.get(f"{B}/products/{barcode}", headers=H).json()["stock"]


def line(q):
    return {"barcode": barcode, "product_name": "x", "quantity": q, "unit_price": 0, "tax_rate": 0, "subtotal": 0, "tax_amount": 0, "total": 0}


def sale(items):
    return requests.post(f"{B}/invoices", headers=H, json={"client_document": doc, "payment_status": "pagado",
                                                           "payment_method": "Efectivo", "items": items})


check(f"stock inicial = {STOCK}", stock() == STOCK, stock())

print("== Casos borde ==")
r = sale([line(-5)])
check("cantidad negativa rechazada (400)", r.status_code == 400, r.status_code)
r = sale([line(0)])
check("cantidad cero rechazada (400)", r.status_code == 400, r.status_code)
r = sale([])
check("factura sin productos rechazada (400)", r.status_code == 400, r.status_code)
r = sale([line(3), line(3)])  # cada línea pasa el chequeo temprano, juntas superan el stock
check("misma referencia repetida que supera el stock rechazada (400)", r.status_code == 400, r.status_code)
check(f"stock intacto = {STOCK} tras los rechazos", stock() == STOCK, stock())

print(f"== {BUYERS} ventas concurrentes de 1 unidad con stock {STOCK} ==")
with ThreadPoolExecutor(max_workers=BUYERS) as pool:
    codes = list(pool.map(lambda _: sale([line(1)]).status_code, range(BUYERS)))
ok, rejected = codes.count(200), codes.count(400)
check(f"exactamente {STOCK} ventas aceptadas", ok == STOCK, codes)
check(f"{BUYERS - STOCK} ventas rechazadas por stock (400)", rejected == BUYERS - STOCK, codes)
check("stock final = 0 (nunca negativo)", stock() == 0, stock())
sales = [m for m in requests.get(f"{B}/inventory/movements", params={"barcode": barcode, "page_size": 200}, headers=H).json()["items"]
         if m["movement_type"] == "sale"]
check(f"{STOCK} movimientos de venta (sin huérfanos)", len(sales) == STOCK, len(sales))
invs = requests.get(f"{B}/pos/invoices", params={"client_document": doc, "limit": 100}, headers=H).json()["invoices"]
check(f"{STOCK} facturas creadas (sin facturas sin stock)", len(invs) == STOCK, len(invs))
nums = sorted(int(i["invoice_number"].split("-")[1]) for i in invs)
check("consecutivos sin huecos ni duplicados", nums == list(range(nums[0], nums[0] + STOCK)), nums)

print(f"\n{sum(results)}/{len(results)} pruebas OK")
sys.exit(0 if all(results) else 1)
