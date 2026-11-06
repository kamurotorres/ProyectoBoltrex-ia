"""Pruebas de "sin contraseña por defecto" y cambio de contraseña (backlog P1.10).

    DB_NAME=boltrex_pwtest tests/prepare_test_db.sh
    DB_NAME=boltrex_pwtest backend/.venv/bin/uvicorn main:app --app-dir backend --port 8001
    BOLTREX_API=http://localhost:8001/api DB_NAME=boltrex_pwtest backend/.venv/bin/python tests/password_change_check.py

Usa solo la BD de prueba. Crea usuarios propios y deja al admin con su contraseña original.
"""
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pymongo
import requests

ADMIN_PASSWORD = os.environ.get("BOLTREX_ADMIN_PASSWORD", "Prueba-Admin-2026")
DB_NAME = os.environ["DB_NAME"]
if DB_NAME == "boltrex":
    sys.exit("Negado: usa una BD de prueba.")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017/?directConnection=true")
mongo = pymongo.MongoClient(MONGO_URL)[DB_NAME]
B = os.environ.get("BOLTREX_API", "http://localhost:8001/api")
ROOT = Path(__file__).resolve().parent.parent
PY = str(ROOT / "backend" / ".venv" / "bin" / "python")
CHANGE_REQUIRED = "Debes cambiar tu contraseña antes de continuar."
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"{'OK ' if ok else 'FAIL'} {name}" + ("" if ok else f" -> {detail}"))


def ip():
    return f"10.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"


def login(email, password):
    return requests.post(f"{B}/auth/login", json={"email": email, "password": password}, headers={"X-Real-IP": ip()})


def auth(token):
    return {"Authorization": f"Bearer {token}"}


for _ in range(30):
    try:
        requests.get(B.rsplit("/api", 1)[0] + "/", timeout=1)
        break
    except Exception:
        time.sleep(0.5)

r = login("admin@boltrex.com", ADMIN_PASSWORD)
assert r.status_code == 200, r.text
A = auth(r.json()["access_token"])
check("admin de prueba entra sin cambio pendiente", r.json()["user"].get("must_change_password") is False, r.json()["user"])

# --- 1. Scripts: sin ADMIN_INITIAL_PASSWORD no se crea admin; con admin123 tampoco ---
scratch_db = "boltrex_pwscripttest"
env = {**os.environ, "DB_NAME": scratch_db, "MONGO_URL": MONGO_URL}
env["ADMIN_INITIAL_PASSWORD"] = ""  # vacía: backend/.env no la rellena (load_dotenv no sobrescribe)
pymongo.MongoClient(MONGO_URL).drop_database(scratch_db)
p = subprocess.run([PY, str(ROOT / "scripts" / "seed_data.py")], env=env, capture_output=True, text=True)
check("seed sin ADMIN_INITIAL_PASSWORD → se detiene con mensaje", p.returncode != 0 and "ADMIN_INITIAL_PASSWORD" in p.stderr, p.stderr[-300:])
p = subprocess.run([PY, str(ROOT / "scripts" / "init_rbac.py")], env={**env, "ADMIN_INITIAL_PASSWORD": "admin123"}, capture_output=True, text=True)
check("init_rbac con admin123 → rechazada", p.returncode != 0 and "no es válida" in p.stderr, p.stderr[-300:])
p = subprocess.run([PY, str(ROOT / "scripts" / "init_rbac.py")], env={**env, "ADMIN_INITIAL_PASSWORD": "corta"}, capture_output=True, text=True)
check("init_rbac con contraseña corta → rechazada", p.returncode != 0 and "8 caracteres" in p.stderr, p.stderr[-300:])
sdb = pymongo.MongoClient(MONGO_URL)[scratch_db]
check("ningún admin creado tras los rechazos", sdb.users_extended.count_documents({}) == 0)
p = subprocess.run([PY, str(ROOT / "scripts" / "init_rbac.py")], env={**env, "ADMIN_INITIAL_PASSWORD": "Inicial-Segura-1"}, capture_output=True, text=True)
adm = sdb.users_extended.find_one({"email": "admin@boltrex.com"})
check("con contraseña válida crea el admin marcado para cambio", p.returncode == 0 and adm and adm.get("must_change_password") is True, p.stderr[-300:])
check("el script no imprime la contraseña", "Inicial-Segura-1" not in p.stdout, p.stdout)
pymongo.MongoClient(MONGO_URL).drop_database(scratch_db)

# --- 2. Usuario con cambio obligatorio ---
email = f"pw_{uuid.uuid4().hex[:8]}@example.com"
r = requests.post(f"{B}/rbac/users", headers=A, json={"email": email, "password": "Temporal-123", "first_name": "Pw", "last_name": "Test"})
check("admin crea usuario", r.status_code == 200, r.text)
r = requests.post(f"{B}/rbac/users/{email}/roles", headers=A, json=["Administrador"])
check("admin le asigna rol", r.status_code == 200, r.text)
mongo.users_extended.update_one({"email": email}, {"$set": {"must_change_password": True}})

