"""Pruebas de alertas (campana) y stock mínimo general / por producto (backlog P2.34).

    source tests/test_env.sh
    DB_NAME=boltrex_altest tests/prepare_test_db.sh
    DB_NAME=boltrex_altest backend/.venv/bin/uvicorn main:app --app-dir backend --port 8001
    BOLTREX_API=http://localhost:8001/api DB_NAME=boltrex_altest backend/.venv/bin/python tests/alerts_check.py
"""
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

import pymongo
import requests

ADMIN_PASSWORD = os.environ.get("BOLTREX_ADMIN_PASSWORD", "Prueba-Admin-2026")
DB_NAME = os.environ["DB_NAME"]
if DB_NAME == "boltrex":
    sys.exit("Negado: usa una BD de prueba.")
mongo = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017/?directConnection=true"), tz_aware=True)[DB_NAME]
B = os.environ.get("BOLTREX_API", "http://localhost:8001/api")
OFFSET = 300
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"{'OK ' if ok else 'FAIL'} {name}" + ("" if ok else f" -> {detail}"))


def login(email, pw):
    r = requests.post(f"{B}/auth/login", json={"email": email, "password": pw},
                      headers={"X-Real-IP": f"10.5.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"})
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
PAN, LECHE = f"PAN{tag}", f"LEC{tag}"
r = requests.post(f"{B}/products", headers=A, json={"barcode": PAN, "name": f"Pan {tag}", "category": "Otros", "purchase_price": 100, "tax_rate": 0,
                                                   "min_stock": 20, "prices": [{"price_list_name": "default", "price": 200}]})
assert r.ok, r.text
r = requests.post(f"{B}/products", headers=A, json={"barcode": LECHE, "name": f"Leche {tag}", "category": "Otros", "purchase_price": 2000, "tax_rate": 0,
                                                   "prices": [{"price_list_name": "default", "price": 3000}]})
assert r.ok, r.text
check("stock mínimo negativo → 422", requests.post(f"{B}/products", headers=A, json={"barcode": f"X{tag}", "name": "X", "category": "Otros",
      "purchase_price": 1, "tax_rate": 0, "min_stock": -1, "prices": [{"price_list_name": "default", "price": 2}]}).status_code == 422)
pn = requests.post(f"{B}/purchases", headers=A, json={"supplier_name": "Proveedor", "items": [
    {"barcode": PAN, "product_name": "Pan", "quantity": 25, "unit_cost": 100, "total": 2500},
    {"barcode": LECHE, "product_name": "Leche", "quantity": 12, "unit_cost": 2000, "total": 24000}]}).json()["purchase_number"]
requests.post(f"{B}/purchases/{pn}/confirm", headers=A)
n = int(tag, 16)
DOC = f"8{n}"
requests.post(f"{B}/clients", headers=A, json={"document_type": "CC", "document_number": DOC, "first_name": "Cliente", "last_name": "Alertas"})

PW = "Vendedor-Alertas-1"
V = f"alertas_{tag.lower()}@example.com"
requests.post(f"{B}/rbac/users", headers=A, json={"email": V, "password": PW, "first_name": "Vendedor", "last_name": "Alertas"})
requests.post(f"{B}/rbac/users/{V}/roles", headers=A, json=["Vendedor"])
HV = login(V, PW)
# Rol sin inventario, productos ni Fios: no debe ver alertas.
ROLE = f"SoloCaja{tag}"
mongo.roles.insert_one({"name": ROLE, "description": "prueba", "is_active": True, "created_at": datetime.now(timezone.utc)})
mongo.role_permissions.insert_one({"role_name": ROLE, "module_slug": "pos", "permissions": {"read": True, "create": True, "update": False, "delete": False}})
C = f"solocaja_{tag.lower()}@example.com"
requests.post(f"{B}/rbac/users", headers=A, json={"email": C, "password": PW, "first_name": "Solo", "last_name": "Caja"})
requests.post(f"{B}/rbac/users/{C}/roles", headers=A, json=[ROLE])
HC = login(C, PW)


