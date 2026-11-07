"""Exportación de reportes a Excel (.xlsx) y PDF (backlog P2.33).

Decisiones del usuario: Excel + PDF + se mantiene el CSV; PDF máximo 3.000 filas (más → usar Excel);
cada exportación queda en la auditoría; el estado de cuenta del cliente muestra lo pendiente y sus abonos.

Uso:
    report = Report(title="Reporte de ventas", filename="ventas_2026-11-01_2026-11-05",
                    filters=["Del 01/11/2026 al 05/11/2026"], summary=[("Ventas netas", money(1250000))],
                    sheets=[Sheet("Facturas", [Col("invoice_number", "Factura"), Col("total", "Total", "money")], rows,
                                  totals={"total": 1250000})])
    return await export_response(report, "xlsx", current_user, module="reports")

Tipos de columna: text · int · number · money · percent · date · datetime (las fechas ya en hora local).
"""
import io
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.errors import BusinessError
from fastapi.responses import Response

from core import audit
from core.database import db
from core.dates import now_utc
from core.money import money, number  # noqa: F401

PDF_MAX_ROWS = 3000
FORMATS = ("csv", "xlsx", "pdf")
MEDIA = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
    "csv": "text/csv; charset=utf-8",
}
FORMAT_LABEL = {"xlsx": "Excel", "pdf": "PDF", "csv": "CSV"}


@dataclass
class Col:
    key: str
    label: str
    kind: str = "text"
    width: float = 0          # ancho relativo (0 = según el tipo)


@dataclass
class Sheet:
    name: str
    columns: List[Col]
    rows: List[Dict[str, Any]]
    totals: Optional[Dict[str, Any]] = None
    in_pdf: bool = True        # hojas de detalle muy largas pueden quedar solo en Excel


@dataclass
class Report:
    title: str
    filename: str
    sheets: List[Sheet]
    filters: List[str] = field(default_factory=list)
    summary: List[Tuple[str, str]] = field(default_factory=list)
    landscape: bool = True
    notes: List[str] = field(default_factory=list)     # párrafos extra (p. ej. observaciones del cierre)


# money / number: formato único del sistema (core/money.py), re-exportados para los reportes.


def check_format(fmt: Optional[str]) -> str:
    fmt = (fmt or "csv").lower()
    if fmt not in FORMATS:
        raise BusinessError("Formato inválido: usa xlsx (Excel), pdf o csv.")
    return fmt


async def company() -> Dict[str, str]:
    cfg = await db.ticket_config.find_one({}, {"_id": 0}) or {}
    return {"name": (cfg.get("company_name") or "Mi Empresa").strip(), "nit": (cfg.get("nit") or "").strip(),
            "phone": (cfg.get("phone") or "").strip(), "address": (cfg.get("address") or "").strip()}


def _default_width(kind: str) -> float:
    return {"money": 14, "int": 9, "number": 10, "percent": 8, "date": 11, "datetime": 15}.get(kind, 18)


def _display(value, kind: str) -> str:
    if value is None or value == "":
        return ""
    if kind == "money":
        return money(value)
    if kind == "percent":
        return f"{number(value)}%"
    if kind in ("int", "number"):
        return number(value) if isinstance(value, (int, float)) else str(value)
    if kind == "date" and isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")
    if kind == "datetime" and isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M")
    return str(value)


# ---------------------------------------------------------------- Excel

