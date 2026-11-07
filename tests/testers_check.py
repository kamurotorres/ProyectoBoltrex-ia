"""Rol «Supervisor de pruebas» y usuarios de prueba (backend/tools/crear_rol_pruebas.py, 2026-11-08).

    scripts/run_all_tests.sh testers
Ejecuta el script contra la BD de prueba y entra como uno de los usuarios: debe cambiar la contraseña, puede
probar los módulos de trabajo y NO puede tocar Usuarios, Roles, Permisos, Auditoría ni el reinicio de fábrica.
"""
import json
import os
import subprocess
import sys
import time
import uuid

import pymongo
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_NAME = os.environ["DB_NAME"]
if DB_NAME == "boltrex":
    sys.exit("Negado: usa una BD de prueba.")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017/?directConnection=true")
mongo = pymongo.MongoClient(MONGO_URL, tz_aware=True)[DB_NAME]
B = os.environ.get("BOLTREX_API", "http://localhost:8001/api")
PY = os.environ.get("PY", os.path.join(ROOT, "backend", ".venv", "bin", "python"))
ROLE = "Supervisor de pruebas"
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"{'OK ' if ok else 'FAIL'} {name}" + ("" if ok else f" -> {detail}"))


def run_tool(*args):
    out = subprocess.run([PY, os.path.join(ROOT, "backend", "tools", "crear_rol_pruebas.py"), "--json", *args],
                         cwd=os.path.join(ROOT, "backend"), env={**os.environ, "DB_NAME": DB_NAME, "MONGO_URL": MONGO_URL},
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout.strip().splitlines()[-1])


def login(email, pw):
    return requests.post(f"{B}/auth/login", json={"email": email, "password": pw},
                         headers={"X-Real-IP": f"10.9.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"})


for _ in range(30):
    try:
        requests.get(B.rsplit("/api", 1)[0] + "/", timeout=1)
        break
    except Exception:
        time.sleep(0.5)

# Por si una corrida anterior dejó los usuarios: se empieza limpio (BD de prueba).
mongo.users_extended.delete_many({"email": {"$in": ["johan@boltrex.com", "may@boltrex.com", "alexis@boltrex.com"]}})

# --- 1. El script crea el rol y los usuarios ---
first = run_tool()
mods = first["modules"]
check("rol: sin Usuarios, Roles ni Permisos", not {"users", "roles", "permissions"} & set(mods), mods)
check("rol: el resto de los módulos (18)", len(mods) == 18 and {"purchases", "inventory", "import", "price-lists", "adjustment-reasons"} <= set(mods), mods)
perms = list(mongo.role_permissions.find({"role_name": ROLE}, {"_id": 0}))
check("rol: ver/crear/editar/eliminar en cada módulo", len(perms) == 18 and all(p["permissions"] == {"read": True, "create": True, "update": True, "delete": True} for p in perms))
pw = first["passwords"]
check("3 usuarios con contraseña temporal", sorted(pw) == ["alexis@boltrex.com", "johan@boltrex.com", "may@boltrex.com"] and all(pw.values()), pw)
u = mongo.users_extended.find_one({"email": "johan@boltrex.com"})
check("usuario: activo, con el rol y cambio de contraseña pendiente", u and u["is_active"] and u["roles"] == [ROLE] and u["must_change_password"] is True, u)
check("auditoría: registra quién lo hizo (el script)", mongo.audit_log.count_documents({"actor_email": "script:crear_rol_pruebas", "entity_id": "johan@boltrex.com"}) >= 1)

# --- 2. Primer ingreso: debe cambiar la contraseña ---
r = login("johan@boltrex.com", pw["johan@boltrex.com"])
check("entra con la contraseña temporal", r.ok, r.text[:200])
H = {"Authorization": f"Bearer {r.json()['access_token']}"} if r.ok else {}
check("al entrar se le pide cambiarla", r.ok and r.json()["user"]["must_change_password"] is True)
r = requests.get(f"{B}/products", headers=H)
check("antes de cambiarla no puede usar la app", r.status_code == 403 and "cambiar tu contraseña" in r.text, r.text[:200])
NEW = "Johan-Prueba-2026"
r = requests.post(f"{B}/auth/change-password", headers=H, json={"current_password": pw["johan@boltrex.com"], "new_password": NEW})
check("cambia su contraseña", r.ok, r.text[:200])
r = login("johan@boltrex.com", NEW)
H = {"Authorization": f"Bearer {r.json()['access_token']}"} if r.ok else {}
check("entra con su contraseña nueva", r.ok and r.json()["user"]["must_change_password"] is False, r.text[:200])

