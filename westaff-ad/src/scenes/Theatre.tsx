import React, {useMemo} from 'react';
import * as THREE from 'three';
import {Beam, Glow, pointsMaterial, glowTexture} from '../three/fx';
import {goldPolished} from '../three/materials';
import {Ticket} from '../three/Ticket';
import {TicketKind} from '../three/ticketArt';
import {ease, prog, mix, rng, Path, clamp} from '../lib/anim';
import {BRAND} from '../brand';
import type {Fonts, CamState, SceneLook} from './types';

export const theatreLook: SceneLook = {background: '#030108', fog: {color: '#0c0414', density: 0.018}, env: 0.3, exposure: 1.0, bloom: 1.1};
const STAGE_Y = 0.9;
export const HERO_TICKET: [number, number, number] = [0.3, 4.4, 4.4];

const camPos = new Path([[0, 5.4, 4.2], [0, 6.4, 12], [0, 6.6, 17.5], [0.9, 4.9, 10]]);
const camTgt = new Path([[0, 5.4, -1], [0, 6.2, -2], [0, 6.0, -3], [0.1, 4.5, -3]]);
export const theatreCamera = (t: number): CamState => {
  const s = t - 14;
  const u = ease.inOutSine(prog(s, 0, 3.5));
  const p = camPos.at(u), g = camTgt.at(u);
  const k = ease.inExpo(prog(s, 3.45, 4.0));
  return {
    pos: [mix(p.x, HERO_TICKET[0], k), mix(p.y, HERO_TICKET[1], k), mix(p.z, HERO_TICKET[2] + 0.75, k)],
    target: [mix(g.x, HERO_TICKET[0], k), mix(g.y, HERO_TICKET[1], k), mix(g.z, HERO_TICKET[2], k)],
    fov: mix(mix(46, 50, u), 34, k), roll: Math.sin(s * 0.6) * 0.012,
  };
};

const prosceniumGeometry = () => {
  const outer = new THREE.Shape(); outer.moveTo(-10.5, 0); outer.lineTo(10.5, 0); outer.lineTo(10.5, 13.5); outer.lineTo(-10.5, 13.5); outer.lineTo(-10.5, 0);
  const hole = new THREE.Path(); hole.moveTo(-7.6, 0); hole.lineTo(7.6, 0); hole.lineTo(7.6, 8.6);
  hole.absellipse(0, 8.6, 7.6, 2.1, 0, Math.PI, false); hole.lineTo(-7.6, 0);
  outer.holes.push(hole);
  const g = new THREE.ExtrudeGeometry(outer, {depth: 0.8, bevelEnabled: true, bevelThickness: 0.18, bevelSize: 0.16, bevelSegments: 6, curveSegments: 48});
  g.translate(0, 0, -0.8);
  return g;
};

const woodTexture = () => {
  const c = document.createElement('canvas'); c.width = 1024; c.height = 1024; const g = c.getContext('2d')!;
  let s = 5; const r = () => ((s = (s * 16807) % 2147483647) / 2147483647);
  for (let i = 0; i < 16; i++) {
    const base = 40 + r() * 20; g.fillStyle = `rgb(${base + 30},${base + 12},${base})`; g.fillRect(i * 64, 0, 64, 1024);
    for (let k = 0; k < 40; k++) { g.strokeStyle = `rgba(20,8,4,${0.05 + r() * 0.1})`; g.beginPath(); const x = i * 64 + r() * 64; g.moveTo(x, 0); g.bezierCurveTo(x + 6, 300, x - 6, 700, x + 3, 1024); g.stroke(); }
    g.fillStyle = 'rgba(0,0,0,0.6)'; g.fillRect(i * 64, 0, 2, 1024);
  }
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(2, 1.5); t.colorSpace = THREE.SRGBColorSpace; return t;
};

/** Rideau : plis sinusoïdaux qui se resserrent vers l'embrasse quand il s'ouvre. */
const Curtain: React.FC<{side: -1 | 1; open: number; mat: THREE.Material; t: number}> = ({side, open, mat, t}) => {
  const geo = useMemo(() => new THREE.PlaneGeometry(8.4, 10.2, 110, 36), []);
  const base = useMemo(() => Float32Array.from(geo.attributes.position.array as Float32Array), [geo]);
  const pos = geo.attributes.position as THREE.BufferAttribute;
  for (let i = 0; i < pos.count; i++) {
    const bx = base[i * 3] + 4.2, by = base[i * 3 + 1] + 5.1; // u: 0 (bord extérieur) → 8.4, y: 0 → 10.2
    const k = clamp(1 - Math.abs(by - 3.4) / 8, 0.42, 1);
    const c = mix(1, 0.17, open * k);
    const sweep = open * Math.pow(clamp((3.4 - by) / 3.4), 2) * 0.9; // la partie basse s'écarte
    const x = -7.95 + bx * c - sweep * (bx / 8.4);
    const amp = 0.17 / Math.sqrt(c);
    const z = Math.sin(bx * 2.7 + side) * amp + Math.sin(bx * 7.3) * 0.035 + Math.sin(t * 1.2 + by * 0.6 + bx) * 0.02 * (1 - open);
    pos.setXYZ(i, side * x, by + STAGE_Y, z);
  }
  pos.needsUpdate = true; geo.computeVertexNormals();
  return <mesh geometry={geo} material={mat} position-z={-1.1} />;
};

