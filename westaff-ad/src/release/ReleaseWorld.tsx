import React, {useEffect, useMemo} from 'react';
import * as THREE from 'three';
import {useThree} from '@react-three/fiber';
import {useCurrentFrame, useVideoConfig, delayRender, continueRender, staticFile} from 'remotion';
import {RoundedBoxGeometry} from 'three/examples/jsm/geometries/RoundedBoxGeometry.js';
import {RoomEnvironment} from 'three/examples/jsm/environments/RoomEnvironment.js';
import {EffectComposer, Bloom, Vignette, Noise, ToneMapping, SMAA, ChromaticAberration} from '@react-three/postprocessing';
import {ToneMappingMode, BlendFunction} from 'postprocessing';
import {Text3D} from '../three/Text3D';
import {Glow, pointsMaterial} from '../three/fx';
import {RadialBlurEffect} from '../three/RadialBlur';
import {ease, prog, mix, rng, clamp} from '../lib/anim';
import type {Fonts} from '../scenes/types';
import {REL, SH, beat} from './config';
import {pending, frameTexture, setFrame} from './frames';

const C = REL.colors;
const ISO_EL = Math.asin(1 / Math.sqrt(3)); // 35,26° : vraie isométrie
const FACE = Math.PI / 4; // les objets « face caméra » sont tournés de 45°
export const CUTS = [SH.B[0], SH.C[0], SH.D[0], SH.E[0]];
const cutAmount = (t: number) => CUTS.reduce((a, b) => Math.max(a, Math.exp(-Math.pow((t - b) / 0.07, 2))), 0);
const shake = (t: number, at: number, amp: number) => (t >= at ? Math.exp(-(t - at) * 9) * amp : 0);

// ---------- matériaux ----------
const mats = () => ({
  redChrome: new THREE.MeshPhysicalMaterial({color: '#c3101c', metalness: 1, roughness: 0.22, clearcoat: 1, clearcoatRoughness: 0.08, emissive: new THREE.Color('#3a0206'), envMapIntensity: 1.6}),
  whiteChrome: new THREE.MeshPhysicalMaterial({color: '#f2efe9', metalness: 1, roughness: 0.16, clearcoat: 1, envMapIntensity: 1.8}),
  darkMetal: new THREE.MeshPhysicalMaterial({color: '#141217', metalness: 0.9, roughness: 0.35, clearcoat: 0.6}),
  neon: new THREE.MeshBasicMaterial({color: new THREE.Color(C.red).multiplyScalar(4), toneMapped: false}),
});

const asphaltTexture = () => {
  const c = document.createElement('canvas'); c.width = c.height = 1024; const g = c.getContext('2d')!;
  g.fillStyle = '#17161a'; g.fillRect(0, 0, 1024, 1024);
  let s = 9; const r = () => ((s = (s * 16807) % 2147483647) / 2147483647);
  for (let i = 0; i < 90000; i++) { const v = 20 + r() * 40; g.fillStyle = `rgba(${v},${v},${v + 4},0.5)`; g.fillRect(r() * 1024, r() * 1024, 2, 2); }
  g.strokeStyle = 'rgba(235,235,225,0.75)'; g.lineWidth = 10;
  for (let i = 0; i < 6; i++) { g.beginPath(); g.moveTo(80 + i * 170, 60); g.lineTo(80 + i * 170, 420); g.stroke(); }
  g.strokeStyle = 'rgba(208,20,31,0.8)'; g.lineWidth = 14; g.strokeRect(30, 30, 964, 964);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; return t;
};

const Platform: React.FC<{size: [number, number]; y?: number; m: ReturnType<typeof mats>; tex: THREE.Texture}> = ({size, y = 0, m, tex}) => {
  const geo = useMemo(() => new RoundedBoxGeometry(size[0], 0.5, size[1], 4, 0.12), [size[0], size[1]]);
  return (
    <group position={[0, y - 0.25, 0]}>
      <mesh geometry={geo} material={m.darkMetal} />
      <mesh position-y={0.252} rotation-x={-Math.PI / 2}><planeGeometry args={[size[0] - 0.1, size[1] - 0.1]} /><meshStandardMaterial map={tex} roughness={0.85} /></mesh>
      {/* liseré néon */}
      <mesh position={[0, 0.26, size[1] / 2 - 0.02]} material={m.neon}><boxGeometry args={[size[0] - 0.2, 0.03, 0.03]} /></mesh>
      <mesh position={[size[0] / 2 - 0.02, 0.26, 0]} material={m.neon}><boxGeometry args={[0.03, 0.03, size[1] - 0.2]} /></mesh>
    </group>
  );
};

