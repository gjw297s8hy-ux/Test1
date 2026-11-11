"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import type { Channel, ContactStatus, Role } from "@prisma/client";
import { db } from "@/lib/db";
import { createSession, destroySession, hashPassword, hashToken, isAdmin, newToken, requireCtx, verifyPassword } from "@/lib/auth";
import { analyzeReply, draftMessages, enrichCompanies, findProspects, startRun } from "@/lib/agent";
import { CHANNELS, CONTACT_STATUSES, domainOf, fullName } from "@/lib/labels";
import { appUrl, canAutoSend, sendEmail, sendTwilio } from "@/lib/send";
import { TRIAL_SIZE, isTrial } from "@/lib/plan";

export type FormState = { error?: string } | undefined;

const s = (fd: FormData, key: string) => String(fd.get(key) ?? "").trim();
const emailOk = (e: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e);
const tags = (v: string) => [...new Set(v.split(",").map((t) => t.trim()).filter(Boolean))];

function flash(path: string, msg: string): never {
  // Le chemin de retour vient parfois du formulaire : on ne redirige que dans l'application.
  if (!path.startsWith("/app")) path = "/app";
  redirect(`${path}${path.includes("?") ? "&" : "?"}msg=${encodeURIComponent(msg)}`);
}

/* ---------- Comptes ---------- */

export async function signup(_: FormState, fd: FormData): Promise<FormState> {
  const name = s(fd, "name");
  const orgName = s(fd, "orgName");
  const email = s(fd, "email").toLowerCase();
  const password = String(fd.get("password") ?? "");
  if (!name || !orgName) return { error: "Indiquez votre nom et celui de votre entreprise." };
  if (!emailOk(email)) return { error: "Adresse e-mail invalide." };
  if (password.length < 10) return { error: "Le mot de passe doit contenir au moins 10 caractères." };
  if (await db.user.findUnique({ where: { email } })) return { error: "Un compte existe déjà avec cette adresse." };

  const user = await db.user.create({
    data: {
      email,
      name,
      passwordHash: await hashPassword(password),
      memberships: { create: { role: "OWNER", org: { create: { name: orgName, senderName: name, replyTo: email } } } },
    },
    include: { memberships: true },
  });
  await createSession(user.id, user.memberships[0].orgId);
  redirect("/app/parametres?bienvenue=1");
}

export async function login(_: FormState, fd: FormData): Promise<FormState> {
  const email = s(fd, "email").toLowerCase();
  const password = String(fd.get("password") ?? "");
  const user = await db.user.findUnique({ where: { email }, include: { memberships: { orderBy: { id: "asc" } } } });
  // Meme message dans les deux cas : ne revele pas si l'adresse a un compte.
  if (!user || !(await verifyPassword(password, user.passwordHash)) || user.memberships.length === 0) {
    return { error: "Adresse e-mail ou mot de passe incorrect." };
  }
  await createSession(user.id, user.memberships[0].orgId);
  redirect("/app");
}

export async function logout() {
  await destroySession();
  redirect("/connexion");
}

export async function switchOrg(fd: FormData) {
  const ctx = await requireCtx();
  const orgId = s(fd, "orgId");
  const membership = await db.membership.findUnique({ where: { userId_orgId: { userId: ctx.userId, orgId } } });
  if (!membership) flash("/app/parametres", "Organisation introuvable.");
  await destroySession();
  await createSession(ctx.userId, orgId);
  redirect("/app");
}

export async function acceptInvitation(_: FormState, fd: FormData): Promise<FormState> {
  const token = s(fd, "token");
  const invitation = await db.invitation.findUnique({ where: { tokenHash: hashToken(token) } });
  if (!invitation || invitation.acceptedAt || invitation.expiresAt < new Date()) {
    return { error: "Cette invitation n'est plus valable." };
  }
  const password = String(fd.get("password") ?? "");
  let user = await db.user.findUnique({ where: { email: invitation.email } });
  if (user) {
    if (!(await verifyPassword(password, user.passwordHash))) return { error: "Mot de passe incorrect." };
  } else {
    const name = s(fd, "name");
    if (!name) return { error: "Indiquez votre nom." };
    if (password.length < 10) return { error: "Le mot de passe doit contenir au moins 10 caractères." };
    user = await db.user.create({ data: { email: invitation.email, name, passwordHash: await hashPassword(password) } });
  }
  await db.membership.upsert({
    where: { userId_orgId: { userId: user.id, orgId: invitation.orgId } },
    create: { userId: user.id, orgId: invitation.orgId, role: invitation.role },
    update: {},
  });
  await db.invitation.update({ where: { id: invitation.id }, data: { acceptedAt: new Date() } });
  await createSession(user.id, invitation.orgId);
  redirect("/app");
}

