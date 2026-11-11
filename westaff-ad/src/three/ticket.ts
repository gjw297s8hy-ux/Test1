import * as THREE from 'three';

/** Dimensions du billet (portrait, unités monde). */
export const TICKET = {w: 0.9, h: 2.25, r: 0.07, notchR: 0.07, stubRatio: 0.258, depth: 0.018};

/** Contour du billet : coins arrondis, encoches latérales et perforations réelles (trous). */
export const ticketShape = (w = TICKET.w, h = TICKET.h, withHoles = true) => {
  const {r, notchR} = TICKET;
  const ny = -h / 2 + h * TICKET.stubRatio;
  const s = new THREE.Shape();
  s.moveTo(-w / 2 + r, -h / 2);
  s.lineTo(w / 2 - r, -h / 2);
  s.absarc(w / 2 - r, -h / 2 + r, r, -Math.PI / 2, 0, false);
  s.lineTo(w / 2, ny - notchR);
  s.absarc(w / 2, ny, notchR, -Math.PI / 2, Math.PI / 2, true);
  s.lineTo(w / 2, h / 2 - r);
  s.absarc(w / 2 - r, h / 2 - r, r, 0, Math.PI / 2, false);
  s.lineTo(-w / 2 + r, h / 2);
  s.absarc(-w / 2 + r, h / 2 - r, r, Math.PI / 2, Math.PI, false);
  s.lineTo(-w / 2, ny + notchR);
  s.absarc(-w / 2, ny, notchR, Math.PI / 2, -Math.PI / 2, true);
  s.lineTo(-w / 2, -h / 2 + r);
  s.absarc(-w / 2 + r, -h / 2 + r, r, Math.PI, Math.PI * 1.5, false);
  if (withHoles) {
    const n = 11, span = w - 2 * notchR - 0.08;
    for (let i = 0; i < n; i++) {
      const hole = new THREE.Path();
      hole.absarc(-span / 2 + (span * i) / (n - 1), ny, 0.011, 0, Math.PI * 2, true);
      s.holes.push(hole);
    }
  }
  return s;
};

const remapUV = (geo: THREE.BufferGeometry, w: number, h: number) => {
  const p = geo.attributes.position, uv = geo.attributes.uv;
  for (let i = 0; i < p.count; i++) uv.setXY(i, (p.getX(i) + w / 2) / w, (p.getY(i) + h / 2) / h);
  uv.needsUpdate = true;
};

let cache: {body: THREE.ExtrudeGeometry; face: THREE.ShapeGeometry} | null = null;
/** Corps extrudé (tranche dorée biseautée) + face avant (artwork). */
export const ticketGeometries = () => {
  if (cache) return cache;
  const {w, h, depth} = TICKET;
  const body = new THREE.ExtrudeGeometry(ticketShape(), {
    depth, bevelEnabled: true, bevelThickness: 0.006, bevelSize: 0.006, bevelSegments: 3, curveSegments: 20,
  });
  body.translate(0, 0, -depth / 2);
  remapUV(body, w, h);
  const face = new THREE.ShapeGeometry(ticketShape(w - 0.012, h - 0.012), 20);
  remapUV(face, w - 0.012, h - 0.012);
  cache = {body, face};
  return cache;
};
export const FACE_Z = TICKET.depth / 2 + 0.0065;
