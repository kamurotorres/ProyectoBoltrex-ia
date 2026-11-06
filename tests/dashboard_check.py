"""Pruebas del Dashboard (backlog P2.29).

    source tests/test_env.sh
    DB_NAME=boltrex_dbtest tests/prepare_test_db.sh
    DB_NAME=boltrex_dbtest backend/.venv/bin/uvicorn main:app --app-dir backend --port 8001
    BOLTREX_API=http://localhost:8001/api DB_NAME=boltrex_dbtest backend/.venv/bin/python tests/dashboard_check.py

Ventas con días y horas conocidos (hora de Colombia, tz_offset_minutes=300) en junio de 2001,
para que ninguna otra venta de la BD de prueba interfiera. Cifras esperadas calculadas a mano.
"""
import os
import sys
import time
import uuid
from datetime import datetime, timezone

import pymongo
import requests

ADMIN_PASSWORD = os.environ.get("BOLTREX_ADMIN_PASSWORD", "Prueba-Admin-2026")
DB_NAME = os.environ["DB_NAME"]
if DB_NAME == "boltrex":
    sys.exit("Negado: usa una BD de prueba.")
mongo = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017/?directConnection=true"), tz_aware=True)[DB_NAME]
B = os.environ.get("BOLTREX_API", "http://localhost:8001/api")
results = []
EPS = 0.01


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"{'OK ' if ok else 'FAIL'} {name}" + ("" if ok else f" -> {detail}"))


def near(a, b):
    return a is not None and abs(a - b) < EPS


def ip():
    return f"10.4.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"


def login(email, pw):
    r = requests.post(f"{B}/auth/login", json={"email": email, "password": pw}, headers={"X-Real-IP": ip()})
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
P1, P2 = f"D1{tag}", f"D2{tag}"
requests.post(f"{B}/products", headers=A, json={"barcode": P1, "name": f"Arroz {tag}", "category": "Otros", "purchase_price": 100, "tax_rate": 19,
                                               "prices": [{"price_list_name": "default", "price": 200}]})
requests.post(f"{B}/products", headers=A, json={"barcode": P2, "name": f"Aceite {tag}", "category": "Otros", "purchase_price": 50, "tax_rate": 0,
                                               "prices": [{"price_list_name": "default", "price": 80}]})
pn = requests.post(f"{B}/purchases", headers=A, json={"supplier_name": "Prov Dash", "items": [
    {"barcode": P1, "product_name": "x", "quantity": 50, "unit_cost": 100, "total": 5000},
    {"barcode": P2, "product_name": "x", "quantity": 50, "unit_cost": 50, "total": 2500}]}).json()["purchase_number"]
requests.post(f"{B}/purchases/{pn}/confirm", headers=A)
doc = f"6{int(tag, 16)}"
requests.post(f"{B}/clients", headers=A, json={"document_type": "CC", "document_number": doc, "first_name": "Cli", "last_name": "Dash"})

PW = "Vendedor-Dash-1"
VA, VB, VN = f"va_{tag.lower()}@example.com", f"vb_{tag.lower()}@example.com", f"vn_{tag.lower()}@example.com"
for email, roles in ((VA, ["Vendedor"]), (VB, ["Vendedor"]), (VN, [])):
    requests.post(f"{B}/rbac/users", headers=A, json={"email": email, "password": PW, "first_name": "V", "last_name": email[:2]})
    if roles:
        requests.post(f"{B}/rbac/users/{email}/roles", headers=A, json=roles)
HA, HB, HN = login(VA, PW), login(VB, PW), login(VN, PW)


def sell(h, items, status="pagado", method="Efectivo"):
    body = {"client_document": doc, "client_document_type": "CC", "payment_status": status, "items": [
        {"barcode": bc, "product_name": "x", "quantity": q, "unit_price": 0, "tax_rate": 0, "subtotal": 0, "tax_amount": 0, "total": 0}
        for bc, q in items]}
    if status == "pagado":
        body["payment_method"] = method
    r = requests.post(f"{B}/invoices", headers=h, json=body)
    assert r.ok, r.text
    return r.json()["invoice_number"]


def at(inv, iso_utc):
    mongo.invoices.update_one({"invoice_number": inv}, {"$set": {"created_at": datetime.fromisoformat(iso_utc)}})


