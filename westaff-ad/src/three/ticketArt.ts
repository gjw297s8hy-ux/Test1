import * as THREE from 'three';
import {BRAND} from '../brand';
import {TICKET} from './ticket';

export type TicketKind = 'master' | 'football' | 'concert' | 'show';
const W = 1024, H = 2560;
const PERF_Y = H * (1 - TICKET.stubRatio);

const goldGrad = (g: CanvasRenderingContext2D, x0: number, y0: number, x1: number, y1: number) => {
  const gr = g.createLinearGradient(x0, y0, x1, y1);
  gr.addColorStop(0, '#fbe3a6'); gr.addColorStop(0.35, '#e0ac52'); gr.addColorStop(0.6, '#fff1c8'); gr.addColorStop(1, '#b8862f');
  return gr;
};

const spaced = (g: CanvasRenderingContext2D, text: string, x: number, y: number, spacing: number) => {
  const chars = [...text];
  const widths = chars.map((c) => g.measureText(c).width);
  const total = widths.reduce((a, b) => a + b, 0) + spacing * (chars.length - 1);
  let cx = x - total / 2;
  chars.forEach((c, i) => { g.fillText(c, cx, y); cx += widths[i] + spacing; });
};

/** Icônes dessinées (aucun logo protégé). */
const icon = (g: CanvasRenderingContext2D, kind: TicketKind, cx: number, cy: number, R: number) => {
  g.save(); g.translate(cx, cy);
  g.strokeStyle = goldGrad(g, -R, -R, R, R); g.fillStyle = g.strokeStyle; g.lineWidth = R * 0.07; g.lineJoin = 'round'; g.lineCap = 'round';
  if (kind === 'football') {
    g.beginPath(); g.arc(0, 0, R, 0, Math.PI * 2); g.stroke();
    const pent = (r: number, rot: number) => { g.beginPath(); for (let i = 0; i < 5; i++) { const a = rot + (i * 2 * Math.PI) / 5; g.lineTo(Math.cos(a) * r, Math.sin(a) * r); } g.closePath(); };
    pent(R * 0.36, -Math.PI / 2); g.fill();
    for (let i = 0; i < 5; i++) {
      const a = -Math.PI / 2 + (i * 2 * Math.PI) / 5;
      g.beginPath(); g.moveTo(Math.cos(a) * R * 0.36, Math.sin(a) * R * 0.36); g.lineTo(Math.cos(a) * R * 0.72, Math.sin(a) * R * 0.72); g.stroke();
      g.save(); g.translate(Math.cos(a) * R * 0.86, Math.sin(a) * R * 0.86); g.beginPath();
      for (let k = 0; k < 5; k++) { const b = a + Math.PI + (k * 2 * Math.PI) / 5; g.lineTo(Math.cos(b) * R * 0.2, Math.sin(b) * R * 0.2); }
      g.closePath(); g.fill(); g.restore();
    }
  } else if (kind === 'concert') {
    g.lineWidth = R * 0.11;
    g.beginPath(); g.moveTo(-R * 0.35, R * 0.55); g.lineTo(-R * 0.35, -R * 0.62); g.lineTo(R * 0.62, -R * 0.82); g.lineTo(R * 0.62, R * 0.35); g.stroke();
    g.beginPath(); g.moveTo(-R * 0.35, -R * 0.38); g.lineTo(R * 0.62, -R * 0.58); g.stroke();
    g.beginPath(); g.ellipse(-R * 0.58, R * 0.58, R * 0.27, R * 0.2, -0.4, 0, Math.PI * 2); g.fill();
    g.beginPath(); g.ellipse(R * 0.39, R * 0.38, R * 0.27, R * 0.2, -0.4, 0, Math.PI * 2); g.fill();
    g.lineWidth = R * 0.04; g.globalAlpha = 0.6;
    for (let i = 1; i <= 3; i++) { g.beginPath(); g.arc(-R * 0.1, 0, R * (0.9 + i * 0.18), -0.5, 0.5); g.stroke(); g.beginPath(); g.arc(R * 0.1, 0, R * (0.9 + i * 0.18), Math.PI - 0.5, Math.PI + 0.5); g.stroke(); }
  } else if (kind === 'show') {
    const mask = (sx: number, sad: boolean) => {
      g.save(); g.translate(sx, sad ? R * 0.15 : -R * 0.1); g.rotate(sad ? 0.25 : -0.2);
      g.beginPath(); g.moveTo(-R * 0.5, -R * 0.55); g.quadraticCurveTo(0, -R * 0.7, R * 0.5, -R * 0.55);
      g.quadraticCurveTo(R * 0.55, R * 0.45, 0, R * 0.7); g.quadraticCurveTo(-R * 0.55, R * 0.45, -R * 0.5, -R * 0.55); g.closePath();
      g.fill(); g.globalCompositeOperation = 'destination-out';
      g.beginPath(); g.ellipse(-R * 0.2, -R * 0.15, R * 0.11, R * 0.07, sad ? 0.3 : -0.3, 0, Math.PI * 2); g.fill();
      g.beginPath(); g.ellipse(R * 0.2, -R * 0.15, R * 0.11, R * 0.07, sad ? -0.3 : 0.3, 0, Math.PI * 2); g.fill();
      g.lineWidth = R * 0.08; g.beginPath();
      if (sad) g.arc(0, R * 0.42, R * 0.2, Math.PI * 1.15, Math.PI * 1.85); else g.arc(0, R * 0.12, R * 0.22, Math.PI * 0.15, Math.PI * 0.85);
      g.stroke(); g.restore();
    };
    mask(-R * 0.32, false); mask(R * 0.36, true);
  } else {
    // pass "master" : étoile + trois pictos
    g.beginPath();
    for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + (i * Math.PI) / 5, r = i % 2 ? R * 0.42 : R; g.lineTo(Math.cos(a) * r, Math.sin(a) * r); }
    g.closePath(); g.stroke();
    g.lineWidth = R * 0.03; g.beginPath(); g.arc(0, 0, R * 1.25, 0, Math.PI * 2); g.stroke();
  }
  g.restore();
};

