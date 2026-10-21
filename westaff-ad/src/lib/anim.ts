import * as THREE from 'three';

export const clamp = (x: number, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const prog = (t: number, a: number, b: number) => clamp((t - a) / (b - a));
export const mix = (a: number, b: number, k: number) => a + (b - a) * k;
export const smooth = (x: number) => x * x * (3 - 2 * x);
export const ease = {
  inCubic: (x: number) => x * x * x,
  outCubic: (x: number) => 1 - Math.pow(1 - x, 3),
  inOutCubic: (x: number) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2),
  outQuint: (x: number) => 1 - Math.pow(1 - x, 5),
  inQuart: (x: number) => x * x * x * x,
  outExpo: (x: number) => (x === 1 ? 1 : 1 - Math.pow(2, -10 * x)),
  inExpo: (x: number) => (x === 0 ? 0 : Math.pow(2, 10 * x - 10)),
  inOutExpo: (x: number) =>
    x === 0 ? 0 : x === 1 ? 1 : x < 0.5 ? Math.pow(2, 20 * x - 10) / 2 : (2 - Math.pow(2, -20 * x + 10)) / 2,
  inOutSine: (x: number) => -(Math.cos(Math.PI * x) - 1) / 2,
  outBack: (x: number) => {
    const c1 = 1.4, c3 = c1 + 1;
    return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2);
  },
};

/** Générateur pseudo-aléatoire déterministe (mulberry32). */
export const rng = (seed: number) => () => {
  seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
  let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};

/** Bruit 1D lisse déterministe (pour micro-mouvements de caméra). */
export const noise1 = (x: number, seed = 0) => {
  const h = (n: number) => { const s = Math.sin(n * 127.1 + seed * 311.7) * 43758.5453; return s - Math.floor(s); };
  const i = Math.floor(x), f = x - i;
  return mix(h(i), h(i + 1), smooth(f)) * 2 - 1;
};

/** Trajectoire de caméra : spline Catmull-Rom centripète parcourue avec un easing global. */
export class Path {
  curve: THREE.CatmullRomCurve3;
  constructor(pts: [number, number, number][]) {
    this.curve = new THREE.CatmullRomCurve3(pts.map((p) => new THREE.Vector3(...p)), false, 'centripetal');
  }
  at(u: number, out = new THREE.Vector3()) { return this.curve.getPointAt(clamp(u), out); }
}
