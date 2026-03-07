"""Generates user-friendly adherence reports in two formats:

1. **WhatsApp message** — a nicely formatted text summary using WhatsApp
   bold/italic markup that can be sent directly to the user.
2. **PDF file** — a downloadable report the user can save/share,
   sent as a WhatsApp document attachment.
"""

import os
import uuid
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ── Directory where generated PDFs are stored ──
REPORTS_DIR = Path(os.getenv("REPORTS_DIR", "/tmp/remindam_reports"))
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _progress_bar(percentage: float, length: int = 10) -> str:
    """Return a text-based progress bar for WhatsApp messages."""
    filled = round(percentage / 100 * length)
    empty = length - filled
    return "▓" * filled + "░" * empty


def format_whatsapp_report(
    *,
    user_name: str,
    report_type: str,
    period_start: datetime,
    period_end: datetime,
    total_reminders: int,
    taken_count: int,
    missed_count: int,
    adherence_percentage: float,
    medication_breakdown: list[dict] | None = None,
) -> str:
    """Build a clean WhatsApp message for the adherence report.

    WhatsApp supports: *bold*, _italic_, ~strikethrough~, ```monospace```
    """
    bar = _progress_bar(adherence_percentage)

    # Header
    lines = [
        f"📊 *{report_type.capitalize()} Adherence Report*",
        f"_{period_start.strftime('%b %d')} – {period_end.strftime('%b %d, %Y')}_",
        "",
        f"Hello *{user_name}*, here's your medication consistency summary:",
        "",
        f"*Adherence Score:* {adherence_percentage:.0f}%",
        f"{bar}",
        "",
        f"✅ Taken: *{taken_count}* / {total_reminders}",
        f"❌ Missed: *{missed_count}* / {total_reminders}",
    ]

    # Per-medication breakdown (if available)
    if medication_breakdown:
        lines.extend(["", "📋 *Breakdown by Medication:*"])
        for med in medication_breakdown:
            med_bar = _progress_bar(med.get("adherence", 0), length=6)
            lines.append(
                f"  • {med['name']} ({med['form']}): "
                f"{med.get('adherence', 0):.0f}% {med_bar}"
            )

    # Footer
    if adherence_percentage >= 90:
        emoji = "🏆"
        message = "Excellent consistency! Keep it up!"
    elif adherence_percentage >= 70:
        emoji = "👍"
        message = "Good job! A little more consistency and you'll be perfect."
    elif adherence_percentage >= 50:
        emoji = "💪"
        message = "You're getting there — try setting extra alarms for missed doses."
    else:
        emoji = "⚠️"
        message = "Your adherence is low. Missing medication can affect your health."

    lines.extend(["", f"{emoji} _{message}_"])

    return "\n".join(lines)


def generate_pdf_report(
    *,
    user_name: str,
    report_type: str,
    period_start: datetime,
    period_end: datetime,
    total_reminders: int,
    taken_count: int,
    missed_count: int,
    adherence_percentage: float,
    medication_breakdown: list[dict] | None = None,
) -> str:
    """Generate a clean PDF report and return the file path.

    The PDF is stored in ``REPORTS_DIR`` with a unique filename.
    """
    filename = f"remindam_report_{uuid.uuid4().hex[:8]}.pdf"
    filepath = str(REPORTS_DIR / filename)

    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontSize=20,
        textColor=colors.HexColor("#1a73e8"),
        spaceAfter=6 * mm,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.grey,
        spaceAfter=4 * mm,
    )
    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=colors.HexColor("#333333"),
        spaceBefore=6 * mm,
        spaceAfter=3 * mm,
    )
    body_style = ParagraphStyle(
        "BodyText",
        parent=styles["Normal"],
        fontSize=11,
        leading=16,
    )

    elements = []

    # ── Title ──
    elements.append(Paragraph("Remindam", title_style))
    elements.append(
        Paragraph(f"{report_type.capitalize()} Adherence Report", subtitle_style)
    )
    period_str = (
        f"{period_start.strftime('%B %d')} – {period_end.strftime('%B %d, %Y')}"
    )
    elements.append(Paragraph(f"Patient: {user_name}", body_style))
    elements.append(Paragraph(f"Period: {period_str}", body_style))
    elements.append(Spacer(1, 4 * mm))
    elements.append(
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e0e0e0"))
    )
    elements.append(Spacer(1, 4 * mm))

    # ── Summary table ──
    elements.append(Paragraph("Overview", heading_style))

    summary_data = [
        ["Metric", "Value"],
        ["Total Reminders", str(total_reminders)],
        ["Taken", str(taken_count)],
        ["Missed", str(missed_count)],
        ["Adherence Score", f"{adherence_percentage:.1f}%"],
    ]

    table = Table(summary_data, colWidths=[8 * cm, 6 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a73e8")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 8),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#f8f9fa")],
                ),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e0e0e0")),
            ]
        )
    )
    elements.append(table)
    elements.append(Spacer(1, 6 * mm))

    # ── Per-medication breakdown ──
    if medication_breakdown:
        elements.append(Paragraph("Medication Breakdown", heading_style))

        med_data = [["Medication", "Form", "Taken", "Missed", "Score"]]
        for med in medication_breakdown:
            med_data.append(
                [
                    med["name"],
                    med.get("form", "—"),
                    str(med.get("taken", 0)),
                    str(med.get("missed", 0)),
                    f"{med.get('adherence', 0):.0f}%",
                ]
            )

        med_table = Table(
            med_data, colWidths=[5 * cm, 3 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm]
        )
        med_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#34a853")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("ALIGN", (2, 0), (-1, -1), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#f8f9fa")],
                    ),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e0e0e0")),
                ]
            )
        )
        elements.append(med_table)
        elements.append(Spacer(1, 6 * mm))

    # ── Encouragement note ──
    if adherence_percentage >= 90:
        note = (
            "🏆 Excellent consistency! "
            "You're doing a great job sticking to your schedule."
        )
    elif adherence_percentage >= 70:
        note = "👍 Good progress! A bit more consistency and you'll be at 100%."
    elif adherence_percentage >= 50:
        note = (
            "💪 You're getting there. "
            "Try setting additional reminders for the doses you tend to miss."
        )
    else:
        note = (
            "⚠️ Your adherence is low. Please consult your healthcare provider "
            "if you're having trouble with your medication."
        )

    elements.append(
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e0e0e0"))
    )
    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph(note, body_style))
    elements.append(Spacer(1, 6 * mm))

    # ── Footer ──
    footer_style = ParagraphStyle(
        "Footer",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.grey,
    )
    elements.append(
        Paragraph(
            f"Generated by Remindam · "
            f"{datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
            footer_style,
        )
    )

    doc.build(elements)
    return filepath
