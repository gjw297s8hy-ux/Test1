// SCENE 3 — 00:09–00:14 — CONCERT ENERGY
// Arena with stage deck, box-truss rig, LED wall (pixel-grid shader), moving heads with
// volumetric beams choreographed to 120 BPM, laser fans, ~3,500 instanced crowd silhouettes
// with raised arms, haze. Generic visuals only: no artist, no identifiable performance.
import * as THREE from 'three';
import { rng, track, cine, settle, remap, smoother, studioEnv, makeCanvas, clamp } from '../src/engine/lib.js';
import { beamMaterial, beam, aimBeam, hazeMaterial } from '../shaders/fx.js';
import { emissive } from '../materials/materials.js';
import { noiseGLSL } from '../shaders/noise.glsl.js';
import { makeTitle } from './common/title.js';

const BPM = 120, BEAT = 60 / BPM;
const VIOLET = '#772BFF', BLUE = '#126BFF', GOLDC = '#D6AE57';

// Box truss along +X, centred, as instanced struts (chords + diagonals)
function truss(len, size, mat) {
  const seg = Math.round(len / size);
  const n = 4 + seg * 4 + seg * 4;
  const im = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.035, 0.035, 1, 6), mat, n);
  const M = new THREE.Matrix4(), q = new THREE.Quaternion(), up = new THREE.Vector3(0, 1, 0);
  let k = 0;
  const strut = (a, b) => {
    const d = b.clone().sub(a), L = d.length();
    q.setFromUnitVectors(up, d.normalize());
    M.compose(a.clone().add(b).multiplyScalar(0.5), q, new THREE.Vector3(1, L, 1));
    im.setMatrixAt(k++, M);
  };
  const h = size / 2;
  const corners = [[-h, -h], [h, -h], [h, h], [-h, h]];
  for (const [y, z] of corners) strut(new THREE.Vector3(-len / 2, y, z), new THREE.Vector3(len / 2, y, z));
  for (let i = 0; i < seg; i++) {
    const x0 = -len / 2 + i * size, x1 = x0 + size;
    for (let c = 0; c < 4; c++) {
      const [y0, z0] = corners[c], [y1, z1] = corners[(c + 1) % 4];
      strut(new THREE.Vector3(x0, y0, z0), new THREE.Vector3(x1, y1, z1));
      strut(new THREE.Vector3(x0, y0, z0), new THREE.Vector3(x0, y1, z1));
    }
  }
  im.count = k;
  return im;
}

function silhouetteAtlas() {
  // 8 generic standing figures, several with arms raised; white = body (alpha)
  const W = 1024, H = 256, c = makeCanvas(W, H), x = c.getContext('2d');
  x.fillStyle = '#fff'; x.strokeStyle = '#fff'; x.lineCap = 'round';
  const R = rng(3);
  for (let i = 0; i < 8; i++) {
    const cx = i * 128 + 64, s = 0.85 + R() * 0.2;
    x.save(); x.translate(cx, 250); x.scale(s, s);
    x.beginPath(); x.ellipse(0, -205, 15, 18, 0, 0, Math.PI * 2); x.fill();         // head
    x.beginPath(); x.moveTo(-28, -180); x.quadraticCurveTo(-34, -100, -24, -20); x.lineTo(24, -20); x.quadraticCurveTo(34, -100, 28, -180); x.closePath(); x.fill(); // torso
    x.fillRect(-24, -30, 48, 30);
    x.lineWidth = 15;
    const arms = i % 4; // 0 down, 1 one up, 2 both up, 3 clapping
    const arm = (side, up) => { x.beginPath(); x.moveTo(side * 24, -170); if (up) { x.lineTo(side * (38 + R() * 14), -230); x.lineTo(side * (30 + R() * 20), -290 - R() * 20); } else { x.lineTo(side * 36, -110); x.lineTo(side * 30, -60); } x.stroke(); };
    arm(-1, arms === 2 || arms === 3); arm(1, arms >= 1);
    x.restore();
  }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.NoColorSpace; t.anisotropy = 8; return t;
}

