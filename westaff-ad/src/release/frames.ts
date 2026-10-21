import * as THREE from 'three';
import {staticFile} from 'remotion';

/**
 * Textures « vidéo » image par image : chaque écran possède une texture dont on remplace l'image.
 * Les chargements sont mis en file ; le pilote de rendu attend leur fin avant de dessiner la frame.
 */
export const pending: Promise<void>[] = [];
const imgCache = new Map<string, HTMLImageElement>();
export const frameTexture = () => { const t = new THREE.Texture(); t.colorSpace = THREE.SRGBColorSpace; return t; };
export const setFrame = (tex: THREE.Texture, dir: string, idx: number) => {
  const url = staticFile(`${dir}/f${String(idx + 1).padStart(3, '0')}.jpg`);
  if ((tex as any).userData.url === url) return;
  (tex as any).userData.url = url;
  const ready = imgCache.get(url);
  if (ready) { tex.image = ready; tex.needsUpdate = true; return; }
  pending.push(new Promise<void>((res) => {
    const im = new Image();
    im.onload = () => { imgCache.set(url, im); if ((tex as any).userData.url === url) { tex.image = im; tex.needsUpdate = true; } if (imgCache.size > 80) imgCache.delete(imgCache.keys().next().value!); res(); };
    im.onerror = () => res();
    im.src = url;
  }));
};
