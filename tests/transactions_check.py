"""Pruebas de los flujos transaccionales (backlog P0.1): compra, venta, devolución y abono.

Uso (contra una BD de PRUEBA sembrada con init_rbac.py + seed_data.py):
    DB_NAME=boltrex_txtest backend/.venv/bin/uvicorn main:app --app-dir backend --port 8001
    BOLTREX_API=http://localhost:8001/api DB_NAME=boltrex_txtest \
        backend/.venv/bin/python tests/transactions_check.py

Parte 1 (API): verifica stock, movimientos, saldos y consecutivos tras cada flujo.
Parte 2 (rollback): solo si MongoDB es replica set; comprueba que una excepción a mitad de
`run_in_transaction` no deja escrituras aplicadas.
"""
import os
# Contraseña del admin de la BD de prueba (ver tests/prepare_test_db.sh). Ya no existe admin123 (P1.10).
ADMIN_PASSWORD = os.environ.get("BOLTREX_ADMIN_PASSWORD", "Prueba-Admin-2026")
import asyncio
import os
import sys
import time
import uuid
from pathlib import Path

import requests

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

r = requests.post(f"{B}/auth/login", json={"email": "admin@boltrex.com", "password": ADMIN_PASSWORD})
assert r.ok, r.text
H = {"Authorization": f"Bearer {r.json()['access_token']}"}

tag = uuid.uuid4().hex[:6].upper()
barcode, doc = f"TX{tag}", f"9{int(tag, 16)}"


def stock():
    return requests.get(f"{B}/products/{barcode}", headers=H).json()["stock"]


def movements():
    return requests.get(f"{B}/inventory/movements", params={"barcode": barcode, "page_size": 200}, headers=H).json()["items"]


print("== Preparación ==")
check("crear cliente", requests.post(f"{B}/clients", headers=H, json={
    "document_type": "CC", "document_number": doc, "first_name": "Tx", "last_name": "Test"}).ok)
check("crear producto", requests.post(f"{B}/products", headers=H, json={
    "barcode": barcode, "name": "Producto Tx", "category": "Otros", "purchase_price": 100, "tax_rate": 19,
    "prices": [{"price_list_name": "default", "price": 200}]}).ok)

print("== Compra ==")
r = requests.post(f"{B}/purchases", headers=H, json={"supplier_name": "Prov Tx", "items": [
    {"barcode": barcode, "product_name": "Producto Tx", "quantity": 10, "unit_cost": 100, "total": 1000}]})
pn = r.json()["purchase_number"]
r = requests.post(f"{B}/purchases/{pn}/confirm", headers=H)
check("confirmar compra", r.ok and r.json()["status"] == "confirmado", r.text)
check("stock = 10 tras compra", stock() == 10, stock())
r = requests.post(f"{B}/purchases/{pn}/confirm", headers=H)
check("segunda confirmación rechazada (400)", r.status_code == 400, r.status_code)
check("stock sigue en 10 (no se duplicó)", stock() == 10, stock())

print("== Venta ==")
item = lambda q: {"barcode": barcode, "product_name": "x", "quantity": q, "unit_price": 0, "tax_rate": 0,
                  "subtotal": 0, "tax_amount": 0, "total": 0}
r = requests.post(f"{B}/invoices", headers=H, json={"client_document": doc, "payment_status": "por_cobrar", "items": [item(3)]})
check("venta a crédito", r.ok, r.text)
inv = r.json()
check("total calculado en servidor (3×200 + 19%)", abs(inv["total"] - 714.0) < 1e-6, inv.get("total"))
check("saldo = total", abs(inv["balance"] - inv["total"]) < 1e-6)
check("stock = 7 tras venta", stock() == 7, stock())
n1 = int(inv["invoice_number"].split("-")[1])

r = requests.post(f"{B}/invoices", headers=H, json={"client_document": doc, "payment_status": "por_cobrar", "items": [item(999)]})
check("venta sin stock rechazada (400)", r.status_code == 400, r.status_code)
check("stock sigue en 7", stock() == 7, stock())

r = requests.post(f"{B}/invoices", headers=H, json={"client_document": doc, "payment_status": "pagado",
                                                     "payment_method": "Efectivo", "items": [item(1)]})
check("venta de contado", r.ok, r.text)
n2 = int(r.json()["invoice_number"].split("-")[1])
check("consecutivo sin huecos tras venta fallida", n2 == n1 + 1, (n1, n2))
check("stock = 6", stock() == 6, stock())

print("== Abono ==")
r = requests.post(f"{B}/fios/{inv['invoice_number']}/payment", headers=H, json={"amount": 300, "payment_method": "Efectivo"})
check("abono registrado", r.ok, r.text)
f = requests.get(f"{B}/invoices/{inv['invoice_number']}", headers=H).json()
check("saldo = 414 tras abono de 300", abs(f["balance"] - 414.0) < 1e-6, f["balance"])
check("abono en historial", len(f["payments_history"]) == 1)
r = requests.post(f"{B}/fios/{inv['invoice_number']}/payment", headers=H, json={"amount": 10_000, "payment_method": "Efectivo"})
check("abono mayor al saldo rechazado (400)", r.status_code == 400, r.status_code)

print("== Devolución ==")
r = requests.post(f"{B}/returns", headers=H, json={"invoice_number": inv["invoice_number"], "items": [
    {"barcode": barcode, "product_name": "Producto Tx", "quantity": 1, "unit_price": 238, "total": 238}]})
check("devolución registrada", r.ok, r.text)
f = requests.get(f"{B}/invoices/{inv['invoice_number']}", headers=H).json()
check("factura en partial_return", f["status"] == "partial_return", f["status"])
check("saldo = 176 (476 − 300)", abs(f["balance"] - 176.0) < 1e-6, f["balance"])
check("stock = 7 tras devolución", stock() == 7, stock())
kinds = sorted(m["movement_type"] for m in movements())
check("movimientos: 1 compra, 2 ventas, 1 devolución", kinds == ["purchase", "return", "sale", "sale"], kinds)

print("== Rollback real (requiere replica set) ==")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from core.database import db  # noqa: E402
from core.transactions import run_in_transaction, transactions_supported  # noqa: E402



async def rollback_test():
    if not await transactions_supported():
        print("SKIP MongoDB standalone: sin transacciones, no aplica")
        return
    marker = f"rollback-{tag}"

    async def work(session):
        await db.inventory_movements.insert_one({"barcode": marker, "movement_type": "test"}, session=session)
        await db.products.update_one({"barcode": barcode}, {"$inc": {"stock": 1000}}, session=session)
        raise RuntimeError("fallo simulado a mitad de la transacción")

    try:
        await run_in_transaction(work)
        check("la excepción se propaga", False)
    except RuntimeError:
        check("la excepción se propaga", True)
    check("insert revertido", await db.inventory_movements.count_documents({"barcode": marker}) == 0)
    p = await db.products.find_one({"barcode": barcode})
    check("update de stock revertido (sigue en 7)", p["stock"] == 7, p["stock"])

asyncio.run(rollback_test())

print(f"\n{sum(results)}/{len(results)} pruebas OK")
sys.exit(0 if all(results) else 1)
