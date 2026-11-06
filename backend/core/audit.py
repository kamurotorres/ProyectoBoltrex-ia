"""Bitácora de auditoría (backlog P1.12).

Cada acción que cambia datos (y los eventos de sesión) deja un registro en `audit_log`:
quién, cuándo, desde qué IP / navegador / dispositivo, qué acción, sobre qué registro,
un resumen en español y el antes/después campo por campo.

- Solo se agregan registros: no hay endpoints para editarlos ni borrarlos, y el factory
  reset no limpia esta colección.
- Retención: el índice TTL sobre `at` borra los registros con más de AUDIT_RETENTION_DAYS
  días (0 = conservar para siempre).
- Nunca se guardan contraseñas ni sus hashes.
- Dentro de una transacción (ventas, devoluciones, abonos, compras) se pasa `session=` para
  que el registro se confirme o se descarte junto con la operación.

Uso en un endpoint (el usuario, la IP y el navegador se toman del contexto de la petición):

    await audit.record("products", "update", entity_id=barcode, entity_name=name,
                       summary="...", before=old_doc, after=new_doc)
"""
import contextvars
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.database import db

logger = logging.getLogger("boltrex")

COLLECTION = "audit_log"

# Contexto de la petición actual: lo llenan core/security (usuario autenticado) y el login.
_context: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar("audit_context", default=None)

SENSITIVE_KEYS = {"password", "hashed_password", "new_password", "current_password", "access_token", "token"}

MODULE_LABELS = {
    "auth": "Sesión",
    "products": "Productos",
    "categories": "Categorías",
    "price-lists": "Listas de precios",
    "tax-rates": "IVA",
    "clients": "Clientes",
    "document-types": "Tipos de documento",
    "suppliers": "Proveedores",
    "purchases": "Compras",
    "invoices": "Ventas",
    "returns": "Devoluciones",
    "fios": "Abonos (Fios)",
    "payment-methods": "Formas de pago",
    "users": "Usuarios",
    "roles": "Roles",
    "permissions": "Permisos",
    "modules": "Módulos",
    "import": "Importación",
    "ticket-config": "Config. tickets",
    "system": "Sistema",
    "access": "Acceso a secciones",
    "cash": "Caja",
    "reports": "Reportes",
    "inventory": "Inventario",
    "adjustment-reasons": "Motivos de ajuste",
}

ACTION_LABELS = {
    "create": "Crear",
    "update": "Modificar",
    "delete": "Eliminar",
    "confirm": "Confirmar",
    "activate": "Activar",
    "assign_roles": "Asignar roles",
    "change_password": "Cambiar contraseña",
    "import": "Importar",
    "export": "Exportar",
    "factory_reset": "Restablecer sistema",
    "login": "Inicio de sesión",
    "login_failed": "Inicio de sesión fallido",
    "login_blocked": "Cuenta bloqueada",
    "logout": "Cerrar sesión",
    "logout_all": "Cerrar sesión en todos los equipos",
    "session_idle": "Cierre por inactividad",
    "session_expired": "Sesión expirada",
    "access_denied": "Acceso denegado",
}


FIELD_LABELS = {
    "name": "nombre", "description": "descripción", "category": "categoría", "purchase_price": "costo",
    "tax_rate": "IVA", "stock": "stock", "barcode": "código", "is_active": "activo", "first_name": "nombre",
    "last_name": "apellido", "phone": "teléfono", "email": "email", "address": "dirección", "roles": "roles",
    "price_list": "lista de precios", "document_type": "tipo de documento", "document_number": "documento",
    "supplier_name": "proveedor", "items": "productos", "total": "total", "subtotal": "subtotal",
    "total_tax": "IVA total", "status": "estado", "payment_status": "estado de pago", "payment_method": "forma de pago",
    "amount_paid": "abonado", "balance": "saldo", "rate": "tarifa", "company_name": "empresa", "nit": "NIT",
    "ticket_width": "ancho del ticket", "footer_message": "mensaje final", "must_change_password": "debe cambiar contraseña",
    "tarifa_activa": "tarifa activa",
    "credit_days": "plazo de crédito (días)", "credit_limit": "cupo de crédito", "due_date": "vencimiento",
    "applies_to": "aplica a", "requires_note": "exige observación",
    "min_stock": "stock mínimo", "low_stock_threshold": "stock mínimo general",
    "default_term_days": "plazo de crédito por defecto", "due_soon_days": "días para «por vencer»",
}


