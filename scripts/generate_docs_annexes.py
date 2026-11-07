"""Génère docs/annexes/PROMPTS.md et SCHEMAS.md depuis le code (aucune copie manuelle).

Usage : DATABASE_URL=... SECRET_KEY=... python scripts/generate_docs_annexes.py
"""

from __future__ import annotations

import json
from pathlib import Path

from app.agents.cv_extraction import CVExtractionInput
from app.agents.document_verification import DocumentVerificationInput, VerificationExtractionOut
from app.agents.job_requirement import JobRequirementInput
from app.agents.matching import MatchingInput, SemanticEvaluationOut
from app.agents.report import ReportInput
from app.schemas.agent_outputs import (
    DocumentVerificationOut,
    ExtractedProfileOut,
    MatchingOut,
    ReportOut,
    StructuredRequirementsOut,
)

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = [
    ("1 - Job Requirement Agent", "job_requirement_agent.txt"),
    ("2 - CV Extraction Agent", "cv_extraction_agent.txt"),
    ("3 - Document Verification Agent", "document_verification_agent.txt"),
    ("4 - Matching Agent (évaluation sémantique)", "matching_agent.txt"),
    ("5 - Report Agent", "report_agent.txt"),
]
SCHEMAS = [
    ("Agent 1", JobRequirementInput, StructuredRequirementsOut),
    ("Agent 2", CVExtractionInput, ExtractedProfileOut),
    ("Agent 3 (extraction LLM)", DocumentVerificationInput, VerificationExtractionOut),
    ("Agent 3 (sortie finale)", DocumentVerificationInput, DocumentVerificationOut),
    ("Agent 4 (réponse LLM)", MatchingInput, SemanticEvaluationOut),
    ("Agent 4 (sortie finale)", MatchingInput, MatchingOut),
    ("Agent 5", ReportInput, ReportOut),
]


def main() -> None:
    out = ROOT / "docs" / "annexes"
    out.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Annexe A : prompts des agents",
        "",
        "Fichier généré par `scripts/generate_docs_annexes.py` depuis `app/agents/prompts/`.",
        "",
    ]
    for title, name in PROMPTS:
        text = (ROOT / "app" / "agents" / "prompts" / name).read_text(encoding="utf-8").strip()
        lines += [
            f"## Agent {title}",
            "",
            f"Source : `app/agents/prompts/{name}`",
            "",
            "```text",
            text,
            "```",
            "",
        ]
    (out / "PROMPTS.md").write_text("\n".join(lines), encoding="utf-8")

    lines = [
        "# Annexe B : schémas JSON des entrées et sorties",
        "",
        "Fichier généré par `scripts/generate_docs_annexes.py` (Pydantic `model_json_schema`).",
        'Toutes les sorties utilisent `extra="forbid"` : un champ inattendu est rejeté.',
        "",
    ]
    for title, model_in, model_out in SCHEMAS:
        lines += [
            f"## {title}",
            "",
            f"### Entrée : `{model_in.__name__}`",
            "",
            "```json",
            json.dumps(model_in.model_json_schema(), indent=2, ensure_ascii=False),
            "```",
            "",
            f"### Sortie : `{model_out.__name__}`",
            "",
            "```json",
            json.dumps(model_out.model_json_schema(), indent=2, ensure_ascii=False),
            "```",
            "",
        ]
    (out / "SCHEMAS.md").write_text("\n".join(lines), encoding="utf-8")
    print("annexes générées")


if __name__ == "__main__":
    main()
