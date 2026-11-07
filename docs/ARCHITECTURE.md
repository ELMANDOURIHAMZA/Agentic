# Architecture et diagrammes

## Cas d'utilisation

```mermaid
flowchart LR
  C[Candidat] --> P[Consulter les offres]
  C --> A[Déposer une candidature]
  C --> V[Consulter sa vue limitée]
  AD[Administrateur] --> J[Gérer les offres]
  AD --> T[Lancer ou relancer le traitement]
  AD --> R[Consulter rapport et logs]
  T --> W[Orchestrateur]
  W --> X[Analyse des 5 agents]
```

## Modèle de données

```mermaid
erDiagram
  USER ||--o{ APPLICATION : submits
  JOB ||--o{ APPLICATION : receives
  APPLICATION ||--o{ DOCUMENT : contains
  JOB ||--o| STRUCTURED_REQUIREMENTS : has
  APPLICATION ||--o| EXTRACTED_PROFILE : produces
  APPLICATION ||--o| DOCUMENT_VERIFICATION : produces
  APPLICATION ||--o| ANALYSIS_RESULT : produces
  APPLICATION ||--o{ WORKFLOW_RUN : executes
  WORKFLOW_RUN ||--o{ WORKFLOW_STEP_LOG : records
```

## Workflow de bout en bout

```mermaid
sequenceDiagram
  participant A as Admin
  participant API as Route admin
  participant DB as PostgreSQL
  participant W as Orchestrateur
  participant L as Agents/LLM
  A->>API: clic Lancer le traitement
  API->>DB: verrouiller et passer PROCESSING
  API-->>A: redirection immédiate
  API->>W: tâche de fond run_batch
  W->>L: agents 1 et 2 en parallèle
  W->>L: agent 3 vérification
  W->>L: agent 4 matching
  W->>L: agent 5 rapport
  W->>DB: sorties, logs, COMPLETED
```

## Cinq agents et dépendances

```mermaid
flowchart TD
  A1[1 Exigences offre] --> A4[4 Matching]
  A2[2 Extraction CV] --> A3[3 Vérification documents]
  A2 --> A4
  A3 --> A4
  A1 --> A5[5 Rapport]
  A2 --> A5
  A3 --> A5
  A4 --> A5
```

Agents 1 et 2 sont concurrents ; les autres suivent l'ordre imposé.
