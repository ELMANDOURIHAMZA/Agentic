"""Données de démonstration 100 % fictives : offres, candidats, CV, diplômes et CIN.

Aucune donnée réelle : noms inventés, adresses ``@example.test``, numéros de CIN
visiblement factices (``ZZ`` + chiffres) et mention « SPÉCIMEN FICTIF » sur chaque
document. Les PDF sont générés par du code (reportlab) : rien de personnel n'est versionné.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

FICTIVE = "SPÉCIMEN FICTIF - donnée de démonstration"


@dataclass(frozen=True)
class DemoJob:
    key: str
    title: str
    description: str
    required_degree: str
    required_experience_years: int
    required_skills: list[str]
    preferred_skills: list[str]
    languages: list[str]
    location: str
    other_requirements: str = ""


@dataclass(frozen=True)
class DemoCandidate:
    key: str
    first_name: str
    last_name: str
    job_key: str
    cv_lines: list[str]
    diploma_title: str
    diploma_year: int
    institution: str
    cin_number: str
    # Écarts volontaires (None = cohérent avec l'identité du candidat)
    diploma_holder: tuple[str, str] | None = None
    scenario: str = ""
    phone: str = "+212600000000"
    email: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "email", f"{self.key}@example.test")


JOBS: list[DemoJob] = [
    DemoJob(
        key="backend",
        title="Développeur Backend Python (démo)",
        description=(
            "Conception d'API REST avec Python et FastAPI, base PostgreSQL, "
            "déploiement conteneurisé. Travail en équipe agile."
        ),
        required_degree="Master en informatique",
        required_experience_years=3,
        required_skills=["Python", "FastAPI", "PostgreSQL"],
        preferred_skills=["Docker", "Redis"],
        languages=["Français", "Anglais"],
        location="Rabat",
        other_requirements="Esprit d'équipe, rigueur.",
    ),
    DemoJob(
        key="analyst",
        title="Data Analyst (démo, sans diplôme exigé)",
        description=(
            "Analyse de données de ventes, tableaux de bord et reporting. "
            "Aucun diplôme particulier n'est exigé."
        ),
        required_degree="",
        required_experience_years=1,
        required_skills=["SQL", "Power BI", "Excel"],
        preferred_skills=["Python"],
        languages=["Français"],
        location="Casablanca",
    ),
]

CANDIDATES: list[DemoCandidate] = [
    DemoCandidate(
        key="amina.benali",
        first_name="Amina",
        last_name="Benali",
        job_key="backend",
        scenario="Profil très proche de l'offre, dossier cohérent.",
        diploma_title="Master en informatique",
        diploma_year=2019,
        institution="Université Atlas (fictive)",
        cin_number="ZZ000001",
        cv_lines=[
            "Amina Benali",
            "Développeuse backend",
            "FORMATION : Master en informatique, Université Atlas (fictive), 2019",
            "EXPÉRIENCE : Développeuse Python, Atlas Soft, 48 mois",
            "COMPÉTENCES : Python, FastAPI, PostgreSQL, Docker, Redis",
            "LANGUES : Français, Anglais",
        ],
    ),
    DemoCandidate(
        key="youssef.tazi",
        first_name="Youssef",
        last_name="Tazi",
        job_key="backend",
        scenario="Profil partiel : Python et SQL seulement, expérience courte.",
        diploma_title="Licence en informatique",
        diploma_year=2022,
        institution="Faculté Horizon (fictive)",
        cin_number="ZZ000002",
        cv_lines=[
            "Youssef Tazi",
            "Développeur junior",
            "FORMATION : Licence en informatique, Faculté Horizon (fictive), 2022",
            "EXPÉRIENCE : Développeur Python, Start Demo, 12 mois",
            "COMPÉTENCES : Python, SQL, Git",
            "LANGUES : Français",
        ],
    ),
    DemoCandidate(
        key="salma.idrissi",
        first_name="Salma",
        last_name="Idrissi",
        job_key="analyst",
        scenario="Profil analyste complet, dossier cohérent.",
        diploma_title="Licence en statistiques",
        diploma_year=2020,
        institution="Institut Delta (fictif)",
        cin_number="ZZ000003",
        cv_lines=[
            "Salma Idrissi",
            "Analyste de données",
            "FORMATION : Licence en statistiques, Institut Delta (fictif), 2020",
            "EXPÉRIENCE : Analyste, Commerce Demo, 30 mois",
            "COMPÉTENCES : SQL, Power BI, Excel, Python",
            "LANGUES : Français, Anglais",
        ],
    ),
    DemoCandidate(
        key="omar.fassi",
        first_name="Omar",
        last_name="Fassi",
        job_key="analyst",
        scenario="Profil faible : seulement Excel, dossier cohérent.",
        diploma_title="Baccalauréat sciences économiques",
        diploma_year=2021,
        institution="Lycée Zénith (fictif)",
        cin_number="ZZ000004",
        cv_lines=[
            "Omar Fassi",
            "Assistant administratif",
            "FORMATION : Baccalauréat sciences économiques, Lycée Zénith (fictif), 2021",
            "EXPÉRIENCE : Assistant, Bureau Demo, 8 mois",
            "COMPÉTENCES : Excel, Word",
            "LANGUES : Français",
        ],
    ),
    DemoCandidate(
        key="karim.alaoui",
        first_name="Karim",
        last_name="Alaoui",
        job_key="backend",
        scenario=(
            "INCOHÉRENCE VOLONTAIRE : diplôme au nom d'une autre personne "
            "(Mehdi Chraibi) et année contradictoire (CV 2018, diplôme 2011)."
        ),
        diploma_title="Master en informatique",
        diploma_year=2011,
        institution="Université Atlas (fictive)",
        cin_number="ZZ000005",
        diploma_holder=("Mehdi", "Chraibi"),
        cv_lines=[
            "Karim Alaoui",
            "Ingénieur logiciel",
            "FORMATION : Master en informatique, Université Atlas (fictive), 2018",
            "EXPÉRIENCE : Développeur Python, Delta Soft, 60 mois",
            "COMPÉTENCES : Python, FastAPI, PostgreSQL, Docker",
            "LANGUES : Français, Anglais",
        ],
    ),
]


def _pdf(lines: list[str], title: str) -> bytes:
    stream = io.BytesIO()
    document = canvas.Canvas(stream, pagesize=A4, invariant=1)
    document.setTitle(title)
    document.setFont("Helvetica-Bold", 14)
    document.drawString(56, 790, title)
    document.setFont("Helvetica", 11)
    y = 760
    for line in [*lines, "", FICTIVE]:
        document.drawString(56, y, line)
        y -= 20
    document.save()
    return stream.getvalue()


def cv_pdf(candidate: DemoCandidate) -> bytes:
    return _pdf(candidate.cv_lines, "CURRICULUM VITAE")


def diploma_pdf(candidate: DemoCandidate) -> bytes:
    first, last = candidate.diploma_holder or (candidate.first_name, candidate.last_name)
    return _pdf(
        [
            "Il est certifié que :",
            f"Prénom : {first}",
            f"Nom : {last}",
            f"a obtenu le diplôme : {candidate.diploma_title}",
            f"Établissement : {candidate.institution}",
            f"Année d'obtention : {candidate.diploma_year}",
        ],
        "DIPLÔME",
    )


def cin_pdf(candidate: DemoCandidate) -> bytes:
    return _pdf(
        [
            "ROYAUME DE DÉMONSTRATION - CARTE NATIONALE D'IDENTITÉ",
            f"Prénom : {candidate.first_name}",
            f"Nom : {candidate.last_name}",
            "Date de naissance : 01/01/1990 (fictive)",
            f"N° CIN : {candidate.cin_number}",
        ],
        "CIN",
    )


def documents_for(candidate: DemoCandidate) -> dict[str, bytes]:
    return {"cv": cv_pdf(candidate), "diploma": diploma_pdf(candidate), "cin": cin_pdf(candidate)}