# --- Ventas (hora UTC → hora Colombia = UTC − 5) ---
inv1 = sell(HA, [(P1, 2)])                                  # 2 × 238 = 476 · ganancia 2 × (200−100) = 200
at(inv1, "2001-06-10T14:30:00+00:00")                       # 10-jun 09:30 local
inv2 = sell(HA, [(P2, 3)], status="por_cobrar")             # 3 × 80 = 240 · ganancia 3 × 30 = 90 (crédito)
at(inv2, "2001-06-10T23:00:00+00:00")                       # 10-jun 18:00 local
inv3 = sell(HB, [(P1, 1), (P2, 1)], method="Tarjeta de Débito")  # 238 + 80 = 318 · ganancia 100 + 30 = 130
at(inv3, "2001-06-12T01:00:00+00:00")                       # 11-jun 20:00 local (en UTC ya es el 12)
inv4 = sell(HA, [(P2, 1)])                                  # periodo ANTERIOR: 80 · ganancia 30
at(inv4, "2001-06-09T17:00:00+00:00")                       # 9-jun 12:00 local
r = requests.post(f"{B}/returns", headers=A, json={"invoice_number": inv1, "items": [
    {"barcode": P1, "product_name": "x", "quantity": 1, "unit_price": 238, "total": 238}]})
check("devolución de 1 unidad de la factura 1", r.ok, r.text)
check("la venta guarda el precio de compra de cada línea", mongo.invoices.find_one({"invoice_number": inv3})["items"][0].get("unit_cost") == 100)
check("la devolución guarda el costo de la línea original", mongo.returns.find_one({"invoice_number": inv1})["items"][0].get("unit_cost") == 100)
# Venta antigua sin costo registrado (anterior a P2.29): cuenta en ventas, no en ganancia
LEG = f"LG{tag}"
mongo.invoices.insert_one({"invoice_number": LEG, "client_document": doc, "client_document_type": "CC", "client_name": "Legacy",
                           "items": [{"barcode": f"LGP{tag}", "product_name": "Viejo", "quantity": 1, "unit_price": 100, "tax_rate": 0,
                                      "subtotal": 100, "tax_amount": 0, "total": 100}],
                           "subtotal": 100, "total_tax": 0, "total": 100, "status": "completed", "payment_status": "pagado",
                           "payment_method": "Efectivo", "amount_paid": 100, "balance": 0, "created_by": "legacy@example.com",
                           "created_at": datetime(2001, 6, 10, 15, 0, tzinfo=timezone.utc)})  # 10:00 local

P = {"start_date": "2001-06-10", "end_date": "2001-06-11", "tz_offset_minutes": 300}
get = lambda h, **extra: requests.get(f"{B}/dashboard/summary", headers=h, params={**P, **extra})

# --- Administrador: toda la tienda ---
d = get(A).json()
k = d["kpis"]
check("admin: ventas netas 896 (476−238 + 240 + 318 + 100)", near(k["net_sales"], 896), k)
check("admin: 4 facturas y ticket promedio 224", k["invoices"] == 4 and near(k["avg_ticket"], 224), k)
check("admin: 7 unidades netas (2−1 + 3 + 2 + 1)", k["units"] == 7, k["units"])
check("admin: ganancia 320 = (venta sin IVA − compra) × cant. (200 − 100 + 90 + 130)", near(k["profit"], 320), k["profit"])
check("…la venta sin costo registrado se informa aparte (1)", k["invoices_without_cost"] == 1, k)
check("admin: ventas brutas y devoluciones", near(k["gross_sales"], 1134) and near(k["returns_total"], 238), k)
check("comparación con el periodo anterior (2 días antes: 80) → +1020 %", near(d["comparison"]["net_sales"], 1020.0) and near(d["previous"]["net_sales"], 80), d["comparison"])
check("ganancia del periodo anterior 30 → +966,7 %", near(d["previous"]["profit"], 30) and near(d["comparison"]["profit"], 966.7), (d["previous"]["profit"], d["comparison"]["profit"]))
s = {x["date"]: x["net"] for x in d["series"]}
check("ventas por día con días LOCALES (la venta de las 20:00 del 11 no cae el 12)", s == {"2001-06-10": 578.0, "2001-06-11": 318.0}, s)
check("agrupación diaria para 2 días", d["range"]["bucket"] == "day")
pay = {x["method"]: x["net"] for x in d["payments"]}
check("formas de pago: Efectivo 338, Crédito (Fios) 240, Débito 318", pay == {"Efectivo": 338.0, "Crédito (Fios)": 240.0, "Tarjeta de Débito": 318.0}, pay)
check("participación por forma de pago suma 100 %", near(sum(x["share"] for x in d["payments"]), 100.0) or abs(sum(x["share"] for x in d["payments"]) - 100) <= 0.2)
top_net = [(x["barcode"], x["net"], x["units"]) for x in d["top_products"]["by_net"] if x["barcode"] in (P1, P2)]
check("top por dinero (neto de devoluciones): Arroz 476 (2 u) > Aceite 320 (4 u)", top_net == [(P1, 476.0, 2), (P2, 320.0, 4)], top_net)
top_u = [x["barcode"] for x in d["top_products"]["by_units"] if x["barcode"] in (P1, P2)]
check("top por unidades: Aceite (4) > Arroz (2)", top_u == [P2, P1], top_u)
h = {x["hour"]: x["net"] for x in d["hours"] if x["net"]}
check("ventas por hora local: 9h 238 · 10h 100 · 18h 240 · 20h 318", h == {9: 238.0, 10: 100.0, 18: 240.0, 20: 318.0}, h)
check("24 horas en la gráfica", len(d["hours"]) == 24)
check("cartera Fios incluida", d["credit"]["balance"] >= 240 and d["credit"]["clients"] >= 1, d["credit"])
check("alertas de stock incluidas", {"low_stock_count", "out_of_stock_count", "threshold"} <= set(d["stock"]))
check("admin ve la lista de vendedores para filtrar", VA in d.get("sellers", []) and VB in d["sellers"] and d["scope"]["is_admin"] is True)