def render_xlsx(report: Report, comp: Dict[str, str], generated: str) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    wb.remove(wb.active)
    head_fill = PatternFill("solid", fgColor="1F2937")
    head_font = Font(bold=True, color="FFFFFF")
    total_font = Font(bold=True)
    thin = Side(style="thin", color="D1D5DB")
    fmt = {"money": '"$" #,##0;[Red]-"$" #,##0', "int": "#,##0", "number": "#,##0.##", "percent": '0.##"%"',
           "date": "dd/mm/yyyy", "datetime": "dd/mm/yyyy hh:mm"}

    def header_block(ws, ncols: int) -> int:
        ws.cell(row=1, column=1, value=comp["name"] + (f" · NIT {comp['nit']}" if comp["nit"] else "")).font = Font(bold=True, size=13)
        ws.cell(row=2, column=1, value=report.title).font = Font(bold=True, size=12)
        line = 3
        for f in report.filters:
            ws.cell(row=line, column=1, value=f).font = Font(italic=True, color="4B5563")
            line += 1
        ws.cell(row=line, column=1, value=generated).font = Font(italic=True, color="6B7280")
        return line + 2

    for sheet in report.sheets:
        ws = wb.create_sheet(title=sheet.name[:31])
        start = header_block(ws, len(sheet.columns))
        for c, col in enumerate(sheet.columns, start=1):
            cell = ws.cell(row=start, column=c, value=col.label)
            cell.fill, cell.font = head_fill, head_font
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            ws.column_dimensions[get_column_letter(c)].width = max(col.width or _default_width(col.kind), len(col.label) + 2)
        r = start
        for row in sheet.rows:
            r += 1
            for c, col in enumerate(sheet.columns, start=1):
                v = row.get(col.key)
                if isinstance(v, datetime) and v.tzinfo is not None:
                    v = v.replace(tzinfo=None)
                cell = ws.cell(row=r, column=c, value=v)
                if col.kind in fmt:
                    cell.number_format = fmt[col.kind]
                cell.border = Border(bottom=thin)
        if sheet.totals:
            r += 1
            for c, col in enumerate(sheet.columns, start=1):
                v = sheet.totals.get(col.key)
                if v is None and c == 1:
                    v = "TOTAL"
                cell = ws.cell(row=r, column=c, value=v)
                cell.font = total_font
                if col.kind in fmt and not isinstance(v, str):
                    cell.number_format = fmt[col.kind]
                cell.border = Border(top=Side(style="medium"))
        ws.freeze_panes = ws.cell(row=start + 1, column=1)
        if sheet.rows:
            ws.auto_filter.ref = f"A{start}:{get_column_letter(len(sheet.columns))}{start + len(sheet.rows)}"

    if report.summary or report.notes:
        ws = wb.create_sheet(title="Resumen", index=0)
        line = header_block(ws, 2)
        ws.column_dimensions["A"].width = 34
        ws.column_dimensions["B"].width = 22
        for label, value in report.summary:
            ws.cell(row=line, column=1, value=label).font = Font(bold=True)
            ws.cell(row=line, column=2, value=value).alignment = Alignment(horizontal="right")
            line += 1
        for n in report.notes:
            line += 1
            ws.cell(row=line, column=1, value=n).alignment = Alignment(wrap_text=True)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------- PDF

def render_pdf(report: Report, comp: Dict[str, str], generated: str) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from xml.sax.saxutils import escape

    pdf_sheets = [s for s in report.sheets if s.in_pdf]
    rows_total = sum(len(s.rows) for s in pdf_sheets)
    if rows_total > PDF_MAX_ROWS:
        raise BusinessError(f"El PDF admite máximo {number(PDF_MAX_ROWS)} filas y este reporte tiene {number(rows_total)}. "
                            "Expórtalo en Excel o filtra un periodo más corto.")

    page = landscape(A4) if report.landscape else A4
    styles = getSampleStyleSheet()
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=7.5, leading=9)
    small_r = ParagraphStyle("small_r", parent=small, alignment=2)
    head = ParagraphStyle("head", parent=small, textColor=colors.white, fontName="Helvetica-Bold")
    title = ParagraphStyle("title", parent=styles["Heading2"], spaceAfter=2)
    meta = ParagraphStyle("meta", parent=styles["Normal"], fontSize=8.5, textColor=colors.HexColor("#4B5563"))
    company_line = escape(comp["name"]) + (f" · NIT {escape(comp['nit'])}" if comp["nit"] else "")

    class NumberedCanvas(rl_canvas.Canvas):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self._pages = []

        def showPage(self):
            self._pages.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            n = len(self._pages)
            for state in self._pages:
                self.__dict__.update(state)
                self.setFont("Helvetica", 7.5)
                self.setFillColor(colors.HexColor("#6B7280"))
                self.drawString(12 * mm, 8 * mm, f"{comp['name']} · {report.title} · {generated}")
                self.drawRightString(page[0] - 12 * mm, 8 * mm, f"Página {self._pageNumber} de {n}")
                super().showPage()
            super().save()

    story = [Paragraph(company_line, styles["Normal"]), Paragraph(escape(report.title), title)]
    for f in report.filters:
        story.append(Paragraph(escape(f), meta))
    story.append(Paragraph(escape(generated), meta))
    story.append(Spacer(1, 4 * mm))
    if report.summary:
        cells = [[Paragraph(f"<b>{escape(k)}</b>", small), Paragraph(escape(v), small_r)] for k, v in report.summary]
        half = (len(cells) + 1) // 2
        grid = [cells[i] + (cells[i + half] if i + half < len(cells) else ["", ""]) for i in range(half)]
        t = Table(grid, colWidths=[55 * mm, 35 * mm, 55 * mm, 35 * mm], hAlign="LEFT")
        t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                               ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
                               ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        story += [t, Spacer(1, 4 * mm)]
    for n in report.notes:
        story += [Paragraph(escape(n), styles["Normal"]), Spacer(1, 2 * mm)]

    avail = page[0] - 24 * mm
    for sheet in pdf_sheets:
        if len(pdf_sheets) > 1 or report.summary:
            story.append(Paragraph(f"<b>{escape(sheet.name)}</b>", styles["Heading4"]))
        widths = [c.width or _default_width(c.kind) for c in sheet.columns]
        scale = avail / sum(widths)
        col_w = [w * scale for w in widths]
        right = {"money", "int", "number", "percent"}
        data = [[Paragraph(escape(c.label), head) for c in sheet.columns]]
        for row in sheet.rows:
            data.append([Paragraph(escape(_display(row.get(c.key), c.kind)), small_r if c.kind in right else small) for c in sheet.columns])
        if sheet.totals:
            data.append([Paragraph(f"<b>{escape(_display(sheet.totals.get(c.key), c.kind) if sheet.totals.get(c.key) is not None else ('TOTAL' if i == 0 else ''))}</b>",
                                   small_r if c.kind in right else small) for i, c in enumerate(sheet.columns)])
        if len(data) == 1:
            data.append([Paragraph("Sin datos para este filtro.", small)] + [""] * (len(sheet.columns) - 1))
        t = Table(data, colWidths=col_w, repeatRows=1)
        style = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F2937")),
                 ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                 ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                 ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
        for i in range(1, len(data)):
            if i % 2 == 0:
                style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F3F4F6")))
        if sheet.totals:
            style.append(("LINEABOVE", (0, len(data) - 1), (-1, len(data) - 1), 1, colors.black))
        t.setStyle(TableStyle(style))
        story += [t, Spacer(1, 5 * mm)]
    if not pdf_sheets:
        story.append(KeepTogether([Paragraph("El detalle completo está en la versión Excel.", meta)]))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=page, leftMargin=12 * mm, rightMargin=12 * mm, topMargin=12 * mm, bottomMargin=14 * mm,
                            title=report.title, author=comp["name"])
    doc.build(story, canvasmaker=NumberedCanvas)
    return buf.getvalue()