/* ---------- Parametres ---------- */

export async function updateOrg(fd: FormData) {
  const ctx = await requireCtx();
  if (!isAdmin(ctx)) flash("/app/parametres", "Réservé aux administrateurs.");
  const name = s(fd, "name");
  if (!name) flash("/app/parametres", "Le nom de l'entreprise est obligatoire.");
  const replyTo = s(fd, "replyTo").toLowerCase();
  if (replyTo && !emailOk(replyTo)) flash("/app/parametres", "Adresse de réponse invalide.");
  await db.organization.update({
    where: { id: ctx.orgId },
    data: {
      name,
      offer: s(fd, "offer"),
      senderName: s(fd, "senderName"),
      replyTo,
      signature: s(fd, "signature"),
      legalFooter: s(fd, "legalFooter"),
    },
  });
  flash("/app/parametres", "Paramètres enregistrés.");
}

export async function inviteMember(fd: FormData) {
  const ctx = await requireCtx();
  if (!isAdmin(ctx)) flash("/app/parametres", "Réservé aux administrateurs.");
  const email = s(fd, "email").toLowerCase();
  const role: Role = s(fd, "role") === "ADMIN" ? "ADMIN" : "MEMBER";
  if (!emailOk(email)) flash("/app/parametres", "Adresse e-mail invalide.");
  const already = await db.membership.findFirst({ where: { orgId: ctx.orgId, user: { email } } });
  if (already) flash("/app/parametres", "Cette personne fait déjà partie de l'équipe.");
  const token = newToken();
  await db.invitation.deleteMany({ where: { orgId: ctx.orgId, email, acceptedAt: null } });
  await db.invitation.create({
    data: { orgId: ctx.orgId, email, role, tokenHash: hashToken(token), expiresAt: new Date(Date.now() + 7 * 86_400_000) },
  });
  // Le lien n'est affiche qu'une fois : seul son hachage est conserve.
  redirect(`/app/parametres?invitation=${encodeURIComponent(`${appUrl()}/invitation/${token}`)}`);
}

export async function revokeInvitation(fd: FormData) {
  const ctx = await requireCtx();
  if (!isAdmin(ctx)) flash("/app/parametres", "Réservé aux administrateurs.");
  await db.invitation.deleteMany({ where: { id: s(fd, "id"), orgId: ctx.orgId } });
  flash("/app/parametres", "Invitation annulée.");
}

export async function removeMember(fd: FormData) {
  const ctx = await requireCtx();
  if (!isAdmin(ctx)) flash("/app/parametres", "Réservé aux administrateurs.");
  const target = await db.membership.findFirst({ where: { id: s(fd, "id"), orgId: ctx.orgId } });
  if (!target) flash("/app/parametres", "Membre introuvable.");
  if (target.role === "OWNER") flash("/app/parametres", "Le propriétaire ne peut pas être retiré.");
  await db.session.deleteMany({ where: { userId: target.userId, orgId: ctx.orgId } });
  await db.membership.delete({ where: { id: target.id } });
  flash("/app/parametres", "Membre retiré.");
}

/* ---------- Entreprises ---------- */

function companyData(fd: FormData) {
  const website = s(fd, "website");
  return {
    name: s(fd, "name"),
    website,
    domain: domainOf(website),
    industry: s(fd, "industry"),
    city: s(fd, "city"),
    size: s(fd, "size"),
    phone: s(fd, "phone"),
    description: s(fd, "description"),
    tags: tags(s(fd, "tags")),
  };
}

