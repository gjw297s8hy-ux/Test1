import React, {useMemo} from 'react';
import * as THREE from 'three';
import {Beam, Glow, SkyDome, pointsMaterial} from '../three/fx';
import {chrome} from '../three/materials';
import {ease, prog, mix, rng, Path} from '../lib/anim';
import type {Fonts, CamState, SceneLook} from './types';

export const stadiumLook: SceneLook = {background: '#02030a', fog: {color: '#0a1430', density: 0.0055}, env: 0.18, exposure: 0.92, bloom: 0.85};

const L = 105, W = 68;
const MASTS: [number, number, number][] = [[-74, 0, -54], [74, 0, -54], [-74, 0, 54], [74, 0, 54]];
const MAST_H = 62;

// ---------- caméra : grue plongeante continue depuis le billet, finit au ras du ballon ----------
const camPos = new Path([[-6, 96, 30], [-16, 52, 44], [-2, 20, 40], [5, 3.6, 14], [1.25, 0.5, 2.7]]);
const camTgt = new Path([[0, 0, -6], [0, 2, -4], [0, 2, 0], [0, 1.2, -4], [0, 1.15, -10]]);
export const stadiumCamera = (t: number): CamState => {
  const s = t - 4;
  const u = ease.outCubic(prog(s, 0, 4.35));
  const p = camPos.at(u), g = camTgt.at(u);
  const drift = prog(s, 4.0, 5.0);
  p.x += drift * 0.35; p.z -= drift * 0.25;
  // transition : la caméra lève les yeux vers le mât d'éclairage
  const up = ease.inCubic(prog(s, 4.45, 5.0));
  const mast = new THREE.Vector3(MASTS[1][0], MAST_H + 3, MASTS[1][2]);
  g.lerp(mast, up);
  return {pos: [p.x, p.y, p.z], target: [g.x, g.y, g.z], fov: mix(mix(46, 34, u), 22, up), roll: mix(0.12, 0.0, u) + up * 0.08};
};

// ---------- géométrie : contour arrondi du stade ----------
const A = L / 2 + 7.5, B = W / 2 + 7.5, RC = 16;
const M = 300;
const ring = (() => {
  const pts: {p: THREE.Vector2; n: THREE.Vector2}[] = [];
  const segs: {c: [number, number]; a0: number}[] = [{c: [A - RC, B - RC], a0: 0}, {c: [-(A - RC), B - RC], a0: Math.PI / 2}, {c: [-(A - RC), -(B - RC)], a0: Math.PI}, {c: [A - RC, -(B - RC)], a0: Math.PI * 1.5}];
  const per = 2 * (2 * (A - RC) + 2 * (B - RC)) + 2 * Math.PI * RC;
  for (let i = 0; i < M; i++) {
    let d = (i / M) * per;
    // parcours : côté droit (x=A) puis arc, haut, arc, gauche, arc, bas, arc
    const sides = [2 * (B - RC), 0.5 * Math.PI * RC, 2 * (A - RC), 0.5 * Math.PI * RC, 2 * (B - RC), 0.5 * Math.PI * RC, 2 * (A - RC), 0.5 * Math.PI * RC];
    let k = 0; while (d > sides[k]) { d -= sides[k]; k++; }
    let p: THREE.Vector2, n: THREE.Vector2;
    if (k === 0) { p = new THREE.Vector2(A, -(B - RC) + d); n = new THREE.Vector2(1, 0); }
    else if (k === 2) { p = new THREE.Vector2(A - RC - d, B); n = new THREE.Vector2(0, 1); }
    else if (k === 4) { p = new THREE.Vector2(-A, B - RC - d); n = new THREE.Vector2(-1, 0); }
    else if (k === 6) { p = new THREE.Vector2(-(A - RC) + d, -B); n = new THREE.Vector2(0, -1); }
    else { const seg = segs[(k - 1) / 2]; const a = seg.a0 + d / RC; n = new THREE.Vector2(Math.cos(a), Math.sin(a)); p = new THREE.Vector2(seg.c[0] + n.x * RC, seg.c[1] + n.y * RC); }
    pts.push({p, n});
  }
  return pts;
})();
const at = (i: number, off: number) => { const r = ring[((i % M) + M) % M]; return [r.p.x + r.n.x * off, r.p.y + r.n.y * off] as const; };

