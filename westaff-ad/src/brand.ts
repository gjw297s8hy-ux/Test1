/**
 * Configuration de marque — tout ce qui est éditable sans toucher aux scènes.
 * Les textes respectent la règle : aucune promesse chiffrée (pas de %, pas de prix, pas de garantie).
 */
export const BRAND = {
  name: 'WESTAFF',
  nameSub: 'PLACE',
  handle: 'Westaff', // ← remplacer par le compte TikTok / Instagram
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
    leagues: {eyebrow: 'CHAMPIONNATS', lines: ['LES PLUS', 'GRANDES LIGUES.']},
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

export const VIDEO = {width: 1080, height: 1920, fps: 60, seconds: 35};

/** Découpage temporel (secondes) — synchronisé avec scripts/make_audio.py (120 BPM). */
export const T = {
  intro: [0, 4],
  stadium: [4, 9],
  leagues: [9, 14],
  concert: [14, 19],
  theatre: [19, 23],
  hero: [23, 29],
  brand: [29, 35],
} as const;

/** Scène « championnats » insérée à 9 s (5 s). Les scènes suivantes sont écrites en temps « historique » (sans l'insertion). */
export const INSERT = {at: 9, dur: 5};
export const legacyTime = (t: number) => (t < INSERT.at ? t : t >= INSERT.at + INSERT.dur ? t - INSERT.dur : -1);

/** Images fournies (public/img) — utilisées dans les scènes et les billets. */
export const IMAGES = {
  moon: 'img/moon.jpg', ball: 'img/ball.jpg', concert: 'img/concert.jpg', logo: 'img/logo.jpg',
  pl: 'img/pl.jpg', laliga: 'img/laliga.jpg', laligaPlayers: 'img/laliga_players.jpg', seriea: 'img/seriea.jpg', bundesliga: 'img/bundesliga.jpg', ligue1: 'img/ligue1.jpg',
};
export const CLUBS_VIDEO = {dir: 'video/clubs', frames: 110, fps: 30};

/** Zones de sécurité TikTok / Reels (px sur 1080x1920). */
export const SAFE = {top: 250, bottom: 440, left: 80, right: 140};
