// SCENE 4 — 00:14–00:18 — THEATRICAL GRANDEUR
// Gold proscenium, crimson velvet traveler curtains with procedurally animated folds,
// valance with gold fringe, balconies with warm sconces, dust in the spotlights, two polished
// gold masks (comedy / tragedy, modelled from signed-distance outlines) rotating in space.
// The curtains part to reveal a luminous ticket portal.
import * as THREE from 'three';
import { rng, track, cine, settle, remap, smoother, studioEnv, makeCanvas, clamp, easeInCubic } from '../src/engine/lib.js';
import { beamMaterial, beam, aimBeam, particleField, glint } from '../shaders/fx.js';
import { gold, velvet, emissive } from '../materials/materials.js';
import { ticketShapeV } from './common/ticket.js';
import { makeTitle } from './common/title.js';
import { noiseGLSL } from '../shaders/noise.glsl.js';

// ---------- masks ----------
const sdEllipse = (x, y, cx, cy, rx, ry, rot = 0) => {
  const c = Math.cos(rot), s = Math.sin(rot);
  const dx = x - cx, dy = y - cy;
  const u = (dx * c + dy * s) / rx, v = (-dx * s + dy * c) / ry;
  return (Math.hypot(u, v) - 1) * Math.min(rx, ry);
};
function maskSDF(kind) {
  const smile = kind === 'comedy';
  return (x, y) => {
    // face: wide brow, tapered chin
    const taper = 1 - 0.28 * clamp((-y) / 0.65);
    const face = sdEllipse(x / taper, y, 0, 0, 0.5, 0.66);
    const eyeTilt = smile ? 0.35 : -0.35;
    const e1 = sdEllipse(x, y, -0.19, 0.14, 0.11, 0.055, eyeTilt);
    const e2 = sdEllipse(x, y, 0.19, 0.14, 0.11, 0.055, -eyeTilt);
    let mouth;
    if (smile) mouth = Math.max(sdEllipse(x, y, 0, -0.18, 0.27, 0.2), -sdEllipse(x, y, 0, -0.08, 0.3, 0.17));
    else mouth = Math.max(sdEllipse(x, y, 0, -0.42, 0.25, 0.18), -sdEllipse(x, y, 0, -0.52, 0.28, 0.17));
    return Math.max(face, -e1, -e2, -mouth);
  };
}
function maskHeight(kind, x, y) {
  const smile = kind === 'comedy';
  const dome = 0.26 * Math.sqrt(Math.max(0, 1 - (x / 0.56) ** 2 - (y / 0.72) ** 2));
  const g = (cx, cy, sx, sy, a) => a * Math.exp(-(((x - cx) / sx) ** 2) - (((y - cy) / sy) ** 2));
  let h = dome;
  h += g(0, -0.04, 0.05, 0.16, 0.07);                  // nose ridge
  h += g(0, -0.17, 0.08, 0.05, 0.03);                  // nose tip
  const browY = smile ? 0.29 : 0.27;
  h += g(-0.19, browY + (smile ? 0 : 0.0) + x * (smile ? 0 : -0.25), 0.15, 0.035, 0.04);
  h += g(0.19, browY + x * (smile ? 0 : 0.25), 0.15, 0.035, 0.04);
  if (smile) { h += g(-0.27, -0.06, 0.1, 0.08, 0.045); h += g(0.27, -0.06, 0.1, 0.08, 0.045); }
  else { h += g(-0.22, -0.3, 0.09, 0.12, 0.02); h += g(0.22, -0.3, 0.09, 0.12, 0.02); }
  return h;
}
function maskGeometry(kind, res = 220) {
  const sdf = maskSDF(kind);
  const W = 1.2, H = 1.5, nx = res, ny = Math.round(res * H / W);
  const verts = [], index = [], map = new Int32Array((nx + 1) * (ny + 1)).fill(-1);
  const P = (i, j) => [-W / 2 + (i / nx) * W, -H / 2 + (j / ny) * H];
  const vid = (i, j) => {
    const k = j * (nx + 1) + i;
    if (map[k] < 0) {
      let [x, y] = P(i, j);
      // project boundary vertices onto the zero contour (smooth outline, no stair-stepping)
      for (let it = 0; it < 4; it++) {
        const d = sdf(x, y);
        if (d <= 0) break;
        const e = 1e-4, gx = (sdf(x + e, y) - sdf(x - e, y)) / (2 * e), gy = (sdf(x, y + e) - sdf(x, y - e)) / (2 * e);
        const gl = Math.hypot(gx, gy) || 1;
        x -= (gx / gl) * d; y -= (gy / gl) * d;
      }
      map[k] = verts.length / 3;
      verts.push(x, y, 0);
    }
    return map[k];
  };
  for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
    const quads = [[[i, j], [i + 1, j], [i + 1, j + 1]], [[i, j], [i + 1, j + 1], [i, j + 1]]];
    for (const tri of quads) {
      const cx = tri.reduce((a, [a1, b1]) => a + P(a1, b1)[0], 0) / 3, cy = tri.reduce((a, [a1, b1]) => a + P(a1, b1)[1], 0) / 3;
      if (sdf(cx, cy) < 0) index.push(...tri.map(([a, b]) => vid(a, b)));
    }
  }
  for (let k = 0; k < verts.length; k += 3) verts[k + 2] = maskHeight(kind, verts[k], verts[k + 1]);
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
  g.setIndex(index);
  g.computeVertexNormals();
  return g;
}

