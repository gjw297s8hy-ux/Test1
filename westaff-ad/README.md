# Westaff Place — Publicité verticale 35 s (Remotion + React Three Fiber)

Publicité 1080×1920, 60 FPS, 35 s, H.264 + AAC, pensée pour TikTok / Reels / Shorts.
Toutes les scènes sont en **vraie 3D temps réel** (Three.js via React Three Fiber), montées et rendues image par image par **Remotion**.

## Storyboard réalisé

| Temps | Scène | Contenu 3D | Texte |
|---|---|---|---|
| 0–4 s | Intro | Sur fond Terre/Lune (image fournie), 5 200 particules dorées forment un billet holographique extrudé portant le logo | **TES ÉVÉNEMENTS.** (3D extrudé) |
| 4–9 s | Stade | La caméra traverse le billet → grue plongeante sur un stade nocturne procédural : pelouse tondue + tracés réglementaires, tribunes à 2 niveaux, ~20 000 spectateurs instanciés, flashs, mâts + faisceaux volumétriques, buts + filets, ballon procédural | LES PLUS GRANDS MATCHS. |
| 9–14 s | Championnats | Tour d'écrans 3D des 5 championnats (images fournies), montée d'un écran par temps, puis écran géant diffusant la vidéo des clubs | LES PLUS GRANDES LIGUES. |
| 14–19 s | Concert | Raccord sur la lumière d'un projecteur → scène, mur LED (shader), treillis, lyres motorisées, lasers, 2 400 silhouettes qui sautent sur le tempo, confettis métalliques | LES CONCERTS INOUBLIABLES. |
| 19–23 s | Spectacle | Plongée dans le mur LED → rideaux de velours (plis simulés qui se resserrent à l'ouverture), arc de scène doré, plancher bois, poursuites, billets flottants | ET BIEN PLUS ENCORE. |
| 23–29 s | Hero | La caméra entre dans un billet → 3 billets (photos ballon / concert fournies) en lévitation avec reflets, étiquette « € » qui rétrécit par crans + chevrons descendants (aucun chiffre) | **TES PLACES À PRIX RÉDUITS.** (3D) + Football • Concerts • Spectacles |
| 29–35 s | Marque | Logo fourni avec balayage lumineux, halo, rayons, particules | RÉSERVE TES PROCHAINES ÉMOTIONS → CONTACTE **@NOM_DU_COMPTE** |

Raccords : mouvements de caméra continus + flou radial (zoom blur) et surexposition dans le pipeline de post-traitement, flash lumineux additif sur le pic de lumière.
Post-traitement : SMAA, bloom, aberration chromatique légère, vignettage, grain, tone mapping ACES.

## Installation

```bash
npm install
python3 -m pip install numpy scipy   # pour régénérer la bande-son
```
Prérequis : Node ≥ 18, ffmpeg, Python 3.

## Rendu

```bash
npm run audio                 # régénère public/audio/soundtrack.wav (optionnel, déjà fourni)
npm run render                # → out/westaff_ad_1080x1920_60fps.mp4
bash scripts/stills.sh 2.5 6 12   # images-clés de contrôle (secondes) → out/stills/
npm run studio                # prévisualisation interactive (props : showSafeZones, forceFallback)
```

Variables d'environnement :
- `REMOTION_GL` : `swangle` (par défaut, rendu CPU — fonctionne sans GPU), `angle` ou `egl` pour accélérer sur machine avec GPU.
- `REMOTION_CONCURRENCY` : nombre d'onglets de rendu parallèles (3 par défaut).
- `REMOTION_BROWSER` : chemin d'un Chrome Headless Shell si le téléchargement automatique est impossible.
- `FALLBACK=1` : force la version de secours 2D.

**4K (2160×3840)** : changez `VIDEO.width/height` dans `src/brand.ts` (les scènes sont en unités monde, les textes 2D se ré-échelonnent) — à réserver à une machine avec GPU (`REMOTION_GL=angle`), le rendu CPU 4K/60 fps prendrait plusieurs heures.

### Version de secours sans WebGL
- Sans GPU : WebGL logiciel (SwiftShader/ANGLE, `REMOTION_GL=swangle`) — c'est ainsi que le master a été rendu.
- Sans aucun WebGL : `Ad.tsx` détecte l'absence de contexte et bascule automatiquement sur `Fallback2D` (même rythme, mêmes textes, même bande-son).

## Images et vidéo fournies
- `public/img/` : décor Terre/Lune, ballon, concert, logo, visuels des 5 championnats.
- `public/video/clubs/` : images de la vidéo des clubs (son mixé dans la bande-son).
- `src/brand.ts → IMAGES / CLUBS_VIDEO` : chemins à remplacer pour changer de visuels.
- ⚠️ Droits : logos de ligues/clubs, joueurs et marques visibles dans ces visuels appartiennent à leurs titulaires ; le décor Terre/Lune est un aperçu Adobe Stock filigrané (licence à acheter pour la version HD propre).

## Personnalisation

Tout est dans **`src/brand.ts`** :
- `handle` : remplacez `@NOM_DU_COMPTE`.
- `name` / `nameSub` : logotype 3D.
- `colors` : palette (noir, or, bleu électrique, violet néon).
- `copy` : tous les textes. Règle respectée : aucune promesse chiffrée (pas de %, pas de prix, pas de garantie).
- `T` : découpage temporel des scènes (à garder synchronisé avec `scripts/make_audio.py`).
- `SAFE` : zones de sécurité TikTok/Reels (activer `showSafeZones` dans le Studio pour les afficher).

## Bande-son
`scripts/make_audio.py` **compose et synthétise** une musique originale (120 BPM, ré mineur) avec effets synchronisés :
pulsation d'intro, montées + impacts sur chaque raccord (4 / 9 / 14 / 19 / 23 / 29 s), foule au stade, zaps laser au concert, cordes et timbales au spectacle,
blips descendants synchronisés aux chevrons du « prix réduit », carillon du logo, bascule du CTA. Générée par code → aucun droit tiers.
Normalisée à −14 LUFS (standard réseaux sociaux).

## Arborescence
```
src/
  brand.ts              configuration de marque, textes, timing, safe zones
  Ad.tsx / Root.tsx     composition Remotion
  lib/anim.ts           easing, interpolation, splines de caméra, aléatoire déterministe
  three/                briques 3D réutilisables : Ticket, Text3D, faisceaux, particules, matériaux, World (caméra + post)
  scenes/               Intro, Stadium, Concert, Theatre, Hero, Brand
  overlay/              titres cinétiques 2D, flashs, CTA, safe zones, fallback 2D
scripts/                make_audio.py, render.sh, stills.sh
public/                 polices Inter (OFL), bande-son
```

## Droits
- Les éléments 3D (billets, stade, scène, ballon, pictogrammes) sont procéduraux. Les visuels de ligues/clubs et le logo proviennent des fichiers fournis par le client (voir « Images et vidéo fournies »).
- Polices : Inter / Inter Display (SIL Open Font License).
- Musique et effets : générés par `scripts/make_audio.py`.
