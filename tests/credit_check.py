"""Pruebas de cartera con vencimientos (backlog P2.30).

    source tests/test_env.sh
    DB_NAME=boltrex_crtest tests/prepare_test_db.sh
    DB_NAME=boltrex_crtest backend/.venv/bin/uvicorn main:app --app-dir backend --port 8001
    BOLTREX_API=http://localhost:8001/api DB_NAME=boltrex_crtest backend/.venv/bin/python tests/credit_check.py

Producto a $1.000 sin IVA. Las fechas de vencimiento de algunas facturas se mueven directo en la BD
para simular atrasos de 10, 45 y 100 días.
"""
import asyncio
import os
import sys
import time
import uuid
from datetime import date, datetime, timedelta, timezone

import pymongo
import requests

ADMIN_PASSWORD = os.environ.get("BOLTREX_ADMIN_PASSWORD", "Prueba-Admin-2026")
DB_NAME = os.environ["DB_NAME"]
if DB_NAME == "boltrex":
    sys.exit("Negado: usa una BD de prueba.")
mongo = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017/?directConnection=true"), tz_aware=True)[DB_NAME]
B = os.environ.get("BOLTREX_API", "http://localhost:8001/api")
OFFSET = 300   # Colombia
results = []
EPS = 0.01


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"{'OK ' if ok else 'FAIL'} {name}" + ("" if ok else f" -> {detail}"))


def near(a, b):
    return a is not None and abs(a - b) < EPS


def login(email, pw):
    r = requests.post(f"{B}/auth/login", json={"email": email, "password": pw},
                      headers={"X-Real-IP": f"10.3.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"})
    assert r.ok, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def local_date(dt: datetime) -> date:
    return (dt - timedelta(minutes=OFFSET)).date()


def today() -> date:
    return local_date(datetime.now(timezone.utc))


for _ in range(30):
    try:
        requests.get(B.rsplit("/api", 1)[0] + "/", timeout=1)
        break
    except Exception:
        time.sleep(0.5)

A = login("admin@boltrex.com", ADMIN_PASSWORD)
tag = uuid.uuid4().hex[:6].upper()
P = f"CR{tag}"
requests.post(f"{B}/products", headers=A, json={"barcode": P, "name": "Producto crédito", "category": "Otros", "purchase_price": 500,
                                               "tax_rate": 0, "prices": [{"price_list_name": "default", "price": 1000}]})
pn = requests.post(f"{B}/purchases", headers=A, json={"supplier_name": "Proveedor", "items": [
    {"barcode": P, "product_name": "Producto crédito", "quantity": 1000, "unit_cost": 500, "total": 500000}]}).json()["purchase_number"]
requests.post(f"{B}/purchases/{pn}/confirm", headers=A)

n = int(tag, 16)
DOC_STD, DOC_15, DOC_CUPO, DOC_AGE, DOC_VEND = (f"{k}{n}" for k in (61, 62, 63, 64, 65))
for d in (DOC_STD, DOC_15, DOC_CUPO, DOC_AGE, DOC_VEND):
    r = requests.post(f"{B}/clients", headers=A, json={"document_type": "CC", "document_number": d, "first_name": "Cliente", "last_name": d[:2]})
    assert r.ok, r.text

PW = "Vendedor-Cartera-1"
V = f"cartera_{tag.lower()}@example.com"
requests.post(f"{B}/rbac/users", headers=A, json={"email": V, "password": PW, "first_name": "Vendedor", "last_name": "Cartera"})
requests.post(f"{B}/rbac/users/{V}/roles", headers=A, json=["Vendedor"])
HV = login(V, PW)


def sell(h, doc, qty, status="por_cobrar", due=None):
    body = {"client_document": doc, "client_document_type": "CC", "payment_status": status, "tz_offset_minutes": OFFSET,
            "items": [{"barcode": P, "product_name": "x", "quantity": qty, "unit_price": 0, "tax_rate": 0, "subtotal": 0, "tax_amount": 0, "total": 0}]}
    if status == "pagado":
        body["payment_method"] = "Efectivo"
    if due is not None:
        body["due_date"] = due
    return requests.post(f"{B}/invoices", headers=h, json=body)