# --- 3. Puede probar los módulos de trabajo ---
tag = uuid.uuid4().hex[:6].upper()
r = requests.post(f"{B}/categories", headers=H, json={"name": f"Cat {tag}"})
check("crea una categoría", r.ok, r.text[:200])
r = requests.delete(f"{B}/categories/Cat {tag}", headers=H)
check("elimina una categoría", r.ok, r.text[:200])
code = f"TST{tag}"
r = requests.post(f"{B}/products", headers=H, json={"barcode": code, "name": "Producto prueba", "category": "Otros", "purchase_price": 100,
                                                   "tax_rate": 0, "prices": [{"price_list_name": "default", "price": 200}]})
check("crea un producto", r.ok, r.text[:200])
r = requests.post(f"{B}/purchases", headers=H, json={"supplier_name": "Proveedor", "items": [
    {"barcode": code, "product_name": "Producto prueba", "quantity": 5, "unit_cost": 100, "total": 500}]})
check("crea una compra", r.ok, r.text[:200])
r = requests.post(f"{B}/purchases/{r.json()['purchase_number']}/confirm", headers=H) if r.ok else r
check("procesa la compra (el Supervisor de fábrica no podía)", r.ok, r.text[:200])
for path in ("/inventory", "/reports/sales", "/price-lists", "/adjustment-reasons", "/payment-methods", "/ticket-config", "/fios", "/cash/current"):
    r = requests.get(f"{B}{path}", headers=H)
    check(f"puede ver {path}", r.ok, f"{r.status_code} {r.text[:120]}")

# --- 4. NO puede administrar usuarios, roles, permisos ni lo que es solo del Administrador ---
for method, path, body, name in [
    ("get", "/rbac/users", None, "ver usuarios"),
    ("post", "/rbac/users", {"email": f"x{tag.lower()}@x.com", "password": "Otra-Clave-2026", "first_name": "X", "last_name": "Y"}, "crear usuarios"),
    ("post", "/rbac/users/johan@boltrex.com/roles", ["Administrador"], "darse el rol Administrador"),
    ("post", "/rbac/roles", {"name": f"Rol {tag}"}, "crear roles"),
    ("post", "/rbac/permissions", {"role_name": ROLE, "module_slug": "users", "permissions": {"read": True}}, "darse permisos"),
    ("get", "/audit", None, "ver la auditoría"),
    ("post", "/system/factory-reset", {"password": NEW}, "reinicio de fábrica"),
]:
    r = getattr(requests, method)(f"{B}{path}", headers=H, **({"json": body} if body is not None else {}))
    check(f"NO puede {name}", r.status_code == 403, f"{r.status_code} {r.text[:150]}")
check("sigue sin el rol Administrador", mongo.users_extended.find_one({"email": "johan@boltrex.com"})["roles"] == [ROLE])

# --- 5. Repetir el script no duplica ni cambia contraseñas; --reset da temporales nuevas ---
again = run_tool()
check("repetir: no cambia contraseñas", all(v is None for v in again["passwords"].values()), again["passwords"])
check("repetir: no duplica permisos ni usuarios", mongo.role_permissions.count_documents({"role_name": ROLE}) == 18
      and mongo.roles.count_documents({"name": ROLE}) == 1 and mongo.users_extended.count_documents({"email": "johan@boltrex.com"}) == 1)
check("repetir: Johan sigue entrando con su contraseña", login("johan@boltrex.com", NEW).ok)
reset = run_tool("--reset")
check("--reset: contraseñas temporales nuevas", all(reset["passwords"].values()) and reset["passwords"]["johan@boltrex.com"] != pw["johan@boltrex.com"])
r = login("johan@boltrex.com", reset["passwords"]["johan@boltrex.com"])
check("--reset: entra con la temporal y debe cambiarla otra vez", r.ok and r.json()["user"]["must_change_password"] is True, r.text[:200])

total = len(results)
passed = sum(results)
print(f"\n{passed}/{total} pruebas OK")
sys.exit(0 if passed == total else 1)
