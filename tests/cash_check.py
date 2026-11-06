"""Pruebas del control de caja (backlog P2.31).

    source tests/test_env.sh
    DB_NAME=boltrex_cjtest tests/prepare_test_db.sh
    DB_NAME=boltrex_cjtest backend/.venv/bin/uvicorn main:app --app-dir backend --port 8001
    BOLTREX_API=http://localhost:8001/api DB_NAME=boltrex_cjtest backend/.venv/bin/python tests/cash_check.py

Producto "Pan" a $200 sin IVA (costo 100). Cifras esperadas calculadas a mano.
"""
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pymongo
import requests

ADMIN_PASSWORD = os.environ.get("BOLTREX_ADMIN_PASSWORD", "Prueba-Admin-2026")
DB_NAME = os.environ["DB_NAME"]
if DB_NAME == "boltrex":
    sys.exit("Negado: usa una BD de prueba.")
mongo = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017/?directConnection=true"))[DB_NAME]
B = os.environ.get("BOLTREX_API", "http://localhost:8001/api")
results = []
EPS = 0.01


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"{'OK ' if ok else 'FAIL'} {name}" + ("" if ok else f" -> {detail}"))


def near(a, b):
    return a is not None and abs(a - b) < EPS


def login(email, pw):
    r = requests.post(f"{B}/auth/login", json={"email": email, "password": pw},
                      headers={"X-Real-IP": f"10.2.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"})
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
PAN = f"PAN{tag}"
requests.post(f"{B}/products", headers=A, json={"barcode": PAN, "name": "Pan", "category": "Otros", "purchase_price": 100, "tax_rate": 0,
                                               "prices": [{"price_list_name": "default", "price": 200}]})
pn = requests.post(f"{B}/purchases", headers=A, json={"supplier_name": "Panadería", "items": [
    {"barcode": PAN, "product_name": "Pan", "quantity": 500, "unit_cost": 100, "total": 50000}]}).json()["purchase_number"]
requests.post(f"{B}/purchases/{pn}/confirm", headers=A)
doc = f"5{int(tag, 16)}"
requests.post(f"{B}/clients", headers=A, json={"document_type": "CC", "document_number": doc, "first_name": "Cliente", "last_name": "Pan"})

PW = "Cajero-Caja-1"
VA, VB = f"caja_a_{tag.lower()}@example.com", f"caja_b_{tag.lower()}@example.com"
for email in (VA, VB):
    requests.post(f"{B}/rbac/users", headers=A, json={"email": email, "password": PW, "first_name": "Cajero", "last_name": email[5]})
    requests.post(f"{B}/rbac/users/{email}/roles", headers=A, json=["Vendedor"])
HA, HB = login(VA, PW), login(VB, PW)


def sell(h, qty, status="pagado", method="Efectivo"):
    body = {"client_document": doc, "client_document_type": "CC", "payment_status": status,
            "items": [{"barcode": PAN, "product_name": "x", "quantity": qty, "unit_price": 0, "tax_rate": 0, "subtotal": 0, "tax_amount": 0, "total": 0}]}
    if status == "pagado":
        body["payment_method"] = method
    return requests.post(f"{B}/invoices", headers=h, json=body)


def ret(h, inv, qty):
    return requests.post(f"{B}/returns", headers=h, json={"invoice_number": inv, "items": [
        {"barcode": PAN, "product_name": "Pan", "quantity": qty, "unit_price": 200, "total": 200 * qty}]})


def cash_of(summary, method="Efectivo"):
    return next((m for m in summary["methods"] if m["method"] == method), {})


# --- 1. Configuración (interruptor) ---
s = requests.get(f"{B}/cash/settings", headers=HA).json()
check("interruptor apagado por defecto y denominaciones colombianas", s["require_open_session"] is False
      and s["denominations"]["bills"][0] == 100000 and 50 in s["denominations"]["coins"], s)
