# Guide de démonstration de bout en bout

Données 100 % fictives. Mot de passe du jeu de démonstration : celui que vous définissez dans
`SEED_PASSWORD` (jamais versionné).

## Préparation

```bash
cp .env.example .env            # adapter SECRET_KEY, POSTGRES_PASSWORD, LLM_*
alembic upgrade head
export SEED_PASSWORD='Choisir-Un-Mot-De-Passe-Demo!2026'
python -m app.cli seed-demo     # idempotent : relancer ne duplique rien
uvicorn app.main:app --reload
```

Le seed crée : 1 administrateur (`admin.demo@example.test`), 2 offres publiées, 5 candidats
(`<prénom>.<nom>@example.test`), 5 candidatures **en attente** et 15 documents fictifs.
`python -m app.cli generate-fixtures` écrit aussi les PDF dans `data/fixtures/` pour les
déposer à la main pendant la démonstration.

| Candidat | Offre | Scénario |
|---|---|---|
| Amina Benali | Backend Python | Profil excellent, dossier cohérent, score attendu élevé |
| Youssef Tazi | Backend Python | Profil partiel : compétences et expérience manquantes |
| Salma Idrissi | Data Analyst (sans diplôme exigé) | Profil complet ; le critère diplôme est exclu du score |
| Omar Fassi | Data Analyst | Profil faible |
| Karim Alaoui | Backend Python | **Incohérence volontaire** : diplôme au nom de « Mehdi Chraibi » et année 2011 au lieu de 2018 |

## Scénario

1. **Public** : ouvrir `/`, rechercher une offre, ouvrir son détail.
2. **Candidat** : cliquer « Postuler », créer un compte, compléter le profil, déposer les trois
   PDF de `data/fixtures/<candidat>/`, confirmer. Statut : « En attente de traitement ».
   Deux emails sont envoyés (vérifier dans Mailtrap ou le serveur SMTP configuré).
3. **Règle bloquante** : constater que rien ne se lance seul. Le statut reste « En attente ».
4. **Admin** : se connecter, ouvrir `/admin/applications`, cocher une ou plusieurs
   candidatures, cliquer « Lancer le traitement ». Le statut passe à « En cours de traitement »
   et la page reste réactive.
5. **Résultats admin** : score global, détail par critère, compétences présentes et manquantes,
   conformité du diplôme, incohérences, rapport complet, logs des cinq étapes.
6. **Cas incohérent** : traiter Karim Alaoui, vérifier les incohérences « titulaire du
   diplôme » et « année » et la mention « Revue humaine obligatoire ».
7. **Vue candidat** : se connecter en candidat, ouvrir le résultat : score, compétences,
   conformité générale. Ni rapport complet ni détail des incohérences.
8. **Isolation** : un candidat qui ouvre la candidature d'un autre reçoit 403/404.
9. **Erreur et relance** : configurer temporairement un fournisseur LLM invalide, traiter une
   candidature (statut « Erreur de traitement »), rétablir la configuration, cliquer
   « Relancer ».

## Vérification automatique équivalente

`pytest tests/test_workflow_integration.py tests/test_robustness.py` rejoue ces scénarios avec
un fournisseur LLM simulé. Cela ne remplace pas une démonstration avec un vrai modèle.