export const Theatre: React.FC<{t: number; fonts: Fonts}> = ({t}) => {
  const s = t - 14;
  const open = ease.inOutCubic(prog(s, 0.3, 2.1));
  const res = useMemo(() => {
    const r = rng(23);
    const velvet = new THREE.MeshPhysicalMaterial({color: '#4a0b30', roughness: 0.78, sheen: 1, sheenColor: new THREE.Color('#ff5aa8'), sheenRoughness: 0.45, side: THREE.DoubleSide});
    // fauteuils
    const seatGeo = new THREE.BoxGeometry(0.55, 0.12, 0.5); seatGeo.translate(0, 0.45, 0);
    const backGeo = new THREE.BoxGeometry(0.55, 0.7, 0.1); backGeo.translate(0, 0.8, 0.25);
    const rows = 10, per = 24;
    const seats = new THREE.InstancedMesh(seatGeo, velvet, rows * per), backs = new THREE.InstancedMesh(backGeo, velvet, rows * per);
    const heads = new THREE.InstancedMesh(new THREE.SphereGeometry(0.13, 10, 8), new THREE.MeshStandardMaterial({color: '#08060a', roughness: 0.6}), rows * per);
    const m = new THREE.Matrix4(); let k = 0;
    for (let i = 0; i < rows; i++) for (let j = 0; j < per; j++, k++) {
      const x = (j - per / 2 + 0.5) * 0.62 + (j >= per / 2 ? 0.8 : -0.8), z = 3.2 + i * 1.05, y = i * 0.28;
      m.makeTranslation(x, y, z); seats.setMatrixAt(k, m); backs.setMatrixAt(k, m);
      m.makeTranslation(x + (r() - 0.5) * 0.05, r() < 0.55 ? y + 1.32 : -9, z + 0.05); heads.setMatrixAt(k, m);
    }
    // toile étoilée du fond de scène
    const NS = 900, sg = new THREE.BufferGeometry(), sp = new Float32Array(NS * 3), sc = new Float32Array(NS * 3), ss = new Float32Array(NS), sa = new Float32Array(NS);
    for (let i = 0; i < NS; i++) { sp.set([(r() - 0.5) * 15, STAGE_Y + 0.5 + r() * 10, -8.5], i * 3); const c = new THREE.Color(r() < 0.7 ? BRAND.colors.goldLight : '#ffffff'); sc.set([c.r * 1.5, c.g * 1.5, c.b * 1.5], i * 3); ss[i] = 0.02 + r() * 0.05; sa[i] = 0.3 + r() * 0.7; }
    sg.setAttribute('position', new THREE.BufferAttribute(sp, 3)); sg.setAttribute('color', new THREE.BufferAttribute(sc, 3)); sg.setAttribute('aSize', new THREE.BufferAttribute(ss, 1)); sg.setAttribute('aAlpha', new THREE.BufferAttribute(sa, 1));
    const sm = pointsMaterial(); sm.uniforms.uScale.value = 900;
    const kinds: TicketKind[] = ['concert', 'show', 'football'];
    const tickets = Array.from({length: 13}, (_, i) => ({
      kind: kinds[i % 3],
      p: i < 7 ? [(r() - 0.5) * 9, STAGE_Y + 1.8 + r() * 5, -1.5 - r() * 4.5] : [(r() < 0.5 ? -1 : 1) * (1.4 + r() * 2.6), 3.2 + r() * 2.8, 1 + r() * 7],
      ph: r() * 6.28, sp: 0.3 + r() * 0.5, sc: 0.35 + r() * 0.2,
    }));
    const wall = new THREE.Shape(); wall.moveTo(-40, -2); wall.lineTo(40, -2); wall.lineTo(40, 30); wall.lineTo(-40, 30); wall.lineTo(-40, -2);
    const wh = new THREE.Path(); wh.moveTo(-10.4, 0); wh.lineTo(10.4, 0); wh.lineTo(10.4, 13.4); wh.lineTo(-10.4, 13.4); wh.lineTo(-10.4, 0); wall.holes.push(wh);
    return {velvet, seats, backs, heads, sg, sm, tickets, frame: prosceniumGeometry(), wall: new THREE.ShapeGeometry(wall), wood: woodTexture(), gold: goldPolished()};
  }, []);

  return (
    <group>
      <ambientLight intensity={0.06} />
      <spotLight position={[0, 15, 11]} target-position={[0, STAGE_Y, -3]} angle={0.26} penumbra={0.5} intensity={1400 * (0.2 + open)} distance={60} color="#fff0d6" />
      <spotLight position={[-7, 13, 9]} target-position={[-1, 5, -1]} angle={0.4} penumbra={0.8} intensity={600} distance={50} color={BRAND.colors.violet} />
      <spotLight position={[7, 13, 9]} target-position={[1, 5, -1]} angle={0.4} penumbra={0.8} intensity={600} distance={50} color={BRAND.colors.electric} />
      <pointLight position={[0, 3, 2]} intensity={40} distance={14} color="#ffcf8a" />
      <spotLight position={[0, 9, 16]} target-position={[0, 6, -1]} angle={0.55} penumbra={0.9} intensity={900} distance={60} color="#ffd9a8" />
      <spotLight position={[-9, 3, 12]} target-position={[-6, 8, 0]} angle={0.5} penumbra={0.9} intensity={350} distance={40} color={BRAND.colors.violet} />
      <spotLight position={[9, 3, 12]} target-position={[6, 8, 0]} angle={0.5} penumbra={0.9} intensity={350} distance={40} color={BRAND.colors.electric} />
      {/* architecture */}
      <mesh geometry={res.wall} position={[0, 0, -0.85]}><meshStandardMaterial color="#120818" roughness={0.9} /></mesh>
      <mesh geometry={res.frame} material={res.gold} position-z={-0.2} />
      <mesh position={[0, STAGE_Y / 2, -4]}><boxGeometry args={[22, STAGE_Y, 10]} /><meshStandardMaterial color="#0d0709" roughness={0.6} /></mesh>
      <mesh position={[0, STAGE_Y + 0.001, -4]} rotation-x={-Math.PI / 2}><planeGeometry args={[22, 10]} /><meshPhysicalMaterial map={res.wood} roughness={0.3} clearcoat={0.6} clearcoatRoughness={0.2} /></mesh>
      <mesh position={[0, 0, 12]} rotation-x={-Math.PI / 2}><planeGeometry args={[80, 30]} /><meshStandardMaterial color="#0a050c" roughness={0.9} /></mesh>
      <mesh position={[0, STAGE_Y + 0.003, -3]} rotation-x={-Math.PI / 2}><circleGeometry args={[2.6, 48]} /><meshBasicMaterial map={glowTexture()} color={new THREE.Color(1.6, 1.3, 1)} transparent opacity={0.9 * open} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
      <mesh position={[0, 6, -8.8]}><planeGeometry args={[18, 14]} /><meshBasicMaterial color="#090418" /></mesh>
      <points geometry={res.sg} material={res.sm} />
      {/* rideaux + lambrequin */}
      <Curtain side={-1} open={open} mat={res.velvet} t={t} />
      <Curtain side={1} open={open} mat={res.velvet} t={t} />
      <mesh position={[0, 10.15, -0.7]}><boxGeometry args={[16, 1.5, 0.3]} /><primitive object={res.velvet} attach="material" /></mesh>
      <mesh position={[0, 9.4, -0.52]}><boxGeometry args={[16, 0.08, 0.05]} /><primitive object={res.gold} attach="material" /></mesh>
      {/* rampe de lumière + appliques */}
      {Array.from({length: 11}, (_, i) => <Glow key={i} position={[-7 + i * 1.4, STAGE_Y + 0.1, 0.4]} scale={0.9} color="#ffcc80" opacity={0.8} />)}
      {[-13, 13].map((x) => [4, 8].map((y) => <Glow key={`${x}${y}`} position={[x, y, -0.6]} scale={2.2} color="#ffb766" opacity={0.7} />))}
      <Beam position={[0, 15, 11]} target={[0, STAGE_Y, -3]} radius={3.0} length={20} color="#ffe6c0" opacity={0.18 + 0.25 * open} />
      <Beam position={[-7, 13, 9]} target={[-1, 4, -1]} radius={3.4} length={17} color={BRAND.colors.violet} opacity={0.25} />
      <Beam position={[7, 13, 9]} target={[1, 4, -1]} radius={3.4} length={17} color={BRAND.colors.electric} opacity={0.25} />
      {/* public */}
      <primitive object={res.seats} /><primitive object={res.backs} /><primitive object={res.heads} />
      {/* billets flottants */}
      {res.tickets.map((tk, i) => (
        <Ticket key={i} kind={tk.kind as TicketKind} scale={tk.sc}
          position={[tk.p[0], tk.p[1] + Math.sin(t * tk.sp + tk.ph) * 0.25, tk.p[2]]}
          rotation={[Math.sin(t * 0.5 + tk.ph) * 0.3, t * tk.sp + tk.ph, Math.sin(t * 0.4 + tk.ph) * 0.2]}
          sweep={((t * 0.4 + tk.ph) % 2) - 0.4} time={t} holo={0.25} emissive={0.35} />
      ))}
      <Ticket kind="football" position={HERO_TICKET} scale={0.42} rotation={[0.05, Math.sin(t * 0.8) * 0.25, 0.03]} sweep={mix(-0.5, 1.5, prog(s, 2.8, 3.9))} time={t} holo={0.35} emissive={0.35} />
    </group>
  );
};
