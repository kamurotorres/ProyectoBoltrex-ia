"""Pruebas anti-escalada de privilegios (backlog P1.8).

Uso (contra una BD de PRUEBA sembrada con init_rbac.py + seed_data.py):
    DB_NAME=boltrex_uptest backend/.venv/bin/uvicorn main:app --app-dir backend --port 8001
    BOLTREX_API=http://localhost:8001/api DB_NAME=boltrex_uptest \
        backend/.venv/bin/python tests/user_protection_check.py
"""
import os
# Contraseña del admin de la BD de prueba (ver tests/prepare_test_db.sh). Ya no existe admin123 (P1.10).
ADMIN_PASSWORD = os.environ.get("BOLTREX_ADMIN_PASSWORD", "Prueba-Admin-2026")
import asyncio
import os
import sys
import time
import uuid
from pathlib import Path

import pymongo
import requests

DB_NAME = os.environ["DB_NAME"]
if DB_NAME == "boltrex":
    sys.exit("Negado: usa una BD de prueba.")
mongo = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017/?directConnection=true"))[DB_NAME]
B = os.environ.get("BOLTREX_API", "http://localhost:8001/api")
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"{'OK ' if ok else 'FAIL'} {name}" + ("" if ok else f" -> {detail}"))


def denied(name, r, code, *must_contain):
    """Rechazo con el código esperado y un `detail` de texto que explica el motivo."""
    detail = r.json().get("detail") if "json" in r.headers.get("content-type", "") else None
    ok = r.status_code == code and isinstance(detail, str) and all(m.lower() in detail.lower() for m in must_contain)
    check(name, ok, (r.status_code, detail))
    if ok:
        print(f"       mensaje: {detail}")


for _ in range(30):
    try:
        requests.get(B.rsplit("/api", 1)[0] + "/", timeout=1)
        break
    except Exception:
        time.sleep(0.5)


def login(email, pw):
    r = requests.post(f"{B}/auth/login", json={"email": email, "password": pw})
    return {"Authorization": f"Bearer {r.json()['access_token']}"} if r.ok else None


t = uuid.uuid4().hex[:5]
A = login("admin@boltrex.com", ADMIN_PASSWORD)
assert A
GEST, ADM2, VEND, ROLE = f"gestor{t}@test.com", f"admin2{t}@test.com", f"vend{t}@test.com", f"Gestor{t}"
api = lambda h, m, path, body=None: getattr(requests, m)(f"{B}{path}", headers=h, json=body)

# Rol "Gestor": NO es administrador, pero gestiona usuarios y puede editar permisos.
api(A, "post", "/rbac/roles", {"name": ROLE})
for mod, perms in [("users", dict(read=True, create=True, update=True, delete=True)),
                   ("permissions", dict(read=True, create=False, update=True, delete=False)),
                   ("roles", dict(read=True, create=False, update=False, delete=False))]:
    api(A, "post", "/rbac/permissions", {"role_name": ROLE, "module_slug": mod, "permissions": perms})
for email, role in [(GEST, ROLE), (ADM2, "Administrador"), (VEND, "Vendedor")]:
    api(A, "post", "/rbac/users", {"email": email, "password": "Pass-1234", "first_name": role, "last_name": "T"})
    api(A, "post", f"/rbac/users/{email}/roles", [role])
G = login(GEST, "Pass-1234")
assert G

print("== A. Asignarse / dar el rol Administrador (gestor no-admin) ==")
denied("A1 gestor se asigna Administrador", api(G, "post", f"/rbac/users/{GEST}/roles", [ROLE, "Administrador"]), 403, "tus propios roles")
denied("A2 gestor da Administrador a un vendedor", api(G, "post", f"/rbac/users/{VEND}/roles", ["Administrador"]), 403, "solo un administrador", "rol administrador")
denied("A3 gestor cambia sus propios roles", api(G, "post", f"/rbac/users/{GEST}/roles", [ROLE, "Supervisor"]), 403, "tus propios roles")
check("A  el gestor sigue sin ser Administrador", "Administrador" not in mongo.users_extended.find_one({"email": GEST})["roles"])

print("== B. Tomar la cuenta de un Administrador (gestor no-admin) ==")
denied("B1 gestor cambia la contraseña de un admin", api(G, "put", f"/rbac/users/{ADM2}", {"password": "hacked"}), 403, "otro administrador")
check("B1 el admin sigue entrando con su contraseña", login(ADM2, "Pass-1234") is not None and login(ADM2, "hacked") is None)
denied("B2 gestor desactiva a un admin", api(G, "put", f"/rbac/users/{ADM2}", {"is_active": False}), 403, "otro administrador")
denied("B3 gestor elimina a un admin", api(G, "delete", f"/rbac/users/{ADM2}"), 403, "otro administrador")
denied("B4 gestor quita el rol Administrador a un admin", api(G, "post", f"/rbac/users/{ADM2}/roles", ["Vendedor"]), 403, "otro administrador")

print("== Lo legítimo del gestor sigue funcionando ==")
check("gestor edita los datos de un vendedor", api(G, "put", f"/rbac/users/{VEND}", {"first_name": "Nuevo"}).ok)
check("gestor desactiva y reactiva a un vendedor", api(G, "put", f"/rbac/users/{VEND}", {"is_active": False}).ok
      and api(G, "put", f"/rbac/users/{VEND}", {"is_active": True}).ok)
