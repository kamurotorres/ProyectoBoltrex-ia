"""Pruebas de exportación a Excel / PDF / CSV (backlog P2.33).

    source tests/test_env.sh
    DB_NAME=boltrex_extest tests/prepare_test_db.sh
    DB_NAME=boltrex_extest backend/.venv/bin/uvicorn main:app --app-dir backend --port 8001
    BOLTREX_API=http://localhost:8001/api DB_NAME=boltrex_extest backend/.venv/bin/python tests/exports_check.py

Los Excel se leen con openpyxl; los PDF se validan descomprimiendo su contenido (zlib) y buscando textos.
"""
import io
import os
import re
import sys
import time
import uuid
import zlib
from datetime import datetime, timedelta, timezone

import openpyxl
import pymongo
import requests

ADMIN_PASSWORD = os.environ.get("BOLTREX_ADMIN_PASSWORD", "Prueba-Admin-2026")
DB_NAME = os.environ["DB_NAME"]
if DB_NAME == "boltrex":
    sys.exit("Negado: usa una BD de prueba.")
mongo = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017/?directConnection=true"), tz_aware=True)[DB_NAME]
B = os.environ.get("BOLTREX_API", "http://localhost:8001/api")
OFFSET = 300
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"{'OK ' if ok else 'FAIL'} {name}" + ("" if ok else f" -> {detail}"))


def login(email, pw):
    r = requests.post(f"{B}/auth/login", json={"email": email, "password": pw},
                      headers={"X-Real-IP": f"10.6.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"})
    assert r.ok, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def wb(resp):
    return openpyxl.load_workbook(io.BytesIO(resp.content))


def pdf_text(resp) -> str:
    """Texto aproximado de un PDF de reportlab (contenidos comprimidos con Flate)."""
    import base64
    out = []
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", resp.content, re.S):
        raw = m.group(1).strip()
        try:   # reportlab: ASCII85 + Flate
            if raw.endswith(b"~>"):
                raw = base64.a85decode(raw[:-2].replace(b"\n", b"").replace(b"\r", b""))
            out.append(zlib.decompress(raw).decode("latin-1"))
        except Exception:
            out.append(raw.decode("latin-1", "ignore"))
    return "\n".join(out)


def pages(resp) -> int:
    return len(re.findall(rb"/Type\s*/Page[^s]", resp.content))


def sheet_rows(ws):
    return [[c.value for c in r] for r in ws.iter_rows()]


def find_header(ws, first):
    for i, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if row and row[0] == first:
            return i
    return None


for _ in range(30):
    try:
        requests.get(B.rsplit("/api", 1)[0] + "/", timeout=1)
        break
    except Exception:
        time.sleep(0.5)

A = login("admin@boltrex.com", ADMIN_PASSWORD)
tag = uuid.uuid4().hex[:6].upper()
requests.put(f"{B}/ticket-config", headers=A, json={"company_name": f"Panaderia {tag}", "nit": "900123456", "phone": "", "email": "",
                                                    "address": "", "ticket_width": 80, "footer_message": "Gracias"})
P1, P2 = f"PAN{tag}", f"LEC{tag}"
for code, name, cost, price in ((P1, "Pan", 100, 200), (P2, "Leche", 2000, 3000)):
    requests.post(f"{B}/products", headers=A, json={"barcode": code, "name": f"{name} {tag}", "category": "Otros", "purchase_price": cost,
                                                   "tax_rate": 0, "prices": [{"price_list_name": "default", "price": price}]})
SUP = f"Molinos {tag}"
requests.post(f"{B}/suppliers", headers=A, json={"name": SUP})
pn = requests.post(f"{B}/purchases", headers=A, json={"supplier_name": SUP, "items": [
    {"barcode": P1, "product_name": "Pan", "quantity": 100, "unit_cost": 100, "total": 10000},
    {"barcode": P2, "product_name": "Leche", "quantity": 20, "unit_cost": 2000, "total": 40000}]}).json()["purchase_number"]