// ---------- curtains ----------
function curtain(w, h, side, mat) {
  const nx = 140, ny = 60;
  const g = new THREE.PlaneGeometry(w, h, nx, ny);
  g.translate(side * w / 2, -h / 2, 0); // hinge on the centre line at top
  const base = g.attributes.position.array.slice();
  const m = new THREE.Mesh(g, mat);
  m.userData = { base, w, h, side };
  m.castShadow = false; m.receiveShadow = true;
  return m;
}
// open: 0 closed .. 1 fully gathered to the side
function shapeCurtain(m, open, t) {
  const { base, w, h, side } = m.userData;
  const p = m.geometry.attributes.position;
  for (let i = 0; i < p.count; i++) {
    const x0 = base[i * 3], y0 = base[i * 3 + 1];
    const u = Math.abs(x0) / w;                       // 0 at centre edge, 1 at outer edge
    const vy = -y0 / h;                               // 0 top, 1 bottom
    // traveler gathers toward the outer side; bottom lags slightly (cloth weight)
    const o = clamp(open * (1.0 - 0.12 * vy * (1 - open)));
    const gathered = 1 - o * 0.82;
    const x = side * (w - (w - u * w) * gathered);
    const amp = 0.1 + 0.32 * o;
    const z = Math.sin(u * 16 * Math.PI * 2 + side) * amp * (0.75 + 0.25 * Math.sin(u * 37.0))
      + Math.sin(t * 1.3 + u * 6 + vy * 2) * 0.02 * (1 - o * 0.5);
    p.setXYZ(i, x, y0, z);
  }
  p.needsUpdate = true;
  m.geometry.computeVertexNormals();
}

function woodTexture() {
  const c = makeCanvas(1024, 1024), x = c.getContext('2d'); const R = rng(4);
  for (let i = 0; i < 16; i++) {
    const v = 50 + R() * 25;
    x.fillStyle = `rgb(${v + 30},${v + 10},${v - 10})`; x.fillRect(0, i * 64, 1024, 64);
    for (let k = 0; k < 40; k++) { x.strokeStyle = `rgba(20,10,5,${0.15 * R()})`; x.beginPath(); const yy = i * 64 + R() * 64; x.moveTo(0, yy); x.bezierCurveTo(300, yy + R() * 6, 700, yy - R() * 6, 1024, yy); x.stroke(); }
    x.fillStyle = 'rgba(0,0,0,0.6)'; x.fillRect(0, i * 64, 1024, 2);
    x.fillRect(R() * 1024, i * 64, 2, 64);
  }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(3, 3); t.anisotropy = 8; return t;
}

