import React, {useMemo} from 'react';
import * as THREE from 'three';
import {delayRender, continueRender, staticFile} from 'remotion';
import {Glow, Beam, pointsMaterial} from '../three/fx';
import {goldBrushed} from '../three/materials';
import {IMG, CLUB_FRAMES} from '../three/assets';
import {ease, prog, mix, rng, clamp} from '../lib/anim';
import {BRAND, CLUBS_VIDEO} from '../brand';
import type {Fonts, CamState, SceneLook} from './types';

/**
 * Scène insérée (9 → 14 s) : tour d'écrans des 5 championnats (montée sur le tempo, 1 écran par temps),
 * puis écran géant diffusant la vidéo des clubs, dans laquelle la caméra plonge.
 */
export const leaguesLook: SceneLook = {background: '#02030b', fog: {color: '#060a1e', density: 0.03}, env: 0.5, exposure: 1.0, bloom: 1.0};

const PANELS = [
  {img: 'pl', x: -0.4, z: -0.5, ry: 0.22},
  {img: 'laliga', x: 0.4, z: 0.2, ry: -0.22},
  {img: 'seriea', x: -0.38, z: -0.3, ry: 0.2},
  {img: 'bundesliga', x: 0.4, z: 0.1, ry: -0.22},
  {img: 'ligue1', x: -0.34, z: -0.4, ry: 0.18},
];
const GAP = 2.8, PW = 3.3, PH = 1.86;
const SCREEN_Y = PANELS.length * GAP + 1.6, SCREEN = 3.2;
const VIDEO_START = 1.36; // s (scène) : la vidéo se termine pile au raccord de 14 s
const BEAT = 0.5;

/** Hauteur caméra : un « cran » par temps (tenue puis montée), aligné sur la grosse caisse. */
const climb = (s: number) => {
  const k = (s - 0.05) / BEAT;
  const i = Math.floor(k), f = k - i;
  const step = clamp(i + ease.inOutCubic(clamp((f - 0.45) / 0.55)), 0, PANELS.length - 1);
  return step * GAP;
};

export const leaguesCamera = (t: number): CamState => {
  const s = t - 9;
  const yA = climb(s);
  const toScreen = ease.inOutCubic(prog(s, 2.45, 3.3));
  const push = ease.inOutSine(prog(s, 3.0, 4.55));
  const dive = ease.inExpo(prog(s, 4.5, 5.0));
  const y = mix(yA, SCREEN_Y, toScreen) + Math.sin(s * 1.3) * 0.05;
  const z = mix(mix(11, 7.2, push), 0.9, dive);
  return {pos: [Math.sin(s * 0.8) * 0.35 * (1 - dive), y + 0.15, z], target: [0, y, 0], fov: mix(40, 36, push), roll: Math.sin(s * 0.9) * 0.012 * (1 - dive)};
};

const coverTexture = (im: HTMLImageElement, aspect: number) => {
  const tx = new THREE.Texture(im); tx.colorSpace = THREE.SRGBColorSpace; tx.anisotropy = 8; tx.needsUpdate = true;
  const ia = im.width / im.height;
  if (ia > aspect) { tx.repeat.set(aspect / ia, 1); tx.offset.set((1 - aspect / ia) / 2, 0); }
  else { tx.repeat.set(1, ia / aspect); tx.offset.set(0, (1 - ia / aspect) * 0.75); }
  return tx;
};

/** Image courante de la vidéo des clubs (frames préchargées → rendu déterministe). */
const videoCache = new Map<number, THREE.Texture>();
const clubsFrame = (s: number) => {
  const idx = clamp(Math.floor((s - VIDEO_START) * CLUBS_VIDEO.fps), 0, CLUBS_VIDEO.frames - 1);
  if (!videoCache.has(idx)) { const tx = new THREE.Texture(CLUB_FRAMES[idx]); tx.colorSpace = THREE.SRGBColorSpace; tx.needsUpdate = true; videoCache.set(idx, tx); }
  return videoCache.get(idx)!;
};

