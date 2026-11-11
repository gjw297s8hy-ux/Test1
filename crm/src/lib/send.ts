import nodemailer from "nodemailer";
import type { Channel } from "@prisma/client";
import { toE164 } from "./links";

export function appUrl(): string {
  return (process.env.APP_URL || "http://localhost:3000").replace(/\/$/, "");
}

export function smtpConfigured(): boolean {
  return Boolean(process.env.SMTP_URL && process.env.SMTP_FROM);
}

export function twilioConfigured(channel: "SMS" | "WHATSAPP"): boolean {
  const from = channel === "SMS" ? process.env.TWILIO_SMS_FROM : process.env.TWILIO_WHATSAPP_FROM;
  return Boolean(process.env.TWILIO_ACCOUNT_SID && process.env.TWILIO_AUTH_TOKEN && from);
}

/** Vrai si l'application peut envoyer elle-meme sur ce canal ; sinon l'envoi est manuel. */
export function canAutoSend(channel: Channel): boolean {
  if (channel === "EMAIL") return smtpConfigured();
  if (channel === "SMS" || channel === "WHATSAPP") return twilioConfigured(channel);
  return false; // LinkedIn : toujours manuel, l'automatisation est contraire a leurs conditions.
}

/** Pied ajoute a chaque e-mail : identite de l'expediteur et lien d'opposition (RGPD). */
export function emailFooter(legalFooter: string, unsubscribeUrl: string): string {
  return `\n\n--\n${legalFooter ? `${legalFooter}\n` : ""}Pour ne plus recevoir nos messages : ${unsubscribeUrl}`;
}

export async function sendEmail(opts: {
  to: string;
  subject: string;
  body: string;
  senderName: string;
  replyTo: string;
  footer: string;
  unsubscribeUrl: string;
}): Promise<void> {
  const transport = nodemailer.createTransport(process.env.SMTP_URL!);
  const text = opts.body + emailFooter(opts.footer, opts.unsubscribeUrl);
  await transport.sendMail({
    from: opts.senderName ? { name: opts.senderName, address: process.env.SMTP_FROM! } : process.env.SMTP_FROM!,
    to: opts.to,
    replyTo: opts.replyTo || undefined,
    subject: opts.subject,
    text,
    headers: { "List-Unsubscribe": `<${opts.unsubscribeUrl}>` },
  });
}

export async function sendTwilio(channel: "SMS" | "WHATSAPP", phone: string, body: string): Promise<void> {
  const sid = process.env.TWILIO_ACCOUNT_SID!;
  const to = toE164(phone);
  const from = channel === "SMS" ? process.env.TWILIO_SMS_FROM! : process.env.TWILIO_WHATSAPP_FROM!;
  const params = new URLSearchParams({
    To: channel === "WHATSAPP" ? `whatsapp:${to}` : to,
    From: channel === "WHATSAPP" ? `whatsapp:${from.replace(/^whatsapp:/, "")}` : from,
    Body: body,
  });
  const res = await fetch(`https://api.twilio.com/2010-04-01/Accounts/${sid}/Messages.json`, {
    method: "POST",
    headers: {
      Authorization: `Basic ${Buffer.from(`${sid}:${process.env.TWILIO_AUTH_TOKEN}`).toString("base64")}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: params,
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => null)) as { message?: string } | null;
    throw new Error(detail?.message || `Twilio a répondu ${res.status}`);
  }
}