def field_label(field: str) -> str:
    """'prices.Detal.price' → 'precio Detal'; 'permissions.read' → 'permiso ver'; 'purchase_price' → 'costo'."""
    parts = field.split(".")
    if len(parts) == 3 and parts[0] == "prices" and parts[2] == "price":
        return f"precio {parts[1]}"
    if len(parts) == 2 and parts[0] == "permissions":
        return "permiso " + {"read": "ver", "create": "crear", "update": "editar", "delete": "eliminar"}.get(parts[1], parts[1])
    return " / ".join(FIELD_LABELS.get(p, p) for p in parts)


def format_value(v: Any) -> str:
    if v is None or v == "":
        return "—"
    if isinstance(v, bool):
        return "sí" if v else "no"
    if isinstance(v, float):
        return f"{v:,.0f}".replace(",", ".") if v.is_integer() else f"{v:,.2f}"
    if isinstance(v, int):
        return f"{v:,}".replace(",", ".") if abs(v) >= 10000 else str(v)
    if isinstance(v, list):
        return ", ".join(format_value(i) for i in v) if all(not isinstance(i, (dict, list)) for i in v) else f"{len(v)} elemento(s)"
    return str(v)


# ---------------------------------------------------------------- contexto de la petición

def set_request_context(request=None, actor_email: Optional[str] = None, session_id: Optional[str] = None) -> None:
    from core.login_throttle import client_ip

    ctx = dict(_context.get() or {})
    if request is not None:
        ua = request.headers.get("user-agent", "") or ""
        ctx.update({"ip": client_ip(request), "user_agent": ua[:300]})
    if actor_email is not None:
        ctx["actor_email"] = actor_email
    if session_id is not None:
        ctx["session_id"] = session_id
    _context.set(ctx)


# ---------------------------------------------------------------- navegador y dispositivo

def parse_user_agent(ua: Optional[str]) -> Dict[str, str]:
    """Navegador y tipo de dispositivo legibles a partir del User-Agent (sin librerías externas)."""
    ua = ua or ""
    low = ua.lower()
    if not ua:
        return {"browser": "Desconocido", "device": "Desconocido"}

    tools = (("python-requests", "Script (Python)"), ("curl/", "curl"), ("postman", "Postman"),
             ("httpx", "Script (Python)"), ("okhttp", "App Android"), ("axios", "Script (Node)"))
    for needle, name in tools:
        if needle in low:
            return {"browser": name, "device": "Otro (API)"}

    def version(pattern: str) -> str:
        m = re.search(pattern, ua)
        return f" {m.group(1).split('.')[0]}" if m else ""

    if "edg/" in low or "edga/" in low or "edgios/" in low:
        browser = "Edge" + version(r"Edg(?:A|iOS)?/([\d.]+)")
    elif "opr/" in low or "opera" in low:
        browser = "Opera" + version(r"OPR/([\d.]+)")
    elif "samsungbrowser/" in low:
        browser = "Samsung Internet" + version(r"SamsungBrowser/([\d.]+)")
    elif "firefox/" in low or "fxios/" in low:
        browser = "Firefox" + version(r"(?:Firefox|FxiOS)/([\d.]+)")
    elif "crios/" in low:
        browser = "Chrome" + version(r"CriOS/([\d.]+)")
    elif "chrome/" in low or "chromium/" in low:
        browser = "Chrome" + version(r"Chrom(?:e|ium)/([\d.]+)")
    elif "safari/" in low:
        browser = "Safari" + version(r"Version/([\d.]+)")
    else:
        browser = "Otro"

    if "ipad" in low or "tablet" in low or ("android" in low and "mobile" not in low):
        device = "Tablet"
    elif "mobi" in low or "iphone" in low or "ipod" in low or "android" in low:
        device = "Celular"
    else:
        device = "PC"

    if "windows" in low:
        os_name = "Windows"
    elif "iphone" in low or "ipad" in low or "ios" in low:
        os_name = "iOS"
    elif "android" in low:
        os_name = "Android"
    elif "mac os" in low or "macintosh" in low:
        os_name = "macOS"
    elif "linux" in low:
        os_name = "Linux"
    else:
        os_name = ""
    return {"browser": browser, "device": f"{device} ({os_name})" if os_name else device}


