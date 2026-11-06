"""Pruebas de la bitácora de auditoría (backlog P1.12).

    DB_NAME=boltrex_audtest tests/prepare_test_db.sh
    DB_NAME=boltrex_audtest backend/.venv/bin/uvicorn main:app --app-dir backend --port 8001
    BOLTREX_API=http://localhost:8001/api DB_NAME=boltrex_audtest backend/.venv/bin/python tests/audit_check.py

Usa solo la BD de prueba. Termina con un factory reset (verifica que la bitácora sobrevive).
"""
import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pymongo
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

ADMIN_PASSWORD = os.environ.get("BOLTREX_ADMIN_PASSWORD", "Prueba-Admin-2026")
DB_NAME = os.environ["DB_NAME"]
if DB_NAME == "boltrex":
    sys.exit("Negado: usa una BD de prueba.")
mongo = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017/?directConnection=true"))[DB_NAME]
B = os.environ.get("BOLTREX_API", "http://localhost:8001/api")
results = []

UA_IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
UA_WIN_CHROME = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
UA_ANDROID_TAB = "Mozilla/5.0 (Linux; Android 13; SM-X200) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"{'OK ' if ok else 'FAIL'} {name}" + ("" if ok else f" -> {detail}"))


def ip():
    return f"10.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"


def login(email, password, ua=UA_WIN_CHROME):
    r = requests.post(f"{B}/auth/login", json={"email": email, "password": password},
                      headers={"X-Real-IP": ip(), "User-Agent": ua})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}", "User-Agent": ua}


def last(module, action, **extra):
    return mongo.audit_log.find_one({"module": module, "action": action, **extra}, sort=[("at", -1)])


for _ in range(30):
    try:
        requests.get(B.rsplit("/api", 1)[0] + "/", timeout=1)
        break
    except Exception:
        time.sleep(0.5)

tag = uuid.uuid4().hex[:6].upper()

# --- 1. Navegador y dispositivo ---
from core.audit import parse_user_agent  # noqa: E402

cases = [
    (UA_IPHONE, "Safari 17", "Celular (iOS)"),
    (UA_WIN_CHROME, "Chrome 124", "PC (Windows)"),
    (UA_ANDROID_TAB, "Chrome 124", "Tablet (Android)"),
    ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36", "Chrome 124", "Celular (Android)"),
    ("Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1", "Safari 17", "Tablet (iOS)"),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) Gecko/20100101 Firefox/125.0", "Firefox 125", "PC (macOS)"),
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 Edg/124.0", "Edge 124", "PC (Windows)"),
    ("python-requests/2.31", "Script (Python)", "Otro (API)"),
    ("", "Desconocido", "Desconocido"),
]
for ua, browser, device in cases:
    got = parse_user_agent(ua)
    check(f"UA → {browser} / {device}", got == {"browser": browser, "device": device}, got)

# --- 2. Sesión ---
A = login("admin@boltrex.com", ADMIN_PASSWORD, ua=UA_IPHONE)
rec = last("auth", "login", actor_email="admin@boltrex.com")
check("login registrado con navegador y dispositivo", rec and rec["browser"] == "Safari 17" and rec["device"] == "Celular (iOS)"
      and rec.get("ip") and rec.get("session_id"), rec)

ghost = f"ghost_{tag.lower()}@example.com"
for _ in range(5):
    requests.post(f"{B}/auth/login", json={"email": ghost, "password": "mala-clave-1"}, headers={"X-Real-IP": ip()})
fails = mongo.audit_log.count_documents({"action": "login_failed", "entity_id": ghost, "success": False})
check("5 logins fallidos registrados (success=false)", fails == 5, fails)
check("bloqueo de cuenta registrado", mongo.audit_log.count_documents({"action": "login_blocked", "entity_id": ghost}) == 1)
before_429 = mongo.audit_log.count_documents({"entity_id": ghost})
for _ in range(3):
    requests.post(f"{B}/auth/login", json={"email": ghost, "password": "mala-clave-1"}, headers={"X-Real-IP": ip()})
check("reintentos durante el bloqueo (429) NO llenan la bitácora",
      mongo.audit_log.count_documents({"entity_id": ghost}) == before_429)
mongo.login_attempts.delete_many({})

