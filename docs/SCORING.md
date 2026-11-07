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
redistribué proportionnellement entre les catégories ayant une exigence. Le
diplôme est facultatif : lorsque l'offre ne précise aucun diplôme demandé,
l'Agent 1 conserve le champ vide et le Matching Agent exclut ce critère. Elle
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

## Barème de conformité documentaire

L'agent 3 extrait avec le LLM les identités de la CIN et du diplôme, puis
compare par code déterministe le nom/prénom du CV, de la CIN et le titulaire du
diplôme, ainsi que l'année du diplôme. Départ à 100 ; document illisible −50 ; champ non vérifiable −10 ;
prénom/nom en correspondance partielle −30, sans correspondance −50 ; année du
diplôme divergente −20 (moyenne) ou −35 (élevée). Le niveau, borné à 0, est
utilisé tel quel par le matching.
