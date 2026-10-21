// Premium ticket factory: real bevelled geometry with notches + procedurally drawn PBR maps
// (albedo, roughness/metalness, bump) so foil, engraving and lacquer respond to light physically.
import * as THREE from 'three';
import { makeCanvas, rng, guilloche, planarUV, text3D, titleEnv } from '../../src/engine/lib.js';
import { gold, GOLD } from '../../materials/materials.js';

let fontsLoaded = null;
export function loadCssFonts() {
  if (!fontsLoaded) {
    const faces = [
      ['Cinzel', '/node_modules/@fontsource/cinzel/files/cinzel-latin-700-normal.woff2', '700'],
      ['Cinzel', '/node_modules/@fontsource/cinzel/files/cinzel-latin-900-normal.woff2', '900'],
      ['Montserrat', '/node_modules/@fontsource/montserrat/files/montserrat-latin-600-normal.woff2', '600'],
      ['Montserrat', '/node_modules/@fontsource/montserrat/files/montserrat-latin-800-normal.woff2', '800'],
    ];
    fontsLoaded = Promise.all(faces.map(async ([fam, url, weight]) => { const f = new FontFace(fam, `url(${url})`, { weight }); await f.load(); document.fonts.add(f); }));
  }
  return fontsLoaded;
}

// Portrait ticket outline: rounded corners, semicircular notches on both long edges at the stub line.
export function ticketShapeV(w, h, r, nr, stubY) {
  const s = new THREE.Shape();
  const x0 = -w / 2, x1 = w / 2, y0 = -h / 2, y1 = h / 2;
  s.moveTo(x0 + r, y0);
  s.lineTo(x1 - r, y0); s.quadraticCurveTo(x1, y0, x1, y0 + r);
  s.lineTo(x1, stubY - nr); s.absarc(x1, stubY, nr, -Math.PI / 2, Math.PI / 2, true);
  s.lineTo(x1, y1 - r); s.quadraticCurveTo(x1, y1, x1 - r, y1);
  s.lineTo(x0 + r, y1); s.quadraticCurveTo(x0, y1, x0, y1 - r);
  s.lineTo(x0, stubY + nr); s.absarc(x0, stubY, nr, Math.PI / 2, -Math.PI / 2, true);
  s.lineTo(x0, y0 + r); s.quadraticCurveTo(x0, y0, x0 + r, y0);
  return s;
}

const KIND = {
  hero: { title: 'WESTAFF PLACE', label: 'PASS', accent: null, style: 'gold' },
  football: { title: 'WESTAFF PLACE', label: 'FOOTBALL', accent: '#126BFF', style: 'black' },
  concert: { title: 'WESTAFF PLACE', label: 'CONCERT', accent: '#772BFF', style: 'black' },
  spectacle: { title: 'WESTAFF PLACE', label: 'SPECTACLE', accent: '#B0182E', style: 'black' },
};

/*
 * Each map is painted with the same layout. "Layers" carry semantic material ids:
 *   base  - card body (gold metal for hero, black lacquer for others)
 *   foil  - raised polished gold foil
 *   etch  - recessed engraving (rougher, lower)
 *   ink   - accent enamel (dielectric colour)
 */
function painter(map, style, accent) {
  const gold = style === 'gold';
  const P = {
    color: { base: gold ? '#E2BA64' : '#09090c', foil: '#F0CD7C', etch: gold ? '#B98E3E' : '#C9A050', ink: accent || '#E2BA64' },
    // R unused, G = roughness, B = metalness
    orm: { base: gold ? 'rgb(0,70,255)' : 'rgb(0,40,0)', foil: 'rgb(0,38,255)', etch: gold ? 'rgb(0,130,255)' : 'rgb(0,90,255)', ink: 'rgb(0,80,0)' },
    bump: { base: '#000', foil: '#9a9a9a', etch: '#3a3a3a', ink: '#4a4a4a' },
  }[map];
  return (k) => P[k];
}

