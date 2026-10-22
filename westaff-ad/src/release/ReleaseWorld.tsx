import React, {useEffect, useMemo} from 'react';
import * as THREE from 'three';
import {useThree} from '@react-three/fiber';
import {useCurrentFrame, useVideoConfig, delayRender, continueRender, staticFile} from 'remotion';
import {RoundedBoxGeometry} from 'three/examples/jsm/geometries/RoundedBoxGeometry.js';
import {RoomEnvironment} from 'three/examples/jsm/environments/RoomEnvironment.js';
import {EffectComposer, Bloom, Noise, ToneMapping, SMAA, Vignette} from '@react-three/postprocessing';
import {ToneMappingMode, BlendFunction} from 'postprocessing';
import {Text3D} from '../three/Text3D';
import {Glow, glowTexture} from '../three/fx';
import {RadialBlurEffect} from '../three/RadialBlur';
import {ease, prog, mix, rng, clamp} from '../lib/anim';
import type {Fonts} from '../scenes/types';
import {REL, SH, beat} from './config';
import {pending, frameTexture, setFrame} from './frames';
import {GradeGlitchEffect} from './GradeGlitch';
import {LensFXEffect} from './LensFX';
import {asphalt, concrete, Surface} from './surfaces';

/**
 * Teaser « nouveau son » — diorama isométrique réaliste (parking souterrain en coupe), DA rouge & noir.
 * Effets inspirés des clips de référence : objectif grand-angle, punchs de zoom, flous filés, glitchs, flares, pétales en 3D.
 */
const C = REL.colors;
const ISO_EL = Math.asin(1 / Math.sqrt(3));
const FACE = Math.PI / 4;
const HALF = 4.5; // demi-taille du diorama
export const CUTS = [SH.B[0], SH.C[0], SH.D[0], SH.E[0]];
export const IMPACTS = [SH.B[0], beat(5), SH.C[0] + 0.28, SH.E[0]];
export const near = (t: number, list: number[], w: number) => list.reduce((a, b) => Math.max(a, Math.exp(-Math.pow((t - b) / w, 2))), 0);
const GLITCH_AT = [...CUTS, beat(16.6), beat(19)];
export const glitchAmount = (t: number) => GLITCH_AT.reduce((a, b) => Math.max(a, t > b - 0.1 && t < b + 0.14 ? 1 - Math.abs(t - b) / 0.14 : 0), 0);
const shake = (t: number, at: number, amp: number) => (t >= at ? Math.exp(-(t - at) * 9) * amp : 0);
const PORTRAIT: [number, number, number] = [8.2, 0, -8.2];
export const SHOT_T = [beat(14), beat(16.6), beat(19)];

// ---------- matériaux ----------
const useMats = () => useMemo(() => {
  const asph = asphalt(), conc = concrete(true), concPlain = concrete(false);
  const surf = (s: Surface, rep: number, extra: Partial<THREE.MeshPhysicalMaterialParameters> = {}) => {
    [s.map, s.roughnessMap, s.normalMap].forEach((t) => t.repeat.set(rep, rep));
    return new THREE.MeshPhysicalMaterial({map: s.map, roughnessMap: s.roughnessMap, normalMap: s.normalMap, normalScale: new THREE.Vector2(0.8, 0.8), roughness: 1, metalness: 0, ...extra});
  };
  return {
    floor: surf(asph, 1, {clearcoat: 0.35, clearcoatRoughness: 0.25}),
    wall: surf(conc, 1),
    slab: surf(concPlain, 1),
    redChrome: new THREE.MeshPhysicalMaterial({color: '#c3101c', metalness: 1, roughness: 0.2, clearcoat: 1, clearcoatRoughness: 0.08, envMapIntensity: 1.7}),
    nameChrome: new THREE.MeshPhysicalMaterial({color: '#f4f1ec', metalness: 1, roughness: 0.15, clearcoat: 1, emissive: new THREE.Color('#ffffff'), emissiveIntensity: 0.1, envMapIntensity: 1.8}),
    glowWhite: new THREE.MeshStandardMaterial({color: '#ffffff', emissive: new THREE.Color('#ffffff'), emissiveIntensity: 0.42, roughness: 0.25, metalness: 0.6}),
    blackGloss: new THREE.MeshPhysicalMaterial({color: '#0b0b0d', metalness: 0.6, roughness: 0.22, clearcoat: 1, clearcoatRoughness: 0.05}),
    steel: new THREE.MeshPhysicalMaterial({color: '#3a3a40', metalness: 1, roughness: 0.35}),
    neonTube: new THREE.MeshBasicMaterial({color: new THREE.Color(C.red).multiplyScalar(5), toneMapped: false}),
    neonStrip: new THREE.MeshBasicMaterial({color: new THREE.Color(C.red).multiplyScalar(3), toneMapped: false}),
  };
}, []);
type M = ReturnType<typeof useMats>;