# --- 3. Productos y precios ---
cat = f"CatAud{tag}"
requests.post(f"{B}/categories", headers=A, json={"name": cat, "description": "x"})
check("crear categoría registrado", last("categories", "create", entity_id=cat) is not None)
bc = f"AUD{tag}"
r = requests.post(f"{B}/products", headers=A, json={"barcode": bc, "name": "Prod Aud", "category": cat, "purchase_price": 100,
                                                    "tax_rate": 19, "prices": [{"price_list_name": "default", "price": 200}]})
check("crear producto registrado", r.ok and last("products", "create", entity_id=bc) is not None, r.text)
r = requests.put(f"{B}/products/{bc}", headers=A, json={"prices": [{"price_list_name": "default", "price": 250}], "purchase_price": 120})
rec = last("products", "update", entity_id=bc)
ch = {c["field"]: (c["before"], c["after"]) for c in (rec or {}).get("changes", [])}
check("cambio de precio: antes/después por lista", ch.get("prices.default.price") == (200, 250) and ch.get("purchase_price") == (100, 120), ch)
check("resumen legible del cambio", rec and "200 → 250" in rec["summary"], (rec or {}).get("summary"))
requests.put(f"{B}/products/{bc}", headers=A, json={"purchase_price": 120})
check("guardar sin cambios reales NO registra", mongo.audit_log.count_documents({"module": "products", "action": "update", "entity_id": bc}) == 1)
requests.put(f"{B}/categories/{cat}", headers=A, json={"name": cat + "X", "description": "x"})
rec = last("categories", "update", entity_id=cat + "X")
check("renombrar categoría registra productos afectados", rec and rec.get("details", {}).get("products_renamed") == 1, rec)
cat = cat + "X"

# --- 4. Compras, ventas, abonos, devoluciones ---
doc = f"9{int(tag, 16)}"
requests.post(f"{B}/clients", headers=A, json={"document_type": "CC", "document_number": doc, "first_name": "Cli", "last_name": "Aud"})
check("crear cliente registrado", last("clients", "create", entity_id=f"CC {doc}") is not None)
r = requests.post(f"{B}/purchases", headers=A, json={"supplier_name": "Prov Aud", "items": [
    {"barcode": bc, "product_name": "Prod Aud", "quantity": 10, "unit_cost": 100, "total": 1000}]})
pn = r.json()["purchase_number"]
requests.post(f"{B}/purchases/{pn}/confirm", headers=A)
rec = last("purchases", "confirm", entity_id=pn)
check("confirmar compra registrado con unidades", rec and "10 unidad" in rec["summary"], rec)

item = lambda q: {"barcode": bc, "product_name": "x", "quantity": q, "unit_price": 0, "tax_rate": 0, "subtotal": 0, "tax_amount": 0, "total": 0}
r = requests.post(f"{B}/invoices", headers=A, json={"client_document": doc, "payment_status": "por_cobrar", "items": [item(2)]})
inv = r.json()["invoice_number"]
rec = last("invoices", "create", entity_id=inv)
check("venta registrada (número, cliente, total)", rec and inv in rec["summary"] and "Cli Aud" in rec["summary"] and "a crédito" in rec["summary"], rec)
count_inv = mongo.audit_log.count_documents({"module": "invoices"})
r = requests.post(f"{B}/invoices", headers=A, json={"client_document": doc, "payment_status": "por_cobrar", "items": [item(999)]})
check("venta fallida (sin stock) NO deja registro (misma transacción)",
      r.status_code == 400 and mongo.audit_log.count_documents({"module": "invoices"}) == count_inv, r.status_code)
requests.post(f"{B}/fios/{inv}/payment", headers=A, json={"amount": 100, "payment_method": "Efectivo"})
rec = last("fios", "create", entity_id=inv)
check("abono registrado con saldo antes → después", rec and "→" in rec["summary"] and rec["changes"], rec)
requests.post(f"{B}/returns", headers=A, json={"invoice_number": inv, "items": [
    {"barcode": bc, "product_name": "Prod Aud", "quantity": 1, "unit_price": 297.5, "total": 297.5}]})
rec = last("returns", "create", entity_id=inv)
check("devolución registrada", rec and "parcial" in rec["summary"], rec)

