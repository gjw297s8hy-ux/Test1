import React, {useEffect, useMemo} from 'react';
import * as THREE from 'three';
import {useThree} from '@react-three/fiber';
import {useCurrentFrame, useVideoConfig, delayRender, continueRender} from 'remotion';
import {RoomEnvironment} from 'three/examples/jsm/environments/RoomEnvironment.js';
import {EffectComposer, Bloom, Vignette, ChromaticAberration, Noise, ToneMapping, SMAA} from '@react-three/postprocessing';
import {ToneMappingMode, BlendFunction} from 'postprocessing';
import {T} from '../brand';
import {RadialBlurEffect} from './RadialBlur';
import {transitionAmount} from '../overlay/Overlays';
import type {Fonts, CamState, SceneLook} from '../scenes/types';
import {Intro, introCamera, introLook} from '../scenes/Intro';
import {Stadium, stadiumCamera, stadiumLook} from '../scenes/Stadium';
import {Concert, concertCamera, concertLook} from '../scenes/Concert';
import {Theatre, theatreCamera, theatreLook} from '../scenes/Theatre';
import {Hero, heroCamera, heroLook} from '../scenes/Hero';
import {BrandScene, brandCamera, brandLook} from '../scenes/Brand';

type Def = {key: keyof typeof T; C: React.FC<{t: number; fonts: Fonts}>; cam: (t: number) => CamState; look: SceneLook};
const SCENES: Def[] = [
  {key: 'intro', C: Intro, cam: introCamera, look: introLook},
  {key: 'stadium', C: Stadium, cam: stadiumCamera, look: stadiumLook},
  {key: 'concert', C: Concert, cam: concertCamera, look: concertLook},
  {key: 'theatre', C: Theatre, cam: theatreCamera, look: theatreLook},
  {key: 'hero', C: Hero, cam: heroCamera, look: heroLook},
  {key: 'brand', C: BrandScene, cam: brandCamera, look: brandLook},
];

/** Rendu déterministe : un seul rendu WebGL par frame Remotion, déclenché après la mise à jour de la scène. */
const FrameDriver: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const advance = useThree((s) => s.advance);
  const handle = useMemo(() => delayRender(`webgl frame ${frame}`), [frame]);
  useEffect(() => {
    advance((frame / fps) * 1000);
    requestAnimationFrame(() => continueRender(handle));
  }, [frame, fps, advance, handle]);
  return null;
};

export const World: React.FC<{fonts: Fonts}> = ({fonts}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const {camera, scene, gl} = useThree();

  useMemo(() => {
    const pm = new THREE.PMREMGenerator(gl);
    scene.environment = pm.fromScene(new RoomEnvironment(), 0.04).texture;
    gl.localClippingEnabled = true;
  }, [gl, scene]);

  const def = SCENES.find((s) => t >= T[s.key][0] && t < T[s.key][1]) ?? SCENES[SCENES.length - 1];
  const local = t; // les scènes reçoivent le temps global (secondes)
  const c = def.cam(local);
  const cam = camera as THREE.PerspectiveCamera;
  cam.position.set(...c.pos);
  cam.up.set(Math.sin(c.roll ?? 0), Math.cos(c.roll ?? 0), 0);
  cam.lookAt(...c.target);
  cam.fov = c.fov; cam.near = 0.05; cam.far = 2000; cam.updateProjectionMatrix();
  scene.background = new THREE.Color(def.look.background);
  scene.fog = def.look.fog ? new THREE.FogExp2(def.look.fog.color, def.look.fog.density) : null;
  (scene as any).environmentIntensity = def.look.env;
  gl.toneMappingExposure = def.look.exposure;

  const blur = useMemo(() => new RadialBlurEffect(), []);
  const tr = transitionAmount(t);
  blur.set(tr * 0.22, 1 + tr * 1.4);
  const S = def.C;
  return (
    <>
      <S t={local} fonts={fonts} />
      <EffectComposer multisampling={0} enableNormalPass={false}>
        <SMAA />
        <Bloom mipmapBlur intensity={def.look.bloom} luminanceThreshold={0.62} luminanceSmoothing={0.25} radius={0.75} />
        <ChromaticAberration offset={new THREE.Vector2(0.0007, 0.0005)} radialModulation modulationOffset={0.4} />
        <primitive object={blur} dispose={null} />
        <Vignette offset={0.28} darkness={0.72} />
        <Noise premultiply blendFunction={BlendFunction.SOFT_LIGHT} opacity={0.35} />
        <ToneMapping mode={ToneMappingMode.ACES_FILMIC} />
      </EffectComposer>
      <FrameDriver />
    </>
  );
};