export async function createCompany(fd: FormData) {
  const ctx = await requireCtx();
  const data = companyData(fd);
  if (!data.name) flash("/app/entreprises", "Le nom de l'entreprise est obligatoire.");
  const company = await db.company.create({ data: { ...data, orgId: ctx.orgId } });
  redirect(`/app/entreprises/${company.id}`);
}

export async function updateCompany(fd: FormData) {
  const ctx = await requireCtx();
  const id = s(fd, "id");
  const data = companyData(fd);
  if (!data.name) flash(`/app/entreprises/${id}`, "Le nom de l'entreprise est obligatoire.");
  await db.company.updateMany({ where: { id, orgId: ctx.orgId }, data });
  flash(`/app/entreprises/${id}`, "Fiche enregistrée.");
}

export async function deleteCompany(fd: FormData) {
  const ctx = await requireCtx();
  await db.company.deleteMany({ where: { id: s(fd, "id"), orgId: ctx.orgId } });
  flash("/app/entreprises", "Entreprise supprimée.");
}

/* ---------- Contacts ---------- */

async function contactData(fd: FormData, orgId: string) {
  const companyId = s(fd, "companyId");
  const company = companyId ? await db.company.findFirst({ where: { id: companyId, orgId } }) : null;
  const status = s(fd, "status") as ContactStatus;
  return {
    firstName: s(fd, "firstName"),
    lastName: s(fd, "lastName"),
    jobTitle: s(fd, "jobTitle"),
    email: s(fd, "email").toLowerCase(),
    phone: s(fd, "phone"),
    linkedinUrl: s(fd, "linkedinUrl"),
    notes: s(fd, "notes"),
    tags: tags(s(fd, "tags")),
    companyId: company?.id ?? null,
    ...(CONTACT_STATUSES.includes(status) ? { status } : {}),
  };
}

export async function createContact(fd: FormData) {
  const ctx = await requireCtx();
  const data = await contactData(fd, ctx.orgId);
  if (!data.firstName && !data.lastName) flash("/app/prospects", "Indiquez au moins un nom ou un prénom.");
  if (data.email && !emailOk(data.email)) flash("/app/prospects", "Adresse e-mail invalide.");
  const contact = await db.contact.create({ data: { ...data, orgId: ctx.orgId, sourceUrl: "Saisie manuelle" } });
  redirect(`/app/prospects/${contact.id}`);
}

export async function updateContact(fd: FormData) {
  const ctx = await requireCtx();
  const id = s(fd, "id");
  const data = await contactData(fd, ctx.orgId);
  if (data.email && !emailOk(data.email)) flash(`/app/prospects/${id}`, "Adresse e-mail invalide.");
  const doNotContact = fd.get("doNotContact") === "on";
  await db.contact.updateMany({ where: { id, orgId: ctx.orgId }, data: { ...data, doNotContact } });
  if (doNotContact) {
    await db.message.updateMany({ where: { contactId: id, orgId: ctx.orgId, status: "DRAFT" }, data: { status: "DISCARDED" } });
  }
  flash(`/app/prospects/${id}`, "Fiche enregistrée.");
}

/** RGPD : suppression definitive du contact et de tout son historique. */
export async function deleteContact(fd: FormData) {
  const ctx = await requireCtx();
  await db.contact.deleteMany({ where: { id: s(fd, "id"), orgId: ctx.orgId } });
  flash("/app/prospects", "Contact et historique supprimés.");
}

/* ---------- Taches ---------- */

export async function createTask(fd: FormData) {
  const ctx = await requireCtx();
  const back = s(fd, "back") || "/app/taches";
  const title = s(fd, "title");
  if (!title) flash(back, "Indiquez l'intitulé de la tâche.");
  const contactId = s(fd, "contactId");
  const contact = contactId ? await db.contact.findFirst({ where: { id: contactId, orgId: ctx.orgId } }) : null;
  const due = s(fd, "dueAt");
  await db.task.create({
    data: {
      orgId: ctx.orgId,
      title,
      contactId: contact?.id ?? null,
      assigneeId: ctx.userId,
      // Date saisie sans heure : echeance a midi pour rester le bon jour quel que soit le fuseau.
      dueAt: due ? new Date(`${due}T12:00:00`) : null,
    },
  });
  revalidatePath(back);
}

