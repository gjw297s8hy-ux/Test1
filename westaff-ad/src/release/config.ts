/** Teaser de sortie « NPNG » — O'NEAL. Tout le texte et le timing sont éditables ici. */
export const REL = {
  artist: "O'NEAL",
  artistGothic: "O'Neal", // version gothique (minuscules : plus lisible)
  title: 'NPNG',
  titleLong: ['NO PAIN', 'NO GAIN'],
  kicker: 'NOUVEAU SON',
  cta: 'DISPONIBLE MAINTENANT',
  platforms: 'Spotify • Apple Music • Deezer • YouTube',
  colors: {red: '#d0141f', redDeep: '#6e0710', ember: '#ff6a1a', white: '#f4f1ec', bg: '#060407'},
  video: {width: 1080, height: 1920, fps: 30, seconds: 15},
  clip: {dir: 'npng/clip', frames: 416, fps: 30},
  rose: {dir: 'npng/rose', frames: 34, fps: 30},
  cover: 'npng/cover.jpg',
  photos: {studio: 'npng/photo_studio.jpg', duo: 'npng/photo_duo.jpg', profile: 'npng/photo_profile.jpg'},
  audio: 'npng/soundtrack.wav',
};
/** Grille rythmique mesurée sur le morceau (≈118 BPM) : temps k → secondes. */
export const BEAT = 0.508, BEAT0 = 0.396;
export const beat = (k: number) => BEAT0 + BEAT * k;
/** Découpage des plans (calés sur des temps forts). */
export const SH = {A: [0, beat(4)], B: [beat(4), beat(8)], C: [beat(8), beat(11)], D: [beat(11), beat(22)], E: [beat(22), 15]} as const;
