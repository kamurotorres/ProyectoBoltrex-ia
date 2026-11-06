"""Pruebas de paginación real y exportación completa (backlog P1.18).

    DB_NAME=boltrex_pgtest tests/prepare_test_db.sh
    DB_NAME=boltrex_pgtest backend/.venv/bin/uvicorn main:app --app-dir backend --port 8001
    BOLTREX_API=http://localhost:8001/api DB_NAME=boltrex_pgtest backend/.venv/bin/python tests/pagination_check.py

Inserta 1.205 productos y 1.205 clientes de prueba (con nombres repetidos a propósito, para
probar que las páginas no se repiten ni se saltan registros) y los borra al terminar.
"""
import os
import sys
import time
import uuid

import pymongo
import requests

ADMIN_PASSWORD = os.environ.get("BOLTREX_ADMIN_PASSWORD", "Prueba-Admin-2026")
DB_NAME = os.environ["DB_NAME"]
if DB_NAME == "boltrex":
    sys.exit("Negado: usa una BD de prueba.")
mongo = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017/?directConnection=true"))[DB_NAME]
B = os.environ.get("BOLTREX_API", "http://localhost:8001/api")
results = []
N = 1205
KEYS = {"items", "total", "page", "page_size", "pages"}


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"{'OK ' if ok else 'FAIL'} {name}" + ("" if ok else f" -> {detail}"))


for _ in range(30):
    try:
        requests.get(B.rsplit("/api", 1)[0] + "/", timeout=1)
        break
    except Exception:
        time.sleep(0.5)

r = requests.post(f"{B}/auth/login", json={"email": "admin@boltrex.com", "password": ADMIN_PASSWORD},
                  headers={"X-Real-IP": f"10.6.{uuid.uuid4().int % 250}.1"})
assert r.ok, r.text
H = {"Authorization": f"Bearer {r.json()['access_token']}"}
get = lambda path, **params: requests.get(f"{B}{path}", headers=H, params=params)

tag = uuid.uuid4().hex[:6].upper()
products = [{"barcode": f"PG{tag}{i:05d}", "name": f"Pagina {tag} {i % 7}", "category": "Otros", "purchase_price": 10,
             "tax_rate": 0, "prices": [{"price_list_name": "default", "price": 20}], "stock": i % 15,
             "created_at": "2001-01-01T00:00:00+00:00"} for i in range(N)]
mongo.products.insert_many([dict(p) for p in products])
clients = [{"document_type": "CC", "document_number": f"9{tag}{i:05d}", "first_name": f"Cli{tag}", "last_name": f"N{i % 5}",
            "price_list": "default", "created_at": "2001-01-01T00:00:00+00:00"} for i in range(N)]
mongo.clients.insert_many([dict(c) for c in clients])

# --- Formato y límites ---
r = get("/products", search=tag)
d = r.json()
check("formato común {items, total, page, page_size, pages}", r.ok and KEYS <= set(d), list(d))
check(f"{N} productos → 50 por página, 25 páginas", d["total"] == N and len(d["items"]) == 50 and d["pages"] == 25, {k: d[k] for k in ("total", "pages")})
check("page_size 25/100 respetado", len(get("/products", search=tag, page_size=25).json()["items"]) == 25
      and len(get("/products", search=tag, page_size=100).json()["items"]) == 100)
check("page_size > 200 → 422", get("/products", page_size=500).status_code == 422)
check("page 0 → 422", get("/products", page=0).status_code == 422)
d = get("/products", search=tag, page=99).json()
check("página fuera de rango → vacía, con total real", d["items"] == [] and d["total"] == N)

# --- Recorrer todas las páginas: ni repetidos ni saltados (hay nombres repetidos a propósito) ---
seen = []
for page in range(1, 26):
    seen += [p["barcode"] for p in get("/products", search=tag, page=page).json()["items"]]
