import Link from "next/link";
import type { Company, Contact, Message } from "@prisma/client";
import { CHANNEL_LABEL, fullName } from "@/lib/labels";
import { appUrl, canAutoSend, emailFooter } from "@/lib/send";
import { isTrial } from "@/lib/plan";
import { DraftEditor } from "./draft-editor";

export async function DraftCard({
  message,
  contact,
  legalFooter,
  back,
  showContact = true,
}: {
  message: Message;
  contact: Contact & { company?: Company | null };
  legalFooter: string;
  back: string;
  showContact?: boolean;
}) {
  // Offre gratuite : jamais d'envoi par le serveur de l'application, seulement depuis la messagerie de l'utilisateur.
  const autoSend = canAutoSend(message.channel) && !(await isTrial(message.orgId));
  const missing =
    message.channel === "EMAIL" ? !contact.email : message.channel === "SMS" || message.channel === "WHATSAPP" ? !contact.phone : false;
  return (
    <article className="card p-4">
      <header className="mb-3 flex flex-wrap items-center gap-2 text-sm">
        <span className="rounded-md bg-white/10 px-2 py-0.5 text-xs font-medium text-white">{CHANNEL_LABEL[message.channel]}</span>
        {message.step > 1 && <span className="rounded-md bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">Relance {message.step - 1}</span>}
        {message.aiGenerated && <span className="rounded-md bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">Rédigé par l'agent</span>}
        {showContact && (
          <span className="text-slate-600">
            pour{" "}
            <Link href={`/app/prospects/${contact.id}`} className="font-medium text-slate-900 hover:text-brand-600 hover:underline">
              {fullName(contact)}
            </Link>
            {contact.company ? ` · ${contact.company.name}` : ""}
          </span>
        )}
        <span className="ml-auto text-xs text-slate-500">
          {message.channel === "EMAIL" ? contact.email : message.channel === "LINKEDIN" ? "" : contact.phone}
          {missing && <span className="text-rose-600">Coordonnée manquante</span>}
        </span>
      </header>
      <DraftEditor
        id={message.id}
        channel={message.channel}
        subject={message.subject}
        body={message.body}
        contact={{ email: contact.email, phone: contact.phone, linkedinUrl: contact.linkedinUrl }}
        autoSend={autoSend}
        emailFooter={emailFooter(legalFooter, `${appUrl()}/desinscription/${contact.unsubscribeToken}`)}
        blocked={contact.doNotContact}
        error={message.error}
        back={back}
      />
    </article>
  );
}
