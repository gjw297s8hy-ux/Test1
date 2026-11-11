import React, {useMemo} from 'react';
import {AbsoluteFill, Audio, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {ThreeCanvas} from '@remotion/three';
import * as THREE from 'three';
import {useFonts} from './three/fonts';
import {World} from './three/World';
import {Overlays} from './overlay/Overlays';
import {Fallback2D} from './overlay/Fallback2D';
import {SafeZones} from './overlay/SafeZones';

export type AdProps = {showSafeZones: boolean; forceFallback: boolean; withAudio: boolean};

const hasWebGL = () => {
  try { const c = document.createElement('canvas'); return !!(c.getContext('webgl2') || c.getContext('webgl')); } catch { return false; }
};

export const Ad: React.FC<AdProps> = ({showSafeZones, forceFallback, withAudio}) => {
  const {width, height, fps} = useVideoConfig();
  const frame = useCurrentFrame();
  const fonts = useFonts();
  const webgl = useMemo(() => !forceFallback && hasWebGL(), [forceFallback]);
  return (
    <AbsoluteFill style={{background: '#020205'}}>
      {webgl ? (
        fonts && (
          <ThreeCanvas width={width} height={height} frameloop="never" dpr={1}
            gl={{antialias: false, preserveDrawingBuffer: true, powerPreference: 'high-performance', toneMapping: THREE.NoToneMapping, outputColorSpace: THREE.SRGBColorSpace}}
            camera={{fov: 35, position: [0, 0, 8]}}>
            <World fonts={fonts} />
          </ThreeCanvas>
        )
      ) : (
        <Fallback2D />
      )}
      {fonts && <Overlays />}
      {withAudio && <Audio src={staticFile('audio/soundtrack.wav')} />}
      {showSafeZones && <SafeZones />}
    </AbsoluteFill>
  );
};
