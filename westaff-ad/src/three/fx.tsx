import React, {useMemo} from 'react';
import * as THREE from 'three';

/** Faisceau volumétrique simulé : cône additif avec atténuation longitudinale et bords doux (fresnel). */
export const beamMaterial = (color: string, opacity = 0.35) =>
  new THREE.ShaderMaterial({
    uniforms: {uColor: {value: new THREE.Color(color)}, uOpacity: {value: opacity}, uLen: {value: 1}},
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
    vertexShader: `
      varying float vL; varying vec3 vN; varying vec3 vV;
      uniform float uLen;
      void main(){ vL = position.z / uLen; vec4 mv = modelViewMatrix*vec4(position,1.0);
        vN = normalize(normalMatrix*normal); vV = normalize(-mv.xyz); gl_Position = projectionMatrix*mv; }`,
    fragmentShader: `
      uniform vec3 uColor; uniform float uOpacity; varying float vL; varying vec3 vN; varying vec3 vV;
      void main(){ float edge = pow(abs(dot(vN, vV)), 2.2);
        float fall = pow(1.0 - clamp(vL,0.0,1.0), 1.6) * smoothstep(0.0, 0.04, vL);
        gl_FragColor = vec4(uColor * edge * fall * uOpacity, 1.0); }`,
  });

export const beamGeometry = (radius: number, length: number) => {
  const g = new THREE.CylinderGeometry(radius * 0.04, radius, length, 48, 1, true);
  g.translate(0, -length / 2, 0);
  g.rotateX(-Math.PI / 2); // apex à l'origine, s'étend vers +Z (compatible lookAt)
  return g;
};

type BeamProps = {position: [number, number, number]; target: [number, number, number]; radius: number; length: number; color: string; opacity?: number};
export const Beam: React.FC<BeamProps> = ({position, target, radius, length, color, opacity = 0.35}) => {
  const geo = useMemo(() => beamGeometry(radius, length), [radius, length]);
  const mat = useMemo(() => { const m = beamMaterial(color, opacity); m.uniforms.uLen.value = length; return m; }, [color, length]);
  mat.uniforms.uOpacity.value = opacity;
  const obj = useMemo(() => new THREE.Object3D(), []);
  obj.position.set(...position); obj.lookAt(new THREE.Vector3(...target));
  return <mesh geometry={geo} material={mat} position={position} quaternion={obj.quaternion} frustumCulled={false} />;
};

/** Particules (sprites doux additifs, taille en perspective). */
export const pointsMaterial = () =>
  new THREE.ShaderMaterial({
    uniforms: {uScale: {value: 900}},
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, vertexColors: true,
    vertexShader: `
      attribute float aSize; attribute float aAlpha; varying vec3 vC; varying float vA; uniform float uScale;
      void main(){ vC = color; vA = aAlpha; vec4 mv = modelViewMatrix*vec4(position,1.0);
        gl_PointSize = aSize * uScale / max(0.1, -mv.z); gl_Position = projectionMatrix*mv; }`,
    fragmentShader: `
      varying vec3 vC; varying float vA;
      void main(){ float d = length(gl_PointCoord-0.5); float a = smoothstep(0.5,0.0,d); a = a*a + smoothstep(0.12,0.0,d)*0.8;
        gl_FragColor = vec4(vC*a*vA, 1.0); }`,
  });

/** Dôme de ciel dégradé (horizon lumineux). */
export const SkyDome: React.FC<{top: string; horizon: string; glow?: string; radius?: number}> = ({top, horizon, glow = '#000000', radius = 900}) => {
  const mat = useMemo(() => new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false, fog: false,
    uniforms: {uTop: {value: new THREE.Color(top)}, uHor: {value: new THREE.Color(horizon)}, uGlow: {value: new THREE.Color(glow)}},
    vertexShader: `varying vec3 vP; void main(){ vP = normalize(position); gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0);} `,
    fragmentShader: `uniform vec3 uTop,uHor,uGlow; varying vec3 vP;
      void main(){ float h = clamp(vP.y,0.0,1.0); vec3 c = mix(uHor, uTop, pow(h,0.45)); c += uGlow*exp(-h*9.0);
        gl_FragColor = vec4(c,1.0); }`,
  }), [top, horizon, glow]);
  return <mesh material={mat} renderOrder={-10}><sphereGeometry args={[radius, 32, 16]} /></mesh>;
};

/** Texture de halo radial réutilisable (sprites lumineux). */
let glowTex: THREE.CanvasTexture | null = null;
export const glowTexture = () => {
  if (glowTex) return glowTex;
  const c = document.createElement('canvas'); c.width = c.height = 256;
  const g = c.getContext('2d')!; const gr = g.createRadialGradient(128, 128, 0, 128, 128, 128);
  gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(0.15, 'rgba(255,255,255,0.55)'); gr.addColorStop(0.45, 'rgba(255,255,255,0.12)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = gr; g.fillRect(0, 0, 256, 256);
  glowTex = new THREE.CanvasTexture(c); return glowTex;
};
export const Glow: React.FC<{position: [number, number, number]; scale: number; color: string; opacity?: number}> = ({position, scale, color, opacity = 1}) => (
  <sprite position={position} scale={[scale, scale, 1]}>
    <spriteMaterial map={glowTexture()} color={color} transparent opacity={opacity} blending={THREE.AdditiveBlending} depthWrite={false} />
  </sprite>
);