r = requests.put(f"{B}/cash/settings", headers=HA, json={"require_open_session": True})
check("un cajero no puede cambiar el interruptor (403)", r.status_code == 403, r.status_code)
check("el módulo Caja existe con permisos para Vendedor", mongo.system_modules.find_one({"slug": "cash"}) is not None
      and (mongo.role_permissions.find_one({"role_name": "Vendedor", "module_slug": "cash"}) or {}).get("permissions", {}).get("update") is True)

# --- 2. Interruptor APAGADO: se vende sin caja; queda pendiente y se asocia al abrir ---
r = sell(HA, 1)
inv0 = r.json().get("invoice_number")
check("sin caja y con el interruptor apagado → se vende", r.ok, r.text)
check("…el dinero queda como movimiento pendiente (sin caja)", mongo.cash_movements.count_documents({"reference": inv0, "session_id": None}) == 1)
r = requests.post(f"{B}/cash/open", headers=HA, json={"opening_amount": 100000})
caja_a = r.json()
SA = caja_a.get("session_id")
check("abrir caja con base $100.000 → CAJ-000001", r.ok and SA and SA.startswith("CAJ-"), r.text)
check("…se asocian los movimientos pendientes (1)", caja_a.get("attached_pending") == 1, caja_a.get("attached_pending"))
check("abrir una segunda caja → 400 con mensaje", requests.post(f"{B}/cash/open", headers=HA, json={"opening_amount": 0}).status_code == 400)
with ThreadPoolExecutor(10) as ex:
    codes = list(ex.map(lambda _: requests.post(f"{B}/cash/open", headers=HB, json={"opening_amount": 50000}).status_code, range(10)))
check("10 aperturas simultáneas del mismo cajero → solo 1 caja", codes.count(200) == 1 and mongo.cash_sessions.count_documents({"cashier_email": VB}) == 1, codes)

# --- 3. Movimientos del turno de A (el ejemplo del pan) ---
# El rol Vendedor no trae permiso de devoluciones: se le da para la prueba.
mongo.role_permissions.update_one({"role_name": "Vendedor", "module_slug": "returns"},
                                  {"$set": {"permissions": {"read": True, "create": True, "update": False, "delete": False}}}, upsert=True)
inv1 = sell(HA, 2).json()["invoice_number"]                                  # contado efectivo 400
sell(HA, 1, method="Tarjeta de Débito")                                        # tarjeta 200
r = sell(HA, 5, status="por_cobrar")                                           # crédito: se lleva 5 panes (1.000)
invc = r.json()["invoice_number"]
check("venta a crédito no mueve dinero de la caja", mongo.cash_movements.count_documents({"reference": invc}) == 0
      and mongo.invoices.find_one({"invoice_number": invc})["cash_session_id"] == SA)
requests.post(f"{B}/fios/{invc}/payment", headers=HA, json={"amount": 300, "payment_method": "Efectivo"})   # abona 300
r = ret(HA, inv1, 1)
check("devolución de contado (1 pan de 2) → reembolso en efectivo $200", r.ok and near(r.json().get("refund_amount"), 200), r.text)
r = ret(HA, invc, 2)
d = mongo.invoices.find_one({"invoice_number": invc})
check("CASO PAN: crédito de 5, devuelve 2 → solo debe 3 (600 − 300 abonado = 300) y no sale dinero",
      r.ok and near(r.json().get("refund_amount"), 0) and near(d["total"], 600) and near(d["balance"], 300) and d["payment_status"] == "por_cobrar", (r.text, d.get("balance")))
r = ret(HA, invc, 2)
d = mongo.invoices.find_one({"invoice_number": invc})
check("CASO P1.40: devuelve 2 más (queda 1 pan = 200, ya abonó 300) → se le devuelven $100 en efectivo",
      r.ok and near(r.json().get("refund_amount"), 100) and near(d["amount_paid"], 200) and near(d["balance"], 0) and d["payment_status"] == "pagado",
      (r.text, d.get("amount_paid"), d.get("payment_status")))
inv_c = mongo.invoices.find_one({"invoice_number": inv1})
check("la factura de contado ajusta lo pagado al nuevo total (200)", near(inv_c["amount_paid"], 200) and near(inv_c["total"], 200))

