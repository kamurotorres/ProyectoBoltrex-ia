"""Pruebas de seguridad RBAC end-to-end.

Uso (contra una BD de PRUEBA sembrada con init_rbac.py + seed_data.py; crea y borra usuarios):
    DB_NAME=boltrex_sectest backend/.venv/bin/uvicorn main:app --app-dir backend --port 8001
    BOLTREX_API=http://localhost:8001/api backend/.venv/bin/python tests/security_rbac_check.py
"""
import os
# Contraseña del admin de la BD de prueba (ver tests/prepare_test_db.sh). Ya no existe admin123 (P1.10).
ADMIN_PASSWORD = os.environ.get("BOLTREX_ADMIN_PASSWORD", "Prueba-Admin-2026")
import os, sys, time
import requests
import os


B = os.environ.get("BOLTREX_API", "http://localhost:8001/api")
results = []

def check(name, resp, expected):
    ok = resp.status_code in (expected if isinstance(expected, tuple) else (expected,))
    results.append(ok)
    print(f"{'OK ' if ok else 'FAIL'} {resp.status_code:>3} (esperado {expected}) {name}"
          + ("" if ok else f" -> {resp.text[:150]}"))

for _ in range(30):
    try:
        requests.get(B.rsplit("/api", 1)[0] + "/", timeout=1); break
    except Exception:
        time.sleep(0.5)

