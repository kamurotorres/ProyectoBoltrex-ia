"""Lectura de archivos para la pantalla Importar (CSV y Excel .xlsx) sin pandas.

Mantenimiento fase 1b: antes se usaba pandas (+ numpy, ~100 MB en la imagen) solo para leer estas
tablas. Ahora: `csv` de Python y `openpyxl` (el mismo de las exportaciones).

Comportamiento (igual o mejor que con pandas):
- Encabezados en la primera fila; se les quitan los espacios de los lados.
- Celdas vacías → None (antes NaN). Filas totalmente vacías se ignoran.
- Cada fila trae su número REAL en la hoja (la del encabezado es la 1), para los mensajes de error.
- Excel: un número entero se lee como entero (un documento 123456 no se vuelve "123456.0", lo que con
  pandas pasaba si la columna tenía alguna celda vacía).
- CSV: todo se lee como texto (los ceros a la izquierda de un código, p. ej. 00123, se conservan; pandas
  los perdía). Acepta UTF-8 (con o sin BOM) y Latin-1, y separador «,», «;» o tabulador (los CSV que
  guarda Excel en español usan «;»).
- El formato .xls antiguo no se puede leer: se pide guardarlo como .xlsx o CSV (con pandas también
  fallaba, porque faltaba la librería xlrd).
"""
import csv
import io
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import UploadFile

from core.errors import BusinessError
from core.money import number as fmt_number   # «number» ya es la variable del número de fila

MAX_ROWS = 20000
Row = Dict[str, Any]


def _clean(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip()
        return v if v != "" else None
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    return value


def _decode(content: bytes) -> str:
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return content.decode(enc)
        except UnicodeDecodeError:
            continue
    raise BusinessError("No se pudo leer el CSV: guárdalo con codificación UTF-8.")


def _read_csv(content: bytes) -> List[List[Any]]:
    text = _decode(content)
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","
    return list(csv.reader(io.StringIO(text), delimiter=delimiter))


def _read_xlsx(content: bytes) -> List[List[Any]]:
    from openpyxl import load_workbook
    try:
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:
        raise BusinessError(f"No se pudo leer el Excel: {exc}")
    ws = wb.worksheets[0]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    wb.close()
    return rows


def read_table(file: UploadFile) -> Tuple[List[str], List[Tuple[int, Row]]]:
    """Devuelve (columnas, [(número de fila en la hoja, {columna: valor})])."""
    name = (file.filename or "").lower()
    content = file.file.read()
    if name.endswith(".csv"):
        raw = _read_csv(content)
    elif name.endswith(".xlsx"):
        raw = _read_xlsx(content)
    elif name.endswith(".xls"):
        raise BusinessError("El formato .xls (Excel antiguo) no es compatible: guarda el archivo como .xlsx o CSV.")
    else:
        raise BusinessError("Formato de archivo no soportado. Use CSV o Excel (.xlsx).")
    if not raw:
        raise BusinessError("El archivo está vacío: la primera fila debe tener los nombres de las columnas.")
    header = [str(h).strip() if h is not None else "" for h in raw[0]]
    while header and header[-1] == "":
        header.pop()
    if not any(header):
        raise BusinessError("La primera fila debe tener los nombres de las columnas.")
    rows: List[Tuple[int, Row]] = []
    for number, values in enumerate(raw[1:], start=2):
        cells = [_clean(v) for v in values]
        if all(c is None for c in cells):
            continue
        row = {col: (cells[i] if i < len(cells) else None) for i, col in enumerate(header) if col}
        rows.append((number, row))
        if len(rows) > MAX_ROWS:
            raise BusinessError(f"El archivo tiene más de {fmt_number(MAX_ROWS)} filas: divídelo en varios.")
    return [h for h in header if h], rows


def has(value: Any) -> bool:
    """¿La celda tiene dato? (reemplaza a pd.notna)."""
    return value is not None and str(value).strip() != ""


def text(value: Any, default: Optional[str] = None) -> Optional[str]:
    return str(value) if has(value) else default