def sell(h, code, qty, status="pagado"):
    body = {"client_document": DOC, "client_document_type": "CC", "payment_status": status,
            "items": [{"barcode": code, "product_name": "x", "quantity": qty, "unit_price": 0, "tax_rate": 0, "subtotal": 0, "tax_amount": 0, "total": 0}]}
    if status == "pagado":
        body["payment_method"] = "Efectivo"
    return requests.post(f"{B}/invoices", headers=h, json=body)


def adjust(kind, reason, code, qty):
    r = requests.post(f"{B}/inventory/adjustments", headers=A, json={"kind": kind, "reason": reason, "items": [{"barcode": code, "quantity": qty}]})
    assert r.ok, r.text


def alerts(h):
    r = requests.get(f"{B}/alerts", headers=h)
    assert r.ok, r.text
    return r.json()


def item(a, code):
    return next((i for i in a["groups"].get("stock", {}).get("items", []) if i["barcode"] == code), None)


def low_row(code):
    """Estado de un producto por el filtro «Bajo stock» de Inventario (no depende de que entre en los 5 de la campana:
    con datos de otras baterías puede haber más productos bajos)."""
    rows = requests.get(f"{B}/inventory", headers=A, params={"search": code, "stock": "low"}).json()["items"]
    return next((p for p in rows if p["barcode"] == code), None)


def stock_keys_new(a):
    return a["groups"].get("stock", {}).get("new", 0)


# --- 1. Stock mínimo general (Config. Sistema) ---
s = requests.get(f"{B}/inventory/settings", headers=HV).json()
check("stock mínimo general por defecto = 10 (lo lee cualquiera)", s.get("low_stock_threshold") == 10, s)
r = requests.put(f"{B}/inventory/settings", headers=HV, json={"low_stock_threshold": 3})
check("un vendedor no puede cambiarlo (403 con motivo)", r.status_code == 403 and "administradores" in r.json()["detail"], r.text)
r = requests.put(f"{B}/inventory/settings", headers=A, json={"low_stock_threshold": -1})
check("negativo → 400", r.status_code == 400, r.text)

# --- 2. Reglas: Pan mínimo propio 20 (stock 25), Leche usa el general 10 (stock 12) ---
inv = requests.get(f"{B}/inventory", headers=A, params={"search": tag}).json()
by = {p["barcode"]: p for p in inv["items"]}
check("Inventario trae el mínimo efectivo (Pan 20 propio, Leche 10 general) y estado normal",
      by[PAN]["min_stock_effective"] == 20 and by[LECHE]["min_stock_effective"] == 10
      and by[PAN]["stock_status"] == "ok" and by[LECHE]["stock_status"] == "ok", by)
r = sell(A, PAN, 6)
w = r.json().get("stock_warnings")
check("venta de 6 panes (queda 19 < 20) → aviso del POS «bajo stock»", r.ok and w and w[0]["barcode"] == PAN and w[0]["status"] == "low"
      and w[0]["stock"] == 19 and w[0]["min_stock"] == 20, w)
r = sell(A, LECHE, 1)
check("venta de 1 leche (queda 11 ≥ 10) → sin aviso", r.ok and r.json().get("stock_warnings") == [], r.json().get("stock_warnings"))
low = requests.get(f"{B}/inventory", headers=A, params={"search": tag, "stock": "low"}).json()
check("filtro «Bajo stock» usa el mínimo de cada producto (Pan sí, Leche no)", [p["barcode"] for p in low["items"]] == [PAN], low["items"])
csv_txt = requests.get(f"{B}/reports/inventory/export", headers=A).content.decode("utf-8-sig")
row = next(l for l in csv_txt.splitlines() if l.startswith(PAN))
check("el CSV de inventario trae stock_minimo y bajo_stock por producto", "stock_minimo" in csv_txt.splitlines()[0] and row.endswith("20,sí"), row)

