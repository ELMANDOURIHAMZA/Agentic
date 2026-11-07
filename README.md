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
| `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL` | fournisseur LLM (OpenAI recommandé, ou anthropic, gemini, ollama) ; `LLM_BASE_URL` remplace l'URL de base ; aucun appel réseau dans les tests |
| `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES` | limites d'appel |
| `WORKFLOW_STALE_TIMEOUT_SECONDS` | délai de récupération d'un run abandonné |
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

Les tests unitaires couvrent les schémas et les fonctions déterministes sans
fournisseur simulé. Les tests marqués `integration` effectuent de vrais appels
au fournisseur configuré uniquement lorsque `RUN_REAL_LLM_TESTS=1` est défini.
Ne jamais placer la clé dans Git ou dans les logs.

## Structure

```text
app/agents/       cinq agents et prompts
app/api/          routes publiques, candidat et admin
app/models/       modèles SQLAlchemy
app/orchestration workflow et récupération des runs
app/services/     stockage, lecture, emails et client LLM
app/services/llm.py client des fournisseurs LLM réels
migrations/       Alembic
scripts/          outils de maintenance non métier
tests/            tests unitaires, intégration et sécurité
docs/             architecture, sécurité, démonstration et plan de test
```

## Intégration LLM réelle

Les tests d'intégration sont opt-in et utilisent exclusivement le fournisseur
configuré dans les variables d'environnement :

```powershell
$env:RUN_REAL_LLM_TESTS="1"
.\.venv\Scripts\python.exe -m pytest -m integration
```

Cette commande peut consommer du quota fournisseur. Aucun CV réel n'est inclus
dans le workspace de livraison.

## Limites connues

L'OCR dépend de Tesseract installé sur la machine (sinon un scan est signalé illisible).
L'ordre des scores peut varier avec un vrai LLM. La limitation de tentatives de connexion est en
mémoire. Les emails ne sont pas relancés automatiquement après un crash. La
recherche accent-insensible est en mémoire. Les preuves du matching doivent
être présentes dans le texte du profil (comparaison insensible à la casse et aux
accents). Aucun appel à un vrai LLM n'est évalué automatiquement sans clé configurée.
Les langues sont comptées dans `matching_skills`/`missing_skills`.
