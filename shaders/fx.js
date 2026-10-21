// Reusable shader-driven effect objects: gold particle fields, volumetric beams, haze, glints.
import * as THREE from 'three';
import { noiseGLSL } from './noise.glsl.js';

/**
 * GPU particle field. Each particle animates analytically from aFrom -> aTo driven by uMix,
 * with curl-noise drift, a swirl around the Y (or chosen) axis and per-particle delay.
 * Fully deterministic: position is a pure function of uniforms.
 */
export function particleField({ from, to, count, color = '#D6AE57', size = 3, intensity = 3, seed = 1, swirl = 1.5, turbulence = 0.6, axis = 'z' }) {
  const g = new THREE.BufferGeometry();
  const rnd = new Float32Array(count * 4);
  let s = seed >>> 0;
  const R = () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; };
  for (let i = 0; i < count * 4; i++) rnd[i] = R();
  g.setAttribute('position', new THREE.BufferAttribute(from, 3));
  g.setAttribute('aTo', new THREE.BufferAttribute(to, 3));
  g.setAttribute('aRnd', new THREE.BufferAttribute(rnd, 4));
  const mat = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    uniforms: {
      uTime: { value: 0 }, uMix: { value: 0 }, uSize: { value: size }, uPx: { value: 1 },
      uColor: { value: new THREE.Color(color) }, uColor2: { value: new THREE.Color('#fff2cf') },
      uIntensity: { value: intensity }, uSwirl: { value: swirl }, uTurb: { value: turbulence }, uFade: { value: 1 },
      uSpread: { value: 0.35 }, uAxis: { value: axis === 'y' ? 1 : 0 },
    },
    vertexShader: noiseGLSL + /* glsl */ `
      attribute vec3 aTo; attribute vec4 aRnd;
      uniform float uTime, uMix, uSize, uPx, uSwirl, uTurb, uSpread, uAxis;
      varying float vA; varying float vSpark;
      mat2 rot(float a){ float c=cos(a), s=sin(a); return mat2(c,-s,s,c); }
      void main(){
        float d = aRnd.x * uSpread;                       // per-particle stagger
        float k = clamp((uMix - d) / (1.0 - uSpread), 0.0, 1.0);
        float e = k*k*k*(k*(k*6.0-15.0)+10.0);            // smootherstep
        vec3 p = mix(position, aTo, e);
        // swirl: rotate around axis, strongest mid-flight
        float sw = uSwirl * sin(3.14159 * e) * (0.6 + aRnd.y);
        if (uAxis < 0.5) p.xy = rot(sw) * p.xy; else p.xz = rot(sw) * p.xz;
        // coherent turbulence, fades out on arrival
        vec3 c = curl3(p * 0.35 + vec3(0.0, 0.0, uTime * 0.15 + aRnd.z * 0.3));
        p += c * uTurb * pow(1.0 - e, 1.5) * 0.25 + c * 0.012;
        vec4 mv = modelViewMatrix * vec4(p, 1.0);
        gl_Position = projectionMatrix * mv;
        float sz = uSize * (0.45 + aRnd.w * 0.9);
        gl_PointSize = clamp(sz * uPx / max(-mv.z, 0.05), 1.0, 64.0);
        vSpark = pow(0.5 + 0.5 * sin(uTime * (6.0 + aRnd.y * 10.0) + aRnd.z * 40.0), 6.0);
        vA = smoothstep(0.0, 0.08, k + 0.02) * (0.55 + 0.45 * aRnd.y);
      }`,
    fragmentShader: /* glsl */ `
      uniform vec3 uColor, uColor2; uniform float uIntensity, uFade;
      varying float vA; varying float vSpark;
      void main(){
        vec2 q = gl_PointCoord * 2.0 - 1.0;
        float r = dot(q, q);
        if (r > 1.0) discard;
        float core = exp(-r * 7.0);
        float halo = exp(-r * 2.2) * 0.35;
        vec3 c = mix(uColor, uColor2, core * 0.6 + vSpark * 0.4);
        gl_FragColor = vec4(c * (core + halo) * uIntensity * (0.7 + vSpark * 1.6) * vA * uFade, 1.0);
      }`,
  });
  const pts = new THREE.Points(g, mat);
  pts.frustumCulled = false;
  return pts;
}

/**
 * Fake-volumetric light cone: additive shell, brighter where the view ray grazes the beam axis,
 * attenuated along length, broken up by drifting 3D noise (haze). Cheap and very convincing with bloom.
 */
