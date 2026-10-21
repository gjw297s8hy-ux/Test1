// Shared, deterministic helpers. Everything is a pure function of its inputs (seeded RNG, time).
import * as THREE from 'three';
import { Font } from 'three/addons/loaders/FontLoader.js';

// ---------- randomness ----------
export function rng(seed = 1) {
  let a = seed >>> 0;
  return function () {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ---------- easing / timing ----------
export const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const lerp = (a, b, t) => a + (b - a) * t;
export const remap = (x, a, b) => clamp((x - a) / (b - a));
export const smooth = (x) => x * x * (3 - 2 * x);
export const smoother = (x) => x * x * x * (x * (x * 6 - 15) + 10);
export const easeOutCubic = (x) => 1 - Math.pow(1 - x, 3);
export const easeInCubic = (x) => x * x * x;
export const easeInOutCubic = (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
export const easeOutExpo = (x) => (x >= 1 ? 1 : 1 - Math.pow(2, -10 * x));
export const easeInExpo = (x) => (x <= 0 ? 0 : Math.pow(2, 10 * x - 10));
export const easeInOutExpo = (x) => x <= 0 ? 0 : x >= 1 ? 1 : x < 0.5 ? Math.pow(2, 20 * x - 10) / 2 : (2 - Math.pow(2, -20 * x + 10)) / 2;
export const easeOutQuint = (x) => 1 - Math.pow(1 - x, 5);
export const easeInOutQuint = (x) => (x < 0.5 ? 16 * x ** 5 : 1 - Math.pow(-2 * x + 2, 5) / 2);
// CSS-style cubic bezier (x1,y1,x2,y2), solved by Newton iterations
export function bezier(x1, y1, x2, y2) {
  const A = (a, b) => 1 - 3 * b + 3 * a, B = (a, b) => 3 * b - 6 * a, C = (a) => 3 * a;
  const calc = (t, a, b) => ((A(a, b) * t + B(a, b)) * t + C(a)) * t;
  const slope = (t, a, b) => 3 * A(a, b) * t * t + 2 * B(a, b) * t + C(a);
  return (x) => {
    if (x <= 0) return 0; if (x >= 1) return 1;
    let t = x;
    for (let i = 0; i < 8; i++) { const s = slope(t, x1, x2); if (Math.abs(s) < 1e-6) break; t -= (calc(t, x1, x2) - x) / s; }
    return calc(clamp(t), y1, y2);
  };
}
export const cine = bezier(0.65, 0, 0.2, 1); // heavy start, long glide: "mass" curve
export const settle = bezier(0.16, 1, 0.3, 1); // fast arrival, long settle
// Damped spring response 0..1 (overshoot tuned by zeta)
export function spring(t, freq = 2.2, zeta = 0.55) {
  if (t <= 0) return 0;
  const w = 2 * Math.PI * freq, wd = w * Math.sqrt(1 - zeta * zeta);
  return 1 - Math.exp(-zeta * w * t) * (Math.cos(wd * t) + (zeta * w / wd) * Math.sin(wd * t));
}
// Keyframe track: [[t, value, ease?], ...]; value may be number or array
export function track(keys, t) {
  if (t <= keys[0][0]) return keys[0][1];
  for (let i = 1; i < keys.length; i++) {
    const [t1, v1, e] = keys[i];
    const [t0, v0] = keys[i - 1];
    if (t <= t1) {
      const k = (e || smoother)((t - t0) / (t1 - t0));
      if (Array.isArray(v0)) return v0.map((v, j) => lerp(v, v1[j], k));
      return lerp(v0, v1, k);
    }
  }
  return keys[keys.length - 1][1];
}
// Smooth catmull-rom camera path sampled with eased parameter
export function pathAt(points, u) {
  const curve = new THREE.CatmullRomCurve3(points.map((p) => new THREE.Vector3(...p)), false, 'centripetal');
  return curve.getPointAt(clamp(u));
}

// ---------- color ----------
export const col = (hex, mul = 1) => new THREE.Color(hex).multiplyScalar(mul);

// ---------- fonts & 3D text ----------
const fontCache = {};
export async function loadFont(name) {
  if (!fontCache[name]) {
    const data = await (await fetch(`/assets/fonts/${name}.json`)).json();
    const f = new Font(data);
    f.kerning = data.kerning || {};
    fontCache[name] = f;
  }
  return fontCache[name];
}

const glyphCache = new Map();
function glyphGeometry(font, ch, o) {
  const key = [font.data.familyName, font.data.resolution, ch, o.size, o.depth, o.bevel, o.curveSegments].join('|');
  if (glyphCache.has(key)) return glyphCache.get(key);
  const shapes = font.generateShapes(ch, o.size);
  let geo = null;
  if (shapes.length) {
    geo = new THREE.ExtrudeGeometry(shapes, {
      depth: o.depth, curveSegments: o.curveSegments, steps: 1,
      bevelEnabled: o.bevel > 0, bevelThickness: o.bevel, bevelSize: o.bevel * 0.75, bevelOffset: 0, bevelSegments: 4,
    });
    geo.translate(0, 0, -o.depth / 2);
    geo.computeVertexNormals();
  }
  glyphCache.set(key, geo);
  return geo;
}

/**
 * Real extruded, bevelled 3D text with per-letter meshes (for kinetic staggering).
 * Lines separated by '|'. Returns { group, letters, lines, width, height }.
 * materials: [frontFace, sides/bevel]
 */
export function text3D(str, font, opts = {}) {
  const o = Object.assign({ size: 1, depth: 0.15, bevel: 0.02, tracking: 0.04, lineHeight: 1.2, curveSegments: 8, align: 'center', materials: null }, opts);
  const scale = o.size / font.data.resolution;
  const group = new THREE.Group();
  const letters = [];
  const lines = str.split('|');
  const lineObjs = [];
  const H = o.size * o.lineHeight;
  lines.forEach((line, li) => {
    const chars = [...line];
    const lineGroup = new THREE.Group();
    let x = 0;
    const placed = [];
    chars.forEach((ch, ci) => {
      const g = font.data.glyphs[ch] || font.data.glyphs['?'];
      const geo = glyphGeometry(font, ch, o);
      if (geo) {
        geo.computeBoundingBox();
        const bb = geo.boundingBox;
        const cx = (bb.min.x + bb.max.x) / 2, cy = (bb.min.y + bb.max.y) / 2;
        const centered = geo.clone(); centered.translate(-cx, -cy, 0);
        const mesh = new THREE.Mesh(centered, o.materials);
        mesh.userData.base = new THREE.Vector3(x + cx, cy, 0);
        placed.push(mesh);
      }
      const kern = ci < chars.length - 1 ? (font.kerning[ch + chars[ci + 1]] || 0) : 0;
      x += (g.ha + kern) * scale + o.tracking * o.size;
    });
    const width = x - o.tracking * o.size;
    const off = o.align === 'center' ? -width / 2 : o.align === 'right' ? -width : 0;
    placed.forEach((m) => {
      m.userData.base.x += off;
      m.userData.base.y -= li * H;
      m.position.copy(m.userData.base);
      m.userData.line = li;
      lineGroup.add(m);
      letters.push(m);
    });
    group.add(lineGroup);
    lineObjs.push({ group: lineGroup, width, letters: placed });
  });
  // vertically center the block on cap height
  const capH = o.size * 0.7;
  const totalH = (lines.length - 1) * H + capH;
  const yShift = totalH / 2 - capH;
  letters.forEach((m) => { m.userData.base.y += yShift; m.position.y = m.userData.base.y; });
  return { group, letters, lines: lineObjs, width: Math.max(...lineObjs.map((l) => l.width)), height: totalH };
}

// Fit a text block to a target fraction of the visible frame width at a given distance.
export function visibleWidthAt(camera, dist) {
  const h = 2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * dist;
  return h * camera.aspect;
}

// ---------- procedural canvas textures ----------
function canvas(w, h) { const c = document.createElement('canvas'); c.width = w; c.height = h; return c; }

export function valueNoiseCanvas(size, seed, octaves = 5, base = 8) {
  const c = canvas(size, size), ctx = c.getContext('2d');
  const img = ctx.createImageData(size, size);
  const R = rng(seed);
  const grids = [];
  for (let o = 0; o < octaves; o++) { const n = base << o; const g = new Float32Array(n * n); for (let i = 0; i < g.length; i++) g[i] = R(); grids.push([n, g]); }
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    let v = 0, amp = 0.5, tot = 0;
    for (const [n, g] of grids) {
      const fx = (x / size) * n, fy = (y / size) * n;
      const x0 = Math.floor(fx), y0 = Math.floor(fy), tx = smooth(fx - x0), ty = smooth(fy - y0);
      const at = (i, j) => g[((j % n) * n) + (i % n)];
      const a = lerp(at(x0, y0), at(x0 + 1, y0), tx), b = lerp(at(x0, y0 + 1), at(x0 + 1, y0 + 1), tx);
      v += lerp(a, b, ty) * amp; tot += amp; amp *= 0.5;
    }
    const k = (v / tot) * 255, i = (y * size + x) * 4;
    img.data[i] = img.data[i + 1] = img.data[i + 2] = k; img.data[i + 3] = 255;
  }
  ctx.putImageData(img, 0, 0);
  return c;
}

export function tex(c, { repeat = 1, srgb = false, aniso = 8 } = {}) {
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(repeat, repeat);
  t.anisotropy = aniso;
  t.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
  t.needsUpdate = true;
  return t;
}

// Fine micro-surface roughness: mid-grey with faint noise + sparse scratches
export function microRoughness(seed = 7, size = 512, base = 0.5, amount = 0.25) {
  const c = valueNoiseCanvas(size, seed, 6, 16);
  const ctx = c.getContext('2d');
  const img = ctx.getImageData(0, 0, size, size);
  for (let i = 0; i < img.data.length; i += 4) {
    const v = base * 255 + (img.data[i] - 128) * amount;
    img.data[i] = img.data[i + 1] = img.data[i + 2] = v;
  }
  ctx.putImageData(img, 0, 0);
  const R = rng(seed + 1);
  ctx.globalAlpha = 0.18; ctx.strokeStyle = '#fff'; ctx.lineWidth = 0.6;
  for (let i = 0; i < 60; i++) {
    const x = R() * size, y = R() * size, a = R() * Math.PI, l = 10 + R() * 80;
    ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + Math.cos(a) * l, y + Math.sin(a) * l); ctx.stroke();
  }
  return c;
}

// Brushed metal streaks (for roughness/bump of brushed aluminium)
export function brushedCanvas(seed = 3, size = 1024) {
  const c = canvas(size, size), ctx = c.getContext('2d');
  ctx.fillStyle = '#808080'; ctx.fillRect(0, 0, size, size);
  const R = rng(seed);
  for (let i = 0; i < 9000; i++) {
    const y = R() * size, x = R() * size, l = 40 + R() * 400, v = Math.floor(100 + R() * 60);
    ctx.strokeStyle = `rgba(${v},${v},${v},${0.15 + R() * 0.3})`;
    ctx.lineWidth = 0.5 + R() * 1.2;
    ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + l, y + (R() - 0.5) * 0.6); ctx.stroke();
  }
  return c;
}

