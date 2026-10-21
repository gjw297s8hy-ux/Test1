import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {BRAND, SAFE, legacyTime} from '../brand';
import {ease, prog, mix, clamp} from '../lib/anim';

const C = BRAND.colors;
const goldText: React.CSSProperties = {
  background: `linear-gradient(100deg, ${C.goldDeep} 0%, ${C.goldLight} 30%, ${C.gold} 50%, #fff3cf 62%, ${C.goldDeep} 100%)`,
  backgroundSize: '220% 100%', WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent',
};

/** Ligne révélée par masque (glisse depuis le bas, flou → net), sortie vers le haut. */
const MaskLine: React.FC<{t: number; t0: number; t1: number; i: number; children: React.ReactNode; style?: React.CSSProperties; gold?: boolean}> = ({t, t0, t1, i, children, style, gold}) => {
  const k = ease.outQuint(prog(t, t0 + i * 0.09, t0 + 0.75 + i * 0.09));
  const o = ease.inCubic(prog(t, t1 + i * 0.05, t1 + 0.35 + i * 0.05));
  const shine = mix(120, -40, prog(t, t0 + 0.4, t0 + 1.9));
  return (
    <div style={{overflow: 'hidden', paddingBottom: 6}}>
      <div style={{
        transform: `translateY(${(1 - k) * 105 - o * 105}%) skewY(${(1 - k) * 4}deg)`, filter: `blur(${(1 - k) * 10 + o * 8}px)`, opacity: clamp(k * 1.5) * (1 - o),
        ...(gold ? {...goldText, backgroundPosition: `${shine}% 0`} : {color: C.white}), ...style,
      }}>{children}</div>
    </div>
  );
};

const Eyebrow: React.FC<{t: number; t0: number; t1: number; text: string}> = ({t, t0, t1, text}) => {
  const k = ease.outCubic(prog(t, t0, t0 + 0.6)), o = prog(t, t1, t1 + 0.3);
  return (
    <div style={{display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 22, opacity: k * (1 - o), marginBottom: 18}}>
      <div style={{height: 2, width: 70 * k, background: `linear-gradient(90deg, transparent, ${C.gold})`}} />
      <div style={{fontFamily: 'WBold', fontSize: 28, letterSpacing: `${mix(0.9, 0.5, k)}em`, color: C.gold, paddingLeft: '0.5em'}}>{text}</div>
      <div style={{height: 2, width: 70 * k, background: `linear-gradient(90deg, ${C.gold}, transparent)`}} />
    </div>
  );
};

const titleStyle: React.CSSProperties = {fontFamily: 'WDisplay', fontSize: 98, lineHeight: 0.98, letterSpacing: '-0.012em', textAlign: 'center', textShadow: '0 8px 40px rgba(0,0,0,0.55)'};

const SceneTitle: React.FC<{t: number; t0: number; t1: number; eyebrow: string; lines: string[]; top: number}> = ({t, t0, t1, eyebrow, lines, top}) => {
  if (t < t0 - 0.05 || t > t1 + 0.8) return null;
  const glow = ease.outCubic(prog(t, t0, t0 + 0.8)) * (1 - prog(t, t1, t1 + 0.4));
  return (
    <div style={{position: 'absolute', left: SAFE.left, right: SAFE.left, top, display: 'flex', flexDirection: 'column', alignItems: 'center'}}>
      <div style={{position: 'absolute', inset: '-90px -60px', background: 'radial-gradient(ellipse at center, rgba(0,0,0,0.55), transparent 70%)', opacity: glow}} />
      <Eyebrow t={t} t0={t0} t1={t1} text={eyebrow} />
      {lines.map((l, i) => <MaskLine key={i} t={t} t0={t0 + 0.12} t1={t1} i={i} gold={i === 1} style={titleStyle}>{l}</MaskLine>)}
    </div>
  );
};

/** Flash lumineux de transition (raccord masqué sur un pic de lumière). */
const Flash: React.FC<{t: number; at: number; color: string; width?: number; strength?: number}> = ({t, at, color, width = 0.06, strength = 1}) => {
  // montée rapide, retombée plus lente (asymétrique, comme une surexposition caméra)
  const d = t - at;
  const k = Math.exp(-Math.pow(d / (d < 0 ? width : width * 2.2), 2)) * strength;
  if (k < 0.003) return null;
  const r = 30 + (1 - k) * 60;
  return (
    <AbsoluteFill style={{mixBlendMode: 'plus-lighter' as any}}>
      <AbsoluteFill style={{background: `radial-gradient(circle at 50% 45%, rgba(255,250,240,1) 0%, ${color} ${r}%, rgba(0,0,0,0) ${r + 45}%)`, opacity: k}} />
    </AbsoluteFill>
  );
};