const artCache = new Map<string, THREE.CanvasTexture>();
export const makeTicketArt = (kind: TicketKind, accent = BRAND.colors.gold) => {
  const key = kind + accent; if (artCache.has(key)) return artCache.get(key)!;
  const c = document.createElement('canvas'); c.width = W; c.height = H;
  const g = c.getContext('2d')!;
  // fond profond
  const bg = g.createLinearGradient(0, 0, 0, H); bg.addColorStop(0, '#0d0c14'); bg.addColorStop(1, '#040407');
  g.fillStyle = bg; g.fillRect(0, 0, W, H);
  // lueurs holographiques
  const glow = (x: number, y: number, r: number, col: string, a: number) => {
    const gr = g.createRadialGradient(x, y, 0, x, y, r); gr.addColorStop(0, col); gr.addColorStop(1, 'rgba(0,0,0,0)');
    g.globalAlpha = a; g.fillStyle = gr; g.fillRect(0, 0, W, H); g.globalAlpha = 1;
  };
  glow(W * 0.15, H * 0.2, 900, accent, 0.35); glow(W * 0.95, H * 0.55, 800, BRAND.colors.violet, 0.28); glow(W * 0.3, H * 0.95, 700, BRAND.colors.electric, 0.22);
  // guilloches (sécurité billet)
  g.strokeStyle = 'rgba(232,185,100,0.13)'; g.lineWidth = 2;
  for (let k = 0; k < 26; k++) {
    g.beginPath();
    for (let x = 0; x <= W; x += 8) g.lineTo(x, 380 + k * 52 + Math.sin(x / 70 + k * 0.6) * 22 + Math.sin(x / 23 + k) * 6);
    g.stroke();
  }
  // cadre
  g.strokeStyle = goldGrad(g, 0, 0, W, H); g.lineWidth = 6;
  g.beginPath(); (g as any).roundRect(46, 46, W - 92, PERF_Y - 92, 40); g.stroke();
  g.lineWidth = 2; g.beginPath(); (g as any).roundRect(66, 66, W - 132, PERF_Y - 132, 30); g.stroke();
  // en-tête marque
  g.fillStyle = goldGrad(g, 0, 140, W, 220); g.font = '800 54px WBold'; g.textBaseline = 'alphabetic';
  spaced(g, `${BRAND.name} ${BRAND.nameSub}`, W / 2, 205, 14);
  g.fillRect(W / 2 - 160, 250, 320, 4);
  // icône
  icon(g, kind, W / 2, 760, 250);
  // titre
  const title = kind === 'master' ? 'PASS' : BRAND.categories.find((x) => x.key === (kind === 'show' ? 'show' : kind))!.label;
  g.fillStyle = '#ffffff'; g.font = `900 ${title.length > 8 ? 132 : 170}px WDisplay`;
  spaced(g, title, W / 2, 1300, 6);
  g.fillStyle = goldGrad(g, 0, 1340, W, 1400); g.font = '600 40px WSemi';
  spaced(g, kind === 'master' ? 'FOOTBALL · CONCERTS · SPECTACLES' : 'ACCÈS ÉVÉNEMENT', W / 2, 1385, 8);
  // infos placement (décoratives, sans prix)
  const cols = [['ACCÈS', kind === 'football' ? 'TRIBUNE' : kind === 'concert' ? 'FOSSE' : kind === 'show' ? 'ORCHESTRE' : 'VIP'], ['RANG', 'A'], ['PLACE', '01']];
  cols.forEach(([l, v], i) => {
    const x = 170 + i * 342;
    g.fillStyle = 'rgba(232,185,100,0.75)'; g.font = '600 34px WSemi'; spaced(g, l, x, 1560, 6);
    g.fillStyle = '#fff'; g.font = '800 64px WBold'; spaced(g, v, x, 1650, 2);
  });
  // perforation
  g.strokeStyle = 'rgba(232,185,100,0.6)'; g.setLineDash([22, 18]); g.lineWidth = 5;
  g.beginPath(); g.moveTo(80, PERF_Y); g.lineTo(W - 80, PERF_Y); g.stroke(); g.setLineDash([]);
  // talon : code-barres + admit one
  let s = 99; const r = () => ((s = (s * 16807) % 2147483647) / 2147483647);
  g.fillStyle = goldGrad(g, 0, PERF_Y, W, H);
  let x = 160; while (x < W - 160) { const bw = 3 + Math.floor(r() * 4) * 3; g.fillRect(x, PERF_Y + 120, bw, 300); x += bw + 5 + Math.floor(r() * 3) * 4; }
  g.font = '800 46px WBold'; spaced(g, 'ADMIT ONE', W / 2, PERF_Y + 520, 18);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 8;
  artCache.set(key, tex);
  return tex;
};

/** Dos du billet : motif monogramme. */
let backTex: THREE.CanvasTexture | null = null;
export const makeTicketBack = () => {
  if (backTex) return backTex;
  const c = document.createElement('canvas'); c.width = 512; c.height = 1280;
  const g = c.getContext('2d')!;
  g.fillStyle = '#0a0910'; g.fillRect(0, 0, 512, 1280);
  g.strokeStyle = 'rgba(232,185,100,0.25)'; g.lineWidth = 2;
  for (let i = -1280; i < 1280; i += 28) { g.beginPath(); g.moveTo(i, 0); g.lineTo(i + 1280, 1280); g.stroke(); }
  g.fillStyle = 'rgba(232,185,100,0.85)'; g.font = '900 120px WDisplay'; g.textAlign = 'center';
  g.fillText('W', 256, 700);
  backTex = new THREE.CanvasTexture(c); backTex.colorSpace = THREE.SRGBColorSpace;
  return backTex;
};
