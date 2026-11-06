"""Pruebas de ajustes de inventario y del catálogo «Motivos de ajuste» (backlog P2.32).

    source tests/test_env.sh
    DB_NAME=boltrex_ajtest tests/prepare_test_db.sh
    DB_NAME=boltrex_ajtest backend/.venv/bin/uvicorn main:app --app-dir backend --port 8001
    BOLTREX_API=http://localhost:8001/api DB_NAME=boltrex_ajtest backend/.venv/bin/python tests/adjustments_check.py

Productos: Pan (costo $100) y Leche (costo $2.000), con 20 y 10 unidades compradas.
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
mongo = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017/?directConnection=true"), tz_aware=True)[DB_NAME]
B = os.environ.get("BOLTREX_API", "http://localhost:8001/api")
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"{'OK ' if ok else 'FAIL'} {name}" + ("" if ok else f" -> {detail}"))


def near(a, b):
    return a is not None and abs(a - b) < 0.01


def login(email, pw):
    r = requests.post(f"{B}/auth/login", json={"email": email, "password": pw},
                      headers={"X-Real-IP": f"10.4.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"})
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
for code, name, cost, price in ((PAN, "Pan", 100, 200), (LECHE, "Leche", 2000, 3000)):
    r = requests.post(f"{B}/products", headers=A, json={"barcode": code, "name": name, "category": "Otros", "purchase_price": cost,
                                                       "tax_rate": 0, "prices": [{"price_list_name": "default", "price": price}]})
    assert r.ok, r.text
pn = requests.post(f"{B}/purchases", headers=A, json={"supplier_name": "Proveedor", "items": [
    {"barcode": PAN, "product_name": "Pan", "quantity": 20, "unit_cost": 100, "total": 2000},
    {"barcode": LECHE, "product_name": "Leche", "quantity": 10, "unit_cost": 2000, "total": 20000}]}).json()["purchase_number"]
requests.post(f"{B}/purchases/{pn}/confirm", headers=A)
doc = f"7{int(tag, 16)}"
requests.post(f"{B}/clients", headers=A, json={"document_type": "CC", "document_number": doc, "first_name": "Cliente", "last_name": "Ajuste"})

PW = "Vendedor-Ajustes-1"
V = f"ajustes_{tag.lower()}@example.com"
requests.post(f"{B}/rbac/users", headers=A, json={"email": V, "password": PW, "first_name": "Vendedor", "last_name": "Ajustes"})
requests.post(f"{B}/rbac/users/{V}/roles", headers=A, json=["Vendedor"])
HV = login(V, PW)


def stock(code):
    return mongo.products.find_one({"barcode": code})["stock"]


def adjust(h, kind, reason, items, notes=None):
    return requests.post(f"{B}/inventory/adjustments", headers=h, json={"kind": kind, "reason": reason, "notes": notes, "items": items})


# --- 1. Catálogo de motivos ---
reasons = requests.get(f"{B}/adjustment-reasons", headers=A).json()
names = {r["name"]: r for r in reasons}
check("motivos por defecto creados (10, con Merma, Daño, Vencido, Inventario inicial, Otro)",
      len(reasons) >= 10 and {"Merma", "Daño", "Vencido", "Inventario inicial", "Otro"} <= set(names), list(names))
check("…«Otro» exige observación y aplica a los 3 tipos", names["Otro"]["requires_note"] and names["Otro"]["applies_to"] == ["entrada", "salida", "conteo"])
check("módulo «Motivos de ajuste» creado en RBAC", mongo.system_modules.find_one({"slug": "adjustment-reasons"}) is not None)
r = requests.get(f"{B}/adjustment-reasons", headers=HV, params={"kind": "salida", "active_only": True})
check("el vendedor (ver inventario) puede leer los motivos; filtro por tipo", r.ok and all("salida" in x["applies_to"] for x in r.json())
      and "Inventario inicial" not in [x["name"] for x in r.json()], r.text[:200])
check("el vendedor no puede crear motivos (403)", requests.post(f"{B}/adjustment-reasons", headers=HV, json={"name": "X"}).status_code == 403)
RN = f"Degustación {tag}"
r = requests.post(f"{B}/adjustment-reasons", headers=A, json={"name": RN, "description": "Muestras", "applies_to": ["salida"]})
check("el admin crea un motivo nuevo (solo salida)", r.ok and r.json()["applies_to"] == ["salida"], r.text)
check("motivo repetido → 400", requests.post(f"{B}/adjustment-reasons", headers=A, json={"name": RN}).status_code == 400)
r = requests.post(f"{B}/adjustment-reasons", headers=A, json={"name": "Sin tipo", "applies_to": []})
check("motivo sin ningún tipo → 400 con motivo", r.status_code == 400 and "al menos un tipo" in r.json()["detail"], r.text)
r = requests.post(f"{B}/adjustment-reasons", headers=A, json={"name": "Raro", "applies_to": ["regalo"]})
check("tipo desconocido → 400", r.status_code == 400, r.text)
pg = requests.get(f"{B}/adjustment-reasons", headers=A, params={"paginated": True, "page_size": 5}).json()
check("listado paginado de motivos", pg.get("page_size") == 5 and pg.get("total", 0) >= 11 and len(pg["items"]) == 5, pg.get("total"))

# --- 2. Permisos de los ajustes (opción A: solo Administrador) ---
r = adjust(HV, "salida", "Merma", [{"barcode": PAN, "quantity": 1}])
check("el vendedor NO puede ajustar (403) y el stock no cambia", r.status_code == 403 and stock(PAN) == 20, r.status_code)
check("el vendedor sí ve el listado de ajustes (inventario → ver)", requests.get(f"{B}/inventory/adjustments", headers=HV).ok)

# --- 3. Validaciones ---
r = adjust(A, "regalo", "Merma", [{"barcode": PAN, "quantity": 1}])
check("tipo inválido → 400", r.status_code == 400, r.text)
r = adjust(A, "salida", "Inventario inicial", [{"barcode": PAN, "quantity": 1}])
check("motivo que no aplica al tipo → 400 con motivo", r.status_code == 400 and "no aplica" in r.json()["detail"], r.text)
r = adjust(A, "salida", "Otro", [{"barcode": PAN, "quantity": 1}])
check("«Otro» sin observación → 400 «exige una observación»", r.status_code == 400 and "observación" in r.json()["detail"], r.text)
r = adjust(A, "salida", "No existe", [{"barcode": PAN, "quantity": 1}])
check("motivo inexistente → 400", r.status_code == 400 and "no existe" in r.json()["detail"], r.text)
check("sin productos → 400", adjust(A, "salida", "Merma", []).status_code == 400)
r = adjust(A, "salida", "Merma", [{"barcode": PAN, "quantity": 1}, {"barcode": PAN, "quantity": 2}])
check("producto repetido → 400", r.status_code == 400 and "repetido" in r.json()["detail"], r.text)
check("cantidad 0 o negativa → 400", adjust(A, "entrada", "Sobrante encontrado", [{"barcode": PAN, "quantity": 0}]).status_code == 400
      and adjust(A, "salida", "Merma", [{"barcode": PAN, "quantity": -3}]).status_code == 400)
r = adjust(A, "salida", "Merma", [{"barcode": "NOEXISTE", "quantity": 1}])
check("producto inexistente → 400", r.status_code == 400 and "no encontrado" in r.json()["detail"], r.text)
r = adjust(A, "salida", "Merma", [{"barcode": PAN, "quantity": 2}, {"barcode": LECHE, "quantity": 50}])
check("salida mayor al stock → 400 «hay 10 y quieres sacar 50»", r.status_code == 400 and "hay 10 y quieres sacar 50" in r.json()["detail"], r.text)
check("…y NO se aplicó nada (atómico: el Pan sigue en 20)", stock(PAN) == 20 and stock(LECHE) == 10
      and mongo.inventory_adjustments.count_documents({}) == 0)

# --- 4. Salida (merma) con varios productos ---
r = adjust(A, "salida", "Merma", [{"barcode": PAN, "quantity": 8}, {"barcode": LECHE, "quantity": 2}], notes="Se dañó en la nevera")
a1 = r.json()
check("salida de 8 panes y 2 leches → AJU-000001", r.ok and a1.get("adjustment_number") == "AJU-000001", r.text)
check("…stock 20→12 y 10→8", stock(PAN) == 12 and stock(LECHE) == 8)
check("…valor al costo: −$800 −$4.000 = pérdida $4.800", near(a1.get("loss_value"), 4800) and near(a1.get("total_value"), -4800)
      and a1.get("units_out") == 10, (a1.get("loss_value"), a1.get("total_value")))
check("…cada producto guarda stock antes/después y costo", a1["items"][0]["stock_before"] == 20 and a1["items"][0]["stock_after"] == 12
      and a1["items"][0]["unit_cost"] == 100)
mv = list(mongo.inventory_movements.find({"reference": "AJU-000001"}))
check("…2 movimientos «adjustment» con motivo y cantidad negativa", len(mv) == 2 and all(m["movement_type"] == "adjustment" and m["reason"] == "Merma"
                                                                                    and m["quantity"] < 0 for m in mv), mv)
check("…queda en la auditoría", mongo.audit_log.find_one({"module": "inventory", "entity_id": "AJU-000001"}) is not None)

# --- 5. Entrada ---
r = adjust(A, "entrada", "Sobrante encontrado", [{"barcode": PAN, "quantity": 3}])
check("entrada de 3 panes → 15 y sobrante $300", r.ok and stock(PAN) == 15 and near(r.json()["gain_value"], 300), r.text)
check("motivo creado por el admin se usa en una salida", adjust(A, "salida", RN, [{"barcode": PAN, "quantity": 1}]).ok and stock(PAN) == 14)

# --- 6. Conteo físico ---
r = adjust(A, "conteo", "Conteo físico periódico", [{"barcode": PAN, "counted": 11, "expected_stock": 14},
                                                    {"barcode": LECHE, "counted": 8, "expected_stock": 8}])
a4 = r.json()
check("conteo: Pan 14 → contado 11 (−3) y Leche sin diferencia", r.ok and stock(PAN) == 11 and stock(LECHE) == 8, r.text)
check("…diferencias guardadas (−3 y 0) con lo contado", [i["quantity"] for i in a4["items"]] == [-3, 0] and a4["items"][0]["counted"] == 11)
check("…solo 1 movimiento (el que tuvo diferencia)", mongo.inventory_movements.count_documents({"reference": a4["adjustment_number"]}) == 1)
r = adjust(A, "conteo", "Conteo físico periódico", [{"barcode": PAN, "counted": 15, "expected_stock": 11}])
check("conteo con sobrante: 11 → 15 (+4, +$400)", r.ok and stock(PAN) == 15 and near(r.json()["gain_value"], 400), r.text)
check("conteo sin el stock que se vio → 400", adjust(A, "conteo", "Conteo físico periódico", [{"barcode": PAN, "counted": 5}]).status_code == 400)
check("conteo negativo → 400", adjust(A, "conteo", "Conteo físico periódico", [{"barcode": PAN, "counted": -1, "expected_stock": 15}]).status_code == 400)
# Una venta mientras se contaba: el sistema mostraba 15, se vendieron 2.
requests.post(f"{B}/invoices", headers=A, json={"client_document": doc, "client_document_type": "CC", "payment_status": "pagado",
                                               "payment_method": "Efectivo", "items": [{"barcode": PAN, "product_name": "Pan", "quantity": 2,
                                               "unit_price": 0, "tax_rate": 0, "subtotal": 0, "tax_amount": 0, "total": 0}]})
r = adjust(A, "conteo", "Conteo físico periódico", [{"barcode": PAN, "counted": 15, "expected_stock": 15}])
check("venta mientras se contaba → 409 «cambió mientras contabas (era 15, ahora es 13)» y no se pierde la venta",
      r.status_code == 409 and "era 15, ahora es 13" in r.json()["detail"] and stock(PAN) == 13, r.text)

# --- 7. Concurrencia: 10 salidas de 2 a la vez con stock 13 → solo 6 pasan, nunca negativo ---
with ThreadPoolExecutor(10) as ex:
    codes = list(ex.map(lambda _: adjust(A, "salida", "Daño", [{"barcode": PAN, "quantity": 2}]).status_code, range(10)))
check("10 salidas simultáneas de 2 con stock 13 → 6 aplicadas, 4 rechazadas, stock 1 (nunca negativo)",
      codes.count(200) == 6 and codes.count(400) == 4 and stock(PAN) == 1, (codes, stock(PAN)))
nums = [a["adjustment_number"] for a in mongo.inventory_adjustments.find({}, {"adjustment_number": 1})]
check("…consecutivos sin repetir ni huecos", len(nums) == len(set(nums)) and sorted(nums)[-1] == f"AJU-{len(nums):06d}", sorted(nums)[-3:])

# --- 8. Listado, detalle, filtros y exportación ---
lst = requests.get(f"{B}/inventory/adjustments", headers=A, params={"page_size": 5}).json()
check("listado paginado, más reciente primero y sin los productos (liviano)", lst["total"] == len(nums) and len(lst["items"]) == 5
      and "items" not in lst["items"][0] and lst["items"][0]["created_at"] >= lst["items"][-1]["created_at"], lst.get("total"))
s = lst["summary"]
check("resumen: pérdidas = 4.800 + 100 (degustación) + 300 (conteo) + 6×200 (daño) = $6.400; sobrantes $700",
      near(s["loss_value"], 6400) and near(s["gain_value"], 700) and near(s["net_value"], -5700), s)
f = requests.get(f"{B}/inventory/adjustments", headers=A, params={"reason": "Daño"}).json()
check("filtro por motivo (Daño → 6)", f["total"] == 6 and near(f["summary"]["loss_value"], 1200), f["total"])
f = requests.get(f"{B}/inventory/adjustments", headers=A, params={"kind": "conteo"}).json()
check("filtro por tipo (conteo → 2)", f["total"] == 2, f["total"])
f = requests.get(f"{B}/inventory/adjustments", headers=A, params={"search": "nevera"}).json()
check("búsqueda por observación", f["total"] == 1 and f["items"][0]["adjustment_number"] == "AJU-000001", f["total"])
f = requests.get(f"{B}/inventory/adjustments", headers=A, params={"search": "Leche"}).json()
check("búsqueda por producto (Leche está en 2 ajustes)", f["total"] == 2, f["total"])
check("tipo inválido en el filtro → 400", requests.get(f"{B}/inventory/adjustments", headers=A, params={"kind": "x"}).status_code == 400)
d = requests.get(f"{B}/inventory/adjustments/AJU-000001", headers=A).json()
check("detalle con los productos", len(d.get("items", [])) == 2 and d["notes"] == "Se dañó en la nevera", d)
check("detalle inexistente → 404", requests.get(f"{B}/inventory/adjustments/AJU-999999", headers=A).status_code == 404)
r = requests.get(f"{B}/inventory/adjustments/export", headers=A, params={"reason": "Merma"})
lines = r.content.decode("utf-8-sig").splitlines()
check("exportar CSV: una fila por producto (Merma → 2 filas + encabezado)", r.ok and len(lines) == 3 and "Diferencia" in lines[0], lines[:2])
inv = requests.get(f"{B}/inventory", headers=A, params={"tz_offset_minutes": 300}).json()
check("Inventario trae «ajustes del mes»: pérdidas $6.400", near(inv.get("adjustments_month", {}).get("loss_value"), 6400), inv.get("adjustments_month"))
mov = requests.get(f"{B}/inventory/movements", headers=A, params={"movement_type": "adjustment", "barcode": LECHE}).json()
check("movimientos filtrables por «adjustment»", mov["total"] == 1 and mov["items"][0]["reference"] == "AJU-000001", mov.get("total"))

# --- 9. Motivos en uso ---
r = requests.delete(f"{B}/adjustment-reasons/{RN}", headers=A)
check("eliminar un motivo usado → 400 «desactívalo»", r.status_code == 400 and "Desactívalo" in r.json()["detail"], r.text)
r = requests.put(f"{B}/adjustment-reasons/{RN}", headers=A, json={"name": RN, "applies_to": ["salida"], "is_active": False})
check("desactivarlo", r.ok and r.json()["is_active"] is False, r.text)
r = adjust(A, "salida", RN, [{"barcode": LECHE, "quantity": 1}])
check("un motivo desactivado no se puede usar (400 con motivo)", r.status_code == 400 and "desactivado" in r.json()["detail"], r.text)
check("…pero el ajuste viejo conserva su motivo", mongo.inventory_adjustments.count_documents({"reason": RN}) == 1)
tmp = f"Temporal {tag}"
requests.post(f"{B}/adjustment-reasons", headers=A, json={"name": tmp, "applies_to": ["entrada"]})
check("eliminar un motivo sin uso", requests.delete(f"{B}/adjustment-reasons/{tmp}", headers=A).ok
      and mongo.adjustment_reasons.find_one({"name": tmp}) is None)
check("no hay forma de editar ni borrar un ajuste (405)", requests.delete(f"{B}/inventory/adjustments/AJU-000001", headers=A).status_code == 405
      and requests.put(f"{B}/inventory/adjustments/AJU-000001", headers=A, json={}).status_code == 405)

# Dejar el rol Vendedor como estaba (no se tocó) y verificar que no tiene crear en inventario.
p = mongo.role_permissions.find_one({"role_name": "Vendedor", "module_slug": "inventory"}) or {}
check("el rol Vendedor sigue con inventario solo lectura", p.get("permissions", {}).get("create") is not True, p)

ok = sum(results)
print(f"\n{ok}/{len(results)} pruebas OK")
sys.exit(0 if ok == len(results) else 1)