export async function create(ctx) {
  const { renderer, aspect } = ctx;
  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2('#08040f', 0.012);
  scene.environment = studioEnv(renderer, {
    ambient: '#040208',
    panels: [
      { pos: [0, 4, -16], size: [18, 8], color: VIOLET, intensity: 3 },
      { pos: [-10, 9, -8], size: [2, 6], color: BLUE, intensity: 6 },
      { pos: [10, 9, -8], size: [2, 6], color: GOLDC, intensity: 6 },
    ],
  });
  scene.environmentIntensity = 0.6;
  const camera = new THREE.PerspectiveCamera(50, aspect, 0.1, 400);
  camera.filmGauge = 35;
  scene.add(camera);

  // ---- venue shell & stage ----
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(160, 160), new THREE.MeshStandardMaterial({ color: '#0a090c', roughness: 0.35, metalness: 0.2 }));
  floor.rotation.x = -Math.PI / 2; scene.add(floor);
  const deckMat = new THREE.MeshPhysicalMaterial({ color: '#0d0d12', roughness: 0.25, metalness: 0.3, clearcoat: 0.6 });
  const deck = new THREE.Mesh(new THREE.BoxGeometry(40, 1.8, 14), deckMat); deck.position.set(0, 0.9, -38); scene.add(deck);
  const lip = new THREE.Mesh(new THREE.BoxGeometry(40, 0.08, 0.08), emissive(GOLDC, 10)); lip.position.set(0, 1.82, -31); scene.add(lip);
  const runway = new THREE.Mesh(new THREE.BoxGeometry(5, 1.6, 16), deckMat); runway.position.set(0, 0.8, -24); scene.add(runway);
  for (const sx of [-2.52, 2.52]) { const rl = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.06, 16), emissive(VIOLET, 12)); rl.position.set(sx, 1.62, -24); scene.add(rl); }

  // LED wall: generic geometric content, beat-reactive, with a resolved pixel grid
  const ledMat = new THREE.ShaderMaterial({
    uniforms: { uTime: { value: 0 }, uBeat: { value: 0 }, uA: { value: new THREE.Color(VIOLET) }, uB: { value: new THREE.Color(BLUE) }, uC: { value: new THREE.Color(GOLDC) }, uGain: { value: 1.0 } },
    vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); }',
    fragmentShader: noiseGLSL + /* glsl */ `
      uniform float uTime, uBeat, uGain; uniform vec3 uA, uB, uC; varying vec2 vUv;
      void main(){
        vec2 res = vec2(288.0, 128.0);
        vec2 p = floor(vUv * res) / res;               // sample content per LED pixel
        vec2 q = (p - 0.5) * vec2(2.25, 1.0);
        float r = length(q);
        float rings = 0.5 + 0.5 * sin(r * 22.0 - uTime * 6.0);
        float bars = step(0.5, fract(q.x * 6.0 + uTime * 0.8 * sign(q.y)));
        float n = snoise(vec3(q * 2.5, uTime * 0.4));
        vec3 col = mix(uA, uB, smoothstep(-0.4, 0.4, n));
        col = mix(col, uC, smoothstep(0.85, 0.98, rings) * 0.7 * smoothstep(0.9, 0.2, r));
        col *= 0.12 + 0.55 * mix(rings, bars, 0.25 + 0.25 * sin(uTime * 0.7));
        col *= 0.6 + 1.6 * uBeat;
        col += uC * exp(-r * 6.0) * (0.5 + 1.5 * uBeat);
        // pixel grid with gaps, anti-aliased when the pitch goes sub-pixel
        vec2 f = fract(vUv * res);
        float w = clamp(1.0 - max(fwidth(vUv.x * res.x), fwidth(vUv.y * res.y)) * 1.2, 0.0, 1.0);
        float grid = smoothstep(0.08, 0.2, f.x) * smoothstep(0.92, 0.8, f.x) * smoothstep(0.08, 0.2, f.y) * smoothstep(0.92, 0.8, f.y);
        col *= mix(0.55, grid, w);
        gl_FragColor = vec4(col * uGain, 1.0);
      }`,
  });
  const led = new THREE.Mesh(new THREE.PlaneGeometry(36, 16), ledMat); led.position.set(0, 10.5, -44.5); scene.add(led);
  const sideLeds = [-24, 24].map((x) => { const m = new THREE.Mesh(new THREE.PlaneGeometry(5, 16), ledMat); m.position.set(x, 10.5, -42); m.rotation.y = -Math.sign(x) * 0.35; scene.add(m); return m; });

  // ---- truss rig ----
  const trussMat = new THREE.MeshStandardMaterial({ color: '#9aa0aa', roughness: 0.35, metalness: 0.9 });
  const rig = new THREE.Group();
  for (const [y, z, len] of [[21, -40, 46], [17, -33, 42], [13, -28, 34]]) { const t = truss(len, 0.55, trussMat); t.position.set(0, y, z); rig.add(t); }
  for (const x of [-23, 23]) { const t = truss(21, 0.55, trussMat); t.rotation.z = Math.PI / 2; t.position.set(x, 10.5, -40); rig.add(t); }
  scene.add(rig);

  // ---- moving heads with beams ----
  const headBody = new THREE.MeshStandardMaterial({ color: '#16161b', roughness: 0.4, metalness: 0.7 });
  const heads = [];
  const cols = [VIOLET, BLUE, GOLDC, BLUE, VIOLET, GOLDC];
  const mkHead = (x, y, z, i) => {
    const g = new THREE.Group();
    const yoke = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.35, 0.4), headBody); yoke.position.y = 0.3; g.add(yoke);
    const lensM = emissive(cols[i % cols.length], 40);
    const lens = new THREE.Mesh(new THREE.CircleGeometry(0.18, 20), lensM); lens.position.y = -0.01; lens.rotation.x = Math.PI / 2; g.add(lens);
    g.position.set(x, y - 0.6, z);
    const bm = beamMaterial({ color: cols[i % cols.length], intensity: 2.4, noise: 0.8, falloff: 0.8 });
    const b = beam(40, 2.0, bm); b.position.set(x, y - 0.7, z);
    scene.add(g, b);
    heads.push({ g, b, bm, lensM, i, x, z });
  };
  for (let i = 0; i < 12; i++) mkHead(-20 + i * (40 / 11), 17, -33, i);
  for (let i = 0; i < 8; i++) mkHead(-15 + i * (30 / 7), 13, -28, i + 3);

  // ---- sky beams: fan up from the stage towers, filling the space above the rig ----
  const sky = [];
  for (let i = 0; i < 10; i++) {
    const m = beamMaterial({ color: i % 3 === 0 ? GOLDC : i % 3 === 1 ? VIOLET : BLUE, intensity: 1.6, noise: 0.7, falloff: 0.9 });
    const b = beam(70, 3.2, m);
    b.position.set(-22 + (i / 9) * 44, 2, -41);
    scene.add(b); sky.push({ b, m, i });
  }

  // ---- laser fans ----
  const lasers = [];
  const laserGeo = new THREE.CylinderGeometry(0.06, 0.06, 1, 5); laserGeo.translate(0, 0.5, 0);
  for (let i = 0; i < 18; i++) {
    const m = new THREE.Mesh(laserGeo, new THREE.MeshBasicMaterial({ color: new THREE.Color(i % 3 === 0 ? GOLDC : i % 3 === 1 ? BLUE : VIOLET).multiplyScalar(60), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
    m.position.set(0, 12, -44); m.scale.y = 110; scene.add(m); lasers.push(m);
  }

  // ---- crowd silhouettes (instanced, deterministic) ----
  const atlas = silhouetteAtlas();
  const NC = 3600;
  const crowdMat = new THREE.ShaderMaterial({
    transparent: false, side: THREE.DoubleSide,
    uniforms: { uAtlas: { value: atlas }, uTime: { value: 0 }, uRim: { value: new THREE.Color(VIOLET) }, uRim2: { value: new THREE.Color(BLUE) }, uBeat: { value: 0 } },
    vertexShader: /* glsl */ `
      attribute vec4 aR; varying vec2 vUv; varying vec4 vR; varying float vD;
      uniform float uTime, uBeat;
      void main(){
        vR = aR;
        vUv = vec2((uv.x + floor(aR.x * 8.0)) / 8.0, uv.y);
        vec3 p = position;
        float jump = max(0.0, sin(uTime * 3.14159 * 2.0 + aR.y * 6.28)) * 0.12 * step(0.55, aR.z);
        p.y += jump;
        vec4 w = modelMatrix * instanceMatrix * vec4(p, 1.0);
        vec4 mv = viewMatrix * w; vD = -mv.z;
        gl_Position = projectionMatrix * mv;
      }`,
    fragmentShader: /* glsl */ `
      uniform sampler2D uAtlas; uniform vec3 uRim, uRim2; uniform float uBeat; varying vec2 vUv; varying vec4 vR; varying float vD;
      void main(){
        float a = texture2D(uAtlas, vUv).r;
        if (a < 0.5) discard;
        // rim from the stage: edge detection on the atlas alpha
        float e = 0.0; vec2 o = vec2(0.004, 0.012);
        e += 1.0 - texture2D(uAtlas, vUv + vec2(o.x, 0.0)).r; e += 1.0 - texture2D(uAtlas, vUv - vec2(o.x, 0.0)).r; e += 1.0 - texture2D(uAtlas, vUv + vec2(0.0, o.y)).r;
        vec3 rim = mix(uRim, uRim2, vR.w) * e * (0.4 + 0.5 * uBeat) * 0.9 * vUv.y;
        vec3 col = vec3(0.006, 0.005, 0.01) + rim * exp(-vD * 0.02);
        gl_FragColor = vec4(col, 1.0);
      }`,
  });
  const cg = new THREE.PlaneGeometry(0.62, 1.8); cg.translate(0, 0.9, 0);
  const crowd = new THREE.InstancedMesh(cg, crowdMat, NC);
  const aR = new Float32Array(NC * 4);
  const R = rng(17);
  const M = new THREE.Matrix4();
  for (let i = 0; i < NC; i++) {
    const x = (R() - 0.5) * 56, z = -20 + R() * 46;
    if (Math.abs(x) < 3.2 && z < -15) { i--; continue; }
    const s = 0.9 + R() * 0.2;
    M.compose(new THREE.Vector3(x, 0, z), new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), (R() - 0.5) * 0.4), new THREE.Vector3(s, s, s));
    crowd.setMatrixAt(i, M);
    aR.set([R(), R(), R(), R()], i * 4);
  }
  crowd.geometry.setAttribute('aR', new THREE.InstancedBufferAttribute(aR, 4));
  crowd.frustumCulled = false;
  scene.add(crowd);

  // stage wash lights (real lights so deck/truss/floor respond)
  const washes = [];
  for (const [x, c] of [[-12, VIOLET], [0, GOLDC], [12, BLUE]]) {
    const s = new THREE.SpotLight(c, 1800, 0, 0.6, 0.7, 2); s.position.set(x, 20, -20); s.target.position.set(x * 0.5, 0, -36); scene.add(s, s.target); washes.push(s);
  }
  const audienceLight = new THREE.SpotLight('#b89cff', 900, 0, 0.9, 1, 2); audienceLight.position.set(0, 22, -30); audienceLight.target.position.set(0, 0, 5); scene.add(audienceLight, audienceLight.target);

  const hazes = [];
  for (let i = 0; i < 6; i++) {
    const h = new THREE.Mesh(new THREE.PlaneGeometry(90, 40), hazeMaterial({ color: i % 2 ? '#8a6bff' : '#6aa0ff', intensity: 0.035, scale: 0.06, speed: 0.12 }));
    h.position.set(0, 14, -42 + i * 4); scene.add(h); hazes.push(h);
  }

  const DIST = 3.4;
  const title = await makeTitle(ctx, camera, [
    { text: 'LES CONCERTS', font: 'cinzel-700', size: 0.045, tracking: 0.2, y: 0.3 },
    { text: 'INOUBLIABLES', font: 'cinzel-900', size: 0.085, tracking: 0.04, y: 0.225, delay: 0.1, stagger: 0.03, maxWidth: 0.88 },
  ], { dist: DIST, fov: 2 * Math.atan(17.5 / 28) * 180 / Math.PI });

  const s = {
    scene, camera, clear: 0x030106,
    dof: { focus: 30, aperture: 0, maxCoC: 12 },
    grade: { exposure: 1.0, tint: [1.02, 0.98, 1.05], bloom: 0.75, sat: 1.08 },
    update(lt, T) {
      const beatPh = (T % BEAT) / BEAT;
      const beat = Math.exp(-beatPh * 5);
      this.beat = beat;
      const bar = Math.floor(T / (BEAT * 4));
      // camera: rises over the crowd and glides toward the stage with a slow orbit
      const u = cine(remap(lt, -0.35, 5.35));
      const ang = THREE.MathUtils.lerp(0.28, -0.12, u);
      const dist = THREE.MathUtils.lerp(70, 44, u);
      camera.position.set(Math.sin(ang) * dist, THREE.MathUtils.lerp(4.5, 8.0, smoother(u)), -38 + Math.cos(ang) * dist);
      camera.lookAt(0, THREE.MathUtils.lerp(10.5, 11.5, u), -38);
      camera.setFocalLength(28);
      camera.updateProjectionMatrix();

      ledMat.uniforms.uTime.value = T; ledMat.uniforms.uBeat.value = beat;
      crowdMat.uniforms.uTime.value = T; crowdMat.uniforms.uBeat.value = beat;
      heads.forEach(({ g, b, bm, lensM, i, x, z }) => {
        // choreography changes every bar: fan, cross, audience sweep
        const mode = bar % 3;
        let tx, tz;
        if (mode === 0) { tx = x * 2.2 + Math.sin(T * 1.6 + i * 0.4) * 8; tz = 10 + Math.cos(T * 1.2) * 8; }
        else if (mode === 1) { tx = -x * 1.8; tz = 0 + Math.sin(T * 2.0 + i) * 10; }
        else { tx = Math.sin(T * 1.4 + i * 0.6) * 30; tz = 15 * Math.cos(T * 0.9 + i * 0.3); }
        const target = new THREE.Vector3(tx, 3, tz);
        aimBeam(b, target);
        g.lookAt(target);
        const on = 0.55 + 0.45 * (i % 2 ? beat : 1 - beat);
        bm.uniforms.uIntensity.value = 2.4 * on; bm.uniforms.uTime.value = T;
        lensM.color.set(cols[i % cols.length]).multiplyScalar(40 * on);
      });
      sky.forEach(({ b, m, i }) => {
        const sway = Math.sin(T * 1.1 + i * 0.7) * 0.35 + (bar % 2 ? 0.25 : -0.25) * Math.sign(i - 4.5);
        aimBeam(b, new THREE.Vector3(b.position.x + Math.sin(sway) * 60, 70, -41 + 25 + Math.cos(T * 0.5 + i) * 10));
        m.uniforms.uTime.value = T;
        m.uniforms.uIntensity.value = 1.4 * (0.6 + 0.4 * (i % 2 ? beat : 1 - beat));
      });
      lasers.forEach((m, i) => {
        const fan = Math.sin(T * 1.3) * 0.6;
        const a = (i / (lasers.length - 1) - 0.5) * 1.6 + fan * 0.3;
        m.rotation.set(-Math.PI / 2 + 0.12 + 0.05 * Math.sin(T * 2 + i), 0, a);
        m.material.opacity = (bar % 2 === 0 ? 0.9 : 0.35) * (0.4 + 0.6 * beat) * remap(lt, 0.3, 0.8);
      });
      washes.forEach((w, i) => (w.intensity = 1800 * (0.6 + 0.4 * beat)));
      hazes.forEach((h) => { h.material.uniforms.uTime.value = T; h.lookAt(camera.position.x, h.position.y, camera.position.z); });
      title.update(lt, 1.6, 'zoom', 4.6, 0.55);
      s.grade.exposure = 1.0 + 0.08 * beat;
      s.dof.focus = camera.position.distanceTo(new THREE.Vector3(0, 9, -38)) * 0.75;
      s.dof.aperture = 1.6;
    },
  };
  return s;
}
