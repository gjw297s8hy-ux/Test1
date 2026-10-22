import * as THREE from 'three';

/** Texture de métal brossé procédurale (stries fines) — sert de roughnessMap / anisotropie. */
let brushed: THREE.CanvasTexture | null = null;
export const brushedTex = () => {
  if (brushed) return brushed;
  const c = document.createElement('canvas'); c.width = 512; c.height = 512;
  const g = c.getContext('2d')!;
  g.fillStyle = '#7a7a7a'; g.fillRect(0, 0, 512, 512);
  let s = 7; const r = () => ((s = (s * 16807) % 2147483647) / 2147483647);
  for (let i = 0; i < 2600; i++) {
    const y = r() * 512, v = 90 + r() * 90;
    g.fillStyle = `rgba(${v},${v},${v},${0.15 + r() * 0.25})`;
    g.fillRect(0, y, 512, 0.6 + r() * 1.2);
  }
  brushed = new THREE.CanvasTexture(c);
  brushed.wrapS = brushed.wrapT = THREE.RepeatWrapping;
  brushed.repeat.set(2, 2);
  return brushed;
};

export const goldBrushed = () =>
  new THREE.MeshPhysicalMaterial({
    color: '#e3b25a', metalness: 1, roughness: 0.32, roughnessMap: brushedTex(),
    anisotropy: 0.7, clearcoat: 0.4, clearcoatRoughness: 0.2, envMapIntensity: 1.4,
  });

export const goldPolished = () =>
  new THREE.MeshPhysicalMaterial({color: '#f0c06a', metalness: 1, roughness: 0.14, clearcoat: 1, clearcoatRoughness: 0.05, envMapIntensity: 1.6});

export const chrome = () => new THREE.MeshPhysicalMaterial({color: '#dfe6f2', metalness: 1, roughness: 0.12, envMapIntensity: 1.5});

export const blackGloss = () =>
  new THREE.MeshPhysicalMaterial({color: '#07070b', metalness: 0.3, roughness: 0.18, clearcoat: 1, clearcoatRoughness: 0.08});
