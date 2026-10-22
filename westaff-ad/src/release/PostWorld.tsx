import React, {useEffect, useMemo} from 'react';
import * as THREE from 'three';
import {useThree} from '@react-three/fiber';
import {useCurrentFrame, useVideoConfig, delayRender, continueRender} from 'remotion';
import {EffectComposer, Bloom, Noise, SMAA, Vignette} from '@react-three/postprocessing';
import {BlendFunction} from 'postprocessing';
import {RadialBlurEffect} from '../three/RadialBlur';
import {pending, frameTexture, setFrame} from './frames';
import {GradeGlitchEffect} from './GradeGlitch';
import {LensFXEffect} from './LensFX';
import {CUTS, IMPACTS, SHOT_T, near, glitchAmount} from './ReleaseWorld';

/**
 * Post-production de la version photoréaliste : chaque image Cycles (public/npng_pr) est affichée plein cadre,
 * puis passe par la même chaîne d'effets que la version temps réel (flou radial, fisheye, glitch, étalonnage rouge & noir, bloom).
 */
const Driver: React.FC = () => {
  const frame = useCurrentFrame(); const {fps} = useVideoConfig();
  const advance = useThree((s) => s.advance);
  const handle = useMemo(() => delayRender(`post ${frame}`), [frame]);
  useEffect(() => { Promise.all(pending.splice(0)).then(() => { advance((frame / fps) * 1000); requestAnimationFrame(() => continueRender(handle)); }); }, [frame, fps, advance, handle]);
  return null;
};

export const PostWorld: React.FC = () => {
  const frame = useCurrentFrame(); const {fps, width, height} = useVideoConfig();
  const t = frame / fps;
  const tex = useMemo(() => frameTexture(), []);
  setFrame(tex, 'npng_pr', frame, 4);
  const fx = useMemo(() => ({blur: new RadialBlurEffect(), grade: new GradeGlitchEffect(), lens: new LensFXEffect()}), []);
  const punch = near(t, IMPACTS, 0.09), whip = near(t, SHOT_T, 0.09), tr = near(t, CUTS, 0.07);
  fx.blur.set(Math.max(tr * 0.18, whip * 0.14), 1 + tr * 0.9);
  fx.grade.set(glitchAmount(t), Math.floor(t * 30));
  fx.grade.mode(true, 0.7);
  fx.lens.set(0.14 + punch * 0.2 + whip * 0.1, 0.016 + punch * 0.03 + tr * 0.04);
  const {scene} = useThree(); scene.background = new THREE.Color('#000');
  return (
    <>
      <mesh><planeGeometry args={[width, height]} /><meshBasicMaterial map={tex} toneMapped={false} /></mesh>
      <EffectComposer multisampling={0} enableNormalPass={false}>
        <SMAA />
        <Bloom mipmapBlur intensity={0.75} luminanceThreshold={0.72} luminanceSmoothing={0.2} radius={0.7} />
        <primitive object={fx.blur} dispose={null} />
        <Vignette offset={0.32} darkness={0.28} />
        <Noise premultiply blendFunction={BlendFunction.SOFT_LIGHT} opacity={0.32} />
        <primitive object={fx.lens} dispose={null} />
        <primitive object={fx.grade} dispose={null} />
      </EffectComposer>
      <Driver />
    </>
  );
};
