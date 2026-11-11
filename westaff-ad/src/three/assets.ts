import {staticFile} from 'remotion';
import {IMAGES, CLUBS_VIDEO} from '../brand';

/** Registre des images préchargées (utilisées par les textures canvas des billets). */
export const IMG: Record<string, HTMLImageElement> = {};
/** Images de la vidéo des clubs (préchargées : rendu frame par frame sans attente). */
export const CLUB_FRAMES: HTMLImageElement[] = [];
const load = (src: string) => new Promise<HTMLImageElement>((res, rej) => { const im = new Image(); im.onload = () => res(im); im.onerror = rej; im.src = staticFile(src); });
export const preloadImages = () =>
  Promise.all([
    ...Object.entries(IMAGES).map(([k, src]) => load(src).then((im) => { IMG[k] = im; })),
    ...Array.from({length: CLUBS_VIDEO.frames}, (_, i) => load(`${CLUBS_VIDEO.dir}/f${String(i + 1).padStart(3, '0')}.jpg`).then((im) => { CLUB_FRAMES[i] = im; })),
  ]);
