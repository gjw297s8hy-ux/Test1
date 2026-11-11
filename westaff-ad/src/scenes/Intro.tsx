import React, {useMemo} from 'react';
import * as THREE from 'three';
import {Ticket} from '../three/Ticket';
import {Text3D} from '../three/Text3D';
import {pointsMaterial, Glow} from '../three/fx';
import {goldPolished} from '../three/materials';
import {TICKET} from '../three/ticket';
import {ease, prog, mix, rng, Path} from '../lib/anim';
import {BRAND} from '../brand';
import {IMG} from '../three/assets';
import type {Fonts, CamState, SceneLook} from './types';

export const introLook: SceneLook = {background: '#020205', env: 0.55, exposure: 1.0, bloom: 1.1};

const camPath = new Path([[0.0, 0.1, 8.2], [0.12, 0.06, 7.3], [0.2, 0.0, 6.6]]);
export const introCamera = (t: number): CamState => {
  const u = ease.inOutSine(prog(t, 0, 3.55));
  const p = camPath.at(u);
  const rush = ease.inExpo(prog(t, 3.5, 4.0));
  return {
    pos: [mix(p.x, 0, rush), mix(p.y, 0.5, rush), mix(p.z, 0.25, rush)],
    target: [0, mix(-0.05, 0.5, rush), 0],
    fov: mix(34, 26, rush), roll: Math.sin(t * 0.8) * 0.01,
  };
};

const TICKET_POS = new THREE.Vector3(0, 0.5, 0);
const ticketRot = (t: number) => new THREE.Euler(Math.sin(t * 0.9) * 0.06 + 0.04, mix(-0.55, 0.1, ease.outCubic(prog(t, 0.6, 3.4))), 0.02);

