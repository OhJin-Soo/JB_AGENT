from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.schemas.analysis import AnalysisResponse


def build_pdf_report(analysis: AnalysisResponse) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 64

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(48, y, analysis.title)
    y -= 32

    pdf.setFont("Helvetica", 10)
    pdf.drawString(48, y, f"Created at: {analysis.created_at.isoformat()}")
    y -= 28

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(48, y, "Summary")
    y -= 18
    pdf.setFont("Helvetica", 10)
    for line in _wrap_text(analysis.result.summary, 90):
        pdf.drawString(48, y, line)
        y -= 14

    y -= 10
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(48, y, "Forecast")
    y -= 18
    pdf.setFont("Helvetica", 9)
    pdf.drawString(48, y, "Month")
    pdf.drawString(120, y, "Income")
    pdf.drawString(210, y, "Expense")
    pdf.drawString(300, y, "Net Cashflow")
    pdf.drawString(410, y, "Net Worth")
    y -= 14

    for point in analysis.result.forecast[:24]:
        if y < 64:
            pdf.showPage()
            y = height - 64
            pdf.setFont("Helvetica", 9)
        pdf.drawString(48, y, point.month)
        pdf.drawRightString(175, y, f"{point.income:,.0f}")
        pdf.drawRightString(265, y, f"{point.expense:,.0f}")
        pdf.drawRightString(385, y, f"{point.net_cashflow:,.0f}")
        pdf.drawRightString(500, y, f"{point.net_worth:,.0f}")
        y -= 14

    pdf.save()
    return buffer.getvalue()


def _wrap_text(text: str, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join([*current, word])
        if len(candidate) > width and current:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines
