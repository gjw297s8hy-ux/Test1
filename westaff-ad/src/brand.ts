/**
 * Configuration de marque — tout ce qui est éditable sans toucher aux scènes.
 * Les textes respectent la règle : aucune promesse chiffrée (pas de %, pas de prix, pas de garantie).
 */
export const BRAND = {
  name: 'WESTAFF',
  nameSub: 'PLACE',
  handle: '@NOM_DU_COMPTE', // ← remplacer par le compte TikTok / Instagram
  colors: {
    black: '#030306',
    gold: '#e8b964',
    goldDeep: '#b8862f',
    goldLight: '#fbe3a6',
    electric: '#2f7bff',
    violet: '#9b3dff',
    white: '#f5f2ea',
  },
  copy: {
    intro: ['TES', 'ÉVÉNEMENTS.'],
    stadium: {eyebrow: 'FOOTBALL', lines: ['LES PLUS', 'GRANDS MATCHS.']},
    concert: {eyebrow: 'CONCERTS', lines: ['LES CONCERTS', 'INOUBLIABLES.']},
    theatre: {eyebrow: 'SPECTACLES', lines: ['ET BIEN PLUS', 'ENCORE.']},
    hero: {lines: ['TES PLACES', 'À PRIX RÉDUITS.'], sub: 'Football • Concerts • Spectacles'},
    cta1: ['RÉSERVE TES', 'PROCHAINES ÉMOTIONS'],
    cta2: 'CONTACTE',
  },
  categories: [
    {key: 'football', label: 'FOOTBALL', accent: '#2f7bff'},
    {key: 'concert', label: 'CONCERTS', accent: '#9b3dff'},
    {key: 'show', label: 'SPECTACLES', accent: '#e8b964'},
  ],
};

export const VIDEO = {width: 1080, height: 1920, fps: 60, seconds: 30};

/** Découpage temporel (secondes) — synchronisé avec scripts/make_audio.py (120 BPM). */
export const T = {
  intro: [0, 4],
  stadium: [4, 9],
  concert: [9, 14],
  theatre: [14, 18],
  hero: [18, 24],
  brand: [24, 30],
} as const;

/** Zones de sécurité TikTok / Reels (px sur 1080x1920). */
export const SAFE = {top: 250, bottom: 440, left: 80, right: 140};
