// SCENE 2 — 00:04–00:09 — FOOTBALL IMMERSION
// Procedural night stadium: superellipse bowl, three seating tiers with shader-driven crowd,
// LED fascia ribbons, cantilever roof with truss, floodlight banks with volumetric beams,
// mown pitch with markings, haze. Crane descent from aerial to pitch level; a metallic
// football spins through the foreground; "LES PLUS GRANDS MATCHS" lands on the beat.
import * as THREE from 'three';
import { rng, track, cine, settle, remap, smoother, studioEnv, makeCanvas, clamp, easeInCubic, easeOutCubic } from '../src/engine/lib.js';
import { beamMaterial, beam, aimBeam, hazeMaterial, glint } from '../shaders/fx.js';
import { gold, chrome, emissive } from '../materials/materials.js';
import { titleEnv } from '../src/engine/lib.js';
import { noiseGLSL } from '../shaders/noise.glsl.js';
import { makeTitle } from './common/title.js';

const A = 63, B = 46, NEXP = 4.2; // bowl inner superellipse half-axes (m)
function se(theta, a, b) {
  const c = Math.cos(theta), s = Math.sin(theta);
  return [a * Math.sign(c) * Math.pow(Math.abs(c), 2 / NEXP), b * Math.sign(s) * Math.pow(Math.abs(s), 2 / NEXP)];
}

