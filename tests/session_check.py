"""Pruebas de sesiones: inactividad, duración máxima y cierre/revocación (backlog P1.11).

Requiere un backend con tiempos cortos para no esperar 1 hora real:
    DB_NAME=boltrex_sstest tests/prepare_test_db.sh
    DB_NAME=boltrex_sstest SESSION_IDLE_MINUTES=0.1 ACCESS_TOKEN_EXPIRE_MINUTES=0.3 \\
        backend/.venv/bin/uvicorn main:app --app-dir backend --port 8001
    BOLTREX_API=http://localhost:8001/api DB_NAME=boltrex_sstest SESSION_IDLE_MINUTES=0.1 \\
        ACCESS_TOKEN_EXPIRE_MINUTES=0.3 backend/.venv/bin/python tests/session_check.py
(Los tiempos deben coincidir con los del backend.)
"""
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pymongo
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

ADMIN_PASSWORD = os.environ.get("BOLTREX_ADMIN_PASSWORD", "Prueba-Admin-2026")
DB_NAME = os.environ["DB_NAME"]
if DB_NAME == "boltrex":
    sys.exit("Negado: usa una BD de prueba.")
IDLE_S = float(os.environ.get("SESSION_IDLE_MINUTES", "0.1")) * 60
MAX_S = float(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "0.3")) * 60
if IDLE_S > 30 or MAX_S > 60:
    sys.exit("Arranca el backend con SESSION_IDLE_MINUTES y ACCESS_TOKEN_EXPIRE_MINUTES cortos (ver docstring).")
TOUCH_S = min(60.0, IDLE_S / 10)
mongo = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017/?directConnection=true"))[DB_NAME]
B = os.environ.get("BOLTREX_API", "http://localhost:8001/api")

MSG_IDLE = "Tu sesión se cerró por inactividad. Inicia sesión de nuevo."
MSG_EXPIRED = "Tu sesión expiró. Inicia sesión de nuevo."
MSG_CLOSED = "Tu sesión fue cerrada. Inicia sesión de nuevo."
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"{'OK ' if ok else 'FAIL'} {name}" + ("" if ok else f" -> {detail}"))


def ip():
    return f"10.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"


def login_raw(email, password):
    return requests.post(f"{B}/auth/login", json={"email": email, "password": password}, headers={"X-Real-IP": ip()})


def login(email, password):
    r = login_raw(email, password)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def me(h):
    return requests.get(f"{B}/auth/me", headers=h)


def is_401(r, msg):
    return r.status_code == 401 and r.json().get("detail") == msg


for _ in range(30):
    try:
        requests.get(B.rsplit("/api", 1)[0] + "/", timeout=1)
        break
    except Exception:
        time.sleep(0.5)

# --- Login y configuración ---
r = login_raw("admin@boltrex.com", ADMIN_PASSWORD)
cfg = r.json().get("session", {})
check("login devuelve tiempos de sesión", abs(cfg.get("idle_minutes", 0) * 60 - IDLE_S) < 0.01 and cfg.get("warning_minutes") is not None
      and abs(cfg.get("max_minutes", 0) * 60 - MAX_S) < 0.01, cfg)
A = {"Authorization": f"Bearer {r.json()['access_token']}"}
check("/auth/me devuelve tiempos de sesión", me(A).json().get("session", {}).get("idle_minutes") == cfg.get("idle_minutes"))
sessions_before = mongo.sessions.count_documents({})
check("login fallido no crea sesión", login_raw("admin@boltrex.com", "mala-clave-1").status_code == 401
      and mongo.sessions.count_documents({}) == sessions_before)
idx = {i["name"]: i for i in mongo.sessions.list_indexes()}
check("índice TTL en sessions.expires_at", idx.get("ttl_sessions_expires_at", {}).get("expireAfterSeconds") == 0, list(idx))

# Usuario de prueba
U = f"ss_{uuid.uuid4().hex[:8]}@example.com"
PW = "Sesion-Clave-1"
requests.post(f"{B}/rbac/users", headers=A, json={"email": U, "password": PW, "first_name": "S", "last_name": "T"})
requests.post(f"{B}/rbac/users/{U}/roles", headers=A, json=["Vendedor"])

# --- Inactividad ---
h = login(U, PW)
check("sesión recién creada funciona", me(h).status_code == 200)
time.sleep(IDLE_S + TOUCH_S + 1.5)
r = me(h)
check("sin actividad → 401 por inactividad", is_401(r, MSG_IDLE), f"{r.status_code} {r.text}")
check("la sesión inactiva se borra del servidor", mongo.sessions.count_documents({"email": U}) == 0)
check("el cierre por inactividad queda en la auditoría (P1.12)",
      mongo.audit_log.count_documents({"action": "session_idle", "actor_email": U}) == 1)
check("tras la inactividad hay que volver a entrar (el mismo token sigue rechazado)", me(h).status_code == 401)

# --- La actividad mantiene viva la sesión ---
h = login(U, PW)
start = time.time()
alive = True
while time.time() - start < IDLE_S * 2:
    time.sleep(IDLE_S / 3)
    alive = alive and requests.post(f"{B}/auth/ping", headers=h).status_code == 200
check(f"con 'sigo aquí' cada {IDLE_S/3:.0f}s la sesión dura más que la inactividad", alive and me(h).status_code == 200)