/** Diorama : dalle de sol épaisse, deux murs en béton (coupe isométrique), poteaux, butées, néons. */
const Diorama: React.FC<{m: M; fonts: Fonts; neonText?: string; flicker: number}> = ({m, fonts, neonText, flicker}) => {
  const W = HALF * 2;
  return (
    <group>
      <mesh position-y={-0.45} receiveShadow castShadow material={m.slab}><boxGeometry args={[W + 0.6, 0.9, W + 0.6]} /></mesh>
      <mesh position-y={0.002} rotation-x={-Math.PI / 2} receiveShadow material={m.floor}><planeGeometry args={[W + 0.6, W + 0.6]} /></mesh>
      <mesh position={[-HALF - 0.2, 3.1, 0]} receiveShadow castShadow material={m.wall}><boxGeometry args={[0.4, 6.2, W + 0.6]} /></mesh>
      <mesh position={[0, 3.1, -HALF - 0.2]} receiveShadow castShadow material={m.wall}><boxGeometry args={[W + 0.6, 6.2, 0.4]} /></mesh>
      {[[-HALF + 0.2, -HALF + 0.2], [-HALF + 0.2, 0.6], [0.6, -HALF + 0.2]].map(([x, z], i) => (
        <mesh key={i} position={[x, 3.1, z]} castShadow receiveShadow material={m.wall}><boxGeometry args={[0.7, 6.2, 0.7]} /></mesh>
      ))}
      {[-2.6, -0.6, 1.4].map((x, i) => (
        <mesh key={i} position={[x, 0.09, -HALF + 0.9]} castShadow receiveShadow material={m.slab}><boxGeometry args={[1.1, 0.18, 0.25]} /></mesh>
      ))}
      <mesh position={[-HALF + 0.02, 5.6, 0]} material={m.neonStrip}><boxGeometry args={[0.04, 0.05, W - 0.4]} /></mesh>
      <mesh position={[0, 5.6, -HALF + 0.02]} material={m.neonStrip}><boxGeometry args={[W - 0.4, 0.05, 0.04]} /></mesh>
      <pointLight position={[-HALF + 0.6, 5.2, 0]} intensity={18 * flicker} distance={9} color={C.red} />
      <pointLight position={[0, 5.2, -HALF + 0.6]} intensity={18 * flicker} distance={9} color={C.red} />
      {neonText && (
        <group position={[2.65, 4.35, -HALF + 0.05]}>
          <Text3D font={fonts.display} text={neonText} size={0.72} depth={0.06} tracking={0.08} material={m.neonTube} />
          <Glow position={[0, 0, 0.3]} scale={5} color={C.red} opacity={0.55 * flicker} />
          <pointLight position={[0, 0, 0.8]} intensity={30 * flicker} distance={8} color={C.red} />
        </group>
      )}
    </group>
  );
};

/** Écran sur pied (cadre noir laqué, dalle émissive, deux montants + pieds). */
const ScreenStand: React.FC<{w: number; aspect?: number; tex: THREE.Texture; m: M; dim?: number; y: number} & JSX.IntrinsicElements['group']> = ({w, aspect = 4 / 3, tex, m, dim = 1.3, y, ...rest}) => {
  const h = w / aspect;
  const frame = useMemo(() => new RoundedBoxGeometry(w + 0.22, h + 0.22, 0.22, 4, 0.06), [w, h]);
  const bottom = y - h / 2 - 0.11;
  return (
    <group {...rest}>
      <mesh geometry={frame} material={m.blackGloss} position={[0, y, -0.12]} castShadow />
      <mesh position={[0, y, 0.0]}><planeGeometry args={[w, h]} /><meshBasicMaterial map={tex} color={new THREE.Color(dim, dim, dim)} toneMapped={false} /></mesh>
      {[-w * 0.3, w * 0.3].map((x, i) => (
        <group key={i}>
          <mesh position={[x, bottom / 2, -0.12]} castShadow material={m.steel}><boxGeometry args={[0.08, Math.max(0.01, bottom), 0.08]} /></mesh>
          <mesh position={[x, 0.025, -0.12]} castShadow material={m.steel}><boxGeometry args={[0.12, 0.05, 1.1]} /></mesh>
        </group>
      ))}
      <mesh position={[0, y - h / 2 - 0.13, 0.0]} material={m.neonTube}><boxGeometry args={[w * 0.5, 0.025, 0.025]} /></mesh>
    </group>
  );
};

