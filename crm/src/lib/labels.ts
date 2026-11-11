import type { Channel, ContactStatus, MessageStatus, RunType } from "@prisma/client";

export const STATUS_LABEL: Record<ContactStatus, string> = {
  NEW: "Nouveau",
  TO_CONTACT: "À contacter",
  CONTACTED: "Contacté",
  REPLIED: "A répondu",
  INTERESTED: "Intéressé",
  MEETING: "RDV pris",
  CUSTOMER: "Client",
  NOT_INTERESTED: "Pas intéressé",
};

export const STATUS_TONE: Record<ContactStatus, string> = {
  NEW: "bg-slate-100 text-slate-700",
  TO_CONTACT: "bg-amber-100 text-amber-800",
  CONTACTED: "bg-sky-100 text-sky-800",
  REPLIED: "bg-violet-100 text-violet-800",
  INTERESTED: "bg-emerald-100 text-emerald-800",
  MEETING: "bg-emerald-200 text-emerald-900",
  CUSTOMER: "bg-green-600 text-white",
  NOT_INTERESTED: "bg-rose-100 text-rose-800",
};

export const CHANNEL_LABEL: Record<Channel, string> = {
  EMAIL: "E-mail",
  LINKEDIN: "LinkedIn",
  SMS: "SMS",
  WHATSAPP: "WhatsApp",
};

export const MESSAGE_STATUS_LABEL: Record<MessageStatus, string> = {
  DRAFT: "Brouillon",
  SENT: "Envoyé",
  FAILED: "Échec",
  DISCARDED: "Écarté",
  RECEIVED: "Reçu",
};

export const RUN_LABEL: Record<RunType, string> = {
  FIND: "Recherche de prospects",
  ENRICH: "Enrichissement et score",
  DRAFT: "Rédaction",
  REPLY: "Analyse de réponse",
};

export const CONTACT_STATUSES = Object.keys(STATUS_LABEL) as ContactStatus[];
export const CHANNELS = Object.keys(CHANNEL_LABEL) as Channel[];

export function fullName(c: { firstName: string; lastName: string }): string {
  return `${c.firstName} ${c.lastName}`.trim() || "Contact sans nom";
}

const dateFmt = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short", year: "numeric", timeZone: "Europe/Paris" });
const dateTimeFmt = new Intl.DateTimeFormat("fr-FR", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Europe/Paris",
});

export function fmtDate(d: Date | null | undefined): string {
  return d ? dateFmt.format(d) : "";
}

export function fmtDateTime(d: Date | null | undefined): string {
  return d ? dateTimeFmt.format(d) : "";
}

export function domainOf(url: string): string {
  if (!url) return "";
  try {
    const u = new URL(url.includes("://") ? url : `https://${url}`);
    return u.hostname.replace(/^www\./, "").toLowerCase();
  } catch {
    return "";
  }
}