export async function create(ctx) {
  const { renderer, aspect } = ctx;
  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2('#0a0303', 0.018);
  scene.environment = studioEnv(renderer, {
    ambient: '#080303',
    panels: [
      { pos: [-6, 10, 8], size: [3, 3], color: '#ffd9a0', intensity: 14 },
      { pos: [6, 9, 6], size: [2, 6], color: '#ffe6c4', intensity: 8 },
      { pos: [0, 2, 12], size: [16, 4], color: '#9a2a1a', intensity: 1.2 },
      { pos: [0, -4, 6], size: [10, 2], color: '#ffb766', intensity: 3 },
      { pos: [0, 4, -10], size: [6, 8], color: '#fff2d8', intensity: 2.2 },
    ],
  });
  scene.environmentIntensity = 0.9;
  const camera = new THREE.PerspectiveCamera(40, aspect, 0.1, 200);
  camera.filmGauge = 35;
  scene.add(camera);

  const goldM = gold({ roughness: 0.22 });
  const goldSatin = gold({ roughness: 0.38, color: '#d9a94f' });

  // ---- proscenium ----
  const OW = 22, OH = 18, IW = 13, IH = 11.5;
  const outer = new THREE.Shape(); outer.moveTo(-OW / 2, -1); outer.lineTo(OW / 2, -1); outer.lineTo(OW / 2, OH); outer.lineTo(-OW / 2, OH); outer.closePath();
  const hole = new THREE.Path(); hole.moveTo(-IW / 2, 0); hole.lineTo(IW / 2, 0); hole.lineTo(IW / 2, IH - 2.6); hole.absellipse(0, IH - 2.6, IW / 2, 2.6, 0, Math.PI, false); hole.lineTo(-IW / 2, 0);
  outer.holes.push(hole);
  const wallMat = new THREE.MeshStandardMaterial({ color: '#2a0508', roughness: 0.8 });
  const prosc = new THREE.Mesh(new THREE.ExtrudeGeometry(outer, { depth: 0.6, bevelEnabled: true, bevelThickness: 0.15, bevelSize: 0.12, bevelSegments: 4, curveSegments: 64 }), [wallMat, goldSatin]);
  prosc.position.z = 1.2; scene.add(prosc);
  // gold moulding bands following the arch (tubes) + rosettes
  const archPath = new THREE.CurvePath();
  const pts = [];
  for (let i = 0; i <= 120; i++) { const a = Math.PI - (i / 120) * Math.PI; pts.push(new THREE.Vector3(Math.cos(a) * (IW / 2 + 0.35), IH - 2.6 + Math.sin(a) * (2.6 + 0.35), 0)); }
  const fullPts = [new THREE.Vector3(-IW / 2 - 0.35, -0.2, 0), ...pts, new THREE.Vector3(IW / 2 + 0.35, -0.2, 0)];
  const moulding = new THREE.CatmullRomCurve3(fullPts, false, 'centripetal', 0.1);
  for (const [r, off] of [[0.14, 0], [0.07, 0.42], [0.05, 0.75]]) {
    const scaled = new THREE.CatmullRomCurve3(fullPts.map((p) => new THREE.Vector3(p.x * (1 + off / (IW / 2)), p.y < 0 ? p.y : p.y + off * (p.y / (IH)), 0)));
    const tube = new THREE.Mesh(new THREE.TubeGeometry(scaled, 400, r, 12, false), goldM);
    tube.position.z = 2.05; scene.add(tube);
  }
  const rosGeo = new THREE.TorusKnotGeometry(0.13, 0.04, 64, 8, 2, 5);
  const ros = new THREE.InstancedMesh(rosGeo, goldM, 36);
  const Mx = new THREE.Matrix4();
  for (let i = 0; i < 36; i++) { const p = moulding.getPointAt((i + 0.5) / 36); Mx.makeTranslation(p.x * 1.035, p.y + 0.2, 2.1); ros.setMatrixAt(i, Mx); }
  scene.add(ros);
  // columns
  for (const sx of [-1, 1]) {
    const col = new THREE.Mesh(new THREE.CylinderGeometry(0.42, 0.48, IH + 0.5, 48, 1), goldSatin);
    col.position.set(sx * (IW / 2 + 1.4), (IH + 0.5) / 2 - 0.5, 2.2); scene.add(col);
    for (let k = 0; k < 24; k++) { // fluting
      const a = (k / 24) * Math.PI * 2;
      const f = new THREE.Mesh(new THREE.BoxGeometry(0.05, IH - 1, 0.05), goldM);
      f.position.set(col.position.x + Math.cos(a) * 0.47, col.position.y, 2.2 + Math.sin(a) * 0.47); scene.add(f);
    }
    for (const yy of [-0.3, IH]) { const cap = new THREE.Mesh(new THREE.TorusGeometry(0.55, 0.12, 12, 48), goldM); cap.rotation.x = Math.PI / 2; cap.position.set(col.position.x, yy, 2.2); scene.add(cap); }
  }

  // ---- curtains & valance ----
  const vel = velvet({ color: '#8a0d1e', sheen: '#ff5a6a' });
  const CW = IW / 2 + 0.6, CH = IH + 0.5;
  const left = curtain(CW, CH, -1, vel), right = curtain(CW, CH, 1, vel);
  left.position.set(0, CH - 0.5, 0.2); right.position.set(0, CH - 0.5, 0.2);
  scene.add(left, right);
  const valG = new THREE.PlaneGeometry(IW + 2, 2.2, 160, 10);
  const vp = valG.attributes.position;
  for (let i = 0; i < vp.count; i++) {
    const x = vp.getX(i), y = vp.getY(i);
    const sw = Math.abs(Math.sin((x / (IW + 2)) * Math.PI * 5));
    const drop = (1 - y / 1.1) * 0.5 * (y < 0 ? sw : 0);
    vp.setXYZ(i, x, y - sw * 0.6 * (y < 0 ? (-y / 1.1) : 0), 0.15 * Math.sin(x * 9) + drop * 0.3);
  }
  valG.computeVertexNormals();
  const valance = new THREE.Mesh(valG, vel); valance.position.set(0, IH - 0.6, 0.9); scene.add(valance);
  // gold fringe along the valance hem
  const fr = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.012, 0.012, 0.32, 4), goldM, 600);
  for (let i = 0; i < 600; i++) {
    const x = -IW / 2 - 1 + (i / 599) * (IW + 2);
    const sw = Math.abs(Math.sin((x / (IW + 2)) * Math.PI * 5));
    Mx.makeTranslation(x, IH - 0.6 - 1.1 - sw * 0.6 - 0.16, 0.9 + 0.15 * Math.sin(x * 9)); fr.setMatrixAt(i, Mx);
  }
  scene.add(fr);

  // ---- stage floor, footlights ----
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(40, 30), new THREE.MeshPhysicalMaterial({ map: woodTexture(), color: '#8a6a55', roughness: 0.5, clearcoat: 0.4, clearcoatRoughness: 0.2 }));
  floor.rotation.x = -Math.PI / 2; floor.position.set(0, -0.01, 0); floor.receiveShadow = true; scene.add(floor);
  const foot = new THREE.InstancedMesh(new THREE.SphereGeometry(0.06, 10, 8), emissive('#ffcf86', 30), 28);
  for (let i = 0; i < 28; i++) { Mx.makeTranslation(-IW / 2 + 0.3 + (i / 27) * (IW - 0.6), 0.08, 2.9); foot.setMatrixAt(i, Mx); }
  scene.add(foot);
  const apron = new THREE.Mesh(new THREE.BoxGeometry(IW + 4, 0.25, 0.4), goldSatin); apron.position.set(0, -0.12, 3.1); scene.add(apron);

  // ---- balconies (auditorium side boxes) ----
  const railMat = gold({ roughness: 0.3 });
  const boxWall = new THREE.MeshStandardMaterial({ color: '#3a0710', roughness: 0.7 });
  const sconces = [];
  for (const sx of [-1, 1]) for (let lvl = 0; lvl < 3; lvl++) {
    const y = 3.5 + lvl * 4.2;
    const front = new THREE.Mesh(new THREE.CylinderGeometry(2.4, 2.4, 1.1, 40, 1, true, sx > 0 ? Math.PI * 1.15 : Math.PI * -0.15, Math.PI * 0.7), boxWall);
    front.position.set(sx * 13.5, y, 5); scene.add(front);
    const rail = new THREE.Mesh(new THREE.TorusGeometry(2.42, 0.07, 8, 60, Math.PI * 0.7), railMat);
    rail.rotation.set(Math.PI / 2, 0, sx > 0 ? Math.PI * 0.65 : Math.PI * -0.35 + Math.PI * 0); rail.position.set(sx * 13.5, y + 0.55, 5); scene.add(rail);
    const lamp = new THREE.Mesh(new THREE.SphereGeometry(0.12, 12, 10), emissive('#ffc070', 25)); lamp.position.set(sx * 11.3, y + 1.4, 5.2); scene.add(lamp); sconces.push(lamp);
  }
  const backWall = new THREE.Mesh(new THREE.PlaneGeometry(60, 30), new THREE.MeshStandardMaterial({ color: '#060102', roughness: 0.95 }));
  backWall.position.set(0, 10, -6); scene.add(backWall);

  // ---- ticket portal (behind the curtains) ----
  const portal = new THREE.Group(); portal.position.set(0, 4.7, -2.5); scene.add(portal);
  const pShape = ticketShapeV(3.2, 6.4, 0.2, 0.22, -1.6);
  const outline = pShape.getSpacedPoints(400).map((p) => new THREE.Vector3(p.x, p.y, 0));
  const pCurve = new THREE.CatmullRomCurve3(outline, true);
  const portalRim = new THREE.Mesh(new THREE.TubeGeometry(pCurve, 600, 0.05, 10, true), emissive('#ffcf7a', 0));
  portal.add(portalRim);
  const fillMat = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    uniforms: { uA: { value: 0 }, uTime: { value: 0 } },
    vertexShader: 'varying vec2 vP; void main(){ vP = position.xy; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); }',
    fragmentShader: noiseGLSL + `uniform float uA, uTime; varying vec2 vP;
      void main(){ float r = length(vP * vec2(1.6, 0.8));
        float n = fbm3(vec3(vP * 0.8, uTime * 0.3)) * 0.5 + 0.5;
        vec3 c = mix(vec3(1.0, 0.75, 0.4), vec3(1.0, 0.95, 0.85), exp(-r * 1.2));
        gl_FragColor = vec4(c * (exp(-r * 0.9) * 3.0 + n * 0.6) * uA, 1.0); }`,
  });
  portal.add(new THREE.Mesh(new THREE.ShapeGeometry(pShape, 48), fillMat));
  const portalBeam = beam(14, 4.5, beamMaterial({ color: '#ffd9a0', intensity: 0, noise: 0.6, falloff: 0.6 }));
  portalBeam.position.set(0, 4.7, -2.4); scene.add(portalBeam); aimBeam(portalBeam, new THREE.Vector3(0, 3.5, 12));
  const portalLight = new THREE.PointLight('#ffd49a', 0, 30, 2); portalLight.position.set(0, 4.7, -1.5); scene.add(portalLight);

  // ---- masks ----
  const maskMat = gold({ roughness: 0.12, color: '#EBC777' });
  maskMat.side = THREE.DoubleSide;
  const comedy = new THREE.Mesh(maskGeometry('comedy'), maskMat), tragedy = new THREE.Mesh(maskGeometry('tragedy'), maskMat);
  comedy.castShadow = tragedy.castShadow = true;
  const mc = new THREE.Group(), mt = new THREE.Group();
  mc.add(comedy); mt.add(tragedy);
  mc.scale.setScalar(1.5); mt.scale.setScalar(1.5);
  scene.add(mc, mt);

  // ---- lights ----
  const key = new THREE.SpotLight('#ffdcae', 900, 0, 0.32, 0.6, 2);
  key.position.set(-5, 15, 10); key.target.position.set(0, 5, 2.5);
  key.castShadow = true; key.shadow.mapSize.set(1024, 1024); key.shadow.bias = -0.0005; key.shadow.camera.near = 5; key.shadow.camera.far = 40;
  scene.add(key, key.target);
  const fill = new THREE.SpotLight('#ffb070', 300, 0, 0.5, 0.8, 2); fill.position.set(7, 10, 9); fill.target.position.set(0, 4, 0); scene.add(fill, fill.target);
  const wash = new THREE.SpotLight('#ff8a5a', 260, 0, 0.9, 1, 2); wash.position.set(0, 16, 6); wash.target.position.set(0, 4, 0); scene.add(wash, wash.target);
  scene.add(new THREE.AmbientLight('#3a0d0a', 0.4));
  // volumetric spotlight shafts from the fly gallery + dust
  const shafts = [];
  for (const [x, c] of [[-5, '#ffe2b8'], [5, '#ffd8a8'], [0, '#fff0d8']]) {
    const m = beamMaterial({ color: c, intensity: 0.5, noise: 0.7, falloff: 0.8 });
    const b = beam(19, 2.2, m); b.position.set(x, 17, 6); aimBeam(b, new THREE.Vector3(x * 0.35, 0, 2.5)); scene.add(b); shafts.push(m);
  }
  const ND = 5000, R = rng(44);
  const dFrom = new Float32Array(ND * 3), dTo = new Float32Array(ND * 3);
  for (let i = 0; i < ND; i++) { const x = (R() - 0.5) * 14, y = R() * 14, z = -1 + R() * 9; dFrom.set([x, y, z], i * 3); dTo.set([x + (R() - 0.5), y - 1 - R(), z + (R() - 0.5)], i * 3); }
  const dust = particleField({ from: dFrom, to: dTo, count: ND, size: 0.018, intensity: 1.2, color: '#ffd9a0', seed: 3, swirl: 0.2, turbulence: 1.4 });
  dust.material.uniforms.uSpread.value = 0.0;
  scene.add(dust);
  const gl = glint({ size: 1.4, intensity: 4 }); scene.add(gl);

  const DIST = 3.6;
  const title = await makeTitle(ctx, camera, [
    { text: 'DES SPECTACLES', font: 'cinzel-700', size: 0.043, tracking: 0.2, y: 0.315 },
    { text: 'EXCEPTIONNELS', font: 'cinzel-900', size: 0.08, tracking: 0.03, y: 0.24, delay: 0.1, stagger: 0.03, maxWidth: 0.88 },
  ], { dist: DIST, fov: 2 * Math.atan(17.5 / 32) * 180 / Math.PI });

  const s = {
    scene, camera, clear: 0x050102,
    dof: { focus: 12, aperture: 0, maxCoC: 12 },
    grade: { exposure: 1.0, tint: [1.05, 0.98, 0.93], bloom: 0.6, sat: 1.04 },
    update(lt, T) {
      // camera: arrive from the stalls in a slow crane-down dolly, then push into the portal
      const z = track([[-0.4, 27], [3.0, 13.5, cine], [4.45, 4.2, easeInCubic]], lt);
      const y = track([[-0.4, 8.5], [3.0, 5.2, cine], [4.45, 4.8]], lt);
      const x = track([[-0.4, 2.8], [3.0, 0.4, cine], [4.45, 0]], lt);
      camera.position.set(x, y, z);
      camera.lookAt(0, track([[-0.4, 5.6], [3.0, 5.0]], lt), 0);
      camera.setFocalLength(32);
      camera.updateProjectionMatrix();

      const open = smoother(remap(lt, 1.7, 3.3));
      shapeCurtain(left, open, T); shapeCurtain(right, open, T);
      // masks: float centre-stage in front of the curtain, rotate, then part with the curtains
      const sep = 1.25 + open * 1.25;
      mc.position.set(-sep, 5.2 + 0.12 * Math.sin(T * 1.1), 3.6 - open * 1.5);
      mt.position.set(sep, 5.0 + 0.12 * Math.sin(T * 1.1 + 1.5), 3.6 - open * 1.5);
      mc.rotation.set(0.1 + 0.08 * Math.sin(T * 0.9), 0.55 * Math.sin(T * 0.8) + 0.35 + open * 0.8, 0.12);
      mt.rotation.set(0.1 + 0.08 * Math.sin(T * 0.9 + 1), -0.55 * Math.sin(T * 0.8 + 0.6) - 0.35 - open * 0.8, -0.12);
      // portal ignites as the curtains open
      const pa = remap(lt, 2.0, 3.2);
      portalRim.material.color.set('#ffcf7a').multiplyScalar(30 * pa);
      fillMat.uniforms.uA.value = 0.9 * pa; fillMat.uniforms.uTime.value = T;
      portalBeam.material.uniforms.uIntensity.value = 0.6 * pa; portalBeam.material.uniforms.uTime.value = T;
      portalLight.intensity = 60 * pa;
      shafts.forEach((m) => { m.uniforms.uTime.value = T; });
      const du = dust.material.uniforms; du.uTime.value = T; du.uMix.value = clamp((lt + 0.5) / 5); du.uPx.value = ctx.pxScale(camera);
      const gk = remap(lt, 1.0, 1.6);
      gl.position.copy(mc.position).add(new THREE.Vector3(0.3, 0.45, 0.6));
      gl.material.uniforms.uAmount.value = Math.sin(Math.PI * gk);
      title.update(lt, 0.55, 'flip', 3.2, 0.6);
      s.dof.focus = camera.position.distanceTo(mc.position);
      s.dof.aperture = 2.0;
    },
  };
  return s;
}
