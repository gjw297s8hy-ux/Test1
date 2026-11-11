import { notFound } from "next/navigation";
import { createTask, deleteContact, launchDraft, registerReply, updateContact } from "@/app/actions";
import { REPLY_LABEL, closeStaleRuns } from "@/lib/agent";
import { requireCtx } from "@/lib/auth";
import { db } from "@/lib/db";
import { CHANNELS, CHANNEL_LABEL, CONTACT_STATUSES, MESSAGE_STATUS_LABEL, STATUS_LABEL, fmtDateTime, fullName } from "@/lib/labels";
import { AutoRefresh, ConfirmSubmit, Submit } from "@/components/client";
import { DraftCard } from "@/components/draft-card";
import { TaskList } from "@/components/task-list";
import { ExtLink, Notice, PageHeader, ScoreBadge, StatusBadge, TextLink } from "@/components/ui";

export default async function Page({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<{ msg?: string }> }) {
  const ctx = await requireCtx();
  const { id } = await params;
  const { msg } = await searchParams;
  await closeStaleRuns(ctx.orgId);
  const contact = await db.contact.findFirst({
    where: { id, orgId: ctx.orgId },
    include: {
      company: true,
      messages: { orderBy: { createdAt: "desc" } },
      tasks: { orderBy: [{ doneAt: { sort: "asc", nulls: "first" } }, { dueAt: "asc" }], take: 20 },
      activities: { orderBy: { createdAt: "desc" }, take: 20 },
    },
  });
  if (!contact) notFound();
  const [org, companies, running] = await Promise.all([
    db.organization.findUniqueOrThrow({ where: { id: ctx.orgId } }),
    db.company.findMany({ where: { orgId: ctx.orgId }, select: { id: true, name: true }, orderBy: { name: "asc" }, take: 500 }),
    db.agentRun.count({ where: { orgId: ctx.orgId, status: "RUNNING", type: { in: ["DRAFT", "REPLY"] } } }),
  ]);
  const back = `/app/prospects/${contact.id}`;
  const drafts = contact.messages.filter((m) => m.status === "DRAFT");
  const history = contact.messages.filter((m) => m.status === "SENT" || m.status === "RECEIVED" || m.status === "FAILED");
  const alreadyContacted = history.some((m) => m.direction === "OUTBOUND");
  const usable = (ch: (typeof CHANNELS)[number]) => (ch === "EMAIL" ? !!contact.email : ch === "LINKEDIN" ? true : !!contact.phone);

  return (
    <>
      <AutoRefresh active={running > 0} />
      <PageHeader title={fullName(contact)} subtitle={[contact.jobTitle, contact.company?.name].filter(Boolean).join(" · ")}>
        <StatusBadge status={contact.status} />
        {contact.doNotContact && <span className="rounded-full bg-rose-600 px-2 py-0.5 text-xs font-medium text-white">Ne pas contacter</span>}
      </PageHeader>
      <Notice msg={msg} />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {!contact.doNotContact && (
            <section className="card p-4">
              <h2 className="text-sm font-semibold">{alreadyContacted ? "Préparer une relance" : "Préparer un premier message"}</h2>
              <p className="mt-1 text-sm text-slate-500">L'agent rédige à partir de la fiche de l'entreprise et des échanges précédents. Vous validez avant l'envoi.</p>
              <form action={launchDraft} className="mt-3 flex flex-wrap items-center gap-3 text-sm">
                <input type="hidden" name="contactId" value={contact.id} />
                <input type="hidden" name="back" value={back} />
                {CHANNELS.map((ch) => (
                  <label key={ch} className={`flex items-center gap-1.5 ${usable(ch) ? "" : "text-slate-400"}`} title={usable(ch) ? undefined : "Coordonnée manquante"}>
                    <input type="checkbox" name="channels" value={ch} defaultChecked={ch === "EMAIL" && usable(ch)} disabled={!usable(ch)} /> {CHANNEL_LABEL[ch]}
                  </label>
                ))}
                <Submit pendingText="Lancement…">Rédiger avec l'agent</Submit>
              </form>
            </section>
          )}

          {running > 0 && <p className="text-sm text-amber-700">L'agent travaille : la page se met à jour toute seule.</p>}

          {drafts.length > 0 && (
            <section className="space-y-3">
              <h2 className="text-sm font-semibold">Brouillons à valider</h2>
              {drafts.map((m) => (
                <DraftCard key={m.id} message={m} contact={contact} legalFooter={org.legalFooter} back={back} showContact={false} />
              ))}
            </section>
          )}

          <section className="card p-4">
            <h2 className="text-sm font-semibold">Le prospect a répondu ?</h2>
            <p className="mt-1 text-sm text-slate-500">Collez sa réponse : l'agent la classe, met la fiche à jour, crée la tâche suivante et propose une réponse.</p>
            <form action={registerReply} className="mt-3 space-y-3">
              <input type="hidden" name="contactId" value={contact.id} />
              <textarea className="input" name="body" rows={4} placeholder="Texte de la réponse reçue" required />
              <div className="flex flex-wrap items-center gap-3">
                <select className="input w-auto" name="channel" defaultValue="EMAIL" aria-label="Canal de la réponse">
                  {CHANNELS.map((ch) => (
                    <option key={ch} value={ch}>
                      Reçue par {CHANNEL_LABEL[ch]}
                    </option>
                  ))}
                </select>
                <Submit pendingText="Enregistrement…">Enregistrer et analyser</Submit>
              </div>
            </form>
          </section>

          <section className="card">
            <h2 className="border-b border-slate-100 px-4 py-3 text-sm font-semibold">Échanges</h2>
            {history.length === 0 ? (
              <p className="px-4 py-6 text-sm text-slate-500">Aucun échange pour l'instant.</p>
            ) : (
              <ul className="divide-y divide-slate-100">
                {history.map((m) => (
                  <li key={m.id} className={`px-4 py-3 text-sm ${m.direction === "INBOUND" ? "bg-emerald-50/50" : ""}`}>
                    <p className="mb-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                      <span className="font-medium text-slate-700">
                        {m.direction === "INBOUND" ? "Reçu" : MESSAGE_STATUS_LABEL[m.status]} · {CHANNEL_LABEL[m.channel]}
                      </span>
                      {m.step > 1 && m.direction === "OUTBOUND" && <span>Relance {m.step - 1}</span>}
                      {m.classification && m.classification in REPLY_LABEL && (
                        <span className="rounded-full bg-emerald-100 px-2 py-0.5 font-medium text-emerald-800">
                          {REPLY_LABEL[m.classification as keyof typeof REPLY_LABEL]}
                        </span>
                      )}
                      <span className="ml-auto">{fmtDateTime(m.sentAt ?? m.createdAt)}</span>
                    </p>
                    {m.subject && <p className="font-medium">{m.subject}</p>}
                    <p className="whitespace-pre-wrap text-slate-700">{m.body}</p>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="card">
            <h2 className="border-b border-slate-100 px-4 py-3 text-sm font-semibold">Tâches</h2>
            {contact.tasks.length > 0 && <TaskList tasks={contact.tasks} showContact={false} />}
            <form action={createTask} className="flex flex-wrap items-end gap-3 border-t border-slate-100 p-4">
              <input type="hidden" name="contactId" value={contact.id} />
              <input type="hidden" name="back" value={back} />
              <label className="min-w-48 flex-1">
                <span className="label">Nouvelle tâche</span>
                <input className="input" name="title" required />
              </label>
              <label>
                <span className="label">Échéance</span>
                <input className="input" type="date" name="dueAt" />
              </label>
              <Submit className="btn-ghost">Ajouter</Submit>
            </form>
          </section>
        </div>

        <div className="space-y-6">
          {contact.company && (
            <section className="card p-4 text-sm">
              <div className="flex items-center justify-between gap-2">
                <TextLink href={`/app/entreprises/${contact.company.id}`}>{contact.company.name}</TextLink>
                <ScoreBadge score={contact.company.score} />
              </div>
              <p className="mt-2 text-slate-600">{contact.company.description || "Fiche non enrichie."}</p>
              {contact.company.scoreReason && <p className="mt-2 text-xs text-slate-500">{contact.company.scoreReason}</p>}
            </section>
          )}

          <form key={contact.updatedAt.getTime()} action={updateContact} className="card space-y-3 p-4">
            <h2 className="text-sm font-semibold">Fiche</h2>
            <input type="hidden" name="id" value={contact.id} />
            <div className="grid grid-cols-2 gap-3">
              <label><span className="label">Prénom</span><input className="input" name="firstName" defaultValue={contact.firstName} /></label>
              <label><span className="label">Nom</span><input className="input" name="lastName" defaultValue={contact.lastName} /></label>
            </div>
            <label className="block"><span className="label">Fonction</span><input className="input" name="jobTitle" defaultValue={contact.jobTitle} /></label>
            <label className="block"><span className="label">E-mail</span><input className="input" type="email" name="email" defaultValue={contact.email} /></label>
            <label className="block"><span className="label">Téléphone</span><input className="input" name="phone" defaultValue={contact.phone} /></label>
            <label className="block"><span className="label">Profil LinkedIn</span><input className="input" name="linkedinUrl" defaultValue={contact.linkedinUrl} /></label>
            <label className="block">
              <span className="label">Entreprise</span>
              <select className="input" name="companyId" defaultValue={contact.companyId ?? ""}>
                <option value="">Aucune</option>
                {companies.map((co) => (
                  <option key={co.id} value={co.id}>{co.name}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="label">Étape</span>
              <select className="input" name="status" defaultValue={contact.status}>
                {CONTACT_STATUSES.map((s) => (
                  <option key={s} value={s}>{STATUS_LABEL[s]}</option>
                ))}
              </select>
            </label>
            <label className="block"><span className="label">Tags (séparés par des virgules)</span><input className="input" name="tags" defaultValue={contact.tags.join(", ")} /></label>
            <label className="block"><span className="label">Notes</span><textarea className="input" name="notes" rows={3} defaultValue={contact.notes} /></label>
            <label className="flex items-start gap-2 text-sm">
              <input type="checkbox" name="doNotContact" defaultChecked={contact.doNotContact} className="mt-1" />
              <span>Ne pas contacter <span className="block text-xs text-slate-500">Opposition à la prospection : bloque tout envoi.</span></span>
            </label>
            <Submit>Enregistrer</Submit>
          </form>

          <section className="card p-4 text-sm">
            <h2 className="text-sm font-semibold">Origine des données</h2>
            <p className="mt-1 break-words text-slate-600">
              {contact.sourceUrl ? <ExtLink href={contact.sourceUrl}>{contact.sourceUrl}</ExtLink> : "Non renseignée"}
            </p>
            <p className="mt-1 text-xs text-slate-500">Ajouté le {fmtDateTime(contact.createdAt)}</p>
            <form action={deleteContact} className="mt-3">
              <input type="hidden" name="id" value={contact.id} />
              <ConfirmSubmit message="Supprimer définitivement ce contact et tout son historique ?">Supprimer le contact</ConfirmSubmit>
            </form>
          </section>

          <section className="card">
            <h2 className="border-b border-slate-100 px-4 py-3 text-sm font-semibold">Historique</h2>
            <ul className="divide-y divide-slate-100">
              {contact.activities.map((a) => (
                <li key={a.id} className="px-4 py-2.5 text-sm">
                  <p className="text-slate-700">{a.summary}</p>
                  <p className="text-xs text-slate-400">{fmtDateTime(a.createdAt)}</p>
                </li>
              ))}
              {contact.activities.length === 0 && <li className="px-4 py-4 text-sm text-slate-500">Rien pour l'instant.</li>}
            </ul>
          </section>
        </div>
      </div>
    </>
  );
}
