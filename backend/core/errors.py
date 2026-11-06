"""Errores de dominio (mantenimiento fase 2).

La lógica de negocio (core/, y desde la fase 3 services/) lanza estos errores con el mensaje en español
para el usuario, sin saber nada de HTTP. Un único manejador (`register_error_handlers`) los convierte en
la respuesta de siempre: `{"detail": "<mensaje>"}` con su código. Así la regla «toda acción bloqueada
muestra su motivo» queda en un solo lugar.

    raise BusinessError("Stock insuficiente de Pan: hay 5 y quieres sacar 8.")   # → 400
    raise NotFoundError("No existe el ajuste AJU-000009.")                         # → 404
    raise ForbiddenError("Solo un administrador puede …")                          # → 403
    raise ConflictError("El stock de Pan cambió mientras contabas …")             # → 409

Los routers pueden seguir usando HTTPException; ambas formas responden igual.
"""
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pymongo.errors import DuplicateKeyError

logger = logging.getLogger("boltrex")


class DomainError(Exception):
    """Base: una regla del negocio impide la acción. `message` es lo que ve el usuario."""
    status_code = 400

    def __init__(self, message: str, status_code: int = None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code

    @property
    def detail(self) -> str:   # mismo nombre que HTTPException.detail (útil en pruebas y logs)
        return self.message


class BusinessError(DomainError):
    status_code = 400


class ForbiddenError(DomainError):
    status_code = 403


class NotFoundError(DomainError):
    status_code = 404


class ConflictError(DomainError):
    status_code = 409


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain_error(request: Request, exc: DomainError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    @app.exception_handler(DuplicateKeyError)
    async def _duplicate_key(request: Request, exc: DuplicateKeyError):
        # La base rechazó un duplicado (p. ej. dos peticiones simultáneas que pasaron la validación
        # previa a la vez): 400 con un mensaje claro, no un 500.
        from core.indexes import duplicate_key_message
        return JSONResponse(status_code=400, content={"detail": duplicate_key_message(exc)})
