"""core/passwords.py (P1.10, P2.26: bcrypt directo) y core/security.py (tokens JWT con PyJWT)."""
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from core.config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY
from core.passwords import INSECURE_PASSWORDS, MIN_PASSWORD_LENGTH, check_password, hash_password, password_problem
from core.security import create_access_token


@pytest.mark.parametrize("password, problem", [
    (None, "La contraseña no puede estar vacía."),
    ("", "La contraseña no puede estar vacía."),
    ("        ", "La contraseña no puede estar vacía."),
    ("corta12", f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres."),
    ("admin123", "Esa contraseña es demasiado común o es la contraseña por defecto. Elige otra."),
    (" Boltrex123 ", "Esa contraseña es demasiado común o es la contraseña por defecto. Elige otra."),
    ("CONTRASEÑA", "Esa contraseña es demasiado común o es la contraseña por defecto. Elige otra."),
    ("Segura#2026", None),
    ("12345679", None),
])
def test_reglas_de_contrasena(password, problem):
    assert password_problem(password) == problem


def test_todas_las_prohibidas_se_rechazan_si_alcanzan_el_largo():
    for p in INSECURE_PASSWORDS:
        expected = ("Esa contraseña es demasiado común o es la contraseña por defecto. Elige otra."
                    if len(p) >= MIN_PASSWORD_LENGTH else f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres.")
        assert password_problem(p) == expected


def test_hash_bcrypt_estandar_y_verificacion():
    h = hash_password("Segura#2026")
    assert h.startswith("$2b$") and h != hash_password("Segura#2026")    # sal distinta cada vez
    assert check_password("Segura#2026", h)
    assert not check_password("segura#2026", h)
    assert not check_password("", h)


def test_bcrypt_usa_solo_72_bytes_como_passlib():
    base = "ñ" * 36                      # 72 bytes en UTF-8
    h = hash_password(base)
    assert check_password(base + "lo que sigue no cuenta", h)


def test_hash_antiguo_de_passlib_sigue_valiendo():
    import bcrypt
    legacy = bcrypt.hashpw(b"Antigua#2025", bcrypt.gensalt(prefix=b"2b")).decode()
    assert check_password("Antigua#2025", legacy)


def test_token_jwt():
    before = datetime.now(timezone.utc)
    token = create_access_token({"sub": "ana@tienda.com", "sid": "abc"})
    data = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert data["sub"] == "ana@tienda.com" and data["sid"] == "abc"
    exp = datetime.fromtimestamp(data["exp"], timezone.utc)
    expected = before + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    assert abs((exp - expected).total_seconds()) < 5
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(token, "otra-clave", algorithms=[ALGORITHM])


def test_token_no_modifica_los_datos_recibidos():
    data = {"sub": "x@y.com"}
    create_access_token(data)
    assert data == {"sub": "x@y.com"}
