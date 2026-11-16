# REVIEW — version 1 (image + sous-titres + bruitages)

## Ce qui est fait
- Les 8 séquences du scénario, aux temps du découpage, en un seul monde 3D continu (carte d'Europe en relief, sociétés A-B-C-D, carton, pièces, trésor public qui devient le trou final).
- Sous-titres mot à mot par groupes de 3 à 5 mots, mots importants agrandis et colorés.
- 33 bruitages calés sur des actions visibles (impacts, passages, pièces, papier).
- Raccord de boucle : le point orange rejoint la ligne TVA de la facture, la dernière image retrouve le cadre de la première.

## Ce qui manque, et pourquoi
- **Les vrais Bitmoji.** Aucune image de référence n'était jointe : les deux personnages sont des doublures 3D paramétrables (bloc `AVATARS` de `compositions/world.html`). Rendu « jouet stylisé », pas Pixar.
- **Les voix.** Pas de synthèse vocale disponible dans cette session, et le choix des voix (genre, timbre) revient à l'équipe. Les bouches et les sous-titres suivent des temps de mots estimés ; ils se recalent en ajoutant `w: [[début, fin], …]` aux répliques de `assets/film-data.js`.
- **La musique.** Aucune source de musique disponible ; rien n'a été composé en code.

## Choix à connaître
- Le prix est montré dans l'ordre de la voix : 120 € TTC d'abord, puis la séparation 100 € HT + 20 € TVA (le scénario décrivait l'inverse).
- Le compteur « Recettes publiques » compte − 20 € par tour de circuit : c'est l'exemple à 20 %, pas une statistique.
- Les prix 120 € / 99 € de la séquence « concurrence » sont illustratifs.
- L'État est un bassin de pièces au centre du circuit : c'est lui qui se vide et devient le trou de la chute.
- La société B ne disparaît pas complètement : elle s'éteint et s'enfonce à moitié, pour rester lisible dans le cercle.

## Mesuré / regardé / non vérifié
- `hyperframes check` : aucune erreur. Avertissements gardés : fichier de scène long (un seul monde 3D continu), contenu 3D qui touche le bord du cadre (voulu).
- Regardé : environ 90 images fixes réparties sur tout le film, dont chaque transition.
- Non vérifié : le son n'a été ni écouté ni mixé face à une voix ; le mouvement n'a été jugé que sur images fixes.

## Plan le plus faible
- 46-54 s : l'avatar 1 est petit et ses gestes se lisent mal à côté des deux boutiques. Avec les vrais avatars, lui donner la moitié gauche du cadre.
- 4,9 s et 13 s : pendant 0,2 s aucun avatar n'est à l'écran entre deux narrateurs.
