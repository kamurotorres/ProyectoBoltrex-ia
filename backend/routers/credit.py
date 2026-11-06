"""Cartera con vencimientos (backlog P2.30): configuración del plazo por defecto y de «Por vencer»
(Config. Sistema, solo administradores) y el estado de crédito de un cliente para el POS.
Reglas en core/credit.py; la cartera paginada y su exportación están en /fios."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core import audit, credit
from core.permissions import require_any_permission
from core.security import get_current_user
from core.user_protection import actor_is_admin
from models.auth import User

router = APIRouter(tags=["Cartera"])


class CreditSettings(BaseModel):
    default_term_days: int
    due_soon_days: int


@router.get("/credit/settings")
async def read_credit_settings(current_user: User = Depends(get_current_user)):
    """Cualquier usuario con sesión la lee (el POS calcula el vencimiento sugerido)."""
    return await credit.get_settings()


@router.put("/credit/settings")
async def update_credit_settings(body: CreditSettings, current_user: User = Depends(get_current_user)):
    if not await actor_is_admin(current_user.email):
        raise HTTPException(status_code=403, detail="Solo los administradores pueden cambiar la configuración de crédito.")
    before = await credit.get_settings()
    after = await credit.set_settings(body.default_term_days, body.due_soon_days, current_user.email)
    changes = audit.diff(before, after)
    if changes:
        await audit.record("fios", "update", entity_id="configuracion", entity_name="Configuración de crédito",
                           summary=f"Cambió la configuración de crédito: {audit.describe_changes(changes)}",
                           before=before, after=after)
    return after


@router.get("/credit/client-status")
async def client_credit_status(document_number: str, document_type: Optional[str] = None,
                               current_user: User = Depends(require_any_permission(("pos", "read"), ("fios", "read"),
                                                                                    ("clients", "read")))):
    """Saldo pendiente, lo vencido y el cupo disponible de un cliente (aviso del POS, opción A: solo avisa)."""
    return await credit.client_credit_status(document_number, document_type)
