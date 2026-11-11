import React from 'react';
import {AbsoluteFill} from 'remotion';
import {SAFE} from '../brand';
/** Guide de zones de sécurité TikTok/Reels (activable via la prop showSafeZones). */
export const SafeZones: React.FC = () => (
  <AbsoluteFill style={{pointerEvents: 'none'}}>
    <div style={{position: 'absolute', left: SAFE.left, right: SAFE.right, top: SAFE.top, bottom: SAFE.bottom, border: '3px dashed rgba(0,255,140,0.8)'}} />
    <div style={{position: 'absolute', left: 0, right: 0, top: 0, height: SAFE.top, background: 'rgba(255,0,60,0.18)'}} />
    <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: SAFE.bottom, background: 'rgba(255,0,60,0.18)'}} />
    <div style={{position: 'absolute', right: 0, top: SAFE.top, bottom: SAFE.bottom, width: SAFE.right, background: 'rgba(255,0,60,0.12)'}} />
  </AbsoluteFill>
);
