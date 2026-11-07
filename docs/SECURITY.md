# Sécurité, limites et test

Mesures : sessions signées et cookies `httpOnly`/`SameSite`, `Secure` hors
développement, Argon2, CSRF sur les POST, dépendances de rôle, échappement
Jinja/HTML, validation extension/MIME/signature/taille, UUID de stockage,
résolution confinée à `UPLOAD_DIR`, rapports admin séparés de la vue candidat,
masquage des CIN, neutralisation de la date de naissance avant Matching/Report,
prompts délimités et preuves exactes, verrous SQL pour éviter le double lancement,
messages d'erreur allowlistés et refus des secrets par défaut hors développement.

Limites : limitation de tentatives en mémoire, e-mails sans relance après crash,
recherche accent-insensible en mémoire, OCR non installé, résultats variables
avec un vrai LLM et preuves dépendantes du texte exact. Les valeurs d'exemple
`change-me` sont acceptées uniquement en développement.

Plan de test : routes et rôles, CSRF, XSS, fichiers hors `UPLOAD_DIR`, isolation
candidat/admin, secrets par défaut, concurrence, reprise d'un run abandonné,
agents avec faux client, migrations upgrade/downgrade/upgrade, seed idempotent,
lint, format, dépendances et Compose.