check("gestor asigna Supervisor a un vendedor", api(G, "post", f"/rbac/users/{VEND}/roles", ["Supervisor"]).ok)
check("gestor edita sus propios datos", api(G, "put", f"/rbac/users/{GEST}", {"phone": "300"}).ok)

print("== F. Ampliar el propio rol ==")
perm = lambda role: {"role_name": role, "module_slug": "products", "permissions": dict(read=True, create=True, update=True, delete=True)}
denied("F1 gestor se da permisos en su propio rol", api(G, "post", "/rbac/permissions", perm(ROLE)), 403, "rol que tienes asignado")
denied("F1 gestor quita permisos de su propio rol", api(G, "delete", f"/rbac/permissions/{ROLE}/users"), 403, "rol que tienes asignado")
check("F2 gestor sí edita permisos de un rol que no tiene (Vendedor)", api(G, "post", "/rbac/permissions", {
    "role_name": "Vendedor", "module_slug": "dashboard", "permissions": dict(read=True)}).ok)

print("== E. Rol Administrador intocable ==")
denied("E1 cambiar permisos del rol Administrador", api(A, "post", "/rbac/permissions", perm("Administrador") | {"permissions": dict(read=True)}), 400, "administrador", "acceso total")
denied("E1 quitar un permiso del rol Administrador", api(A, "delete", "/rbac/permissions/Administrador/users"), 400, "acceso total")
denied("E2 eliminar el rol Administrador", api(A, "delete", "/rbac/roles/Administrador"), 400, "acceso total")
denied("E3 desactivar el rol Administrador", api(A, "put", "/rbac/roles/Administrador", {"is_active": False}), 400, "acceso total")
check("E4 cambiar la descripción del rol Administrador sí se permite", api(A, "put", "/rbac/roles/Administrador", {"description": "Control total"}).ok)
check("E  el admin conserva todos sus permisos", (requests.get(f"{B}/auth/me", headers=A).json()["permissions"].get("users") or {}).get("delete") is True)

print("== D. Auto-bloqueo ==")
denied("D1 admin se desactiva a sí mismo", api(A, "put", "/rbac/users/admin@boltrex.com", {"is_active": False}), 400, "tu propia cuenta")
denied("D2 admin se elimina a sí mismo", api(A, "delete", "/rbac/users/admin@boltrex.com"), 400, "tu propia cuenta")
denied("D3 admin se quita su propio rol Administrador", api(A, "post", "/rbac/users/admin@boltrex.com/roles", ["Vendedor"]), 400, "tu propio rol")

print("== C. Admin protegido y último admin ==")
A2 = login(ADM2, "Pass-1234")
denied("C1 otro admin desactiva a admin@boltrex.com", api(A2, "put", "/rbac/users/admin@boltrex.com", {"is_active": False}), 400, "protegido")
denied("C2 otro admin elimina a admin@boltrex.com", api(A2, "delete", "/rbac/users/admin@boltrex.com"), 400, "protegido")
denied("C3 otro admin quita el rol a admin@boltrex.com", api(A2, "post", "/rbac/users/admin@boltrex.com/roles", ["Vendedor"]), 400, "protegido")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from core.errors import DomainError  # noqa: E402
from core import user_protection as guard  # noqa: E402


# Regla 4 aislada: admin2 como único admin activo. Se desactivan a mano en la BD TODOS los demás
# administradores activos (incluidos los de corridas anteriores) y luego se restauran.
others = [u["email"] for u in mongo.users_extended.find(
    {"roles": "Administrador", "is_active": {"$ne": False}, "email": {"$ne": ADM2}}, {"email": 1})]
mongo.users_extended.update_many({"email": {"$in": others}}, {"$set": {"is_active": False}})


async def last_admin_case():
    try:
        # Actor: un Administrador distinto del objetivo (si no, otras reglas lo frenarían antes).
        await guard.check_user_update("admin@boltrex.com", ADM2, {"is_active": False})
        return None
    except DomainError as e:   # mantenimiento fase 2: la regla lanza un error de dominio
        return e.detail

msg = asyncio.run(last_admin_case())
mongo.users_extended.update_many({"email": {"$in": others}}, {"$set": {"is_active": True}})
check("C4 no se puede desactivar al único Administrador activo", msg and "único administrador activo" in msg.lower(), msg)
if msg:
    print(f"       mensaje: {msg}")

print("== Opción 1: un admin sí cambia la contraseña de otro admin ==")
check("admin cambia la contraseña de admin2", api(A, "put", f"/rbac/users/{ADM2}", {"password": "Nueva-4567"}).ok)
check("admin2 entra con la nueva contraseña", login(ADM2, "Nueva-4567") is not None)

print("== Bug corregido: editar sin escribir contraseña no la borra ==")
check("admin edita a un vendedor enviando password vacía (como el formulario)",
      api(A, "put", f"/rbac/users/{VEND}", {"email": VEND, "password": "", "first_name": "Editado", "last_name": "T", "phone": "", "is_active": True}).ok)
check("el vendedor sigue entrando con su contraseña real", login(VEND, "Pass-1234") is not None)
check("nadie entra con contraseña vacía", login(VEND, "") is None)

print(f"\n{sum(results)}/{len(results)} pruebas OK")
sys.exit(0 if all(results) else 1)