function drawTicket(ctx, W, H, kind, map, stubFrac) {
  const k = KIND[kind];
  const paint = painter(map, k.style, k.accent);
  const R = rng(kind.length * 97 + 3);
  ctx.fillStyle = map === 'bump' ? (k.style === 'gold' ? '#202020' : '#000') : paint('base');
  if (map === 'bump') ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, W, H);
  const stubY = H * (1 - stubFrac);
  const m = 44;
  // guilloche security field (etched) - upper and stub
  const etch = paint('etch');
  guilloche(ctx, m + 20, H * 0.2, W - 2 * m - 40, H * 0.36, 11 + kind.length, { color: etch, alpha: map === 'color' ? (k.style === 'gold' ? 0.9 : 0.5) : 1, lines: 54 });
  guilloche(ctx, m + 20, stubY + 40, W - 2 * m - 40, H - stubY - 100, 29 + kind.length, { color: etch, alpha: map === 'color' ? 0.6 : 1, lines: 30, rosette: false });
  // foil double border with corner ornaments
  ctx.strokeStyle = paint('foil'); ctx.fillStyle = paint('foil');
  ctx.lineWidth = 7; ctx.strokeRect(m, m, W - 2 * m, H - 2 * m);
  ctx.lineWidth = 2.5; ctx.strokeRect(m + 18, m + 18, W - 2 * m - 36, H - 2 * m - 36);
  for (const [cx, cy] of [[m + 18, m + 18], [W - m - 18, m + 18], [m + 18, H - m - 18], [W - m - 18, H - m - 18]]) {
    ctx.beginPath(); ctx.arc(cx, cy, 16, 0, Math.PI * 2); ctx.fill();
  }
  // micro-text engraving along the inner border
  ctx.save();
  ctx.fillStyle = etch; ctx.font = '600 13px Montserrat'; ctx.textBaseline = 'middle';
  const micro = 'WESTAFF PLACE • '.repeat(40);
  ctx.fillText(micro, m + 40, m + 32, W - 2 * m - 80);
  ctx.fillText(micro, m + 40, H - m - 32, W - 2 * m - 80);
  ctx.restore();
  // header
  ctx.fillStyle = paint('foil'); ctx.textAlign = 'center'; ctx.textBaseline = 'alphabetic';
  ctx.font = '700 78px Cinzel'; ctx.fillText('WESTAFF', W / 2, 205);
  ctx.font = '600 44px Montserrat';
  ctx.save(); ctx.translate(W / 2, 262); ctx.fillText('P  L  A  C  E', 0, 0); ctx.restore();
  ctx.fillRect(W * 0.2, 290, W * 0.6, 3);
  // emblem
  const cx = W / 2, cy = H * 0.38;
  ctx.lineWidth = 6; ctx.strokeStyle = paint('foil');
  ctx.beginPath(); ctx.arc(cx, cy, 250, 0, Math.PI * 2); ctx.stroke();
  ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(cx, cy, 228, 0, Math.PI * 2); ctx.stroke();
  for (let i = 0; i < 72; i++) { // engraved tick ring
    const a = (i / 72) * Math.PI * 2;
    ctx.beginPath(); ctx.moveTo(cx + Math.cos(a) * 232, cy + Math.sin(a) * 232); ctx.lineTo(cx + Math.cos(a) * (i % 6 ? 242 : 250), cy + Math.sin(a) * (i % 6 ? 242 : 250)); ctx.stroke();
  }
  drawMotif(ctx, kind, cx, cy, paint);
  // label is real extruded geometry (see makeTicket); only the accent rule is painted
  ctx.textAlign = 'center';
  if (k.accent) { ctx.fillStyle = paint('ink'); ctx.fillRect(W * 0.32, H * 0.64, W * 0.36, 8); }
  ctx.fillStyle = paint('foil'); ctx.font = '600 30px Montserrat';
  ctx.fillText('FOOTBALL  •  CONCERTS  •  SPECTACLES', W / 2, H * 0.69, W - 2 * m - 80);
  // perforation line (engraved holes) at the stub
  ctx.fillStyle = map === 'bump' ? '#000' : (map === 'orm' ? 'rgb(0,200,0)' : '#020202');
  for (let x = m + 30; x < W - m - 20; x += 26) { ctx.beginPath(); ctx.arc(x, stubY, 6, 0, Math.PI * 2); ctx.fill(); }
  // stub
  ctx.fillStyle = paint('foil'); ctx.font = '700 64px Cinzel'; ctx.fillText('ENTRÉE', W / 2, stubY + 150);
  ctx.font = '600 30px Montserrat';
  ctx.fillText('N°  ' + String(1 + Math.floor(R() * 89999)).padStart(5, '0'), W / 2, stubY + 215);
}

