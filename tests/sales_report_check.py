"""Pruebas de reportes de ventas y dashboard (backlog P1.14, opción A).

    DB_NAME=boltrex_srtest tests/prepare_test_db.sh
    DB_NAME=boltrex_srtest backend/.venv/bin/uvicorn main:app --app-dir backend --port 8001
    BOLTREX_API=http://localhost:8001/api DB_NAME=boltrex_srtest backend/.venv/bin/python tests/sales_report_check.py

Usa solo la BD de prueba. Compara deltas (antes/después), así que tolera datos previos.
"""
import os
import sys
import time
import uuid

import pymongo
from datetime import datetime
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
    return abs((a or 0) - (b or 0)) < EPS


for _ in range(30):
    try:
        requests.get(B.rsplit("/api", 1)[0] + "/", timeout=1)
        break
    except Exception:
        time.sleep(0.5)

r = requests.post(f"{B}/auth/login", json={"email": "admin@boltrex.com", "password": ADMIN_PASSWORD},
                  headers={"X-Real-IP": f"10.9.{uuid.uuid4().int % 250}.1"})
assert r.ok, r.text
H = {"Authorization": f"Bearer {r.json()['access_token']}"}


def report(**params):
    r = requests.get(f"{B}/reports/sales", headers=H, params=params)
    assert r.ok, r.text
    return r.json()["summary"]


def dash():
    r = requests.get(f"{B}/dashboard/stats", headers=H)
    assert r.ok, r.text
    return r.json()


# --- Preparación: producto a 200 + IVA 19% = 238 por unidad ---
tag = uuid.uuid4().hex[:6].upper()
bc, doc = f"SR{tag}", f"8{int(tag, 16)}"
requests.post(f"{B}/clients", headers=H, json={"document_type": "CC", "document_number": doc, "first_name": "Rep", "last_name": "Test"})
requests.post(f"{B}/products", headers=H, json={"barcode": bc, "name": "Prod Rep", "category": "Otros", "purchase_price": 100,
                                                "tax_rate": 19, "prices": [{"price_list_name": "default", "price": 200}]})
pn = requests.post(f"{B}/purchases", headers=H, json={"supplier_name": "Prov Rep", "items": [
    {"barcode": bc, "product_name": "Prod Rep", "quantity": 20, "unit_cost": 100, "total": 2000}]}).json()["purchase_number"]
requests.post(f"{B}/purchases/{pn}/confirm", headers=H)

s0, d0 = report(), dash()

item = lambda q: {"barcode": bc, "product_name": "x", "quantity": q, "unit_price": 0, "tax_rate": 0, "subtotal": 0, "tax_amount": 0, "total": 0}
sale = lambda q: requests.post(f"{B}/invoices", headers=H, json={"client_document": doc, "payment_status": "pagado",
                                                                  "payment_method": "Efectivo", "items": [item(q)]}).json()
A = sale(1)                       # completada: 238
Bf = sale(2)                      # 476 → devolución de 1 → neto 238 (parcial)
C = sale(1)                       # 238 → devolución total → neto 0
ret = lambda inv, q: requests.post(f"{B}/returns", headers=H, json={"invoice_number": inv["invoice_number"], "items": [
    {"barcode": bc, "product_name": "Prod Rep", "quantity": q, "unit_price": 238, "total": 238 * q}]})
check("devolución parcial OK", ret(Bf, 1).ok)
check("devolución total OK", ret(C, 1).ok)
st = {i["invoice_number"]: i["status"] for i in mongo.invoices.find({"invoice_number": {"$in": [A["invoice_number"], Bf["invoice_number"], C["invoice_number"]]}})}
check("estados: completada / parcial / devuelta", sorted(st.values()) == ["completed", "partial_return", "returned"], st)

s1, d1 = report(), dash()
delta = lambda k: (s1.get(k) or 0) - (s0.get(k) or 0)

# --- Reporte de ventas ---
check("la factura con devolución parcial YA NO desaparece: ventas netas +476 (238 + 238 + 0)", near(delta("total_sales"), 476), delta("total_sales"))
check("ventas brutas +952 (238 + 476 + 238)", near(delta("gross_sales"), 952), delta("gross_sales"))
check("devoluciones +476 (2 devoluciones)", near(delta("returns_total"), 476) and delta("returns_count") == 2, (delta("returns_total"), delta("returns_count")))
check("bruto − devoluciones = neto", near(s1["gross_sales"] - s1["returns_total"], s1["total_sales"]))
check("facturas de venta +2 (completada + parcial); devuelta por completo aparte (+1)",
      delta("total_invoices") == 2 and delta("returned_invoices") == 1 and delta("partial_return_invoices") == 1, s1)
check("IVA neto +76 (38 + 38)", near(delta("total_tax"), 76), delta("total_tax"))
r = requests.get(f"{B}/reports/sales", headers=H, params={"page_size": 200}).json()
nums = {i["invoice_number"]: i for i in r["items"]}
check("la lista incluye las 3 facturas con su estado y total neto",
      all(n in nums for n in st) and near(nums[Bf["invoice_number"]]["total"], 238) and near(nums[C["invoice_number"]]["total"], 0))

# --- Dashboard ---
check("dashboard: ventas netas +476 (antes la parcial se perdía)", near(d1["total_sales"] - d0["total_sales"], 476), d1["total_sales"] - d0["total_sales"])
check("dashboard: facturas +2", d1["total_invoices"] - d0["total_invoices"] == 2, d1["total_invoices"] - d0["total_invoices"])
check("dashboard coincide con el reporte sin filtros", near(d1["total_sales"], s1["total_sales"]) and d1["total_invoices"] == s1["total_invoices"])
check("dashboard trae bruto y devoluciones", near(d1["gross_sales"] - d1["returns_total"], d1["total_sales"]))

