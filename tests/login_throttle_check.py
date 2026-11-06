"""Pruebas del límite de intentos de login (backlog P1.9).

Requiere un backend con tiempos cortos para no esperar 15 minutos reales:
    DB_NAME=boltrex_lttest LOGIN_LOCK_MINUTES=0.05 LOGIN_WINDOW_MINUTES=0.1 \
        backend/.venv/bin/uvicorn main:app --app-dir backend --port 8001
    BOLTREX_API=http://localhost:8001/api DB_NAME=boltrex_lttest LOGIN_LOCK_MINUTES=0.05 \
        backend/.venv/bin/python tests/login_throttle_check.py
(LOGIN_LOCK_MINUTES debe coincidir con el del backend; por defecto 5 intentos y 20 por IP.)
"""
import os
# Contraseña del admin de la BD de prueba (ver tests/prepare_test_db.sh). Ya no existe admin123 (P1.10).
ADMIN_PASSWORD = os.environ.get("BOLTREX_ADMIN_PASSWORD", "Prueba-Admin-2026")
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pymongo
import requests


DB_NAME = os.environ["DB_NAME"]
if DB_NAME == "boltrex":
    sys.exit("Negado: usa una BD de prueba.")
LOCK_SECONDS = float(os.environ.get("LOGIN_LOCK_MINUTES", "0.05")) * 60
if LOCK_SECONDS > 30:
    sys.exit("Arranca el backend con LOGIN_LOCK_MINUTES corto (p. ej. 0.05) para esta prueba.")
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

t = uuid.uuid4().hex[:5]
_ip_counter = [0]


def new_ip():
    """Cada escenario usa su propia IP para que el contador por IP no interfiera."""
    _ip_counter[0] += 1
    return f"10.{int(t[:2], 16)}.{int(t[2:4], 16)}.{_ip_counter[0]}"


def login(email, pw, ip):
    return requests.post(f"{B}/auth/login", json={"email": email, "password": pw}, headers={"X-Real-IP": ip})


def detail(r):
    return r.json().get("detail") if "json" in r.headers.get("content-type", "") else r.text


admin = requests.post(f"{B}/auth/login", json={"email": "admin@boltrex.com", "password": ADMIN_PASSWORD}, headers={"X-Real-IP": new_ip()})
H = {"Authorization": f"Bearer {admin.json()['access_token']}"}
U = f"usuario{t}@test.com"
requests.post(f"{B}/rbac/users", headers=H, json={"email": U, "password": "correcta1", "first_name": "U", "last_name": "T"})
requests.post(f"{B}/rbac/users/{U}/roles", headers=H, json=["Vendedor"])

print("== Bloqueo por cuenta (5 intentos) ==")
ip = new_ip()
msgs = [detail(login(U, "mala", ip)) for _ in range(5)]
for m in msgs:
    print(f"       mensaje: {m}")
check("intentos 1-3 avisan cuántos quedan", all("te quedan" in m.lower() for m in msgs[:3]) and "quedan 4" in msgs[0].lower(), msgs[:3])
check("intento 4 avisa que el siguiente bloquea", "si vuelves a fallar" in msgs[3].lower(), msgs[3])
check("intento 5 informa el bloqueo", "quedó bloqueado" in msgs[4].lower(), msgs[4])
r = login(U, "correcta1", ip)
check("durante el bloqueo se rechaza incluso la contraseña correcta (429)", r.status_code == 429, (r.status_code, detail(r)))
check("el mensaje de bloqueo dice cuánto esperar", "intenta de nuevo en" in detail(r).lower() and "minuto" in detail(r).lower(), detail(r))
check("la respuesta trae Retry-After", r.headers.get("Retry-After", "").isdigit(), dict(r.headers))
print(f"       mensaje: {detail(r)}")
r = login(U, "correcta1", new_ip())
check("el bloqueo es de la cuenta: otro equipo tampoco entra (429)", r.status_code == 429, r.status_code)