/** Écran 3D (cadre métal + image vidéo), orienté vers la caméra. */
const Screen: React.FC<{w: number; tex: THREE.Texture; m: ReturnType<typeof mats>; dim?: number} & JSX.IntrinsicElements['group']> = ({w, tex, m, dim = 1, ...rest}) => {
  const h = (w * 3) / 4;
  const frame = useMemo(() => new RoundedBoxGeometry(w + 0.3, h + 0.3, 0.35, 4, 0.08), [w, h]);
  return (
    <group {...rest}>
      <mesh geometry={frame} material={m.darkMetal} position-z={-0.19} />
      <mesh position-z={0.0}><planeGeometry args={[w, h]} /><meshBasicMaterial map={tex} color={new THREE.Color(dim, dim, dim)} toneMapped={false} /></mesh>
      <mesh position={[0, -h / 2 - 0.16, 0.0]} material={m.neon}><boxGeometry args={[w * 0.6, 0.03, 0.03]} /></mesh>
    </group>
  );
};

/** Particules de feu / braises (déterministes). */
const Fire: React.FC<{t: number; t0: number; origin: [number, number, number]; width: number; rate?: number; seed?: number}> = ({t, t0, origin, width, seed = 3}) => {
  const N = 900;
  const res = useMemo(() => {
    const r = rng(seed);
    const P = Array.from({length: N}, () => ({x: (r() - 0.5) * width, z: (r() - 0.5) * 0.6, born: r() * 6, life: 0.6 + r() * 1.1, vy: 1.2 + r() * 2.2, sway: r() * 6, s: 0.03 + Math.pow(r(), 3) * 0.12}));
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(N * 3), 3));
    g.setAttribute('color', new THREE.BufferAttribute(new Float32Array(N * 3), 3));
    g.setAttribute('aSize', new THREE.BufferAttribute(new Float32Array(N), 1));
    g.setAttribute('aAlpha', new THREE.BufferAttribute(new Float32Array(N), 1));
    const mt = pointsMaterial(); mt.uniforms.uScale.value = 22; // ortho : taille quasi constante
    return {P, g, mt};
  }, [width, seed]);
  const pos = res.g.attributes.position as THREE.BufferAttribute, col = res.g.attributes.color as THREE.BufferAttribute;
  const sz = res.g.attributes.aSize as THREE.BufferAttribute, al = res.g.attributes.aAlpha as THREE.BufferAttribute;
  const c1 = new THREE.Color('#fff2b0'), c2 = new THREE.Color(C.ember), c3 = new THREE.Color(C.red), tmp = new THREE.Color();
  res.P.forEach((p, i) => {
    const age = ((t - t0 - p.born * 0.25) % p.life + p.life) % p.life;
    const k = age / p.life, alive = t >= t0 + p.born * 0.12;
    const lx = p.x * (1 - k * 0.4) + Math.sin(age * 5 + p.sway) * 0.12, lz = p.z * 3;
    pos.setXYZ(i, origin[0] + lx * Math.cos(FACE) + lz * Math.sin(FACE), origin[1] + age * p.vy, origin[2] - lx * Math.sin(FACE) + lz * Math.cos(FACE));
    tmp.copy(k < 0.3 ? c1 : k < 0.6 ? c2 : c3).lerp(k < 0.3 ? c2 : c3, (k % 0.3) / 0.3).multiplyScalar(2.2);
    col.setXYZ(i, tmp.r, tmp.g, tmp.b);
    sz.setX(i, p.s * (1 - k * 0.6) * 1000);
    al.setX(i, alive ? Math.sin(Math.PI * Math.min(1, k * 1.2)) : 0);
  });
  pos.needsUpdate = col.needsUpdate = sz.needsUpdate = al.needsUpdate = true;
  return <points geometry={res.g} material={res.mt} frustumCulled={false} />;
};

