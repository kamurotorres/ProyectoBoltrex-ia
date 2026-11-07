"""Reglas de arquitectura del backend (mantenimiento fases 2 y 3) convertidas en pruebas: si alguien las
rompe, el CI lo dice con el archivo y la línea. Ver memorias_claude/ARQUITECTURA_BIG_PICTURE.md.

  routers/ (HTTP) → services/ (casos de uso) → core/ + repositories/ (reglas y datos)
"""
import ast
import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
# Módulos de core/ que SON capa HTTP (sesión 401, login 429, permisos 403): pueden usar HTTPException.
HTTP_CORE = {"security.py", "sessions.py", "login_throttle.py", "permissions.py"}


def _py(folder):
    return sorted(p for p in (BACKEND / folder).rglob("*.py") if "__pycache__" not in p.parts)


def _imports(path):
    """[(línea, módulo importado)] del archivo."""
    out = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out += [(node.lineno, a.name) for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.append((node.lineno, node.module))
            out += [(node.lineno, f"{node.module}.{a.name}") for a in node.names]
    return out


def _where(path, line):
    return f"{path.relative_to(BACKEND)}:{line}"


def test_un_router_nunca_importa_otro_router():
    bad = [_where(p, n) + f" importa {m}" for p in _py("routers") for n, m in _imports(p) if m.split(".")[0] == "routers"]
    assert not bad, "Un router importa otro router (mover la lógica compartida a services/ o core/):\n" + "\n".join(bad)


def test_services_y_core_no_importan_routers():
    bad = [_where(p, n) + f" importa {m}" for folder in ("services", "core", "repositories")
           for p in _py(folder) for n, m in _imports(p) if m.split(".")[0] == "routers"]
    assert not bad, "Dependencia hacia arriba (capas: routers → services → core/repositories):\n" + "\n".join(bad)


def test_repositories_no_dependen_de_services():
    bad = [_where(p, n) + f" importa {m}" for p in _py("repositories") for n, m in _imports(p) if m.split(".")[0] == "services"]
    assert not bad, "\n".join(bad)


def test_la_logica_de_negocio_no_usa_httpexception():
    files = _py("services") + _py("repositories") + [p for p in _py("core") if p.name not in HTTP_CORE]
    bad = [_where(p, n) for p in files for n, m in _imports(p) if m.endswith("HTTPException")]
    assert not bad, ("HTTPException en lógica de negocio: usar core/errors (BusinessError, NotFoundError, …):\n"
                     + "\n".join(bad))


def test_services_no_dependen_de_fastapi():
    bad = [_where(p, n) + f" importa {m}" for p in _py("services") for n, m in _imports(p) if m.split(".")[0] in ("fastapi", "starlette")]
    assert not bad, "services/ debe poder usarse sin FastAPI:\n" + "\n".join(bad)


STOCK_WRITE = re.compile(r"""["']\$(inc|set)["']\s*:\s*\{[^}]*["']stock["']|inventory_movements\s*\.\s*(insert|update|delete|replace|bulk_write|find_one_and)""")


def test_el_stock_solo_se_escribe_en_repositories_products():
    allowed = BACKEND / "repositories" / "products.py"
    bad = []
    for folder in ("routers", "services", "core", "repositories"):
        for p in _py(folder):
            if p == allowed:
                continue
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
                if STOCK_WRITE.search(line):
                    bad.append(f"{_where(p, i)}: {line.strip()}")
    assert not bad, ("El stock y los movimientos de inventario se cambian solo con repositories/products.py "
                     "(take_stock, add_stock, set_stock_if, record_movement):\n" + "\n".join(bad))
    assert STOCK_WRITE.search(allowed.read_text(encoding="utf-8")), "la regla ya no reconoce las escrituras del repositorio"


def test_sin_imports_con_asterisco():
    bad = []
    for p in sorted(BACKEND.rglob("*.py")):
        if ".venv" in p.parts or "__pycache__" in p.parts:
            continue
        for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and any(a.name == "*" for a in node.names):
                bad.append(_where(p, node.lineno))
    assert not bad, "Prohibido `from x import *` (fase 2):\n" + "\n".join(bad)


def test_todo_el_backend_compila_e_importa_sin_base_de_datos():
    import main
    assert len(main.app.routes) >= 120


# Formato de dinero/números a mano (f"{v:,.2f}", f"{v:,}", "{:,.0f}".format(v), format(v, ",")): solo en core/money.py.
def _manual_number_formats(path):
    """Líneas con un formato numérico de miles (coma en el formato), leyendo el código con ast."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    lines = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FormattedValue) and node.format_spec is not None:
            spec = "".join(v.value for v in node.format_spec.values if isinstance(v, ast.Constant) and isinstance(v.value, str))
            if "," in spec:
                lines.add(node.lineno)
        elif isinstance(node, ast.Call):
            f = node.func
            if (isinstance(f, ast.Attribute) and f.attr == "format" and isinstance(f.value, ast.Constant)
                    and isinstance(f.value.value, str) and re.search(r"\{[^}]*:[^}]*,[^}]*\}", f.value.value)):
                lines.add(node.lineno)
            if (isinstance(f, ast.Name) and f.id == "format" and len(node.args) == 2 and isinstance(node.args[1], ast.Constant)
                    and "," in str(node.args[1].value)):
                lines.add(node.lineno)
    return sorted(lines)


def test_dinero_y_numeros_solo_con_core_money():
    allowed = BACKEND / "core" / "money.py"
    files = [BACKEND / "ticket_generator.py"] + [p for f in ("routers", "services", "core", "repositories") for p in _py(f)]
    bad = []
    for p in files:
        if p == allowed:
            continue
        text = p.read_text(encoding="utf-8").splitlines()
        bad += [f"{_where(p, n)}: {text[n - 1].strip()}" for n in _manual_number_formats(p)]
    assert not bad, ("Formato de número a mano: usar money()/number() de core/money.py (formato colombiano único, "
                     "el mismo del frontend):\n" + "\n".join(bad))


def test_la_regla_de_formatos_reconoce_los_casos(tmp_path):
    sample = tmp_path / "x.py"
    sample.write_text('a = f"{v:,.2f}"\nb = f"{v:,}"\nc = "{:,.0f}".format(v)\nd = format(v, ",")\n'
                      'ok1 = {"a": 1, "b": 2}\nok2 = f"{v:.2f} {name}"\n', encoding="utf-8")
    assert _manual_number_formats(sample) == [1, 2, 3, 4]