export function beamMaterial({ color = '#ffffff', intensity = 1.5, noise = 0.55, falloff = 1.2 } = {}) {
  return new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
    uniforms: { uColor: { value: new THREE.Color(color) }, uIntensity: { value: intensity }, uTime: { value: 0 }, uNoise: { value: noise }, uFalloff: { value: falloff } },
    vertexShader: /* glsl */ `
      varying vec3 vN; varying vec3 vV; varying float vL; varying vec3 vW;
      void main(){
        vec4 w = modelMatrix * vec4(position, 1.0);
        vW = w.xyz;
        vN = normalize(mat3(modelMatrix) * normal);
        vV = normalize(cameraPosition - w.xyz);
        vL = uv.y; // 1 at apex (light), 0 at far end for ConeGeometry
        gl_Position = projectionMatrix * viewMatrix * w;
      }`,
    fragmentShader: noiseGLSL + /* glsl */ `
      uniform vec3 uColor; uniform float uIntensity, uTime, uNoise, uFalloff;
      varying vec3 vN; varying vec3 vV; varying float vL; varying vec3 vW;
      void main(){
        float edge = pow(abs(dot(normalize(vN), normalize(vV))), 2.2);
        float along = pow(vL, uFalloff);
        float hz = 0.65 + uNoise * fbm3(vW * 0.18 + vec3(0.0, -uTime * 0.25, uTime * 0.1));
        float a = edge * along * hz;
        gl_FragColor = vec4(uColor * a * uIntensity, 1.0);
      }`,
  });
}

// Cone with apex at origin pointing down -Y; length L, radius at far end r. Orient with lookAt helpers.
export function beam(L, r, mat, radial = 48) {
  const geo = new THREE.ConeGeometry(r, L, radial, 1, true);
  geo.translate(0, -L / 2, 0); // apex at origin
  const m = new THREE.Mesh(geo, mat);
  m.renderOrder = 10;
  return m;
}
// Point a beam (apex at its position) toward a world target
export function aimBeam(mesh, target) {
  const dir = new THREE.Vector3().subVectors(target, mesh.position).normalize();
  mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, -1, 0), dir);
}

/** Large drifting haze sheet (camera-facing-ish plane) for atmospheric depth. */
export function hazeMaterial({ color = '#ffffff', intensity = 0.06, scale = 0.25, speed = 0.05 } = {}) {
  return new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
    uniforms: { uColor: { value: new THREE.Color(color) }, uIntensity: { value: intensity }, uTime: { value: 0 }, uScale: { value: scale }, uSpeed: { value: speed } },
    vertexShader: `varying vec3 vW; varying vec2 vUv; void main(){ vUv=uv; vec4 w=modelMatrix*vec4(position,1.0); vW=w.xyz; gl_Position=projectionMatrix*viewMatrix*w; }`,
    fragmentShader: noiseGLSL + `
      uniform vec3 uColor; uniform float uIntensity, uTime, uScale, uSpeed; varying vec3 vW; varying vec2 vUv;
      void main(){
        float n = fbm3(vec3(vW.xy * uScale, uTime * uSpeed) + vec3(uTime*uSpeed, 0.0, 0.0)) * 0.5 + 0.5;
        float edge = smoothstep(0.0, 0.25, vUv.x) * smoothstep(1.0, 0.75, vUv.x) * smoothstep(0.0, 0.25, vUv.y) * smoothstep(1.0, 0.75, vUv.y);
        gl_FragColor = vec4(uColor * n * n * uIntensity * edge, 1.0);
      }`,
  });
}

/** Four-point anamorphic star glint sprite (additive). Animate .material.uniforms.uAmount. */
export function glint({ color = '#fff4d6', size = 1, intensity = 6 } = {}) {
  const mat = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, depthTest: false, blending: THREE.AdditiveBlending,
    uniforms: { uColor: { value: new THREE.Color(color) }, uAmount: { value: 0 }, uIntensity: { value: intensity }, uRot: { value: 0 } },
    vertexShader: `varying vec2 vUv; void main(){ vUv = uv*2.0-1.0; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }`,
    fragmentShader: `
      uniform vec3 uColor; uniform float uAmount, uIntensity, uRot; varying vec2 vUv;
      void main(){
        float c=cos(uRot), s=sin(uRot); vec2 p = mat2(c,-s,s,c)*vUv;
        float core = exp(-dot(p,p)*60.0);
        float h = exp(-abs(p.y)*90.0) * (1.0-smoothstep(0.0,1.0,abs(p.x)));
        float v = exp(-abs(p.x)*90.0) * (1.0-smoothstep(0.0,1.0,abs(p.y))) * 0.6;
        float d = (exp(-abs(p.x-p.y)*140.0) + exp(-abs(p.x+p.y)*140.0)) * (1.0-smoothstep(0.0,0.5,length(p))) * 0.25;
        gl_FragColor = vec4(uColor * (core*2.0 + h + v + d) * uAmount * uIntensity, 1.0);
      }`,
  });
  const m = new THREE.Mesh(new THREE.PlaneGeometry(size, size), mat);
  m.renderOrder = 100;
  return m;
}