// gradins : [offset, hauteur, profondeur de marche]
const ROWS: {o: number; h: number; d: number}[] = [];
for (let i = 0; i < 22; i++) ROWS.push({o: 1.5 + i * 0.85, h: 0.9 + i * 0.44, d: 0.85});
const UPPER0 = 1.5 + 22 * 0.85 + 3.0, UPPERH = 0.9 + 22 * 0.44 + 5.2;
for (let i = 0; i < 20; i++) ROWS.push({o: UPPER0 + i * 0.88, h: UPPERH + i * 0.54, d: 0.88});

const buildBowl = () => {
  const pos: number[] = [], idx: number[] = [];
  const strip = (o0: number, h0: number, o1: number, h1: number) => {
    const base = pos.length / 3;
    for (let i = 0; i <= M; i++) { const a = at(i, o0), b = at(i, o1); pos.push(a[0], h0, a[1], b[0], h1, b[1]); }
    for (let i = 0; i < M; i++) { const k = base + i * 2; idx.push(k, k + 2, k + 1, k + 1, k + 2, k + 3); }
  };
  strip(-0.5, 0.0, 1.5, 0.0);
  strip(1.5, 0.0, 1.5, ROWS[0].h);
  ROWS.forEach((r, i) => {
    strip(r.o, r.h, r.o + r.d, r.h);
    const nx = ROWS[i + 1];
    if (nx && i !== 21) strip(r.o + r.d, r.h, r.o + r.d, nx.h);
  });
  const lastLow = ROWS[21];
  strip(lastLow.o + lastLow.d, lastLow.h, lastLow.o + lastLow.d + 1.5, lastLow.h + 1.2); // allée
  strip(lastLow.o + lastLow.d + 1.5, lastLow.h + 1.2, UPPER0 - 0.3, UPPERH - 1.8); // nez de balcon
  strip(UPPER0 - 0.3, UPPERH - 1.8, UPPER0, UPPERH);
  const top = ROWS[ROWS.length - 1];
  strip(top.o + top.d, top.h, top.o + top.d, top.h + 6); // mur arrière
  // toit
  strip(top.o + top.d, top.h + 6, top.o - 30, top.h + 8.5);
  strip(top.o - 30, top.h + 8.5, top.o - 30, top.h + 7.6);
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(idx); g.computeVertexNormals();
  return g;
};

const pitchTexture = () => {
  const px = 20, c = document.createElement('canvas'); c.width = (L + 8) * px; c.height = (W + 8) * px;
  const g = c.getContext('2d')!;
  const X = (m: number) => (m + L / 2 + 4) * px, Y = (m: number) => (m + W / 2 + 4) * px;
  g.fillStyle = '#13461f'; g.fillRect(0, 0, c.width, c.height);
  for (let i = 0; i < 22; i++) { g.fillStyle = i % 2 ? '#1b5f2a' : '#175224'; g.fillRect(X(-L / 2) + (i * L * px) / 22, Y(-W / 2), (L * px) / 22 + 1, W * px); }
  let s = 3; const r = () => ((s = (s * 16807) % 2147483647) / 2147483647);
  for (let i = 0; i < 60000; i++) { g.fillStyle = `rgba(${r() < 0.5 ? '0,0,0' : '120,200,120'},0.06)`; g.fillRect(r() * c.width, r() * c.height, 2, 2); }
  g.strokeStyle = 'rgba(245,250,245,0.92)'; g.lineWidth = 0.12 * px;
  const rect = (x0: number, y0: number, x1: number, y1: number) => g.strokeRect(X(x0), Y(y0), X(x1) - X(x0), Y(y1) - Y(y0));
  rect(-L / 2, -W / 2, L / 2, W / 2);
  g.beginPath(); g.moveTo(X(0), Y(-W / 2)); g.lineTo(X(0), Y(W / 2)); g.stroke();
  g.beginPath(); g.arc(X(0), Y(0), 9.15 * px, 0, Math.PI * 2); g.stroke();
  g.fillStyle = 'white'; g.beginPath(); g.arc(X(0), Y(0), 0.25 * px, 0, Math.PI * 2); g.fill();
  for (const sgn of [-1, 1]) {
    const gx = (sgn * L) / 2;
    rect(Math.min(gx, gx - sgn * 16.5), -20.15, Math.max(gx, gx - sgn * 16.5), 20.15);
    rect(Math.min(gx, gx - sgn * 5.5), -9.16, Math.max(gx, gx - sgn * 5.5), 9.16);
    g.beginPath(); g.arc(X(gx - sgn * 11), Y(0), 0.22 * px, 0, Math.PI * 2); g.fill();
    g.beginPath(); const a0 = sgn > 0 ? Math.PI - 0.93 : -0.93, a1 = sgn > 0 ? Math.PI + 0.93 : 0.93; g.arc(X(gx - sgn * 11), Y(0), 9.15 * px, a0, a1); g.stroke();
  }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 16;
  return t;
};

