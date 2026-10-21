// Scène 3D (Three.js) : objet central irisé, flyers flottants et particules.
import * as THREE from "three";

const PALETTE = {
  pink: "#ff3d9a",
  violet: "#8b5cff",
  cyan: "#22e4ff",
  gold: "#ffcc4d",
};

// Crée une texture "affiche" dessinée dans un canvas.
function makePosterTexture(title, subtitle, c1, c2) {
  const w = 512;
  const h = 724;
  const cv = document.createElement("canvas");
  cv.width = w;
  cv.height = h;
  const ctx = cv.getContext("2d");

  const g = ctx.createLinearGradient(0, 0, w, h);
  g.addColorStop(0, c1);
  g.addColorStop(1, c2);
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, w, h);

  // Cercles décoratifs
  ctx.globalAlpha = 0.25;
  ctx.fillStyle = "#ffffff";
  ctx.beginPath();
  ctx.arc(w * 0.78, h * 0.25, 150, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalAlpha = 0.12;
  ctx.beginPath();
  ctx.arc(w * 0.2, h * 0.62, 210, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalAlpha = 1;

  // Bandeau sombre
  ctx.fillStyle = "rgba(10,8,20,0.55)";
  ctx.fillRect(0, h * 0.68, w, h * 0.32);

  ctx.fillStyle = "#ffffff";
  ctx.textAlign = "left";
  ctx.font = "900 96px 'Arial Black', Arial, sans-serif";
  ctx.fillText(title, 36, h * 0.8);
  ctx.font = "600 34px Arial, sans-serif";
  ctx.fillStyle = "rgba(255,255,255,0.85)";
  ctx.fillText(subtitle, 40, h * 0.88);

  // Cadre
  ctx.strokeStyle = "rgba(255,255,255,0.6)";
  ctx.lineWidth = 6;
  ctx.strokeRect(18, 18, w - 36, h - 36);

  const tex = new THREE.CanvasTexture(cv);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  return tex;
}

export function initScene(canvas, { variant = "hero" } = {}) {
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  } catch (e) {
    canvas.classList.add("no-webgl");
    return;
  }

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const speed = reduceMotion ? 0.25 : 1;

  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;

  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x07060d, 0.045);

  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
  camera.position.set(0, 0, variant === "hero" ? 9 : 11);

  // Lumières néon
  scene.add(new THREE.AmbientLight(0xffffff, 0.35));
  const l1 = new THREE.PointLight(PALETTE.pink, 60, 30);
  const l2 = new THREE.PointLight(PALETTE.cyan, 60, 30);
  const l3 = new THREE.PointLight(PALETTE.violet, 40, 30);
  scene.add(l1, l2, l3);
  const dir = new THREE.DirectionalLight(0xffffff, 1.2);
  dir.position.set(3, 5, 6);
  scene.add(dir);

  const root = new THREE.Group();
  scene.add(root);

  // Objet central : nœud torique irisé + coque fil de fer
  const knotGeo = new THREE.TorusKnotGeometry(1.25, 0.42, 220, 32);
  const knotMat = new THREE.MeshPhysicalMaterial({
    color: 0x9b7bff,
    metalness: 0.55,
    roughness: 0.18,
    clearcoat: 1,
    clearcoatRoughness: 0.1,
    iridescence: 1,
    iridescenceIOR: 1.6,
    sheen: 1,
    sheenColor: new THREE.Color(PALETTE.pink),
  });
  const knot = new THREE.Mesh(knotGeo, knotMat);
  const shell = new THREE.Mesh(
    new THREE.IcosahedronGeometry(2.6, 1),
    new THREE.MeshBasicMaterial({ color: PALETTE.cyan, wireframe: true, transparent: true, opacity: 0.18 })
  );
  const core = new THREE.Group();
  core.add(knot, shell);
  if (variant === "hero") {
    core.position.set(window.innerWidth > 900 ? 2.4 : 0, window.innerWidth > 900 ? 0 : 0.9, 0);
  } else {
    core.position.set(4.5, 1.5, -3);
    core.scale.setScalar(0.8);
  }
  root.add(core);

  // Flyers flottants
  const posters = [
    ["FLYER", "Soirée · Événement", PALETTE.pink, PALETTE.violet],
    ["TEASER", "Vidéo · Réseaux", PALETTE.cyan, PALETTE.violet],
    ["PUB", "Campagne · Marque", PALETTE.gold, PALETTE.pink],
    ["BOHO", "Night party", PALETTE.violet, PALETTE.cyan],
    ["SPORT", "Vidéo promo", PALETTE.cyan, PALETTE.gold],
  ];
  const cardGeo = new THREE.PlaneGeometry(1.1, 1.55);
  const cards = posters.map(([t, s, a, b], i) => {
    const mat = new THREE.MeshStandardMaterial({
      map: makePosterTexture(t, s, a, b),
      roughness: 0.35,
      metalness: 0.1,
      side: THREE.DoubleSide,
    });
    const m = new THREE.Mesh(cardGeo, mat);
    m.userData = {
      angle: (i / posters.length) * Math.PI * 2,
      radius: 3.4 + (i % 2) * 0.6,
      y: (i % 3) - 1,
      spin: 0.3 + Math.random() * 0.4,
    };
    core.add(m);
    return m;
  });

  // Particules
  const count = variant === "hero" ? 1400 : 900;
  const pos = new Float32Array(count * 3);
  const col = new Float32Array(count * 3);
  const colors = [PALETTE.pink, PALETTE.cyan, PALETTE.violet, PALETTE.gold].map((c) => new THREE.Color(c));
  for (let i = 0; i < count; i++) {
    pos[i * 3] = (Math.random() - 0.5) * 30;
    pos[i * 3 + 1] = (Math.random() - 0.5) * 20;
    pos[i * 3 + 2] = (Math.random() - 0.5) * 20 - 3;
    const c = colors[i % colors.length];
    col[i * 3] = c.r;
    col[i * 3 + 1] = c.g;
    col[i * 3 + 2] = c.b;
  }
  const pGeo = new THREE.BufferGeometry();
  pGeo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  pGeo.setAttribute("color", new THREE.BufferAttribute(col, 3));
  const particles = new THREE.Points(
    pGeo,
    new THREE.PointsMaterial({ size: 0.05, vertexColors: true, transparent: true, opacity: 0.8, depthWrite: false })
  );
  scene.add(particles);

  // Interaction souris / doigt + défilement
  const pointer = { x: 0, y: 0, tx: 0, ty: 0 };
  window.addEventListener("pointermove", (e) => {
    pointer.tx = (e.clientX / window.innerWidth) * 2 - 1;
    pointer.ty = (e.clientY / window.innerHeight) * 2 - 1;
  });
  let scrollY = window.scrollY;
  window.addEventListener("scroll", () => (scrollY = window.scrollY), { passive: true });

  function resize() {
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    if (variant === "hero") {
      const wide = w > 900;
      core.position.x = wide ? 2.4 : 0;
      core.position.y = wide ? 0 : 0.9;
      core.scale.setScalar(wide ? 1 : 0.72);
    }
  }
  window.addEventListener("resize", resize);
  resize();

  let running = true;
  document.addEventListener("visibilitychange", () => {
    running = !document.hidden;
    if (running) {
      clock.getDelta();
      requestAnimationFrame(tick);
    }
  });

  const clock = new THREE.Clock();
  let t = 0;
  function tick() {
    if (!running) return;
    const dt = Math.min(clock.getDelta(), 0.05) * speed;
    t += dt;

    pointer.x += (pointer.tx - pointer.x) * 0.05;
    pointer.y += (pointer.ty - pointer.y) * 0.05;

    knot.rotation.x += dt * 0.35;
    knot.rotation.y += dt * 0.5;
    shell.rotation.y -= dt * 0.12;
    shell.rotation.z += dt * 0.06;

    cards.forEach((m) => {
      const d = m.userData;
      const a = d.angle + t * 0.25;
      m.position.set(Math.cos(a) * d.radius, d.y + Math.sin(t * 0.8 + d.angle) * 0.35, Math.sin(a) * d.radius);
      m.lookAt(camera.position);
      m.rotation.z = Math.sin(t * d.spin + d.angle) * 0.25;
    });

    l1.position.set(Math.sin(t * 0.7) * 6, Math.cos(t * 0.5) * 4, 4);
    l2.position.set(Math.cos(t * 0.6) * -6, Math.sin(t * 0.4) * 4, 3);
    l3.position.set(0, Math.sin(t) * 3, -4);

    particles.rotation.y = t * 0.02;
    root.rotation.y = pointer.x * 0.35 + scrollY * 0.0008;
    root.rotation.x = pointer.y * 0.2;
    camera.position.y = -scrollY * 0.002;

    renderer.render(scene, camera);
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}