cur = requests.get(f"{B}/cash/current", headers=HA).json()
cash = cash_of(cur["session"]["summary"])
check("efectivo esperado = 100.000 + 200 + 400 + 300 abono − 200 − 100 = 100.600",
      near(cash.get("expected"), 100600) and near(cash.get("sales"), 600) and near(cash.get("fio_payments"), 300) and near(cash.get("refunds"), 300), cash)
check("tarjeta de débito esperada 200 (sin base)", near(cash_of(cur["session"]["summary"], "Tarjeta de Débito").get("expected"), 200))

# --- 4. Ingresos y egresos manuales ---
r = requests.post(f"{B}/cash/movements", headers=HA, json={"kind": "income", "amount": 50000, "reason": "Más sencillo"})
check("ingreso manual de $50.000 con motivo", r.ok and near(r.json()["summary"]["expected_cash"], 150600), r.text)
r = requests.post(f"{B}/cash/movements", headers=HA, json={"kind": "expense", "amount": 20000, "reason": "Pago domicilio"})
check("egreso manual de $20.000 → esperado 130.600", r.ok and near(r.json()["summary"]["expected_cash"], 130600), r.text)
r = requests.post(f"{B}/cash/movements", headers=HA, json={"kind": "expense", "amount": 999999, "reason": "Demasiado"})
check("egreso mayor que el efectivo disponible → 400 con mensaje", r.status_code == 400 and "suficiente efectivo" in r.json()["detail"], r.text)
r = requests.post(f"{B}/cash/movements", headers=HA, json={"kind": "expense", "amount": 100, "reason": ""})
check("movimiento sin motivo → rechazado", r.status_code in (400, 422), r.status_code)

# --- 5. Interruptor ENCENDIDO ---
mongo.users_extended.update_one({"email": VB}, {"$set": {"is_active": True}})
r = requests.put(f"{B}/cash/settings", headers=A, json={"require_open_session": True})
check("el admin enciende «Exigir caja abierta para vender»", r.ok and r.json()["require_open_session"] is True, r.text)
check("…queda en la auditoría", mongo.audit_log.count_documents({"module": "cash", "entity_id": "configuracion"}) >= 1)
VC = f"caja_c_{tag.lower()}@example.com"
requests.post(f"{B}/rbac/users", headers=A, json={"email": VC, "password": PW, "first_name": "Sin", "last_name": "Caja"})
requests.post(f"{B}/rbac/users/{VC}/roles", headers=A, json=["Vendedor"])
HC = login(VC, PW)
r = sell(HC, 1)
check("sin caja → no deja vender de contado (400 'Abre tu caja')", r.status_code == 400 and "Abre tu caja" in r.json()["detail"], r.text)
r = sell(HC, 1, status="por_cobrar")
check("…ni a crédito", r.status_code == 400 and "Abre tu caja" in r.json()["detail"], r.text)
check("…y no se descontó stock", mongo.products.find_one({"barcode": PAN})["stock"] == 500 - 1 - 2 - 1 - 5 + 1 + 2 + 2)
invc2 = sell(HA, 1, status="por_cobrar").json()["invoice_number"]           # A (con caja) vende otro a crédito
r = requests.post(f"{B}/fios/{invc2}/payment", headers=HC, json={"amount": 1, "payment_method": "Efectivo"})
check("sin caja → no deja recibir abonos", r.status_code == 400 and "Abre tu caja" in r.json()["detail"], r.text)
invx = sell(HA, 3).json()["invoice_number"]                                    # A tiene caja: vende 600 en efectivo
r = ret(HC, invx, 1)
check("devolución que entrega efectivo sin caja → 400 'esta devolución entrega $200'",
      r.status_code == 400 and "entrega $200" in r.json()["detail"], r.text)
check("con caja abierta sí se vende", sell(HA, 1).ok)

