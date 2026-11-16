// Génère compositions/captions.html à partir de assets/film-data.js.
// Usage : node tools/build-captions.mjs
import fs from "node:fs";
import vm from "node:vm";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const ctx = { window: {} };
ctx.globalThis = ctx;
vm.runInNewContext(fs.readFileSync(path.join(root, "assets/film-data.js"), "utf8"), ctx);
const FILM = ctx.window.__FILM;
const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;");
const r = (n) => Math.round(n * 1000) / 1000;

const groups = FILM.groups
  .map((g, i) => {
    const words = g.words
      .map((w) => `<span class="cw${w.emph === 1 ? " e1" : w.emph === 2 ? " e2" : ""}" data-at="${r(w.start)}">${esc(w.text)}</span>`)
      .join(" ");
    return `      <div id="cap-${i}" class="clip cap" data-start="${r(g.show)}" data-duration="${r(g.hide - g.show)}" data-track-index="1" data-layout-allow-overflow><div class="cap-in">${words}</div></div>`;
  })
  .join("\n");

const html = `<!-- Généré par tools/build-captions.mjs : modifier assets/film-data.js, pas ce fichier. -->
<template>
  <style>
    #root {
      position: absolute;
      inset: 0;
      font-family: "Montserrat", sans-serif;
    }
    #root .cap {
      position: absolute;
      left: 90px;
      top: 1104px;
      width: 900px;
      height: 180px;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: visible;
    }
    #root .cap-in {
      width: 900px;
      text-align: center;
      text-wrap: balance;
      font-weight: 900;
      font-size: 68px;
      line-height: 1.16;
      color: #f5f2eb;
      -webkit-text-stroke: 14px #101827;
      paint-order: stroke fill;
    }
    #root .cw {
      display: inline-block;
      margin: 0 0.06em;
    }
    #root .cw.e1 {
      color: #ff9f1c;
      margin: 0 0.32em;
    }
    #root .cw.e2 {
      color: #ff4057;
      margin: 0 0.32em;
    }
  </style>
  <div id="root" data-composition-id="captions" data-width="1080" data-height="1920">
${groups}
  </div>
  <script>
    (function () {
      const tl = gsap.timeline({ paused: true });
      document.querySelectorAll('[data-composition-id="captions"] .cap').forEach(function (cap) {
        const t0 = parseFloat(cap.dataset.start);
        const inner = cap.querySelector(".cap-in");
        cap.querySelectorAll(".cw").forEach(function (w, i) {
          // chaque mot arrive quand il est prononcé ; les mots importants grossissent
          const at = i === 0 ? t0 : Math.max(t0, parseFloat(w.dataset.at) - 0.04);
          const em = w.classList.contains("e1") || w.classList.contains("e2");
          tl.fromTo(w, { opacity: 0, y: 16 }, { opacity: 1, y: 0, duration: 0.1, ease: "power3.out" }, at);
          if (em) tl.fromTo(w, { scale: 0.8 }, { scale: 1.12, duration: 0.24, ease: "back.out(3)" }, at);
        });
      });
      window.__timelines = window.__timelines || {};
      window.__timelines["captions"] = tl;
    })();
  </script>
</template>
`;
fs.writeFileSync(path.join(root, "compositions/captions.html"), html);
console.log("captions.html :", FILM.groups.length, "groupes,", FILM.words.length, "mots");
