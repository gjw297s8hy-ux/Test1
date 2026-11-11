import React, {useMemo} from 'react';
import * as THREE from 'three';
import {Ticket} from '../three/Ticket';
import {Text3D} from '../three/Text3D';
import {Glow, pointsMaterial} from '../three/fx';
import {goldPolished, goldBrushed, blackGloss} from '../three/materials';
import {ease, prog, mix, rng, clamp} from '../lib/anim';
import {BRAND} from '../brand';
import type {Fonts, CamState, SceneLook} from './types';

export const heroLook: SceneLook = {background: '#020205', env: 0.75, exposure: 1.0, bloom: 0.95};
const FLOOR = -1.18;

export const heroCamera = (t: number): CamState => {
  const s = t - 18;
  const out = ease.outCubic(prog(s, 0, 1.5));
  const orbit = ease.inOutSine(prog(s, 0.8, 5.45));
  const ox = mix(-0.75, 0.75, orbit), oz = mix(7.4, 7.0, orbit);
  const push = ease.inExpo(prog(s, 5.45, 6.0));
  const x = mix(mix(0, ox, out), 0, push), y = mix(mix(-0.25, 0.28, out), 0.0, push), z = mix(mix(1.3, oz, out), 2.0, push);
  return {pos: [x, y, z], target: [0, mix(mix(-0.25, 0.22, out), 0.0, push), 0], fov: 33, roll: Math.sin(s * 0.5) * 0.01};
};

const tagGeometry = () => {
  const sh = new THREE.Shape();
  sh.moveTo(-0.17, -0.13); sh.lineTo(0.28, -0.13); sh.quadraticCurveTo(0.31, -0.13, 0.31, -0.1); sh.lineTo(0.31, 0.1); sh.quadraticCurveTo(0.31, 0.13, 0.28, 0.13);
  sh.lineTo(-0.17, 0.13); sh.lineTo(-0.31, 0); sh.lineTo(-0.17, -0.13);
  const hole = new THREE.Path(); hole.absarc(-0.19, 0, 0.028, 0, Math.PI * 2, true); sh.holes.push(hole);
  const g = new THREE.ExtrudeGeometry(sh, {depth: 0.03, bevelEnabled: true, bevelThickness: 0.012, bevelSize: 0.01, bevelSegments: 4, curveSegments: 16});
  g.translate(0, 0, -0.015); return g;
};
const chevronGeometry = () => {
  const sh = new THREE.Shape(); sh.moveTo(-0.12, 0.05); sh.lineTo(0, -0.05); sh.lineTo(0.12, 0.05); sh.lineTo(0.12, 0.0); sh.lineTo(0, -0.1); sh.lineTo(-0.12, 0.0); sh.lineTo(-0.12, 0.05);
  return new THREE.ExtrudeGeometry(sh, {depth: 0.03, bevelEnabled: true, bevelThickness: 0.008, bevelSize: 0.006, bevelSegments: 2});
};

const fadeTexture = () => {
  const c = document.createElement('canvas'); c.width = c.height = 256; const g = c.getContext('2d')!;
  const gr = g.createRadialGradient(128, 128, 0, 128, 128, 128); gr.addColorStop(0, '#fff'); gr.addColorStop(0.55, '#888'); gr.addColorStop(1, '#000');
  g.fillStyle = gr; g.fillRect(0, 0, 256, 256); return new THREE.CanvasTexture(c);
};

const TICKETS = [
  {kind: 'concert' as const, accent: BRAND.colors.violet, x: -0.82, y: -0.42, z: -0.35, ry: 0.42, rz: 0.06, from: -2.6},
  {kind: 'football' as const, accent: BRAND.colors.electric, x: 0, y: -0.22, z: 0.25, ry: 0, rz: 0, from: 0},
  {kind: 'show' as const, accent: BRAND.colors.gold, x: 0.82, y: -0.42, z: -0.35, ry: -0.42, rz: -0.06, from: 2.6},
];

