"""Pruebas de índices únicos (backlog P0.7).

Uso (contra una BD de PRUEBA sembrada con init_rbac.py + seed_data.py):
    # Opcional, para probar el arranque con duplicados: antes de levantar el backend,
    #   backend/.venv/bin/python tests/indexes_check.py --plant-duplicates
    DB_NAME=boltrex_idxtest backend/.venv/bin/uvicorn main:app --app-dir backend --port 8001 > /tmp/boltrex_idx.log 2>&1
    BOLTREX_API=http://localhost:8001/api DB_NAME=boltrex_idxtest BACKEND_LOG=/tmp/boltrex_idx.log \
        backend/.venv/bin/python tests/indexes_check.py
"""
import os
# Contraseña del admin de la BD de prueba (ver tests/prepare_test_db.sh). Ya no existe admin123 (P1.10).
ADMIN_PASSWORD = os.environ.get("BOLTREX_ADMIN_PASSWORD", "Prueba-Admin-2026")
import asyncio
import io
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pymongo
import requests

DB_NAME = os.environ["DB_NAME"]
if DB_NAME == "boltrex":
    sys.exit("Negado: este test inserta duplicados a propósito; usa una BD de prueba.")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017/?directConnection=true")
mongo = pymongo.MongoClient(MONGO_URL)[DB_NAME]
PLANTED = "DUP-PLANTED"

if "--plant-duplicates" in sys.argv:
    mongo.products.drop_index("uniq_products_barcode") if "uniq_products_barcode" in mongo.products.index_information() else None
    for _ in range(2):
        mongo.products.insert_one({"barcode": PLANTED, "name": "Duplicado", "category": "Otros", "purchase_price": 1,
                                   "tax_rate": 0, "prices": [], "stock": 0})
    print(f"Plantados 2 productos con barcode {PLANTED}")
    sys.exit(0)

B = os.environ.get("BOLTREX_API", "http://localhost:8001/api")
LOG = os.environ.get("BACKEND_LOG")
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"{'OK ' if ok else 'FAIL'} {name}" + ("" if ok else f" -> {detail}"))


for _ in range(40):
    try:
        requests.get(B.rsplit("/api", 1)[0] + "/", timeout=1)
        break
    except Exception:
        time.sleep(0.5)

print("== Arranque con datos duplicados ==")
planted = mongo.products.count_documents({"barcode": PLANTED}) >= 2
check("el backend arrancó y responde", requests.get(B.rsplit("/api", 1)[0] + "/").ok)
if not planted:
    print("SKIP sin duplicados plantados (correr antes con --plant-duplicates para probar el arranque con duplicados)")
if planted and LOG:
    log = Path(LOG).read_text(errors="ignore")
    check("el log avisa qué índice no se creó y por qué", "uniq_products_barcode" in log and "duplicados" in log and PLANTED in log,
          [l for l in log.splitlines() if "ndice" in l][:3])
if planted:
    check("el índice de products.barcode NO se creó (hay duplicados)", "uniq_products_barcode" not in mongo.products.index_information())
check("los demás índices únicos sí se crearon", all(n in mongo[c].index_information() for c, n in [
    ("users_extended", "uniq_users_extended_email"), ("categories", "uniq_categories_name"),
    ("clients", "uniq_clients_document_type_document_number"), ("role_permissions", "uniq_role_permissions_role_name_module_slug")]))

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from core.indexes import INDEXES, ensure_indexes, duplicate_key_message  # noqa: E402


mongo.products.delete_one({"barcode": PLANTED})
report = asyncio.run(ensure_indexes())
check("tras corregir el duplicado, ensure_indexes crea el índice", "uniq_products_barcode" in mongo.products.index_information(), report.failed)
info = {s.name: mongo[s.collection].index_information().get(s.name, {}) for s in INDEXES}
check("ningún índice único tiene caducidad (TTL) por error",
      not [n for s, n in ((s, s.name) for s in INDEXES) if s.unique and "expireAfterSeconds" in info[n]],
      [s.name for s in INDEXES if s.unique and "expireAfterSeconds" in info[s.name]])
check("todo índice único declara su mensaje para el usuario", all(s.message for s in INDEXES if s.unique),
      [s.name for s in INDEXES if s.unique and not s.message])
check(f"todos los índices declarados existen ({len(INDEXES)})",
      all(s.name in mongo[s.collection].index_information() for s in INDEXES),
      [s.name for s in INDEXES if s.name not in mongo[s.collection].index_information()])

r = requests.post(f"{B}/auth/login", json={"email": "admin@boltrex.com", "password": ADMIN_PASSWORD})
H = {"Authorization": f"Bearer {r.json()['access_token']}"}
t = uuid.uuid4().hex[:5]


def race(label, path, body, expect_in_msg, n=15):
    with ThreadPoolExecutor(max_workers=n) as pool:
        resps = list(pool.map(lambda _: requests.post(f"{B}{path}", headers=H, json=body), range(n)))
    codes = [x.status_code for x in resps]
    msgs = {x.json().get("detail") for x in resps if x.status_code == 400}
    check(f"{label}: {n} peticiones simultáneas → solo 1 creada, ningún 500", codes.count(200) == 1 and codes.count(400) == n - 1, codes)
    check(f"{label}: los rechazados explican el motivo", msgs and all(isinstance(m, str) and expect_in_msg in m for m in msgs), msgs)
    print(f"       mensaje: {next(iter(msgs)) if msgs else '-'}")


print("== Duplicados simultáneos ==")
race("producto", "/products", {"barcode": f"B{t}", "name": "P", "category": "Otros", "purchase_price": 1, "tax_rate": 0, "prices": [{"price_list_name": "default", "price": 2}]}, f"B{t}")
race("cliente", "/clients", {"document_type": "CC", "document_number": f"9{t}", "first_name": "A", "last_name": "B"}, f"9{t}")
race("categoría", "/categories", {"name": f"Cat{t}"}, f"Cat{t}")
race("proveedor", "/suppliers", {"name": f"Prov{t}"}, f"Prov{t}")
race("lista de precios", "/price-lists", {"name": f"Lista{t}"}, f"Lista{t}")
race("usuario", "/rbac/users", {"email": f"u{t}@test.com", "password": "Clave-1234", "first_name": "U", "last_name": "T"}, f"u{t}@test.com")

print("== Mensajes del rechazo por índice (sin validación previa) ==")
csv = f"name,contact_name\nImp{t},A\nImp{t},B\n"
r = requests.post(f"{B}/import/suppliers", headers=H, files={"file": ("prov.csv", io.BytesIO(csv.encode()), "text/csv")})
errs = r.json().get("errors", []) if r.ok else []
check("importar CSV con proveedor repetido: 1 importado, la fila 3 explica el duplicado",
      r.ok and r.json()["success"] == 1 and errs and errs[0]["row"] == 3 and f"Imp{t}" in errs[0]["error"] and "Ya existe" in errs[0]["error"],
      r.text[:300])
if errs:
    print(f"       mensaje: fila {errs[0]['row']}: {errs[0]['error']}")
r = requests.post(f"{B}/clients", headers=H, json={"document_type": "NIT", "document_number": f"9{t}", "first_name": "A", "last_name": "B"})
check("mismo número con otro tipo de documento sí se permite (índice compuesto)", r.ok, r.text)

print(f"\n{sum(results)}/{len(results)} pruebas OK")
sys.exit(0 if all(results) else 1)