requests.post(f"{B}/purchases/{pn}/confirm", headers=A)
pn2 = requests.post(f"{B}/purchases", headers=A, json={"supplier_name": SUP, "items": [
    {"barcode": P1, "product_name": "Pan", "quantity": 5, "unit_cost": 100, "total": 500}]}).json()["purchase_number"]   # borrador
DOC = f"9{int(tag, 16)}"
requests.post(f"{B}/clients", headers=A, json={"document_type": "CC", "document_number": DOC, "first_name": "Ana", "last_name": f"Ruiz {tag}",
                                              "phone": "3001112233"})


def sell(code, qty, status="pagado"):
    body = {"client_document": DOC, "client_document_type": "CC", "payment_status": status, "tz_offset_minutes": OFFSET,
            "items": [{"barcode": code, "product_name": "x", "quantity": qty, "unit_price": 0, "tax_rate": 0, "subtotal": 0, "tax_amount": 0, "total": 0}]}
    if status == "pagado":
        body["payment_method"] = "Efectivo"
    r = requests.post(f"{B}/invoices", headers=A, json=body)
    assert r.ok, r.text
    return r.json()["invoice_number"]


i1 = sell(P1, 10)                    # 2.000 efectivo
i2 = sell(P2, 2)                     # 6.000 efectivo
c1 = sell(P2, 3, "por_cobrar")       # 9.000 crédito
c2 = sell(P1, 5, "por_cobrar")       # 1.000 crédito
requests.post(f"{B}/fios/{c1}/payment", headers=A, json={"amount": 4000, "payment_method": "Nequi", "notes": "abono 1"})
mongo.invoices.update_one({"invoice_number": c1}, {"$set": {"due_date": datetime.now(timezone.utc) - timedelta(days=12) + timedelta(hours=1)}})
requests.post(f"{B}/inventory/adjustments", headers=A, json={"kind": "salida", "reason": "Merma", "notes": "Se quemó",
                                                            "items": [{"barcode": P1, "quantity": 4}]})
today = (datetime.now(timezone.utc) - timedelta(minutes=OFFSET)).date().isoformat()
period = {"start_date": today, "end_date": today, "tz_offset_minutes": OFFSET}

# --- 1. Ventas ---
r = requests.get(f"{B}/reports/sales/export", headers=A, params={**period, "format": "xlsx"})
check("ventas en Excel: tipo de archivo y nombre .xlsx", r.ok and r.headers["content-type"].startswith(XLSX)
      and ".xlsx" in r.headers.get("content-disposition", ""), (r.status_code, r.headers.get("content-type"), r.text[:200]))
book = wb(r)
check("…hojas Resumen, Facturas y Detalle por producto", book.sheetnames == ["Resumen", "Facturas", "Detalle por producto"], book.sheetnames)
ws = book["Facturas"]
check("…encabezado con la empresa y NIT, título y periodo", f"Panaderia {tag} · NIT 900123456" == ws["A1"].value
      and ws["A2"].value == "Reporte de ventas" and ws["A3"].value.startswith("Del "), (ws["A1"].value, ws["A2"].value, ws["A3"].value))
h = find_header(ws, "Factura")
data = [row for row in ws.iter_rows(min_row=h + 1, values_only=True) if row[0] and str(row[0]).startswith("INV-")]
total_row = next(row for row in ws.iter_rows(min_row=h + 1, values_only=True) if row[0] == "TOTAL")
ref = requests.get(f"{B}/reports/sales", headers=A, params={**period, "page_size": 1}).json()
check("…todas las facturas del periodo (incluidas las 4 de la prueba) y la fila TOTAL = ventas netas del reporte",
      len(data) == ref["total"] and {i1, i2, c1, c2} <= {row[0] for row in data} and total_row[10] == ref["summary"]["total_sales"],
      (len(data), ref["total"], total_row[10], ref["summary"]["total_sales"]))