// Guilloche security engraving (rosettes + wave bands), drawn light-on-dark for bump maps
export function guilloche(ctx, x, y, w, h, seed = 1, { color = '#fff', alpha = 0.55, lines = 46, rosette = true } = {}) {
  const R = rng(seed);
  ctx.save();
  ctx.strokeStyle = color; ctx.globalAlpha = alpha; ctx.lineWidth = Math.max(0.6, w / 1400);
  const f1 = 3 + Math.floor(R() * 4), f2 = 7 + Math.floor(R() * 6);
  for (let i = 0; i < lines; i++) {
    const ph = (i / lines) * Math.PI * 2;
    ctx.beginPath();
    for (let s = 0; s <= 400; s++) {
      const u = s / 400;
      const yy = y + h / 2 + Math.sin(u * Math.PI * 2 * f1 + ph) * h * 0.32 + Math.sin(u * Math.PI * 2 * f2 - ph * 2) * h * 0.08;
      const xx = x + u * w;
      if (s === 0) ctx.moveTo(xx, yy); else ctx.lineTo(xx, yy);
    }
    ctx.stroke();
  }
  if (rosette) {
    const cx = x + w * 0.5, cy = y + h * 0.5, r0 = Math.min(w, h) * 0.42;
    for (let i = 0; i < 36; i++) {
      ctx.beginPath();
      const ph = (i / 36) * Math.PI * 2;
      for (let s = 0; s <= 720; s++) {
        const a = (s / 720) * Math.PI * 2;
        const r = r0 * (0.62 + 0.25 * Math.sin(a * 12 + ph) + 0.1 * Math.cos(a * 5 - ph * 3));
        const xx = cx + Math.cos(a) * r, yy = cy + Math.sin(a) * r;
        if (s === 0) ctx.moveTo(xx, yy); else ctx.lineTo(xx, yy);
      }
      ctx.stroke();
    }
  }
  ctx.restore();
}

