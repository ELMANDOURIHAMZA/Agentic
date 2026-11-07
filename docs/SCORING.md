# Calcul du score

Les poids par défaut sont : compétences obligatoires 40 %, expérience 20 %,
diplôme 15 %, compétences souhaitées 10 %, langues 5 %, cohérence documentaire
10 %. La configuration vérifie que la somme vaut 100.

Pour chaque compétence, `match = 1`, `partiel = 0,5`, `absent = 0`. Le score
d'une catégorie est la moyenne des critères. L'expérience vaut
`min(années candidat / années exigées, 1)`. La conformité documentaire est
ramenée sur 100 puis convertie en ratio. Le score final est borné à 0–100 et
arrondi à une décimale.

Une catégorie sans exigence est exclue du dénominateur puis son poids est
redistribué proportionnellement entre les catégories ayant une exigence. Elle
ne vaut donc ni zéro ni 100 par défaut.

Exemple : exigences obligatoires 40 % à 100 %, expérience 20 % à 50 %,
diplôme 15 % à 100 %, souhaitées 10 % sans exigence, langues 5 % à 100 %,
documents 10 % à 80 %. Le poids actif est 90 %. Après redistribution du poids
souhaitées, les poids effectifs sont 44,4 %, 22,2 %, 16,7 %, 5,6 % et 11,1 %.
Le score est `100×.444 + 50×.222 + 100×.167 + 100×.056 + 80×.111 = 88,9`.

Le score ne décide jamais d'une embauche ou d'un rejet.

## Revue humaine obligatoire

Le poids de 10 % de la cohérence documentaire peut laisser un score élevé à un
dossier incohérent. Sans modifier le score, l'interface signale « Revue humaine
obligatoire » quand la conformité est inférieure à 70/100 ou qu'une incohérence
est de gravité élevée (détail admin, classement, tableau de bord, PDF).

## Contrat de critères du Matching Agent

Le LLM n'évalue que les critères sémantiques. Leur liste exacte est calculée par
`expected_criteria_ids` : `degree` (seulement si un diplôme est exigé),
`required_skill:<x>`, `preferred_skill:<x>`, `language:<x>`. Elle est transmise dans
`<criteres_attendus>`. Une réponse avec un critère manquant, inconnu ou en double est
rejetée (une nouvelle tentative, puis erreur de l'agent) : un critère absent n'est jamais
compté comme un échec. La casse des identifiants est tolérée. Une preuve qui ne figure pas
dans le profil ramène le verdict à « absent » avec une justification explicite.

## Barème de conformité documentaire

L'agent 3 extrait l'identité de la CIN et le titulaire, l'intitulé, l'établissement et l'année
du diplôme, puis les compare au CV par code déterministe. Départ à 100 :

| Anomalie | Pénalité |
|---|---|
| Document illisible ou vide | −50 par document |
| Information absente ou non lisible (jamais une fraude) | −10 |
| Prénom ou nom CIN ↔ CV, titulaire du diplôme ↔ candidat : correspondance partielle | −30 |
| Idem, sans correspondance | −50 |
| Intitulé du diplôme ↔ CV : partiel / aucun mot en commun | −10 / −20 |
| Année du diplôme divergente (< 5 ans / ≥ 5 ans) | −20 / −35 |

Le niveau est borné à 0 et utilisé tel quel par le matching. Chaque anomalie porte un
type (`identity`, `diploma_holder`, `diploma_title`, `year`, `institution`, `missing`,
`unreadable`) et une explication.