check("todas las páginas: 1.205 productos, sin repetidos ni saltados", len(seen) == N and len(set(seen)) == N, (len(seen), len(set(seen))))

# --- Búsqueda en el servidor (POS / Compras) ---
last = products[-1]["barcode"]
d = get("/products", search=last, page_size=20).json()
check("el producto 1.205 se encuentra al buscarlo (antes: invisible tras 1.000)", [p["barcode"] for p in d["items"]] == [last], d["items"][:2])
check("búsqueda por código exacto (lector de barras)", get("/products", barcode=last).json()["total"] == 1)
check("búsqueda con caracteres especiales no rompe (regex escapada)", get("/products", search="(a+)+$").ok)
lastc = clients[-1]["document_number"]
d = get("/clients", search=lastc, page_size=20).json()
check("el cliente 1.205 se encuentra al buscarlo", [c["document_number"] for c in d["items"]] == [lastc], d["items"][:1])
check(f"clientes paginados ({N})", get("/clients", search=f"Cli{tag}").json()["total"] == N)

pid = products[-1]
mongo.products.update_one({"barcode": last}, {"$set": {"stock": 5}})
r = requests.post(f"{B}/invoices", headers=H, json={"client_document": lastc, "client_document_type": "CC", "payment_status": "pagado",
                                                    "payment_method": "Efectivo", "items": [{"barcode": last, "product_name": "x", "quantity": 1,
                                                    "unit_price": 0, "tax_rate": 0, "subtotal": 0, "tax_amount": 0, "total": 0}]})
check("se puede VENDER el producto 1.205 al cliente 1.205", r.ok and r.json()["total"] == 20, r.text)
inv = r.json().get("invoice_number")

# --- Inventario: totales sobre TODOS los productos ---
d = get("/inventory", search=tag).json()
summ = d["summary"]
all_products = list(mongo.products.find({}, {"purchase_price": 1, "stock": 1}))
exp_value = round(sum((p.get("purchase_price") or 0) * (p.get("stock") or 0) for p in all_products), 2)
exp_low = sum(1 for p in all_products if (p.get("stock") or 0) < 10)
exp_out = sum(1 for p in all_products if (p.get("stock") or 0) <= 0)
check("inventario: valor total exacto sobre todos los productos", abs(summ["total_value"] - exp_value) < 0.01, (summ["total_value"], exp_value))
check("inventario: bajo stock y agotados exactos", summ["low_stock_count"] == exp_low and summ["out_of_stock_count"] == exp_out,
      (summ, exp_low, exp_out))
check("inventario paginado (25 páginas del tag)", d["total"] == N and len(d["items"]) == 50)
tag_out = sum(1 for i in range(N) if i % 15 == 0) - 0  # stock 0 en i%15==0 (el último quedó con 5 - 1 = 4)
d = get("/inventory", search=tag, stock="out").json()
check("filtro 'agotados' en el servidor", d["total"] == tag_out and all(p["stock"] <= 0 for p in d["items"]), (d["total"], tag_out))
rep = get("/reports/inventory").json()
check("reporte de inventario: mismos totales que inventario", abs(rep["summary"]["total_value"] - exp_value) < 0.01 and KEYS <= set(rep))

# --- Exportación completa ---
r = requests.get(f"{B}/reports/inventory/export", headers=H)
lines = [l for l in r.content.decode("utf-8-sig").splitlines() if l.strip()]
check("exportar inventario: TODOS los productos (no solo la página)", r.ok and len(lines) == len(all_products) + 1, (len(lines), len(all_products)))
check("…CSV con encabezado y BOM para Excel", lines[0].startswith("codigo,nombre") and r.content.startswith(b"\xef\xbb\xbf"))
check("…se descarga como archivo", "attachment" in r.headers.get("content-disposition", ""))
check("exportar sin permiso → rechazado", requests.get(f"{B}/reports/inventory/export").status_code in (401, 403))

