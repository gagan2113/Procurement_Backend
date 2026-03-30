"""
PDF Service — generates formatted PDF Purchase Requests using ReportLab.
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from backend.config.settings import get_settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Colour palette
BRAND_BLUE = colors.HexColor("#1A3C6E")
BRAND_LIGHT = colors.HexColor("#E8F0FC")
ACCENT = colors.HexColor("#2563EB")
SUCCESS_GREEN = colors.HexColor("#16A34A")
WARNING_ORANGE = colors.HexColor("#D97706")
TEXT_DARK = colors.HexColor("#1F2937")
TEXT_MUTED = colors.HexColor("#6B7280")
WHITE = colors.white


def _get_pdf_dir() -> Path:
    pdf_dir = Path(settings.pdf_dir)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    return pdf_dir


def generate_pr_pdf(
    pr_number: str,
    item_name: str,
    category: str,
    quantity: int,
    budget: float,
    description: str,
    improved_description: Optional[str],
    missing_fields: Optional[list],
    budget_feedback: Optional[str],
    ai_status: str,
    created_at: Optional[datetime] = None,
) -> str:
    """Generate a PDF for a Purchase Request. Returns the file path."""
    pdf_dir = _get_pdf_dir()
    safe_number = pr_number.replace("/", "-")
    file_path = pdf_dir / f"{safe_number}.pdf"

    doc = SimpleDocTemplate(
        str(file_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    elements = []

    # ── Header ──────────────────────────────────────────────────────────────
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Normal"],
        fontSize=20,
        textColor=WHITE,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#CBD5E1"),
        fontName="Helvetica",
        alignment=TA_CENTER,
    )

    header_data = [
        [Paragraph("PURCHASE REQUEST", title_style)],
        [Paragraph(f"Procurement AI System &nbsp;|&nbsp; {settings.app_name}", subtitle_style)],
    ]
    header_table = Table(header_data, colWidths=[17 * cm])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND_BLUE),
        ("TOPPADDING", (0, 0), (-1, 0), 16),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 14),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("ROUNDEDCORNERS", [6]),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.4 * cm))

    # ── PR Meta Info ─────────────────────────────────────────────────────────
    meta_label = ParagraphStyle(
        "MetaLabel",
        parent=styles["Normal"],
        fontSize=8,
        textColor=TEXT_MUTED,
        fontName="Helvetica-Bold",
    )
    meta_value = ParagraphStyle(
        "MetaValue",
        parent=styles["Normal"],
        fontSize=10,
        textColor=TEXT_DARK,
        fontName="Helvetica-Bold",
    )

    date_str = (created_at or datetime.utcnow()).strftime("%d %b %Y, %H:%M UTC")
    status_colour = SUCCESS_GREEN if ai_status == "valid" else WARNING_ORANGE
    status_label = "✓ VALID" if ai_status == "valid" else "⚠ NEEDS REVIEW"

    meta_data = [
        [
            Paragraph("PR NUMBER", meta_label),
            Paragraph("DATE CREATED", meta_label),
            Paragraph("AI VALIDATION STATUS", meta_label),
        ],
        [
            Paragraph(pr_number, ParagraphStyle("pn", parent=meta_value, textColor=ACCENT, fontSize=12)),
            Paragraph(date_str, meta_value),
            Paragraph(status_label, ParagraphStyle("st", parent=meta_value, textColor=status_colour)),
        ],
    ]
    meta_table = Table(meta_data, colWidths=[6 * cm, 6 * cm, 5 * cm])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND_LIGHT),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 0.5 * cm))

    # ── Section Header helper ─────────────────────────────────────────────────
    def section_header(title: str):
        sh = ParagraphStyle(
            "SH",
            parent=styles["Normal"],
            fontSize=10,
            textColor=WHITE,
            fontName="Helvetica-Bold",
            leftIndent=8,
        )
        t = Table([[Paragraph(title.upper(), sh)]], colWidths=[17 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), ACCENT),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return t

    # ── Procurement Details ───────────────────────────────────────────────────
    elements.append(section_header("Procurement Details"))
    elements.append(Spacer(1, 0.2 * cm))

    label_style = ParagraphStyle("lbl", parent=styles["Normal"], fontSize=9, textColor=TEXT_MUTED, fontName="Helvetica-Bold")
    value_style = ParagraphStyle("val", parent=styles["Normal"], fontSize=10, textColor=TEXT_DARK, fontName="Helvetica")

    details_data = [
        [Paragraph("Item Name", label_style), Paragraph("Category", label_style),
         Paragraph("Quantity", label_style), Paragraph("Budget (USD)", label_style)],
        [
            Paragraph(item_name, value_style),
            Paragraph(category, value_style),
            Paragraph(str(quantity), value_style),
            Paragraph(f"${budget:,.2f}", ParagraphStyle("bud", parent=value_style, fontName="Helvetica-Bold")),
        ],
    ]
    details_table = Table(details_data, colWidths=[5.5 * cm, 4 * cm, 3 * cm, 4.5 * cm])
    details_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
        ("BACKGROUND", (0, 1), (-1, 1), WHITE),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(details_table)
    elements.append(Spacer(1, 0.5 * cm))

    # ── Description ───────────────────────────────────────────────────────────
    elements.append(section_header("Original Description"))
    elements.append(Spacer(1, 0.2 * cm))
    body_style = ParagraphStyle("body", parent=styles["Normal"], fontSize=10, textColor=TEXT_DARK,
                                leading=15, leftIndent=6, rightIndent=6)
    desc_table = Table([[Paragraph(description, body_style)]], colWidths=[17 * cm])
    desc_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), WHITE),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    elements.append(desc_table)
    elements.append(Spacer(1, 0.5 * cm))

    # ── AI Enhanced Section ───────────────────────────────────────────────────
    elements.append(section_header("AI-Enhanced Description"))
    elements.append(Spacer(1, 0.2 * cm))
    ai_bg = colors.HexColor("#F0FDF4") if ai_status == "valid" else colors.HexColor("#FFFBEB")
    ai_border = SUCCESS_GREEN if ai_status == "valid" else WARNING_ORANGE

    ai_desc_text = improved_description or "Not available."
    ai_desc_table = Table([[Paragraph(ai_desc_text, body_style)]], colWidths=[17 * cm])
    ai_desc_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ai_bg),
        ("BOX", (0, 0), (-1, -1), 1.5, ai_border),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    elements.append(ai_desc_table)
    elements.append(Spacer(1, 0.5 * cm))

    # ── AI Feedback ───────────────────────────────────────────────────────────
    elements.append(section_header("AI Validation Feedback"))
    elements.append(Spacer(1, 0.2 * cm))

    feedback_rows = [
        [Paragraph("Budget Feedback", label_style), Paragraph(budget_feedback or "N/A", value_style)],
        [
            Paragraph("Missing Fields", label_style),
            Paragraph(
                ", ".join(missing_fields) if missing_fields else "None — request appears complete.",
                value_style,
            ),
        ],
        [
            Paragraph("Validation Status", label_style),
            Paragraph(
                status_label,
                ParagraphStyle("sfb", parent=value_style, textColor=status_colour, fontName="Helvetica-Bold"),
            ),
        ],
    ]
    feedback_table = Table(feedback_rows, colWidths=[4.5 * cm, 12.5 * cm])
    feedback_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(feedback_table)
    elements.append(Spacer(1, 1 * cm))

    # ── Footer ────────────────────────────────────────────────────────────────
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CBD5E1")))
    elements.append(Spacer(1, 0.2 * cm))
    footer_style = ParagraphStyle("footer", parent=styles["Normal"], fontSize=8, textColor=TEXT_MUTED,
                                  alignment=TA_CENTER)
    elements.append(Paragraph(
        f"Generated by {settings.app_name} &nbsp;|&nbsp; {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} &nbsp;|&nbsp; CONFIDENTIAL",
        footer_style,
    ))

    doc.build(elements)
    logger.info("PDF generated: %s", file_path)
    return str(file_path)