# --- Duración máxima, aunque haya actividad ---
while time.time() - start < MAX_S + 1:
    time.sleep(min(IDLE_S / 3, 2))
    last = requests.post(f"{B}/auth/ping", headers=h)
    if last.status_code == 401:
        break
check("al cumplir la duración máxima → 401 'expiró' aunque haya actividad", is_401(last, MSG_EXPIRED), f"{last.status_code} {last.text}")
check("…y no antes de tiempo", time.time() - start >= MAX_S - 1, time.time() - start)
check("la expiración por duración máxima queda en la auditoría (una sola vez)",
      mongo.audit_log.count_documents({"action": "session_expired", "actor_email": U}) == 1)

# La sesión del admin también quedó inactiva durante las esperas: nueva sesión.
A = login("admin@boltrex.com", ADMIN_PASSWORD)

# --- Salir ---
h = login(U, PW)
r = requests.post(f"{B}/auth/logout", headers=h)
check("logout cierra la sesión en el servidor", r.status_code == 200 and is_401(me(h), MSG_CLOSED), r.text)

# --- Salir de todos los equipos ---
h1, h2, h3 = login(U, PW), login(U, PW), login(U, PW)
r = requests.post(f"{B}/auth/logout-all", headers=h1)
check("logout-all informa cuántas cerró", r.status_code == 200 and r.json().get("closed_sessions") == 3, r.text)
check("logout-all cierra todas (incluida la actual)", all(me(x).status_code == 401 for x in (h1, h2, h3)))
check("logout-all no toca sesiones de otros usuarios", me(A).status_code == 200)

# --- Cambio de contraseña propio: cierra los otros equipos, conserva el actual ---
h1, h2 = login(U, PW), login(U, PW)
r = requests.post(f"{B}/auth/change-password", headers=h1, json={"current_password": PW, "new_password": "Sesion-Clave-2"})
PW = "Sesion-Clave-2"
check("cambio propio: la sesión actual sigue", r.status_code == 200 and me(h1).status_code == 200, r.text)
check("cambio propio: el otro equipo queda cerrado", is_401(me(h2), MSG_CLOSED))

# --- Acciones del administrador ---
h = login(U, PW)
r = requests.put(f"{B}/rbac/users/{U}", headers=A, json={"password": "Sesion-Clave-3"})
PW = "Sesion-Clave-3"
check("admin cambia la contraseña → sesiones del usuario cerradas", r.status_code == 200 and is_401(me(h), MSG_CLOSED), r.text)
check("…y la del admin sigue", me(A).status_code == 200)

h = login(U, PW)
requests.put(f"{B}/rbac/users/{U}", headers=A, json={"first_name": "Otro"})
check("editar solo el nombre NO cierra sesiones", me(h).status_code == 200)
requests.post(f"{B}/rbac/users/{U}/roles", headers=A, json=["Vendedor"])
check("asignar los mismos roles NO cierra sesiones", me(h).status_code == 200)
requests.post(f"{B}/rbac/users/{U}/roles", headers=A, json=["Vendedor", "Supervisor"])
check("cambiar roles → sesiones cerradas", is_401(me(h), MSG_CLOSED))

h = login(U, PW)
requests.put(f"{B}/rbac/users/{U}", headers=A, json={"is_active": False})
check("desactivar → sesiones cerradas", mongo.sessions.count_documents({"email": U}) == 0 and me(h).status_code == 401)
requests.put(f"{B}/rbac/users/{U}", headers=A, json={"is_active": True})

h = login(U, PW)
requests.delete(f"{B}/rbac/users/{U}", headers=A)
check("eliminar usuario → sesiones borradas", mongo.sessions.count_documents({"email": U}) == 0 and me(h).status_code == 401)

# --- Tokens manipulados o antiguos ---
from jose import jwt  # noqa: E402
from core.config import SECRET_KEY, ALGORITHM  # noqa: E402

exp = datetime.now(timezone.utc) + timedelta(minutes=5)
old = jwt.encode({"sub": "admin@boltrex.com", "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)
check("token sin sesión (emitido antes de P1.11) → 401 'expiró'", is_401(me({"Authorization": f"Bearer {old}"}), MSG_EXPIRED))
fake = jwt.encode({"sub": "admin@boltrex.com", "sid": uuid.uuid4().hex, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)
check("token con sesión inventada → 401 'cerrada'", is_401(me({"Authorization": f"Bearer {fake}"}), MSG_CLOSED))
admin_sid = jwt.get_unverified_claims(A["Authorization"].split()[1])["sid"]
other = f"ot_{uuid.uuid4().hex[:6]}@example.com"
stolen = jwt.encode({"sub": other, "sid": admin_sid, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)
check("sesión de otro usuario en el token → 401", me({"Authorization": f"Bearer {stolen}"}).status_code == 401)
r = me({"Authorization": "Bearer basura"})
check("token ilegible → 401 en español", r.status_code == 401 and "Sesión no válida" in r.json().get("detail", ""), r.text)

# --- La actividad se guarda como máximo una vez por intervalo ---
sid = admin_sid
me(A)
t1 = mongo.sessions.find_one({"_id": sid})["last_activity"]
me(A)
t2 = mongo.sessions.find_one({"_id": sid})["last_activity"]
check("dos peticiones seguidas → una sola escritura de actividad", t1 == t2, (t1, t2))

print(f"\n{sum(results)}/{len(results)} pruebas OK")
sys.exit(0 if all(results) else 1)