export function makeCanvas(w, h) { return canvas(w, h); }

// ---------- environment maps ----------
/**
 * Dark studio with emissive softboxes, prefiltered with PMREM. Gives metals real, art-directed
 * reflections (strip lights read as long specular highlights on gold and chrome).
 * panels: [{ pos:[x,y,z], size:[w,h], color:'#fff', intensity: n, lookAt:[x,y,z] }]
 */
export function studioEnv(renderer, { panels = [], ambient = '#060608', floor = null } = {}) {
  const scene = new THREE.Scene();
  const room = new THREE.Mesh(new THREE.BoxGeometry(40, 24, 40), new THREE.MeshBasicMaterial({ color: ambient, side: THREE.BackSide }));
  room.position.y = 6;
  scene.add(room);
  if (floor) {
    const f = new THREE.Mesh(new THREE.PlaneGeometry(40, 40), new THREE.MeshBasicMaterial({ color: floor }));
    f.rotation.x = -Math.PI / 2; f.position.y = -5.9; scene.add(f);
  }
  for (const p of panels) {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(p.size[0], p.size[1]), new THREE.MeshBasicMaterial({ color: new THREE.Color(p.color || '#fff').multiplyScalar(p.intensity ?? 4), side: THREE.DoubleSide }));
    m.position.set(...p.pos);
    m.lookAt(...(p.lookAt || [0, 0, 0]));
    scene.add(m);
  }
  const pm = new THREE.PMREMGenerator(renderer);
  const rt = pm.fromScene(scene, 0.02);
  pm.dispose();
  return rt.texture;
}

