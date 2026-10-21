import React from 'react';
import {AbsoluteFill, Audio, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {ThreeCanvas} from '@remotion/three';
import * as THREE from 'three';
import {useFonts} from '../three/fonts';
import {ReleaseWorld, CUTS, IMPACTS} from './ReleaseWorld';
import {REL, SH} from './config';
import {ease, prog} from '../lib/anim';

/** Teaser vertical « nouveau son » en 3D isométrique (caméra orthographique). */
export const Release: React.FC<{withAudio: boolean}> = ({withAudio}) => {
  const {width, height, fps} = useVideoConfig();
  const t = useCurrentFrame() / fps;
  const fonts = useFonts();
  const flash = CUTS.reduce((a, b) => Math.max(a, Math.exp(-Math.pow((t - b) / (t < b ? 0.04 : 0.1), 2))), 0);
  const plat = ease.outCubic(prog(t, SH.E[0] + 1.35, SH.E[0] + 1.9));
  const fadeOut = prog(t, REL.video.seconds - 0.5, REL.video.seconds);
  return (
    <AbsoluteFill style={{background: REL.colors.bg}}>
      {fonts && (
        <ThreeCanvas width={width} height={height} frameloop="never" dpr={1} orthographic
          gl={{antialias: false, preserveDrawingBuffer: true, toneMapping: THREE.NoToneMapping, outputColorSpace: THREE.SRGBColorSpace}}
          camera={{zoom: 100, position: [20, 20, 20], near: 0.1, far: 200}}>
          <ReleaseWorld fonts={fonts} />
        </ThreeCanvas>
      )}
      {/* plateformes d'écoute (2D, lisibilité maximale) */}
      {fonts && t > SH.E[0] && (
        <div style={{position: 'absolute', left: 0, right: 0, top: 1405, textAlign: 'center', opacity: plat, transform: `translateY(${(1 - plat) * 20}px)`,
          fontFamily: 'WSemi', fontSize: 34, letterSpacing: '0.04em', color: 'rgba(244,241,236,0.9)', textShadow: '0 4px 20px rgba(0,0,0,0.8)'}}>
          {REL.platforms.split('•').map((p, i, a) => <span key={i}>{p.trim()}{i < a.length - 1 && <span style={{color: REL.colors.red, margin: '0 16px'}}>•</span>}</span>)}
        </div>
      )}
      <AbsoluteFill style={{mixBlendMode: 'plus-lighter' as any, background: 'radial-gradient(circle at 50% 45%, rgba(255,240,230,1), rgba(208,20,31,0.6) 40%, rgba(0,0,0,0) 80%)', opacity: flash * 0.9}} />
      {/* flare anamorphique rouge sur les impacts (inspiré des références) */}
      {IMPACTS.map((at, i) => {
        const k = Math.exp(-Math.pow((t - at) / (t < at ? 0.03 : 0.16), 2));
        if (k < 0.01) return null;
        return (
          <AbsoluteFill key={i} style={{mixBlendMode: 'plus-lighter' as any}}>
            <div style={{position: 'absolute', left: '-20%', right: '-20%', top: 860 + i * 37, height: 10 + 40 * k, opacity: k,
              background: 'radial-gradient(ellipse at center, rgba(255,245,240,1) 0%, rgba(255,60,60,0.9) 18%, rgba(208,20,31,0.5) 45%, rgba(0,0,0,0) 72%)', filter: 'blur(3px)'}} />
            <div style={{position: 'absolute', left: '42%', top: 820 + i * 37, width: '16%', height: 120, opacity: k * 0.8,
              background: 'radial-gradient(circle, rgba(255,255,255,1) 0%, rgba(255,80,80,0.5) 35%, rgba(0,0,0,0) 70%)'}} />
          </AbsoluteFill>
        );
      })}
      <AbsoluteFill style={{background: '#000', opacity: fadeOut}} />
      {withAudio && <Audio src={staticFile(REL.audio)} />}
    </AbsoluteFill>
  );
};