money_cell = ws.cell(row=h + 1, column=11)
check("…los pesos son números con formato de moneda (se pueden sumar)", isinstance(money_cell.value, (int, float)) and "$" in money_cell.number_format,
      (money_cell.value, money_cell.number_format))
date_cell = ws.cell(row=h + 1, column=2)
check("…la fecha es fecha de Excel en hora local", isinstance(date_cell.value, datetime) and date_cell.number_format.startswith("dd/mm"),
      (date_cell.value, date_cell.number_format))
check("…encabezado fijo y filtros de Excel", ws.freeze_panes == f"A{h + 1}" and ws.auto_filter.ref.startswith(f"A{h}"), (ws.freeze_panes, ws.auto_filter.ref))
det = book["Detalle por producto"]
check("…el detalle trae una fila por producto vendido", sum(1 for row in det.iter_rows(values_only=True) if row[0] in (i1, i2, c1, c2)) == 4)
res = {row[0]: row[1] for row in book["Resumen"].iter_rows(values_only=True) if row[0]}
net_txt = "$" + f"{ref['summary']['total_sales']:,.0f}".replace(",", ".")
check("…resumen con las ventas netas del reporte y el desglose por forma de pago", res.get("Ventas netas") == net_txt
      and "Por forma de pago: Efectivo" in res and "Por forma de pago: Crédito (Fios)" in res, res)
r = requests.get(f"{B}/reports/sales/export", headers=A, params={**period, "format": "pdf"})
txt = pdf_text(r)
check("ventas en PDF: es un PDF con la empresa, las facturas, TOTAL y «Página 1 de N»", r.ok and r.content[:4] == b"%PDF"
      and f"Panaderia {tag}" in txt and i1 in txt and "TOTAL" in txt and re.search(r"P\S*gina 1 de \d", txt), (r.status_code, txt[:300]))
r = requests.get(f"{B}/reports/sales/export", headers=A, params=period)
check("ventas sin formato → el CSV de siempre (compatibilidad)", r.ok and r.headers["content-type"].startswith("text/csv")
      and r.content.decode("utf-8-sig").startswith("factura,fecha"), r.content[:80])
check("formato inválido → 400 con motivo", requests.get(f"{B}/reports/sales/export", headers=A, params={"format": "doc"}).status_code == 400)

# --- 2. Límite del PDF (3.000 filas) ---
bulk = [{"invoice_number": f"BLK-{tag}-{k:05d}", "client_document": DOC, "client_document_type": "CC", "client_name": "Masivo",
         "items": [], "subtotal": 1, "total_tax": 0, "total": 1, "created_by": "admin@boltrex.com",
         "created_at": datetime(2020, 1, 1, 12, tzinfo=timezone.utc), "status": "completed", "payment_status": "pagado",
         "payment_method": "Efectivo", "amount_paid": 1, "balance": 0} for k in range(3001)]
mongo.invoices.insert_many(bulk)
r = requests.get(f"{B}/reports/sales/export", headers=A, params={"start_date": "2020-01-01", "end_date": "2020-01-01", "format": "pdf"})
check("PDF con 3.001 filas → 400 «máximo 3.000 filas… Expórtalo en Excel»", r.status_code == 400 and "3.000" in r.json()["detail"]
      and "Excel" in r.json()["detail"], r.text[:200])
r = requests.get(f"{B}/reports/sales/export", headers=A, params={"start_date": "2020-01-01", "end_date": "2020-01-01", "format": "xlsx"})
check("…el mismo reporte en Excel sí sale (3.001 facturas)", r.ok and wb(r)["Facturas"].max_row >= 3001 + 5, r.status_code)
mongo.invoices.delete_many({"invoice_number": {"$regex": f"^BLK-{tag}"}})

