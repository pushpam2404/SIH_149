"""Renders a Report as a PDF (erasure certificates, forensic recovery reports)."""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.reporting.report_builder import Report

_MAX_ROWS_PER_TABLE = 200  # keep the PDF generation fast/bounded for very large batches


def render_pdf(report: Report, output_path: str) -> Path:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(out), pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    story = []

    story.append(Paragraph(report.title, styles["Title"]))
    story.append(Paragraph(f"Report ID: {report.report_id}", styles["Normal"]))
    story.append(Paragraph(f"Generated (UTC): {report.generated_at}", styles["Normal"]))
    story.append(Spacer(1, 0.4 * cm))

    if report.notice:
        story.append(Paragraph(f"<b>NOTICE:</b> {report.notice}", styles["Normal"]))
        story.append(Spacer(1, 0.4 * cm))

    story.append(Paragraph("Summary", styles["Heading2"]))
    summary_rows = [[str(k), str(v)] for k, v in report.summary.items()]
    story.append(_table(summary_rows, header=None))
    story.append(Spacer(1, 0.5 * cm))

    for section in report.sections:
        story.append(Paragraph(section.title, styles["Heading2"]))
        if not section.rows:
            story.append(Paragraph("(no entries)", styles["Normal"]))
            story.append(Spacer(1, 0.4 * cm))
            continue
        columns = list(section.rows[0].keys())
        data_rows = [columns] + [
            [str(row.get(col, "")) for col in columns] for row in section.rows[:_MAX_ROWS_PER_TABLE]
        ]
        story.append(_table(data_rows, header=columns))
        if len(section.rows) > _MAX_ROWS_PER_TABLE:
            story.append(
                Paragraph(
                    f"... and {len(section.rows) - _MAX_ROWS_PER_TABLE} more rows (see JSON export for full data).",
                    styles["Normal"],
                )
            )
        story.append(Spacer(1, 0.5 * cm))

    doc.build(story)
    return out


def _table(data_rows: list[list[str]], header: list[str] | None) -> Table:
    table = Table(data_rows, repeatRows=1 if header else 0)
    style = [
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")))
        style.append(("TEXTCOLOR", (0, 0), (-1, 0), colors.white))
        style.append(("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"))
    table.setStyle(TableStyle(style))
    return table