# ---------------------------------------------------------------- antes / después

def _clean(value: Any) -> Any:
    """Copia apta para guardar: sin _id, sin contraseñas, fechas como texto."""
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items() if k != "_id" and k not in SENSITIVE_KEYS}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "model_dump"):
        return _clean(value.model_dump())
    return value


_LIST_KEYS = ("price_list_name", "barcode", "module_slug", "name")


def _flatten(value: Any, prefix: str = "") -> Dict[str, Any]:
    """{'prices': [{'price_list_name': 'Detal', 'price': 10}]} → {'prices.Detal.price': 10}."""
    out: Dict[str, Any] = {}
    if isinstance(value, dict):
        for k, v in value.items():
            out.update(_flatten(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(value, list) and value and all(isinstance(i, dict) for i in value):
        key = next((k for k in _LIST_KEYS if all(k in i for i in value)), None)
        if key:
            for item in value:
                rest = {k: v for k, v in item.items() if k != key}
                out.update(_flatten(rest, f"{prefix}.{item[key]}"))
        else:
            out[prefix] = value
    else:
        out[prefix] = value
    return out


def diff(before: Optional[dict], after: Optional[dict]) -> List[Dict[str, Any]]:
    """Lista de cambios campo por campo entre dos versiones de un registro."""
    b = _flatten(_clean(before or {}))
    a = _flatten(_clean(after or {}))
    ignore = {"updated_at", "created_at"}
    changes = []
    for field in sorted(set(b) | set(a)):
        if field in ignore or field.split(".")[-1] in ignore:
            continue
        if b.get(field) != a.get(field):
            changes.append({"field": field, "label": field_label(field), "before": b.get(field), "after": a.get(field)})
    return changes


# ---------------------------------------------------------------- registro

async def record(
    module: str,
    action: str,
    *,
    entity_id: Optional[str] = None,
    entity_name: Optional[str] = None,
    summary: Optional[str] = None,
    before: Optional[dict] = None,
    after: Optional[dict] = None,
    details: Optional[dict] = None,
    actor_email: Optional[str] = None,
    success: bool = True,
    session=None,
) -> None:
    """Agrega un registro a la bitácora.

    Con `session` (transacción) un fallo se propaga para que la operación completa se revierta.
    Sin transacción, un fallo de la bitácora se registra en el log pero no rompe la acción.
    """
    ctx = _context.get() or {}
    ua_info = parse_user_agent(ctx.get("user_agent"))
    doc = {
        "at": datetime.now(timezone.utc),
        "actor_email": actor_email or ctx.get("actor_email") or "(anónimo)",
        "ip": ctx.get("ip"),
        "user_agent": ctx.get("user_agent"),
        "browser": ua_info["browser"],
        "device": ua_info["device"],
        "session_id": ctx.get("session_id"),
        "module": module,
        "module_label": MODULE_LABELS.get(module, module),
        "action": action,
        "action_label": ACTION_LABELS.get(action, action),
        "entity_id": None if entity_id is None else str(entity_id),
        "entity_name": entity_name,
        "summary": summary,
        "success": success,
        "changes": diff(before, after) if (before is not None or after is not None) else [],
        "before": _clean(before) if before is not None else None,
        "after": _clean(after) if after is not None else None,
        "details": _clean(details) if details is not None else None,
    }
    if session is not None:
        await db[COLLECTION].insert_one(doc, session=session)
        return
    try:
        await db[COLLECTION].insert_one(doc)
    except Exception as exc:  # pragma: no cover - solo registro
        logger.error("No se pudo escribir en la bitácora de auditoría (%s.%s): %s", module, action, exc)


def describe_changes(changes: List[Dict[str, Any]], limit: int = 4) -> str:
    """Resumen corto: 'precio Detal: 2500 → 2800; categoría: A → B'."""
    parts = [f"{c.get('label') or field_label(c['field'])}: {format_value(c['before'])} → {format_value(c['after'])}"
             for c in changes[:limit]]
    if len(changes) > limit:
        parts.append(f"y {len(changes) - limit} cambio(s) más")
    return "; ".join(parts) if parts else "sin cambios"
