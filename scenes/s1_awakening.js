// SCENE 1 — 00:00–00:04 — THE AWAKENING
// Darkness -> gold particle field converges into an energy ring -> camera pushes through ->
// premium gold ticket emerges -> "LES PLUS GRANDES ÉMOTIONS" lands on the impact (t=3.0s, beat 6).
import * as THREE from 'three';
import { rng, track, titleEnv, cine, settle, easeOutCubic, easeInExpo, remap, smoother, studioEnv, loadFont, text3D, clamp } from '../src/engine/lib.js';
import { particleField, glint } from '../shaders/fx.js';
import { gold, emissive } from '../materials/materials.js';
import { makeTicket } from './common/ticket.js';
import { noiseGLSL } from '../shaders/noise.glsl.js';

export const IMPACT = 3.0;

export async function create(ctx) {
  const { renderer, aspect, config } = ctx;
  const scene = new THREE.Scene();
  scene.environment = studioEnv(renderer, {
    panels: [
      { pos: [-9, 4, 6], size: [1.2, 14], color: '#ffe2b0', intensity: 9 },
      { pos: [9, 2, 4], size: [1.0, 12], color: '#fff3e0', intensity: 6 },
      { pos: [0, 11, 0], size: [10, 2], color: '#ffd9a0', intensity: 4 },
      { pos: [0, -2, 12], size: [6, 0.6], color: '#ffffff', intensity: 10 },
      { pos: [3, 3, -12], size: [2, 8], color: '#9fb7ff', intensity: 2 },
    ],
  });
  scene.environmentIntensity = 1.0;

  const camera = new THREE.PerspectiveCamera(40, aspect, 0.05, 200);
  camera.filmGauge = 35;
  scene.add(camera);

  // ---- particle field -> ring ----
  const N = 48000;
  const R = rng(101);
  const from = new Float32Array(N * 3), to = new Float32Array(N * 3);
  const RING = 2.2;
  const gauss = () => { let u = 0; for (let i = 0; i < 4; i++) u += R(); return (u - 2) / 1.15; };
  for (let i = 0; i < N; i++) {
    from[i * 3] = (R() - 0.5) * 16;
    from[i * 3 + 1] = (R() - 0.5) * 26;
    from[i * 3 + 2] = -32 + R() * 41;
    const kind = R();
    if (kind < 0.8) { // tight ring with a gaussian cross-section
      const a = R() * Math.PI * 2, rr = RING + gauss() * 0.05 * (R() < 0.85 ? 1 : 4);
      to[i * 3] = Math.cos(a) * rr; to[i * 3 + 1] = Math.sin(a) * rr; to[i * 3 + 2] = gauss() * 0.06;
    } else { // residual dust that stays as depth/parallax behind the ticket
      to[i * 3] = (R() - 0.5) * 14; to[i * 3 + 1] = (R() - 0.5) * 22; to[i * 3 + 2] = -9 - R() * 22;
    }
  }
  const field = particleField({ from, to, count: N, size: 0.032, intensity: 2.6, seed: 7, swirl: 1.1, turbulence: 0.9 });
  const ringGroup = new THREE.Group();
  ringGroup.add(field);
  scene.add(ringGroup);

  // energy ring core: thin HDR torus + soft additive halo
  const core = new THREE.Mesh(new THREE.TorusGeometry(RING, 0.012, 12, 360), emissive('#ffcf7a', 0));
  ringGroup.add(core);
  const haloMat = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    uniforms: { uA: { value: 0 }, uTime: { value: 0 }, uR: { value: RING } },
    vertexShader: 'varying vec2 vP; void main(){ vP = position.xy; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); }',
    fragmentShader: noiseGLSL + `uniform float uA, uTime, uR; varying vec2 vP;
      void main(){ float r = length(vP); float a = atan(vP.y, vP.x);
        float n = 0.7 + 0.3 * snoise(vec3(cos(a)*2.0, sin(a)*2.0, uTime*0.6));
        float d = r - uR; float g = exp(-d*d*120.0) * 0.9 + exp(-d*d*8.0) * 0.18;
        gl_FragColor = vec4(vec3(1.0, 0.72, 0.32) * g * n * uA, 1.0); }`,
  });
  const halo = new THREE.Mesh(new THREE.PlaneGeometry(RING * 3, RING * 3), haloMat);
  ringGroup.add(halo);
  const ringLight = new THREE.PointLight('#ffc46a', 0, 30, 2);
  scene.add(ringLight);

  // ---- hero ticket ----
  const ticket = await makeTicket('hero', { width: 1.3, height: 2.6 });
  scene.add(ticket);

  // key light sweeping across the ticket + cool rim
  const key = new THREE.SpotLight('#fff1d6', 0, 30, 0.7, 0.9, 1.5);
  key.position.set(-3, 3, -1); key.target = ticket; scene.add(key);
  const rim = new THREE.SpotLight('#a9c2ff', 0, 30, 0.6, 0.8, 1.5);
  rim.position.set(3.5, 2, -10); rim.target = ticket; scene.add(rim);

  // ---- typography (real extruded Cinzel, parented to camera for safe-zone exact layout) ----
  const font = await loadFont('cinzel-700');
  const fontB = await loadFont('cinzel-900');
  const faceMat = gold({ roughness: 0.3 });
  const sideMat = gold({ roughness: 0.1 });
  faceMat.envMap = sideMat.envMap = titleEnv(renderer);
  const t1 = text3D('LES PLUS GRANDES', font, { size: 0.12, depth: 0.028, bevel: 0.0045, tracking: 0.2, materials: [faceMat, sideMat] });
  const t2 = text3D('ÉMOTIONS', fontB, { size: 0.3, depth: 0.065, bevel: 0.009, tracking: 0.05, materials: [faceMat, sideMat] });
  const TD = 4.0;
  const typo = new THREE.Group();
  typo.position.set(0, 0, -TD);
  t1.group.position.y = -0.6; t2.group.position.y = -0.93;
  console.warn('s1 text widths', t1.width.toFixed(3), t2.width.toFixed(3), 'visible', (2 * TD * Math.tan(THREE.MathUtils.degToRad(26.565)) * aspect).toFixed(3));
  typo.add(t1.group, t2.group);
  camera.add(typo);
  const letters = [...t1.letters.map((m, i) => ({ m, d: i * 0.018 })), ...t2.letters.map((m, i) => ({ m, d: 0.16 + i * 0.03 }))];
  letters.forEach(({ m }) => { m.material = m.material.map((x) => { const c = x.clone(); c.transparent = true; return c; }); });
  const typoLight = new THREE.PointLight('#fff0d0', 0, 8, 2);
  camera.add(typoLight); typoLight.position.set(1.5, 0.2, -3.6);
  typo.traverse((o) => o.layers.set(1)); typoLight.layers.enableAll();

  // ---- impact: shockwave + glint ----
  const shockMat = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    uniforms: { uR: { value: 0 }, uA: { value: 0 } },
    vertexShader: 'varying vec2 vP; void main(){ vP = position.xy; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); }',
    fragmentShader: `uniform float uR, uA; varying vec2 vP; void main(){ float d = length(vP) - uR; float g = exp(-d*d*260.0) + exp(-d*d*12.0)*0.15; gl_FragColor = vec4(vec3(1.0,0.78,0.42)*g*uA, 1.0); }`,
  });
  const shock = new THREE.Mesh(new THREE.PlaneGeometry(12, 12), shockMat);
  shock.position.set(0, 0.95, -7.7);
  scene.add(shock);
  const gl1 = glint({ size: 2.2, intensity: 5 });
  camera.add(gl1);

  const s = {
    scene, camera, clear: 0x050507,
    dof: { focus: 10, aperture: 0, maxCoC: 14 },
    grade: { exposure: 1, tint: [1.03, 1.0, 0.95], bloom: 0.6 },
    update(lt) {
      const t = lt;
      // camera: slow creep, then decisive push through the ring, glide to the ticket, then dive into it
      const cz = track([[0, 12.5], [1.5, 10.2], [2.5, -0.9, cine], [3.55, -1.35, (x) => x], [4.4, -5.6, easeInExpo]], t);
      const cx = track([[0, 0.25], [1.5, 0.15], [2.5, 0, cine]], t);
      const cy = track([[0, -0.35], [2.5, 0.0, cine], [4.4, 0.5]], t);
      camera.position.set(cx, cy, cz);
      camera.setFocalLength(track([[0, 24], [1.7, 24], [2.6, 35, cine]], t));
      camera.rotation.set(0, 0, track([[0, 0.05], [2.5, 0, cine]], t));
      camera.updateProjectionMatrix();

      // particle convergence
      const u = field.material.uniforms;
      u.uTime.value = t;
      u.uMix.value = track([[0.25, 0], [1.75, 1, smoother]], t);
      u.uPx.value = ctx.pxScale(camera);
      u.uFade.value = remap(t, 0.05, 0.6) * (1 - 0.5 * remap(t, 2.4, 3.2));
      ringGroup.rotation.z = t * 0.35 + 0.2 * Math.sin(t * 0.6);
      const ringOn = remap(t, 1.3, 1.85);
      core.material.color.set('#ffcf7a').multiplyScalar(14 * ringOn * (1 + 0.6 * Math.exp(-Math.max(0, t - 1.75) * 4)));
      haloMat.uniforms.uA.value = ringOn * 2.2; haloMat.uniforms.uTime.value = t;
      ringLight.intensity = 10 * ringOn * (1 - remap(t, 2.3, 2.9));

      // ticket emerges from depth with mass: long settle, then a slow living drift
      const te = settle(remap(t, 1.95, 3.0));
      ticket.position.set(track([[1.95, -0.7], [3.0, 0.0, settle]], t), track([[1.95, 0.2], [3.0, 0.95, settle]], t) + 0.03 * Math.sin(t * 1.3), track([[1.95, -14], [3.0, -7.6, settle]], t));
      ticket.rotation.set(-0.12 + (1 - te) * 0.5, 0.26 + (1 - te) * -1.6 + 0.05 * Math.sin(t * 0.8), -0.06 + (1 - te) * 0.35);
      ticket.visible = t > 1.9;
      key.intensity = 7 * remap(t, 2.0, 2.6);
      key.position.set(track([[2.0, -4], [3.4, 3.5]], t), 2.5, -2.5);
      rim.intensity = 45 * remap(t, 2.2, 2.8);
      scene.environmentRotation.y = track([[1.9, -0.9], [3.6, 0.7, smoother]], t); // reflections sweep across the foil

      // letters: rise out of depth, staggered, settle exactly on the impact
      letters.forEach(({ m, d }) => {
        const k = remap(t, 2.45 + d, 2.95 + d * 0.6);
        const e = settle(k);
        m.visible = k > 0;
        m.position.set(m.userData.base.x, m.userData.base.y - (1 - e) * 0.18, m.userData.base.z - (1 - e) * 1.6);
        m.rotation.x = (1 - e) * 1.1;
        m.material.forEach((x) => (x.opacity = clamp(k * 2.2)));
      });
      typoLight.intensity = 6 * remap(t, 2.5, 3.0);
      const sweep = remap(t, IMPACT, IMPACT + 0.5);
      gl1.position.set(-1.4 + sweep * 2.8, -1.2, -TD + 0.3);
      gl1.material.uniforms.uAmount.value = Math.sin(Math.PI * sweep) * (t > IMPACT ? 1 : 0);

      // impact
      const ip = t - IMPACT;
      shockMat.uniforms.uR.value = ip > 0 ? easeOutCubic(clamp(ip / 0.8)) * 5.5 : 0;
      shockMat.uniforms.uA.value = ip > 0 ? Math.exp(-ip * 3.5) * 3 : 0;
      s.grade.exposure = 1 + (ip > 0 ? 0.22 * Math.exp(-ip * 6) : 0) - 0.25 * (1 - remap(t, 0, 0.6));

      // focus pulls: ring -> ticket
      const ticketDist = camera.position.distanceTo(ticket.position);
      // focus: ring -> ticket -> rack to the title as it lands
      s.dof.focus = t < 2.0 ? Math.max(1, cz) : THREE.MathUtils.lerp(ticketDist, TD, smoother(remap(t, 2.6, 3.0)));
      s.dof.aperture = 2.4;
    },
  };
  return s;
}
