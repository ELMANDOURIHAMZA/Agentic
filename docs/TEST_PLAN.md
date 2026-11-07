# Plan de test

Les tests couvrent les modèles et transitions, authentification/CSRF/rôles,
offres publiques et admin, candidatures et documents, emails, espace candidat,
chaque agent avec le fournisseur réel configuré, workflow et concurrence,
récupération des runs abandonnés, migration round-trip et protections
XSS/secrets. Les tests d'intégration LLM sont opt-in et ne sont jamais
remplacés par un fournisseur simulé.

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