# --- 3. Campana: alertas de stock con «visto» ---
a = alerts(A)
pi = item(a, PAN)
check("campana del admin: Pan en bajo stock (19 de mín. 20) como nuevo", pi and pi["status"] == "low" and pi["is_new"] and a["new"] >= 1, pi)
check("…la Leche no aparece", item(a, LECHE) is None)
requests.post(f"{B}/alerts/seen", headers=A)
a = alerts(A)
check("«Marcar como visto» → 0 nuevas, pero la alerta sigue en la lista", a["new"] == 0 and item(a, PAN) is not None, (a["new"], item(a, PAN)))
check("…lo visto es por usuario: el vendedor todavía la ve como nueva", item(alerts(HV), PAN)["is_new"] is True)
adjust("salida", "Daño", PAN, 19)
a = alerts(A)
pi = item(a, PAN)
check("empeora (bajo → agotado) → vuelve a ser nueva", pi and pi["status"] == "out" and pi["is_new"] and stock_keys_new(a) == 1, (pi, stock_keys_new(a)))
requests.post(f"{B}/alerts/seen", headers=A)
adjust("entrada", "Sobrante encontrado", PAN, 30)
check("al reponer (30 ≥ 20) la alerta desaparece sola", item(alerts(A), PAN) is None)
adjust("salida", "Merma", PAN, 15)
pi = item(alerts(A), PAN)
check("si vuelve a bajar (15 < 20) avisa de nuevo aunque se había visto antes", pi and pi["status"] == "low" and pi["is_new"], pi)

# --- 4. Cambiar el general y quitar el mínimo propio ---
requests.put(f"{B}/inventory/settings", headers=A, json={"low_stock_threshold": 16})
check("general 16 → la Leche (11) entra en bajo stock", (low_row(LECHE) or {}).get("min_stock_effective") == 16
      and alerts(A)["groups"]["stock"]["count"] >= 2)
check("…queda en la auditoría", mongo.audit_log.find_one({"module": "inventory", "entity_id": "configuracion"}) is not None)
r = requests.put(f"{B}/products/{PAN}", headers=A, json={"min_stock": None})
check("quitar el mínimo propio del Pan → usa el general (16; Pan 15 queda bajo)", r.ok and "min_stock" not in mongo.products.find_one({"barcode": PAN})
      and (low_row(PAN) or {}).get("min_stock_effective") == 16, r.text)
r = requests.put(f"{B}/products/{PAN}", headers=A, json={"min_stock": 5})
check("ponerle mínimo 5 → Pan (15) ya no está bajo", r.ok and item(alerts(A), PAN) is None, r.text)
requests.put(f"{B}/inventory/settings", headers=A, json={"low_stock_threshold": 10})
dash = requests.get(f"{B}/dashboard/summary", headers=A, params={"tz_offset_minutes": OFFSET}).json()["stock"]
summ = requests.get(f"{B}/inventory", headers=A).json()["summary"]
check("Dashboard e Inventario cuentan lo mismo con la regla nueva", dash["low_stock_count"] == summ["low_stock_count"]
      and dash["threshold"] == 10, (dash, summ))

# --- 5. Créditos: vencidos y por vencer, por separado ---
od = sell(A, LECHE, 1, status="por_cobrar").json()["invoice_number"]
so = sell(A, LECHE, 1, status="por_cobrar").json()["invoice_number"]
far = sell(A, LECHE, 1, status="por_cobrar").json()["invoice_number"]


def eod(days):
    d = (datetime.now(timezone.utc) - timedelta(minutes=OFFSET)).date() + timedelta(days=days)
    return datetime(d.year, d.month, d.day, 23, 59, 59, 999000, tzinfo=timezone.utc) + timedelta(minutes=OFFSET)