# ---------------------------------------------------------------- respuesta + auditoría

def render_csv(report: Report) -> bytes:
    import csv
    sheet = report.sheets[0]
    out = io.StringIO()
    w = csv.writer(out, delimiter=";")
    w.writerow([c.label for c in sheet.columns])
    for row in sheet.rows:
        w.writerow([row.get(c.key, "") if not isinstance(row.get(c.key), datetime) else _display(row.get(c.key), c.kind)
                    for c in sheet.columns])
    return ("﻿" + out.getvalue()).encode("utf-8")


async def export_response(report: Report, fmt: str, user, module: str, tz_offset_minutes: int = 0) -> Response:
    from datetime import timedelta
    fmt = check_format(fmt)
    comp = await company()
    local_now = now_utc() - timedelta(minutes=tz_offset_minutes or 0)
    who = (getattr(user, "full_name", "") or "").strip() or user.email
    generated = f"Generado el {local_now.strftime('%d/%m/%Y %H:%M')} por {who}"
    if fmt == "xlsx":
        data = render_xlsx(report, comp, generated)
    elif fmt == "pdf":
        data = render_pdf(report, comp, generated)
    else:
        data = render_csv(report)
    rows = sum(len(s.rows) for s in report.sheets[:1])
    await audit.record(module, "export", entity_id=report.filename, entity_name=report.title,
                       summary=f"Exportó «{report.title}» ({FORMAT_LABEL[fmt]})"
                               + (f" · {'; '.join(report.filters)}" if report.filters else "") + f" · {rows} fila(s)",
                       after={"format": fmt, "rows": rows, "filters": report.filters})
    return Response(content=data, media_type=MEDIA[fmt],
                    headers={"Content-Disposition": f'attachment; filename="{report.filename}.{fmt}"'})


def local(dt, tz_offset_minutes: int):
    """Fecha nativa UTC → datetime local sin zona (para Excel/PDF)."""
    from datetime import timedelta
    from core.dates import as_datetime
    d = as_datetime(dt) if dt else None
    if not isinstance(d, datetime):
        return None
    return (d - timedelta(minutes=tz_offset_minutes or 0)).replace(tzinfo=None)


def period_label(start_date: Optional[str], end_date: Optional[str]) -> Optional[str]:
    def f(s):
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
        except (ValueError, TypeError):
            return s
    if start_date and end_date:
        return f"Del {f(start_date)} al {f(end_date)}"
    if start_date:
        return f"Desde el {f(start_date)}"
    if end_date:
        return f"Hasta el {f(end_date)}"
    return "Todo el periodo"