# --- 5. Usuarios, roles, permisos ---
U = f"aud_{tag.lower()}@example.com"
PW = "Clave-Secreta-Aud-1"
requests.post(f"{B}/rbac/users", headers=A, json={"email": U, "password": PW, "first_name": "Aud", "last_name": "User"})
check("crear usuario registrado", last("users", "create", entity_id=U) is not None)
requests.post(f"{B}/rbac/users/{U}/roles", headers=A, json=["Vendedor"])
rec = last("users", "assign_roles", entity_id=U)
check("asignar roles registrado (+Vendedor)", rec and "+Vendedor" in rec["summary"], rec)
PW2 = "Clave-Secreta-Aud-2"
requests.put(f"{B}/rbac/users/{U}", headers=A, json={"password": PW2})
rec = last("users", "change_password", entity_id=U)
check("admin cambia contraseña → registrado sin la contraseña", rec and "contraseña" in rec["summary"], rec)
role = f"RolAud{tag}"
requests.post(f"{B}/rbac/roles", headers=A, json={"name": role, "description": "x"})
requests.post(f"{B}/rbac/permissions", headers=A, json={"role_name": role, "module_slug": "products",
                                                         "permissions": {"read": True, "create": True, "update": False, "delete": False}})
rec = last("permissions", "update", entity_name=role)
check("dar permisos registrado (concedió ver, crear)", rec and "concedió ver, crear" in rec["summary"], rec)

dump = json.dumps(list(mongo.audit_log.find({}, {"_id": 0})), default=str)
check("ninguna contraseña en la bitácora", PW not in dump and PW2 not in dump and ADMIN_PASSWORD not in dump and "mala-clave-1" not in dump)
check("ningún hash de contraseña en la bitácora", "hashed_password" not in dump and "$2b$" not in dump)

# --- 6. Acceso solo para Administrador ---
V = login(U, PW2)
r = requests.get(f"{B}/audit", headers=V)
check("no administrador → 403 con mensaje", r.status_code == 403 and "administradores" in r.json().get("detail", ""), r.text)
# Aunque tenga todos los permisos de usuarios/roles/permisos, sin el rol Administrador no entra.
G = f"gest_{tag.lower()}@example.com"
requests.post(f"{B}/rbac/users", headers=A, json={"email": G, "password": PW, "first_name": "Ge", "last_name": "St"})
for mod in ("users", "roles", "permissions"):
    requests.post(f"{B}/rbac/permissions", headers=A, json={"role_name": role, "module_slug": mod,
                                                             "permissions": {"read": True, "create": True, "update": True, "delete": True}})
requests.post(f"{B}/rbac/users/{G}/roles", headers=A, json=[role])
r = requests.get(f"{B}/audit/filters", headers=login(G, PW))
check("rol con todos los permisos pero sin Administrador → 403", r.status_code == 403, r.status_code)
check("sin token → rechazado", requests.get(f"{B}/audit").status_code in (401, 403))
for method in ("put", "delete", "patch", "post"):
    r = getattr(requests, method)(f"{B}/audit", headers=A)
    check(f"{method.upper()} /audit no existe (405)", r.status_code == 405, r.status_code)

# --- 7. Consulta, filtros y paginación ---
r = requests.get(f"{B}/audit", headers=A, params={"page_size": 5})
d = r.json()
check("listado paginado (5 por página, más reciente primero)", r.ok and len(d["items"]) == 5 and d["pages"] >= 2
      and d["items"][0]["at"] >= d["items"][-1]["at"], {k: d.get(k) for k in ("total", "pages")})
