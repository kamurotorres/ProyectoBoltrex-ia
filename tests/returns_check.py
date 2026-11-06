"""Pruebas de devoluciones validadas (backlog P0.3).

Uso (contra una BD de PRUEBA sembrada con init_rbac.py + seed_data.py):
    DB_NAME=boltrex_rettest backend/.venv/bin/uvicorn main:app --app-dir backend --port 8001
    BOLTREX_API=http://localhost:8001/api backend/.venv/bin/python tests/returns_check.py
"""
import os
# Contraseña del admin de la BD de prueba (ver tests/prepare_test_db.sh). Ya no existe admin123 (P1.10).
ADMIN_PASSWORD = os.environ.get("BOLTREX_ADMIN_PASSWORD", "Prueba-Admin-2026")
import os
import sys
import time
import uuid

import requests


B = os.environ.get("BOLTREX_API", "http://localhost:8001/api")
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"{'OK ' if ok else 'FAIL'} {name}" + ("" if ok else f" -> {detail}"))


def near(a, b):
    return abs(a - b) < 0.01


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
A, Bc, X, doc = f"RA{tag}", f"RB{tag}", f"RX{tag}", f"7{int(tag, 16)}"

# Producto A: 100 + IVA 19 %. Producto B: 50 sin IVA. Producto X: no se vende.
requests.post(f"{B}/clients", headers=H, json={"document_type": "CC", "document_number": doc, "first_name": "Ret", "last_name": "Test"})
for code, price, tax in [(A, 100, 19), (Bc, 50, 0), (X, 10, 0)]:
    requests.post(f"{B}/products", headers=H, json={"barcode": code, "name": f"Prod {code}", "category": "Otros",
                                                    "purchase_price": 1, "tax_rate": tax, "prices": [{"price_list_name": "default", "price": price}]})
pn = requests.post(f"{B}/purchases", headers=H, json={"supplier_name": "Prov", "items": [
    {"barcode": c, "product_name": c, "quantity": 10, "unit_cost": 1, "total": 10} for c in (A, Bc, X)]}).json()["purchase_number"]
requests.post(f"{B}/purchases/{pn}/confirm", headers=H)


def stock(code):
    return requests.get(f"{B}/products/{code}", headers=H).json()["stock"]


def line(code, q):
    return {"barcode": code, "product_name": "x", "quantity": q, "unit_price": 0, "tax_rate": 0, "subtotal": 0, "tax_amount": 0, "total": 0}


def invoice(n):
    return requests.get(f"{B}/invoices/{n}", headers=H).json()


def ret(items):
    return requests.post(f"{B}/returns", headers=H, json={"invoice_number": inv_no, "items": items})


print("== Venta a crédito: A×3 (100+19%) + B×2 (50) ==")
r = requests.post(f"{B}/invoices", headers=H, json={"client_document": doc, "payment_status": "por_cobrar", "items": [line(A, 3), line(Bc, 2)]})
check("venta creada", r.ok, r.text)
inv_no = r.json()["invoice_number"]
inv = invoice(inv_no)
check("subtotal 400, IVA 57, total 457", near(inv["subtotal"], 400) and near(inv["total_tax"], 57) and near(inv["total"], 457),
      (inv["subtotal"], inv["total_tax"], inv["total"]))

print("== Validaciones (todas deben rechazarse sin cambiar nada) ==")
check("producto que no está en la factura (400)", ret([{"barcode": X, "quantity": 1}]).status_code == 400)
check("cantidad cero (400)", ret([{"barcode": A, "quantity": 0}]).status_code == 400)
check("cantidad negativa (400)", ret([{"barcode": A, "quantity": -2}]).status_code == 400)
check("más de lo vendido (400)", ret([{"barcode": A, "quantity": 4}]).status_code == 400)
check("sin productos (400)", ret([]).status_code == 400)
check("factura inexistente (404)", requests.post(f"{B}/returns", headers=H, json={"invoice_number": "INV-999999", "items": [{"barcode": A, "quantity": 1}]}).status_code == 404)
inv = invoice(inv_no)
check("factura intacta tras los rechazos", near(inv["total"], 457) and inv["status"] == "completed" and not inv["returns_history"], inv["status"])
check("stock A intacto (7)", stock(A) == 7, stock(A))

print("== Devolución parcial con precio falsificado: A×1 a 99999 ==")
r = ret([{"barcode": A, "product_name": "x", "quantity": 1, "unit_price": 99999, "total": 99999}])
check("devolución aceptada", r.ok, r.text)
check("importe calculado por el servidor = 119 (no 99999)", r.ok and near(r.json()["total"], 119), r.json().get("total") if r.ok else r.text)
inv = invoice(inv_no)
check("factura en partial_return", inv["status"] == "partial_return", inv["status"])
check("subtotal 300, IVA 38, total 338 recalculados", near(inv["subtotal"], 300) and near(inv["total_tax"], 38) and near(inv["total"], 338),
      (inv["subtotal"], inv["total_tax"], inv["total"]))
check("saldo del crédito = 338", near(inv["balance"], 338), inv["balance"])
check("stock A = 8", stock(A) == 8, stock(A))

print("== Límite acumulado: quedan 2 unidades de A ==")
check("A×3 rechazado (solo quedan 2) (400)", ret([{"barcode": A, "quantity": 3}]).status_code == 400)
check("A×1 + A×2 en líneas separadas (=3) rechazado (400)", ret([{"barcode": A, "quantity": 1}, {"barcode": A, "quantity": 2}]).status_code == 400)

print("== Abono y devolución total ==")
check("abono de 100", requests.post(f"{B}/fios/{inv_no}/payment", headers=H, json={"amount": 100, "payment_method": "Efectivo"}).ok)
check("saldo = 238 tras abono", near(invoice(inv_no)["balance"], 238))
r = ret([{"barcode": A, "quantity": 2}, {"barcode": Bc, "quantity": 2}])
check("devolución del resto aceptada", r.ok, r.text)
check("importe = 338 (2×119 + 2×50)", r.ok and near(r.json()["total"], 338), r.json().get("total") if r.ok else "")
inv = invoice(inv_no)
check("factura en returned con totales en 0", inv["status"] == "returned" and inv["total"] == 0 and inv["subtotal"] == 0 and inv["total_tax"] == 0,
      (inv["status"], inv["total"]))
check("crédito cerrado: pagado, saldo 0", inv["payment_status"] == "pagado" and inv["balance"] == 0, (inv["payment_status"], inv["balance"]))
check("2 devoluciones en el historial", len(inv["returns_history"]) == 2, len(inv["returns_history"]))
check("stock restaurado: A = 10, B = 10", stock(A) == 10 and stock(Bc) == 10, (stock(A), stock(Bc)))
check("nueva devolución sobre factura devuelta rechazada (400)", ret([{"barcode": Bc, "quantity": 1}]).status_code == 400)

print("== Ticket PDF ==")
r = requests.get(f"{B}/pos/invoices/{inv_no}/ticket", headers=H)
check("ticket con devoluciones se genera (PDF)", r.ok and r.headers.get("content-type") == "application/pdf" and r.content[:4] == b"%PDF",
      (r.status_code, r.headers.get("content-type")))

print(f"\n{sum(results)}/{len(results)} pruebas OK")
sys.exit(0 if all(results) else 1)
