// Deterministic frame engine. Every frame is a pure function of its index: no wall-clock time.
import * as THREE from 'three';
import { Post } from '/shaders/post.js';

const P = new URLSearchParams(location.search);
const E = (window.ENGINE = { ready: false, error: null });
try {
  const config = await (await fetch('/config/config.json')).json();
  const q = { ...config.quality[P.get('q') || 'draft'] };
  if (P.get('w')) { q.width = +P.get('w'); q.height = +P.get('h'); }
  if (P.get('fps')) q.fps = +P.get('fps');
  if (P.get('mb')) q.motionBlurSamples = +P.get('mb');
  const W = q.width, H = q.height;
  const canvas = document.getElementById('c');
  canvas.width = W; canvas.height = H;
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, preserveDrawingBuffer: true, alpha: false, powerPreference: 'high-performance' });
  renderer.setPixelRatio(1);
  renderer.setSize(W, H, false);
  renderer.toneMapping = THREE.NoToneMapping;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  const fx = config.effects;
  const post = new Post(renderer, W, H, q, fx);

  const defs = config.timing.scenes;
  const wanted = P.get('scenes') ? P.get('scenes').split(',') : defs.map((d) => d.id);
  const ctx = { THREE, renderer, config, q, W, H, aspect: W / H };
  // world-units -> pixels factor for point sprites
  ctx.pxScale = (cam) => H / (2 * Math.tan(THREE.MathUtils.degToRad(cam.fov / 2)));
  const scenes = {};
  for (const d of defs) {
    if (!wanted.includes(d.id)) continue;
    let s;
    try {
      const mod = await import(`/scenes/${d.module}`);
      s = await mod.create(ctx);
    } catch (e) {
      if (!String(e).includes('Failed to fetch dynamically imported module')) throw e;
      console.warn('scene module missing, using black placeholder:', d.module);
      const sc = new THREE.Scene(); const cam = new THREE.PerspectiveCamera(40, W / H, 0.1, 10);
      s = { scene: sc, camera: cam, update() {}, grade: {} };
    }
    s.def = d;
    scenes[d.id] = s;
    // compile shaders up-front so frame 0 is not special
    renderer.compile(s.scene, s.camera);
  }
  const trans = config.timing.transitions;
  const MODES = { crossfade: 0, portal: 1, beam: 2, spot: 3, dissolve: 4 };

  function sceneAt(t) {
    for (const d of defs) if (t >= d.start && t < d.end) return d;
    return defs[defs.length - 1];
  }
  function mixGrade(a, b, k) {
    const out = {};
    const keys = new Set([...Object.keys(a || {}), ...Object.keys(b || {})]);
    for (const key of keys) {
      const va = a?.[key], vb = b?.[key];
      if (va === undefined) out[key] = vb; else if (vb === undefined) out[key] = va;
      else if (Array.isArray(va)) out[key] = va.map((x, i) => x + (vb[i] - x) * k);
      else out[key] = va + (vb - va) * k;
    }
    return out;
  }
  function run(s, t) {
    s.update(t - s.def.start, t);
    return s;
  }
  // Render the composited HDR image for time t into post.compRT; returns grade to use
  function composite(t) {
    for (const tr of trans) {
      const t0 = tr.at - tr.duration / 2, t1 = tr.at + tr.duration / 2;
      if (t >= t0 && t < t1) {
        const A = defs.find((d) => d.end === tr.at), B = defs.find((d) => d.start === tr.at);
        const sa = scenes[A.id], sb = scenes[B.id];
        if (sa && sb) {
          const p = (t - t0) / tr.duration;
          const ta = post.renderScene(run(sa, t), 0);
          const tb = post.renderScene(run(sb, t), 1);
          post.comp(ta, tb, p, MODES[tr.type] ?? 0, t);
          return mixGrade(sa.grade, sb.grade, p);
        }
      }
    }
    const d = sceneAt(t);
    const s = scenes[d.id];
    if (!s) throw new Error('scene not loaded for t=' + t + ': ' + d.id);
    post.comp(post.renderScene(run(s, t), 0), null, 0, 0, t);
    return s.grade;
  }

  const gl = renderer.getContext();
  const buf = new Uint8Array(W * H * 4);
  E.info = { W, H, fps: q.fps, duration: config.timing.duration, frames: Math.round(config.timing.duration * q.fps), quality: q };
  E.renderTime = async (t, frame = 0) => {
    const N = Math.max(1, q.motionBlurSamples | 0);
    const shutter = (fx.shutterAngle / 360) / q.fps;
    post.clearAcc();
    let grade = null;
    for (let k = 0; k < N; k++) {
      const ts = N > 1 ? t + ((k + 0.5) / N - 0.5) * shutter : t;
      grade = composite(Math.max(0, ts));
      post.accumulate(1 / N);
    }
    post.finish(frame, grade || {});
  };
  E.renderFrame = async (i) => {
    await E.renderTime(i / q.fps, i);
    gl.readPixels(0, 0, W, H, gl.RGBA, gl.UNSIGNED_BYTE, buf);
    const r = await fetch('/frame?i=' + i, { method: 'POST', body: buf });
    if (!r.ok) throw new Error('frame upload failed');
  };
  E.still = async (t, name) => {
    await E.renderTime(t, Math.round(t * q.fps));
    const blob = await new Promise((res) => canvas.toBlob(res, 'image/png'));
    await fetch('/still?name=' + encodeURIComponent(name), { method: 'POST', body: blob });
  };
  E.ready = true;
} catch (e) {
  E.error = String(e && e.stack || e);
  console.error(E.error);
}
