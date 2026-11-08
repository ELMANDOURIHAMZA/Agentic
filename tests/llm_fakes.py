"""Transport LLM simulé, respectant les contrats des cinq agents (aucun réseau)."""

import json
import re
import threading
from collections.abc import Callable
from typing import Any

from app.agents.matching import expected_criteria_ids
from app.schemas.agent_outputs import StructuredRequirementsOut

Handler = Callable[[dict[str, Any]], Any]


def schema_name(request: dict[str, Any]) -> str:
    return str(request["schema"].get("title", ""))


def between(text: str, tag: str) -> str:
    start = text.index(f"<{tag}>") + len(tag) + 2
    return text[start : text.index(f"</{tag}>", start)].strip()


class FakeLLM:
    """Transport scripté. ``overrides`` remplace la réponse d'un schéma donné."""

    def __init__(self, overrides: dict[str, Handler | str | Exception] | None = None) -> None:
        self.overrides = overrides or {}
        self.calls: list[tuple[str, float, float]] = []
        self.lock = threading.Lock()
        self.barrier: threading.Barrier | None = None
        self.report_delay = 0.0

    def __call__(self, provider: str, request: dict[str, Any], timeout: float) -> Any:
        name = schema_name(request)
        import time

        started = time.monotonic()
        if self.barrier is not None and name in {
            "StructuredRequirementsOut",
            "ExtractedProfileOut",
        }:
            self.barrier.wait(timeout=5)
        try:
            override = self.overrides.get(name)
            if isinstance(override, Exception):
                raise override
            if isinstance(override, str):
                return override
            if name == "ReportOut" and self.report_delay:
                time.sleep(self.report_delay)
            payload = override(request) if override else self.default(name, request)
            return json.dumps(payload)
        finally:
            with self.lock:
                self.calls.append((name, started, time.monotonic()))

    @staticmethod
    def default(name: str, request: dict[str, Any]) -> dict[str, Any]:
        text = request["input"]
        if name == "StructuredRequirementsOut":
            return {}
        if name == "ExtractedProfileOut" and "FORMATION :" in text:
            return parse_cv(text)
        if name == "VerificationExtractionOut" and "N° CIN" in text:
            return parse_documents(text)
        if name == "ExtractedProfileOut":
            return {
                "education": ["Master en informatique, Université Atlas, 2020"],
                "diplomas": ["Master en informatique 2020"],
                "experiences": [
                    {"position": "Développeur", "employer": "Atlas Soft", "duration_months": 48}
                ],
                "skills": ["Python", "FastAPI", "PostgreSQL"],
                "languages": ["Français", "Anglais"],
                "declared_identity": {"first_name": "Amina", "last_name": "Benali"},
            }
        if name == "VerificationExtractionOut":
            return {
                "first_name": "Amina",
                "last_name": "Benali",
                "diploma_holder_first_name": "Amina",
                "diploma_holder_last_name": "Benali",
                "diploma_title": "Master en informatique",
                "institution": "Université Atlas",
                "graduation_year": 2020,
                "cin_number": "ZZ000000",
            }
        if name == "SemanticEvaluationOut":
            requirements = StructuredRequirementsOut.model_validate_json(between(text, "exigences"))
            profile = between(text, "profil_non_fiable")
            criteria = []
            for identifier in expected_criteria_ids(requirements):
                value = identifier.split(":", 1)[-1]
                diplomas = json.loads(profile).get("diplomas", [])
                if identifier == "degree":
                    wanted = requirements.required_degree.split()[0].casefold()
                    hit = next((d for d in diplomas if wanted in d.casefold()), None)
                    present, evidence = hit is not None, [hit] if hit else []
                else:
                    present, evidence = value.casefold() in profile.casefold(), [value]
                criteria.append(
                    {
                        "name": identifier,
                        "verdict": "match" if present else "absent",
                        "justification": "Simulé.",
                        "evidence": evidence if present else [],
                    }
                )
            return {"criteria": criteria}
        if name == "ReportOut":
            matching = json.loads(between(text, "matching"))
            verification = json.loads(between(text, "verification"))
            return {
                "strengths": ["Profil cohérent avec l'offre."],
                "gaps": matching["missing_skills"],
                "inconsistencies": [
                    f"{i['field']}: {i['cv_value']} / {i['document_value']}"
                    for i in verification["inconsistencies"]
                ],
                "criteria": matching["criteria"],
                "conclusion": "Synthèse neutre fondée sur les résultats fournis.",
            }
        raise AssertionError(f"Schéma inattendu: {name}")


def _field(text: str, label: str) -> str | None:
    match = re.search(rf"{re.escape(label)}\s*:\s*(.+)", text)
    return match.group(1).strip() if match else None


def parse_cv(text: str) -> dict[str, Any]:
    """Lit un CV fictif du jeu de démonstration (le vrai LLM fait ce travail en production)."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    name_line = next(
        line for line in lines if re.fullmatch(r"[A-ZÉ][a-zéèï]+ [A-ZÉ][a-zéèï]+", line)
    )
    first, _, last = name_line.partition(" ")
    education = _field(text, "FORMATION")
    experience = _field(text, "EXPÉRIENCE")
    out: dict[str, Any] = {
        "education": [education] if education else [],
        "diplomas": [education.split(",")[0] + " " + education.split(",")[-1].strip()]
        if education
        else [],
        "skills": [s.strip() for s in (_field(text, "COMPÉTENCES") or "").split(",") if s.strip()],
        "languages": [s.strip() for s in (_field(text, "LANGUES") or "").split(",") if s.strip()],
        "declared_identity": {"first_name": first, "last_name": last},
    }
    if experience:
        position, employer, duration = [part.strip() for part in experience.split(",")]
        out["experiences"] = [
            {
                "position": position,
                "employer": employer,
                "duration_months": int(duration.split()[0]),
            }
        ]
    return out


def parse_documents(text: str) -> dict[str, Any]:
    diploma = between(text, "document_diplome")
    cin = between(text, "document_cin")
    return {
        "first_name": _field(cin, "Prénom"),
        "last_name": _field(cin, "Nom"),
        "birth_date": _field(cin, "Date de naissance"),
        "cin_number": _field(cin, "N° CIN"),
        "diploma_holder_first_name": _field(diploma, "Prénom"),
        "diploma_holder_last_name": _field(diploma, "Nom"),
        "diploma_title": _field(diploma, "a obtenu le diplôme"),
        "institution": _field(diploma, "Établissement"),
        "graduation_year": int(_field(diploma, "Année d'obtention") or 0) or None,
    }