def login(email, pw):
    r = requests.post(f"{B}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}

print("== Sin token ==")
check("GET /rbac/users sin token", requests.get(f"{B}/rbac/users"), (401, 403))
check("POST /rbac/users sin token (crear admin)", requests.post(f"{B}/rbac/users", json={
    "email": "hacker@x.com", "password": "x", "first_name": "h", "last_name": "h"}), (401, 403))
check("POST /rbac/users/admin@boltrex.com/roles sin token", requests.post(f"{B}/rbac/users/admin@boltrex.com/roles", json=["Vendedor"]), (401, 403))
check("GET /products sin token", requests.get(f"{B}/products"), (401, 403))
check("POST /auth/register (registro público desactivado)", requests.post(f"{B}/auth/register", json={
    "email": "nuevo@x.com", "password": "x", "full_name": "Nuevo User"}), 403)

print("== Administrador ==")
admin = login("admin@boltrex.com", ADMIN_PASSWORD)
check("GET /auth/me (bug server_rbac corregido)", requests.get(f"{B}/auth/me", headers=admin), 200)
for path in ["/products", "/clients", "/rbac/users", "/rbac/roles", "/rbac/modules", "/invoices",
             "/fios", "/purchases", "/inventory", "/reports/sales", "/dashboard/stats", "/ticket-config",
             "/payment-methods", "/payment-methods/active", "/pos/invoices", "/import/templates/products"]:
    check(f"admin GET {path}", requests.get(f"{B}{path}", headers=admin), 200)
check("admin GET /products?search=(a+)+$ (regex escapada)", requests.get(f"{B}/products", params={"search": "(a+)+$"}, headers=admin), 200)

# Crear usuarios de prueba con cada rol
for email, role in [("vend@test.com", "Vendedor"), ("super@test.com", "Supervisor")]:
    requests.delete(f"{B}/rbac/users/{email}", headers=admin)
    check(f"admin crea {role}", requests.post(f"{B}/rbac/users", headers=admin, json={
        "email": email, "password": "Pass-1234", "first_name": role, "last_name": "Test"}), 200)
    check(f"admin asigna rol {role}", requests.post(f"{B}/rbac/users/{email}/roles", headers=admin, json=[role]), 200)

# Datos mínimos para venta
requests.post(f"{B}/clients", headers=admin, json={"document_type": "CC", "document_number": "999", "first_name": "Cli", "last_name": "Test"})
requests.post(f"{B}/products", headers=admin, json={"barcode": "T1", "name": "Prod", "category": "Otros", "purchase_price": 10, "tax_rate": 19})

print("== Vendedor ==")
v = login("vend@test.com", "Pass-1234")
check("vendedor GET /auth/me", requests.get(f"{B}/auth/me", headers=v), 200)
for path in ["/products", "/clients", "/categories", "/price-lists", "/payment-methods/active", "/invoices",
             "/pos/invoices", "/fios", "/inventory", "/reports/sales", "/dashboard/stats"]:
    check(f"vendedor GET {path}", requests.get(f"{B}{path}", headers=v), 200)
check("vendedor POST /invoices (pasa permiso; falla por stock 0 => 400)", requests.post(f"{B}/invoices", headers=v, json={
    "client_document": "999", "payment_status": "por_cobrar",
    "items": [{"barcode": "T1", "product_name": "Prod", "quantity": 1, "unit_price": 0, "tax_rate": 0, "subtotal": 0, "tax_amount": 0, "total": 0}]}), 400)
check("vendedor POST /clients (tiene create)", requests.post(f"{B}/clients", headers=v, json={
    "document_type": "CC", "document_number": "998", "first_name": "A", "last_name": "B"}), 200)
for method, path, body in [
    ("get", "/rbac/users", None), ("post", "/rbac/users", {"email": "e@x.com", "password": "x", "first_name": "a", "last_name": "b"}),
    ("post", "/rbac/users/vend@test.com/roles", ["Administrador"]),
    ("post", "/rbac/permissions", {"role_name": "Vendedor", "module_slug": "users", "permissions": {"read": True, "create": True, "update": True, "delete": True}}),
    ("post", "/products", {"barcode": "X", "name": "X", "category": "Otros", "purchase_price": 1, "tax_rate": 0}),
    ("delete", "/clients/998", None), ("get", "/purchases", None), ("get", "/suppliers", None),
    ("get", "/returns", None), ("put", "/ticket-config", {"company_name": "Hack"}),
    ("post", "/payment-methods", {"name": "Hack"}), ("post", "/system/factory-reset", {"password": "Pass-1234"}),
    ("get", "/import/templates/products", None), ("post", "/tax-rates", {"name": "X", "rate": 1}),
]:
    check(f"vendedor {method.upper()} {path} (prohibido)", getattr(requests, method)(f"{B}{path}", headers=v, json=body), 403)

print("== Supervisor ==")
s = login("super@test.com", "Pass-1234")
for path in ["/purchases", "/suppliers", "/products", "/returns", "/invoices", "/ticket-config"]:
    check(f"supervisor GET {path}", requests.get(f"{B}{path}", headers=s), 200)
r = requests.post(f"{B}/purchases", headers=s, json={"supplier_name": "Prov", "items": [{"barcode": "T1", "product_name": "Prod", "quantity": 5, "unit_cost": 10, "total": 50}]})
check("supervisor POST /purchases (create)", r, 200)
pn = r.json().get("purchase_number") if r.ok else "PUR-000000"
check("supervisor confirma compra (requiere update: prohibido, igual que en la UI)", requests.post(f"{B}/purchases/{pn}/confirm", headers=s), 403)
check("admin confirma compra", requests.post(f"{B}/purchases/{pn}/confirm", headers=admin), 200)
check("supervisor DELETE /products/T1 (prohibido)", requests.delete(f"{B}/products/T1", headers=s), 403)
check("supervisor GET /rbac/users (prohibido)", requests.get(f"{B}/rbac/users", headers=s), 403)

print("== Usuario desactivado ==")
check("admin desactiva vendedor", requests.put(f"{B}/rbac/users/vend@test.com", headers=admin, json={"is_active": False}), 200)
# Desde P1.11 desactivar cierra sus sesiones: el token previo recibe 401 "Tu sesión fue cerrada".
check("token previo del vendedor desactivado", requests.get(f"{B}/products", headers=v), 401)

for email in ["vend@test.com", "super@test.com"]:
    requests.delete(f"{B}/rbac/users/{email}", headers=admin)

print(f"\n{sum(results)}/{len(results)} pruebas OK")
sys.exit(0 if all(results) else 1)
