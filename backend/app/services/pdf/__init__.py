from io import BytesIO
from typing import Dict, Any, List

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, ListFlowable, ListItem
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.pdfbase.pdfmetrics import stringWidth


def build_study_guide_pdf(
    title: str,
    content: Dict[str, Any],
    course_name: str = "",
) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=LETTER,
        leftMargin=0.75*inch, rightMargin=0.75*inch,
        topMargin=0.75*inch, bottomMargin=0.75*inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CoverTitle", parent=styles["Title"],
        fontSize=22, leading=26, alignment=TA_CENTER,
        textColor=colors.HexColor("#1e1b4b"), spaceAfter=20,
    )
    h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=16, leading=20, textColor=colors.HexColor("#312e81"), spaceBefore=14, spaceAfter=8)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=13, leading=16, textColor=colors.HexColor("#4338ca"), spaceBefore=10, spaceAfter=6)
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=10, leading=14, alignment=TA_LEFT)
    subtle = ParagraphStyle("Subtle", parent=body, textColor=colors.HexColor("#4b5563"), fontSize=9)
    badge = ParagraphStyle("Badge", parent=body, textColor=colors.HexColor("#1e40af"), fontSize=9, backColor=colors.HexColor("#e0e7ff"), borderPadding=3)

    story = []

    story.append(Spacer(1, 0.8*inch))
    story.append(Paragraph(title or "Study Guide", title_style))
    if course_name:
        story.append(Paragraph(course_name, ParagraphStyle("Sub", parent=styles["Normal"], alignment=TA_CENTER, fontSize=12, textColor=colors.HexColor("#4b5563"))))
    story.append(Spacer(1, 0.6*inch))

    coverage_summary = content.get("coverage_summary", {}) if isinstance(content, dict) else {}
    if coverage_summary:
        data = [
            ["Total Topics", "Total Lectures", "High-Coverage Topics"],
            [
                str(coverage_summary.get("total_topics", 0)),
                str(coverage_summary.get("total_lectures", 0)),
                str(coverage_summary.get("high_coverage_topics", 0)),
            ],
        ]
        t = Table(data, colWidths=[2*inch, 2*inch, 2.3*inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4338ca")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f5f3ff")),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.3*inch))

    lecture_summaries = content.get("lecture_summaries", []) if isinstance(content, dict) else []
    if lecture_summaries:
        story.append(Paragraph("Lecture Summaries", h1))
        for ls in lecture_summaries:
            ltitle = ls.get("title", "Lecture")
            overview = (ls.get("overview") or "No overview available.").strip()
            story.append(Paragraph(escape(ltitle), h2))
            story.append(Paragraph(escape(overview[:800]), body))
            story.append(Spacer(1, 6))

    top_topics = content.get("top_topics", []) if isinstance(content, dict) else []
    if top_topics:
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph("Key Topics by Coverage", h1))

        for i, tt in enumerate(top_topics):
            name = tt.get("name", "Topic")
            score = float(tt.get("coverage_score", 0)) * 100
            lectures_in = tt.get("lectures", [])
            lect_list = ", ".join(l.get("title", "") for l in lectures_in[:5])

            story.append(Paragraph(f"{i+1}. {escape(name)}", h2))

            meta = f"Coverage: {score:.0f}% | Lectures: {tt.get('lecture_count', 0)} | Evidence pieces: {tt.get('evidence_count', 0)}"
            story.append(Paragraph(escape(meta), badge))
            story.append(Spacer(1, 4))

            summary = (tt.get("summary") or "Recurring concept across the semester.").strip()
            story.append(Paragraph(escape(summary), body))

            if lect_list:
                story.append(Paragraph(f"Source lectures: {escape(lect_list)}", subtle))
            story.append(Spacer(1, 8))

    doc.build(story)
    return buf.getvalue()


def escape(text: str) -> str:
    if text is None:
        return ""
    text = str(text)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
