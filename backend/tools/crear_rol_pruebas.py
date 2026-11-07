"""Crea el rol «Supervisor de pruebas» y los usuarios de quienes ayudan a probar la app (2026-11-08).

    docker compose exec backend python tools/crear_rol_pruebas.py
    docker compose exec backend python tools/crear_rol_pruebas.py --reset    # nuevas contraseñas temporales

- Rol: ver / crear / editar / eliminar en TODOS los módulos menos Usuarios, Roles y Permisos.
  Config. Sistema (reinicio de fábrica) y Auditoría siguen siendo solo del Administrador (lo exige el sistema).
- Usuarios: uno por persona (la auditoría muestra quién hizo qué), con contraseña TEMPORAL que se muestra una
  sola vez; el sistema les pide cambiarla al primer ingreso (must_change_password).
- Se puede ejecutar varias veces: no duplica nada; a un usuario que ya existe no le cambia la contraseña (salvo
  --reset) y solo se asegura de que tenga el rol y esté activo.
- Usa la base configurada en el backend (MONGO_URL / DB_NAME). Todo queda en la auditoría.
"""
import argparse
import asyncio
import json
import os
import secrets
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import audit  # noqa: E402
from core.config import settings  # noqa: E402
from core.database import db  # noqa: E402
from core.dates import now_utc  # noqa: E402
from core.passwords import hash_password, password_problem  # noqa: E402
from rbac import DEFAULT_MODULES  # noqa: E402

ROLE = "Supervisor de pruebas"
DESCRIPTION = "Pruebas de la app: todo menos Usuarios, Roles y Permisos (Config. Sistema y Auditoría: solo Administrador)."
EXCLUDED = {"users", "roles", "permissions"}
TESTERS = [("johan@boltrex.com", "Johan"), ("may@boltrex.com", "May"), ("alexis@boltrex.com", "Alexis")]
ACTOR = "script:crear_rol_pruebas"
FULL = {"read": True, "create": True, "update": True, "delete": True}


def role_modules(slugs):
    """Módulos que recibe el rol: todos menos los de administración de usuarios y permisos."""
    return sorted(s for s in set(slugs) if s not in EXCLUDED)


def temporary_password() -> str:
    while True:
        pw = "Bx-" + secrets.token_urlsafe(9)
        if not password_problem(pw):
            return pw


async def ensure_role() -> list:
    now = now_utc()
    if not await db.roles.find_one({"name": ROLE}):
        doc = {"name": ROLE, "description": DESCRIPTION, "is_active": True, "created_at": now}
        await db.roles.insert_one(dict(doc))
        await audit.record("roles", "create", entity_id=ROLE, entity_name=ROLE, summary=f"Creó el rol '{ROLE}' (script de pruebas)",
                           after=doc, actor_email=ACTOR)
    else:
        await db.roles.update_one({"name": ROLE}, {"$set": {"is_active": True, "description": DESCRIPTION}})
    slugs = [m["slug"] async for m in db.system_modules.find({}, {"_id": 0, "slug": 1})] or [m["slug"] for m in DEFAULT_MODULES]
    modules = role_modules(slugs)
    for slug in modules:
        await db.role_permissions.update_one(
            {"role_name": ROLE, "module_slug": slug},
            {"$set": {"permissions": dict(FULL)}, "$setOnInsert": {"role_name": ROLE, "module_slug": slug, "created_at": now}},
            upsert=True)
    # Si alguna vez tuvo permisos en los módulos excluidos, se quitan.
    await db.role_permissions.delete_many({"role_name": ROLE, "module_slug": {"$in": sorted(EXCLUDED)}})
    await audit.record("permissions", "update", entity_id=ROLE, entity_name=ROLE, actor_email=ACTOR,
                       summary=f"Permisos completos del rol '{ROLE}' en {len(modules)} módulo(s); sin Usuarios, Roles ni Permisos",
                       after={"modules": modules})
    return modules


async def ensure_user(email: str, first_name: str, reset: bool):
    """Devuelve la contraseña temporal si se creó o se reinició; None si ya existía y no se tocó."""
    now = now_utc()
    user = await db.users_extended.find_one({"email": email})
    password = None
    if user is None:
        password = temporary_password()
        doc = {"email": email, "first_name": first_name, "last_name": "(pruebas)", "phone": None, "is_active": True,
               "hashed_password": hash_password(password), "roles": [ROLE], "must_change_password": True,
               "created_at": now, "updated_at": now}
        await db.users_extended.insert_one(dict(doc))
        doc.pop("hashed_password")
        await audit.record("users", "create", entity_id=email, entity_name=f"{first_name} (pruebas)", actor_email=ACTOR,
                           summary=f"Creó el usuario {email} con el rol '{ROLE}' (script de pruebas)", after=doc)
        return password
    changes = {"is_active": True, "updated_at": now}
    if ROLE not in (user.get("roles") or []):
        changes["roles"] = list(user.get("roles") or []) + [ROLE]
    if reset:
        password = temporary_password()
        changes.update({"hashed_password": hash_password(password), "must_change_password": True})
    await db.users_extended.update_one({"email": email}, {"$set": changes})
    await audit.record("users", "update", entity_id=email, entity_name=email, actor_email=ACTOR,
                       summary=f"Usuario de pruebas {email}: rol '{ROLE}' asegurado" + ("; contraseña temporal nueva" if reset else ""))
    return password


async def main(reset: bool, as_json: bool) -> int:
    audit.set_request_context(actor_email=ACTOR)
    modules = await ensure_role()
    created = {email: await ensure_user(email, name, reset) for email, name in TESTERS}
    if as_json:
        print(json.dumps({"role": ROLE, "modules": modules, "passwords": created}))
        return 0
    print(f"Base de datos: {settings.db_name}")
    print(f"Rol «{ROLE}»: ver / crear / editar / eliminar en {len(modules)} módulos")
    print("  (sin Usuarios, Roles ni Permisos; Config. Sistema y Auditoría siguen siendo solo del Administrador)\n")
    for email, pw in created.items():
        if pw:
            print(f"  {email:24}  contraseña temporal: {pw}")
        else:
            print(f"  {email:24}  ya existía: se dejó su contraseña (usa --reset para darle una temporal nueva)")
    if any(created.values()):
        print("\nCopia las contraseñas ahora: no se vuelven a mostrar. Al primer ingreso el sistema les pide cambiarla.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reset", action="store_true", help="dar contraseñas temporales nuevas a los usuarios que ya existen")
    parser.add_argument("--json", action="store_true", help="salida en JSON (para las pruebas)")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.reset, args.json)))
