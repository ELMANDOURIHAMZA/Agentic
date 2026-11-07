# Agentic AI Recruitment Platform

Mini-projet universitaire indépendant « Mini-projet 2 Agentic AI ».

## Présentation

Cette application FastAPI propose un parcours de recrutement : offres
publiques, candidatures avec documents, espace candidat, espace administrateur,
cinq agents spécialisés et un orchestrateur traçable. Le score est une aide à
la décision ; la décision finale reste humaine.

## Fonctionnalités présentes

- authentification candidat/admin, sessions signées, Argon2 et CSRF ;
- création, publication et clôture d'offres par l'administrateur ;
- site public avec recherche d'offres ;
- candidatures avec CV, diplôme et CIN déposés par le candidat, validation de fichiers et
  téléchargement protégé ;
- notifications email SMTP configurables ;
- espace candidat et vue candidat limitée ;
- agents d'exigences, extraction CV, vérification documentaire, matching et
  rapport ;
- orchestrateur avec étapes, statuts, logs, relance et récupération des runs
  abandonnés ;
- espace admin des candidatures avec lancement explicite, polling et rapports ;
- import local de CV depuis une archive dataset, sans copie des données dans Git ;
- modification d'une offre brouillon ou publiée (pas clôturée) ;
- bonus : classement des candidats par offre (`/admin/jobs/{id}/ranking`),
  tableau de bord statistique (`/admin/dashboard`), export PDF du rapport
  (`/admin/applications/{id}/report.pdf`), traitement par lot, évaluation avec
  vérité terrain, CV en français/anglais/arabe, aucune donnée de genre/âge/photo
  dans le schéma extrait ;