def inv(number):
    return mongo.invoices.find_one({"invoice_number": number})


# --- 1. Configuración (Config. Sistema) ---
s = requests.get(f"{B}/credit/settings", headers=HV).json()
check("configuración por defecto: plazo 7 días y «por vencer» 5 días (la lee cualquier usuario)",
      s.get("default_term_days") == 7 and s.get("due_soon_days") == 5, s)
r = requests.put(f"{B}/credit/settings", headers=HV, json={"default_term_days": 30, "due_soon_days": 5})
check("un vendedor no puede cambiarla (403 con motivo)", r.status_code == 403 and "administradores" in r.json().get("detail", ""), r.text)
r = requests.put(f"{B}/credit/settings", headers=A, json={"default_term_days": -1, "due_soon_days": 5})
check("plazo negativo → 400 con motivo", r.status_code == 400 and "plazo" in r.json().get("detail", ""), r.text)
r = requests.put(f"{B}/credit/settings", headers=A, json={"default_term_days": 7, "due_soon_days": 400})
check("«por vencer» mayor a 365 → 400", r.status_code == 400, r.text)
r = requests.put(f"{B}/credit/settings", headers=A, json={"default_term_days": 10, "due_soon_days": 3})
check("el administrador la cambia (10 / 3)", r.ok and r.json()["default_term_days"] == 10, r.text)
check("…y queda en la bitácora", mongo.audit_log.find_one({"module": "fios", "entity_id": "configuracion"}) is not None)

# --- 2. Vencimiento de cada venta a crédito ---
r = sell(A, DOC_STD, 1)
i = inv(r.json().get("invoice_number"))
check("venta a crédito sin plazo propio → vence hoy + plazo por defecto (10)",
      r.ok and i.get("due_date") and local_date(i["due_date"]) == today() + timedelta(days=10) and i.get("credit_term_days") == 10, r.text)
check("…el vencimiento es el fin del día local (23:59:59 en Colombia)",
      (i["due_date"] - timedelta(minutes=OFFSET)).strftime("%H:%M:%S") == "23:59:59", i.get("due_date"))
requests.put(f"{B}/credit/settings", headers=A, json={"default_term_days": 7, "due_soon_days": 5})
r = sell(A, DOC_STD, 1, status="pagado")
check("venta de contado no tiene vencimiento", r.ok and "due_date" not in inv(r.json()["invoice_number"]), r.text)

r = requests.put(f"{B}/clients/{DOC_15}?document_type=CC", headers=HV, json={"credit_days": 15})
check("un vendedor no puede poner el plazo de un cliente (403 con motivo)", r.status_code == 403 and "administrador" in r.json().get("detail", ""), r.text)
r = requests.put(f"{B}/clients/{DOC_15}?document_type=CC", headers=A, json={"credit_days": 15})
check("el administrador le pone 15 días al cliente", r.ok and r.json().get("credit_days") == 15, r.text)
r = sell(A, DOC_15, 1)
i = inv(r.json().get("invoice_number"))
check("venta al cliente de 15 días → vence hoy + 15", r.ok and local_date(i["due_date"]) == today() + timedelta(days=15), r.text)
r = requests.put(f"{B}/clients/{DOC_15}?document_type=CC", headers=HV, json={"phone": "3001234567", "credit_days": 15})
check("el vendedor sí puede editar otros datos si no toca el plazo", r.ok, r.text)

due3 = (today() + timedelta(days=3)).isoformat()
r = sell(A, DOC_STD, 1, due=due3)
i = inv(r.json().get("invoice_number"))
check("fecha elegida en el POS (hoy + 3) se respeta", r.ok and local_date(i["due_date"]).isoformat() == due3 and i["credit_term_days"] == 3, r.text)
r = sell(A, DOC_STD, 1, due=(today() - timedelta(days=1)).isoformat())
check("fecha de vencimiento en el pasado → 400 con motivo", r.status_code == 400 and "anterior a hoy" in r.json().get("detail", ""), r.text)
r = sell(A, DOC_STD, 1, due="31/12/2026")
check("fecha con formato inválido → 400", r.status_code == 400 and "AAAA-MM-DD" in r.json().get("detail", ""), r.text)