time.sleep(LOCK_SECONDS + 1)
check("pasado el bloqueo, la contraseña correcta funciona", login(U, "correcta1", ip).ok)

print("== Un login correcto reinicia el contador ==")
ip = new_ip()
for _ in range(4):
    login(U, "mala", ip)
check("tras 4 fallos, login correcto OK", login(U, "correcta1", ip).ok)
m = detail(login(U, "mala", ip))
check("el contador volvió a empezar (quedan 4)", "quedan 4" in m.lower(), m)

print("== Emails inexistentes: mismo trato, sin revelar nada ==")
ip = new_ip()
fake = f"noexiste{t}@test.com"
m_fake = [detail(login(fake, "x", ip)) for _ in range(5)]
check("mismo mensaje que para un email real", m_fake[0] == msgs[0], (m_fake[0], msgs[0]))
check("un email inexistente también se bloquea", login(fake, "x", ip).status_code == 429)

print("== Cambiar la contraseña desbloquea ==")
ip = new_ip()
for _ in range(5):
    login(U, "mala", ip)
check("cuenta bloqueada", login(U, "correcta1", ip).status_code == 429)
check("admin cambia la contraseña desde Usuarios", requests.put(f"{B}/rbac/users/{U}", headers=H, json={"password": "Nueva-2222"}).ok)
check("entra al instante con la nueva contraseña", login(U, "Nueva-2222", ip).ok)

print("== Bloqueo por equipo (20 fallos contra emails distintos) ==")
time.sleep(LOCK_SECONDS + 1)
ip = new_ip()
for i in range(20):
    login(f"spray{i}{t}@test.com", "x", ip)
r = login(U, "Nueva-2222", ip)
check("desde ese equipo ya no entra ni con la contraseña correcta (429)", r.status_code == 429 and "este equipo" in detail(r).lower(), (r.status_code, detail(r)))
print(f"       mensaje: {detail(r)}")
check("desde otro equipo la cuenta sí entra", login(U, "Nueva-2222", new_ip()).ok)

print("== Concurrencia: 20 intentos simultáneos no se saltan el límite ==")
time.sleep(LOCK_SECONDS + 1)
ip = new_ip()
with ThreadPoolExecutor(max_workers=20) as pool:
    codes = list(pool.map(lambda _: login(U, "mala", ip).status_code, range(20)))
check("ninguno entra y ninguno da 500", all(c in (401, 429) for c in codes), codes)
check("solo 5 llegaron a comprobar la contraseña (401); los otros 15, bloqueados (429)",
      codes.count(401) == 5 and codes.count(429) == 15, sorted(codes))
check("después, la cuenta queda bloqueada", login(U, "Nueva-2222", ip).status_code == 429)

print("== Otros ==")
time.sleep(LOCK_SECONDS + 1)
requests.put(f"{B}/rbac/users/{U}", headers=H, json={"is_active": False})
r = login(U, "Nueva-2222", new_ip())
check("usuario desactivado: mensaje en español", r.status_code == 403 and "desactivada" in detail(r).lower(), (r.status_code, detail(r)))
print(f"       mensaje: {detail(r)}")
ip = new_ip()
codes = [login(U, "Nueva-2222", ip).status_code for _ in range(7)]
check("desactivado con contraseña correcta repetida: siempre 'desactivada', nunca 'bloqueado'", codes == [403] * 7, codes)
idx = mongo.login_attempts.index_information().get("ttl_login_attempts_expires_at", {})
check("índice TTL creado (los registros caducan solos)", idx.get("expireAfterSeconds") == 0, idx)
check("los registros tienen fecha de caducidad", mongo.login_attempts.count_documents({"expires_at": {"$exists": False}}) == 0)

print(f"\n{sum(results)}/{len(results)} pruebas OK")
sys.exit(0 if all(results) else 1)
