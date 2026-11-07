# Évaluation du matching

> **Document historique.** Sortie du 2026-10-30 produite avec un serveur LLM factice par un script
> qui n'est pas livré dans ce dépôt. Elle n'est donc ni reproductible ici ni une preuve de la
> qualité d'un modèle réel. Les preuves reproductibles sont dans `tests/` (voir `TEST_PLAN.md`).

Généré le 2026-10-30 — fournisseur `ollama`, modèle `stub`, 3 exécution(s) par candidat.

> **Attention** : `LLM_BASE_URL` est défini (serveur factice). Ces chiffres valident le code (parsing, validation, scoring, workflow), **pas la qualité d'un modèle réel**.

## Classement par offre

### python_backend
- Attendu : amina_excellente > youssef_partiel
- Obtenu : amina_excellente > youssef_partiel
- Tau de Kendall : 1.00 ; top-1 correct : True

| Candidat | Score moyen |
|---|---|
| amina_excellente | 100.0 |
| youssef_partiel | 63.3 |

### data_analyst
- Attendu : sarah_incoherente > ines_faible > karim_hors_sujet
- Obtenu : sarah_incoherente > ines_faible > karim_hors_sujet
- Tau de Kendall : 1.00 ; top-1 correct : True

| Candidat | Score moyen |
|---|---|
| sarah_incoherente | 89.7 |
| ines_faible | 28.3 |
| karim_hors_sujet | 12.5 |

## Vérification documentaire
- Incohérence volontaire détectée : True
- Faux positifs : aucun

## Stabilité
- Écart-type maximal des scores entre exécutions : 0.00