export async function toggleTask(fd: FormData) {
  const ctx = await requireCtx();
  const task = await db.task.findFirst({ where: { id: s(fd, "id"), orgId: ctx.orgId } });
  if (task) await db.task.update({ where: { id: task.id }, data: { doneAt: task.doneAt ? null : new Date() } });
  revalidatePath("/app", "layout");
}

export async function deleteTask(fd: FormData) {
  const ctx = await requireCtx();
  await db.task.deleteMany({ where: { id: s(fd, "id"), orgId: ctx.orgId } });
  revalidatePath("/app", "layout");
}

/* ---------- Campagnes et agent ---------- */

function campaignData(fd: FormData) {
  const channels = fd.getAll("channels").map(String).filter((c): c is Channel => CHANNELS.includes(c as Channel));
  return {
    name: s(fd, "name"),
    industry: s(fd, "industry"),
    location: s(fd, "location"),
    size: s(fd, "size"),
    roles: s(fd, "roles"),
    keywords: s(fd, "keywords"),
    pitch: s(fd, "pitch"),
    tone: s(fd, "tone") || "professionnel et direct",
    channels: channels.length ? channels : (["EMAIL"] as Channel[]),
  };
}

export async function createCampaign(fd: FormData) {
  const ctx = await requireCtx();
  const data = campaignData(fd);
  if (!data.name) flash("/app/agent", "Donnez un nom à la campagne.");
  if (!data.industry && !data.keywords) flash("/app/agent", "Décrivez la cible : un secteur ou des critères.");
  const campaign = await db.campaign.create({ data: { ...data, orgId: ctx.orgId } });
  redirect(`/app/agent/${campaign.id}`);
}

export async function updateCampaign(fd: FormData) {
  const ctx = await requireCtx();
  const id = s(fd, "id");
  const data = campaignData(fd);
  if (!data.name) flash(`/app/agent/${id}`, "Donnez un nom à la campagne.");
  await db.campaign.updateMany({ where: { id, orgId: ctx.orgId }, data });
  flash(`/app/agent/${id}`, "Campagne enregistrée.");
}

export async function deleteCampaign(fd: FormData) {
  const ctx = await requireCtx();
  await db.campaign.deleteMany({ where: { id: s(fd, "id"), orgId: ctx.orgId } });
  flash("/app/agent", "Campagne supprimée. Les entreprises et contacts trouvés sont conservés.");
}

export async function launchFind(fd: FormData) {
  const ctx = await requireCtx();
  const campaignId = s(fd, "campaignId");
  const campaign = await db.campaign.findFirst({ where: { id: campaignId, orgId: ctx.orgId } });
  if (!campaign) flash("/app/agent", "Campagne introuvable.");
  const count = (await isTrial(ctx.orgId)) ? TRIAL_SIZE : Math.max(3, Math.min(20, Number(s(fd, "count")) || 10));
  const res = await startRun({
    orgId: ctx.orgId,
    type: "FIND",
    label: `${count} prospect${count > 1 ? "s" : ""} pour « ${campaign.name} »`,
    campaignId,
    work: (usage) => findProspects(ctx.orgId, campaignId, count, usage),
  });
  flash(`/app/agent/${campaignId}`, res.ok ? "Recherche lancée. Les résultats apparaîtront ici dans quelques minutes." : res.error);
}

export async function launchEnrich(fd: FormData) {
  const ctx = await requireCtx();
  const back = s(fd, "back") || "/app/entreprises";
  const campaignId = s(fd, "campaignId");
  const ids = fd.getAll("companyId").map(String).filter(Boolean);
  const companies = await db.company.findMany({
    where: { orgId: ctx.orgId, ...(ids.length ? { id: { in: ids } } : { campaignId: campaignId || "-", enrichedAt: null }) },
    select: { id: true, name: true },
    take: (await isTrial(ctx.orgId)) ? TRIAL_SIZE : 15,
  });
  if (companies.length === 0) flash(back, "Aucune entreprise à enrichir.");
  const companyIds = companies.map((c) => c.id);
  const res = await startRun({
    orgId: ctx.orgId,
    type: "ENRICH",
    label: companies.length === 1 ? companies[0].name : `${companies.length} entreprises`,
    campaignId: campaignId || null,
    work: (usage) => enrichCompanies(ctx.orgId, companyIds, usage),
  });
  flash(back, res.ok ? "Enrichissement lancé." : res.error);
}