/** Décor de fond : ville isométrique de blocs sombres à liserés néon (continuité entre les plans). */
const Backdrop: React.FC<{m: ReturnType<typeof mats>; t: number}> = ({m, t}) => {
  const res = useMemo(() => {
    const r = rng(77); const items: {x: number; z: number; w: number; d: number; h: number; neon: boolean}[] = [];
    for (let i = 0; i < 140; i++) {
      const x = (r() - 0.5) * 44, z = (r() - 0.5) * 44;
      if (Math.abs(x) < 7.5 && Math.abs(z) < 7.5) continue;
      if (x + z > 6) continue; // ne rien mettre entre la caméra et la scène
      items.push({x, z, w: 1.2 + r() * 2.6, d: 1.2 + r() * 2.6, h: 1 + Math.pow(r(), 1.6) * 13, neon: r() < 0.6});
    }
    const box = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshPhysicalMaterial({color: '#2b2730', metalness: 0.7, roughness: 0.4, clearcoat: 0.5}), items.length);
    const neon = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), m.neon, items.length);
    const mt = new THREE.Matrix4();
    items.forEach((b, i) => {
      mt.compose(new THREE.Vector3(b.x, b.h / 2 - 6, b.z), new THREE.Quaternion(), new THREE.Vector3(b.w, b.h, b.d)); box.setMatrixAt(i, mt);
      mt.compose(new THREE.Vector3(b.x, b.h - 6 + 0.02, b.z + b.d / 2), new THREE.Quaternion(), b.neon ? new THREE.Vector3(b.w, 0.04, 0.04) : new THREE.Vector3(0, 0, 0)); neon.setMatrixAt(i, mt);
    });
    return {box, neon};
  }, [m]);
  return <group position-y={Math.sin(t * 0.4) * 0.15}><primitive object={res.box} /><primitive object={res.neon} /></group>;
};

const dropIn = (t: number, start: number, dur = 0.4) => {
  const k = ease.outBack(prog(t, start, start + dur));
  return {y: (1 - k) * 1.2, rx: (1 - k) * -1.3, s: Math.max(0.001, Math.min(1.06, k))};
};

// ---------- caméra ----------
type Cam = {target: [number, number, number]; zoom: number; az: number};
const camAt = (t: number): Cam => {
  const sway = Math.sin(t * 0.6) * 0.06;
  if (t < SH.A[1]) return {target: [0, 2.2, 0], zoom: mix(118, 140, ease.outCubic(prog(t, 0, 2.4))), az: FACE - 0.25 + ease.outCubic(prog(t, 0, 2.4)) * 0.25 + sway};
  if (t < SH.B[1]) return {target: [0, 2.7, 0], zoom: mix(150, 172, prog(t, SH.B[0], SH.B[1])), az: FACE + sway};
  if (t < SH.C[1]) return {target: [0, mix(1.0, 1.8, ease.inOutCubic(prog(t, beat(9.5), SH.C[1]))), 0], zoom: mix(122, 138, prog(t, SH.C[0], SH.C[1])), az: FACE + 0.12 * Math.sin(t) };
  if (t < SH.D[1]) {
    // recadrages sur les temps forts
    const shots: [number, Cam][] = [
      [SH.D[0], {target: [0, 2.4, 0], zoom: 100, az: FACE - 0.18}],
      [beat(14), {target: [0, 3.3, 0], zoom: 150, az: FACE}],
      [beat(17), {target: [0.4, 3.1, 0], zoom: 175, az: FACE + 0.28}],
      [beat(19), {target: [-0.4, 3.1, 0], zoom: 175, az: FACE - 0.28}],
      [beat(20), {target: [0, 2.6, 0], zoom: 108, az: FACE + 0.22}],
    ];
    let i = shots.length - 1; while (i > 0 && t < shots[i][0]) i--;
    const [s0, a] = shots[i]; const b = shots[Math.min(i + 1, shots.length - 1)][1];
    const next = shots[Math.min(i + 1, shots.length - 1)][0];
    const k = i === shots.length - 1 ? 0 : ease.inOutExpo(prog(t, next - 0.22, next + 0.06));
    const drift = (t - s0) * 0.02;
    return {target: [mix(a.target[0], b.target[0], k), mix(a.target[1], b.target[1], k), mix(a.target[2], b.target[2], k)], zoom: mix(a.zoom, b.zoom, k) * (1 + drift), az: mix(a.az, b.az, k) + sway * 0.5};
  }
  const e = ease.outCubic(prog(t, SH.E[0], SH.E[0] + 1.2));
  return {target: [0, mix(3.2, 2.0, e), 0], zoom: mix(140, 170, e) + (t - SH.E[0]) * 2.5, az: FACE + mix(0.3, 0, e) + sway * 0.4};
};

