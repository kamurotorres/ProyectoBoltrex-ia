"""Pruebas de IVA por producto y precios de venta obligatorios (backlog P1.16 y P1.17).

    DB_NAME=boltrex_prtest tests/prepare_test_db.sh
    DB_NAME=boltrex_prtest backend/.venv/bin/uvicorn main:app --app-dir backend --port 8001
    BOLTREX_API=http://localhost:8001/api DB_NAME=boltrex_prtest backend/.venv/bin/python tests/pricing_check.py
"""
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
                  headers={"X-Real-IP": f"10.7.{uuid.uuid4().int % 250}.1"})
assert r.ok, r.text
H = {"Authorization": f"Bearer {r.json()['access_token']}"}
tag = uuid.uuid4().hex[:6].upper()
PL = f"Mayor{tag}"
requests.post(f"{B}/price-lists", headers=H, json={"name": PL, "description": "x", "is_active": True})


def product(code, **over):
    body = {"barcode": f"{code}{tag}", "name": f"Prod {code}", "category": "Otros", "purchase_price": 100,
            "tax_rate": 0, "prices": [{"price_list_name": "default", "price": 200}]}
    body.update(over)
    return requests.post(f"{B}/products", headers=H, json=body)


def rejected(name, r, text):
    check(name, r.status_code == 400 and text in r.json().get("detail", ""), f"{r.status_code} {r.text[:200]}")


# --- P1.16: IVA entre 0 y 100 ---
check("IVA 0 aceptado", product("I0", tax_rate=0).ok)
check("IVA 100 aceptado (límite)", product("I100", tax_rate=100).ok)
check("IVA 5 aceptado", product("I5", tax_rate=5).ok)
rejected("IVA negativo → 400", product("IN", tax_rate=-19), "entre 0 y 100")
rejected("IVA mayor a 100 → 400", product("IG", tax_rate=100.01), "entre 0 y 100")
check("los rechazados no se crean", mongo.products.count_documents({"barcode": {"$in": [f"IN{tag}", f"IG{tag}"]}}) == 0)

# --- P1.17: precios obligatorios ---
rejected("sin precios → 400 'No se puede crear un producto sin precios'", product("NP", prices=[]), "sin precios de venta")
rejected("sin precio 'default' → 400", product("ND", prices=[{"price_list_name": PL, "price": 300}]), "'default' es obligatorio")
rejected("precio 0 → 400", product("Z", prices=[{"price_list_name": "default", "price": 0}]), "mayor a 0")
rejected("precio menor que el de compra → 400", product("LT", prices=[{"price_list_name": "default", "price": 99.99}]), "no puede ser menor que el precio de compra")
rejected("cualquier lista menor que el costo → 400", product("LT2", prices=[{"price_list_name": "default", "price": 200}, {"price_list_name": PL, "price": 50}]), f"'{PL}'")
check("precio IGUAL al de compra aceptado", product("EQ", prices=[{"price_list_name": "default", "price": 100}]).ok)
rejected("lista repetida → 400", product("DUP", prices=[{"price_list_name": "default", "price": 200}, {"price_list_name": "default", "price": 210}]), "repetida")
rejected("precio de compra negativo → 400", product("NC", purchase_price=-1), "negativo")

# --- Editar ---
bc = f"ED{tag}"
product("ED", prices=[{"price_list_name": "default", "price": 200}, {"price_list_name": PL, "price": 150}])
rejected("editar quitando todos los precios → 400", requests.put(f"{B}/products/{bc}", headers=H, json={"prices": []}), "sin precios")
rejected("editar subiendo el costo por encima de un precio → 400", requests.put(f"{B}/products/{bc}", headers=H, json={"purchase_price": 160}), "no puede ser menor que el precio de compra")
rejected("editar IVA a 150 → 400", requests.put(f"{B}/products/{bc}", headers=H, json={"tax_rate": 150}), "entre 0 y 100")
check("…y el producto queda como estaba", mongo.products.find_one({"barcode": bc})["purchase_price"] == 100)
check("editar válido (costo 140, IVA 19) → OK", requests.put(f"{B}/products/{bc}", headers=H, json={"purchase_price": 140, "tax_rate": 19}).ok)

# --- Venta: precio de la lista del cliente o 'default'; IVA del producto ---
pn = requests.post(f"{B}/purchases", headers=H, json={"supplier_name": "Prov PR", "items": [
    {"barcode": bc, "product_name": "x", "quantity": 20, "unit_cost": 100, "total": 2000},
    {"barcode": f"I5{tag}", "product_name": "x", "quantity": 20, "unit_cost": 100, "total": 2000}]}).json()["purchase_number"]