r = login(email, "Temporal-123")
check("login devuelve must_change_password=true", r.status_code == 200 and r.json()["user"]["must_change_password"] is True, r.text)
U = auth(r.json()["access_token"])
r = requests.get(f"{B}/auth/me", headers=U)
check("/auth/me permitido con cambio pendiente", r.status_code == 200 and r.json()["must_change_password"] is True, r.text)
for path in ("/products", "/clients", "/rbac/users", "/invoices"):
    r = requests.get(f"{B}{path}", headers=U)
    check(f"GET {path} bloqueado con mensaje", r.status_code == 403 and r.json().get("detail") == CHANGE_REQUIRED, f"{r.status_code} {r.text[:120]}")

cases = [
    ({"current_password": "mala-actual", "new_password": "Nueva-Clave-9"}, "La contraseña actual no es correcta."),
    ({"current_password": "Temporal-123", "new_password": "corta"}, "al menos 8 caracteres"),
    ({"current_password": "Temporal-123", "new_password": "admin123"}, "demasiado común"),
    ({"current_password": "Temporal-123", "new_password": "Temporal-123"}, "distinta de la actual"),
]
for body, msg in cases:
    r = requests.post(f"{B}/auth/change-password", headers=U, json=body)
    check(f"cambio rechazado: {msg}", r.status_code == 400 and msg in r.json().get("detail", ""), r.text)

r = requests.post(f"{B}/auth/change-password", headers=U, json={"current_password": "Temporal-123", "new_password": "Nueva-Clave-9"})
check("cambio válido aceptado", r.status_code == 200 and "actualizada" in r.json().get("message", ""), r.text)
r = requests.get(f"{B}/products", headers=U)
check("tras el cambio, el mismo token ya opera", r.status_code == 200, r.status_code)
check("contraseña vieja ya no entra", login(email, "Temporal-123").status_code == 401)
r = login(email, "Nueva-Clave-9")
check("contraseña nueva entra sin cambio pendiente", r.status_code == 200 and r.json()["user"]["must_change_password"] is False, r.text)
U = auth(r.json()["access_token"])

# --- 3. Cambio voluntario y reglas en Usuarios ---
r = requests.post(f"{B}/auth/change-password", headers=U, json={"current_password": "Nueva-Clave-9", "new_password": "Otra-Clave-10"})
check("cambio voluntario sin bandera", r.status_code == 200, r.text)
r = requests.post(f"{B}/auth/change-password", json={"current_password": "x", "new_password": "Otra-Clave-11"})
check("change-password sin token → rechazado", r.status_code in (401, 403), r.status_code)
r = requests.post(f"{B}/rbac/users", headers=A, json={"email": f"x_{uuid.uuid4().hex[:6]}@example.com", "password": "123", "first_name": "X", "last_name": "Y"})
check("crear usuario con contraseña corta → 400 con mensaje", r.status_code == 400 and "8 caracteres" in r.json().get("detail", ""), r.text)
r = requests.put(f"{B}/rbac/users/{email}", headers=A, json={"password": "admin123"})
check("editar usuario con admin123 → 400 con mensaje", r.status_code == 400 and "común" in r.json().get("detail", ""), r.text)
r = requests.put(f"{B}/rbac/users/{email}", headers=A, json={"first_name": "Pw2", "password": ""})
check("editar sin contraseña sigue funcionando", r.status_code == 200, r.text)

# --- 4. Detección al arrancar: admin con admin123 queda marcado ---
sys.path.insert(0, str(ROOT / "backend"))
import asyncio  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from core.security import flag_default_passwords, get_password_hash  # noqa: E402

legacy = f"legacy_{uuid.uuid4().hex[:8]}@example.com"
mongo.users_extended.insert_one({"email": legacy, "first_name": "L", "last_name": "G", "is_active": True,
                                 "roles": ["Administrador"], "hashed_password": get_password_hash("admin123"),
                                 "created_at": "2026-01-01T00:00:00+00:00"})


async def run_flag():
    return await flag_default_passwords(AsyncIOMotorClient(MONGO_URL)[DB_NAME])

n = asyncio.run(run_flag())
check("arranque marca al admin con admin123", n >= 1 and mongo.users_extended.find_one({"email": legacy}).get("must_change_password") is True, n)
check("arranque no marca al admin de prueba", not mongo.users_extended.find_one({"email": "admin@boltrex.com"}).get("must_change_password"))
r = login(legacy, "admin123")
check("admin123 entra pero con cambio obligatorio", r.status_code == 200 and r.json()["user"]["must_change_password"] is True, r.text)

mongo.users_extended.delete_many({"email": {"$in": [email, legacy]}})
mongo.users.delete_many({"email": {"$in": [email, legacy]}})

print(f"\n{sum(results)}/{len(results)} OK")
sys.exit(0 if all(results) else 1)
