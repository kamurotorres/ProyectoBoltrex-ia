"""Al arrancar (P2.31): crea en bases ya existentes los módulos de rbac.DEFAULT_MODULES que falten
(p. ej. "Caja") y les asigna los permisos por defecto de los roles predeterminados.
Solo toca módulos NUEVOS: no cambia permisos que el administrador ya haya personalizado."""
import logging

from core.database import db
from core.dates import now_utc

logger = logging.getLogger("boltrex")


async def ensure_new_modules() -> list:
    from rbac import DEFAULT_MODULES, DEFAULT_ROLES
    created = []
    try:
        if not await db.system_modules.count_documents({}):
            return created            # BD vacía: lo hace scripts/init_rbac.py
        for mod in DEFAULT_MODULES:
            if await db.system_modules.find_one({"slug": mod["slug"]}, {"_id": 1}):
                continue
            await db.system_modules.insert_one({**mod, "is_active": True, "created_at": now_utc()})
            for role in DEFAULT_ROLES:
                perm = role["permissions"].get(mod["slug"])
                if perm is None or not await db.roles.find_one({"name": role["name"]}, {"_id": 1}):
                    continue
                await db.role_permissions.update_one(
                    {"role_name": role["name"], "module_slug": mod["slug"]},
                    {"$setOnInsert": {"role_name": role["name"], "module_slug": mod["slug"],
                                      "permissions": perm.model_dump(), "created_at": now_utc()}},
                    upsert=True,
                )
            created.append(mod["slug"])
        if created:
            logger.info("Módulos nuevos creados con sus permisos por defecto: %s", ", ".join(created))
    except Exception as exc:  # pragma: no cover
        logger.error("No se pudieron sincronizar los módulos nuevos: %s", exc)
    return created
