"""Reglas de contraseña (backlog P1.10).

Módulo sin dependencias de BD ni configuración: lo usan el backend y también
los scripts de carga inicial (scripts/init_rbac.py, scripts/seed_data.py).
"""
from typing import Optional

MIN_PASSWORD_LENGTH = 8

# Contraseña que traían las instalaciones antiguas; el backend la detecta al arrancar.
LEGACY_DEFAULT_PASSWORD = "admin123"

# Contraseñas que nunca se aceptan: la que traía el proyecto por defecto y otras obvias.
INSECURE_PASSWORDS = {"admin123", "admin", "12345678", "password", "contraseña", "boltrex", "boltrex123"}

# Mensaje con el que el backend rechaza cualquier acción mientras el usuario no cambie su contraseña.
PASSWORD_CHANGE_REQUIRED = "Debes cambiar tu contraseña antes de continuar."


def password_problem(password: Optional[str]) -> Optional[str]:
    """Devuelve por qué la contraseña no es válida, o None si es aceptable."""
    if password is None or not password.strip():
        return "La contraseña no puede estar vacía."
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres."
    if password.strip().lower() in INSECURE_PASSWORDS:
        return "Esa contraseña es demasiado común o es la contraseña por defecto. Elige otra."
    return None
