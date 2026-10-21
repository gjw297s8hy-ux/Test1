// SCENE 5 — 00:18–00:24 — THE TICKET REVEAL (hero commercial moment)
// Three premium tickets (FOOTBALL / CONCERT / SPECTACLE) emerge from darkness on staggered arcs,
// settle into a floating fan formation under an orbiting camera. A holographic price-tag motif
// (€ + downward chevron, no figures) suggests savings without stating any number.
import * as THREE from 'three';
import { titleEnv, rng, track, cine, settle, remap, smoother, studioEnv, loadFont, text3D, clamp, roundedRectShape, easeOutCubic, spring } from '../src/engine/lib.js';
import { particleField, glint, beamMaterial, beam, aimBeam } from '../shaders/fx.js';
import { gold, holographic, emissive } from '../materials/materials.js';
import { makeTicket } from './common/ticket.js';
import { makeTitle } from './common/title.js';
import { noiseGLSL } from '../shaders/noise.glsl.js';

export const LAYOUT = {
  // final formation (shared with scene 6 so the hand-off is seamless)
  tickets: [
    { kind: 'football', pos: [-1.02, 0.02, -0.35], rot: [0.02, 0.38, 0.05], accent: '#126BFF' },
    { kind: 'concert', pos: [0, 0.1, 0.05], rot: [0, 0, 0], accent: '#772BFF' },
    { kind: 'spectacle', pos: [1.02, 0.02, -0.35], rot: [0.02, -0.38, -0.05], accent: '#B0182E' },
  ],
  size: { width: 0.98, height: 1.96 },
};

// Pure pose functions (shared with scene 6 for a seamless hand-off)
export function cameraPose(lt) {
  const u = cine(remap(lt, -0.4, 3.2));
  const ang = THREE.MathUtils.lerp(-0.85, 0, u) + 0.03 * Math.sin(lt * 0.6) * remap(lt, 3.2, 4);
  const rad = THREE.MathUtils.lerp(7.2, 5.75, u) - 0.2 * smoother(remap(lt, 3.2, 6));
  return {
    pos: new THREE.Vector3(Math.sin(ang) * rad, THREE.MathUtils.lerp(1.6, 0.25, u), Math.cos(ang) * rad),
    look: new THREE.Vector3(0, THREE.MathUtils.lerp(0.4, 0.05, u), 0),
  };
}
export function ticketPose(i, lt, T) {
  const L = LAYOUT.tickets[i];
  const d = [0.2, 0.0, 0.4][i];
  const k = remap(lt, -0.35 + d, 1.75 + d);
  const e = settle(k);
  const startX = L.pos[0] * 4 + (i - 1) * 1.5, startZ = -9 - i;
  return {
    k,
    pos: new THREE.Vector3(THREE.MathUtils.lerp(startX, L.pos[0], e), THREE.MathUtils.lerp(-2.5 + i, L.pos[1], e) + 0.04 * Math.sin(T * 1.2 + i * 2), THREE.MathUtils.lerp(startZ, L.pos[2], e)),
    rot: new THREE.Euler(L.rot[0] + (1 - e) * 1.2, L.rot[1] + (1 - e) * (i - 1) * 2.4 + 0.04 * Math.sin(T * 0.8 + i), L.rot[2] + (1 - e) * 0.6),
  };
}

export function studioForTickets(renderer) {
  return studioEnv(renderer, {
    ambient: '#050507',
    panels: [
      { pos: [-8, 5, 6], size: [1, 14], color: '#fff1dc', intensity: 9 },
      { pos: [8, 3, 5], size: [1, 12], color: '#e9efff', intensity: 7 },
      { pos: [0, 10, 2], size: [12, 1.2], color: '#ffe0aa', intensity: 6 },
      { pos: [0, 2, 12], size: [14, 5], color: '#2a2216', intensity: 1.5 },
      { pos: [-4, -3, -8], size: [6, 2], color: '#126BFF', intensity: 2 },
      { pos: [4, -3, -8], size: [6, 2], color: '#772BFF', intensity: 2 },
    ],
  });
}