const N = 5200;
export const Intro: React.FC<{t: number; fonts: Fonts}> = ({t, fonts}) => {
  // particules : départ sur une coquille sphérique, arrivée sur la surface du billet
  const data = useMemo(() => {
    const r = rng(42);
    const start = new Float32Array(N * 3), target = new Float32Array(N * 3), delay = new Float32Array(N), size = new Float32Array(N), col = new Float32Array(N * 3);
    const {w, h} = TICKET;
    for (let i = 0; i < N; i++) {
      const th = r() * Math.PI * 2, ph = Math.acos(2 * r() - 1), rad = 3.5 + r() * 6;
      start[i * 3] = Math.sin(ph) * Math.cos(th) * rad; start[i * 3 + 1] = Math.cos(ph) * rad * 0.8; start[i * 3 + 2] = Math.min(3.5, Math.sin(ph) * Math.sin(th) * rad) - 1.5;
      let x, y;
      if (r() < 0.35) { // contour
        const e = r() * 2 * (w + h);
        if (e < w) { x = -w / 2 + e; y = -h / 2; } else if (e < w + h) { x = w / 2; y = -h / 2 + (e - w); } else if (e < 2 * w + h) { x = w / 2 - (e - w - h); y = h / 2; } else { x = -w / 2; y = h / 2 - (e - 2 * w - h); }
      } else { x = (r() - 0.5) * w; y = (r() - 0.5) * h; }
      target[i * 3] = x; target[i * 3 + 1] = y; target[i * 3 + 2] = 0.02 + (r() - 0.5) * 0.01;
      delay[i] = r() * 0.6;
      size[i] = 0.014 + Math.pow(r(), 3) * 0.05;
      const c = new THREE.Color(r() < 0.82 ? BRAND.colors.gold : r() < 0.5 ? '#ffffff' : r() < 0.5 ? BRAND.colors.electric : BRAND.colors.violet);
      c.multiplyScalar(1.2 + r() * 2.0);
      col.set([c.r, c.g, c.b], i * 3);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(N * 3), 3));
    geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
    geo.setAttribute('aSize', new THREE.BufferAttribute(size, 1));
    geo.setAttribute('aAlpha', new THREE.BufferAttribute(new Float32Array(N), 1));
    const mat = pointsMaterial(); mat.uniforms.uScale.value = 1500;
    return {start, target, delay, geo, mat};
  }, []);

  const rot = ticketRot(t);
  const reveal = ease.inOutCubic(prog(t, 2.05, 2.95));
  const mtx = new THREE.Matrix4().compose(TICKET_POS, new THREE.Quaternion().setFromEuler(rot), new THREE.Vector3(1, 1, 1));
  const pos = data.geo.attributes.position as THREE.BufferAttribute, alpha = data.geo.attributes.aAlpha as THREE.BufferAttribute;
  const v = new THREE.Vector3();
  for (let i = 0; i < N; i++) {
    const e = ease.inOutCubic(prog(t, 0.25 + data.delay[i], 2.2 + data.delay[i] * 0.5));
    v.set(data.target[i * 3], data.target[i * 3 + 1], data.target[i * 3 + 2]).applyMatrix4(mtx);
    const sx = data.start[i * 3], sy = data.start[i * 3 + 1], sz = data.start[i * 3 + 2];
    const a = (1 - e) * 2.4, ca = Math.cos(a), sa = Math.sin(a);
    const rx = sx * ca - sz * sa, rz = sx * sa + sz * ca;
    pos.setXYZ(i, mix(rx, v.x, e), mix(sy, v.y, e) + Math.sin(t * 3 + i) * 0.01 * (1 - e), mix(rz, v.z, e));
    const localY = data.target[i * 3 + 1];
    const covered = reveal > 0 && localY < -TICKET.h / 2 + TICKET.h * reveal ? 1 : 0;
    alpha.setX(i, prog(t, 0.15 + data.delay[i] * 0.5, 0.7 + data.delay[i]) * (1 - covered * 0.92) * (1 - prog(t, 3.3, 3.7)));
  }
  pos.needsUpdate = true; alpha.needsUpdate = true;

  // pulsation initiale synchronisée sur le battement sonore (0 / 0.5 / 1.0 s)
  const pulse = [0, 0.5, 1.0, 1.5].reduce((acc, b) => acc + Math.exp(-Math.max(0, t - b) * 7) * (t >= b ? 1 : 0), 0);

  const gold = useMemo(() => goldPolished(), []);
  const letter = (start: number) => (i: number) => {
    const k = ease.outBack(prog(t, start + i * 0.045, start + 0.55 + i * 0.045));
    return {y: (1 - k) * -0.22, rx: (1 - k) * -1.4, s: Math.max(0, Math.min(1.05, k))};
  };
  const key = mix(-3, 3, prog(t, 2.2, 3.6));

  const moonTex = useMemo(() => { const tx = new THREE.Texture(IMG.moon); tx.colorSpace = THREE.SRGBColorSpace; tx.needsUpdate = true; return tx; }, []);
  const bgIn = ease.inOutSine(prog(t, 0.6, 2.6));
  return (
    <group>
      {/* décor fourni : la Terre vue depuis la Lune, en fond lointain (parallaxe lente) */}
      <mesh position={[0.3 - t * 0.12, 1.6 - t * 0.05, -34]} scale={1 + t * 0.012}>
        <planeGeometry args={[40, 28]} />
        <meshBasicMaterial map={moonTex} color={new THREE.Color(0.62, 0.66, 0.78).multiplyScalar(bgIn)} toneMapped={false} fog={false} />
      </mesh>
      <ambientLight intensity={0.15} />
      <spotLight position={[2.5, 4, 5]} angle={0.5} penumbra={0.8} intensity={60} color="#ffe2b0" decay={2} />
      <pointLight position={[-3, 1, -2]} intensity={25} color={BRAND.colors.electric} />
      <pointLight position={[3, -1, -1.5]} intensity={25} color={BRAND.colors.violet} />
      <pointLight position={[key, 0.6, 2.2]} intensity={12} color="#fff3d6" />
      <points geometry={data.geo} material={data.mat} frustumCulled={false} />
      <Glow position={[0, 0.5, -0.2]} scale={0.6 + pulse * 2.2 + reveal * 2.5} color={BRAND.colors.gold} opacity={Math.min(1, 0.25 + pulse * 0.6 + reveal * 0.35)} />
      <Ticket kind="master" position={TICKET_POS} rotation={rot} reveal={reveal} sweep={mix(-0.4, 1.6, prog(t, 2.6, 3.5))} time={t} holo={0.3} emissive={0.25} />
      <group position={[0, -0.98, 0.4]}>
        <Text3D font={fonts.display} text={BRAND.copy.intro[0]} size={0.135} material={gold} tracking={0.1} anim={letter(2.45)} position={[0, 0.04, 0]} />
        <Text3D font={fonts.display} text={BRAND.copy.intro[1]} size={0.14} material={gold} tracking={0.0} anim={letter(2.6)} position={[0, -0.17, 0]} />
      </group>
    </group>
  );
};