export async function launchDraft(fd: FormData) {
  const ctx = await requireCtx();
  const back = s(fd, "back") || "/app/messages";
  const campaignId = s(fd, "campaignId");
  const ids = fd.getAll("contactId").map(String).filter(Boolean);
  const campaign = campaignId ? await db.campaign.findFirst({ where: { id: campaignId, orgId: ctx.orgId } }) : null;
  let channels = fd.getAll("channels").map(String).filter((c): c is Channel => CHANNELS.includes(c as Channel));
  if (channels.length === 0) channels = campaign?.channels ?? [];
  if (channels.length === 0) flash(back, "Choisissez au moins un canal.");
  const contacts = await db.contact.findMany({
    where: {
      orgId: ctx.orgId,
      doNotContact: false,
      // Sans selection explicite : les contacts de la campagne qui n'ont encore aucun message.
      ...(ids.length ? { id: { in: ids } } : { company: { campaignId: campaign?.id ?? "-" }, messages: { none: {} } }),
    },
    select: { id: true, firstName: true, lastName: true },
    take: (await isTrial(ctx.orgId)) ? TRIAL_SIZE : 25,
  });
  if (contacts.length === 0) flash(back, "Aucun contact à traiter (déjà contactés, ou opposés à la prospection).");
  const contactIds = contacts.map((c) => c.id);
  const res = await startRun({
    orgId: ctx.orgId,
    type: "DRAFT",
    label: contacts.length === 1 ? fullName(contacts[0]) : `${contacts.length} contacts`,
    campaignId: campaign?.id ?? null,
    work: (usage) => draftMessages(ctx.orgId, contactIds, channels, campaign?.id ?? null, usage),
  });
  flash(back, res.ok ? "Rédaction lancée. Les brouillons arriveront dans « Messages à valider »." : res.error);
}

/* ---------- Messages ---------- */

export async function saveDraft(fd: FormData) {
  const ctx = await requireCtx();
  const back = s(fd, "back") || "/app/messages";
  const body = s(fd, "body");
  if (!body) flash(back, "Le message est vide.");
  await db.message.updateMany({
    where: { id: s(fd, "id"), orgId: ctx.orgId, status: "DRAFT" },
    data: { subject: s(fd, "subject"), body, error: "" },
  });
  flash(back, "Brouillon enregistré.");
}

export async function discardDraft(fd: FormData) {
  const ctx = await requireCtx();
  await db.message.updateMany({ where: { id: s(fd, "id"), orgId: ctx.orgId, status: "DRAFT" }, data: { status: "DISCARDED" } });
  revalidatePath("/app", "layout");
}

/** Validation humaine : rien ne part sans ce clic. L'application envoie elle-meme le message. */
export async function sendMessageNow(fd: FormData) {
  await deliver(fd, true);
}

/** L'utilisateur a envoye le message a la main (messagerie, LinkedIn, telephone) : on le consigne. */
export async function markMessageSent(fd: FormData) {
  await deliver(fd, false);
}