function drawMotif(ctx, kind, cx, cy, paint) {
  ctx.save();
  ctx.strokeStyle = paint('foil'); ctx.fillStyle = paint('foil'); ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  if (kind === 'hero') {
    ctx.font = '900 300px Cinzel'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText('W', cx, cy + 14);
    ctx.lineWidth = 3;
    for (let i = 0; i < 24; i++) { const a = (i / 24) * Math.PI * 2; ctx.beginPath(); ctx.moveTo(cx + Math.cos(a) * 175, cy + Math.sin(a) * 175); ctx.lineTo(cx + Math.cos(a) * 205, cy + Math.sin(a) * 205); ctx.stroke(); }
  } else if (kind === 'football') {
    // stylised pitch + ball (generic, no club or league marks)
    ctx.lineWidth = 6;
    ctx.strokeRect(cx - 120, cy - 180, 240, 360);
    ctx.beginPath(); ctx.moveTo(cx - 120, cy); ctx.lineTo(cx + 120, cy); ctx.stroke();
    ctx.beginPath(); ctx.arc(cx, cy, 52, 0, Math.PI * 2); ctx.stroke();
    ctx.strokeRect(cx - 60, cy - 180, 120, 60); ctx.strokeRect(cx - 60, cy + 120, 120, 60);
    ctx.strokeStyle = paint('ink'); ctx.lineWidth = 4;
    ctx.beginPath(); ctx.arc(cx, cy, 30, 0, Math.PI * 2); ctx.stroke();
  } else if (kind === 'concert') {
    // equaliser bars + waveform
    for (let i = -6; i <= 6; i++) {
      const h = 40 + 150 * Math.abs(Math.sin(i * 0.9 + 0.4)) * (1 - Math.abs(i) / 9);
      ctx.fillStyle = i % 3 === 0 ? paint('ink') : paint('foil');
      ctx.fillRect(cx + i * 30 - 9, cy - h / 2, 18, h);
    }
    ctx.lineWidth = 3; ctx.strokeStyle = paint('foil'); ctx.beginPath();
    for (let x = -200; x <= 200; x += 4) { const y = Math.sin(x * 0.06) * 30 * Math.exp(-(x * x) / 24000); x === -200 ? ctx.moveTo(cx + x, cy + 150 + y) : ctx.lineTo(cx + x, cy + 150 + y); }
    ctx.stroke();
  } else if (kind === 'spectacle') {
    // two theatre masks (line art) under a curtain swag
    const mask = (ox, smile) => {
      ctx.beginPath(); ctx.ellipse(cx + ox, cy, 72, 96, 0, 0, Math.PI * 2); ctx.lineWidth = 6; ctx.stroke();
      ctx.beginPath(); ctx.ellipse(cx + ox - 26, cy - 22, 15, 9, smile ? -0.3 : 0.3, 0, Math.PI * 2); ctx.fill();
      ctx.beginPath(); ctx.ellipse(cx + ox + 26, cy - 22, 15, 9, smile ? 0.3 : -0.3, 0, Math.PI * 2); ctx.fill();
      ctx.beginPath(); smile ? ctx.arc(cx + ox, cy + 18, 34, 0.15 * Math.PI, 0.85 * Math.PI) : ctx.arc(cx + ox, cy + 62, 34, 1.15 * Math.PI, 1.85 * Math.PI); ctx.stroke();
    };
    mask(-62, true); mask(62, false);
    ctx.strokeStyle = paint('ink'); ctx.lineWidth = 5;
    ctx.beginPath(); ctx.moveTo(cx - 200, cy - 150); ctx.quadraticCurveTo(cx, cy - 60, cx + 200, cy - 150); ctx.stroke();
  }
  ctx.restore();
}