# --- 6. Cierre con arqueo ---
cur = requests.get(f"{B}/cash/current", headers=HA).json()
expected = cur["session"]["summary"]["expected_cash"]
check("esperado tras las nuevas ventas: 130.600 + 600 + 200 = 131.400", near(expected, 131400), expected)
r = requests.post(f"{B}/cash/sessions/{SA}/close", headers=HA, json={"denominations": {"100000": 1, "3000": 1}})
check("denominación que no existe en Colombia → 400", r.status_code == 400 and "no válida" in r.json()["detail"], r.text)
r = requests.post(f"{B}/cash/sessions/{SA}/close", headers=HA, json={"denominations": {"100000": 1, "20000": 1, "10000": 1, "1000": 1}})
check("faltante sin observación → 400 pide la observación", r.status_code == 400 and "faltante" in r.json()["detail"], r.text)
r = requests.post(f"{B}/cash/sessions/{SA}/close", headers=HB, json={"counted_cash": 0})
check("otro cajero no puede cerrar mi caja (403)", r.status_code == 403, r.status_code)
denoms = {"100000": 1, "20000": 1, "10000": 1, "1000": 1, "200": 2}          # = 131.400
r = requests.post(f"{B}/cash/sessions/{SA}/close", headers=HA, json={"denominations": denoms, "reconciled": {"Tarjeta de Débito": True}})
c = r.json()
check("cierre por denominaciones cuadrado (131.400, diferencia 0)", r.ok and c["status"] == "closed" and near(c["counted_cash"], 131400)
      and near(c["difference"], 0) and c["reconciled"] == {"Tarjeta de Débito": True}, r.text)
check("…la foto del cierre queda guardada", near(c["summary"]["expected_cash"], 131400))
check("cerrar dos veces → 400", requests.post(f"{B}/cash/sessions/{SA}/close", headers=HA, json={"counted_cash": 0}).status_code == 400)
r = sell(HA, 1)
check("con la caja cerrada y el interruptor encendido → ya no vende", r.status_code == 400 and "Abre tu caja" in r.json()["detail"], r.text)
check("cierre en la auditoría", mongo.audit_log.count_documents({"module": "cash", "entity_id": SA}) >= 2)

# --- 7. Visibilidad e historial ---
SB = mongo.cash_sessions.find_one({"cashier_email": VB})["session_id"]
check("un cajero no ve la caja de otro (403)", requests.get(f"{B}/cash/sessions/{SA}", headers=HB).status_code == 403)
h = requests.get(f"{B}/cash/sessions", headers=HA).json()
check("historial del cajero: solo sus cajas", h["total"] >= 1 and all(x["cashier_email"] == VA for x in h["items"]) and not h["is_admin"], h["total"])
h = requests.get(f"{B}/cash/sessions", headers=A).json()
check("historial del admin: todas, con filtro de cajeros", h["is_admin"] and {VA, VB} <= set(h["cashiers"]), h.get("cashiers"))
check("filtro por estado (abiertas)", all(x["status"] == "open" for x in requests.get(f"{B}/cash/sessions", headers=A, params={"status": "open"}).json()["items"]))

# --- 8. Cierre forzado por el admin ---
r = requests.post(f"{B}/cash/sessions/{SB}/close", headers=A, json={"counted_cash": 45000})
check("cierre forzado sin motivo → 400", r.status_code == 400 and "motivo" in r.json()["detail"], r.text)
r = requests.post(f"{B}/cash/sessions/{SB}/close", headers=A, json={"counted_cash": 45000, "notes": "Cajero se fue sin cerrar"})
c = r.json()
check("admin cierra la caja olvidada de B (forzado, faltante 5.000 con observación)",
      r.ok and c["forced_close"] is True and near(c["difference"], -5000) and c["closed_by"] == "admin@boltrex.com", r.text)

# Limpieza: interruptor apagado y el rol Vendedor vuelve a no tener devoluciones (no contaminar otras baterías).
requests.put(f"{B}/cash/settings", headers=A, json={"require_open_session": False})
mongo.role_permissions.delete_one({"role_name": "Vendedor", "module_slug": "returns"})
print(f"\n{sum(results)}/{len(results)} pruebas OK")
sys.exit(0 if all(results) else 1)