export const Leagues: React.FC<{t: number; fonts: Fonts}> = ({t}) => {
  const s = t - 9;
  const res = useMemo(() => {
    const r = rng(31);
    const frame = goldBrushed();
    const panels = PANELS.map((p) => new THREE.MeshBasicMaterial({map: coverTexture(IMG[p.img], PW / PH), toneMapped: false}));
    const side = new THREE.MeshBasicMaterial({map: coverTexture(IMG.laligaPlayers, 2 / 3.1), toneMapped: false});
    const N = 1600, g = new THREE.BufferGeometry(), pos = new Float32Array(N * 3), c = new Float32Array(N * 3), sz = new Float32Array(N), a = new Float32Array(N);
    for (let i = 0; i < N; i++) {
      pos.set([(r() - 0.5) * 16, -4 + r() * (SCREEN_Y + 10), -9 + r() * 12], i * 3);
      const col = new THREE.Color(r() < 0.6 ? BRAND.colors.electric : r() < 0.6 ? BRAND.colors.gold : BRAND.colors.violet).multiplyScalar(1 + r());
      c.set([col.r, col.g, col.b], i * 3); sz[i] = 0.01 + Math.pow(r(), 4) * 0.08; a[i] = 0.25 + r() * 0.6;
    }
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3)); g.setAttribute('color', new THREE.BufferAttribute(c, 3));
    g.setAttribute('aSize', new THREE.BufferAttribute(sz, 1)); g.setAttribute('aAlpha', new THREE.BufferAttribute(a, 1));
    const pm = pointsMaterial(); pm.uniforms.uScale.value = 1100;
    const screenMat = new THREE.MeshBasicMaterial({color: '#000', toneMapped: false});
    return {frame, panels, side, g, pm, screenMat};
  }, []);
  const vtx = clubsFrame(s);
  res.screenMat.map = s >= VIDEO_START - 0.05 ? vtx : null;
  res.screenMat.color.set(s >= VIDEO_START - 0.05 && vtx ? '#ffffff' : '#000000');
  res.screenMat.needsUpdate = true;

  const camY = leaguesCamera(t).target[1];
  return (
    <group>
      <ambientLight intensity={0.2} />
      <pointLight position={[-4, camY + 2, 4]} intensity={50} color={BRAND.colors.electric} />
      <pointLight position={[4, camY - 1, 4]} intensity={50} color={BRAND.colors.violet} />
      <pointLight position={[0, camY + 1, 6]} intensity={25} color="#ffe6c0" />
      {/* faisceaux verticaux d'ambiance */}
      {[-5, 5].map((x, i) => <Beam key={i} position={[x, -6, -6]} target={[x * 0.4, SCREEN_Y + 6, -2]} radius={2.4} length={34} color={i ? BRAND.colors.violet : BRAND.colors.electric} opacity={0.35} />)}
      {/* tour d'écrans des championnats */}
      {PANELS.map((p, i) => {
        const y = i * GAP;
        const dist = Math.abs(y - camY);
        const bright = clamp(1 - Math.max(0, dist - 0.4) / 3.2, 0.18, 1);
        const pop = ease.outBack(prog(s, i * BEAT - 0.25, i * BEAT + 0.2));
        res.panels[i].color.setScalar(bright * 1.05);
        return (
          <group key={i} position={[p.x, y, p.z]} rotation={[0, p.ry + Math.sin(s * 1.1 + i) * 0.03, 0]} scale={mix(0.85, 1, pop)}>
            <mesh position-z={-0.06}><boxGeometry args={[PW + 0.14, PH + 0.14, 0.1]} /><primitive object={res.frame} attach="material" /></mesh>
            <mesh material={res.panels[i]}><planeGeometry args={[PW, PH]} /></mesh>
            <Glow position={[0, 0, -0.4]} scale={PW * 1.5} color={BRAND.colors.electric} opacity={0.18 * bright} />
          </group>
        );
      })}
      {/* écran géant : vidéo des clubs */}
      <group position={[0, SCREEN_Y, -0.2]}>
        <mesh position-z={-0.08}><boxGeometry args={[SCREEN + 0.2, SCREEN + 0.2, 0.14]} /><primitive object={res.frame} attach="material" /></mesh>
        <mesh material={res.screenMat}><planeGeometry args={[SCREEN, SCREEN]} /></mesh>
        <Glow position={[0, 0, -0.6]} scale={SCREEN * 2.6} color={BRAND.colors.gold} opacity={0.35} />
        {[-1, 1].map((sgn) => (
          <group key={sgn} position={[sgn * 2.75, -0.2, -1.2]} rotation={[0, -sgn * 0.45, 0]}>
            <mesh position-z={-0.05}><boxGeometry args={[2.1, 3.2, 0.08]} /><primitive object={res.frame} attach="material" /></mesh>
            <mesh material={res.side}><planeGeometry args={[2.0, 3.1]} /></mesh>
          </group>
        ))}
      </group>
      <points geometry={res.g} material={res.pm} frustumCulled={false} />
    </group>
  );
};
