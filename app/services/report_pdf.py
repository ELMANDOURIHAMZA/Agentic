"""Export PDF du rapport détaillé (réservé à l'administrateur)."""

from datetime import datetime
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.services.presentation import criterion_label, format_score, severity_label


def _p(text: object, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(str(text)), style)


def _bullets(items: list[str], style: ParagraphStyle) -> list[Paragraph]:
    return [_p(f"• {item}", style) for item in items] or [_p("—", style)]


def build_report_pdf(
    *,
    candidate_name: str,
    job_title: str,
    status_label: str,
    global_score: float,
    score_details: dict[str, Any],
    matching_skills: list[str],
    missing_skills: list[str],
    verification: dict[str, Any] | None,
    report: dict[str, Any] | None,
    review_reasons: list[str],
    generated_at: datetime,
) -> bytes:
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9.5, leading=13)
    small = ParagraphStyle("small", parent=body, fontSize=8.5, leading=11)
    h1 = ParagraphStyle("h1", parent=styles["Title"], fontSize=18)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12, spaceBefore=10)
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=f"Rapport - {candidate_name}",
        author="Agentic AI Recruitment Platform",
    )
    story: list[Any] = [
        _p("Rapport d'analyse de candidature", h1),
        _p(f"Candidat : {candidate_name}", body),
        _p(f"Poste : {job_title}", body),
        _p(f"Statut : {status_label}", body),
        _p(f"Score global : {format_score(global_score)} / 100", body),
        _p(f"Généré le {generated_at:%d/%m/%Y %H:%M} UTC", small),
    ]
    if review_reasons:
        story += [Spacer(1, 6), _p("REVUE HUMAINE OBLIGATOIRE", h2)]
        story += _bullets(review_reasons, body)

    story.append(_p("Détail du score", h2))
    rows: list[list[Any]] = [["Critère", "Score", "Poids", "Justification"]]
    for name, detail in score_details.items():
        rows.append(
            [
                _p(criterion_label(name), small),
                format_score(detail.get("score")),
                format_score(detail.get("weight")) + " %",
                _p(detail.get("justification", ""), small),
            ]
        )
    table = Table(rows, colWidths=[4 * cm, 1.6 * cm, 1.8 * cm, 9.6 * cm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9ecef")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ]
        )
    )
    story += [table, _p("Compétences correspondantes", h2)]
    story += _bullets(matching_skills, body)
    story.append(_p("Compétences manquantes", h2))
    story += _bullets(missing_skills, body)

    story.append(_p("Cohérence des documents", h2))
    if verification:
        story.append(_p(f"Niveau de conformité : {verification.get('compliance_level')}/100", body))
        found = verification.get("inconsistencies", [])
        if found:
            for item in found:
                gravity = severity_label(item.get("severity", ""))
                line = (
                    f"• {item.get('field')} (gravité {gravity}) : "
                    f"CV « {item.get('cv_value')} » / document « {item.get('document_value')} »"
                )
                story.append(_p(line, body))
        else:
            story.append(_p("Aucune incohérence détectée.", body))
    else:
        story.append(_p("Vérification non disponible.", body))

    if report:
        story.append(_p("Rapport détaillé", h2))
        story.append(_p("Points forts", body))
        story += _bullets(report.get("strengths", []), body)
        story.append(_p("Manques", body))
        story += _bullets(report.get("gaps", []), body)
        story += [_p("Conclusion", body), _p(report.get("conclusion", ""), body)]
        reminder = report.get("human_decision_reminder", "")
        if reminder and reminder.casefold() not in str(report.get("conclusion", "")).casefold():
            story += [Spacer(1, 8), _p(reminder, small)]
    story += [
        Spacer(1, 10),
        _p(
            "Le score est une aide à la décision : la décision finale de recrutement "
            "appartient toujours à l'humain.",
            small,
        ),
    ]
    doc.build(story)
    return buffer.getvalue()
