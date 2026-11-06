---
name: mensajes-al-usuario
description: Regla del usuario — toda acción bloqueada o fallida debe mostrar en pantalla un mensaje que explique por qué
metadata:
  type: feedback
---

Siempre que el sistema impida una acción (validación, regla de negocio, permiso, dato en uso), el usuario final debe ver **en pantalla** un mensaje que explique el motivo y, si se puede, qué hacer. Nunca un genérico "Error al eliminar".

**Why:** el usuario lo pidió explícitamente el 2026-11-04 al aprobar P0.6 ("siempre los mensajes se deben mostrar en pantalla al usuario para saber por qué no se puede hacer dicha acción").

**How to apply:**
- Backend: `HTTPException(400, detail="No se puede <acción> '<nombre>': <motivo con cifras>. <Qué hacer>.")` en español; `detail` siempre texto (no dict).
- Frontend: en cada `catch`, `toast.error(getErrorMessage(error, '<fallback>'))` con `getErrorMessage` de `frontend/src/lib/utils.js` (maneja `detail` texto, lista 422 y errores de red).
- En los tests, verificar que el rechazo trae `detail` de texto con el motivo (ver `blocked()` en `tests/references_check.py`).
- Relacionado: [[BACKLOG_MEJORAS]] punto 21 (llevar `getErrorMessage` a todas las páginas).
