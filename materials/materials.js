// PBR material library. All metals are true metalness=1 materials lit by art-directed PMREM
// environments, with procedural micro-roughness so highlights break up like real surfaces.
import * as THREE from 'three';
import { microRoughness, brushedCanvas, tex } from '../src/engine/lib.js';

let cache = null;
function maps() {
  if (cache) return cache;
  cache = {
    micro: tex(microRoughness(11, 512, 0.5, 0.35), { repeat: 3 }),
    microFine: tex(microRoughness(23, 512, 0.5, 0.2), { repeat: 8 }),
    brushed: tex(brushedCanvas(5, 1024), { repeat: 1 }),
  };
  return cache;
}

export const GOLD = '#E4BC66';      // lifted from brand #D6AE57 so metal reads gold, not brown, after ACES
export const GOLD_DEEP = '#C8963E';
export const SILVER = '#D9DDE4';

export function gold({ roughness = 0.2, color = GOLD, clearcoat = 0, envMapIntensity = 1, bump = null, bumpScale = 1 } = {}) {
  const m = maps();
  return new THREE.MeshPhysicalMaterial({
    color, metalness: 1, roughness, roughnessMap: m.micro, clearcoat, clearcoatRoughness: 0.08, envMapIntensity,
    bumpMap: bump, bumpScale, specularIntensity: 1,
  });
}

export function brushedSilver({ roughness = 0.32, color = SILVER, anisotropy = 0.85, rotation = 0 } = {}) {
  const m = maps();
  return new THREE.MeshPhysicalMaterial({
    color, metalness: 1, roughness, roughnessMap: m.brushed, anisotropy, anisotropyRotation: rotation,
    clearcoat: 0.25, clearcoatRoughness: 0.15,
  });
}

export function chrome({ color = '#eef1f6', roughness = 0.04 } = {}) {
  return new THREE.MeshPhysicalMaterial({ color, metalness: 1, roughness, roughnessMap: maps().microFine });
}

export function smokedGlass({ color = '#0b0c11', opacity = 0.72 } = {}) {
  return new THREE.MeshPhysicalMaterial({ color, metalness: 0, roughness: 0.05, clearcoat: 1, clearcoatRoughness: 0.03, transparent: true, opacity, ior: 1.5, specularIntensity: 1 });
}

export function holographic({ color = '#d6dcea', roughness = 0.14, thickness = [180, 820] } = {}) {
  return new THREE.MeshPhysicalMaterial({
    color, metalness: 1, roughness, roughnessMap: maps().microFine,
    iridescence: 1, iridescenceIOR: 1.85, iridescenceThicknessRange: thickness,
  });
}

export function velvet({ color = '#790B1A', sheen = '#ff6a6a' } = {}) {
  return new THREE.MeshPhysicalMaterial({ color, roughness: 0.85, metalness: 0, sheen: 1, sheenColor: new THREE.Color(sheen), sheenRoughness: 0.42 });
}

export function blackLacquer() {
  return new THREE.MeshPhysicalMaterial({ color: '#07070a', metalness: 0.2, roughness: 0.35, clearcoat: 1, clearcoatRoughness: 0.05 });
}

export function emissive(color, intensity = 3) {
  return new THREE.MeshBasicMaterial({ color: new THREE.Color(color).multiplyScalar(intensity), toneMapped: false });
}
