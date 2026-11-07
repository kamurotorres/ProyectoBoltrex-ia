"""core/exporting.py (P2.33: Excel/PDF/CSV) y core/importing.py (fase 1b: Importar sin pandas)."""
import io
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from openpyxl import Workbook, load_workbook

from core.errors import BusinessError
from core.exporting import (PDF_MAX_ROWS, Col, Report, Sheet, _display, check_format, local, money, period_label,
                            render_csv, render_pdf, render_xlsx)
from core.importing import MAX_ROWS, has, read_table, text

COMP = {"name": "Tienda Don Pepe", "nit": "900.123.456-7", "phone": "", "address": ""}
WHEN = datetime(2026, 11, 6, 15, 30)


def _report(rows=None, **kw):
    cols = [Col("name", "Producto"), Col("qty", "Cantidad", "int"), Col("total", "Total", "money"), Col("at", "Fecha", "datetime")]
    rows = rows if rows is not None else [{"name": "Gaseosa", "qty": 2, "total": 3000.0, "at": WHEN},
                                          {"name": "Pan; tajado", "qty": 1, "total": 2500, "at": None}]
    return Report(title="Ventas", filename="ventas", sheets=[Sheet("Ventas", cols, rows, totals={"total": 5500})], **kw)


# ---------------------------------------------------------------- exportar
def test_formato_de_dinero_con_negativos():
    assert money(1500) == "$1.500" and money(-1500) == "−$1.500" and money(None) == "$0"


def test_formato_pedido():
    assert check_format(None) == "csv" and check_format("XLSX") == "xlsx" and check_format("pdf") == "pdf"
    with pytest.raises(BusinessError, match="Formato inválido"):
        check_format("docx")


@pytest.mark.parametrize("value, kind, shown", [
    (None, "money", ""), ("", "text", ""), (1234.4, "money", "$1.234"), (19, "percent", "19%"), (8.5, "percent", "8.5%"),
    (12345, "int", "12.345"), (2.5, "number", "2.5"), (WHEN, "date", "06/11/2026"), (WHEN, "datetime", "06/11/2026 15:30"),
    ("x", "text", "x"),
])
def test_como_se_muestra_cada_tipo(value, kind, shown):
    assert _display(value, kind) == shown


def test_csv_para_excel_en_espanol():
    data = render_csv(_report())
    assert data.startswith("﻿".encode("utf-8"))                 # BOM: Excel lo abre con tildes bien
    lines = data.decode("utf-8-sig").splitlines()
    assert lines[0] == "Producto;Cantidad;Total;Fecha"
    assert lines[1] == "Gaseosa;2;3000.0;06/11/2026 15:30"
    assert lines[2] == '"Pan; tajado";1;2500;'                      # el ; dentro del texto va entre comillas


def test_excel_con_encabezado_de_empresa_y_datos():
    wb = load_workbook(io.BytesIO(render_xlsx(_report(filters=["Del 01/11/2026 al 06/11/2026"]), COMP, "Generado hoy")))
    values = [v for row in wb.worksheets[0].iter_rows(values_only=True) for v in row if v is not None]
    for expected in ("Tienda Don Pepe", "Ventas", "Producto", "Gaseosa", 3000, "Generado hoy"):
        assert expected in values or any(isinstance(v, str) and str(expected) in v for v in values), expected


def test_pdf_y_su_limite_de_filas():
    pdf = render_pdf(_report(), COMP, "Generado hoy")
    assert pdf.startswith(b"%PDF") and len(pdf) > 1000
    big = _report(rows=[{"name": "x", "qty": 1, "total": 1, "at": None}] * (PDF_MAX_ROWS + 1))
    with pytest.raises(BusinessError) as e:
        render_pdf(big, COMP, "x")
    assert e.value.message == ("El PDF admite máximo 3.000 filas y este reporte tiene 3.001. "
                               "Expórtalo en Excel o filtra un periodo más corto.")


