# RUPTURE — teaser 3D, 18 s, 9:16

Une minuscule invitation noire touche un désert de sel. La croûte s'arrache en une vague
dont la doublure se révèle en satin rouge. Le temps s'arrête. Les fragments se réassemblent
en scène monumentale. **LA NUIT CHANGE LES RÈGLES — PROCHAINEMENT.**

Livrable : `telechargements/RUPTURE_18s.mp4` (racine du dépôt) — 1080 × 1920 natif, 30 i/s
constantes, 540 images, H.264 yuv420p, son AAC stéréo 48 kHz.

## Feuille de route : les trois effets décisifs

| Effet | Méthode | Risque visuel | Vérification |
| --- | --- | --- | --- |
| Sel → satin | Nappe de croûte subdivisée (377 × 301), animée en Python : courbe inextensible intégrée le long du sens de déferlement, épaisseur réelle (solidify 0,8 m), attribut `sat` qui pilote le mélange sel/satin sur la face intérieure, plis géométriques qui naissent derrière le front, éclats balistiques qui tombent au passage du front | Mur frontal sans profondeur ; transformation déjà finie avant d'être vue ; repliement des plis | Images 4,27 / 4,67 / 5,07 / 5,47 s comparées en deux variantes |
| Arrêt du temps | Temps des objets séparé du temps caméra (`sim.object_time`) : figé de 7 à 10 s, caméra en orbite de 50° qui monte ; vrais volumes (41 blocs, rubans, scène) à toutes les distances, cristal qui frôle l'objectif | Effet « image fixe qui tourne » | Parallaxe vérifiée en rendu réel à 7,0 / 8,5 / 10,0 s |
| Assemblage | Chaque bloc = une cellule réelle des gradins (appareillage décalé) : pose d'origine, pose suspendue, pose finale ; trajectoire de Bézier qui reprend l'élan précédent puis descend dans sa loge, rebond amorti ; racine cristalline rétractée par clé de forme ; les rubans deviennent les bandes de l'auvent puis se soudent | Gravats désordonnés ; jours entre bandes de tissu | Variantes A/B à 11,0–13,4 s |

Variantes comparées (mêmes cadrages, même lumière, `RUPTURE_FRONT` / `RUPTURE_ASSEMBLY`) :

- **Front A retenu** : le satin part de la lèvre (première matière arrachée, côté impact) et descend
  vers le pied ; on voit le sel céder la place au satin. En B, tout est rouge dès que la croûte se
  dresse : la transformation ne se lit pas.
- **Assemblage A retenu** : gradin par gradin, du centre vers l'extérieur — construction lisible.
  En B (vague ouest → est), des blocs flottent encore à 13,4 s.

## Structure

| Fichier | Rôle |
| --- | --- |
| `src/sim.py` | Toute l'animation en numpy pur : timeline, caméra, carte, onde, vague, blocs, scène, rubans/auvent. Chaque image ne dépend que de son numéro ; graines fixes |
| `src/build.py` | Construit la scène Blender (géométrie, matériaux, lumière) et applique `sim` à chaque image |
| `src/sky.py` | Ciel du désert précalculé (HDR équirectangulaire) : fond, brume des matériaux |
| `src/audio.py` | Habillage sonore original synthétisé, calé sur 2,5 / 7,0 / 10,0 / 14,0 s et sur la pose de chaque bloc |
| `src/titles.py` | Titres en calques ajoutés après le rendu ; export PNG transparents + SVG éditable |
| `titres.json` | Configuration unique : titre, signature, artiste, date, lieu, mention (un champ vide n'est pas affiché) |
| `render.sh` | Procédure complète et reproductible |
| `fonts/` | Bodoni Moda et Inter (licence OFL) |

## Rendu

Prérequis : Blender 4.2 LTS, Python 3 avec numpy et Pillow, ffmpeg.

```bash
BLENDER=/chemin/vers/blender ./render.sh                    # final : 1080p, 10 échantillons + débruitage OIDN
BLENDER=... RES=270 SAMPLES=4 ./render.sh                   # prévisualisation complète en quelques minutes
blender -b -P src/build.py -- --res 540 --frames 255 --out tmp   # une image
blender -b -P src/build.py -- --save rupture.blend          # scène inspectable dans Blender
```

Le rendu est reprenable : les images déjà présentes dans `renders/frames` sont conservées.

## Paramètres éditables

- Timeline et accents : `sim.py` (`T_IMPACT`, `T_FREEZE`, `T_RESUME`, `T_REVEAL`), trajectoires caméra
  `CAM_A` / `CAM_B` (temps, position, cible, focale).
- Vague : `ALPHA` (direction), `TEAR_GAIN` (taille), `_curl_amount` (déferlement), `T_SAT0/1` (front satin).
- Gradins et scène : `TIERS`, `STAGE_FLOOR`, `BACKDROP` ; auvent : `_canopy_spine`, `canopy_final`.
- Lumière : soleil dans `build_scene` (direction commune `sim.SUN_DIR`), ciel dans `sky.py`.
- Textes : `titres.json`.

## Vérifications effectuées

- `ffprobe` : H.264 High, yuv420p, 1080 × 1920, 30/1 constant, 540 images, 18,000 s ; AAC 48 kHz, 18,000 s.
  Décodage complet sans erreur ; audio présent (moyenne −17,9 dB, crête −1,5 dB).
- Images extraites du MP4 à 1,0 ; 2,5 ; 4,5 ; 7,0 ; 8,5 ; 10,0 ; 12,0 ; 14,8 ; 17,5 s et inspectées.
- Raccord à 6,0 s (satin plein cadre des deux côtés), jonction entre deux sessions de rendu (12,2 s),
  décélération de la caméra jusqu'au cadre fixe : contrôlés image par image.

## Ce qui a été réellement produit et ses limites

- Moteur : Blender 4.2 Cycles **sur CPU** (4 cœurs, pas de GPU dans l'environnement).
- Pas de simulation physique de tissu : les drapés sont procéduraux et précalculés (déterministes).
- Pas de flou de mouvement (coût de rendu sur CPU) ; profondeur de champ réelle sur la caméra.
- La bande son est synthétisée dans `audio.py`, sans échantillon externe.
- Défauts connus restants : une limite visible au sol où s'arrête la zone de cristaux détaillés
  (vers 13,3 s) ; le rouge du satin est un peu plus clair juste après le raccord de 6,0 s.
- Calques de titres finaux : `calques/` (PNG transparents + `titres.svg` éditable).
