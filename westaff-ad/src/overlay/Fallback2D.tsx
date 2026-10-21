import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {BRAND, T} from '../brand';
import {ease, prog, mix} from '../lib/anim';

/**
 * Version de secours sans WebGL (aucun GPU ni WebGL logiciel disponible).
 * Reprend la même narration, le même rythme et les mêmes textes avec des dégradés et un billet en CSS 3D.
 */
const C = BRAND.colors;
const BG: Record<string, string> = {
  intro: 'radial-gradient(circle at 50% 38%, #2a1f0a 0%, #050407 55%)',
  stadium: 'radial-gradient(ellipse at 50% 85%, #1b5f2a 0%, #0a1430 45%, #02030a 80%)',
  concert: 'radial-gradient(ellipse at 50% 35%, #5a1fb0 0%, #1a0838 45%, #04020b 80%)',
  theatre: 'radial-gradient(ellipse at 50% 45%, #6a1240 0%, #22061a 50%, #030108 85%)',
  hero: 'radial-gradient(ellipse at 50% 55%, #2a1650 0%, #0a0612 55%, #020205 85%)',
  brand: 'radial-gradient(circle at 50% 45%, #3a2a0c 0%, #0a0806 50%, #020205 85%)',
};

const CssTicket: React.FC<{rot: number; scale: number; label: string}> = ({rot, scale, label}) => (
  <div style={{width: 300, height: 750, borderRadius: 26, transform: `perspective(1400px) rotateY(${rot}deg) scale(${scale})`,
    background: 'linear-gradient(160deg, #15121c, #050508)', boxShadow: `0 0 0 5px ${C.gold}, 0 0 60px rgba(232,185,100,0.5)`,
    display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'space-between', padding: '50px 0', color: C.gold, fontFamily: 'WBold'}}>
    <div style={{letterSpacing: '0.25em', fontSize: 22}}>{BRAND.name} {BRAND.nameSub}</div>
    <div style={{fontFamily: 'WDisplay', fontSize: 52, color: '#fff'}}>{label}</div>
    <div style={{width: 200, height: 90, background: `repeating-linear-gradient(90deg, ${C.gold} 0 4px, transparent 4px 9px)`}} />
  </div>
);

export const Fallback2D: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const key = (Object.keys(T) as (keyof typeof T)[]).find((k) => t >= T[k][0] && t < T[k][1]) ?? 'brand';
  const [a] = T[key];
  const k = ease.outCubic(prog(t, a, a + 0.8));
  const showTicket = key === 'intro' || key === 'hero' || key === 'brand';
  return (
    <AbsoluteFill style={{background: BG[key], transform: `scale(${mix(1.12, 1, k)})`}}>
      {showTicket && (
        <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', top: key === 'brand' ? -380 : 80}}>
          <CssTicket rot={mix(-60, 0, k) + Math.sin(t) * 8} scale={key === 'brand' ? 0.5 : 0.9 * k} label={key === 'hero' ? 'PASS' : 'PASS'} />
        </AbsoluteFill>
      )}
      {(key === 'intro' || key === 'hero' || key === 'brand') && (
        <AbsoluteFill style={{alignItems: 'center', justifyContent: key === 'brand' ? 'center' : 'flex-start', paddingTop: key === 'intro' ? 1380 : 300}}>
          {(key === 'intro' ? BRAND.copy.intro : key === 'hero' ? BRAND.copy.hero.lines : [BRAND.name]).map((l, i) => (
            <div key={i} style={{fontFamily: 'WDisplay', fontSize: key === 'brand' ? 150 : 96, color: i ? C.gold : '#fff', opacity: ease.outCubic(prog(t, a + 0.3 + i * 0.1, a + 1 + i * 0.1)), textAlign: 'center'}}>{l}</div>
          ))}
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  );
};
