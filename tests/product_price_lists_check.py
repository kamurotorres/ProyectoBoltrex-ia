"""Pruebas de precios por lista en productos: sin repetidos, solo listas existentes, máximo
dinámico, listas inactivas (opción A) e importación dinámica.

    source tests/test_env.sh
    DB_NAME=boltrex_pltest tests/prepare_test_db.sh
    DB_NAME=boltrex_pltest backend/.venv/bin/uvicorn main:app --app-dir backend --port 8001
    BOLTREX_API=http://localhost:8001/api DB_NAME=boltrex_pltest backend/.venv/bin/python tests/product_price_lists_check.py
"""
import csv
import io
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
                  headers={"X-Real-IP": f"10.3.{uuid.uuid4().int % 250}.1"})
assert r.ok, r.text
H = {"Authorization": f"Bearer {r.json()['access_token']}"}
tag = uuid.uuid4().hex[:6].upper()
lists = sorted(l["name"] for l in requests.get(f"{B}/price-lists", headers=H).json())
check("seed: existen default, mayorista y minorista", {"default", "mayorista", "minorista"} <= set(lists), lists)

P = lambda name, price: {"price_list_name": name, "price": price}


def create(code, prices):
    return requests.post(f"{B}/products", headers=H, json={"barcode": f"{code}{tag}", "name": f"Prod {code}", "category": "Otros",
                                                           "purchase_price": 100, "tax_rate": 0, "prices": prices})


def rejected(name, r, text):
    check(name, r.status_code == 400 and text in r.json().get("detail", ""), f"{r.status_code} {r.text[:200]}")


# --- Sin repetidos y solo listas existentes ---
rejected("'default' repetido → 400", create("R1", [P("default", 200), P("default", 210)]), "repetida")
rejected("'mayorista' repetido → 400", create("R2", [P("default", 200), P("mayorista", 150), P("mayorista", 160)]), "repetida")
rejected("lista que no existe → 400 'no existe'", create("R3", [P("default", 200), P("fantasma", 150)]), "'fantasma' no existe")
check("con las 3 listas existentes (el máximo actual) → OK", create("OK3", [P("default", 200), P("mayorista", 150), P("minorista", 180)]).ok)
rejected("4 precios con solo 3 listas (uno repetido) → 400", create("R4", [P("default", 200), P("mayorista", 150), P("minorista", 180), P("minorista", 190)]), "repetida")

# --- El máximo sigue al número de listas parametrizadas ---
DIST = f"distribuidor{tag.lower()}"
requests.post(f"{B}/price-lists", headers=H, json={"name": DIST, "description": "nueva", "is_active": True})
r = create("OK4", [P("default", 200), P("mayorista", 150), P("minorista", 180), P(DIST, 140)])
check("con una 4.ª lista creada, el producto acepta 4 precios", r.ok, r.text)
check("…y el formulario la recibe en la lista completa", DIST in [l["name"] for l in requests.get(f"{B}/price-lists", headers=H).json()])

# --- Lista inactiva (opción A) ---
r = requests.put(f"{B}/price-lists/{DIST}", headers=H, json={"is_active": False})
check("desactivar la 4.ª lista", r.ok, r.text)
rejected("producto NUEVO con precio en lista inactiva → 400", create("R5", [P("default", 200), P(DIST, 140)]), "inactiva")
bc = f"OK4{tag}"
r = requests.put(f"{B}/products/{bc}", headers=H, json={"name": "Prod OK4 editado"})
check("producto que YA tenía precio en la lista desactivada se puede editar (se conserva)", r.ok, r.text)
check("…y el precio de la lista inactiva sigue guardado", any(p["price_list_name"] == DIST for p in mongo.products.find_one({"barcode": bc})["prices"]))
r = requests.put(f"{B}/products/{bc}", headers=H, json={"prices": [P("default", 200), P("mayorista", 150), P("minorista", 180), P(DIST, 145)]})
check("…también se puede ajustar ese precio conservado", r.ok, r.text)
r = requests.put(f"{B}/products/{bc}", headers=H, json={"prices": [P("default", 200), P("mayorista", 150), P("minorista", 180)]})
check("…y quitarlo", r.ok and all(p["price_list_name"] != DIST for p in mongo.products.find_one({"barcode": bc})["prices"]), r.text)
rejected("…pero una vez quitado no se vuelve a agregar mientras esté inactiva", requests.put(f"{B}/products/{bc}", headers=H, json={
    "prices": [P("default", 200), P(DIST, 145)]}), "inactiva")
rejected("editar agregando una lista que no existe → 400", requests.put(f"{B}/products/{bc}", headers=H, json={
    "prices": [P("default", 200), P("fantasma", 150)]}), "no existe")

# --- Plantilla e importación dinámicas ---
def template_cols():
    r = requests.get(f"{B}/import/templates/products", headers=H)
    return next(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))

cols = template_cols()
active = sorted((l["name"] for l in requests.get(f"{B}/price-lists", headers=H).json() if l.get("is_active", True)), key=lambda n: (n != "default", n))
check("plantilla: una columna por lista ACTIVA ('default' primero; sin la inactiva)",
      [c for c in cols if c.startswith("price_")] == [f"price_{n}" for n in active] and f"price_{DIST}" not in cols, cols)
requests.put(f"{B}/price-lists/{DIST}", headers=H, json={"is_active": True})
check("plantilla: al activar la 4.ª lista aparece su columna", f"price_{DIST}" in template_cols())


def import_csv(text):
    return requests.post(f"{B}/import/products", headers=H, files={"file": ("p.csv", io.BytesIO(text.encode()), "text/csv")})

r = import_csv(f"barcode,name,category,purchase_price,tax_rate,price_default,price_{DIST}\nIM1{tag},Imp 1,Otros,100,0,200,150\n")
check("importar con la columna de la 4.ª lista → se guarda ese precio", r.ok and r.json()["success"] == 1
      and any(p["price_list_name"] == DIST for p in mongo.products.find_one({"barcode": f"IM1{tag}"})["prices"]), r.text)
r = import_csv(f"barcode,name,category,purchase_price,tax_rate,price_default,price_fantasma\nIM2{tag},Imp 2,Otros,100,0,200,150\n")
check("importar con columna de una lista inexistente → 400 con las listas válidas",
      r.status_code == 400 and "price_fantasma" in r.json()["detail"] and "price_default" in r.json()["detail"], r.text)
requests.put(f"{B}/price-lists/{DIST}", headers=H, json={"is_active": False})
r = import_csv(f"barcode,name,category,purchase_price,tax_rate,price_default,price_{DIST}\n"
               f"IM3{tag},Imp 3,Otros,100,0,200,150\nIM4{tag},Imp 4,Otros,100,0,200,\n")
errs = {e["row"]: e["error"] for e in r.json().get("errors", [])}
check("importar con la lista inactiva: la fila con precio en ella se rechaza con motivo, la vacía se importa",
      r.ok and r.json()["success"] == 1 and "inactiva" in errs.get(2, ""), r.json())

mongo.products.delete_many({"barcode": {"$regex": f"{tag}$"}})
mongo.price_lists.delete_many({"name": DIST})
print(f"\n{sum(results)}/{len(results)} pruebas OK")
sys.exit(0 if all(results) else 1)
