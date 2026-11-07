"""Aides d'affichage partagées par l'espace admin, le classement et l'export PDF."""

from typing import Any

CRITERION_LABELS = {
    "required_skills": "Compétences obligatoires",
    "experience": "Expérience",
    "degree": "Diplôme / formation",
    "preferred_skills": "Compétences souhaitées",
    "languages": "Langues",
    "documents": "Cohérence des documents",
}

SEVERITY_LABELS = {"low": "faible", "medium": "moyenne", "high": "élevée"}

# En dessous de ce niveau de conformité, un humain doit relire le dossier.
REVIEW_COMPLIANCE_THRESHOLD = 70.0


def criterion_label(name: str) -> str:
    return CRITERION_LABELS.get(name, name)


def severity_label(value: str) -> str:
    return SEVERITY_LABELS.get(value, value)


def format_score(value: float | int | None) -> str:
    if value is None:
        return "—"
    return f"{float(value):.1f}"


def review_reasons(verification: dict[str, Any] | None) -> list[str]:
    """Raisons pour lesquelles une revue humaine est obligatoire (liste vide sinon).

    Le score reste inchangé (pondération de la fiche) : cette règle empêche seulement
    qu'un dossier à incohérence grave soit retenu sur la seule foi de son rang.
    """
    if not verification:
        return []
    reasons: list[str] = []
    compliance = verification.get("compliance_level")
    if isinstance(compliance, int | float) and compliance < REVIEW_COMPLIANCE_THRESHOLD:
        reasons.append(f"Conformité documentaire faible ({float(compliance):.0f}/100).")
    high = [
        item
        for item in verification.get("inconsistencies", [])
        if isinstance(item, dict) and item.get("severity") == "high"
    ]
    if high:
        fields = ", ".join(sorted({str(item.get("field", "?")) for item in high}))
        reasons.append(f"Incohérence de gravité élevée entre les documents ({fields}).")
    return reasons