d = get(A, seller=VB).json()
check("admin filtrando por vendedor B → solo sus ventas (318)", near(d["kpis"]["net_sales"], 318) and d["scope"]["seller"] == VB, d["kpis"])

# --- Vendedores: solo lo suyo (opción B) ---
d = get(HA).json()
k = d["kpis"]
check("vendedor A ve solo sus ventas: 478 netas, 2 facturas", near(k["net_sales"], 478) and k["invoices"] == 2, k)
check("vendedor A: ganancia 190 y 4 unidades", near(k["profit"], 190) and k["units"] == 4, k)
check("vendedor A: su cartera (240)", near(d["credit"]["balance"], 240), d["credit"])
check("vendedor A: sin lista de vendedores", "sellers" not in d and d["scope"] == {"is_admin": False, "seller": VA}, d.get("scope"))
d = get(HB, seller=VA).json()
check("vendedor B no puede ver las de A aunque lo pida (ve las suyas: 318)", near(d["kpis"]["net_sales"], 318) and d["scope"]["seller"] == VB, d["kpis"])
check("sin permiso de Dashboard → 403", get(HN).status_code == 403)
check("sin sesión → rechazado", requests.get(f"{B}/dashboard/summary", params=P).status_code in (401, 403))

# --- Periodos ---
d = requests.get(f"{B}/dashboard/summary", headers=A, params={"tz_offset_minutes": 300}).json()
check("sin fechas → HOY (día local)", d["range"]["start_date"] == d["range"]["end_date"] and len(d["series"]) == 1, d["range"])
check("60 días → agrupado por semana", get(A, start_date="2001-05-01", end_date="2001-06-29").json()["range"]["bucket"] == "week")
d = get(A, start_date="2001-01-01", end_date="2001-12-31").json()
check("1 año → agrupado por mes (12 barras)", d["range"]["bucket"] == "month" and len(d["series"]) == 12, (d["range"]["bucket"], len(d["series"])))
check("…y el total del año coincide con el del periodo", near(sum(x["net"] for x in d["series"]), 896 + 80), sum(x["net"] for x in d["series"]))
r = get(A, start_date="2001-06-12", end_date="2001-06-10")
check("rango invertido → 400 con mensaje", r.status_code == 400 and "desde" in r.json()["detail"], r.text)
d = get(A, start_date="1990-01-01", end_date="1990-01-01").json()
check("periodo sin ventas → ceros y sin comparación (no divide por 0)", d["kpis"]["net_sales"] == 0 and d["comparison"]["net_sales"] is None, d["comparison"])

# --- Coincide con Reportes ---
rep = requests.get(f"{B}/reports/sales", headers=A, params=P).json()["summary"]
check("Dashboard y Reporte de ventas dan las mismas ventas netas", near(rep["total_sales"], 896), rep["total_sales"])

mongo.invoices.delete_many({"invoice_number": {"$in": [inv1, inv2, inv3, inv4, LEG]}})
print(f"\n{sum(results)}/{len(results)} pruebas OK")
sys.exit(0 if all(results) else 1)