// ---------- geometry helpers ----------
export function roundedRectShape(w, h, r) {
  const s = new THREE.Shape();
  const x = -w / 2, y = -h / 2;
  s.moveTo(x + r, y);
  s.lineTo(x + w - r, y); s.quadraticCurveTo(x + w, y, x + w, y + r);
  s.lineTo(x + w, y + h - r); s.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  s.lineTo(x + r, y + h); s.quadraticCurveTo(x, y + h, x, y + h - r);
  s.lineTo(x, y + r); s.quadraticCurveTo(x, y, x + r, y);
  return s;
}

// Classic event-ticket outline: rounded corners, semicircular side notches at the stub line
export function ticketShape(w, h, r, notchR, stubX) {
  const s = new THREE.Shape();
  const x0 = -w / 2, y0 = -h / 2, x1 = w / 2, y1 = h / 2;
  s.moveTo(x0 + r, y0);
  s.lineTo(stubX - notchR, y0);
  s.absarc(stubX, y0, notchR, Math.PI, 0, true);
  s.lineTo(x1 - r, y0); s.quadraticCurveTo(x1, y0, x1, y0 + r);
  s.lineTo(x1, y1 - r); s.quadraticCurveTo(x1, y1, x1 - r, y1);
  s.lineTo(stubX + notchR, y1);
  s.absarc(stubX, y1, notchR, 0, Math.PI, true);
  s.lineTo(x0 + r, y1); s.quadraticCurveTo(x0, y1, x0, y1 - r);
  s.lineTo(x0, y0 + r); s.quadraticCurveTo(x0, y0, x0 + r, y0);
  return s;
}