# --- Resto de listados: formato común y permisos intactos ---
for path in ("/suppliers", "/purchases", "/returns", "/invoices", "/inventory/movements", "/fios", "/rbac/users", "/reports/sales"):
    r = get(path)
    check(f"GET {path} paginado", r.ok and KEYS <= set(r.json()), r.text[:150])
    check(f"GET {path} sin token → rechazado", requests.get(f"{B}{path}").status_code in (401, 403))
d = get("/rbac/users").json()
check("usuarios paginados nunca devuelven el hash de la contraseña", all("hashed_password" not in u for u in d["items"]))
d = get("/inventory/movements", search=last).json()
check("movimientos: búsqueda por producto en el servidor", d["total"] >= 1 and all(m["barcode"] == last for m in d["items"]), d["total"])
d = get("/invoices", search=inv).json()
check("facturas: búsqueda por número (Devoluciones)", [i["invoice_number"] for i in d["items"]] == [inv], d["items"][:1])
check("facturas: excluir devueltas", all(i["status"] != "returned" for i in get("/invoices", exclude_status="returned", page_size=200).json()["items"]))
d = get("/fios").json()
check("Fios: resumen de toda la cartera", {"total_credit", "total_paid", "balance", "clients_count"} <= set(d.get("summary", {})), d.get("summary"))

# --- Catálogos pequeños sin tope oculto ---
for path in ("/categories", "/price-lists", "/payment-methods", "/document-types", "/rbac/roles", "/rbac/modules"):
    r = get(path)
    check(f"GET {path} sigue siendo lista completa", r.ok and isinstance(r.json(), list), r.status_code)

# --- Categorías, listas de precios y formas de pago: pantalla paginada, selectores con lista completa ---
M = 120
for coll, path in (("categories", "/categories"), ("price_lists", "/price-lists"), ("payment_methods", "/payment-methods")):
    mongo[coll].insert_many([{"name": f"Cat{tag}{coll[:3]}{i:03d}", "description": "pg", "is_active": True,
                              "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc)} for i in range(M)])
    d = get(path, paginated="true", search=f"{tag}{coll[:3]}").json()
    check(f"{path}?paginated=true → formato común, {M} en 3 páginas de 50", KEYS <= set(d) and d["total"] == M and len(d["items"]) == 50 and d["pages"] == 3,
          {k: d.get(k) for k in ("total", "pages")})
    names = []
    for page in (1, 2, 3):
        names += [x["name"] for x in get(path, paginated="true", search=f"{tag}{coll[:3]}", page=page).json()["items"]]
    check(f"{path}: recorrido completo sin repetidos", len(names) == M and len(set(names)) == M, len(set(names)))
    full = get(path).json()
    check(f"{path} sin paginated → lista COMPLETA para selectores ({M}+)",
          isinstance(full, list) and sum(1 for x in full if f"{tag}{coll[:3]}" in x["name"]) == M, type(full).__name__)
    mongo[coll].delete_many({"name": {"$regex": f"^Cat{tag}"}})
check("POS y Fios siguen usando formas de pago activas (lista completa)", isinstance(get("/payment-methods/active").json(), list))

# --- Facturas (pantalla): formato común + compatibilidad ---
d = get("/pos/invoices", page_size=25).json()
check("/pos/invoices: formato común + page_size", KEYS <= set(d) and d["page_size"] == 25, list(d))
check("/pos/invoices: conserva 'invoices' y 'pagination' (compatibilidad)", d["invoices"] == d["items"] and d["pagination"]["total"] == d["total"])
check("/pos/invoices: page_size > 200 → 422", get("/pos/invoices", page_size=500).status_code == 422)

# Limpieza
mongo.products.delete_many({"barcode": {"$regex": f"^PG{tag}"}})
mongo.clients.delete_many({"document_number": {"$regex": f"^9{tag}"}})
print(f"\n{sum(results)}/{len(results)} pruebas OK")
sys.exit(0 if all(results) else 1)
