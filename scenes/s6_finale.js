// SCENE 6 — 00:24–00:30 — WESTAFF PLACE BRAND FINALE
// Opens on the exact scene-5 hero frame. The tickets burn away (noise dissolve with an
// incandescent gold edge) into ~40k particles sampled from their surfaces, which spiral inward
// and land on points sampled from the wordmark geometry. The wordmark resolves: WESTAFF in
// extruded brushed silver with polished gold bevels, PLACE in gold between gold rules.
// Halo, glints, tagline and contact line follow; ends on a stable hero frame.
import * as THREE from 'three';
import { rng, track, cine, settle, remap, smoother, studioEnv, loadFont, text3D, clamp, sampleSurface, easeOutCubic, titleEnv } from '../src/engine/lib.js';
import { particleField, glint } from '../shaders/fx.js';
import { gold, brushedSilver, emissive } from '../materials/materials.js';
import { makeTicket } from './common/ticket.js';
import { makeTitle } from './common/title.js';
import { LAYOUT, cameraPose, ticketPose, studioForTickets } from './s5_tickets.js';
import { noiseGLSL } from '../shaders/noise.glsl.js';

const S5_DURATION = 6; // scene 5 local time at the hand-off

// Inject a screen-space noise burn into any built-in material
function burnable(mat, U) {
  mat.transparent = false;
  mat.onBeforeCompile = (sh) => {
    sh.uniforms.uBurn = U.uBurn; sh.uniforms.uRes = U.uRes; sh.uniforms.uSeed = U.uSeed;
    sh.fragmentShader = 'uniform float uBurn; uniform vec2 uRes; uniform float uSeed;\n' + noiseGLSL + sh.fragmentShader.replace('#include <dithering_fragment>', `
      #include <dithering_fragment>
      {
        vec2 sp = gl_FragCoord.xy / uRes.y;
        float n = 0.5 + 0.5 * fbm3(vec3(sp * 7.0, uSeed));
        float th = uBurn * 1.25 - 0.1;
        if (n < th) discard;
        float edge = smoothstep(th + 0.05, th, n) * step(0.001, uBurn);
        gl_FragColor.rgb += vec3(1.0, 0.68, 0.28) * edge * 9.0;
      }`);
  };
  mat.customProgramCacheKey = () => 'burn';
  return mat;
}