export async function create(ctx) {
  const { renderer, aspect } = ctx;
  const scene = new THREE.Scene();
  scene.environment = studioForTickets(renderer);
  const camera = new THREE.PerspectiveCamera(40, aspect, 0.05, 100);
  camera.filmGauge = 35;
  scene.add(camera);

  // backdrop: deep radial glow + soft floor glow
  const bgMat = new THREE.ShaderMaterial({
    depthWrite: false,
    uniforms: { uTime: { value: 0 }, uA: { value: 0 } },
    vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); }',
    fragmentShader: noiseGLSL + `uniform float uTime, uA; varying vec2 vUv;
      void main(){ vec2 q = (vUv - vec2(0.5, 0.52)) * vec2(1.0, 1.4); float r = length(q);
        vec3 c = vec3(0.42, 0.28, 0.1) * exp(-r * 4.0) * 0.3 + vec3(0.03, 0.06, 0.2) * exp(-length(q - vec2(-0.3, -0.05)) * 6.0) * 0.25 + vec3(0.14, 0.04, 0.26) * exp(-length(q - vec2(0.3, -0.05)) * 6.0) * 0.25;
        c *= 0.8 + 0.2 * snoise(vec3(q * 3.0, uTime * 0.2));
        gl_FragColor = vec4(c * uA, 1.0); }`,
  });
  const bg = new THREE.Mesh(new THREE.PlaneGeometry(40, 40), bgMat); bg.position.z = -14; scene.add(bg);

  // bokeh dust far behind (DOF turns it into soft discs)
  const NB = 2500, R = rng(55);
  const bf = new Float32Array(NB * 3), bt = new Float32Array(NB * 3);
  for (let i = 0; i < NB; i++) { const p = [(R() - 0.5) * 18, (R() - 0.5) * 20, -4 - R() * 9]; bf.set(p, i * 3); bt.set([p[0] + (R() - 0.5) * 2, p[1] + 1 + R(), p[2]], i * 3); }
  const bokeh = particleField({ from: bf, to: bt, count: NB, size: 0.05, intensity: 1.3, seed: 9, swirl: 0, turbulence: 0.6 });
  bokeh.material.uniforms.uSpread.value = 0; scene.add(bokeh);

  // backlight shafts for silhouettes
  const shafts = [];
  for (const [x, c] of [[-3, '#5a8cff'], [3, '#9a6bff'], [0, '#ffd9a0']]) {
    const m = beamMaterial({ color: c, intensity: 0.0, noise: 0.6, falloff: 0.9 });
    const b = beam(14, 2.5, m); b.position.set(x, 7, -6); aimBeam(b, new THREE.Vector3(x * 0.2, -2, 0)); scene.add(b); shafts.push(m);
  }

  // ---- tickets ----
  const labelFont = await loadFont('cinzel-900');
  const tickets = [];
  for (const [i, L] of LAYOUT.tickets.entries()) {
    const t = await makeTicket(L.kind, { ...LAYOUT.size, labelFont, renderer });
    scene.add(t);
    const rim = new THREE.SpotLight(L.accent, 0, 12, 0.5, 0.8, 2);
    rim.position.set(L.pos[0] * 2.5, 2.5, L.pos[2] - 3); rim.target = t; scene.add(rim);
    tickets.push({ t, L, i, rim });
  }
  const key = new THREE.SpotLight('#fff0dc', 0, 20, 0.6, 0.9, 2); key.position.set(-2.5, 3, 4); key.target.position.set(0, 0, 0); scene.add(key, key.target);

  // ---- holographic price tag (no figures): € + down chevron ----
  const tag = new THREE.Group();
  const tShape = roundedRectShape(0.62, 0.42, 0.08);
  const holeP = new THREE.Path(); holeP.absarc(-0.22, 0, 0.04, 0, Math.PI * 2, true); tShape.holes.push(holeP);
  const holo = holographic({ roughness: 0.2, color: '#8e9ab8' });
  holo.envMap = titleEnv(renderer); holo.envMapIntensity = 0.55;
  const tagMesh = new THREE.Mesh(new THREE.ExtrudeGeometry(tShape, { depth: 0.015, bevelEnabled: true, bevelThickness: 0.006, bevelSize: 0.006, bevelSegments: 3, curveSegments: 24 }), [holo, gold({ roughness: 0.15 })]);
  tag.add(tagMesh);
  const euroFont = await loadFont('montserrat-800');
  const euro = text3D('€', euroFont, { size: 0.2, depth: 0.03, bevel: 0.005, materials: [gold({ roughness: 0.15 }), gold({ roughness: 0.1 })] });
  euro.letters.forEach((m) => m.material.forEach((x) => (x.envMap = titleEnv(renderer))));
  euro.group.position.set(0.0, 0.0, 0.03); tag.add(euro.group);
  const chev = new THREE.Shape(); chev.moveTo(-0.06, 0.05); chev.lineTo(0, -0.01); chev.lineTo(0.06, 0.05); chev.lineTo(0.06, 0.01); chev.lineTo(0, -0.05); chev.lineTo(-0.06, 0.01); chev.closePath();
  const chevMat = emissive('#7fd0ff', 0);
  const chevrons = [0, 1].map((k) => { const m = new THREE.Mesh(new THREE.ExtrudeGeometry(chev, { depth: 0.01, bevelEnabled: false }), chevMat); m.position.set(0.19, 0.06 - k * 0.09, 0.03); tag.add(m); return m; });
  // hologram projection: scanline sheet
  const scanMat = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
    uniforms: { uA: { value: 0 }, uTime: { value: 0 } },
    vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); }',
    fragmentShader: `uniform float uA, uTime; varying vec2 vUv;
      void main(){ float l = 0.5 + 0.5 * sin(vUv.y * 160.0 - uTime * 8.0); float e = smoothstep(0.0, 0.15, vUv.x) * smoothstep(1.0, 0.85, vUv.x) * smoothstep(0.0, 0.2, vUv.y) * smoothstep(1.0, 0.8, vUv.y);
        vec3 c = mix(vec3(0.3, 0.8, 1.0), vec3(0.8, 0.5, 1.0), vUv.x); gl_FragColor = vec4(c * (0.25 + 0.75 * l * l) * e * uA * 0.6, 1.0); }`,
  });
  const scan = new THREE.Mesh(new THREE.PlaneGeometry(0.85, 0.6), scanMat); scan.position.z = -0.02; tag.add(scan);
  scene.add(tag);

  const gl1 = glint({ size: 1.0, intensity: 5 }); scene.add(gl1);
  const gl2 = glint({ size: 0.7, intensity: 4 }); scene.add(gl2);

  // ---- typography ----
  const DIST = 3.6;
  const fov = 2 * Math.atan(17.5 / 35) * 180 / Math.PI;
  const title = await makeTitle(ctx, camera, [
    { text: 'TES PLACES', font: 'cinzel-900', size: 0.06, tracking: 0.14, y: 0.355 },
    { text: 'À PRIX RÉDUITS', font: 'cinzel-900', size: 0.075, tracking: 0.04, y: 0.27, delay: 0.12, stagger: 0.03, maxWidth: 0.9 },
  ], { dist: DIST, fov });
  const sub = await makeTitle(ctx, camera, [
    { text: 'FOOTBALL • CONCERTS • SPECTACLES', font: 'montserrat-600', size: 0.026, tracking: 0.12, y: -0.265, stagger: 0.012, maxWidth: 0.86 },
  ], { dist: DIST, fov, scrimOpacity: 0.35 });

  const s = {
    scene, camera, clear: 0x050507,
    dof: { focus: 6, aperture: 0, maxCoC: 16 },
    grade: { exposure: 1.0, tint: [1.02, 1.0, 0.98], bloom: 0.55, sat: 1.06 },
    update(lt, T) {
      // orbit: sweeping arc that resolves to a frontal hero framing
      const cp = cameraPose(lt);
      camera.position.copy(cp.pos);
      camera.lookAt(cp.look);
      camera.setFocalLength(35);
      camera.updateProjectionMatrix();
      bgMat.uniforms.uTime.value = T; bgMat.uniforms.uA.value = 0.5 + 0.5 * remap(lt, -0.4, 1.0);
      const bu = bokeh.material.uniforms; bu.uTime.value = T; bu.uMix.value = clamp((lt + 0.5) / 7); bu.uPx.value = ctx.pxScale(camera); bu.uFade.value = remap(lt, 0, 1);
      shafts.forEach((m) => { m.uniforms.uTime.value = T; m.uniforms.uIntensity.value = 0.18 * remap(lt, 0.4, 1.5); });

      // tickets: emerge from darkness on arcs with staggered mass
      tickets.forEach(({ t, L, i, rim }) => {
        const d = [0.2, 0.0, 0.4][i];
        const tp = ticketPose(i, lt, T);
        const k = tp.k;
        t.position.copy(tp.pos);
        t.rotation.copy(tp.rot);
        t.visible = k > 0;
        rim.intensity = 30 * remap(lt, 0.0 + d, 1.2 + d);
      });
      key.intensity = 18 * remap(lt, 0.2, 1.4);
      scene.environmentRotation.y = track([[0, -0.6], [3, 0.4, smoother], [6, 0.7]], lt); // light sweeps across the foil

      // holographic tag arrives with a spring and hovers above-right of the centre ticket
      const tk = spring(Math.max(0, lt - 2.3), 1.6, 0.6);
      tag.position.set(0.5, -0.62 + 0.02 * Math.sin(T * 1.7), 0.42);
      tag.scale.setScalar(Math.max(0.0001, tk) * 1.1);
      tag.rotation.set(0.05, -0.25 + 0.2 * Math.sin(T * 0.9), 0.14);
      tag.visible = lt > 2.3;
      const pulse = (k) => 0.5 + 0.5 * Math.sin(T * 6 - k * 1.5);
      chevrons.forEach((m, k) => (m.position.y = 0.06 - k * 0.09 - 0.02 * pulse(k)));
      chevMat.color.set('#7fd0ff').multiplyScalar(8 * remap(lt, 2.4, 2.8) * (0.6 + 0.4 * pulse(0)));
      scanMat.uniforms.uA.value = remap(lt, 2.4, 2.9); scanMat.uniforms.uTime.value = T;

      title.update(lt, 1.85, 'rise', 5.35, 0.55);
      sub.update(lt, 2.9, 'rise', 5.3, 0.5);
      // glints travel along the ticket edges on the hero beat
      const g1 = remap(lt, 2.0, 2.6), g2 = remap(lt, 3.4, 3.9);
      gl1.position.set(-0.5 + g1 * 1.0, 1.08, 0.12); gl1.material.uniforms.uAmount.value = Math.sin(Math.PI * g1);
      gl2.position.set(1.4, -0.6 + g2 * 1.4, -0.2); gl2.material.uniforms.uAmount.value = Math.sin(Math.PI * g2);
      s.grade.exposure = 1 + 0.12 * Math.exp(-Math.max(0, lt - 1.95) * 6) * (lt > 1.95 ? 1 : 0);
      s.dof.focus = camera.position.length();
      s.dof.aperture = 2.2;
    },
  };
  return s;
}
