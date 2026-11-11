import { notFound } from "next/navigation";
import { deleteCompany, launchEnrich, updateCompany } from "@/app/actions";
import { closeStaleRuns } from "@/lib/agent";
import { requireCtx } from "@/lib/auth";
import { db } from "@/lib/db";
import { fmtDateTime, fullName } from "@/lib/labels";
import { AutoRefresh, ConfirmSubmit, Submit } from "@/components/client";
import { ExtLink, Notice, PageHeader, ScoreBadge, StatusBadge, TextLink } from "@/components/ui";

/** Rend cliquables les URL que l'agent cite dans ses notes. */
function Linkified({ text }: { text: string }) {
  return (
    <>
      {text.split(/(https?:\/\/[^\s)]+)/g).map((part, i) =>
        /^https?:\/\//.test(part) ? (
          <ExtLink key={i} href={part}>
            source
          </ExtLink>
        ) : (
          part
        ),
      )}
    </>
  );
}

export default async function Page({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<{ msg?: string }> }) {
  const ctx = await requireCtx();
  const { id } = await params;
  const { msg } = await searchParams;
  await closeStaleRuns(ctx.orgId);
  const company = await db.company.findFirst({
    where: { id, orgId: ctx.orgId },
    include: { contacts: { orderBy: { createdAt: "asc" } }, campaign: true, activities: { orderBy: { createdAt: "desc" }, take: 10 } },
  });
  if (!company) notFound();
  const running = await db.agentRun.count({ where: { orgId: ctx.orgId, status: "RUNNING", type: "ENRICH" } });
  const back = `/app/entreprises/${company.id}`;

  return (
    <>
      <AutoRefresh active={running > 0} />
      <PageHeader title={company.name} subtitle={[company.industry, company.city, company.size].filter(Boolean).join(" · ")}>
        <ScoreBadge score={company.score} />
        <form action={launchEnrich}>
          <input type="hidden" name="companyId" value={company.id} />
          <input type="hidden" name="back" value={back} />
          <Submit pendingText="Lancement…">{company.enrichedAt ? "Approfondir à nouveau" : "Approfondir avec l'agent"}</Submit>
        </form>
      </PageHeader>
      <Notice msg={msg} />
      {running > 0 && <p className="mb-4 text-sm text-amber-700">L'agent travaille : la page se met à jour toute seule.</p>}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <section className="card p-4 text-sm">
            <h2 className="text-sm font-semibold">Analyse de l'agent</h2>
            {company.scoreReason || company.insights ? (
              <>
                {company.scoreReason && <p className="mt-2 text-slate-700">{company.scoreReason}</p>}
                {company.insights && (
                  <>
                    <h3 className="mt-4 text-xs font-medium uppercase tracking-wide text-slate-500">Signaux pour l'accroche</h3>
                    <p className="mt-1 whitespace-pre-wrap break-words text-slate-700">
                      <Linkified text={company.insights} />
                    </p>
                  </>
                )}
                {company.enrichedAt && <p className="mt-3 text-xs text-slate-400">Enrichie le {fmtDateTime(company.enrichedAt)}. À vérifier avant de vous en servir.</p>}
              </>
            ) : (
              <p className="mt-2 text-slate-500">Pas encore enrichie. L'agent peut rechercher l'activité, les actualités et les interlocuteurs, puis attribuer un score.</p>
            )}
          </section>

          <section className="card">
            <h2 className="border-b border-white/[0.06] px-5 py-4 font-display text-[15px] font-semibold">Contacts</h2>
            {company.contacts.length === 0 ? (
              <p className="px-4 py-6 text-sm text-slate-500">Aucun contact. L'enrichissement en cherche ; vous pouvez aussi en ajouter depuis « Contacts ».</p>
            ) : (
              <ul className="divide-y divide-white/[0.06]">
                {company.contacts.map((c) => (
                  <li key={c.id} className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm">
                    <div className="min-w-0 flex-1">
                      <TextLink href={`/app/prospects/${c.id}`}>{fullName(c)}</TextLink>
                      <p className="text-xs text-slate-500">{[c.jobTitle, c.email, c.phone].filter(Boolean).join(" · ")}</p>
                    </div>
                    <StatusBadge status={c.status} />
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>

        <div className="space-y-6">
          <form action={updateCompany} className="card space-y-3 p-4">
            <h2 className="text-sm font-semibold">Fiche</h2>
            <input type="hidden" name="id" value={company.id} />
            <label className="block"><span className="label">Nom</span><input className="input" name="name" defaultValue={company.name} required /></label>
            <label className="block"><span className="label">Site web</span><input className="input" name="website" defaultValue={company.website} /></label>
            <label className="block"><span className="label">Secteur</span><input className="input" name="industry" defaultValue={company.industry} /></label>
            <div className="grid grid-cols-2 gap-3">
              <label><span className="label">Ville</span><input className="input" name="city" defaultValue={company.city} /></label>
              <label><span className="label">Taille</span><input className="input" name="size" defaultValue={company.size} /></label>
            </div>
            <label className="block"><span className="label">Téléphone</span><input className="input" name="phone" defaultValue={company.phone} /></label>
            <label className="block"><span className="label">Activité</span><textarea className="input" name="description" rows={3} defaultValue={company.description} /></label>
            <label className="block"><span className="label">Tags (séparés par des virgules)</span><input className="input" name="tags" defaultValue={company.tags.join(", ")} /></label>
            <Submit>Enregistrer</Submit>
          </form>

          <section className="card p-4 text-sm">
            <h2 className="text-sm font-semibold">Origine</h2>
            {company.campaign && (
              <p className="mt-1 text-slate-600">
                Campagne : <TextLink href={`/app/agent/${company.campaign.id}`}>{company.campaign.name}</TextLink>
              </p>
            )}
            <p className="mt-1 break-words text-slate-600">{company.sourceUrl ? <ExtLink href={company.sourceUrl}>{company.sourceUrl}</ExtLink> : "Saisie manuelle"}</p>
            {company.website && (
              <p className="mt-1">
                <ExtLink href={company.website.includes("://") ? company.website : `https://${company.website}`}>Ouvrir le site</ExtLink>
              </p>
            )}
            <form action={deleteCompany} className="mt-3">
              <input type="hidden" name="id" value={company.id} />
              <ConfirmSubmit message="Supprimer cette entreprise ? Ses contacts sont conservés, sans entreprise.">Supprimer l'entreprise</ConfirmSubmit>
            </form>
          </section>
        </div>
      </div>
    </>
  );
}