# --- 3. Compras (nuevo) ---
r = requests.get(f"{B}/purchases/export", headers=A, params={"search": SUP, "format": "xlsx"})
book = wb(r) if r.ok else None
ws = book["Compras"] if book else None
rows = [row for row in ws.iter_rows(values_only=True) if row[0] in (pn, pn2)] if ws else []
check("compras en Excel: 2 compras (confirmada y borrador) con total", r.ok and len(rows) == 2
      and {row[3] for row in rows} == {"Confirmada", "Borrador"}, (r.status_code, rows))
check("…hoja Detalle con los 3 productos", book and sum(1 for row in book["Detalle"].iter_rows(values_only=True) if row[0] in (pn, pn2)) == 3)
r = requests.get(f"{B}/purchases/export", headers=A, params={"search": SUP, "status": "confirmado", "format": "pdf"})
txt = pdf_text(r)
check("compras en PDF filtradas por estado (solo la confirmada)", r.ok and pn in txt and pn2 not in txt, txt[:200])
check("…estado inválido → 400", requests.get(f"{B}/purchases/export", headers=A, params={"status": "x"}).status_code == 400)
r = requests.get(f"{B}/purchases/export", headers=A, params={"search": SUP, "format": "csv"})
check("compras en CSV", r.ok and pn in r.content.decode("utf-8-sig"), r.status_code)
check("/purchases/{número} sigue funcionando (no lo tapa /purchases/export)", requests.get(f"{B}/purchases/{pn}", headers=A).ok)

# --- 4. Cartera y estado de cuenta ---
r = requests.get(f"{B}/fios/export", headers=A, params={"status": "overdue", "format": "xlsx", "tz_offset_minutes": OFFSET})
ws = wb(r)["Cartera"] if r.ok else None
row = next((row for row in ws.iter_rows(values_only=True) if row[1] == DOC), None) if ws else None
check("cartera vencida en Excel: el cliente con saldo $6.000 y vencido $5.000 (12 días)", row and row[4] == 6000 and row[5] == 5000 and row[7] == 12, row)
r = requests.get(f"{B}/fios/export", headers=A, params={"format": "pdf"})
check("cartera en PDF", r.ok and r.content[:4] == b"%PDF" and DOC in pdf_text(r), r.status_code)
check("cartera sin formato → CSV de siempre", requests.get(f"{B}/fios/export", headers=A).content.decode("utf-8-sig").startswith("Tipo doc."))
r = requests.get(f"{B}/fios/statement/{DOC}", headers=A, params={"document_type": "CC", "tz_offset_minutes": OFFSET})
txt = pdf_text(r)
check("estado de cuenta (PDF): facturas pendientes, abono y saldo", r.ok and r.content[:4] == b"%PDF" and c1 in txt and c2 in txt
      and i1 not in txt and "abono 1" in txt and "6.000" in txt, (r.status_code, txt[:300]))
check("…en hoja vertical (A4 retrato)", b"/MediaBox [ 0 0 595.2756 841.8898 ]" in r.content, re.findall(rb"/MediaBox \[[^\]]*\]", r.content)[:1])
r = requests.get(f"{B}/fios/statement/{DOC}", headers=A, params={"document_type": "CC", "format": "xlsx"})
book = wb(r) if r.ok else None
check("…también en Excel (Facturas pendientes + Abonos)", book and book.sheetnames == ["Resumen", "Facturas pendientes", "Abonos"],
      book.sheetnames if book else r.text)
check("…cliente inexistente → 404", requests.get(f"{B}/fios/statement/000000", headers=A).status_code == 404)