/** Ballon procédural : pentagones noirs calculés à partir des 12 directions d'un dodécaèdre. */
const ballGeometry = () => {
  const g = new THREE.SphereGeometry(0.11, 128, 96);
  const phi = (1 + Math.sqrt(5)) / 2;
  const dirs = [[0, 1, phi], [0, -1, phi], [0, 1, -phi], [0, -1, -phi], [1, phi, 0], [-1, phi, 0], [1, -phi, 0], [-1, -phi, 0], [phi, 0, 1], [-phi, 0, 1], [phi, 0, -1], [-phi, 0, -1]].map((d) => new THREE.Vector3(...d).normalize());
  const col: number[] = []; const v = new THREE.Vector3();
  const p = g.attributes.position;
  for (let i = 0; i < p.count; i++) {
    v.fromBufferAttribute(p, i).normalize();
    let best = -1, second = -1;
    dirs.forEach((d) => { const k = v.dot(d); if (k > best) { second = best; best = k; } else if (k > second) second = k; });
    const black = best > 0.952;
    const seam = !black && best - second < 0.006;
    const c = black ? 0.03 : seam ? 0.55 : 0.95;
    col.push(c, c, c * (black ? 1 : 0.985));
  }
  g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  return g;
};

const Goal: React.FC<{x: number}> = ({x}) => {
  const sgn = Math.sign(x);
  const net = useMemo(() => {
    const pts: number[] = [];
    for (let i = 0; i <= 24; i++) { const z = -3.66 + (7.32 * i) / 24; pts.push(0, 0, z, 0, 2.44, z, 0, 2.44, z, sgn * 2, 1.6, z, sgn * 2, 1.6, z, sgn * 2, 0, z); }
    for (let j = 0; j <= 10; j++) { const y = (2.44 * j) / 10; pts.push(0, y, -3.66, 0, y, 3.66); }
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3)); return g;
  }, [sgn]);
  const post = new THREE.MeshStandardMaterial({color: '#f4f4f4', roughness: 0.3, metalness: 0.2, emissive: '#ffffff', emissiveIntensity: 0.15});
  return (
    <group position={[x, 0, 0]}>
      <mesh position={[0, 1.22, -3.66]} material={post}><cylinderGeometry args={[0.06, 0.06, 2.44, 12]} /></mesh>
      <mesh position={[0, 1.22, 3.66]} material={post}><cylinderGeometry args={[0.06, 0.06, 2.44, 12]} /></mesh>
      <mesh position={[0, 2.44, 0]} rotation={[Math.PI / 2, 0, 0]} material={post}><cylinderGeometry args={[0.06, 0.06, 7.44, 12]} /></mesh>
      <lineSegments geometry={net}><lineBasicMaterial color="#c8ccd6" transparent opacity={0.35} /></lineSegments>
    </group>
  );
};