export const TRANSITIONS = [4.0, 9.0, 14.0, 19.0, 23.0, 29.0];
/** Intensité de transition (pour flou de mouvement / zoom du canvas 3D). */
export const transitionAmount = (t: number) => TRANSITIONS.reduce((a, b) => Math.max(a, Math.exp(-Math.pow((t - b) / 0.075, 2))), 0);

export const Overlays: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const real = frame / fps;
  const t = legacyTime(real); // textes historiques (−1 pendant la scène insérée)
  const cp = BRAND.copy;
  // CTA
  const cta1 = t >= 25.2 && t < 27.9;
  const pill = ease.outBack(prog(t, 27.65, 28.25));
  const pulse = 1 + Math.sin(Math.max(0, t - 28.3) * 5) * 0.015 * prog(t, 28.3, 28.6);
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <SceneTitle t={t} t0={4.55} t1={8.45} eyebrow={cp.stadium.eyebrow} lines={cp.stadium.lines} top={300} />
      <SceneTitle t={real} t0={9.2} t1={11.25} eyebrow={cp.leagues.eyebrow} lines={cp.leagues.lines} top={290} />
      <SceneTitle t={t} t0={9.55} t1={13.45} eyebrow={cp.concert.eyebrow} lines={cp.concert.lines} top={1150} />
      <SceneTitle t={t} t0={14.75} t1={17.45} eyebrow={cp.theatre.eyebrow} lines={cp.theatre.lines} top={290} />
      {/* sous-texte du hero */}
      {t > 19.4 && t < 23.9 && (
        <div style={{position: 'absolute', left: 0, right: 0, top: 600, display: 'flex', justifyContent: 'center'}}>
          <div style={{
            fontFamily: 'WSemi', fontSize: 38, letterSpacing: '0.06em', color: 'rgba(245,242,234,0.92)', textShadow: '0 4px 24px rgba(0,0,0,0.7)',
            opacity: ease.outCubic(prog(t, 19.5, 20.1)) * (1 - prog(t, 23.3, 23.7)), transform: `translateY(${(1 - ease.outCubic(prog(t, 19.5, 20.1))) * 24}px)`,
            filter: `blur(${(1 - prog(t, 19.5, 20.0)) * 6}px)`,
          }}>
            {cp.hero.sub.split('•').map((w, i, a) => (
              <span key={i}>{w.trim()}{i < a.length - 1 && <span style={{color: C.gold, margin: '0 18px'}}>•</span>}</span>
            ))}
          </div>
        </div>
      )}
      {/* CTA 1 */}
      {cta1 && (
        <div style={{position: 'absolute', left: SAFE.left, right: SAFE.left, top: 1210, display: 'flex', flexDirection: 'column', alignItems: 'center'}}>
          {cp.cta1.map((l, i) => <MaskLine key={i} t={t} t0={25.25} t1={27.45} i={i} gold={i === 1} style={{...titleStyle, fontSize: 72}}>{l}</MaskLine>)}
        </div>
      )}
      {/* CTA 2 : contact */}
      {t >= 27.55 && (
        <div style={{position: 'absolute', left: 0, right: 0, top: 1215, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 26}}>
          <div style={{fontFamily: 'WBold', fontSize: 32, letterSpacing: '0.55em', paddingLeft: '0.55em', color: C.gold, opacity: ease.outCubic(prog(t, 27.6, 28.1))}}>{cp.cta2}</div>
          <div style={{
            transform: `scale(${Math.max(0, pill) * pulse})`, padding: '22px 52px', borderRadius: 999,
            background: 'linear-gradient(180deg, rgba(20,16,10,0.85), rgba(5,5,8,0.85))',
            boxShadow: `0 0 0 2.5px ${C.gold}, 0 0 ${30 + 20 * Math.sin(t * 4)}px rgba(232,185,100,0.45), inset 0 0 30px rgba(232,185,100,0.18)`,
          }}>
            <div style={{fontFamily: 'WDisplay', fontSize: 60, letterSpacing: '0.01em', color: C.white}}>{BRAND.handle}</div>
          </div>
        </div>
      )}
      <Flash t={real} at={4.0} color="rgba(232,185,100,0.55)" />
      <Flash t={real} at={9.0} color="rgba(120,160,255,0.55)" />
      <Flash t={real} at={14.0} color="rgba(120,160,255,0.55)" />
      <Flash t={real} at={19.0} color="rgba(155,61,255,0.55)" />
      <Flash t={real} at={23.0} color="rgba(232,185,100,0.5)" width={0.08} />
      <Flash t={real} at={29.0} color="rgba(232,185,100,0.6)" width={0.13} />
    </AbsoluteFill>
  );
};