/** Pétales de rose (rouges et noirs) qui tombent en tournoyant — remplacent les particules. */
const Petals: React.FC<{t: number; t0: number; count?: number; seed?: number; area?: number}> = ({t, t0, count = 70, seed = 1, area = 8}) => {
  const res = useMemo(() => {
    const r = rng(seed);
    const g = new THREE.PlaneGeometry(0.28, 0.36, 6, 6);
    const p = g.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < p.count; i++) { const x = p.getX(i), y = p.getY(i); p.setZ(i, (x * x) * 1.6 - Math.abs(y) * 0.15); p.setX(i, x * (1 - Math.max(0, y) * 0.9)); }
    g.computeVertexNormals();
    const mat = new THREE.MeshPhysicalMaterial({color: '#ffffff', roughness: 0.55, sheen: 1, sheenColor: new THREE.Color('#ff3348'), sheenRoughness: 0.4, side: THREE.DoubleSide});
    const mesh = new THREE.InstancedMesh(g, mat, count);
    mesh.castShadow = true;
    const P = Array.from({length: count}, (_, i) => {
      mesh.setColorAt(i, new THREE.Color(r() < 0.6 ? '#7a0a14' : '#0e0c0e'));
      return {x: (r() - 0.5) * area, z: (r() - 0.5) * area, y0: 7 + r() * 6, v: 0.7 + r() * 0.8, ph: r() * 6.3, sp: 1 + r() * 3, sw: 0.3 + r() * 0.6};
    });
    return {mesh, P};
  }, [count, seed, area]);
  const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler(), one = new THREE.Vector3(1, 1, 1), v = new THREE.Vector3();
  const s = Math.max(0, t - t0);
  res.P.forEach((p, i) => {
    const y = p.y0 - p.v * s * 1.6;
    if (y > 0.03) { e.set(s * p.sp + p.ph, s * p.sp * 0.6, Math.sin(s * 2 + p.ph) * 0.8); } else { e.set(-Math.PI / 2, 0, p.ph); }
    q.setFromEuler(e);
    m4.compose(v.set(p.x + Math.sin(s * 1.4 + p.ph) * p.sw, Math.max(0.03, y), p.z + Math.cos(s * 1.1 + p.ph) * p.sw), q, one);
    res.mesh.setMatrixAt(i, m4);
  });
  res.mesh.instanceMatrix.needsUpdate = true;
  return <primitive object={res.mesh} visible={t >= t0} />;
};

/** Poussière de béton à l'impact (nuages gris qui s'étalent au sol). */
const Dust: React.FC<{t: number; at: number}> = ({t, at}) => {
  const P = useMemo(() => { const r = rng(91); return Array.from({length: 26}, () => ({a: r() * Math.PI * 2, sp: 1.5 + r() * 2.5, s: 0.8 + r() * 1.4, h: r() * 0.6})); }, []);
  const k = t - at;
  if (k < 0 || k > 2.2) return null;
  return (
    <group>
      {P.map((p, i) => {
        const d = (1 - Math.exp(-k * 3)) * p.sp;
        return (
          <sprite key={i} position={[Math.cos(p.a) * d, 0.3 + p.h + k * 0.25, Math.sin(p.a) * d]} scale={[p.s * (1 + k * 1.2), p.s * (1 + k * 1.2), 1]}>
            <spriteMaterial map={glowTexture()} color="#8a8486" transparent opacity={0.55 * Math.exp(-k * 1.6)} depthWrite={false} />
          </sprite>
        );
      })}
    </group>
  );
};

const dropIn = (t: number, start: number, dur = 0.4) => {
  const k = ease.outBack(prog(t, start, start + dur));
  return {y: (1 - k) * 1.5, rx: (1 - k) * -1.3, s: Math.max(0.001, Math.min(1.06, k))};
};

