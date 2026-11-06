"""Pruebas de referencias por nombre (backlog P0.6): renombrar propaga, borrar en uso se bloquea
con un mensaje explicativo (que el frontend muestra tal cual).

Uso (contra una BD de PRUEBA sembrada con init_rbac.py + seed_data.py):
    DB_NAME=boltrex_reftest backend/.venv/bin/uvicorn main:app --app-dir backend --port 8001
    BOLTREX_API=http://localhost:8001/api backend/.venv/bin/python tests/references_check.py
"""
import os
# Contraseña del admin de la BD de prueba (ver tests/prepare_test_db.sh). Ya no existe admin123 (P1.10).
ADMIN_PASSWORD = os.environ.get("BOLTREX_ADMIN_PASSWORD", "Prueba-Admin-2026")
import os
import sys
import time
import uuid
from urllib.parse import quote

import requests


B = os.environ.get("BOLTREX_API", "http://localhost:8001/api")
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"{'OK ' if ok else 'FAIL'} {name}" + ("" if ok else f" -> {detail}"))


def blocked(name, r, *must_contain):
    """El rechazo debe ser 400 con un `detail` de texto que explique el motivo."""
    detail = r.json().get("detail") if r.headers.get("content-type", "").startswith("application/json") else None
    ok = r.status_code == 400 and isinstance(detail, str) and all(m.lower() in detail.lower() for m in must_contain)
    check(name, ok, (r.status_code, detail))
    if ok:
        print(f"       mensaje: {detail}")


for _ in range(30):
    try:
        requests.get(B.rsplit("/api", 1)[0] + "/", timeout=1)
        break
    except Exception:
        time.sleep(0.5)

r = requests.post(f"{B}/auth/login", json={"email": "admin@boltrex.com", "password": ADMIN_PASSWORD})
assert r.ok, r.text
H = {"Authorization": f"Bearer {r.json()['access_token']}"}
t = uuid.uuid4().hex[:5]
get = lambda path: requests.get(f"{B}{path}", headers=H)
put = lambda path, body: requests.put(f"{B}{path}", headers=H, json=body)
post = lambda path, body: requests.post(f"{B}{path}", headers=H, json=body)
delete = lambda path: requests.delete(f"{B}{path}", headers=H)

print("== Categorías ==")
catA, catB = f"CatA-{t}", f"CatB-{t}"
post("/categories", {"name": catA})
post("/products", {"barcode": f"P1{t}", "name": "Prod 1", "category": catA, "purchase_price": 10, "tax_rate": 0,
                   "prices": [{"price_list_name": "default", "price": 20}]})
r = put(f"/categories/{quote(catA)}", {"name": catB, "description": "renombrada"})
check("renombrar categoría (antes daba 500)", r.ok and r.json()["name"] == catB, (r.status_code, r.text[:120]))
check("el producto sigue la categoría nueva", get(f"/products/P1{t}").json()["category"] == catB)
blocked("renombrar a un nombre que ya existe", put(f"/categories/{quote(catB)}", {"name": "Otros"}), "ya existe", "Otros")
blocked("renombrar a nombre vacío", put(f"/categories/{quote(catB)}", {"name": "   "}), "vacío")
blocked("borrar categoría en uso", delete(f"/categories/{quote(catB)}"), catB, "1 producto")
put(f"/products/P1{t}", {"category": "Otros"})
check("borrar categoría sin productos", delete(f"/categories/{quote(catB)}").ok)

print("== Listas de precios ==")
vip, premium, doc = f"vip-{t}", f"premium-{t}", f"6{int(t, 16)}"
check("crear lista", post("/price-lists", {"name": vip}).ok)
blocked("crear lista duplicada", post("/price-lists", {"name": vip}), "ya existe")
post("/clients", {"document_type": "CC", "document_number": doc, "first_name": "Vip", "last_name": "Cliente", "price_list": vip})
post("/products", {"barcode": f"P2{t}", "name": "Prod 2", "category": "Otros", "purchase_price": 10, "tax_rate": 0,
                   "prices": [{"price_list_name": "default", "price": 20}, {"price_list_name": vip, "price": 15}]})
check("renombrar lista", put(f"/price-lists/{quote(vip)}", {"name": premium}).ok)
check("el cliente quedó con la lista nueva", get(f"/clients/{doc}").json()["price_list"] == premium)
names = sorted(p["price_list_name"] for p in get(f"/products/P2{t}").json()["prices"])
check("el precio del producto quedó con la lista nueva", names == sorted(["default", premium]), names)
pn = post("/purchases", {"supplier_name": "X", "items": [{"barcode": f"P2{t}", "product_name": "Prod 2", "quantity": 5, "unit_cost": 10, "total": 50}]}).json()["purchase_number"]
post(f"/purchases/{pn}/confirm", {})
r = post("/invoices", {"client_document": doc, "payment_status": "pagado", "payment_method": "Efectivo", "items": [
    {"barcode": f"P2{t}", "product_name": "x", "quantity": 1, "unit_price": 0, "tax_rate": 0, "subtotal": 0, "tax_amount": 0, "total": 0}]})
check("el POS cobra el precio de la lista renombrada (15, no costo×1.3 = 13)", r.ok and abs(r.json()["unit_price"] if "unit_price" in r.json() else r.json()["items"][0]["unit_price"] - 15) < 1e-6,
      r.json()["items"][0]["unit_price"] if r.ok else r.text)
blocked("borrar lista en uso", delete(f"/price-lists/{quote(premium)}"), premium, "1 cliente", "1 producto")
blocked("renombrar la lista default", put("/price-lists/default", {"name": "otra"}), "default", "no se puede renombrar")
blocked("borrar la lista default", delete("/price-lists/default"), "default", "no se puede eliminar")
check("cambiar descripción de default sí se permite", put("/price-lists/default", {"description": "Precio general"}).ok)

print("== Proveedores ==")
provA, provB = f"ProvA-{t}", f"ProvB-{t}"
check("crear proveedor", post("/suppliers", {"name": provA}).ok)
blocked("crear proveedor duplicado", post("/suppliers", {"name": provA}), "ya existe")
item = {"barcode": f"P2{t}", "product_name": "Prod 2", "quantity": 1, "unit_cost": 10, "total": 10}
draft = post("/purchases", {"supplier_name": provA, "items": [item]}).json()["purchase_number"]
done = post("/purchases", {"supplier_name": provA, "items": [item]}).json()["purchase_number"]
post(f"/purchases/{done}/confirm", {})
check("renombrar proveedor", put(f"/suppliers/{quote(provA)}", {"name": provB}).ok)
check("la compra en borrador tomó el nombre nuevo", get(f"/purchases/{draft}").json()["supplier_name"] == provB)
check("la compra confirmada conserva el nombre histórico", get(f"/purchases/{done}").json()["supplier_name"] == provA)
blocked("borrar proveedor con compras en borrador", delete(f"/suppliers/{quote(provB)}"), provB, "1 compra", "borrador")
post(f"/purchases/{draft}/confirm", {})
check("borrar proveedor sin borradores", delete(f"/suppliers/{quote(provB)}").ok)

print("== Inexistentes (404 con mensaje en español) ==")
for path in ["/categories/NoExiste", "/price-lists/NoExiste", "/suppliers/NoExiste"]:
    r = delete(path)
    check(f"DELETE {path} → 404 con mensaje", r.status_code == 404 and "no encontrad" in r.json().get("detail", "").lower(), (r.status_code, r.text))

print(f"\n{sum(results)}/{len(results)} pruebas OK")
sys.exit(0 if all(results) else 1)