requests.post(f"{B}/purchases/{pn}/confirm", headers=H)
c_may, c_min, c_def = f"41{int(tag, 16)}", f"42{int(tag, 16)}", f"43{int(tag, 16)}"
requests.post(f"{B}/clients", headers=H, json={"document_type": "CC", "document_number": c_may, "first_name": "Cli", "last_name": "Mayor", "price_list": PL})
requests.post(f"{B}/clients", headers=H, json={"document_type": "CC", "document_number": c_min, "first_name": "Cli", "last_name": "Minor", "price_list": "minorista"})
requests.post(f"{B}/clients", headers=H, json={"document_type": "CC", "document_number": c_def, "first_name": "Cli", "last_name": "Def"})
item = lambda code: {"barcode": code, "product_name": "x", "quantity": 1, "unit_price": 1, "tax_rate": 50, "subtotal": 1, "tax_amount": 0, "total": 1}
sell = lambda doc, code: requests.post(f"{B}/invoices", headers=H, json={"client_document": doc, "client_document_type": "CC",
                                                                          "payment_status": "pagado", "payment_method": "Efectivo", "items": [item(code)]})
r = sell(c_may, bc)
it = r.json()["items"][0]
check("cliente con lista propia → precio de su lista (150)", r.ok and abs(it["unit_price"] - 150) < 0.01, it)
check("IVA = el del producto (19 %), no el que envía el navegador", abs(it["tax_rate"] - 19) < 0.01 and abs(it["tax_amount"] - 28.5) < 0.01, it)
r = sell(c_min, bc)
it = r.json()["items"][0]
check("lista sin precio para el producto → se toma 'default' (200), no costo×1,3", r.ok and abs(it["unit_price"] - 200) < 0.01, it)
r = sell(c_def, f"I5{tag}")
it = r.json()["items"][0]
check("IVA 5 % del producto aplicado", r.ok and abs(it["tax_amount"] - 10) < 0.01 and abs(r.json()["total"] - 210) < 0.01, r.json().get("total"))

# Producto antiguo sin precio (creado antes de la regla): no se vende y el motivo es claro
old = f"OLD{tag}"
mongo.products.insert_one({"barcode": old, "name": "Producto viejo", "category": "Otros", "purchase_price": 10, "tax_rate": 0, "prices": [], "stock": 5})
r = sell(c_def, old)
check("producto sin ningún precio → 400 'no tiene precio de venta' (sin vender)",
      r.status_code == 400 and "no tiene precio de venta" in r.json()["detail"] and mongo.products.find_one({"barcode": old})["stock"] == 5, r.text)
rejected("…y editarlo sin agregarle precio también se rechaza", requests.put(f"{B}/products/{old}", headers=H, json={"name": "Viejo 2"}), "sin precios")
check("agregándole el precio 'default' se arregla", requests.put(f"{B}/products/{old}", headers=H, json={"prices": [{"price_list_name": "default", "price": 20}]}).ok)
check("…y ya se puede vender", sell(c_def, old).ok)

# --- Importar productos: mismas reglas por fila ---
csv = ("barcode,name,category,purchase_price,tax_rate,price_default,price_mayorista\n"
       f"IMP1{tag},Ok,Otros,100,19,200,150\n"
       f"IMP2{tag},Sin precio,Otros,100,19,,\n"
       f"IMP3{tag},IVA malo,Otros,100,120,200,\n"
       f"IMP4{tag},Bajo costo,Otros,100,0,90,\n"
       f"IMP5{tag},Sin default,Otros,100,0,,150\n")
r = requests.post(f"{B}/import/products", headers=H, files={"file": ("p.csv", io.BytesIO(csv.encode()), "text/csv")})
d = r.json()
errs = {e["row"]: e["error"] for e in d.get("errors", [])}
check("importación: 1 fila creada de 5", r.ok and d["success"] == 1, d)
check("…fila sin precios rechazada con motivo", "sin precios" in errs.get(3, ""), errs)
check("…fila con IVA 120 rechazada con motivo", "entre 0 y 100" in errs.get(4, ""), errs)
check("…fila con precio < costo rechazada con motivo", "menor que el precio de compra" in errs.get(5, ""), errs)
check("…fila sin precio default rechazada con motivo", "'default' es obligatorio" in errs.get(6, ""), errs)

mongo.products.delete_many({"barcode": {"$regex": f"{tag}$"}})
print(f"\n{sum(results)}/{len(results)} pruebas OK")
sys.exit(0 if all(results) else 1)