export const Hero: React.FC<{t: number; fonts: Fonts}> = ({t, fonts}) => {
  const s = t - 18;
  const res = useMemo(() => {
    const r = rng(77);
    const N = 1400, g = new THREE.BufferGeometry(), p = new Float32Array(N * 3), c = new Float32Array(N * 3), sz = new Float32Array(N), a = new Float32Array(N);
    const base = Array.from({length: N}, () => [(r() - 0.5) * 6, -1.1 + r() * 4, -3 + r() * 5, r() * 6.28, 0.05 + r() * 0.15]);
    for (let i = 0; i < N; i++) { const col = new THREE.Color(r() < 0.85 ? BRAND.colors.gold : r() < 0.5 ? BRAND.colors.electric : BRAND.colors.violet).multiplyScalar(1.2 + r()); c.set([col.r, col.g, col.b], i * 3); sz[i] = 0.004 + Math.pow(r(), 4) * 0.03; a[i] = 0.3 + r() * 0.7; }
    g.setAttribute('position', new THREE.BufferAttribute(p, 3)); g.setAttribute('color', new THREE.BufferAttribute(c, 3)); g.setAttribute('aSize', new THREE.BufferAttribute(sz, 1)); g.setAttribute('aAlpha', new THREE.BufferAttribute(a, 1));
    const m = pointsMaterial(); m.uniforms.uScale.value = 1400;
    const floor = new THREE.MeshPhysicalMaterial({color: '#050509', roughness: 0.12, metalness: 0.4, clearcoat: 1, transparent: true, opacity: 0.86, alphaMap: fadeTexture()});
    return {g, m, base, floor, tag: tagGeometry(), chev: chevronGeometry(), gold: goldPolished(), goldB: goldBrushed(), dark: blackGloss(),
      chevMat: [0, 1, 2].map(() => new THREE.MeshStandardMaterial({color: '#0a1a40', emissive: new THREE.Color(BRAND.colors.electric), emissiveIntensity: 0, metalness: 0.6, roughness: 0.3}))};
  }, []);
  const pos = res.g.attributes.position as THREE.BufferAttribute;
  res.base.forEach((b, i) => pos.setXYZ(i, b[0] + Math.sin(t * 0.3 + b[3]) * 0.15, b[1] + ((t * b[4]) % 4), b[2]));
  pos.needsUpdate = true;

  const conv = ease.inExpo(prog(s, 5.4, 6.0)); // convergence finale vers le logo
  const tickets = TICKETS.map((k, i) => {
    const e = ease.outCubic(prog(s, 0.15 + i * 0.08, 1.5 + i * 0.08));
    const x = mix(k.x + k.from, k.x, k.from ? e : 1) * (1 - conv);
    const y = k.y + Math.sin(t * 1.1 + i * 2) * 0.05 * (1 - conv);
    const ry = (k.from ? mix(k.ry + Math.sign(k.from) * Math.PI * 1.5, k.ry, e) : k.ry + Math.sin(s * 0.7) * 0.12) + conv * Math.PI * 2 * (i - 1 || 1);
    return {...k, x, y, ry, z: k.z + conv * 0.4};
  });

  // effet « prix qui diminue » : étiquette qui rétrécit par crans + chevrons descendants (aucun chiffre)
  const tagIn = ease.outBack(prog(s, 1.9, 2.4));
  const steps = [2.55, 2.95, 3.35].reduce((acc, st) => acc + ease.outCubic(prog(s, st, st + 0.22)), 0);
  const tagScale = tagIn * Math.pow(0.86, steps) * (1 - conv);
  res.chevMat.forEach((mm, i) => { const st = 2.55 + i * 0.4; mm.emissiveIntensity = 3.5 * Math.exp(-Math.max(0, s - st) * 2.2) * (s >= st ? 1 : 0) + (s >= st ? 0.5 : 0); });

  const line = (start: number) => (i: number, n: number) => {
    const k = ease.outBack(prog(s, start + i * 0.035, start + 0.5 + i * 0.035));
    const o = ease.inCubic(prog(s, 5.3, 5.7));
    return {y: (1 - k) * 0.25 + o * 0.6, rx: (1 - k) * 1.5, s: Math.max(0, Math.min(1.04, k)) * (1 - o)};
  };
  const sweepX = mix(-2.5, 2.5, prog(s, 2.2, 3.6));

  return (
    <group>
      <ambientLight intensity={0.1} />
      <spotLight position={[2.5, 4.5, 5]} target-position={[0, -0.2, 0]} angle={0.45} penumbra={0.8} intensity={120} color="#ffe2b4" />
      <pointLight position={[-3, 1.2, -2]} intensity={45} color={BRAND.colors.electric} />
      <pointLight position={[3, 1.2, -2]} intensity={45} color={BRAND.colors.violet} />
      <pointLight position={[sweepX, 1.6, 2.2]} intensity={10} color="#fff4dc" />
      <Glow position={[0, 0.0, -2.5]} scale={6} color={BRAND.colors.violet} opacity={0.35} />
      <Glow position={[0, -0.2, -1.5]} scale={3.5} color={BRAND.colors.gold} opacity={0.3} />
      {/* titre 3D */}
      <group position={[0, 1.5, 0.3]}>
        <Text3D font={fonts.display} text={BRAND.copy.hero.lines[0]} size={0.19} material={res.gold} tracking={0.02} anim={line(1.0)} />
        <Text3D font={fonts.display} text={BRAND.copy.hero.lines[1]} size={0.14} material={res.goldB} tracking={0.0} anim={line(1.3)} position={[0, -0.27, 0]} />
      </group>
      {/* billets + reflets au sol */}
      {tickets.map((k, i) => (
        <group key={i}>
          <Ticket kind={k.kind} accent={k.accent} position={[k.x, k.y, k.z]} rotation={[0.02, k.ry, k.rz]} scale={0.62}
            sweep={mix(-0.6, 1.6, prog(s, 1.6 + i * 0.25, 2.8 + i * 0.25))} time={t} holo={0.35} emissive={0.3} />
          <group position={[0, FLOOR, 0]} scale={[1, -1, 1]}>
            <Ticket kind={k.kind} accent={k.accent} position={[k.x, k.y - FLOOR, k.z]} rotation={[0.02, k.ry, k.rz]} scale={0.62} time={t} holo={0} emissive={0.15} />
          </group>
        </group>
      ))}
      <mesh position={[0, FLOOR, 0]} rotation-x={-Math.PI / 2} material={res.floor}><planeGeometry args={[9, 9]} /></mesh>
      {/* étiquette prix */}
      <group position={[0.62, 0.68, 0.9]} rotation={[0, -0.35 + Math.sin(t * 1.5) * 0.15, Math.sin(t * 2) * 0.05]} scale={tagScale}>
        <mesh geometry={res.tag} material={res.gold} />
        <Text3D font={fonts.display} text="€" size={0.16} depth={0.12} material={res.dark} position={[0.07, 0.0, 0.03]} />
      </group>
      {[0, 1, 2].map((i) => (
        <mesh key={i} geometry={res.chev} material={res.chevMat[i]} position={[0.62, 0.42 - i * 0.12, 0.9]} scale={tagIn * (1 - conv)} />
      ))}
      <points geometry={res.g} material={res.m} frustumCulled={false} />
      <Glow position={[0, -0.2, 0.8]} scale={conv * 9} color="#ffe2a8" opacity={conv} />
    </group>
  );
};
