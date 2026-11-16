# Fraude carrousel à la TVA — vidéo verticale 60 s

Projet [HyperFrames](https://hyperframes.heygen.com) (HTML rendu en vidéo), 1080 x 1920, 30 fps.

| Fichier | Rôle |
| --- | --- |
| `index.html` | Composition racine : monde 3D, sous-titres, bruitages |
| `compositions/world.html` | Scène 3D (Three.js) : carte d'Europe, sociétés, carton, pièces, avatars, titres |
| `compositions/captions.html` | Sous-titres — **généré**, ne pas modifier à la main |
| `assets/film-data.js` | Le script : répliques, groupes de sous-titres, mots importants, fenêtres de parole |
| `tools/build-captions.mjs` | Régénère les sous-titres depuis le script |
| `SPEC.md`, `REVIEW.md` | Direction artistique chiffrée, et bilan de la version livrée |

```bash
npx hyperframes preview --background   # aperçu dans le navigateur
node tools/build-captions.mjs          # après toute modification du script
npx hyperframes check                  # contrôle
npx hyperframes render -o renders/fraude-carrousel-tva.mp4
```

Les avatars sont des doublures : leurs réglages (peau, cheveux, tenue, lunettes) sont dans le bloc
`AVATARS` en tête de `compositions/world.html`.

Crédits des bruitages : `assets/sfx/CREDITS.md`.
