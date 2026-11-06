"""Consulta de la bitácora de auditoría (backlog P1.12).

Solo lectura y solo para el rol Administrador. No es un permiso asignable desde Roles y
Permisos: nadie puede habilitárselo a otro rol. No existen endpoints para editar ni borrar
registros (la retención la aplica el índice TTL, ver AUDIT_RETENTION_DAYS).
"""
import math
import re
from datetime import datetime, time, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core import audit
from core.config import AUDIT_RETENTION_DAYS
from core.database import db
from core.security import get_current_user
from core.user_protection import actor_is_admin
from models.auth import User

router = APIRouter(tags=["Auditoría"])

ONLY_ADMIN = "Solo los administradores pueden ver la auditoría del sistema."


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not await actor_is_admin(current_user.email):
        raise HTTPException(status_code=403, detail=ONLY_ADMIN)
    return current_user


def _parse_day(value: Optional[str], end: bool = False) -> Optional[datetime]:
    """'2026-11-04' → inicio (o fin) de ese día en UTC."""
    if not value:
        return None
    try:
        day = datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Fecha inválida '{value}': usa el formato AAAA-MM-DD.")
    moment = datetime.combine(day, time.max if end else time.min, tzinfo=timezone.utc)
    return moment


@router.get("/audit")
async def list_audit(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    actor: Optional[str] = None,
    module: Optional[str] = None,
    action: Optional[str] = None,
    device: Optional[str] = None,
    success: Optional[bool] = None,
    q: Optional[str] = None,
    tz_offset_minutes: int = Query(0, description="Desfase del navegador (getTimezoneOffset) para filtrar por días locales"),
    current_user: User = Depends(require_admin),
):
    """Registros de auditoría, del más reciente al más antiguo, paginados en el servidor."""
    query: dict = {}
    start = _parse_day(date_from)
    end = _parse_day(date_to, end=True)
    if start and end and start > end:
        raise HTTPException(status_code=400, detail="La fecha 'desde' no puede ser posterior a la fecha 'hasta'.")
    offset = timedelta(minutes=tz_offset_minutes)
    if start or end:
        query["at"] = {}
        if start:
            query["at"]["$gte"] = start + offset
        if end:
            query["at"]["$lte"] = end + offset
    if actor:
        query["actor_email"] = actor
    if module:
        query["module"] = module
    if action:
        query["action"] = action
    if device:
        query["device"] = {"$regex": f"^{re.escape(device)}"}
    if success is not None:
        query["success"] = success
    if q:
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        query["$or"] = [{"entity_id": rx}, {"entity_name": rx}, {"summary": rx}, {"actor_email": rx}, {"ip": rx}]

    total = await db[audit.COLLECTION].count_documents(query)
    pages = max(1, math.ceil(total / page_size))
    cursor = (db[audit.COLLECTION].find(query, {"_id": 0, "user_agent": 1, "at": 1, "actor_email": 1, "ip": 1,
                                                "browser": 1, "device": 1, "module": 1, "module_label": 1,
                                                "action": 1, "action_label": 1, "entity_id": 1, "entity_name": 1,
                                                "summary": 1, "success": 1, "changes": 1, "details": 1})
              .sort("at", -1).skip((page - 1) * page_size).limit(page_size))
    items = await cursor.to_list(page_size)
    for item in items:
        if isinstance(item.get("at"), datetime):
            at = item["at"] if item["at"].tzinfo else item["at"].replace(tzinfo=timezone.utc)
            item["at"] = at.isoformat()
    return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": pages,
            "retention_days": AUDIT_RETENTION_DAYS}


@router.get("/audit/filters")
async def audit_filters(current_user: User = Depends(require_admin)):
    """Valores disponibles para los filtros de la pantalla de auditoría."""
    actors = sorted(a for a in await db[audit.COLLECTION].distinct("actor_email") if a)
    modules = sorted(await db[audit.COLLECTION].distinct("module"))
    actions = sorted(await db[audit.COLLECTION].distinct("action"))
    return {
        "actors": actors,
        "modules": [{"value": m, "label": audit.MODULE_LABELS.get(m, m)} for m in modules],
        "actions": [{"value": a, "label": audit.ACTION_LABELS.get(a, a)} for a in actions],
        "devices": ["PC", "Celular", "Tablet", "Otro (API)"],
        "retention_days": AUDIT_RETENTION_DAYS,
    }


# ---------------------------------------------------------------- accesos denegados (P1.13)

from pydantic import BaseModel, Field  # noqa: E402

ACCESS_DENIED_DEDUP_MINUTES = 10


class AccessDeniedReport(BaseModel):
    path: str = Field(..., max_length=200)
    section: Optional[str] = Field(None, max_length=100)


@router.post("/audit/access-denied")
async def report_access_denied(report: AccessDeniedReport, current_user: User = Depends(get_current_user)):
    """El frontend avisa que el usuario intentó abrir una sección sin permiso.

    Cualquier usuario autenticado puede llamarlo (es sobre sí mismo). El mismo usuario y la
    misma ruta se registran como mucho una vez cada ACCESS_DENIED_DEDUP_MINUTES, para que
    recargar la página no llene la bitácora.
    """
    path = report.path.strip() or "/"
    since = datetime.now(timezone.utc) - timedelta(minutes=ACCESS_DENIED_DEDUP_MINUTES)
    recent = await db[audit.COLLECTION].find_one(
        {"action": "access_denied", "actor_email": current_user.email, "entity_id": path, "at": {"$gte": since}},
        {"_id": 1},
    )
    if recent:
        return {"recorded": False}
    label = report.section or path
    await audit.record("access", "access_denied", entity_id=path, entity_name=label,
                       summary=f"Intentó abrir la sección '{label}' ({path}) sin permiso", success=False)
    return {"recorded": True}