const FrameDriver: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const advance = useThree((s) => s.advance);
  const handle = useMemo(() => delayRender(`iso frame ${frame}`), [frame]);
  useEffect(() => {
    // attendre les images vidéo demandées par les écrans avant de dessiner
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
    (scene as any).environmentIntensity = 0.55;
    scene.background = new THREE.Color(C.bg);
    scene.fog = new THREE.Fog(C.bg, 32, 66);
  }, [gl, scene]);

  const m = useMemo(() => mats(), []);
  const asphalt = useMemo(() => asphaltTexture(), []);
  const roseTex = useMemo(() => frameTexture(), []);
  const clipTex = useMemo(() => [frameTexture(), frameTexture(), frameTexture()], []);
  const coverTex = useMemo(() => { const tx = new THREE.TextureLoader().load(staticFile(REL.cover)); tx.colorSpace = THREE.SRGBColorSpace; tx.anisotropy = 8; return tx; }, []);
  const blur = useMemo(() => new RadialBlurEffect(), []);

  // caméra orthographique isométrique
  const c = camAt(t);
  const shk = shake(t, SH.B[0], 0.12) + shake(t, beat(5), 0.1) + shake(t, beat(8) + 0.28, 0.22) + shake(t, SH.E[0], 0.08);
  const R = 40;
  const cam = camera as THREE.OrthographicCamera;
  cam.position.set(c.target[0] + R * Math.cos(ISO_EL) * Math.sin(c.az) + Math.sin(t * 70) * shk, c.target[1] + R * Math.sin(ISO_EL) + Math.cos(t * 63) * shk, c.target[2] + R * Math.cos(ISO_EL) * Math.cos(c.az));
  cam.lookAt(...c.target);
  cam.zoom = c.zoom; cam.near = 0.1; cam.far = 200; cam.updateProjectionMatrix();
  const tr = cutAmount(t);
  blur.set(tr * 0.18, 1 + tr * 1.2);

  // flux vidéo
  const rosePing = (x: number) => { const n = REL.rose.frames - 1; const k = Math.floor(x) % (2 * n); return k < n ? k : 2 * n - k; };
  setFrame(roseTex, REL.rose.dir, rosePing(t * 15));
  const TXT: [number, number] = [7.55, 8.65]; // passage du clip avec texte incrusté → remplacé par du texte 3D
  const clipIdx = (s: number) => { if (s >= TXT[0] && s <= TXT[1]) s -= 3.1; return clamp(Math.floor(s * REL.clip.fps), 0, REL.clip.frames - 1); };
  const titleK = ease.outExpo(prog(t, TXT[0], TXT[0] + 0.2)) * (1 - ease.inCubic(prog(t, TXT[1] - 0.15, TXT[1] + 0.05)));
  if (t >= SH.D[0] - 0.1 && t < SH.D[1] + 0.1) {
    setFrame(clipTex[0], REL.clip.dir, clipIdx(t)); // synchro labiale avec la bande-son
    setFrame(clipTex[1], REL.clip.dir, clipIdx(t - 5.2));
    setFrame(clipTex[2], REL.clip.dir, clipIdx(t + 1.6));
  }

  const inA = t < SH.A[1], inB = t >= SH.B[0] && t < SH.B[1], inC = t >= SH.C[0] && t < SH.C[1], inD = t >= SH.D[0] && t < SH.D[1], inE = t >= SH.E[0];
  const lights = (
    <>
      <ambientLight intensity={0.25} />
      <directionalLight position={[6, 12, 4]} intensity={2.2} color="#ffe2d0" />
      <pointLight position={[-6, 4, 6]} intensity={60} color={C.red} />
      <pointLight position={[6, 5, -4]} intensity={50} color="#5a7dff" />
    </>
  );

  return (
    <>
      {lights}
      <Backdrop m={m} t={t} />
      {/* A — la rose en feu sur un écran, le nom de l'artiste en 3D */}
      {inA && (
        <group>
          <Platform size={[7.5, 7.5]} m={m} tex={asphalt} />
          <group rotation-y={FACE}>
            <Screen w={5.4} tex={roseTex} m={m} position={[0, 2.95, -0.6]} scale={[1, Math.max(0.001, ease.outBack(prog(t, 0.05, 0.55))), 1]} />
            <Glow position={[0, 3, -1.5]} scale={8} color={C.ember} opacity={0.35} />
            <Text3D font={fonts.display} text={REL.artist} size={1.05} depth={0.4} tracking={0.04} material={m.whiteChrome} position={[0, 0.6, 1.2]}
              anim={(i) => dropIn(t, beat(1) + i * 0.085)} />
          </group>
          <Fire t={t} t0={0.6} origin={[0, 0.1, 0]} width={6} seed={4} />
        </group>
      )}
      {/* B — NO PAIN / NO GAIN en 3D, en feu */}
      {inB && (
        <group>
          <Platform size={[7.5, 7.5]} m={m} tex={asphalt} />
          <group rotation-y={FACE}>
            <Screen w={5.4} tex={roseTex} m={m} position={[0, 2.95, -1.4]} dim={0.45} />
            <Text3D font={fonts.display} text={REL.titleLong[0]} size={1.15} depth={0.32} tracking={0.0} material={m.redChrome} position={[0, 3.85, 0.9]}
              anim={() => { const k = ease.outExpo(prog(t, SH.B[0], SH.B[0] + 0.25)); return {s: mix(2.4, 1, k), z: (1 - k) * 4}; }} />
            <Text3D font={fonts.display} text={REL.titleLong[1]} size={1.15} depth={0.32} tracking={0.0} material={m.redChrome} position={[0, 2.0, 0.9]}
              anim={() => { const k = ease.outExpo(prog(t, beat(5), beat(5) + 0.25)); return {s: t < beat(5) ? 0.001 : mix(2.4, 1, k), z: (1 - k) * 4}; }} />
            <Glow position={[0, 2.8, 0.2]} scale={9} color={C.red} opacity={0.4 + 0.3 * Math.sin(t * 20) ** 2} />
          </group>
          <Fire t={t} t0={beat(6) - 0.3} origin={[0, 1.3, 0.5]} width={6} seed={7} />
          <Fire t={t} t0={SH.B[0]} origin={[0, 0.1, 0]} width={6} seed={8} />
        </group>
      )}
      {/* C — la pochette tombe et s'écrase, puis se redresse */}
      {inC && (() => {
        const land = SH.C[0] + 0.28;
        const fall = ease.inCubic(prog(t, SH.C[0], land));
        const bounce = t > land ? Math.exp(-(t - land) * 7) * Math.abs(Math.sin((t - land) * 22)) * 0.35 : 0;
        const stand = ease.inOutCubic(prog(t, beat(9.5), SH.C[1] - 0.05));
        const ring = prog(t, land, land + 0.6);
        return (
          <group>
            <Platform size={[7.5, 7.5]} m={m} tex={asphalt} />
            <group rotation-y={FACE} position={[0, mix(mix(11, 0.2, fall) + bounce, 2.4, stand), 0]}>
              <group rotation-x={mix(0, Math.PI / 2 - 0.2, stand)}>
                <mesh><boxGeometry args={[4.2, 0.32, 4.2]} /><primitive object={m.darkMetal} attach="material" /></mesh>
                <mesh position-y={0.165} rotation-x={-Math.PI / 2}><planeGeometry args={[4.0, 4.0]} /><meshStandardMaterial map={coverTex} roughness={0.35} metalness={0.1} /></mesh>
              </group>
            </group>
            <mesh position-y={0.03} rotation-x={-Math.PI / 2} scale={mix(1, 3.6, ease.outCubic(ring))} visible={ring > 0 && ring < 1}>
              <ringGeometry args={[1.9, 2.05, 96]} /><meshBasicMaterial color={new THREE.Color(C.ember).multiplyScalar(3)} transparent opacity={1 - ring} toneMapped={false} />
            </mesh>
            <Fire t={t} t0={land} origin={[0, 0.1, 0]} width={5} seed={11} />
            <group rotation-y={FACE}>
              <Text3D font={fonts.display} text={REL.kicker} size={0.6} depth={0.35} material={m.whiteChrome} position={[0, 5.2, -0.6]}
                anim={(i) => dropIn(t, beat(9) + i * 0.04, 0.35)} />
            </group>
          </group>
        );
      })()}
      {/* D — le clip sur des écrans isométriques (synchro labiale) */}
      {inD && (
        <group>
          <Platform size={[12, 10]} m={m} tex={asphalt} />
          <group rotation-y={FACE}>
            <Screen w={7.0} tex={clipTex[0]} m={m} position={[0, 3.35, -1.2]} dim={mix(1, 0.4, titleK)} />
            <group visible={titleK > 0.001} position={[0, 3.35, 0.4]} scale={mix(1.8, 1, titleK)}>
              <Text3D font={fonts.display} text={REL.titleLong[0]} size={1.0} depth={0.3} material={m.whiteChrome} position={[0, 0.75, 0]} />
              <Text3D font={fonts.display} text={REL.titleLong[1]} size={1.0} depth={0.3} material={m.redChrome} position={[0, -0.85, 0]} />
            </group>
            <Text3D font={fonts.display} text={REL.artist} size={0.7} depth={0.45} tracking={0.05} material={m.redChrome} position={[0, 0.5, 1.6]}
              anim={(i) => dropIn(t, SH.D[0] + 0.1 + i * 0.06)} />
          </group>
          {[[-3.6, 1.2, -1], [1.2, -3.6, 1]].map(([x, z, sgn], i) => (
            <group key={i} position={[x, 0, z]} rotation-y={FACE + sgn * 0.12}>
              <mesh position-y={0.9}><boxGeometry args={[3.0, 1.8, 2.2]} /><primitive object={m.darkMetal} attach="material" /></mesh>
              <Screen w={2.9} tex={clipTex[i + 1]} m={m} position={[0, 2.95, 0]} />
            </group>
          ))}
          <Fire t={t} t0={SH.D[0]} origin={[0, 0.1, -3]} width={10} seed={13} />
        </group>
      )}
      {/* E — carton final : pochette + NPNG + O'NEAL + disponible maintenant */}
      {inE && (
        <group>
          <Platform size={[8, 6]} m={m} tex={asphalt} y={-0.6} />
          <group rotation-y={FACE}>
            <group position={[0, 5.0, -0.6]} rotation-x={-0.12} scale={ease.outBack(prog(t, SH.E[0], SH.E[0] + 0.5))}>
              <mesh position-z={-0.17}><boxGeometry args={[3.7, 3.7, 0.3]} /><primitive object={m.darkMetal} attach="material" /></mesh>
              <mesh><planeGeometry args={[3.5, 3.5]} /><meshStandardMaterial map={coverTex} emissiveMap={coverTex} emissive="#ffffff" emissiveIntensity={0.55} roughness={0.35} /></mesh>
            </group>
            <Glow position={[0, 5.0, -1.4]} scale={8} color={C.red} opacity={0.45} />
            <Text3D font={fonts.display} text={REL.title} size={1.2} depth={0.38} tracking={0.03} material={m.redChrome} position={[0, 2.05, 0.4]}
              anim={(i) => dropIn(t, SH.E[0] + 0.25 + i * 0.08, 0.45)} />
            <Text3D font={fonts.display} text={REL.artist} size={0.58} depth={0.32} tracking={0.08} material={m.whiteChrome} position={[0, 0.88, 0.4]}
              anim={(i) => dropIn(t, SH.E[0] + 0.6 + i * 0.05)} />
            <Text3D font={fonts.bold} text={REL.cta} size={0.26} depth={0.25} tracking={0.12} material={m.whiteChrome} position={[0, 0.2, 0.4]}
              anim={(i) => dropIn(t, SH.E[0] + 1.0 + i * 0.025, 0.3)} />
          </group>
        </group>
      )}
      <EffectComposer multisampling={0} enableNormalPass={false}>
        <SMAA />
        <Bloom mipmapBlur intensity={1.1} luminanceThreshold={0.6} luminanceSmoothing={0.25} radius={0.7} />
        <ChromaticAberration offset={new THREE.Vector2(0.0008, 0.0006)} radialModulation modulationOffset={0.4} />
        <primitive object={blur} dispose={null} />
        <Vignette offset={0.25} darkness={0.8} />
        <Noise premultiply blendFunction={BlendFunction.SOFT_LIGHT} opacity={0.4} />
        <ToneMapping mode={ToneMappingMode.ACES_FILMIC} />
      </EffectComposer>
      <FrameDriver />
    </>
  );
};