def test_fecha_local_y_periodo():
    assert local(datetime(2026, 11, 6, 3, 0, tzinfo=timezone.utc), 300) == datetime(2026, 11, 5, 22, 0)
    assert local("2026-11-06T03:00:00Z", 300) == datetime(2026, 11, 5, 22, 0)
    assert local(None, 300) is None and local("x", 300) is None
    assert period_label("2026-11-01", "2026-11-06") == "Del 01/11/2026 al 06/11/2026"
    assert period_label("2026-11-01", None) == "Desde el 01/11/2026"
    assert period_label(None, "2026-11-06") == "Hasta el 06/11/2026"
    assert period_label(None, None) == "Todo el periodo"


# ---------------------------------------------------------------- importar
def _upload(name, content):
    return SimpleNamespace(filename=name, file=io.BytesIO(content))


def test_csv_con_punto_y_coma_conserva_ceros_y_numera_filas():
    content = "barcode;name;price\n00123;Gaseosa;1500\n;;\n  0456 ; Pan ;2.0\n".encode("utf-8")
    cols, rows = read_table(_upload("productos.CSV", content))
    assert cols == ["barcode", "name", "price"]
    # La fila vacía (3) se salta, pero los números de fila son los de la hoja.
    assert rows == [(2, {"barcode": "00123", "name": "Gaseosa", "price": "1500"}),
                    (4, {"barcode": "0456", "name": "Pan", "price": "2.0"})]


def test_csv_con_comas_bom_y_latin1():
    _, rows = read_table(_upload("a.csv", "﻿code,name\n1,Café\n".encode("utf-8")))
    assert rows == [(2, {"code": "1", "name": "Café"})]
    _, rows = read_table(_upload("a.csv", "code,name\n1,Café\n".encode("latin-1")))
    assert rows[0][1]["name"] == "Café"


def test_excel_numeros_enteros_y_fechas():
    wb = Workbook()
    ws = wb.active
    ws.append(["barcode", "price", "since", None])
    ws.append(["00123", 5.0, datetime(2026, 11, 6), None])
    ws.append([None, None, None, None])
    ws.append([770, 2.5, None, None])
    buf = io.BytesIO()
    wb.save(buf)
    cols, rows = read_table(_upload("p.xlsx", buf.getvalue()))
    assert cols == ["barcode", "price", "since"]                    # columnas vacías al final se quitan
    assert rows == [(2, {"barcode": "00123", "price": 5, "since": "2026-11-06"}),
                    (4, {"barcode": 770, "price": 2.5, "since": None})]


@pytest.mark.parametrize("name, content, message", [
    ("p.xls", b"x", "El formato .xls (Excel antiguo) no es compatible: guarda el archivo como .xlsx o CSV."),
    ("p.txt", b"x", "Formato de archivo no soportado. Use CSV o Excel (.xlsx)."),
    ("p.csv", b"", "El archivo está vacío: la primera fila debe tener los nombres de las columnas."),
    # Encabezado sin nombres. Ojo: con «;;» el detector de separador de Python no decide y se asume «,»
    # (queda una columna llamada «;;»); con archivos reales sí detecta «;» (ver la prueba de arriba).
    ("p.csv", b",,\n1,2", "La primera fila debe tener los nombres de las columnas."),
])
def test_archivos_invalidos(name, content, message):
    with pytest.raises(BusinessError) as e:
        read_table(_upload(name, content))
    assert e.value.message == message


def test_excel_danado():
    with pytest.raises(BusinessError, match="No se pudo leer el Excel"):
        read_table(_upload("p.xlsx", b"no es un excel"))


def test_limite_de_filas():
    content = ("a\n" + "1\n" * (MAX_ROWS + 1)).encode()
    with pytest.raises(BusinessError) as e:
        read_table(_upload("p.csv", content))
    assert e.value.message == "El archivo tiene más de 20.000 filas: divídelo en varios."


def test_celdas_con_dato():
    assert has(0) and has("x") and has(0.0)
    assert not has(None) and not has("") and not has("   ")
    assert text(5) == "5" and text(None) is None and text(" ", "def") == "def"