# --- 3. Cupo de crédito ---
r = requests.put(f"{B}/clients/{DOC_CUPO}?document_type=CC", headers=HV, json={"credit_limit": 999999})
check("un vendedor no puede ampliar el cupo (403)", r.status_code == 403, r.text)
r = requests.put(f"{B}/clients/{DOC_CUPO}?document_type=CC", headers=A, json={"credit_limit": 5000})
check("el administrador asigna cupo $5.000", r.ok and near(r.json().get("credit_limit"), 5000), r.text)
c1 = sell(HV, DOC_CUPO, 3)
check("crédito de $3.000 dentro del cupo → se vende", c1.ok, c1.text)
r = sell(HV, DOC_CUPO, 3)
check("otro crédito de $3.000 (debería $6.000 > $5.000) → 400 con el motivo y el disponible",
      r.status_code == 400 and "cupo" in r.json().get("detail", "") and "$2.000" in r.json().get("detail", ""), r.text)
check("…y no se descontó stock ni se creó factura", mongo.invoices.count_documents({"client_document": DOC_CUPO}) == 1)
r = sell(HV, DOC_CUPO, 3, status="pagado")
check("de contado sí se le vende aunque no tenga cupo", r.ok, r.text)
requests.post(f"{B}/fios/{c1.json()['invoice_number']}/payment", headers=HV, json={"amount": 1000, "payment_method": "Efectivo"})
r = sell(HV, DOC_CUPO, 3)
check("tras abonar $1.000 (debe $2.000) un crédito de $3.000 cabe justo en el cupo", r.ok, r.text)
st = requests.get(f"{B}/credit/client-status", headers=HV, params={"document_number": DOC_CUPO, "document_type": "CC"}).json()
check("estado del cliente: debe $5.000, cupo $5.000, disponible $0", near(st.get("balance"), 5000) and near(st.get("available"), 0)
      and near(st.get("credit_limit"), 5000), st)
r = requests.put(f"{B}/clients/{DOC_CUPO}?document_type=CC", headers=A, json={"credit_limit": None})
check("quitar el cupo (vacío) → sin límite", r.ok and r.json().get("credit_limit") is None
      and "credit_limit" not in mongo.clients.find_one({"document_number": DOC_CUPO}), r.text)
check("…y ya se le puede fiar más", sell(HV, DOC_CUPO, 1).ok)

# --- 4. Antigüedad de la cartera (atrasos simulados) ---
nums = {}
for key, qty in (("od10", 1), ("od45", 2), ("od100", 4), ("soon", 8), ("far", 16)):
    r = sell(A, DOC_AGE, qty)
    assert r.ok, r.text
    nums[key] = r.json()["invoice_number"]
now = datetime.now(timezone.utc)


def eod(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 23, 59, 59, 999000, tzinfo=timezone.utc) + timedelta(minutes=OFFSET)


for key, days in (("od10", -10), ("od45", -45), ("od100", -100), ("soon", 2), ("far", 30)):
    mongo.invoices.update_one({"invoice_number": nums[key]}, {"$set": {"due_date": eod(today() + timedelta(days=days))}})

page = requests.get(f"{B}/fios", headers=A, params={"search": DOC_AGE}).json()
acc = page["items"][0] if page.get("items") else {}
check("cuenta del cliente: saldo $31.000, vencido $7.000 en 3 facturas, por vencer $8.000",
      near(acc.get("balance"), 31000) and near(acc.get("overdue_balance"), 7000) and acc.get("overdue_invoices") == 3
      and near(acc.get("due_soon_balance"), 8000), acc)
check("…atraso máximo 100 días y estado «Vencida (100 días)»", acc.get("max_days_overdue") == 100
      and acc.get("credit_status") == "overdue" and acc.get("credit_status_label") == "Vencida (100 días)", acc)
check("…tramos: 1–30 = $1.000 · 31–60 = $2.000 · 61–90 = $0 · +90 = $4.000",
      near(acc["buckets"]["1_30"], 1000) and near(acc["buckets"]["31_60"], 2000) and near(acc["buckets"]["61_90"], 0)
      and near(acc["buckets"]["90_plus"], 4000), acc.get("buckets"))