mongo.invoices.update_one({"invoice_number": od}, {"$set": {"due_date": eod(-10)}})
mongo.invoices.update_one({"invoice_number": so}, {"$set": {"due_date": eod(2)}})
mongo.invoices.update_one({"invoice_number": far}, {"$set": {"due_date": eod(30)}})
a = alerts(A)
o = a["groups"]["overdue"]
s = a["groups"]["due_soon"]
oi = next((i for i in o["items"] if i["client_document"] == DOC), None)
si = next((i for i in s["items"] if i["invoice_number"] == so), None)
check("grupo «vencidos»: el cliente con $3.000 vencidos hace 10 días (nuevo)", oi and oi["balance"] == 3000 and oi["max_days_overdue"] == 10
      and oi["is_new"], oi)
check("grupo «por vencer» separado: la factura que vence en 2 días", si and si["label"] == "Vence en 2 días" and s["due_soon_days"] == 5, si)
check("…la que vence en 30 días no alerta", all(i["invoice_number"] != far for i in s["items"]))
requests.post(f"{B}/alerts/seen", headers=A)
check("visto → 0 nuevas", alerts(A)["new"] == 0)
mongo.invoices.update_one({"invoice_number": od}, {"$set": {"due_date": eod(-45)}})
a = alerts(A)
oi = next(i for i in a["groups"]["overdue"]["items"] if i["client_document"] == DOC)
check("el atraso pasa de 1–30 a 31–60 días → vuelve a ser nueva", oi["is_new"] and a["groups"]["overdue"]["new"] == 1, oi)
requests.post(f"{B}/alerts/seen", headers=A)
mongo.invoices.update_one({"invoice_number": so}, {"$set": {"due_date": eod(-1)}})
a = alerts(A)
check("la «por vencer» se vence → sale de «por vencer» y el cliente vuelve a ser nuevo en «vencidos»",
      all(i["invoice_number"] != so for i in a["groups"]["due_soon"]["items"]) and a["groups"]["overdue"]["new"] == 1
      and next(i for i in a["groups"]["overdue"]["items"] if i["client_document"] == DOC)["invoices"] == 2, a["groups"])
requests.post(f"{B}/fios/{od}/payment", headers=A, json={"amount": 3000, "payment_method": "Efectivo"})
requests.post(f"{B}/fios/{so}/payment", headers=A, json={"amount": 3000, "payment_method": "Efectivo"})
a = alerts(A)
check("al pagar, la alerta de crédito desaparece", all(i["client_document"] != DOC for i in a["groups"]["overdue"]["items"]))
# Pagar una de dos vencidas no vuelve «nueva» la otra.
x1 = sell(A, LECHE, 1, status="por_cobrar").json()["invoice_number"]
x2 = sell(A, LECHE, 1, status="por_cobrar").json()["invoice_number"]
mongo.invoices.update_many({"invoice_number": {"$in": [x1, x2]}}, {"$set": {"due_date": eod(-3)}})
requests.post(f"{B}/alerts/seen", headers=A)
requests.post(f"{B}/fios/{x1}/payment", headers=A, json={"amount": 3000, "payment_method": "Efectivo"})
oi = next(i for i in alerts(A)["groups"]["overdue"]["items"] if i["client_document"] == DOC)
check("pagar una de dos facturas vencidas no vuelve «nueva» la otra", oi["invoices"] == 1 and oi["is_new"] is False, oi)

# --- 6. Quién ve qué ---
av = alerts(HV)
check("el vendedor (inventario + Fios) ve los grupos de stock y créditos", set(av["groups"]) == {"stock", "overdue", "due_soon"}, list(av["groups"]))
ac = alerts(HC)
check("un rol sin inventario, productos ni Fios no ve alertas", ac["groups"] == {} and ac["total"] == 0 and ac["new"] == 0, ac)
check("«visto» sin alertas no falla", requests.post(f"{B}/alerts/seen", headers=HC).ok)
check("sin sesión → rechazado (401/403, como el resto de la API)", requests.get(f"{B}/alerts").status_code in (401, 403))

ok = sum(results)
print(f"\n{ok}/{len(results)} pruebas OK")
sys.exit(0 if ok == len(results) else 1)
