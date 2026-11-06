"""Pruebas de la pantalla Importar (CSV y Excel .xlsx) sin pandas — mantenimiento fase 1b.

    source tests/test_env.sh
    DB_NAME=boltrex_imtest tests/prepare_test_db.sh
    DB_NAME=boltrex_imtest backend/.venv/bin/uvicorn main:app --app-dir backend --port 8001
    BOLTREX_API=http://localhost:8001/api DB_NAME=boltrex_imtest backend/.venv/bin/python tests/import_check.py

Cubre lo que pandas hacía y lo que hacía mal: ceros a la izquierda, documentos numéricos con celdas
vacías ("123.0"), CSV de Excel en español (; y Latin-1), filas en blanco y números de fila reales.
"""
import io
import os
import sys
import time
import uuid

import openpyxl
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
                  headers={"X-Real-IP": f"10.7.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"})
H = {"Authorization": f"Bearer {r.json()['access_token']}"}
tag = uuid.uuid4().hex[:6].upper()


def xlsx(rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def send(kind, name, content, mime="text/csv"):
    return requests.post(f"{B}/import/{kind}", headers=H, files={"file": (name, io.BytesIO(content), mime)})


XMIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# --- 1. Categorías: Excel con fila en blanco, encabezados con espacios y una celda requerida vacía ---
CAT = f"Panes {tag}"
r = send("categories", "cat.xlsx", xlsx([[" name ", "description"], [CAT, "Del día"], [None, None], [None, "sin nombre"],
                                         [f"Lácteos {tag}", None]]), XMIME)
d = r.json()
check("categorías desde Excel: 2 creadas, la fila sin nombre rechazada con su motivo y su número real (4)",
      r.ok and d["success"] == 2 and d["total"] == 3 and d["errors"] == [{"row": 4, "error": "Falta el valor de: name"}], d)
check("…la fila totalmente vacía se ignora (no cuenta ni da error)", r.ok and d["total"] == 3)
check("…descripción vacía queda en '' (como antes)", mongo.categories.find_one({"name": f"Lácteos {tag}"})["description"] == "")
r = send("categories", "cat.xlsx", xlsx([["name"], [CAT]]), XMIME)
check("categoría repetida → error de la fila 2", r.ok and r.json()["errors"][0] == {"row": 2, "error": f"Categoría '{CAT}' ya existe"}, r.text)

# --- 2. Productos: CSV de Excel en español (; y Latin-1), con ceros a la izquierda ---
code1, code2 = f"00{tag}1", f"00{tag}2"
csv_es = (f"barcode;name;category;purchase_price;tax_rate;price_default;price_mayorista\n"
          f"{code1};Pan francés;{CAT};100;0;200;180\n"
          f"{code2};Mogolla;{CAT};150;19;300;\n"
          f"00{tag}3;Sin precio;{CAT};100;0;;\n").encode("latin-1")
r = send("products", "productos.csv", csv_es)
d = r.json()
p1 = mongo.products.find_one({"barcode": code1})
check("productos desde CSV con «;» y Latin-1 (como lo guarda Excel en español): 2 creados", r.ok and d["success"] == 2, d)
check("…el código conserva los ceros a la izquierda (pandas los quitaba)", p1 is not None and p1["barcode"] == code1, p1 and p1["barcode"])
check("…tildes bien leídas y precios de 2 listas", p1["name"] == "Pan francés" and {x["price_list_name"]: x["price"] for x in p1["prices"]} == {"default": 200.0, "mayorista": 180.0},
      (p1["name"], p1["prices"]))
check("…una lista vacía en la fila no crea precio", [x["price_list_name"] for x in mongo.products.find_one({"barcode": code2})["prices"]] == ["default"])
check("…sin precio default → la fila 4 se rechaza con el motivo de siempre", d["errors"] and d["errors"][0]["row"] == 4
      and "precio" in d["errors"][0]["error"].lower(), d["errors"])
# Excel con números: el costo y el IVA llegan como números
r = send("products", "p.xlsx", xlsx([["barcode", "name", "category", "purchase_price", "tax_rate", "price_default"],
                                      [f"X{tag}", "Galleta", CAT, 1200, 19, 2000.5]]), XMIME)
g = mongo.products.find_one({"barcode": f"X{tag}"})
check("productos desde Excel con números reales", r.ok and r.json()["success"] == 1 and g["purchase_price"] == 1200.0 and g["prices"][0]["price"] == 2000.5, r.text)
r = send("products", "p.csv", f"barcode,name,category,purchase_price,tax_rate,price_default\nY{tag},Malo,{CAT},abc,0,10\n".encode())
check("precio de compra no numérico → error de la fila con el motivo", r.ok and r.json()["errors"][0]["row"] == 2
      and "número" in r.json()["errors"][0]["error"], r.text)
r = send("products", "p.csv", f"barcode,name,category,purchase_price,tax_rate,price_premium\nZ{tag},X,{CAT},1,0,2\n".encode())
check("columna de precio sin lista → 400 con las listas válidas (igual que antes)", r.status_code == 400 and "price_default" in r.json()["detail"], r.text)

# --- 3. Clientes: Excel con documento numérico y celdas vacías ---
doc1, doc2 = int(f"7{int(tag, 16)}"), int(f"8{int(tag, 16)}")
r = send("clients", "clientes.xlsx", xlsx([
    ["document_type", "document_number", "first_name", "last_name", "phone", "email", "latitude", "longitude", "price_list"],
    ["CC", doc1, "Ana", "Ruiz", 3001234567, None, 4.6, -74.08, None],
    ["CC", doc2, "Luis", "Paz", None, "luis@example.com", None, None, "mayorista"],
    ["XX", 1, "Mal", "Tipo", None, None, None, None, None]]), XMIME)
d = r.json()
c1 = mongo.clients.find_one({"document_number": str(doc1)})
c2 = mongo.clients.find_one({"document_number": str(doc2)})
check("clientes desde Excel: 2 creados", r.ok and d["success"] == 2, d)
check("…el documento numérico queda «123456», no «123456.0» (con pandas pasaba si había celdas vacías)",
      c1 is not None and c2 is not None and ".0" not in c1["document_number"] + c2["document_number"], (c1 and c1["document_number"]))
check("…teléfono numérico sin «.0», coordenadas y lista por defecto", c1["phone"] == "3001234567" and c1["latitude"] == 4.6
      and c1["price_list"] == "default" and c1["email"] is None, c1)
check("…lista de precios propia y email", c2["price_list"] == "mayorista" and c2["email"] == "luis@example.com" and c2["phone"] is None, c2)
check("…tipo de documento inexistente → error de la fila 4", d["errors"] == [{"row": 4, "error": "Tipo de documento 'XX' no existe"}], d["errors"])

# --- 4. Proveedores: CSV UTF-8 con BOM (como lo exporta Excel «CSV UTF-8») ---
r = send("suppliers", "prov.csv", ("﻿name,contact_name,phone\n" + f"Molinos {tag},Pedro,6011234\n").encode("utf-8"))
s = mongo.suppliers.find_one({"name": f"Molinos {tag}"})
check("proveedores desde CSV UTF-8 con BOM (el encabezado «name» se reconoce)", r.ok and r.json()["success"] == 1 and s and s["contact_name"] == "Pedro", r.text)

# --- 5. Archivos no válidos ---
r = send("categories", "viejo.xls", b"cualquier cosa", "application/vnd.ms-excel")
check(".xls antiguo → 400 «guárdalo como .xlsx o CSV»", r.status_code == 400 and ".xlsx o CSV" in r.json()["detail"], r.text)
r = send("categories", "notas.txt", b"name\nX\n", "text/plain")
check("formato no soportado → 400", r.status_code == 400 and "no soportado" in r.json()["detail"], r.text)
r = send("categories", "vacio.csv", b"")
check("archivo vacío → 400 con motivo", r.status_code == 400 and "vacío" in r.json()["detail"], r.text)
r = send("categories", "c.csv", b"nombre,descripcion\nX,Y\n")
check("columnas requeridas faltantes → 400 «Columnas requeridas: name»", r.status_code == 400 and r.json()["detail"] == "Columnas requeridas: name", r.text)
r = send("categories", "roto.xlsx", b"no es un excel", XMIME)
check("Excel dañado → 400 con motivo", r.status_code == 400 and "Excel" in r.json()["detail"], r.text)

# --- 6. Plantillas siguen saliendo y se pueden reimportar ---
t = requests.get(f"{B}/import/templates/suppliers", headers=H)
check("la plantilla CSV sigue saliendo (con BOM para Excel)", t.ok and t.text.lstrip("\ufeff").startswith("name,contact_name"), t.text[:80])
check("la importación queda en la auditoría", mongo.audit_log.count_documents({"module": "import"}) >= 6)

ok = sum(results)
print(f"\n{ok}/{len(results)} pruebas OK")
sys.exit(0 if ok == len(results) else 1)
