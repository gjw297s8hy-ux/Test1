import React, {useLayoutEffect, useMemo, useRef} from 'react';
import * as THREE from 'three';
import {ticketGeometries, FACE_Z, TICKET} from './ticket';
import {makeTicketArt, makeTicketBack, TicketKind} from './ticketArt';
import {goldBrushed} from './materials';

/** Film holographique : bande irisée balayant la face (additif). */
const holoMaterial = () =>
  new THREE.ShaderMaterial({
    uniforms: {uSweep: {value: -1}, uTime: {value: 0}, uIntensity: {value: 0.6}},
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, clipping: true,
    vertexShader: `
      #include <clipping_planes_pars_vertex>
      varying vec2 vUv;
      void main(){ vUv = uv; vec4 mvPosition = modelViewMatrix * vec4(position,1.0); gl_Position = projectionMatrix * mvPosition;
      #include <clipping_planes_vertex>
      }`,
    fragmentShader: `
      #include <clipping_planes_pars_fragment>
      uniform float uSweep, uTime, uIntensity; varying vec2 vUv;
      void main(){
        #include <clipping_planes_fragment>
        float d = vUv.x*0.55 + vUv.y*0.85 - uSweep;
        float band = exp(-d*d*28.0);
        vec3 rainbow = 0.5 + 0.5*cos(6.2831*(vUv.y*1.7 + vUv.x*0.9 + uTime*0.15 + vec3(0.0,0.33,0.67)));
        float sheen = 0.015 + 0.015*sin(vUv.y*90.0 + uTime*2.0);
        gl_FragColor = vec4(rainbow*(band*1.1 + sheen)*uIntensity, 1.0);
      }`,
  });

export type TicketProps = JSX.IntrinsicElements['group'] & {
  kind: TicketKind; accent?: string; sweep?: number; time?: number; holo?: number;
  /** révélation de bas en haut (0 → 1), utilise des plans de découpe locaux */
  reveal?: number; emissive?: number;
};

export const Ticket: React.FC<TicketProps> = ({kind, accent, sweep = -1, time = 0, holo = 0.6, reveal = 1, emissive = 0.22, ...rest}) => {
  const {body, face} = ticketGeometries();
  const ref = useRef<THREE.Group>(null);
  const plane = useMemo(() => new THREE.Plane(), []);
  const m = useMemo(() => {
    const art = makeTicketArt(kind, accent);
    const front = new THREE.MeshPhysicalMaterial({
      map: art, emissiveMap: art, emissive: new THREE.Color('#ffffff'), emissiveIntensity: emissive,
      metalness: 0.35, roughness: 0.3, clearcoat: 1, clearcoatRoughness: 0.1,
      iridescence: 0.4, iridescenceIOR: 1.3, iridescenceThicknessRange: [200, 500],
    });
    const back = new THREE.MeshPhysicalMaterial({map: makeTicketBack(), metalness: 0.4, roughness: 0.35, clearcoat: 1});
    const edge = goldBrushed();
    const holoM = holoMaterial();
    return {front, back, edge, holoM};
  }, [kind, accent]);
  m.front.emissiveIntensity = emissive;
  m.holoM.uniforms.uSweep.value = sweep;
  m.holoM.uniforms.uTime.value = time;
  m.holoM.uniforms.uIntensity.value = holo;

  useLayoutEffect(() => {
    const g = ref.current; if (!g) return;
    const mats = [m.front, m.back, m.edge, m.holoM];
    if (reveal >= 1) { mats.forEach((x) => (x.clippingPlanes = null)); return; }
    g.updateWorldMatrix(true, false);
    const y = -TICKET.h / 2 - 0.05 + (TICKET.h + 0.1) * reveal;
    plane.set(new THREE.Vector3(0, -1, 0), y).applyMatrix4(g.matrixWorld);
    mats.forEach((x) => (x.clippingPlanes = [plane]));
  });

  return (
    <group ref={ref} {...rest}>
      <mesh geometry={body} material={[m.back, m.edge]} />
      <mesh geometry={face} material={m.front} position-z={FACE_Z} />
      <mesh geometry={face} material={m.holoM} position-z={FACE_Z + 0.0015} />
    </group>
  );
};