export async function create(ctx) {
  const { renderer, aspect, config, W, H } = ctx;
  const brand = config.brand;
  const scene = new THREE.Scene();
  scene.environment = studioForTickets(renderer);
  const camera = new THREE.PerspectiveCamera(40, aspect, 0.05, 100);
  camera.filmGauge = 35;
  scene.add(camera);

  // logo lighting: neutral studio so silver stays silver and gold stays champagne
  const logoEnv = studioEnv(renderer, {
    ambient: '#060606',
    panels: [
      { pos: [0, 6, 12], size: [26, 6], color: '#f4f6fa', intensity: 0.8 },
      { pos: [0, 1.2, 12.2], size: [26, 3.5], color: '#dfe3ea', intensity: 0.75 },
      { pos: [0, -3, 12.3], size: [26, 4], color: '#6b5a40', intensity: 0.6 },
      { pos: [0, 0.3, 11.8], size: [26, 0.3], color: '#ffffff', intensity: 5 },
      { pos: [-11, 2, 6], size: [0.8, 16], color: '#ffffff', intensity: 14 },
      { pos: [11, 0, 6], size: [0.8, 16], color: '#ffeccc', intensity: 12 },
      { pos: [0, 12, -2], size: [12, 1], color: '#ffffff', intensity: 8 },
    ],
  });

  // backdrop glow (continuity with scene 5, then settles to deep black)
  const bgMat = new THREE.ShaderMaterial({
    depthWrite: false, uniforms: { uA: { value: 1 }, uB: { value: 0 } },
    vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); }',
    fragmentShader: `uniform float uA, uB; varying vec2 vUv;
      void main(){ vec2 q = (vUv - vec2(0.5, 0.52)) * vec2(1.0, 1.4); float r = length(q);
        vec3 c = vec3(0.42, 0.28, 0.1) * exp(-r * 4.0) * 0.3 + vec3(0.03, 0.06, 0.2) * exp(-length(q - vec2(-0.3, -0.05)) * 6.0) * 0.25 + vec3(0.14, 0.04, 0.26) * exp(-length(q - vec2(0.3, -0.05)) * 6.0) * 0.25;
        vec3 fin = vec3(0.35, 0.24, 0.1) * exp(-r * 5.5) * 0.35;
        gl_FragColor = vec4(c * uA + fin * uB, 1.0); }`,
  });
  const bg = new THREE.Mesh(new THREE.PlaneGeometry(40, 40), bgMat); bg.position.z = -14; scene.add(bg);

  // ---- tickets (identical to scene 5's end state), made burnable ----
  const U = { uBurn: { value: 0 }, uRes: { value: new THREE.Vector2(W, H) }, uSeed: { value: 3.7 } };
  const labelFont = await loadFont('cinzel-900');
  const tickets = [];
  for (const [i, L] of LAYOUT.tickets.entries()) {
    const t = await makeTicket(L.kind, { ...LAYOUT.size, labelFont, renderer });
    t.traverse((o) => { if (o.isMesh) { o.material = (Array.isArray(o.material) ? o.material : [o.material]).map((m) => burnable(m.clone(), U)); if (o.material.length === 1) o.material = o.material[0]; } });
    const tp = ticketPose(i, S5_DURATION, 24);
    t.position.copy(tp.pos); t.rotation.copy(tp.rot);
    scene.add(t); tickets.push(t);
  }
  scene.updateMatrixWorld(true);

  // ---- wordmark ----
  const fTop = await loadFont('cinzel-900');
  const fBot = await loadFont('montserrat-600');
  const silver = brushedSilver({ roughness: 0.3, anisotropy: 0.9 });
  const goldPol = gold({ roughness: 0.1, color: '#EBC777' });
  const goldFace = gold({ roughness: 0.24, color: '#E2BC6A' });
  [silver, goldPol, goldFace].forEach((m) => { m.transparent = true; });
  silver.envMap = logoEnv; goldPol.envMap = goldFace.envMap = titleEnv(renderer);
  const logo = new THREE.Group();
  const top = text3D(brand.wordmarkTop, fTop, { size: 0.5, depth: 0.16, bevel: 0.018, tracking: 0.035, materials: [silver, goldPol], curveSegments: 10 });
  const bot = text3D(brand.wordmarkBottom, fBot, { size: 0.25, depth: 0.06, bevel: 0.007, tracking: 0.55, materials: [goldFace, goldPol] });
  top.group.position.y = 0.2; bot.group.position.y = -0.3;
  logo.add(top.group, bot.group);
  const ruleGeo = new THREE.BoxGeometry(1, 0.016, 0.02);
  const rules = [-1, 1].map((sx) => { const r = new THREE.Mesh(ruleGeo, goldPol); r.scale.x = 0.5; r.position.set(sx * (bot.width / 2 + 0.38), -0.3, 0); logo.add(r); return r; });
  const scale = 2.55 / top.width; // wordmark spans ~81% of the frame width
  logo.scale.setScalar(scale);
  logo.position.set(0, 0.42, 0);
  scene.add(logo);
  scene.updateMatrixWorld(true);

  // ---- particles: ticket surfaces -> wordmark surfaces ----
  const N = 42000;
  const from = new Float32Array(N * 3), to = new Float32Array(N * 3);
  const perT = Math.floor(N / 3);
  tickets.forEach((t, i) => { const pts = sampleSurface(t.userData.mesh, i < 2 ? perT : N - perT * 2, 100 + i); from.set(pts, i * perT * 3); });
  const letterMeshes = [...top.letters, ...bot.letters, ...rules];
  const areas = letterMeshes.map((m) => { m.geometry.computeBoundingBox(); const b = m.geometry.boundingBox; return (b.max.x - b.min.x) * (b.max.y - b.min.y) * m.getWorldScale(new THREE.Vector3()).x ** 2; });
  const sumA = areas.reduce((a, b) => a + b, 0);
  let off = 0;
  letterMeshes.forEach((m, i) => {
    const n = i === letterMeshes.length - 1 ? N - off : Math.floor((N * areas[i]) / sumA);
    if (n <= 0) return;
    to.set(sampleSurface(m, n, 300 + i), off * 3); off += n;
  });
  const field = particleField({ from, to, count: N, size: 0.022, intensity: 2.4, seed: 21, swirl: 2.6, turbulence: 1.4 });
  field.material.uniforms.uSpread.value = 0.4;
  scene.add(field);

  // halo + rim ring (callback to the opening ring)
  const haloMat = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    uniforms: { uA: { value: 0 }, uTime: { value: 0 } },
    vertexShader: 'varying vec2 vP; void main(){ vP = position.xy; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); }',
    fragmentShader: noiseGLSL + `uniform float uA, uTime; varying vec2 vP;
      void main(){ vec2 q = vP * vec2(0.62, 1.0); float r = length(q);
        float glow = exp(-r * r * 1.3) * 0.1;
        float ring = exp(-pow((r - 1.45) * 40.0, 2.0)) * (0.35 + 0.65 * smoothstep(-0.2, 0.8, snoise(vec3(atan(q.y, q.x) * 1.5, uTime * 0.5, 0.0))));
        gl_FragColor = vec4(vec3(1.0, 0.74, 0.36) * (glow + ring * 0.0) * uA, 1.0); }`,
  });
  const halo = new THREE.Mesh(new THREE.PlaneGeometry(8, 5), haloMat); halo.position.set(0, 0.42, -0.6); scene.add(halo);
  const glints = [glint({ size: 0.9, intensity: 5 }), glint({ size: 0.6, intensity: 4 }), glint({ size: 0.7, intensity: 4 })];
  glints.forEach((g) => scene.add(g));
  const sweep = new THREE.SpotLight('#ffffff', 0, 12, 0.25, 0.9, 2); sweep.position.set(-3, 2, 3); sweep.target = logo; scene.add(sweep);

  // ---- end-card typography ----
  const DIST = 3.6, fov = 2 * Math.atan(17.5 / 35) * 180 / Math.PI;
  const handle = brand.socialHandle ? (brand.socialHandle.startsWith('@') ? brand.socialHandle : '@' + brand.socialHandle) : brand.handlePlaceholder;
  const tag = await makeTitle(ctx, camera, [
    { text: brand.tagline, font: 'cinzel-700', size: 0.04, tracking: 0.08, y: -0.17, stagger: 0.015, maxWidth: 0.88 },
  ], { dist: DIST, fov, scrimOpacity: 0 });
  const contact = await makeTitle(ctx, camera, [
    { text: `${brand.contactPrefix} ${handle}`, font: 'montserrat-600', size: 0.03, tracking: 0.12, y: -0.24, stagger: 0.012, maxWidth: 0.84 },
  ], { dist: DIST, fov, scrimOpacity: 0 });

  const endPos = new THREE.Vector3(0, 0.38, 5.9), endLook = new THREE.Vector3(0, 0.3, 0);
  const s = {
    scene, camera, clear: 0x050507,
    dof: { focus: 6, aperture: 0, maxCoC: 12 },
    grade: { exposure: 1.0, tint: [1.02, 1.0, 0.98], bloom: 0.55, sat: 1.04 },
    update(lt, T) {
      // camera: holds the scene-5 frame, then settles into a frontal hero framing with a slow push
      const cp = cameraPose(S5_DURATION + Math.max(-0.3, Math.min(lt, 0)));
      const m = cine(remap(lt, 0.3, 2.8));
      const push = smoother(remap(lt, 2.8, 6)) * 0.25;
      camera.position.lerpVectors(cp.pos, endPos, m).add(new THREE.Vector3(0, 0, -push));
      camera.lookAt(new THREE.Vector3().lerpVectors(cp.look, endLook, m));
      camera.setFocalLength(35);
      camera.updateProjectionMatrix();
      bgMat.uniforms.uA.value = 1 - smoother(remap(lt, 0.3, 2.0));
      bgMat.uniforms.uB.value = smoother(remap(lt, 1.8, 3.2));

      // tickets keep floating exactly as in scene 5, then burn away
      tickets.forEach((t, i) => { const tp = ticketPose(i, S5_DURATION + lt, T); t.position.copy(tp.pos); t.rotation.copy(tp.rot); });
      U.uBurn.value = smoother(remap(lt, 0.15, 1.35));
      tickets.forEach((t) => (t.visible = U.uBurn.value < 0.999));

      const u = field.material.uniforms;
      u.uTime.value = T; u.uPx.value = ctx.pxScale(camera);
      u.uMix.value = remap(lt, 0.25, 2.75);
      u.uFade.value = remap(lt, 0.2, 0.6) * (1 - smoother(remap(lt, 2.6, 3.6)));

      // wordmark resolves out of the particles (opacity + slight forward settle), gold rules extend
      const L = smoother(remap(lt, 2.2, 3.0));
      [silver, goldPol, goldFace].forEach((mm) => (mm.opacity = L));
      logo.visible = L > 0.001;
      logo.position.z = (1 - settle(remap(lt, 2.2, 3.2))) * -0.3;
      rules.forEach((r) => (r.scale.x = 0.001 + 0.5 * settle(remap(lt, 2.7, 3.5))));
      scene.environmentRotation.y = track([[2.6, -0.5], [4.4, 0.6, smoother]], lt);
      sweep.intensity = 25 * Math.sin(Math.PI * remap(lt, 3.0, 4.6));
      sweep.position.set(track([[3.0, -3], [4.6, 3]], lt), 2, 3);
      haloMat.uniforms.uA.value = smoother(remap(lt, 2.5, 3.3)) * (1 + 0.6 * Math.exp(-Math.max(0, lt - 3.0) * 5) * (lt > 3 ? 1 : 0)); haloMat.uniforms.uTime.value = T;
      // glints travel across the letters after the impact
      const gs = [[3.15, 0.5, [-1.1, 0.75]], [3.6, 0.5, [0.95, 0.62]], [4.6, 0.6, [0.3, 0.16]]];
      glints.forEach((g, i) => { const [t0, d, p] = gs[i]; const k = remap(lt, t0, t0 + d); g.position.set(p[0], p[1], 0.3); g.material.uniforms.uAmount.value = Math.sin(Math.PI * k); });
      tag.update(lt, 3.35, 'rise', null, 0.5);
      contact.update(lt, 3.9, 'rise', null, 0.5);
      s.grade.exposure = 1 + (lt > 3.0 ? 0.18 * Math.exp(-(lt - 3.0) * 6) : 0);
      s.dof.focus = camera.position.distanceTo(logo.position);
      s.dof.aperture = 1.6;
    },
  };
  return s;
}
