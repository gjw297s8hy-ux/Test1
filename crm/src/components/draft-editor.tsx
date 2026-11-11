"use client";

import { useState } from "react";
import type { Channel } from "@prisma/client";
import { discardDraft, markMessageSent, saveDraft, sendMessageNow } from "@/app/actions";
import { manualLink } from "@/lib/links";
import { CopyButton, Submit } from "./client";

const OPEN_LABEL: Record<Channel, string> = {
  EMAIL: "Ouvrir dans ma messagerie",
  LINKEDIN: "Ouvrir le profil LinkedIn",
  SMS: "Ouvrir dans Messages",
  WHATSAPP: "Ouvrir dans WhatsApp",
};

const LIMIT: Partial<Record<Channel, number>> = { LINKEDIN: 300, SMS: 320 };

export function DraftEditor({
  id,
  channel,
  subject: initialSubject,
  body: initialBody,
  contact,
  autoSend,
  emailFooter,
  blocked,
  error,
  back,
}: {
  id: string;
  channel: Channel;
  subject: string;
  body: string;
  contact: { email: string; phone: string; linkedinUrl: string };
  /** Vrai si l'application peut envoyer elle-meme sur ce canal. */
  autoSend: boolean;
  emailFooter: string;
  blocked: boolean;
  error: string;
  back: string;
}) {
  const [subject, setSubject] = useState(initialSubject);
  const [body, setBody] = useState(initialBody);
  const full = channel === "EMAIL" ? body + emailFooter : body;
  const link = manualLink(channel, contact, subject, full);
  const limit = LIMIT[channel];

  return (
    <form className="space-y-3">
      <input type="hidden" name="id" value={id} />
      <input type="hidden" name="back" value={back} />
      {channel === "EMAIL" && (
        <input className="input font-medium" name="subject" aria-label="Objet" placeholder="Objet" value={subject} onChange={(e) => setSubject(e.target.value)} />
      )}
      <textarea
        className="input min-h-36 leading-relaxed"
        name="body"
        aria-label="Message"
        rows={channel === "EMAIL" ? 9 : 4}
        value={body}
        onChange={(e) => setBody(e.target.value)}
      />
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
        <span>
          {channel === "EMAIL"
            ? "Votre mention légale et le lien de désinscription sont ajoutés à l'envoi."
            : channel === "LINKEDIN"
              ? "LinkedIn : envoi manuel depuis votre compte."
              : ""}
        </span>
        <span className={limit && body.length > limit ? "font-medium text-rose-600" : ""}>
          {body.length} caractères{limit ? ` / ${limit}` : ""}
        </span>
      </div>
      {error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-800">Dernier essai : {error}</p>}
      {blocked ? (
        <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-800">Ce contact s'est opposé à la prospection : envoi bloqué.</p>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          {autoSend ? (
            <Submit formAction={sendMessageNow} pendingText="Envoi…">
              Valider et envoyer
            </Submit>
          ) : (
            <>
              {link && (
                <a className="btn" href={link} target="_blank" rel="noopener noreferrer">
                  {OPEN_LABEL[channel]}
                </a>
              )}
              <CopyButton text={full} label="Copier le texte" />
              <Submit formAction={markMessageSent} className="btn-ghost">
                Marquer comme envoyé
              </Submit>
            </>
          )}
          <Submit formAction={saveDraft} className="btn-ghost">
            Enregistrer
          </Submit>
          <Submit formAction={discardDraft} className="btn-danger">
            Écarter
          </Submit>
        </div>
      )}
    </form>
  );
}
