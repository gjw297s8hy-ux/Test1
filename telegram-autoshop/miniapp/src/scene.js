// Real-time 3D backdrop: a tropical ocean at sunset.
// Source for ../scene.js - rebuild with:  npx esbuild src/scene.js --bundle --minify --format=iife --outfile=scene.js
import {
  ACESFilmicToneMapping, MathUtils, PerspectiveCamera, PlaneGeometry, RepeatWrapping, Scene,
  TextureLoader, Vector3, WebGLRenderer,
} from 'three';
import { Sky } from 'three/addons/objects/Sky.js';
import { Water } from 'three/addons/objects/Water.js';

function startScene(canvas, normalsUrl) {
  const renderer = new WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
  // Phones have dense screens; rendering every physical pixel costs battery for no visible gain.
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
  renderer.toneMapping = ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.36;

  const scene = new Scene();
  const camera = new PerspectiveCamera(58, 1, 1, 20000);

  // Low sun, straight ahead: long warm reflection across the water.
  const sun = new Vector3().setFromSphericalCoords(1, MathUtils.degToRad(90 - 1.6), MathUtils.degToRad(180));

  const sky = new Sky();
  sky.scale.setScalar(10000);
  const su = sky.material.uniforms;
  su.turbidity.value = 10;
  su.rayleigh.value = 3.4;
  su.mieCoefficient.value = 0.004;
  su.mieDirectionalG.value = 0.92;
  su.sunPosition.value.copy(sun);
  scene.add(sky);

  const normals = new TextureLoader().load(normalsUrl, (t) => { t.wrapS = t.wrapT = RepeatWrapping; });
  const water = new Water(new PlaneGeometry(10000, 10000), {
    textureWidth: 512,
    textureHeight: 512,
    waterNormals: normals,
    sunDirection: sun.clone(),
    sunColor: 0xfff1d6,
    waterColor: 0x0b7285, // lagoon teal rather than open-sea navy
    distortionScale: 3.2,
    fog: false,
  });
  water.rotation.x = -Math.PI / 2;
  scene.add(water);

  function resize() {
    const w = canvas.clientWidth || window.innerWidth;
    const h = canvas.clientHeight || window.innerHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  window.addEventListener('resize', resize);
  resize();

  const calm = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let running = true;
  let scroll = 0;
  document.addEventListener('visibilitychange', () => { running = !document.hidden; if (running) requestAnimationFrame(frame); });

  function frame(ms) {
    if (!running) return;
    const t = ms / 1000;
    // Gentle swell, as if standing in the shallows; the view dips slightly as the page scrolls.
    camera.position.set(Math.sin(t * 0.11) * 6, 9 + Math.sin(t * 0.5) * 0.6, 110);
    // Looking down a little puts the horizon, and the sun, just under the shop title.
    camera.lookAt(Math.sin(t * 0.07) * 10, -150 - scroll * 30, -400);
    water.material.uniforms.time.value = t * 0.55;
    renderer.render(scene, camera);
    if (!calm) requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);

  return { setScroll(v) { scroll = Math.max(0, Math.min(1, v)); if (calm) requestAnimationFrame(frame); } };
}

window.startScene = startScene;