// ---------- caméra ----------
type Cam = {target: [number, number, number]; zoom: number; az: number};
const camAt = (t: number): Cam => {
  const sway = Math.sin(t * 0.6) * 0.05;
  if (t < SH.A[1]) return {target: [-0.3, 2.4, -0.3], zoom: mix(88, 118, ease.outCubic(prog(t, 0, 2.4))), az: FACE - 0.3 + ease.outCubic(prog(t, 0, 2.4)) * 0.3 + sway};
  if (t < SH.B[1]) return {target: [0.2, 2.2, 0.2], zoom: mix(112, 124, prog(t, SH.B[0], SH.B[1])), az: FACE + sway};
  if (t < SH.C[1]) return {target: [0.2, mix(1.2, 2.2, ease.inOutCubic(prog(t, beat(9.5), SH.C[1]))), 0.2], zoom: mix(100, 116, prog(t, SH.C[0], SH.C[1])), az: FACE + 0.1 * Math.sin(t)};
  if (t < SH.D[1]) {
    const shots: [number, Cam][] = [
      [SH.D[0], {target: [-0.6, 2.6, -0.6], zoom: 84, az: FACE - 0.18}],
      [beat(14), {target: [-1.4, 3.4, -1.4], zoom: 140, az: FACE}],
      [beat(16.6), {target: [PORTRAIT[0], 2.8, PORTRAIT[2]], zoom: 150, az: FACE}],
      [beat(19), {target: [1.8, 2.4, -1.8], zoom: 74, az: FACE + 0.2}],
    ];
    let i = shots.length - 1; while (i > 0 && t < shots[i][0]) i--;
    const [s0, a] = shots[i]; const b = shots[Math.min(i + 1, shots.length - 1)][1];
    const next = shots[Math.min(i + 1, shots.length - 1)][0];
    const k = i === shots.length - 1 ? 0 : ease.inOutExpo(prog(t, next - 0.22, next + 0.06));
    const drift = (t - s0) * 0.02;
    return {target: [mix(a.target[0], b.target[0], k), mix(a.target[1], b.target[1], k), mix(a.target[2], b.target[2], k)], zoom: mix(a.zoom, b.zoom, k) * (1 + drift), az: mix(a.az, b.az, k) + sway * 0.5};
  }
  const e = ease.outCubic(prog(t, SH.E[0], SH.E[0] + 1.2));
  return {target: [0, mix(2.6, 1.5, e), 0], zoom: mix(105, 128, e) + (t - SH.E[0]) * 2, az: FACE + mix(0.3, 0, e) + sway * 0.4};
};

const FrameDriver: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const advance = useThree((s) => s.advance);
  const handle = useMemo(() => delayRender(`iso frame ${frame}`), [frame]);
  useEffect(() => {
    Promise.all(pending.splice(0)).then(() => {
      advance((frame / fps) * 1000);
      requestAnimationFrame(() => continueRender(handle));
    });
  }, [frame, fps, advance, handle]);
  return null;
};