// Ribbon surface around the bowl: rows from (offset d0, height y0) to (d1, y1)
function bowlRibbon(d0, y0, d1, y1, seg = 720) {
  const pos = [], uv = [], idx = [];
  let arc = 0, prev = null;
  for (let i = 0; i <= seg; i++) {
    const th = (i / seg) * Math.PI * 2;
    const p0 = se(th, A + d0, B + d0), p1 = se(th, A + d1, B + d1);
    if (prev) arc += Math.hypot(p0[0] - prev[0], p0[1] - prev[1]);
    prev = p0;
    pos.push(p0[0], y0, p0[1], p1[0], y1, p1[1]);
    uv.push(arc, 0, arc, 1);
    if (i < seg) { const k = i * 2; idx.push(k, k + 1, k + 2, k + 1, k + 3, k + 2); }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
}

function crowdMaterial(rows, light) {
  return new THREE.ShaderMaterial({
    side: THREE.DoubleSide,
    uniforms: { uTime: { value: 0 }, uRows: { value: rows }, uLight: { value: light }, uFog: { value: new THREE.Color('#0b1220') }, uFogD: { value: 0.0042 }, uFlash: { value: 1 } },
    vertexShader: `varying vec2 vUv; varying vec3 vW; void main(){ vUv = uv; vec4 w = modelMatrix*vec4(position,1.0); vW = w.xyz; gl_Position = projectionMatrix*viewMatrix*w; }`,
    fragmentShader: noiseGLSL + /* glsl */ `
      uniform float uTime, uRows, uLight, uFogD, uFlash; uniform vec3 uFog; varying vec2 vUv; varying vec3 vW;
      void main(){
        float row = vUv.y * uRows;
        vec2 cell = vec2(floor(vUv.x / 0.58), floor(row));
        vec2 f = vec2(fract(vUv.x / 0.58), fract(row));
        float h = hash12(cell), h2 = hash12(cell + 17.3), h3 = hash12(cell * 1.7 + 3.1);
        // clothing palette: dark neutrals, a few saturated colours (no club colours implied)
        vec3 c = mix(vec3(0.09,0.09,0.1), vec3(0.42,0.38,0.34), h);
        if (h2 > 0.8) c = mix(vec3(0.7,0.14,0.1), vec3(0.12,0.28,0.7), h3) * 0.8;
        if (h2 < 0.12) c = vec3(0.75, 0.72, 0.66);
        // person silhouette in the seat cell: head + shoulders, slight bob
        float bob = 0.06 * sin(uTime * (3.0 + h * 4.0) + h3 * 30.0) * step(0.55, h3);
        float body = smoothstep(0.42, 0.3, abs(f.x - 0.5)) * smoothstep(0.05, 0.2, f.y) * smoothstep(0.78 + bob, 0.6 + bob, f.y);
        float head = smoothstep(0.2, 0.12, length((f - vec2(0.5, 0.82 + bob)) * vec2(1.0, 1.4)));
        float person = max(body, head) * step(0.06, h3);       // a few empty seats
        vec3 seat = vec3(0.05, 0.055, 0.07);
        vec3 col = mix(seat, c, person);
        // floodlight falloff: front rows brighter, banding by light bank
        float lit = uLight * (0.75 + 0.25 * smoothstep(0.0, 1.0, 1.0 - vUv.y)) * (0.85 + 0.3 * snoise(vec3(vW.xz * 0.02, 0.0)));
        col *= lit;
        // phone lights and camera flashes
        float ph = step(0.9965, hash12(cell + 91.0)) * (0.6 + 0.4 * sin(uTime * 2.0 + h * 50.0));
        float fl = step(0.9992, hash12(cell + floor(uTime * 12.0) * 7.13)) * uFlash;
        col += vec3(1.0, 0.97, 0.9) * (ph * 1.5 + fl * 25.0) * person;
        // anti-alias: when a seat cell shrinks below ~2px, resolve to the cell-average colour
        float aa = clamp(fwidth(vUv.x / 0.58) * 1.6 + fwidth(row) * 1.6 - 0.15, 0.0, 1.0);
        vec3 avg = vec3(0.17, 0.165, 0.17) * lit * (0.85 + 0.3 * snoise(vec3(vUv.x * 0.08, row * 0.1, 0.0)));
        col = mix(col, avg + vec3(1.0,0.97,0.9) * ph * 0.08, aa);
        float d = length(vW - cameraPosition);
        col = mix(uFog, col, exp(-pow(d * uFogD, 1.6)));
        gl_FragColor = vec4(col, 1.0);
      }`,
  });
}

function pitchTexture() {
  const W = 2100, H = 1360; // 20 px per metre over a 105 x 68 pitch
  const c = makeCanvas(W, H), x = c.getContext('2d');
  const R = rng(5);
  for (let i = 0; i < 18; i++) { x.fillStyle = i % 2 ? '#2f7030' : '#29632a'; x.fillRect((i * W) / 18, 0, W / 18 + 1, H); }
  // checker overlay for the cross-cut mowing pattern
  for (let j = 0; j < 12; j++) { x.fillStyle = j % 2 ? 'rgba(255,255,255,0.012)' : 'rgba(0,0,0,0.015)'; x.fillRect(0, (j * H) / 12, W, H / 12 + 1); }
  for (let i = 0; i < 40000; i++) { x.fillStyle = `rgba(${R() < 0.5 ? '20,40,15' : '120,170,90'},${0.08 * R()})`; x.fillRect(R() * W, R() * H, 2, 2); }
  const m = 20; x.strokeStyle = 'rgba(245,245,240,0.95)'; x.lineWidth = 2.6;
  x.strokeRect(0.5 * m, 0.5 * m, W - m, H - m);
  x.beginPath(); x.moveTo(W / 2, 0.5 * m); x.lineTo(W / 2, H - 0.5 * m); x.stroke();
  x.beginPath(); x.arc(W / 2, H / 2, 9.15 * m, 0, Math.PI * 2); x.stroke();
  x.fillStyle = 'rgba(245,245,240,0.95)'; x.beginPath(); x.arc(W / 2, H / 2, 0.3 * m, 0, Math.PI * 2); x.fill();
  for (const side of [0, 1]) {
    const sx = side ? W - 0.5 * m : 0.5 * m, dir = side ? -1 : 1;
    x.strokeRect(side ? sx - 16.5 * m : sx, H / 2 - 20.16 * m, 16.5 * m, 40.32 * m);
    x.strokeRect(side ? sx - 5.5 * m : sx, H / 2 - 9.16 * m, 5.5 * m, 18.32 * m);
    x.beginPath(); x.arc(sx + dir * 11 * m, H / 2, 0.3 * m, 0, Math.PI * 2); x.fill();
    x.beginPath(); x.arc(sx + dir * 11 * m, H / 2, 9.15 * m, side ? Math.PI - 0.93 : -0.93, side ? Math.PI + 0.93 : 0.93); x.stroke();
  }
  for (const [cx, cy, a0] of [[0.5 * m, 0.5 * m, 0], [W - 0.5 * m, 0.5 * m, Math.PI / 2], [W - 0.5 * m, H - 0.5 * m, Math.PI], [0.5 * m, H - 0.5 * m, -Math.PI / 2]]) {
    x.beginPath(); x.arc(cx, cy, 1 * m, a0, a0 + Math.PI / 2); x.stroke();
  }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 16; return t;
}

function ledTexture() {
  const c = makeCanvas(2048, 64), x = c.getContext('2d');
  const g = x.createLinearGradient(0, 0, 2048, 0);
  g.addColorStop(0, '#1a1205'); g.addColorStop(0.5, '#3a2a0c'); g.addColorStop(1, '#1a1205');
  x.fillStyle = g; x.fillRect(0, 0, 2048, 64);
  x.fillStyle = '#ffd27a'; x.font = '700 40px Cinzel'; x.textBaseline = 'middle';
  for (let i = 0; i < 4; i++) x.fillText('WESTAFF PLACE', 60 + i * 512, 34);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.wrapS = THREE.RepeatWrapping; return t;
}

// Truncated-icosahedron football: Voronoi of the 12 + 20 face centres on a dense sphere.
function footballGeometry(r) {
  const g = new THREE.IcosahedronGeometry(r, 48);
  const phi = (1 + Math.sqrt(5)) / 2;
  const P = [], H = [];
  for (const [a, b] of [[1, phi], [-1, phi], [1, -phi], [-1, -phi]]) { P.push([0, a, b], [a, b, 0], [b, 0, a]); }
  for (const x of [-1, 1]) for (const y of [-1, 1]) for (const z of [-1, 1]) H.push([x, y, z]);
  for (const [a, b] of [[1 / phi, phi], [-1 / phi, phi], [1 / phi, -phi], [-1 / phi, -phi]]) { H.push([0, a, b], [a, b, 0], [b, 0, a]); }
  const centres = [...P.map((p) => [new THREE.Vector3(...p).normalize(), 1]), ...H.map((p) => [new THREE.Vector3(...p).normalize(), 0])];
  const pos = g.attributes.position;
  const panel = new Float32Array(pos.count);
  const v = new THREE.Vector3();
  for (let i = 0; i < pos.count; i++) {
    v.fromBufferAttribute(pos, i).normalize();
    let d1 = -2, d2 = -2, k = 0;
    for (const [c, isP] of centres) { const d = v.dot(c); if (d > d1) { d2 = d1; d1 = d; k = isP; } else if (d > d2) d2 = d; }
    const seam = clamp((d1 - d2) / 0.035); // 0 on the seam
    const depth = 1 - 0.018 * (1 - smoother(seam)) + 0.004 * smoother(seam);
    v.multiplyScalar(r * depth);
    pos.setXYZ(i, v.x, v.y, v.z);
    panel[i] = k;
  }
  g.setAttribute('aPanel', new THREE.BufferAttribute(panel, 1));
  g.computeVertexNormals();
  // two material groups via vertex colours: pentagons gold, hexagons chrome
  const colors = new Float32Array(pos.count * 3);
  const gc = new THREE.Color('#E4BC66'), sc = new THREE.Color('#e9ecf2');
  for (let i = 0; i < pos.count; i++) { const c = panel[i] ? gc : sc; colors.set([c.r, c.g, c.b], i * 3); }
  g.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  return g;
}

export async function create(ctx) {
  const { renderer, aspect } = ctx;
  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2('#0b1220', 0.0042);
  // stadium environment: dark sky, ring of floodlight banks, green floor bounce
  const panels = [];
  for (let i = 0; i < 16; i++) { const a = (i / 16) * Math.PI * 2; panels.push({ pos: [Math.cos(a) * 16, 9, Math.sin(a) * 12], size: [3, 0.9], color: '#f4f6ff', intensity: 22, lookAt: [0, 0, 0] }); }
  panels.push({ pos: [0, 16, 0], size: [30, 30], color: '#0e1830', intensity: 1 });
  scene.environment = studioEnv(renderer, { ambient: '#05070c', floor: '#13351a', panels });
  scene.environmentIntensity = 0.55;

  const camera = new THREE.PerspectiveCamera(50, aspect, 0.1, 900);
  camera.filmGauge = 35;
  scene.add(camera);

  // ---- pitch & surround ----
  const pitchTex = pitchTexture();
  const grassRough = new THREE.CanvasTexture((() => { const c = makeCanvas(512, 512), x = c.getContext('2d'); const R = rng(9); x.fillStyle = '#b0b0b0'; x.fillRect(0, 0, 512, 512); for (let i = 0; i < 30000; i++) { const v = 120 + R() * 120; x.fillStyle = `rgb(${v},${v},${v})`; x.fillRect(R() * 512, R() * 512, 1, 2); } return c; })());
  grassRough.wrapS = grassRough.wrapT = THREE.RepeatWrapping; grassRough.repeat.set(60, 40);
  const pitch = new THREE.Mesh(new THREE.PlaneGeometry(105, 68), new THREE.MeshStandardMaterial({ map: pitchTex, roughness: 0.92, roughnessMap: grassRough, bumpMap: grassRough, bumpScale: 0.6 }));
  pitch.rotation.x = -Math.PI / 2; pitch.receiveShadow = true;
  scene.add(pitch);
  const surround = new THREE.Mesh(new THREE.PlaneGeometry(150, 120), new THREE.MeshStandardMaterial({ color: '#1d4a1f', roughness: 0.95 }));
  surround.rotation.x = -Math.PI / 2; surround.position.y = -0.02; scene.add(surround);
  // goals (posts + net frame)
  const postMat = new THREE.MeshStandardMaterial({ color: '#f2f2f2', roughness: 0.35, metalness: 0.1 });
  for (const sx of [-52.5, 52.5]) {
    const goal = new THREE.Group();
    const post = new THREE.CylinderGeometry(0.06, 0.06, 2.44, 12);
    const p1 = new THREE.Mesh(post, postMat); p1.position.set(0, 1.22, -3.66);
    const p2 = p1.clone(); p2.position.z = 3.66;
    const bar = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 7.32, 12), postMat); bar.rotation.x = Math.PI / 2; bar.position.y = 2.44;
    const net = new THREE.Mesh(new THREE.BoxGeometry(2, 2.44, 7.32), new THREE.MeshStandardMaterial({ color: '#ffffff', transparent: true, opacity: 0.18, roughness: 1, wireframe: true }));
    net.position.set(Math.sign(sx) * 1, 1.22, 0);
    goal.add(p1, p2, bar, net); goal.position.x = sx; scene.add(goal);
  }

  // ---- bowl ----
  const tiers = [
    { d0: 8, y0: 1.2, d1: 26, y1: 11, rows: 26 },
    { d0: 29, y0: 15, d1: 43, y1: 25, rows: 20 },
    { d0: 45, y0: 29, d1: 60, y1: 41, rows: 22 },
  ];
  const crowdMats = [];
  const concrete = new THREE.MeshStandardMaterial({ color: '#2a2c33', roughness: 0.85, metalness: 0.0 });
  const led = ledTexture();
  led.repeat.set(14, 1);
  const ledMat = new THREE.MeshBasicMaterial({ map: led, color: new THREE.Color(2.2, 2.2, 2.2) });
  for (const t of tiers) {
    const m = crowdMaterial(t.rows, 1.1);
    crowdMats.push(m);
    scene.add(new THREE.Mesh(bowlRibbon(t.d0, t.y0, t.d1, t.y1), m));
    // fascia below the front row (with LED ribbon on upper tiers)
    const fascia = new THREE.Mesh(bowlRibbon(t.d0 - 0.2, t.y0 - (t.y0 > 2 ? 3.2 : 1.2), t.d0, t.y0), t.y0 > 2 ? ledMat : concrete);
    scene.add(fascia);
    // walkway between tiers
    scene.add(new THREE.Mesh(bowlRibbon(t.d1, t.y1, t.d1 + 2.5, t.y1), concrete));
  }
  scene.add(new THREE.Mesh(bowlRibbon(61, 41, 61.5, 47), concrete)); // back wall
  scene.add(new THREE.Mesh(bowlRibbon(4, 0.02, 8, 1.2), new THREE.MeshStandardMaterial({ color: '#173a1a', roughness: 0.95 })));
  // perimeter advertising boards: generic gold/black LED with brand only
  scene.add(new THREE.Mesh(bowlRibbon(5.5, 0.02, 5.6, 1.0), ledMat));

  // ---- roof: cantilever ring with truss and floodlight rim ----
  const roofMat = new THREE.MeshStandardMaterial({ color: '#1a1c22', roughness: 0.7, metalness: 0.6, side: THREE.DoubleSide });
  scene.add(new THREE.Mesh(bowlRibbon(30, 50, 66, 47), roofMat));
  const trussMat = new THREE.MeshStandardMaterial({ color: '#3a3d45', roughness: 0.5, metalness: 0.8 });
  const nTruss = 96;
  const truss = new THREE.InstancedMesh(new THREE.BoxGeometry(0.35, 0.35, 1), trussMat, nTruss * 2);
  const lampGeo = new THREE.BoxGeometry(1.4, 0.7, 0.3);
  const lamps = new THREE.InstancedMesh(lampGeo, emissive('#f4f7ff', 60), nTruss * 2);
  const M = new THREE.Matrix4(), q = new THREE.Quaternion(), sc = new THREE.Vector3();
  const lampPos = [];
  for (let i = 0; i < nTruss; i++) {
    const th = (i / nTruss) * Math.PI * 2;
    const [ix, iz] = se(th, A + 30, B + 30), [ox, oz] = se(th, A + 66, B + 66);
    const a = new THREE.Vector3(ix, 49.6, iz), b = new THREE.Vector3(ox, 47, oz);
    const mid = a.clone().add(b).multiplyScalar(0.5), len = a.distanceTo(b);
    q.setFromUnitVectors(new THREE.Vector3(0, 0, 1), b.clone().sub(a).normalize());
    M.compose(mid.clone().setY(mid.y - 1.2), q, sc.set(1, 1, len)); truss.setMatrixAt(i * 2, M);
    M.compose(mid.clone().setY(mid.y - 0.3), q, sc.set(1, 6, len * 0.9)); truss.setMatrixAt(i * 2 + 1, M);
    for (const k of [0, 1]) {
      const lp = new THREE.Vector3(ix, 49.1 - k * 0.8, iz).multiplyScalar(1);
      const look = new THREE.Vector3(0, 0, 0);
      const mm = new THREE.Matrix4().lookAt(lp, look, new THREE.Vector3(0, 1, 0));
      M.compose(lp, new THREE.Quaternion().setFromRotationMatrix(mm), sc.set(1, 1, 1));
      lamps.setMatrixAt(i * 2 + k, M);
    }
    lampPos.push(new THREE.Vector3(ix, 49, iz));
  }
  scene.add(truss, lamps);

  // ---- lighting ----
  scene.add(new THREE.HemisphereLight('#7f93c4', '#0d2210', 0.12));
  const R = rng(33);
  const floods = [];
  for (const [x, z] of [[-55, -38], [55, -38], [-55, 38], [55, 38]]) {
    const s = new THREE.SpotLight('#f3f5ff', 10000, 0, 0.85, 0.85, 2);
    s.position.set(x * 1.3, 52, z * 1.3); s.target.position.set(x * 0.05, 0, z * 0.05);
    scene.add(s, s.target); floods.push(s);
  }
  floods[0].castShadow = true; floods[0].shadow.mapSize.set(1024, 1024); floods[0].shadow.camera.near = 20; floods[0].shadow.camera.far = 200;

  // volumetric floodlight beams from the roof rim, plus sweeping show beams
  const beams = [];
  const bm = beamMaterial({ color: '#dfe6ff', intensity: 0.22, noise: 0.6, falloff: 1.4 });
  for (let i = 0; i < 16; i++) {
    const lp = lampPos[(i * 6 + 2) % nTruss];
    const b = beam(80, 9, bm); b.position.copy(lp);
    aimBeam(b, new THREE.Vector3((R() - 0.5) * 60, 0, (R() - 0.5) * 40)); scene.add(b);
  }
  const showCols = ['#ffffff', '#D6AE57', '#126BFF', '#ffffff', '#D6AE57', '#126BFF'];
  for (let i = 0; i < 6; i++) {
    const m = beamMaterial({ color: showCols[i], intensity: 0.5, noise: 0.7, falloff: 1.1 });
    const b = beam(110, 5, m);
    const lp = lampPos[Math.floor((i / 6) * nTruss + 8) % nTruss];
    b.position.copy(lp); scene.add(b);
    beams.push({ b, m, ph: i * 1.7, lp });
  }
  // haze sheets inside the bowl
  const hazes = [];
  for (let i = 0; i < 5; i++) {
    const h = new THREE.Mesh(new THREE.PlaneGeometry(200, 60), hazeMaterial({ color: '#9fb4e8', intensity: 0.05, scale: 0.03, speed: 0.08 }));
    h.position.set(0, 8 + i * 7, -40 + i * 20); scene.add(h); hazes.push(h);
  }

  // ---- metallic football (foreground) ----
  const ballMat = new THREE.MeshPhysicalMaterial({ vertexColors: true, metalness: 1, roughness: 0.16, clearcoat: 0.6, clearcoatRoughness: 0.05, envMap: titleEnv(renderer), envMapIntensity: 1.1 });
  const ball = new THREE.Mesh(footballGeometry(0.3), ballMat);
  const ballRig = new THREE.Group(); ballRig.add(ball); camera.add(ballRig);
  const ballKey = new THREE.PointLight('#fff4e0', 0, 6, 2); camera.add(ballKey); ballKey.position.set(-1, 1, -0.8);
  const ballRim = new THREE.PointLight('#8fb0ff', 0, 6, 2); camera.add(ballRim); ballRim.position.set(1.4, 0.6, -3.4);
  const gl = glint({ size: 1.2, intensity: 4 }); camera.add(gl);

  // ---- title ----
  const DIST = 3.2;
  const title = await makeTitle(ctx, camera, [
    { text: 'LES PLUS GRANDS', font: 'cinzel-700', size: 0.042, tracking: 0.2, y: 0.3 },
    { text: 'MATCHS', font: 'cinzel-900', size: 0.115, tracking: 0.06, y: 0.215, delay: 0.12, stagger: 0.04 },
  ], { dist: DIST, fov: 2 * Math.atan(17.5 / 24) * 180 / Math.PI });

  // camera crane: aerial -> sweeping descent -> pitch level
  const path = new THREE.CatmullRomCurve3([
    new THREE.Vector3(-6, 170, 70), new THREE.Vector3(22, 118, 72), new THREE.Vector3(38, 52, 52), new THREE.Vector3(26, 12, 40), new THREE.Vector3(14, 2.2, 36),
  ], false, 'centripetal');
  const look = new THREE.CatmullRomCurve3([
    new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, 0, 0), new THREE.Vector3(-2, 2, 0), new THREE.Vector3(-6, 4, -4), new THREE.Vector3(-8, 6, -10),
  ]);
  const camQ = new THREE.Vector3();

  const s = {
    scene, camera, clear: 0x03050a,
    dof: { focus: 60, aperture: 0, maxCoC: 12 },
    grade: { exposure: 1.05, tint: [0.97, 1.0, 1.04], bloom: 0.55, sat: 1.0 },
    update(lt, T) {
      const u = cine(remap(lt, -0.35, 4.6));
      camera.position.copy(path.getPointAt(u));
      camera.lookAt(look.getPointAt(u));
      camera.setFocalLength(24);
      camera.updateProjectionMatrix();
      crowdMats.forEach((m) => { m.uniforms.uTime.value = T; });
      led.offset.x = -T * 0.05;
      beams.forEach(({ b, m, ph, lp }) => {
        const tx = Math.sin(T * 0.9 + ph) * 40, tz = Math.cos(T * 0.7 + ph * 1.3) * 28;
        aimBeam(b, new THREE.Vector3(tx, 0, tz));
        m.uniforms.uTime.value = T;
        m.uniforms.uIntensity.value = 0.45 * (0.6 + 0.4 * Math.sin(T * 2.0 + ph));
      });
      bm.uniforms.uTime.value = T;
      hazes.forEach((h) => { h.material.uniforms.uTime.value = T; h.lookAt(camera.position.x, h.position.y, camera.position.z); });

      // ball: enters from right spinning hard, decelerates, hangs, exits
      const bIn = settle(remap(lt, 2.0, 3.0)), bOut = easeInCubic(remap(lt, 4.2, 4.95));
      ballRig.visible = lt > 1.95 && lt < 4.95;
      ballRig.position.set(1.9 - bIn * 1.55 - bOut * 2.4, -0.62 + 0.03 * Math.sin(lt * 2.0) - bOut * 0.6, -2.3);
      const spin = 7 * (1 - Math.exp(-3 * Math.max(0, lt - 2.0))) + lt * 0.6;
      ball.rotation.set(spin * 0.35, -spin, 0.3);
      ballKey.intensity = 4 * remap(lt, 2.0, 2.5); ballRim.intensity = 10 * remap(lt, 2.0, 2.5);
      const gk = remap(lt, 3.0, 3.6);
      gl.position.set(ballRig.position.x - 0.12, ballRig.position.y + 0.17, -2.0);
      gl.material.uniforms.uAmount.value = Math.sin(Math.PI * gk) * 0.8;

      title.update(lt, 2.35, 'slide', 4.55, 0.6);
      // focus: stadium -> ball/title plane
      s.dof.aperture = 2.4 * remap(lt, 1.9, 2.6);
      s.dof.focus = THREE.MathUtils.lerp(80, 2.4, smoother(remap(lt, 1.9, 2.6)));
    },
  };
  return s;
}