async function deliver(fd: FormData, auto: boolean) {
  const ctx = await requireCtx();
  const back = s(fd, "back") || "/app/messages";
  const message = await db.message.findFirst({
    where: { id: s(fd, "id"), orgId: ctx.orgId, status: "DRAFT" },
    include: { contact: true, org: true },
  });
  if (!message) flash(back, "Ce brouillon n'existe plus.");
  const { contact, org } = message;
  if (contact.doNotContact) flash(back, `${fullName(contact)} s'est opposé à la prospection : envoi bloqué.`);

  // Le texte affiche dans le formulaire fait foi : on envoie ce que l'utilisateur a sous les yeux.
  const subject = fd.has("subject") ? s(fd, "subject") : message.subject;
  const body = fd.has("body") ? s(fd, "body") : message.body;
  if (!body) flash(back, "Le message est vide.");
  if (message.channel === "EMAIL" && !subject) flash(back, "L'e-mail n'a pas d'objet.");

  if (auto) {
    if (!canAutoSend(message.channel)) flash(back, "L'envoi automatique n'est pas configuré pour ce canal.");
    try {
      if (message.channel === "EMAIL") {
        if (!contact.email) throw new Error("Ce contact n'a pas d'adresse e-mail.");
        await sendEmail({
          to: contact.email,
          subject,
          body,
          senderName: org.senderName || org.name,
          replyTo: org.replyTo,
          footer: org.legalFooter,
          unsubscribeUrl: `${appUrl()}/desinscription/${contact.unsubscribeToken}`,
        });
      } else if (message.channel === "SMS" || message.channel === "WHATSAPP") {
        if (!contact.phone) throw new Error("Ce contact n'a pas de numéro de téléphone.");
        await sendTwilio(message.channel, contact.phone, body);
      }
    } catch (err) {
      const detail = err instanceof Error ? err.message : "erreur inconnue";
      await db.message.update({ where: { id: message.id }, data: { subject, body, error: detail } });
      flash(back, `Échec de l'envoi : ${detail}`);
    }
  }

  await db.message.update({ where: { id: message.id }, data: { subject, body, status: "SENT", sentAt: new Date(), error: "" } });
  if (contact.status === "NEW" || contact.status === "TO_CONTACT") {
    await db.contact.update({ where: { id: contact.id }, data: { status: "CONTACTED" } });
  }
  await db.activity.create({
    data: { orgId: ctx.orgId, contactId: contact.id, kind: "message", summary: `Message envoyé (${message.channel.toLowerCase()}) par ${ctx.userName}` },
  });
  // Relance : une seule tache ouverte par contact, a J+4.
  const open = await db.task.findFirst({ where: { orgId: ctx.orgId, contactId: contact.id, doneAt: null, title: { startsWith: "Relancer" } } });
  if (!open) {
    await db.task.create({
      data: {
        orgId: ctx.orgId,
        contactId: contact.id,
        assigneeId: ctx.userId,
        title: `Relancer ${fullName(contact)} si pas de réponse`,
        dueAt: new Date(Date.now() + 4 * 86_400_000),
      },
    });
  }
  flash(back, `${auto ? "Message envoyé" : "Message marqué comme envoyé"}. Une relance est planifiée à J+4.`);
}

export async function registerReply(fd: FormData) {
  const ctx = await requireCtx();
  const contactId = s(fd, "contactId");
  const back = `/app/prospects/${contactId}`;
  const contact = await db.contact.findFirst({ where: { id: contactId, orgId: ctx.orgId } });
  if (!contact) flash("/app/prospects", "Contact introuvable.");
  const body = s(fd, "body");
  if (!body) flash(back, "Collez le texte de la réponse reçue.");
  const channel = (CHANNELS.includes(s(fd, "channel") as Channel) ? s(fd, "channel") : "EMAIL") as Channel;

  const inbound = await db.message.create({
    data: { orgId: ctx.orgId, contactId, channel, direction: "INBOUND", status: "RECEIVED", body, sentAt: new Date() },
  });
  if (["NEW", "TO_CONTACT", "CONTACTED"].includes(contact.status)) {
    await db.contact.update({ where: { id: contactId }, data: { status: "REPLIED" } });
  }
  // Le prospect a repondu : la relance automatique n'a plus lieu d'etre.
  await db.task.updateMany({
    where: { orgId: ctx.orgId, contactId, doneAt: null, title: { startsWith: "Relancer" } },
    data: { doneAt: new Date() },
  });
  await db.activity.create({ data: { orgId: ctx.orgId, contactId, kind: "message", summary: "Réponse reçue" } });

  const res = await startRun({
    orgId: ctx.orgId,
    type: "REPLY",
    label: fullName(contact),
    work: (usage) => analyzeReply(ctx.orgId, inbound.id, usage),
  });
  flash(back, res.ok ? "Réponse enregistrée. L'agent l'analyse et prépare la suite." : `Réponse enregistrée. ${res.error}`);
}
