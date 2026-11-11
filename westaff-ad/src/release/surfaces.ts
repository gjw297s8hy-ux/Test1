import * as THREE from 'three';

/**
 * Matériaux procéduraux réalistes (béton banché, asphalte mouillé) : couleur + rugosité + normal map
 * générées à partir d'un bruit fractal déterministe.
 */
const S = 1024;
const hash = (x: number, y: number, s: number) => { const h = Math.sin(x * 127.1 + y * 311.7 + s * 74.7) * 43758.5453; return h - Math.floor(h); };
const vnoise = (x: number, y: number, s: number) => {
  const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi;
  const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
  const a = hash(xi, yi, s), b = hash(xi + 1, yi, s), c = hash(xi, yi + 1, s), d = hash(xi + 1, yi + 1, s);
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
};
const fbm = (x: number, y: number, s: number, oct = 5) => { let a = 0, f = 1, w = 0.5, n = 0; for (let i = 0; i < oct; i++) { a += vnoise(x * f, y * f, s + i) * w; n += w; f *= 2.03; w *= 0.5; } return a / n; };

const toTex = (data: Uint8ClampedArray, srgb: boolean, repeat = 1) => {
  const c = document.createElement('canvas'); c.width = c.height = S; const g = c.getContext('2d')!;
  g.putImageData(new ImageData(data, S, S), 0, 0);
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(repeat, repeat); t.anisotropy = 8;
  if (srgb) t.colorSpace = THREE.SRGBColorSpace; return t;
};
const normalFromHeight = (h: Float32Array, strength: number) => {
  const out = new Uint8ClampedArray(S * S * 4);
  for (let y = 0; y < S; y++) for (let x = 0; x < S; x++) {
    const l = h[y * S + ((x - 1 + S) % S)], r = h[y * S + ((x + 1) % S)], u = h[((y - 1 + S) % S) * S + x], d = h[((y + 1) % S) * S + x];
    let nx = (l - r) * strength, ny = (u - d) * strength, nz = 1; const len = Math.hypot(nx, ny, nz); nx /= len; ny /= len; nz /= len;
    const i = (y * S + x) * 4; out[i] = (nx * 0.5 + 0.5) * 255; out[i + 1] = (ny * 0.5 + 0.5) * 255; out[i + 2] = (nz * 0.5 + 0.5) * 255; out[i + 3] = 255;
  }
  return out;
};

export type Surface = {map: THREE.Texture; roughnessMap: THREE.Texture; normalMap: THREE.Texture};

/** Asphalte de parking : granulat, flaques brillantes, marquages blancs usés, zone hachurée rouge. */
export const asphalt = (): Surface => {
  const col = new Uint8ClampedArray(S * S * 4), rough = new Uint8ClampedArray(S * S * 4), h = new Float32Array(S * S);
  const c = document.createElement('canvas'); c.width = c.height = S; const g = c.getContext('2d')!;
  // marquages (dessinés dans un calque, puis mélangés)
  g.fillStyle = '#000'; g.fillRect(0, 0, S, S);
  g.strokeStyle = '#fff'; g.lineWidth = 12;
  for (let i = 0; i < 5; i++) { g.beginPath(); g.moveTo(140 + i * 190, 40); g.lineTo(140 + i * 190, 430); g.stroke(); }
  g.fillStyle = '#f00';
  for (let i = -6; i < 12; i++) { g.save(); g.beginPath(); g.rect(40, 500, 260, 230); g.clip(); g.translate(40 + i * 50, 500); g.rotate(-0.785); g.fillRect(0, -400, 18, 1200); g.restore(); }
  g.strokeStyle = '#f00'; g.lineWidth = 9; g.strokeRect(40, 500, 260, 230);
  const marks = g.getImageData(0, 0, S, S).data;
  for (let y = 0; y < S; y++) for (let x = 0; x < S; x++) {
    const i = y * S + x, k = i * 4, u = x / S * 8, v = y / S * 8;
    const grain = hash(x, y, 3), n = fbm(u, v, 1), stain = fbm(u * 0.35, v * 0.35, 9, 4);
    const puddle = Math.max(0, Math.min(1, (fbm(u * 0.4 + 3, v * 0.4, 21, 4) - 0.6) * 9));
    const wear = fbm(u * 3, v * 3, 33, 3) > 0.42 ? 1 : 0.35;
    let r = 62 + n * 40 + (grain > 0.97 ? 45 : 0) - stain * 18, gg = r, b = r + 4;
    const white = marks[k] > 128 && marks[k + 1] > 128 ? wear : 0, red = marks[k] > 128 && marks[k + 1] < 60 ? wear : 0;
    r = r * (1 - white) + 205 * white; gg = gg * (1 - white) + 200 * white; b = b * (1 - white) + 190 * white;
    r = r * (1 - red) + 150 * red; gg = gg * (1 - red) + 14 * red; b = b * (1 - red) + 22 * red;
    const wet = 1 - puddle * 0.45;
    col[k] = r * wet; col[k + 1] = gg * wet; col[k + 2] = b * wet; col[k + 3] = 255;
    const ro = (0.82 - puddle * 0.78 + grain * 0.1) * 255; rough[k] = rough[k + 1] = rough[k + 2] = ro; rough[k + 3] = 255;
    h[i] = (n * 0.6 + grain * 0.5) * (1 - puddle);
  }
  return {map: toTex(col, true), roughnessMap: toTex(rough, false), normalMap: toTex(normalFromHeight(h, 3.5), false)};
};

/** Béton banché : planches de coffrage, trous de banche, coulures, bande rouge peinte. */
export const concrete = (redBand = true): Surface => {
  const col = new Uint8ClampedArray(S * S * 4), rough = new Uint8ClampedArray(S * S * 4), h = new Float32Array(S * S);
  for (let y = 0; y < S; y++) for (let x = 0; x < S; x++) {
    const i = y * S + x, k = i * 4, u = x / S * 6, v = y / S * 6;
    const n = fbm(u, v, 5), fine = hash(x, y, 7);
    const plank = (y % 128) < 3 ? 1 : 0, joint = (x % 256) < 2 ? 1 : 0;
    const hx = (x % 256) - 128, hy = (y % 128) - 64, hole = Math.hypot(hx, hy) < 7 ? 1 : 0;
    const drip = fbm(u * 6, v * 0.4, 13, 3) * Math.max(0, 1 - (y % 128) / 128);
    let c = 92 + n * 50 - drip * 30 - (plank + joint) * 35 - hole * 50 + (fine - 0.5) * 14;
    let r = c, g = c, b = c + 2;
    const band = redBand && y > 700 && y < 790 ? 1 : 0;
    if (band) { const chip = fbm(u * 5, v * 5, 41, 3) > 0.35 ? 1 : 0.2; r = r * (1 - chip) + 120 * chip; g = g * (1 - chip) + 8 * chip; b = b * (1 - chip) + 14 * chip; }
    col[k] = r; col[k + 1] = g; col[k + 2] = b; col[k + 3] = 255;
    const ro = (0.88 - band * 0.35 + fine * 0.08) * 255; rough[k] = rough[k + 1] = rough[k + 2] = ro; rough[k + 3] = 255;
    h[i] = n * 0.7 + fine * 0.25 - (plank + joint) * 0.8 - hole;
  }
  return {map: toTex(col, true), roughnessMap: toTex(rough, false), normalMap: toTex(normalFromHeight(h, 4), false)};
};