export const ReleaseWorld: React.FC<{fonts: Fonts}> = ({fonts}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const {camera, scene, gl} = useThree();
  useMemo(() => {
    const pm = new THREE.PMREMGenerator(gl);
    scene.environment = pm.fromScene(new RoomEnvironment(), 0.04).texture;
    (scene as any).environmentIntensity = 0.6;
    scene.background = new THREE.Color('#050405');
    scene.fog = new THREE.Fog('#050405', 36, 70);
    gl.shadowMap.enabled = true; gl.shadowMap.type = THREE.PCFSoftShadowMap;
  }, [gl, scene]);

  const m = useMats();
  const roseTex = useMemo(() => frameTexture(), []);
  const clipTex = useMemo(() => frameTexture(), []);
  const coverTex = useMemo(() => { const tx = new THREE.TextureLoader().load(staticFile(REL.cover)); tx.colorSpace = THREE.SRGBColorSpace; tx.anisotropy = 8; return tx; }, []);
  const photo = useMemo(() => Object.fromEntries(Object.entries(REL.photos).map(([k, src]) => { const tx = new THREE.TextureLoader().load(staticFile(src)); tx.colorSpace = THREE.SRGBColorSpace; tx.anisotropy = 8; return [k, tx]; })) as Record<keyof typeof REL.photos, THREE.Texture>, []);
  const gothic = fonts.gothic ?? fonts.display;
  const fx = useMemo(() => ({blur: new RadialBlurEffect(), grade: new GradeGlitchEffect(), lens: new LensFXEffect()}), []);
  const coverMat = useMemo(() => new THREE.MeshStandardMaterial({map: coverTex, emissiveMap: coverTex, emissive: new THREE.Color('#ffffff'), emissiveIntensity: 0.9, roughness: 0.55, envMapIntensity: 0.2}), [coverTex]);

  // caméra orthographique isométrique + punch de zoom sur les impacts (comme les « speed ramps » des références)
  const c = camAt(t);
  const punch = near(t, IMPACTS, 0.09);
  const shk = shake(t, SH.B[0], 0.1) + shake(t, beat(5), 0.08) + shake(t, SH.C[0] + 0.28, 0.25) + shake(t, SH.E[0], 0.08);
  const R = 40;
  const cam = camera as THREE.OrthographicCamera;
  cam.position.set(c.target[0] + R * Math.cos(ISO_EL) * Math.sin(c.az) + Math.sin(t * 70) * shk, c.target[1] + R * Math.sin(ISO_EL) + Math.cos(t * 63) * shk, c.target[2] + R * Math.cos(ISO_EL) * Math.cos(c.az));
  cam.lookAt(...c.target);
  cam.zoom = c.zoom * (1 + punch * 0.14); cam.near = 0.1; cam.far = 200; cam.updateProjectionMatrix();
  const whip = near(t, SHOT_T, 0.09), tr = near(t, CUTS, 0.07);
  fx.blur.set(Math.max(tr * 0.18, whip * 0.14), 1 + tr * 0.9);
  fx.grade.set(glitchAmount(t), Math.floor(t * 30));
  fx.lens.set(0.16 + punch * 0.2 + whip * 0.1, 0.018 + punch * 0.03 + tr * 0.04);

  // flux vidéo
  const rosePing = (x: number) => { const n = REL.rose.frames - 1; const k = Math.floor(x) % (2 * n); return k < n ? k : 2 * n - k; };
  setFrame(roseTex, REL.rose.dir, rosePing(t * 15));
  const TXT: [number, number] = [7.55, 8.65];
  const clipIdx = (s: number) => { if (s >= TXT[0] && s <= TXT[1]) s -= 3.1; return clamp(Math.floor(s * REL.clip.fps), 0, REL.clip.frames - 1); };
  const titleK = ease.outExpo(prog(t, TXT[0], TXT[0] + 0.2)) * (1 - ease.inCubic(prog(t, TXT[1] - 0.15, TXT[1] + 0.05)));
  if (t >= SH.D[0] - 0.1 && t < SH.D[1] + 0.1) setFrame(clipTex, REL.clip.dir, clipIdx(t));

  const flicker = 0.85 + 0.15 * Math.sin(t * 37) * Math.sin(t * 13.3) + (Math.floor(t * 30) % 47 === 0 ? -0.5 : 0);
  const inA = t < SH.A[1], inB = t >= SH.B[0] && t < SH.B[1], inC = t >= SH.C[0] && t < SH.C[1], inD = t >= SH.D[0] && t < SH.D[1], inE = t >= SH.E[0];
  const onFloor = (size: number) => size * 0.36; // poser un texte 3D sur le sol

  return (
    <>
      <ambientLight intensity={0.25} />
      <hemisphereLight args={['#d6dbe8', '#2a0508', 0.9]} />
      <directionalLight position={[7, 14, 9]} intensity={4.2} color="#f1ecf2" castShadow shadow-mapSize={[2048, 2048]}
        shadow-camera-left={-9} shadow-camera-right={9} shadow-camera-top={9} shadow-camera-bottom={-9} shadow-camera-near={1} shadow-camera-far={40} shadow-bias={-0.0004} shadow-normalBias={0.02} />
      <spotLight position={[5, 8, 5]} target-position={[0, 0, 0]} angle={0.6} penumbra={0.8} intensity={260} distance={30} color={C.red} />
      <pointLight position={[3, 3.5, 6]} intensity={40} distance={20} color="#e8ecf5" />
      <Diorama m={m} fonts={fonts} neonText={inE || inD ? REL.title : undefined} flicker={flicker} />

      {/* A — la rose en feu à l'écran, le nom de l'artiste posé au sol */}
      {inA && (
        <group>
          <group position={[-1.2, 0, -1.2]} rotation-y={FACE}>
            <ScreenStand w={4.8} tex={roseTex} m={m} y={3.0} scale={[1, Math.max(0.001, ease.outBack(prog(t, 0.05, 0.55))), 1]} />
          </group>
          <group position={[1.0, 0, 1.0]} rotation-y={FACE}>
            <Text3D font={fonts.display} text={REL.artist} size={1.0} depth={0.4} tracking={0.04} material={m.nameChrome} position={[0, onFloor(1.0), 0]} castShadow
              anim={(i) => dropIn(t, beat(1) + i * 0.085)} />
          </group>
          <Petals t={t} t0={0.4} count={60} seed={2} />
        </group>
      )}
      {/* B — NO PAIN / NO GAIN en lettres monumentales posées dans le parking */}
      {inB && (
        <group>
          <group position={[-1.6, 0, -1.6]} rotation-y={FACE}><ScreenStand w={4.8} tex={roseTex} m={m} y={3.4} dim={0.5} /></group>
          <group position={[0.7, 0, 0.7]} rotation-y={FACE}>
            <Text3D font={fonts.display} text={REL.titleLong[0]} size={1.05} depth={0.45} material={m.redChrome} position={[0, 1.55 + onFloor(1.05), -0.6]} castShadow
              anim={() => { const k = ease.outExpo(prog(t, SH.B[0], SH.B[0] + 0.25)); return {s: mix(2.4, 1, k), z: (1 - k) * 4}; }} />
            <Text3D font={fonts.display} text={REL.titleLong[1]} size={1.05} depth={0.45} material={m.redChrome} position={[0, onFloor(1.05), 0.3]} castShadow
              anim={() => { const k = ease.outExpo(prog(t, beat(5), beat(5) + 0.25)); return {s: t < beat(5) ? 0.001 : mix(2.4, 1, k), z: (1 - k) * 4}; }} />
          </group>
          <Petals t={t} t0={SH.B[0] - 1.5} count={80} seed={3} />
        </group>
      )}
      {/* C — la pochette s'écrase sur le sol (ombre qui grandit, poussière), puis se redresse */}
      {inC && (() => {
        const land = SH.C[0] + 0.28;
        const fall = ease.inCubic(prog(t, SH.C[0], land));
        const bounce = t > land ? Math.exp(-(t - land) * 7) * Math.abs(Math.sin((t - land) * 22)) * 0.3 : 0;
        const stand = ease.inOutCubic(prog(t, beat(9.5), SH.C[1] - 0.05));
        return (
          <group position={[0.4, 0, 0.4]}>
            <group rotation-y={FACE} position={[0, mix(mix(12, 0.17, fall) + bounce, 2.35, stand), 0]}>
              <group rotation-x={mix(0, Math.PI / 2 - 0.15, stand)}>
                <mesh castShadow receiveShadow material={m.blackGloss}><boxGeometry args={[4.0, 0.3, 4.0]} /></mesh>
                <mesh position-y={0.152} rotation-x={-Math.PI / 2} material={coverMat}><planeGeometry args={[3.8, 3.8]} /></mesh>
              </group>
            </group>
            <Dust t={t} at={land} />
            <group rotation-y={FACE}>
              <Text3D font={fonts.display} text={REL.kicker} size={0.55} depth={0.3} material={m.nameChrome} position={[0, 5.0, -0.6]} castShadow
                anim={(i) => dropIn(t, beat(9) + i * 0.04, 0.35)} />
            </group>
          </group>
        );
      })()}
      {/* D — le clip sur l'écran du parking (synchro labiale), photos sur les côtés, portrait */}
      {inD && (
        <group>
          <group position={[-1.4, 0, -1.4]} rotation-y={FACE}>
            <ScreenStand w={6.0} tex={clipTex} m={m} y={3.5} dim={mix(1, 0.35, titleK)} />
            <group visible={titleK > 0.001} position={[0, 3.5, 0.6]} scale={mix(1.8, 1, titleK)}>
              <Text3D font={gothic} text="No Pain" size={0.9} depth={0.22} material={m.glowWhite} position={[0, 0.65, 0]} />
              <Text3D font={gothic} text="No Gain" size={0.9} depth={0.22} material={m.glowWhite} position={[0, -0.85, 0]} />
            </group>
          </group>
          {[[-3.2, 1.7, photo.studio], [1.7, -3.2, photo.duo]].map(([x, z, tx], i) => (
            <group key={i} position={[x as number, 0, z as number]} rotation-y={FACE + (i ? -0.15 : 0.15)}>
              <ScreenStand w={1.9} aspect={3 / 4} tex={tx as THREE.Texture} m={m} y={2.0} dim={1.35} />
            </group>
          ))}
          <group position={[1.4, 0, 1.4]} rotation-y={FACE}>
            <Text3D font={fonts.display} text={REL.artist} size={0.7} depth={0.35} tracking={0.05} material={m.redChrome} position={[0, onFloor(0.7), 0]} castShadow
              anim={(i) => dropIn(t, SH.D[0] + 0.1 + i * 0.06)} />
          </group>
          <group position={PORTRAIT}>
            <mesh position-y={-0.3} receiveShadow castShadow material={m.slab}><boxGeometry args={[4.6, 0.6, 4.6]} /></mesh>
            <mesh position-y={0.002} rotation-x={-Math.PI / 2} receiveShadow material={m.floor}><planeGeometry args={[4.6, 4.6]} /></mesh>
            <group rotation-y={FACE}>
              <ScreenStand w={2.9} aspect={3 / 4} tex={photo.profile} m={m} y={2.4} dim={1.9} position={[0, 0, -0.6]} />
              <Text3D font={fonts.display} text={REL.artist} size={0.7} depth={0.32} tracking={0.05} material={m.nameChrome} position={[0, onFloor(0.7), 1.1]} castShadow
                anim={(i) => dropIn(t, beat(16.6) + 0.1 + i * 0.06, 0.35)} />
            </group>
          </group>
        </group>
      )}
      {/* E — carton final : pochette sur chevalet, NPNG en néon au mur, titres 3D au sol */}
      {inE && (
        <group>
          <group position={[-1.3, 0, -1.3]} rotation-y={FACE}>
            <group position={[0, 3.2, 0]} rotation-x={-0.1} scale={ease.outBack(prog(t, SH.E[0], SH.E[0] + 0.5))}>
              <mesh position-z={-0.16} castShadow material={m.blackGloss}><boxGeometry args={[3.6, 3.6, 0.26]} /></mesh>
              <mesh material={coverMat}><planeGeometry args={[3.4, 3.4]} /></mesh>
            </group>
            <mesh position={[0, 0.7, -0.4]} castShadow material={m.steel}><boxGeometry args={[0.1, 1.4, 0.1]} /></mesh>
          </group>
          <group position={[1.1, 0, 1.1]} rotation-y={FACE}>
            <Text3D font={fonts.display} text={REL.title} size={1.15} depth={0.45} tracking={0.03} material={m.redChrome} position={[0, onFloor(1.15), -0.9]} castShadow
              anim={(i) => dropIn(t, SH.E[0] + 0.25 + i * 0.08, 0.45)} />
            <Text3D font={fonts.display} text={REL.artist} size={0.55} depth={0.3} tracking={0.08} material={m.nameChrome} position={[0, onFloor(0.55), 0.35]} castShadow
              anim={(i) => dropIn(t, SH.E[0] + 0.6 + i * 0.05)} />
            <Text3D font={fonts.bold} text={REL.cta} size={0.24} depth={0.2} tracking={0.12} material={m.nameChrome} position={[0, onFloor(0.24), 1.15]} castShadow
              anim={(i) => dropIn(t, SH.E[0] + 1.0 + i * 0.025, 0.3)} />
          </group>
          <Petals t={t} t0={SH.E[0] - 0.8} count={70} seed={5} />
        </group>
      )}
      <EffectComposer multisampling={0} enableNormalPass={false}>
        <SMAA />
        <Bloom mipmapBlur intensity={1.0} luminanceThreshold={0.62} luminanceSmoothing={0.25} radius={0.72} />
        <primitive object={fx.blur} dispose={null} />
        <Vignette offset={0.22} darkness={0.85} />
        <Noise premultiply blendFunction={BlendFunction.SOFT_LIGHT} opacity={0.4} />
        <ToneMapping mode={ToneMappingMode.ACES_FILMIC} />
        <primitive object={fx.lens} dispose={null} />
        <primitive object={fx.grade} dispose={null} />
      </EffectComposer>
      <FrameDriver />
    </>
  );
};
