import type { Channel } from "@prisma/client";

/** Numero francais vers le format international E.164 (06 12 34 56 78 -> +33612345678). */
export function toE164(phone: string): string {
  const digits = phone.replace(/[^\d+]/g, "");
  if (digits.startsWith("+")) return digits;
  if (digits.startsWith("00")) return `+${digits.slice(2)}`;
  if (digits.startsWith("0") && digits.length === 10) return `+33${digits.slice(1)}`;
  return digits;
}

/** Lien qui ouvre l'application de l'utilisateur avec le message pre-rempli (envoi manuel). */
export function manualLink(channel: Channel, c: { email: string; phone: string; linkedinUrl: string }, subject: string, body: string): string {
  switch (channel) {
    case "EMAIL":
      return c.email ? `mailto:${c.email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}` : "";
    case "SMS":
      return c.phone ? `sms:${toE164(c.phone)}?body=${encodeURIComponent(body)}` : "";
    case "WHATSAPP":
      return c.phone ? `https://wa.me/${toE164(c.phone).replace("+", "")}?text=${encodeURIComponent(body)}` : "";
    case "LINKEDIN":
      return c.linkedinUrl;
  }
}