# --- 5. Inventario y ajustes ---
r = requests.get(f"{B}/reports/inventory/export", headers=A, params={"format": "xlsx"})
ws = wb(r)["Inventario"]
row = next(row for row in ws.iter_rows(values_only=True) if row[0] == P1)
check("inventario valorizado en Excel: Pan stock 81, mínimo 10, valor $8.100", row[3] == 81 and row[4] == 10 and row[7] == 8100, row)
check("inventario en PDF", requests.get(f"{B}/reports/inventory/export", headers=A, params={"format": "pdf"}).content[:4] == b"%PDF")
r = requests.get(f"{B}/inventory/adjustments/export", headers=A, params={"format": "xlsx", "reason": "Merma"})
book = wb(r)
row = next(row for row in book["Ajustes"].iter_rows(values_only=True) if row[0] and str(row[0]).startswith("AJU-"))
check("ajustes en Excel: la merma con pérdida $400 y la observación", row[3] == "Merma" and row[4] == "Se quemó" and row[6] == 400, row)
check("…filtro anotado en el encabezado", any(c.value == "Motivo: Merma" for c in book["Ajustes"]["A"]), [c.value for c in book["Ajustes"]["A"][:6]])
check("ajustes en PDF", requests.get(f"{B}/inventory/adjustments/export", headers=A, params={"format": "pdf"}).content[:4] == b"%PDF")

# --- 6. Cierre de caja en A4 ---
cj = requests.post(f"{B}/cash/open", headers=A, json={"opening_amount": 50000})
sid = cj.json()["session_id"] if cj.ok else (requests.get(f"{B}/cash/current", headers=A).json()["session"] or {}).get("session_id")
sell(P2, 1)                                       # 3.000 en efectivo a esta caja
expected = int(requests.get(f"{B}/cash/current", headers=A).json()["session"]["summary"]["expected_cash"])
den, rest = {}, expected
for bill in (100000, 50000, 20000, 10000, 5000, 2000, 1000, 500, 200, 100, 50):
    if rest >= bill:
        den[str(bill)], rest = rest // bill, rest % bill
rc = requests.post(f"{B}/cash/sessions/{sid}/close", headers=A, json={"denominations": den})
assert rc.ok, rc.text
exp_txt = "$" + f"{expected:,}".replace(",", ".")
r = requests.get(f"{B}/cash/sessions/{sid}/export", headers=A, params={"tz_offset_minutes": OFFSET})
txt = pdf_text(r)
check(f"cierre de caja en PDF A4: caja, esperado {exp_txt}, cuadrada y arqueo", r.ok and sid in txt and exp_txt[1:] in txt and "Cuadrada" in txt
      and "Arqueo" in txt, (r.status_code, txt[:300]))
r = requests.get(f"{B}/cash/sessions/{sid}/export", headers=A, params={"format": "xlsx"})
check("…en Excel con hojas por forma de pago, movimientos y arqueo", r.ok and wb(r).sheetnames == ["Resumen", "Por forma de pago", "Movimientos", "Arqueo"],
      wb(r).sheetnames if r.ok else r.text)

# --- 7. Permisos y auditoría ---
PW = "Vendedor-Export-1"
V = f"export_{tag.lower()}@example.com"
requests.post(f"{B}/rbac/users", headers=A, json={"email": V, "password": PW, "first_name": "Vendedor", "last_name": "Export"})
requests.post(f"{B}/rbac/users/{V}/roles", headers=A, json=["Vendedor"])
HV = login(V, PW)
check("el vendedor (sin Compras) no exporta compras (403)", requests.get(f"{B}/purchases/export", headers=HV).status_code == 403)
check("el vendedor no exporta la caja de otro (403)", requests.get(f"{B}/cash/sessions/{sid}/export", headers=HV).status_code == 403)
check("el vendedor sí exporta reportes de ventas (tiene Reportes → ver)",
      requests.get(f"{B}/reports/sales/export", headers=HV, params={**period, "format": "xlsx"}).ok)
logs = list(mongo.audit_log.find({"action": "export"}))
check("cada exportación Excel/PDF queda en la auditoría con formato y filas",
      len(logs) >= 15 and any("Exportó «Reporte de ventas» (Excel)" in (l.get("summary") or "") and "fila(s)" in l["summary"] for l in logs)
      and any(l.get("module") == "purchases" for l in logs) and any(l.get("module") == "cash" for l in logs), len(logs))

ok = sum(results)
print(f"\n{ok}/{len(results)} pruebas OK")
sys.exit(0 if ok == len(results) else 1)
