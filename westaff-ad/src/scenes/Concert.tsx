import React, {useMemo} from 'react';
import * as THREE from 'three';
import {Beam, Glow, pointsMaterial} from '../three/fx';
import {blackGloss, chrome} from '../three/materials';
import {ease, prog, mix, rng, Path} from '../lib/anim';
import {BRAND} from '../brand';
import type {Fonts, CamState, SceneLook} from './types';

export const concertLook: SceneLook = {background: '#04020b', fog: {color: '#120828', density: 0.022}, env: 0.12, exposure: 1.0, bloom: 1.35};
const BPM = 120, beat = 60 / BPM;

const camPos = new Path([[-3, 13, 40], [-1.5, 8, 33], [0.5, 4.6, 24], [0, 3.5, 16.5]]);
const camTgt = new Path([[0, 9.5, -8], [0, 7.2, -8], [0, 5.6, -9], [0, 5.0, -9.5]]);
export const concertCamera = (t: number): CamState => {
  const s = t - 9;
  const u = ease.inOutCubic(prog(s, 0, 4.45));
  const p = camPos.at(u), g = camTgt.at(u);
  const dive = ease.inExpo(prog(s, 4.45, 5.0));
  return {
    pos: [p.x + Math.sin(s * 0.7) * 0.4, mix(p.y, 7.6, dive), mix(p.z, -6.5, dive)],
    target: [g.x, mix(g.y, 7.6, dive), mix(g.z, -9.6, dive)],
    fov: mix(mix(56, 46, u), 30, dive), roll: Math.sin(s * 0.9) * 0.025,
  };
};

