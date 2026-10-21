// Comportements communs : menu mobile, apparition au défilement,
// effet 3D au survol des cartes, liens de contact.
import { CONFIG } from "./config.js";

// Menu mobile
const toggle = document.querySelector(".menu-toggle");
const links = document.querySelector(".nav-links");
if (toggle && links) {
  toggle.addEventListener("click", () => {
    const open = links.classList.toggle("open");
    toggle.setAttribute("aria-expanded", String(open));
  });
  links.querySelectorAll("a").forEach((a) => a.addEventListener("click", () => links.classList.remove("open")));
}

// Apparition au défilement
const io = new IntersectionObserver(
  (entries) =>
    entries.forEach((e) => {
      if (e.isIntersecting) {
        e.target.classList.add("visible");
        io.unobserve(e.target);
      }
    }),
  { threshold: 0.12 }
);
document.querySelectorAll(".reveal").forEach((el) => io.observe(el));

// Inclinaison 3D des cartes au survol (souris uniquement)
if (window.matchMedia("(hover: hover) and (prefers-reduced-motion: no-preference)").matches) {
  document.querySelectorAll("[data-tilt]").forEach((el) => {
    el.addEventListener("pointermove", (e) => {
      const r = el.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width - 0.5;
      const y = (e.clientY - r.top) / r.height - 0.5;
      el.style.transform = `perspective(800px) rotateY(${x * 10}deg) rotateX(${-y * 10}deg) translateZ(6px)`;
    });
    el.addEventListener("pointerleave", () => (el.style.transform = ""));
  });
}

// Liens de contact remplis depuis la configuration
document.querySelectorAll("[data-email]").forEach((a) => {
  a.href = `mailto:${CONFIG.CONTACT_EMAIL}`;
  a.textContent = CONFIG.CONTACT_EMAIL;
});
[["instagram", CONFIG.INSTAGRAM], ["tiktok", CONFIG.TIKTOK]].forEach(([name, url]) => {
  document.querySelectorAll(`[data-social="${name}"]`).forEach((a) => {
    if (url) a.href = url;
    else a.remove();
  });
});

const year = document.getElementById("year");
if (year) year.textContent = new Date().getFullYear();

// Pré-sélection d'une prestation depuis l'URL (ex. commande.html?service=teaser)
const wanted = new URLSearchParams(location.search).get("service");
if (wanted) {
  const box = document.querySelector(`input[name="prestations"][value="${CSS.escape(wanted)}"]`);
  if (box) box.checked = true;
}
