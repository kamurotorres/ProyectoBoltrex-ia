"""Formato colombiano de dinero y números para TODO lo que arma el backend como texto (tickets, PDF/Excel,
mensajes de error, resúmenes de auditoría).

Regla única del sistema (la misma de frontend/src/lib/format.js):
- punto de miles y coma decimal: 1500 → $1.500 · 999.99 → $999,99 · -1500 → −$1.500
- centavos SOLO si existen (redondeado a 2 decimales): 1500.0 → $1.500 · 2.5 → $2,50
- números (cantidades, porcentajes): hasta 2 decimales sin ceros de sobra: 2.5 → 2,5 · 12345 → 12.345

Se escribe a mano (no con locale) para que dé exactamente lo mismo en cualquier equipo y en el navegador.
Los dos lados se prueban contra los mismos casos: tests/money_cases.json.
Sin dependencias: lo puede importar cualquier módulo.
"""
import math

MINUS = "−"   # signo menos tipográfico (U+2212), como en el frontend


def _round2(value) -> float:
    """Redondeo a centavos, mitad hacia arriba, igual en Python y JavaScript (Math.floor(x*100+0.5)/100)."""
    try:
        v = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(v) or math.isinf(v):
        return 0.0
    r = math.floor(abs(v) * 100 + 0.5) / 100
    return -r if v < 0 and r != 0 else r


def _group(integer: int) -> str:
    return f"{integer:,}".replace(",", ".")


def _split(a: float):
    """Valor ≥ 0 ya redondeado → (parte entera, centavos 0–99)."""
    cents = int(round(a * 100))
    return cents // 100, cents % 100


def money(value) -> str:
    """$1.500 · $999,99 · −$1.500 · $0."""
    n = _round2(value)
    whole, cents = _split(abs(n))
    text = _group(whole) + (f",{cents:02d}" if cents else "")
    return (MINUS if n < 0 else "") + "$" + text


def signed_money(value) -> str:
    """+$300 · −$800 · $0 (diferencias: sobrantes/faltantes, ajustes)."""
    n = _round2(value)
    return ("+" if n > 0 else "") + money(n)


def number(value) -> str:
    """12.345 · 2,5 · 0,33 · −4 (hasta 2 decimales, sin ceros de sobra)."""
    n = _round2(value)
    whole, cents = _split(abs(n))
    decimals = f"{cents:02d}".rstrip("0") if cents else ""
    return (MINUS if n < 0 else "") + _group(whole) + (f",{decimals}" if decimals else "")
