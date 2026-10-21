// Envoi du formulaire de commande vers Formspree.
// Si Formspree n'est pas encore configuré, on ouvre l'e-mail avec la demande pré-remplie.
import { CONFIG } from "./config.js";

const form = document.getElementById("order-form");
const errorBox = document.getElementById("form-error");
const submitBtn = form?.querySelector('button[type="submit"]');
const configured = CONFIG.FORMSPREE_ID && !CONFIG.FORMSPREE_ID.startsWith("VOTRE_");

if (form && !configured) {
  document.getElementById("setup-notice")?.removeAttribute("hidden");
}

function collect() {
  const data = new FormData(form);
  const out = {};
  for (const [k, v] of data.entries()) {
    if (k === "_gotcha") continue;
    if (out[k]) out[k] = `${out[k]}, ${v}`;
    else out[k] = v;
  }
  return out;
}

function validate() {
  errorBox.textContent = "";
  if (!form.querySelector('input[name="prestations"]:checked')) {
    errorBox.textContent = "Choisissez au moins une prestation (flyer, teaser, publicité…).";
    form.querySelector('input[name="prestations"]').focus();
    return false;
  }
  if (!form.checkValidity()) {
    form.reportValidity();
    return false;
  }
  return true;
}

function showSuccess(name) {
  const card = document.getElementById("form-card");
  card.innerHTML = `
    <div class="result">
      <div class="big">🎉</div>
      <h2>Merci ${name ? escapeHtml(name) : ""} !</h2>
      <p>Votre demande est bien partie. Je reviens vers vous très vite (sous 24 à 48 h)
      pour en parler et vous envoyer un devis.</p>
      <a class="btn" href="index.html">Retour à l'accueil</a>
    </div>`;
  card.scrollIntoView({ behavior: "smooth", block: "start" });
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

const LABELS = {
  prestations: "Prestations",
  profil: "Profil",
  prenom: "Prénom",
  nom: "Nom",
  entreprise: "Entreprise / événement",
  email: "E-mail",
  telephone: "Téléphone",
  contact_prefere: "Contact préféré",
  date_evenement: "Date de l'événement",
  delai: "Délai souhaité",
  budget: "Budget",
  supports: "Supports",
  description: "Description du besoin",
  liens: "Liens / inspirations",
};

function mailtoFallback(values) {
  const body = Object.entries(values)
    .filter(([k]) => !k.startsWith("_") && k !== "consentement")
    .map(([k, v]) => `${LABELS[k] || k} : ${v}`)
    .join("\n");
  const subject = `Nouvelle demande : ${values.prestations || "projet"} (${values.prenom || ""} ${values.nom || ""})`;
  window.location.href = `mailto:${CONFIG.CONTACT_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}

form?.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!validate()) return;

  // Piège anti-robots : si ce champ caché est rempli, on ignore.
  if (form.querySelector('input[name="_gotcha"]').value) return;

  const values = collect();

  if (!configured) {
    mailtoFallback(values);
    return;
  }

  submitBtn.disabled = true;
  submitBtn.textContent = "Envoi en cours…";
  try {
    const res = await fetch(`https://formspree.io/f/${CONFIG.FORMSPREE_ID}`, {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({
        ...values,
        _subject: `Nouvelle commande : ${values.prestations} (${values.prenom} ${values.nom})`,
        _replyto: values.email,
      }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    showSuccess(values.prenom);
  } catch (err) {
    errorBox.innerHTML = `Oups, l'envoi a échoué. Réessayez, ou écrivez-moi directement à
      <a href="mailto:${CONFIG.CONTACT_EMAIL}">${CONFIG.CONTACT_EMAIL}</a>.`;
    submitBtn.disabled = false;
    submitBtn.textContent = "Envoyer ma demande";
  }
});