/** Mur LED : barres d'égaliseur + motifs, grille de pixels visible. */
const ledMaterial = () => new THREE.ShaderMaterial({
  uniforms: {uTime: {value: 0}, uBeat: {value: 0}, uA: {value: new THREE.Color(BRAND.colors.violet)}, uB: {value: new THREE.Color(BRAND.colors.electric)}},
  toneMapped: false,
  vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0);} `,
  fragmentShader: `
    uniform float uTime, uBeat; uniform vec3 uA, uB; varying vec2 vUv;
    float h(float n){ return fract(sin(n*91.345)*47453.21); }
    void main(){
      vec2 grid = vec2(156.0, 72.0);
      vec2 cell = floor(vUv*grid); vec2 f = fract(vUv*grid);
      float px = smoothstep(0.5,0.38,abs(f.x-0.5))*smoothstep(0.5,0.38,abs(f.y-0.5));
      float col = floor(vUv.x*26.0);
      float level = 0.25 + 0.6*abs(sin(uTime*2.2 + col*0.7))*(0.6+0.4*h(col+floor(uTime*4.0))) + uBeat*0.25;
      float bar = step(vUv.y, level) * step(0.08, fract(vUv.x*26.0));
      vec2 c = vUv - vec2(0.5,0.55); c.x *= 2.2;
      float ring = smoothstep(0.02,0.0,abs(length(c) - (0.15 + fract(uTime*0.5)*0.5)));
      vec3 colr = mix(uB, uA, vUv.y + 0.3*sin(uTime + vUv.x*3.0));
      vec3 o = colr * (bar*0.9 + ring*1.3 + 0.05) * (0.8 + uBeat*0.6);
      gl_FragColor = vec4(o * px * 0.9, 1.0);
    }`,
});

export const Concert: React.FC<{t: number; fonts: Fonts}> = ({t}) => {
  const s = t - 9;
  const beatPhase = (t % beat) / beat;
  const kick = Math.exp(-beatPhase * 6);
  const res = useMemo(() => {
    const r = rng(11);
    // foule stylisée : torse + tête + bras (instanciés)
    const N = 2400;
    const body = new THREE.InstancedMesh(new THREE.CapsuleGeometry(0.2, 0.55, 3, 8), new THREE.MeshStandardMaterial({color: '#0b0a12', roughness: 0.55, metalness: 0.15}), N);
    const head = new THREE.InstancedMesh(new THREE.SphereGeometry(0.12, 12, 10), new THREE.MeshStandardMaterial({color: '#0d0c14', roughness: 0.5, metalness: 0.15}), N);
    const arms = new THREE.InstancedMesh(new THREE.CapsuleGeometry(0.045, 0.62, 2, 6), new THREE.MeshStandardMaterial({color: '#0b0a12', roughness: 0.55, metalness: 0.15}), N);
    const people = Array.from({length: N}, () => {
      const z = 3 + Math.pow(r(), 0.8) * 40, spread = 9 + z * 0.55;
      return {x: (r() - 0.5) * 2 * spread, z, ph: r() * Math.PI * 2, arm: r() < 0.5, side: r() < 0.5 ? -1 : 1, h: 0.9 + r() * 0.2, jump: r() < 0.35};
    });
    // treillis (truss) : membrures + diagonales
    const trussPieces: THREE.Matrix4[] = [];
    const add = (a: THREE.Vector3, b: THREE.Vector3) => {
      const mid = a.clone().add(b).multiplyScalar(0.5), len = a.distanceTo(b);
      const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), b.clone().sub(a).normalize());
      trussPieces.push(new THREE.Matrix4().compose(mid, q, new THREE.Vector3(1, len, 1)));
    };
    const box = (x0: number, x1: number, y: number, z: number, vertical = false) => {
      const seg = 24, w = 0.5;
      for (let i = 0; i < seg; i++) {
        const k0 = i / seg, k1 = (i + 1) / seg;
        const P = (k: number, dy: number, dz: number) => vertical ? new THREE.Vector3(x0 + dy, mix(0, y, k), z + dz) : new THREE.Vector3(mix(x0, x1, k), y + dy, z + dz);
        for (const [dy, dz] of [[0, 0], [w, 0], [0, w], [w, w]]) add(P(k0, dy, dz), P(k1, dy, dz));
        add(P(k0, 0, 0), P(k1, w, 0)); add(P(k0, 0, w), P(k1, w, w)); add(P(k0, 0, 0), P(k1, 0, w)); add(P(k0, w, 0), P(k1, w, w));
      }
    };
    box(-15, 15, 16, -1.2); box(-15.3, 0, 16.3, -1.2, true); box(14.8, 0, 16.3, -1.2, true); box(-13, 13, 13.5, -8.8);
    const truss = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.035, 0.035, 1, 6), chrome(), trussPieces.length);
    trussPieces.forEach((m, i) => truss.setMatrixAt(i, m));
    // confettis métalliques
    const NC = 900;
    const conf = new THREE.InstancedMesh(new THREE.PlaneGeometry(0.07, 0.11), new THREE.MeshStandardMaterial({metalness: 0.9, roughness: 0.25, side: THREE.DoubleSide}), NC);
    const confData = Array.from({length: NC}, (_, i) => {
      conf.setColorAt(i, new THREE.Color([BRAND.colors.gold, BRAND.colors.goldLight, BRAND.colors.violet, '#ffffff'][Math.floor(r() * 4)]));
      return {x: (r() - 0.5) * 34, z: -4 + r() * 30, y0: 18 + r() * 12, v: 1.3 + r() * 1.2, ph: r() * 6, spin: 2 + r() * 5};
    });
    // brume lumineuse (poussière dans les faisceaux)
    const NH = 1800, hg = new THREE.BufferGeometry(), hp = new Float32Array(NH * 3), hc = new Float32Array(NH * 3), hs = new Float32Array(NH), ha = new Float32Array(NH);
    for (let i = 0; i < NH; i++) { hp.set([(r() - 0.5) * 40, r() * 18, -8 + r() * 40], i * 3); const c = new THREE.Color(r() < 0.5 ? BRAND.colors.violet : BRAND.colors.electric); hc.set([c.r, c.g, c.b], i * 3); hs[i] = 0.03 + r() * 0.06; ha[i] = 0.3 + r() * 0.5; }
    hg.setAttribute('position', new THREE.BufferAttribute(hp, 3)); hg.setAttribute('color', new THREE.BufferAttribute(hc, 3)); hg.setAttribute('aSize', new THREE.BufferAttribute(hs, 1)); hg.setAttribute('aAlpha', new THREE.BufferAttribute(ha, 1));
    const hm = pointsMaterial(); hm.uniforms.uScale.value = 900;
    return {body, head, arms, people, truss, conf, confData, hg, hm, led: ledMaterial(), stage: blackGloss()};
  }, []);

  // animation de la foule sur le tempo
  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), v = new THREE.Vector3(), one = new THREE.Vector3(1, 1, 1);
  const drop = s > 1.0 ? 1 : 0;
  res.people.forEach((p, i) => {
    const bob = Math.abs(Math.sin((t / beat) * Math.PI + p.ph * 0.2)) * 0.09 + (p.jump && drop ? Math.max(0, Math.sin((t / beat) * Math.PI)) * 0.25 : 0);
    const y = p.h + bob;
    q.identity(); m.compose(v.set(p.x, y, p.z), q, one); res.body.setMatrixAt(i, m);
    m.compose(v.set(p.x, y + 0.55, p.z), q, one); res.head.setMatrixAt(i, m);
    if (p.arm) {
      const wave = Math.sin(t * 4 + p.ph) * 0.25;
      q.setFromEuler(new THREE.Euler(0.15, 0, p.side * (0.35 + wave)));
      m.compose(v.set(p.x + p.side * 0.28, y + 0.65, p.z), q, one);
    } else m.compose(v.set(p.x, -5, p.z), q, one);
    res.arms.setMatrixAt(i, m);
  });
  res.body.instanceMatrix.needsUpdate = res.head.instanceMatrix.needsUpdate = res.arms.instanceMatrix.needsUpdate = true;
  // confettis (lâchés au drop)
  const cs = Math.max(0, s - 1.0);
  res.confData.forEach((c, i) => {
    const y = c.y0 - c.v * cs * 2.2;
    q.setFromEuler(new THREE.Euler(cs * c.spin + c.ph, cs * c.spin * 0.7, c.ph));
    m.compose(v.set(c.x + Math.sin(cs * 1.5 + c.ph) * 0.6, s > 1.0 ? y : 40, c.z), q, one);
    res.conf.setMatrixAt(i, m);
  });
  res.conf.instanceMatrix.needsUpdate = true;
  res.led.uniforms.uTime.value = t; res.led.uniforms.uBeat.value = kick;

  // projecteurs motorisés (balayage) + lasers
  const heads = Array.from({length: 9}, (_, i) => {
    const x = -12 + i * 3, ph = i * 0.7;
    const tx = x * 0.4 + Math.sin(s * 1.3 + ph) * 14, tz = 16 + Math.cos(s * 1.1 + ph) * 12;
    return {pos: [x, 15.6, -0.9] as [number, number, number], target: [tx, 0, tz] as [number, number, number], color: [BRAND.colors.electric, BRAND.colors.violet, '#e8eeff'][i % 3]};
  });
  const laserOn = s > 1.0 ? 1 : 0;
  const lasers = Array.from({length: 14}, (_, i) => {
    const a = (i / 13 - 0.5) * 1.9 + Math.sin(s * 1.6 + i * 0.3) * 0.25;
    const el = 0.12 + 0.18 * Math.abs(Math.sin(s * 0.9 + i));
    const dir = new THREE.Vector3(Math.sin(a), Math.sin(el), Math.cos(a)).normalize();
    return {dir, color: i % 2 ? BRAND.colors.violet : '#4aa3ff'};
  });
  const laserGeo = useMemo(() => { const g = new THREE.CylinderGeometry(0.018, 0.018, 70, 6, 1, true); g.translate(0, 35, 0); return g; }, []);

  return (
    <group>
      <ambientLight intensity={0.05} />
      <pointLight position={[0, 9, -7]} intensity={260 * (0.7 + kick * 0.6)} distance={60} color={BRAND.colors.violet} />
      <pointLight position={[-10, 6, -4]} intensity={160} distance={40} color={BRAND.colors.electric} />
      <pointLight position={[10, 6, -4]} intensity={160} distance={40} color={BRAND.colors.electric} />
      <spotLight position={[0, 15, 6]} target-position={[0, 1.5, -3]} angle={0.35} penumbra={0.6} intensity={900} distance={60} color="#fff1dc" />
      {/* scène */}
      <mesh position={[0, 0.75, -5]} material={res.stage}><boxGeometry args={[26, 1.5, 10]} /></mesh>
      <mesh position={[0, 1.51, -0.02]}><boxGeometry args={[26, 0.05, 0.05]} /><meshBasicMaterial color={new THREE.Color(1.5, 2.2, 6)} toneMapped={false} /></mesh>
      <mesh position={[0, 0, 20]} rotation-x={-Math.PI / 2}><planeGeometry args={[120, 80]} /><meshStandardMaterial color="#07060c" roughness={0.6} /></mesh>
      <mesh position={[0, 8, -9.6]} material={res.led}><planeGeometry args={[26, 12.5]} /></mesh>
      <primitive object={res.truss} />
      {/* artiste en silhouette */}
      <group position={[0, 1.5, -3.2]}>
        <mesh position={[0, 1.0, 0]}><capsuleGeometry args={[0.24, 0.8, 4, 10]} /><meshStandardMaterial color="#050508" roughness={0.4} /></mesh>
        <mesh position={[0, 1.78, 0]}><sphereGeometry args={[0.15, 16, 12]} /><meshStandardMaterial color="#050508" /></mesh>
        <mesh position={[0.32, 1.52, 0.1]} rotation-z={-0.5}><capsuleGeometry args={[0.05, 0.6, 2, 6]} /><meshStandardMaterial color="#050508" /></mesh>
        <mesh position={[-0.3, 1.9, 0]} rotation-z={0.25}><capsuleGeometry args={[0.05, 0.75, 2, 6]} /><meshStandardMaterial color="#050508" /></mesh>
        <mesh position={[0.5, 0.75, 0.35]}><cylinderGeometry args={[0.015, 0.015, 1.5, 6]} /><meshStandardMaterial color="#222" metalness={1} /></mesh>
      </group>
      <Glow position={[0, 3.4, -3.6]} scale={9 + kick * 3} color="#ffe6c4" opacity={0.55} />
      {heads.map((h, i) => (
        <group key={i}>
          <mesh position={h.pos}><boxGeometry args={[0.5, 0.55, 0.5]} /><meshStandardMaterial color="#111" metalness={0.8} roughness={0.3} /></mesh>
          <Glow position={[h.pos[0], h.pos[1] - 0.3, h.pos[2] + 0.2]} scale={2.4} color={h.color} />
          <Beam position={[h.pos[0], h.pos[1] - 0.3, h.pos[2]]} target={h.target} radius={3.2} length={42} color={h.color} opacity={0.5} />
        </group>
      ))}
      {lasers.map((l, i) => {
        const q2 = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), l.dir);
        return (
          <mesh key={i} geometry={laserGeo} position={[0, 2.2, -1]} quaternion={q2} visible={laserOn > 0}>
            <meshBasicMaterial color={new THREE.Color(l.color).multiplyScalar(4)} toneMapped={false} transparent opacity={0.85} blending={THREE.AdditiveBlending} depthWrite={false} />
          </mesh>
        );
      })}
      <primitive object={res.body} /><primitive object={res.head} /><primitive object={res.arms} />
      <primitive object={res.conf} />
      <points geometry={res.hg} material={res.hm} frustumCulled={false} />
    </group>
  );
};
