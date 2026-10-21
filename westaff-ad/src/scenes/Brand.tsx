import React, {useMemo} from 'react';
import * as THREE from 'three';
import {Ticket} from '../three/Ticket';
import {Text3D} from '../three/Text3D';
import {Glow, pointsMaterial} from '../three/fx';
import {goldBrushed, goldPolished, chrome} from '../three/materials';
import {ease, prog, mix, rng} from '../lib/anim';
import {BRAND} from '../brand';
import {IMG} from '../three/assets';
import type {Fonts, CamState, SceneLook} from './types';

export const brandLook: SceneLook = {background: '#020205', env: 0.7, exposure: 1.0, bloom: 1.15};

export const brandCamera = (t: number): CamState => {
  const s = t - 24;
  const e = ease.outCubic(prog(s, 0, 2.2));
  const drift = ease.inOutSine(prog(s, 2.2, 6));
  return {pos: [mix(0, 0.12, drift), mix(0.0, 0.3, e), mix(2.6, 5.9, e) - drift * 0.35], target: [0, mix(0.2, 0.36, e), 0], fov: 32, roll: 0};
};

/** Éventail de rayons lumineux tournant derrière le logo. */
const raysMaterial = () => new THREE.ShaderMaterial({
  uniforms: {uT: {value: 0}, uO: {value: 0}, uC: {value: new THREE.Color(BRAND.colors.gold)}},
  transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
  vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0);} `,
  fragmentShader: `uniform float uT,uO; uniform vec3 uC; varying vec2 vUv;
    void main(){ vec2 p = vUv-0.5; float a = atan(p.y,p.x); float r = length(p);
      float rays = pow(0.5+0.5*sin(a*18.0 + uT*0.6), 6.0) + 0.5*pow(0.5+0.5*sin(a*7.0 - uT*0.4), 8.0);
      float fall = smoothstep(0.5,0.08,r) * smoothstep(0.02,0.12,r);
      gl_FragColor = vec4(uC*rays*fall*uO*0.13, 1.0); }`,
});

export const BrandScene: React.FC<{t: number; fonts: Fonts}> = ({t, fonts}) => {
  const s = t - 24;
  const res = useMemo(() => {
    const r = rng(5);
    const N = 2200, g = new THREE.BufferGeometry(), p = new Float32Array(N * 3), c = new Float32Array(N * 3), sz = new Float32Array(N), a = new Float32Array(N);
    const base = Array.from({length: N}, () => ({rad: 0.6 + r() * 2.6, ang: r() * 6.28, y: (r() - 0.5) * 2.2, sp: 0.15 + r() * 0.5, z: (r() - 0.5) * 1.5}));
    for (let i = 0; i < N; i++) { const col = new THREE.Color(r() < 0.8 ? BRAND.colors.gold : r() < 0.5 ? BRAND.colors.electric : BRAND.colors.violet).multiplyScalar(1 + r()); c.set([col.r, col.g, col.b], i * 3); sz[i] = 0.004 + Math.pow(r(), 4) * 0.025; a[i] = 0.4 + r() * 0.6; }
    g.setAttribute('position', new THREE.BufferAttribute(p, 3)); g.setAttribute('color', new THREE.BufferAttribute(c, 3)); g.setAttribute('aSize', new THREE.BufferAttribute(sz, 1)); g.setAttribute('aAlpha', new THREE.BufferAttribute(a, 1));
    const m = pointsMaterial(); m.uniforms.uScale.value = 1300;
    const ringMat = new THREE.MeshBasicMaterial({color: new THREE.Color(BRAND.colors.gold).multiplyScalar(3.2), toneMapped: false});
    return {g, m, base, rays: raysMaterial(), ringMat, goldB: goldBrushed(), gold: goldPolished(), silver: new THREE.MeshPhysicalMaterial({color: '#f6efe0', metalness: 1, roughness: 0.18, envMapIntensity: 2.2, emissive: new THREE.Color('#fff2d8'), emissiveIntensity: 0.25})};
  }, []);
  const pos = res.g.attributes.position as THREE.BufferAttribute;
  const gather = ease.outCubic(prog(s, 0, 1.6));
  res.base.forEach((b, i) => {
    const ang = b.ang + s * b.sp;
    const rad = mix(b.rad * 2.4, b.rad, gather);
    pos.setXYZ(i, Math.cos(ang) * rad, 0.35 + b.y * mix(1.5, 0.55, gather), Math.sin(ang) * rad * 0.35 - 0.8 + b.z * 0.2);
  });
  pos.needsUpdate = true;
  res.rays.uniforms.uT.value = t; res.rays.uniforms.uO.value = ease.outCubic(prog(s, 0.5, 1.8));
  const ringE = ease.outExpo(prog(s, 0.25, 1.4));

  const word = (start: number) => (i: number) => {
    const k = ease.outQuint(prog(s, start + i * 0.07, start + 0.75 + i * 0.07));
    return {z: (1 - k) * -3.5, y: (1 - k) * 0.3, ry: (1 - k) * -1.2, s: Math.max(0.001, k)};
  };
  const tk = ease.outBack(prog(s, 0.1, 1.2));
  const lightX = mix(-3, 3, ease.inOutSine(prog(s, 1.0, 2.4)));
  const logoMat = useMemo(() => {
    const tx = new THREE.Texture(IMG.logo); tx.colorSpace = THREE.SRGBColorSpace; tx.needsUpdate = true;
    return new THREE.ShaderMaterial({
      uniforms: {uMap: {value: tx}, uSweep: {value: -1}, uO: {value: 0}},
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false,
      vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0);} `,
      fragmentShader: `uniform sampler2D uMap; uniform float uSweep, uO; varying vec2 vUv;
        void main(){ vec3 c = texture2D(uMap, vUv).rgb; c = pow(c, vec3(2.2));
          float d = vUv.x*0.7 + vUv.y*0.5 - uSweep; float band = exp(-d*d*60.0);
          float lum = dot(c, vec3(0.3,0.59,0.11));
          gl_FragColor = vec4((c*1.15 + vec3(1.0,0.9,0.7)*band*lum*2.5)*uO, 1.0); }`,
    });
  }, []);
  logoMat.uniforms.uSweep.value = mix(-0.4, 1.6, ease.inOutSine(prog(s, 1.0, 2.2)));
  logoMat.uniforms.uO.value = ease.outCubic(prog(s, 0.15, 0.9));

  return (
    <group>
      <ambientLight intensity={0.1} />
      <spotLight position={[0, 3, 4]} target-position={[0, 0.3, 0]} angle={0.5} penumbra={0.8} intensity={70} color="#ffe6c0" />
      <pointLight position={[lightX, 0.6, 1.4]} intensity={16} color="#fff6e0" />
      <pointLight position={[-2.5, 1, -1.5]} intensity={25} color={BRAND.colors.electric} />
      <pointLight position={[2.5, 1, -1.5]} intensity={25} color={BRAND.colors.violet} />
      {/* halo */}
      <mesh position={[0, 0.78, -1.2]} material={res.rays}><planeGeometry args={[7, 7]} /></mesh>
      <mesh position={[0, 0.78, -0.3]} scale={mix(0.2, 1, ringE)} rotation-x={0.0}><torusGeometry args={[0.78, 0.006, 12, 200]} /><primitive object={res.ringMat} attach="material" /></mesh>
      <Glow position={[0, 0.78, -1]} scale={mix(0.5, 3.2, ringE)} color={BRAND.colors.gold} opacity={0.3} />
      <Glow position={[0, 0.36, -1.4]} scale={5.5} color={BRAND.colors.violet} opacity={0.25 * ringE} />
      {/* logo fourni (fond noir → fusion additive) avec balayage lumineux */}
      <mesh position={[0, 0.78, 0.1]} rotation={[0, Math.sin(t * 0.7) * 0.08, 0]} scale={mix(0.6, 1, ease.outBack(prog(s, 0.2, 1.1)))}>
        <planeGeometry args={[1.42, 1.42]} />
        <primitive object={logoMat} attach="material" />
      </mesh>
      {false && <group>{/* ancien emblème billet + logotype 3D (désactivés : remplacés par le logo fourni) */}
      <Ticket kind="master" position={[0, 0.95, 0]} rotation={[0.1, (1 - tk) * Math.PI * 3 + Math.sin(t * 0.9) * 0.25, Math.PI / 2]} scale={0.26 * Math.max(0.001, tk)}
        sweep={mix(-0.5, 1.5, prog(s, 1.2, 2.2))} time={t} holo={0.35} emissive={0.35} />
      {/* logotype 3D */}
      <Text3D font={fonts.display} text={BRAND.name} size={0.128} depth={0.34} tracking={0.03} material={res.gold} anim={word(0.35)} position={[0, 0.36, 0]} />
      <Text3D font={fonts.bold} text={BRAND.nameSub} size={0.058} depth={0.25} tracking={0.8} material={res.silver} anim={word(0.9)} position={[0, 0.17, 0]} />
      <mesh position={[-0.42, 0.175, 0]} scale-x={ease.outCubic(prog(s, 1.2, 1.8))}><boxGeometry args={[0.12, 0.005, 0.005]} /><primitive object={res.gold} attach="material" /></mesh>
      <mesh position={[0.42, 0.175, 0]} scale-x={ease.outCubic(prog(s, 1.2, 1.8))}><boxGeometry args={[0.12, 0.005, 0.005]} /><primitive object={res.gold} attach="material" /></mesh>
      </group>}
      <points geometry={res.g} material={res.m} frustumCulled={false} />
    </group>
  );
};