check("…próximo vencimiento = el que vence en 2 días", acc.get("next_due_date") and
      local_date(datetime.fromisoformat(acc["next_due_date"].replace("Z", "+00:00"))) == today() + timedelta(days=2), acc.get("next_due_date"))
ag = page.get("aging", {})
by = {b["key"]: b for b in ag.get("buckets", [])}
check("resumen de antigüedad de toda la cartera con los 5 tramos", [b["key"] for b in ag.get("buckets", [])] ==
      ["current", "1_30", "31_60", "61_90", "90_plus"] and by["90_plus"]["balance"] >= 4000 and ag.get("overdue_clients", 0) >= 1, ag)
check("…total del resumen = suma de los tramos", near(ag.get("total_balance"), sum(b["balance"] for b in ag["buckets"])), ag)

for status, expected in (("overdue", True), ("90_plus", True), ("61_90", False), ("due_soon", True), ("current", False)):
    p = requests.get(f"{B}/fios", headers=A, params={"status": status, "search": DOC_AGE}).json()
    check(f"filtro «{status}» {'incluye' if expected else 'no incluye'} al cliente atrasado", (p.get("total") == 1) == expected, p.get("total"))
p = requests.get(f"{B}/fios", headers=A, params={"status": "current", "search": DOC_15}).json()
check("filtro «current» sí incluye al cliente sin atrasos", p.get("total") == 1, p)
r = requests.get(f"{B}/fios", headers=A, params={"status": "malo"})
check("filtro inválido → 400 con las opciones", r.status_code == 400 and "overdue" in r.json().get("detail", ""), r.text)
first = requests.get(f"{B}/fios", headers=A, params={"page_size": 100}).json()["items"]
check("la cartera lista primero a los más atrasados", first and first[0]["max_days_overdue"] == max(a["max_days_overdue"] for a in first),
      [a["max_days_overdue"] for a in first[:3]])

det = requests.get(f"{B}/fios/{DOC_AGE}", headers=A, params={"document_type": "CC"}).json()
lab = {i["invoice_number"]: i for i in det.get("invoices", [])}
check("detalle: cada factura con su estado y días de atraso",
      lab[nums["od45"]]["credit_status"] == "overdue" and lab[nums["od45"]]["days_overdue"] == 45
      and lab[nums["od45"]]["credit_status_label"] == "Vencida hace 45 días", lab.get(nums["od45"]))
check("…«Vence en 2 días» (dentro de los 5 de «por vencer») y la lejana «Al día»",
      lab[nums["soon"]]["credit_status"] == "due_soon" and lab[nums["soon"]]["credit_status_label"] == "Vence en 2 días"
      and lab[nums["far"]]["credit_status"] == "current", (lab[nums["soon"]].get("credit_status_label"), lab[nums["far"]].get("credit_status")))
check("…ordenadas por vencimiento (la más atrasada primero)", det["invoices"][0]["invoice_number"] == nums["od100"], det["invoices"][0]["invoice_number"])
check("…resumen del detalle: vencido $7.000, atraso máx. 100", near(det["summary"].get("overdue_balance"), 7000)
      and det["summary"].get("max_days_overdue") == 100, det.get("summary"))
mongo.invoices.update_one({"invoice_number": nums["far"]}, {"$set": {"due_date": eod(today())}})
det = requests.get(f"{B}/fios/{DOC_AGE}", headers=A, params={"document_type": "CC"}).json()
check("una factura que vence hoy → «Vence hoy» (aún no vencida)",
      next(i for i in det["invoices"] if i["invoice_number"] == nums["far"])["credit_status_label"] == "Vence hoy")
mongo.invoices.update_one({"invoice_number": nums["far"]}, {"$set": {"due_date": eod(today() - timedelta(days=1))}})
det = requests.get(f"{B}/fios/{DOC_AGE}", headers=A, params={"document_type": "CC"}).json()
check("una que venció ayer → «Vencida hace 1 día»",
      next(i for i in det["invoices"] if i["invoice_number"] == nums["far"])["credit_status_label"] == "Vencida hace 1 día")