export const Stadium: React.FC<{t: number; fonts: Fonts}> = ({t}) => {
  const s = t - 4;
  const res = useMemo(() => {
    const bowl = buildBowl();
    const pitch = pitchTexture();
    // spectateurs instanciés
    const r = rng(7);
    const seats: THREE.Matrix4[] = [], colors: THREE.Color[] = [];
    const palette = ['#14161f', '#1d2130', '#262a3a', '#323648', '#4a4f66', '#11131a'];
    const blocks = ['#2453d6', '#e8eaf2', '#7b2ff0', '#d8a440', '#1a3fae'];
    const q = new THREE.Quaternion(), sc = new THREE.Vector3(1, 1, 1), m = new THREE.Matrix4();
    ROWS.forEach((row, ri) => {
      const step = 3;
      for (let i = 0; i < M; i += 1) {
        for (let k = 0; k < step; k++) {
          if (r() < 0.06) continue;
          const f = i + k / step;
          const i0 = Math.floor(f), fr = f - i0;
          const a = at(i0, row.o + row.d * 0.5), b = at(i0 + 1, row.o + row.d * 0.5);
          const x = mix(a[0], b[0], fr), z = mix(a[1], b[1], fr);
          const n = ring[i0].n;
          q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), Math.atan2(n.x, n.y) + (r() - 0.5) * 0.4);
          const hgt = 0.8 + r() * 0.35;
          sc.set(1, hgt, 1);
          m.compose(new THREE.Vector3(x, row.h + 0.35 * hgt, z), q, sc);
          seats.push(m.clone());
          const sector = Math.floor((i / M) * 16 + (ri > 21 ? 3 : 0)) % 5;
          colors.push(new THREE.Color(r() < 0.14 ? blocks[sector] : palette[Math.floor(r() * palette.length)]).multiplyScalar(0.35 + r() * 0.4));
        }
      }
    });
    const crowd = new THREE.InstancedMesh(new THREE.CapsuleGeometry(0.17, 0.42, 2, 6), new THREE.MeshStandardMaterial({roughness: 0.85, metalness: 0.0}), seats.length);
    seats.forEach((mm, i) => { crowd.setMatrixAt(i, mm); crowd.setColorAt(i, colors[i]); });
    crowd.instanceMatrix.needsUpdate = true;
    // flashs de téléphones
    const NF = 1600, fl = new THREE.BufferGeometry(), fp = new Float32Array(NF * 3), fc = new Float32Array(NF * 3), fs = new Float32Array(NF), fa = new Float32Array(NF);
    for (let i = 0; i < NF; i++) { const e = new THREE.Vector3().setFromMatrixPosition(seats[Math.floor(r() * seats.length)]); fp.set([e.x, e.y + 0.6, e.z], i * 3); fc.set([1.6, 1.6, 2.0], i * 3); fs[i] = 0.12 + r() * 0.2; }
    fl.setAttribute('position', new THREE.BufferAttribute(fp, 3)); fl.setAttribute('color', new THREE.BufferAttribute(fc, 3));
    fl.setAttribute('aSize', new THREE.BufferAttribute(fs, 1)); fl.setAttribute('aAlpha', new THREE.BufferAttribute(fa, 1));
    const flMat = pointsMaterial(); flMat.uniforms.uScale.value = 700;
    // lampes des projecteurs
    const lampGeo = new THREE.SphereGeometry(0.42, 10, 8);
    const lamps = new THREE.InstancedMesh(lampGeo, new THREE.MeshBasicMaterial({color: new THREE.Color(6, 6.2, 7), toneMapped: false}), MASTS.length * 32);
    let li = 0;
    MASTS.forEach(([mx, , mz]) => {
      const head = new THREE.Object3D(); head.position.set(mx, MAST_H, mz); head.lookAt(0, 0, 0);
      for (let a = 0; a < 8; a++) for (let b = 0; b < 4; b++) {
        const o = new THREE.Object3D(); o.position.set(-4.2 + a * 1.2, -1.8 + b * 1.2, 0.35); head.add(o); head.updateMatrixWorld(true);
        lamps.setMatrixAt(li++, o.matrixWorld);
      }
    });
    // éclairage de toit (rampe)
    const top = ROWS[ROWS.length - 1];
    const NR = 160, roofLights = new THREE.InstancedMesh(new THREE.BoxGeometry(1.6, 0.12, 0.3), new THREE.MeshBasicMaterial({color: new THREE.Color(3, 3.2, 4), toneMapped: false}), NR);
    for (let i = 0; i < NR; i++) {
      const k = Math.floor((i / NR) * M), p = at(k, top.o - 29.5), n = ring[k].n;
      const o = new THREE.Object3D(); o.position.set(p[0], top.h + 7.5, p[1]); o.rotation.y = Math.atan2(n.x, n.y); o.updateMatrix(); roofLights.setMatrixAt(i, o.matrix);
    }
    return {bowl, pitch, crowd, fl, flMat, lamps, roofLights, ball: ballGeometry(), NF};
  }, []);

  // scintillement des flashs (déterministe par frame)
  const frameIdx = Math.floor(t * 30);
  const fa = res.fl.attributes.aAlpha as THREE.BufferAttribute;
  for (let i = 0; i < res.NF; i++) { const h = Math.sin(i * 12.9898 + frameIdx * 78.233) * 43758.5453; fa.setX(i, h - Math.floor(h) > 0.93 ? 1 : 0.0); }
  fa.needsUpdate = true;

  const concrete = useMemo(() => new THREE.MeshStandardMaterial({color: '#1b1d26', roughness: 0.92, side: THREE.DoubleSide}), []);
  const ballMat = useMemo(() => new THREE.MeshPhysicalMaterial({vertexColors: true, roughness: 0.38, clearcoat: 0.8, clearcoatRoughness: 0.25}), []);
  const mastMat = useMemo(() => chrome(), []);
  const flick = 1 + Math.sin(t * 40) * 0.01;

  return (
    <group>
      <SkyDome top="#010208" horizon="#0b1430" glow="#1d3576" />
      <hemisphereLight args={['#2a3c80', '#05070c', 0.35]} />
      {MASTS.map((m, i) => (
        <spotLight key={i} position={[m[0], MAST_H, m[2]]} intensity={3.2 * flick} decay={0} distance={0} angle={0.42} penumbra={0.7} color="#eef3ff"
          target-position={[m[0] * 0.15, 0, m[2] * 0.15]} />
      ))}
      <pointLight position={[0, 6, 6]} intensity={30} distance={30} color="#dfe8ff" />
      {/* sol + pelouse */}
      <mesh rotation-x={-Math.PI / 2} position-y={-0.02}><planeGeometry args={[260, 200]} /><meshStandardMaterial color="#0b120e" roughness={1} /></mesh>
      <mesh rotation-x={-Math.PI / 2}><planeGeometry args={[L + 8, W + 8]} /><meshStandardMaterial map={res.pitch} roughness={0.9} color="#8fa892" /></mesh>
      <Goal x={-L / 2} /><Goal x={L / 2} />
      <mesh geometry={res.ball} material={ballMat} position={[0, 0.11, 0]} rotation={[0.3, s * 0.15, 0.2]} />
      {/* tribunes */}
      <mesh geometry={res.bowl} material={concrete} />
      <primitive object={res.crowd} />
      <points geometry={res.fl} material={res.flMat} frustumCulled={false} />
      <primitive object={res.roofLights} />
      {/* mâts + têtes de projecteurs + faisceaux */}
      {MASTS.map((m, i) => (
        <group key={i}>
          <mesh position={[m[0], MAST_H / 2, m[2]]} material={mastMat}><cylinderGeometry args={[0.5, 0.9, MAST_H, 16]} /></mesh>
          <Glow position={[m[0], MAST_H, m[2]]} scale={34} color="#dfe8ff" opacity={0.9} />
          <Beam position={[m[0], MAST_H, m[2]]} target={[m[0] * 0.1, 0, m[2] * 0.1]} radius={26} length={105} color="#9fb8ff" opacity={0.22} />
        </group>
      ))}
      <primitive object={res.lamps} />
    </group>
  );
};
