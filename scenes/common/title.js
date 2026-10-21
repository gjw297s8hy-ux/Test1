// Shared kinetic typography: real extruded metal letters, camera-parented so layout respects the
// 9:16 safe zones exactly, lit by the dedicated title environment so they always read.
import * as THREE from 'three';
import { loadFont, text3D, titleEnv, remap, settle, clamp, smoother } from '../../src/engine/lib.js';
import { gold, brushedSilver } from '../../materials/materials.js';

export const TITLE_GOLD = '#EBC777';

/**
 * lines: [{ text, font: 'cinzel-700', size, tracking, y, depth? }]
 * opts: { dist, material: 'gold'|'silver' }
 * Sizes and y are in "frame units": 1.0 = full visible frame height at `dist`, so a layout is
 * lens-independent. y = 0 is frame centre, +0.5 top edge.
 */
export async function makeTitle(ctx, camera, lines, { dist = 4, material = 'gold', fov = null, scrimOpacity = 0.55 } = {}) {
  const env = titleEnv(ctx.renderer);
  const face = material === 'gold' ? gold({ roughness: 0.3, color: TITLE_GOLD }) : brushedSilver({ roughness: 0.28 });
  const side = gold({ roughness: 0.1, color: TITLE_GOLD });
  face.envMap = side.envMap = env;
  const group = new THREE.Group();
  group.position.set(0, 0, -dist);
  camera.add(group);
  const frameH = () => 2 * dist * Math.tan(THREE.MathUtils.degToRad((fov || camera.fov) / 2));
  const H = frameH();
  const letters = [];
  const blocks = [];
  for (const [li, L] of lines.entries()) {
    const font = await loadFont(L.font || 'cinzel-700');
    const size = L.size * H;
    const t = text3D(L.text, font, { size, depth: size * (L.depth ?? 0.22), bevel: size * 0.032, tracking: L.tracking ?? 0.08, materials: [face, side] });
    t.group.position.y = L.y * H;
    group.add(t.group);
    const maxW = H * camera.aspect * (L.maxWidth ?? 0.86);
    if (t.width > maxW) { const k = maxW / t.width; t.group.scale.setScalar(k); }
    blocks.push(t);
    t.letters.forEach((m, i) => {
      m.material = m.material.map((x) => { const c = x.clone(); c.transparent = true; return c; });
      letters.push({ m, line: li, i, n: t.letters.length, delay: (L.delay ?? li * 0.14) + i * (L.stagger ?? 0.025) });
    });
  }
  // soft radial scrim behind the block: keeps titles readable over bright plates
  const scrimMat = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, depthTest: false,
    uniforms: { uA: { value: 0 } },
    vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); }',
    fragmentShader: 'uniform float uA; varying vec2 vUv; void main(){ vec2 q = (vUv-0.5)*vec2(1.0,2.2); float a = exp(-dot(q,q)*3.5); gl_FragColor = vec4(0.0,0.0,0.0, a*uA); }',
  });
  const ys = lines.map((L) => L.y * H);
  const scrim = new THREE.Mesh(new THREE.PlaneGeometry(H * camera.aspect * 1.6, (Math.max(...ys) - Math.min(...ys)) + H * 0.32), scrimMat);
  scrim.position.set(0, (Math.max(...ys) + Math.min(...ys)) / 2, -0.05);
  scrim.renderOrder = -1;
  group.add(scrim);
  const scrimMax = scrimOpacity;
  const light = new THREE.PointLight('#fff0d0', 0, dist * 2, 2);
  light.position.set(H * 0.3, 0, -dist * 0.8);
  camera.add(light);

  /** style: rise | slide | flip | zoom ; tin: start time ; tout: optional exit start */
  function update(t, tin, style = 'rise', tout = null, dur = 0.55) {
    group.visible = t > tin - 0.01;
    letters.forEach(({ m, delay, i, n, line }) => {
      const k = remap(t, tin + delay, tin + delay + dur);
      const e = settle(k);
      const b = m.userData.base;
      const inv = 1 - e;
      let x = b.x, y = b.y, z = b.z, rx = 0, ry = 0, s = 1;
      if (style === 'rise') { y -= inv * size0(m) * 0.6; z -= inv * dist * 0.35; rx = inv * 1.1; }
      else if (style === 'slide') { x += inv * (line % 2 ? -1 : 1) * size0(m) * 6; ry = inv * (line % 2 ? 0.9 : -0.9); z -= inv * 0.2; }
      else if (style === 'flip') { rx = -inv * Math.PI * 0.5; y += inv * size0(m) * 0.3; }
      else if (style === 'zoom') { z += inv * dist * 0.5; s = 1 + inv * 0.6; }
      let a = clamp(k * 2.2);
      if (tout !== null) {
        const o = smoother(remap(t, tout + (n - i) * 0.01, tout + 0.35 + (n - i) * 0.01));
        a *= 1 - o; z += o * dist * 0.25; y += o * size0(m) * 0.4;
      }
      m.visible = a > 0.002;
      m.position.set(x, y, z);
      m.rotation.set(rx, ry, 0);
      m.scale.setScalar(s);
      m.material.forEach((mm) => (mm.opacity = a));
    });
    light.intensity = 5 * remap(t, tin, tin + 0.4);
    scrimMat.uniforms.uA.value = scrimMax * remap(t, tin - 0.2, tin + 0.4) * (tout !== null ? 1 - remap(t, tout, tout + 0.5) : 1);
  }
  function size0(m) { return m.geometry.boundingBox ? (m.geometry.boundingBox.max.y - m.geometry.boundingBox.min.y) : 0.2; }
  letters.forEach(({ m }) => m.geometry.computeBoundingBox());
  group.traverse((o) => o.layers.set(1));
  light.layers.enableAll();
  return { group, letters, blocks, update, frameH: H };
}