mongo.invoices.update_one({"invoice_number": nums["far"]}, {"$set": {"due_date": eod(today() + timedelta(days=30))}})

st = requests.get(f"{B}/credit/client-status", headers=HV, params={"document_number": DOC_AGE, "document_type": "CC"}).json()
check("aviso del POS: el cliente tiene $7.000 vencidos en 3 facturas, 100 días de atraso",
      near(st.get("overdue_balance"), 7000) and st.get("overdue_invoices") == 3 and st.get("max_days_overdue") == 100, st)
check("opción A: con facturas vencidas el POS solo avisa, la venta a crédito se permite", sell(HV, DOC_AGE, 1).ok)

# Pagar la vencida de +90 la saca del tramo.
requests.post(f"{B}/fios/{nums['od100']}/payment", headers=A, json={"amount": 4000, "payment_method": "Efectivo"})
acc = requests.get(f"{B}/fios", headers=A, params={"search": DOC_AGE}).json()["items"][0]
check("al pagar la de 100 días: +90 = $0 y el atraso máximo baja a 45", near(acc["buckets"]["90_plus"], 0) and acc["max_days_overdue"] == 45, acc)

# --- 5. Exportación CSV ---
r = requests.get(f"{B}/fios/export", headers=A, params={"status": "overdue"})
txt = r.content.decode("utf-8-sig")
check("exportar la cartera vencida (CSV con tramos)", r.ok and "Vencido;Por vencer" in txt.splitlines()[0]
      and DOC_AGE in txt and DOC_15 not in txt, txt[:300])
check("…sin permiso de Fios no se exporta", requests.get(f"{B}/fios/export").status_code in (401, 403))

# --- 6. Dashboard: cartera vencida con la visibilidad de P2.29 ---
vend_inv = sell(HV, DOC_VEND, 6).json()["invoice_number"]
mongo.invoices.update_one({"invoice_number": vend_inv}, {"$set": {"due_date": eod(today() - timedelta(days=5))}})
dv = requests.get(f"{B}/dashboard/summary", headers=HV, params={"tz_offset_minutes": OFFSET}).json()["credit"]
check("dashboard del vendedor: solo su cartera vencida ($6.000 en 1 factura)",
      near(dv.get("overdue_balance"), 6000) and dv.get("overdue_invoices") == 1, dv)
da = requests.get(f"{B}/dashboard/summary", headers=A, params={"tz_offset_minutes": OFFSET}).json()["credit"]
check("dashboard del administrador: toda la cartera vencida (≥ $9.000)", da.get("overdue_balance", 0) >= 9000
      and len(da.get("buckets", [])) == 5, da)

# --- 7. Facturas antiguas sin vencimiento (arranque) ---
old = f"OLD-{tag}"
mongo.invoices.insert_one({"invoice_number": old, "client_document": DOC_15, "client_document_type": "CC", "client_name": "Antigua",
                           "items": [], "subtotal": 500, "total_tax": 0, "total": 500, "created_by": "admin@boltrex.com",
                           "created_at": datetime.now(timezone.utc) - timedelta(days=20), "status": "completed",
                           "payment_status": "por_cobrar", "amount_paid": 0, "balance": 500})
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from core.credit import backfill_due_dates  # noqa: E402  (usa MONGO_URL / DB_NAME de la prueba)
async def _twice():   # el cliente Motor queda ligado a un solo event loop: ambas corridas en el mismo
    return await backfill_due_dates(), await backfill_due_dates()


n_upd, n_again = asyncio.run(_twice())
o = inv(old)
check("al arrancar, una factura antigua sin vencimiento recibe venta + plazo del cliente (15) → vencida hace 5 días",
      n_upd >= 1 and o.get("credit_term_days") == 15 and local_date(o["due_date"]) == local_date(o["created_at"]) + timedelta(days=15), o)
check("…es idempotente (la segunda vez no cambia nada)", n_again == 0, n_again)

ok = sum(results)
print(f"\n{ok}/{len(results)} pruebas OK")
sys.exit(0 if ok == len(results) else 1)