check("cada fila trae navegador y dispositivo", all("browser" in i and "device" in i for i in d["items"]))
r2 = requests.get(f"{B}/audit", headers=A, params={"page_size": 5, "page": 2}).json()
check("página 2 distinta de la 1", r2["items"] and r2["items"][0]["at"] <= d["items"][-1]["at"])
r = requests.get(f"{B}/audit", headers=A, params={"actor": U}).json()
check("filtro por usuario", r["total"] >= 1 and all(i["actor_email"] == U for i in r["items"]), r["total"])
r = requests.get(f"{B}/audit", headers=A, params={"module": "products", "q": bc}).json()
check("filtro por módulo + búsqueda por código", r["total"] == 2 and all(i["module"] == "products" for i in r["items"]), r["total"])
r = requests.get(f"{B}/audit", headers=A, params={"device": "Celular"}).json()
check("filtro por dispositivo", r["total"] >= 1 and all(i["device"].startswith("Celular") for i in r["items"]), r["total"])
r = requests.get(f"{B}/audit", headers=A, params={"success": "false"}).json()
check("filtro por resultado fallido", r["total"] >= 6 and all(i["success"] is False for i in r["items"]), r["total"])
today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
r = requests.get(f"{B}/audit", headers=A, params={"date_from": today, "date_to": today}).json()
check("filtro por fecha (hoy)", r["total"] >= 20, r["total"])
r = requests.get(f"{B}/audit", headers=A, params={"date_from": "2000-01-01", "date_to": "2000-01-02"}).json()
check("rango sin registros → 0", r["total"] == 0)
r = requests.get(f"{B}/audit", headers=A, params={"date_from": "2026-12-01", "date_to": "2026-11-01"})
check("rango invertido → 400 con mensaje", r.status_code == 400 and "desde" in r.json()["detail"], r.text)
r = requests.get(f"{B}/audit", headers=A, params={"date_from": "04/11/2026"})
check("fecha mal escrita → 400 con mensaje", r.status_code == 400 and "AAAA-MM-DD" in r.json()["detail"], r.text)
f = requests.get(f"{B}/audit/filters", headers=A).json()
check("filtros disponibles (usuarios, módulos con etiqueta)", U in f["actors"] and {"value": "products", "label": "Productos"} in f["modules"], f)

# --- 8. Retención (6 meses) ---
idx = {i["name"]: i for i in mongo.audit_log.list_indexes()}
check("índice TTL de 180 días sobre audit_log.at", idx.get("ttl_audit_log_at", {}).get("expireAfterSeconds") == 180 * 86400, idx.get("ttl_audit_log_at"))
check("retención informada a la pantalla", f.get("retention_days") == 180)

# --- 8b. Accesos denegados a secciones (P1.13) ---
r = requests.post(f"{B}/audit/access-denied", headers=V, json={"path": "/users", "section": "Usuarios"})
check("acceso denegado registrado", r.ok and r.json().get("recorded") is True, r.text)
rec = last("access", "access_denied", actor_email=U)
check("…con sección, usuario, dispositivo y success=false",
      rec and rec["entity_id"] == "/users" and "Usuarios" in rec["summary"] and rec["success"] is False and rec.get("device"), rec)
r = requests.post(f"{B}/audit/access-denied", headers=V, json={"path": "/users", "section": "Usuarios"})
check("recargar la misma sección no repite el registro (10 min)", r.ok and r.json().get("recorded") is False
      and mongo.audit_log.count_documents({"action": "access_denied", "actor_email": U, "entity_id": "/users"}) == 1, r.text)
r = requests.post(f"{B}/audit/access-denied", headers=V, json={"path": "/audit", "section": "Auditoría"})
check("otra sección sí se registra", r.ok and r.json().get("recorded") is True)
check("sin token → rechazado", requests.post(f"{B}/audit/access-denied", json={"path": "/users"}).status_code in (401, 403))
r = requests.post(f"{B}/audit/access-denied", headers=V, json={"path": "/" + "x" * 300})
check("ruta demasiado larga → 422", r.status_code == 422, r.status_code)
r = requests.get(f"{B}/audit", headers=A, params={"action": "access_denied"}).json()
check("el admin ve los accesos denegados filtrando por acción", r["total"] == 2 and all(i["actor_email"] == U for i in r["items"]), r["total"])

# --- 9. Factory reset: la bitácora sobrevive y registra el reset ---
r = requests.post(f"{B}/system/factory-reset", headers=A, json={"password": "incorrecta-123"})
rec = last("system", "factory_reset", success=False)
check("intento de reset con contraseña incorrecta registrado (y responde 401)", r.status_code == 401 and rec is not None, r.status_code)
n_before = mongo.audit_log.count_documents({})
r = requests.post(f"{B}/system/factory-reset", headers=A, json={"password": ADMIN_PASSWORD})
check("factory reset OK", r.ok, r.text)
check("la bitácora NO se borra con el reset", mongo.audit_log.count_documents({}) >= n_before + 1)
rec = last("system", "factory_reset", success=True)
check("el reset queda registrado con lo que borró", rec and rec.get("details", {}).get("deleted", {}).get("products", 0) >= 1, rec)

print(f"\n{sum(results)}/{len(results)} pruebas OK")
sys.exit(0 if all(results) else 1)