// Planar UVs mapped to the shape's bounding box (ExtrudeGeometry's default UVs are world units)
export function planarUV(geo, w, h) {
  const p = geo.attributes.position, uv = geo.attributes.uv;
  for (let i = 0; i < p.count; i++) uv.setXY(i, p.getX(i) / w + 0.5, p.getY(i) / h + 0.5);
  uv.needsUpdate = true;
}

// Sample N points uniformly over a mesh's surface (world space) - used for particle dissolve/reform
export function sampleSurface(mesh, n, seed = 1) {
  const R = rng(seed);
  const geo = mesh.geometry.index ? mesh.geometry.toNonIndexed() : mesh.geometry;
  const pos = geo.attributes.position;
  const tris = pos.count / 3;
  const areas = new Float32Array(tris);
  const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3(), t = new THREE.Vector3();
  let total = 0;
  for (let i = 0; i < tris; i++) {
    a.fromBufferAttribute(pos, i * 3); b.fromBufferAttribute(pos, i * 3 + 1); c.fromBufferAttribute(pos, i * 3 + 2);
    total += t.subVectors(b, a).cross(c.clone().sub(a)).length() / 2;
    areas[i] = total;
  }
  mesh.updateWorldMatrix(true, false);
  const out = new Float32Array(n * 3);
  for (let k = 0; k < n; k++) {
    const r = R() * total;
    let lo = 0, hi = tris - 1;
    while (lo < hi) { const m = (lo + hi) >> 1; if (areas[m] < r) lo = m + 1; else hi = m; }
    a.fromBufferAttribute(pos, lo * 3); b.fromBufferAttribute(pos, lo * 3 + 1); c.fromBufferAttribute(pos, lo * 3 + 2);
    let u = R(), v = R(); if (u + v > 1) { u = 1 - u; v = 1 - v; }
    t.copy(a).addScaledVector(b.clone().sub(a), u).addScaledVector(c.clone().sub(a), v).applyMatrix4(mesh.matrixWorld);
    out.set([t.x, t.y, t.z], k * 3);
  }
  return out;
}

// Dedicated typography lighting: a warm overhead gradient the letter faces always reflect, plus
// hard strip lights for bevel glints. Assigned as material.envMap so titles stay readable no
// matter how dark or how rotated the scene's own environment is.
let _titleEnv = null;
export function titleEnv(renderer) {
  if (_titleEnv) return _titleEnv;
  _titleEnv = studioEnv(renderer, {
    ambient: '#0d0a07',
    panels: [
      { pos: [0, 5.5, 12], size: [30, 5], color: '#fff1da', intensity: 2.8 },
      { pos: [0, 1.0, 12.1], size: [30, 4], color: '#ffe4bd', intensity: 1.9 },
      { pos: [0, -3.0, 12.2], size: [30, 4], color: '#e9bd7c', intensity: 1.0 },
      { pos: [0, 0.2, 11.8], size: [30, 0.35], color: '#fff6e6', intensity: 7 },
      { pos: [-11, 2, 6], size: [0.8, 16], color: '#ffffff', intensity: 14 },
      { pos: [11, 0, 6], size: [0.8, 16], color: '#ffe6bd', intensity: 10 },
      { pos: [0, -8, 8], size: [26, 4], color: '#4a3013', intensity: 1 },
      { pos: [0, 12, -2], size: [10, 1], color: '#ffffff', intensity: 8 },
    ],
  });
  return _titleEnv;
}
