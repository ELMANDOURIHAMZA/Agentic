# Plan de test

Les tests couvrent les modèles et transitions, authentification, CSRF et rôles, offres publiques
et admin, candidatures et documents, emails, espace candidat, **chacun des cinq agents**,
l'orchestrateur complet (`ApplicationWorkflow`), la concurrence, la récupération des runs
abandonnés et orphelins, la migration round-trip et les protections XSS et secrets.

Les agents et le workflow sont exécutés avec un **transport LLM simulé** (`tests/llm_fakes.py`),
ce qui rend la suite déterministe, sans réseau ni clé. Les tests d'intégration avec un vrai
fournisseur sont opt-in (`RUN_REAL_LLM_TESTS=1`) et n'ont **pas** été exécutés lors de la remise
en conformité.

| Scénario du cahier | Test |
|---|---|
| Offre créée, publiée, visible | `test_admin_jobs.py`, `test_public_jobs.py` |
| Compte, connexion, candidature complète | `test_auth.py`, `test_applications.py` |
| Statut « En attente », aucune analyse automatique | `test_complete_application_is_pending_without_workflow` |
| Déclenchement manuel | `test_real_http_workflow.py` |
| Cinq agents et sorties JSON | `test_*_agent.py`, `test_workflow_integration.py` |
| Incohérence volontaire détectée | `test_voluntary_inconsistency_is_detected_and_flagged` |
| Score reproductible et justifié | `test_matching_agent.py` |
| Isolation candidats, rapport réservé admin | `test_candidate_sees_real_compliance_but_never_inconsistency_details` |
| Erreur d'agent, relance, double exécution | `test_agent_failure_sets_error_status_logs_and_allows_retry`, `test_double_execution_is_prevented` |
| Exécution asynchrone, lot parallèle borné | `test_agents_1_and_2_run_in_parallel...`, `test_batch_runs_with_bounded_parallelism...` |
| Emails | `test_email_service.py` |
| Fichiers invalides | `test_applications.py` |
| Reproductibilité de l'installation | `test_migrations_roundtrip.py`, seed idempotent |

Non couverts automatiquement : interface dans un navigateur, responsive, Docker `build`/`up`,
SMTP et LLM réels. Voir `docs/RAPPORT_TECHNIQUE.md` sections 14 et 16.

## Captures d'écran à réaliser

1. Accueil public avec les offres.
2. Détail d'une offre.
3. Assistant de candidature.
4. Confirmation candidat en `PENDING`.
5. Liste admin des candidatures.
6. Liste admin en `PROCESSING`.
7. Résultat admin `COMPLETED`.
8. Détail admin du cas incohérent.
9. Vue candidat limitée sans rapport ni incohérences.
10. Écran admin `ERROR` avec bouton « Relancer ».