- règle « revue humaine obligatoire » : signalée si la conformité documentaire
  est < 70/100 ou si une incohérence est de gravité élevée (le score n'est pas modifié) ;
- OCR Tesseract pour images et PDF scannés (`OCR_LANGUAGES=fra+eng+ara`,
  paquets `tesseract-ocr tesseract-ocr-fra tesseract-ocr-ara` ; l'image Docker les installe).

## Architecture

```text
Navigateur -> FastAPI/routes -> services -> SQLAlchemy/PostgreSQL
                                 |
                                 +-> orchestrateur -> agents -> LLM injecté
                                 +-> stockage protégé des documents
                                 +-> SMTP optionnel
```

Le détail des flux se trouve dans [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
et [docs/AGENTS.md](docs/AGENTS.md).

## Prérequis

- Python 3.13 exactement (contrainte de [.python-version](.python-version)) ;
- PostgreSQL 16, local ou via Docker ;
- Docker Desktop si la pile conteneurisée est utilisée.

## Installation locale

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Adapter `.env` avec des valeurs locales. En dehors du développement,
`SECRET_KEY` et `POSTGRES_PASSWORD` doivent être remplacés ; l'application
refuse les valeurs d'exemple.

### Variables de configuration

| Variable | Rôle |
|---|---|
| `DATABASE_URL` | URL SQLAlchemy PostgreSQL |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_PORT` | PostgreSQL Docker |
| `SECRET_KEY` | signature des sessions |
| `APP_ENV` | `development`, `test` ou autre environnement |
| `LLM_PROVIDER=groq`, `GROQ_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL` | API Groq uniquement ; modèle hébergé par Groq par défaut `openai/gpt-oss-120b` ; URL personnalisée facultative |
| `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES` | limites d'appel |
| `WORKFLOW_STALE_TIMEOUT_SECONDS` | délai de récupération d'un run abandonné |
| `WORKFLOW_BATCH_CONCURRENCY` | nombre maximal de candidatures traitées simultanément (1 à 8, défaut 3) |
| `MATCHING_*_WEIGHT` | six pondérations du score, total 100 |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_STARTTLS` | notifications |
| `ADMIN_NOTIFICATION_EMAIL` | destinataire admin |
| `UPLOAD_DIR`, `MAX_UPLOAD_MB` | stockage et taille des fichiers |
| `APP_PORT` | port publié par Docker |

`.env.example` ne contient aucun secret réel.

## Lancement local

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Pages principales : `/`, `/login`, `/register`, `/admin/jobs`,
`/admin/applications` et `/candidate`.

Créer un administrateur :

```powershell
$env:ADMIN_EMAIL = "admin@example.test"
$env:ADMIN_PASSWORD = "Choisir-Un-Mot-De-Passe-Local!123"
.\.venv\Scripts\python.exe -m app.cli create-admin
```

## Lancement Docker

Configurer `.env`, puis :

```powershell
docker compose build
docker compose up -d
docker compose ps
curl http://127.0.0.1:8000/health
docker compose down
```

Le conteneur applicatif exécute `alembic upgrade head` avant Uvicorn. Les
uploads sont conservés dans le volume `recruitment_uploads`. La base et ce
volume ne sont pas supprimés par `docker compose down`.

## Dataset fictif de démonstration

Après l'installation locale et l'application des migrations, générer le jeu de
données demandé (2 offres publiées, 5 candidats, 5 candidatures en attente et
15 documents fictifs (14 PDF et 1 CV DOCX en arabe)) :

```powershell
.\\.venv\\Scripts\\python.exe -m scripts.seed_demo_data
```

Le script est réexécutable : il remplace les précédents comptes/offres marqués
comme données de démonstration. Les documents générés sont stockés dans
`UPLOAD_DIR`, pas dans Git. Aucun workflow IA n'est déclenché par le seed ;
l'administrateur doit toujours cliquer sur « Lancer le traitement ».

Comptes candidats de démonstration (mot de passe commun) :

| Candidat | Email |
|---|---|
| Amina Benali | `amina.benali@example.test` |
| Youssef Berrada | `youssef.berrada@example.test` |
| Karim El Idrissi | `karim.elidrissi@example.test` |
| Sarah Bennani | `sarah.bennani@example.test` |
| Ines Amrani | `ines.amrani@example.test` |

Mot de passe : `Demo-Candidate-2026!`. Ces comptes sont réservés à la
démonstration locale ; ne pas réutiliser ce mot de passe en production.
Le dossier de Sarah contient une incohérence volontaire entre le nom du CV/CIN
et celui du titulaire figurant sur le diplôme.

## Données de livraison académique

La livraison académique n'embarque aucun CV, diplôme ou CIN réel. Les archives
personnelles et les offres externes sont conservées hors du workspace de
livraison. Les commandes d'import et de benchmark de données personnelles ne
font pas partie de l'interface CLI livrée.

## Règle de déclenchement IA

**Aucune analyse IA n'est exécutée sans clic explicite de l'administrateur sur
« Lancer le traitement » ou « Relancer ».** Une candidature confirmée par le
candidat reste `PENDING`. Une configuration LLM invalide est refusée avant le
passage à `PROCESSING`.

## Tests et qualité

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m alembic current
docker compose config
```

Les tests unitaires du transport Groq utilisent un faux serveur HTTP et ne
consomment aucun quota. Les tests marqués `integration` effectuent de vrais
appels à Groq uniquement lorsque `RUN_REAL_LLM_TESTS=1` et `GROQ_API_KEY` sont
définis. Ils peuvent consommer du quota Groq.
Ne jamais placer la clé dans Git ou dans les logs.

## Structure

```text
app/agents/       cinq agents et prompts
app/api/          routes publiques, candidat et admin
app/models/       modèles SQLAlchemy
app/orchestration workflow et récupération des runs
app/services/     stockage, lecture, emails et client LLM
app/services/llm.py client HTTP Groq réel
migrations/       Alembic
scripts/          outils de maintenance non métier
tests/            tests unitaires, intégration et sécurité
docs/             architecture, sécurité, démonstration et plan de test
```

## Intégration LLM Groq réelle

Le projet utilise exclusivement l'API Chat Completions de Groq. Le modèle par défaut `openai/gpt-oss-120b` est hébergé par Groq : le nom du modèle ne signifie pas que le service OpenAI est appelé. Définir `GROQ_API_KEY` dans le fichier `.env` local (ne jamais la commiter) et `LLM_PROVIDER=groq`. Le modèle reste configurable avec `LLM_MODEL`.

Les tests d'intégration sont opt-in et appellent directement Groq :

```powershell
$env:RUN_REAL_LLM_TESTS="1"
$env:LLM_PROVIDER="groq"
.\.venv\Scripts\python.exe -m pytest -m integration
```

Cette commande consomme le quota du compte Groq. Les tests unitaires ne font
aucun appel réseau. Aucun CV réel n'est inclus dans le workspace de livraison.

## Limites connues

L'OCR dépend de Tesseract installé sur la machine (sinon un scan est signalé illisible).
L'ordre des scores peut varier avec un vrai LLM. La limitation de tentatives de connexion est en
mémoire. Les emails ne sont pas relancés automatiquement après un crash. La
recherche accent-insensible est en mémoire. Les preuves du matching doivent
être présentes dans le texte du profil (comparaison insensible à la casse et aux
accents). Aucun appel à Groq n'est effectué par les tests unitaires sans activation explicite des tests d'intégration.
Les langues sont comptées dans `matching_skills`/`missing_skills`.