const mapCache = {};
function ticketMaps(kind, stubFrac) {
  if (mapCache[kind]) return mapCache[kind];
  const W = 1024, H = 2048;
  const mk = (map, cs) => {
    const c = makeCanvas(W, H);
    drawTicket(c.getContext('2d'), W, H, kind, map, stubFrac);
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = cs; t.anisotropy = 8; t.needsUpdate = true;
    return t;
  };
  mapCache[kind] = { color: mk('color', THREE.SRGBColorSpace), orm: mk('orm', THREE.NoColorSpace), bump: mk('bump', THREE.NoColorSpace) };
  return mapCache[kind];
}

/**
 * Build a ticket. Returns a Group (pivot at ticket centre, face toward +Z).
 * opts: kind, width, height, depth, labelFont (Font for real extruded label)
 */
export async function makeTicket(kind = 'hero', { width = 1.5, height = 3.0, depth = 0.035, labelFont = null, renderer = null } = {}) {
  await loadCssFonts();
  const stubFrac = 0.2;
  const stubY = -height / 2 + height * stubFrac;
  const shape = ticketShapeV(width, height, 0.08, 0.085, stubY);
  const bevel = 0.012;
  const geo = new THREE.ExtrudeGeometry(shape, { depth, bevelEnabled: true, bevelThickness: bevel, bevelSize: bevel * 0.8, bevelSegments: 4, curveSegments: 24 });
  geo.translate(0, 0, -depth / 2);
  planarUV(geo, width + bevel * 1.6, height + bevel * 1.6);
  // split caps into back (first half) and front (second half)
  const caps = geo.groups.find((g) => g.materialIndex === 0);
  const half = caps.count / 2;
  geo.clearGroups();
  geo.addGroup(caps.start, half, 2);
  geo.addGroup(caps.start + half, half, 0);
  geo.addGroup(caps.start + caps.count, geo.attributes.position.count - caps.count, 1);
  geo.computeVertexNormals();

  const maps = ticketMaps(kind, stubFrac);
  const isGold = KIND[kind].style === 'gold';
  const face = new THREE.MeshPhysicalMaterial({
    map: maps.color, roughnessMap: maps.orm, metalnessMap: maps.orm, roughness: 1, metalness: 1,
    bumpMap: maps.bump, bumpScale: isGold ? 2.2 : 0.7, clearcoat: isGold ? 0.15 : 0.9, clearcoatRoughness: 0.06,
  });
  const edge = gold({ roughness: 0.14 });
  const back = isGold ? gold({ roughness: 0.32 }) : new THREE.MeshPhysicalMaterial({ color: '#0b0b0e', roughness: 0.3, clearcoat: 1, clearcoatRoughness: 0.08 });
  if (renderer) [face, edge].forEach((m) => { m.envMap = titleEnv(renderer); m.envMapIntensity = 0.9; });
  const mesh = new THREE.Mesh(geo, [face, edge, back]);
  const g = new THREE.Group();
  g.add(mesh);
  g.userData = { mesh, width, height, depth, kind };
  // real embossed (extruded) label sitting on the foil
  if (labelFont && kind !== 'hero') {
    const lm = [gold({ roughness: 0.22, color: '#EBC777' }), gold({ roughness: 0.1, color: '#EBC777' })];
    if (renderer) lm.forEach((m) => (m.envMap = titleEnv(renderer)));
    const t = text3D(KIND[kind].label, labelFont, { size: 0.15, depth: 0.012, bevel: 0.004, tracking: 0.06, materials: lm });
    const fit = (width * 0.8) / t.width;
    if (fit < 1) t.group.scale.set(fit, fit, 1);
    t.group.position.set(0, height * 0.5 - height * 0.62 + 0.06, depth / 2 + 0.016);
    // the painted label is replaced by the real one; hide painted one by covering is unnecessary - same position, same colour
    g.add(t.group);
    g.userData.label = t;
  }
  return g;
}
