"""core/money.py — regla única de formato colombiano (misma tabla que el frontend: tests/money_cases.json)."""
import json
from pathlib import Path

import pytest

from core import money as M

CASES = json.loads((Path(__file__).resolve().parents[1] / "money_cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("fn", ["money", "signed_money", "number"])
def test_misma_tabla_que_el_frontend(fn):
    bad = [(v, getattr(M, fn)(v), expected) for v, expected in CASES[fn] if getattr(M, fn)(v) != expected]
    assert not bad, f"{fn}: (valor, da, esperado) {bad}"


def test_nan_e_infinito_no_rompen():
    assert M.money(float("nan")) == "$0" and M.money(float("inf")) == "$0"