# --- Fechas: días locales completos (Colombia, UTC-5 → getTimezoneOffset = 300) ---
marker = f"TZ{tag}"
docs = [
    {"invoice_number": f"{marker}-1", "created_at": "2001-03-10T04:30:00+00:00", "total": 1.0},   # 9-mar 23:30 local
    {"invoice_number": f"{marker}-2", "created_at": "2001-03-10T23:30:00+00:00", "total": 10.0},  # 10-mar 18:30 local
    {"invoice_number": f"{marker}-3", "created_at": "2001-03-11T02:00:00.123456+00:00", "total": 100.0},  # 10-mar 21:00 local
    {"invoice_number": f"{marker}-4", "created_at": "2001-03-11T05:00:00+00:00", "total": 1000.0},  # 11-mar 00:00 local
]
for d in docs:
    d["created_at"] = datetime.fromisoformat(d["created_at"])  # P1.19: fechas nativas
    mongo.invoices.insert_one({**d, "status": "completed", "total_tax": 0, "subtotal": d["total"], "items": [],
                               "client_document": "0", "client_name": "TZ", "created_by": "t", "payment_status": "pagado",
                               "amount_paid": d["total"], "balance": 0})
s = report(start_date="2001-03-10", end_date="2001-03-10", tz_offset_minutes=300)
check("día local 10-mar incluye 18:30 y 21:00 (antes las 21:00 caían al 11)", near(s["total_sales"], 110) and s["total_invoices"] == 2, s["total_sales"])
s = report(start_date="2001-03-10", end_date="2001-03-10", tz_offset_minutes=0)
check("con desfase 0 (UTC) el día 10 son 04:30 y 23:30", near(s["total_sales"], 11), s["total_sales"])
s = report(end_date="2001-03-10", tz_offset_minutes=300)
check("'hasta' incluye el día completo (sin 'desde')", near(s["total_sales"], 111), s["total_sales"])
s = report(start_date="2001-03-11", end_date="2001-03-11", tz_offset_minutes=300)
check("medianoche local exacta cae en el día siguiente", near(s["total_sales"], 1000), s["total_sales"])
r = requests.get(f"{B}/pos/invoices", headers=H, params={"start_date": "2001-03-10", "end_date": "2001-03-10", "tz_offset_minutes": 300, "limit": 100})
got = sorted(i["invoice_number"] for i in r.json().get("invoices", r.json().get("items", [])))
check("pantalla Facturas: mismo criterio de día local", got == [f"{marker}-2", f"{marker}-3"], (r.status_code, got))
r = requests.get(f"{B}/invoices", headers=H, params={"start_date": "2001-03-10", "end_date": "2001-03-10", "tz_offset_minutes": 300})
got = sorted(i["invoice_number"] for i in r.json()["items"] if i["invoice_number"].startswith(marker))
check("listado /invoices: mismo criterio de día local", got == [f"{marker}-2", f"{marker}-3"], got)

r = requests.get(f"{B}/reports/sales", headers=H, params={"start_date": "2001-03-12", "end_date": "2001-03-10"})
check("rango invertido → 400 con mensaje", r.status_code == 400 and "desde" in r.json()["detail"], r.text)
r = requests.get(f"{B}/reports/sales", headers=H, params={"start_date": "10/03/2001"})
check("fecha mal escrita → 400 con mensaje", r.status_code == 400 and "AAAA-MM-DD" in r.json()["detail"], r.text)

# --- Totales sin tope de 1.000 ---
bulk = f"BK{tag}"
mongo.invoices.insert_many([{"invoice_number": f"{bulk}-{i:05d}", "created_at": datetime.fromisoformat(f"2002-05-05T15:{i % 60:02d}:00+00:00"),
                             "status": "completed", "total": 2.0, "total_tax": 0.0, "subtotal": 2.0, "items": [],
                             "client_document": "0", "client_name": "Bulk", "created_by": "t", "payment_status": "pagado",
                             "amount_paid": 2.0, "balance": 0} for i in range(1005)])
r = requests.get(f"{B}/reports/sales", headers=H, params={"start_date": "2002-05-05", "end_date": "2002-05-05"}).json()
sm = r["summary"]
check("1.005 facturas: totales completos (2.010)", near(sm["total_sales"], 2010) and sm["total_invoices"] == 1005, sm)
check("el detalle está paginado (P1.18): 50 por página, 21 páginas", len(r["items"]) == 50 and r["total"] == 1005 and r["pages"] == 21, {k: r[k] for k in ("total", "pages")})
r = requests.get(f"{B}/reports/sales/export", headers=H, params={"start_date": "2002-05-05", "end_date": "2002-05-05"})
lines = [l for l in r.content.decode("utf-8-sig").splitlines() if l.strip()]
check("exportar CSV trae TODAS las facturas del periodo (1.005 + encabezado)", r.ok and len(lines) == 1006 and lines[0].startswith("factura,"), len(lines))

# Limpieza de los documentos insertados a mano
mongo.invoices.delete_many({"invoice_number": {"$regex": f"^({marker}|{bulk})-"}})

print(f"\n{sum(results)}/{len(results)} pruebas OK")
sys.exit(0 if all(results) else 1)
