import { notFound } from "next/navigation";
import { deleteCampaign, launchDraft, launchEnrich, launchFind, updateCampaign } from "@/app/actions";
import { closeStaleRuns } from "@/lib/agent";
import { requireCtx } from "@/lib/auth";
import { db } from "@/lib/db";
import { CHANNEL_LABEL } from "@/lib/labels";
import { AutoRefresh, ConfirmSubmit, Submit } from "@/components/client";
import { CampaignFields } from "@/components/campaign-fields";
import { Notice, PageHeader, RunList, ScoreBadge, TextLink, TrialNotice } from "@/components/ui";
import { isTrial, isSiteAdmin } from "@/lib/plan";

function Step({ n, title, hint, children }: { n: number; title: string; hint: string; children: React.ReactNode }) {
  return (
    <div className="card flex flex-col p-4">
      <p className="text-xs font-semibold text-brand-600">Étape {n}</p>
      <h3 className="mt-0.5 font-semibold">{title}</h3>
      <p className="mt-1 flex-1 text-sm text-slate-500">{hint}</p>
      <div className="mt-3">{children}</div>
    </div>
  );
}

export default async function Page({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<{ msg?: string }> }) {
  const ctx = await requireCtx();
  const { id } = await params;
  const { msg } = await searchParams;
  await closeStaleRuns(ctx.orgId);
  const campaign = await db.campaign.findFirst({ where: { id, orgId: ctx.orgId } });
  if (!campaign) notFound();
  const [companies, runs, toEnrich, toDraft, drafts, trial] = await Promise.all([
    db.company.findMany({
      where: { orgId: ctx.orgId, campaignId: id },
      include: { _count: { select: { contacts: true } } },
      orderBy: [{ score: { sort: "desc", nulls: "last" } }, { createdAt: "desc" }],
      take: 100,
    }),
    db.agentRun.findMany({ where: { orgId: ctx.orgId, campaignId: id }, orderBy: { createdAt: "desc" }, take: 8 }),
    db.company.count({ where: { orgId: ctx.orgId, campaignId: id, enrichedAt: null } }),
    db.contact.count({ where: { orgId: ctx.orgId, doNotContact: false, company: { campaignId: id }, messages: { none: {} } } }),
    db.message.count({ where: { orgId: ctx.orgId, campaignId: id, status: "DRAFT" } }),
    isTrial(ctx.orgId),
  ]);
  const back = `/app/agent/${id}`;

  return (
    <>
      <AutoRefresh active={runs.some((r) => r.status === "RUNNING")} />
      <PageHeader title={campaign.name} subtitle={[campaign.industry, campaign.location, campaign.size].filter(Boolean).join(" · ")} />
      <Notice msg={msg} />
      {trial && <TrialNotice />}

      <div className="grid gap-4 md:grid-cols-3">
        <Step n={1} title="Trouver des prospects" hint="L'agent cherche sur le web des entreprises qui correspondent à la cible, avec leurs interlocuteurs et les pages sources.">
          <form action={launchFind} className="flex items-center gap-2">
            <input type="hidden" name="campaignId" value={id} />
            {trial ? (
              <span className="text-sm text-slate-600">1 entreprise (essai)</span>
            ) : (
              <select className="input w-auto" name="count" defaultValue="10" aria-label="Nombre d'entreprises">
                <option value="5">5</option>
                <option value="10">10</option>
                <option value="20">20</option>
              </select>
            )}
            <Submit pendingText="Lancement…">Chercher</Submit>
          </form>
        </Step>
        <Step
          n={2}
          title="Approfondir (facultatif)"
          hint={`La recherche donne déjà un score. Approfondir cherche les actualités récentes et d'autres interlocuteurs : utile pour vos meilleures cibles. ${toEnrich} entreprise${toEnrich > 1 ? "s" : ""} non approfondie${toEnrich > 1 ? "s" : ""}.`}
        >
          <form action={launchEnrich}>
            <input type="hidden" name="campaignId" value={id} />
            <input type="hidden" name="back" value={back} />
            <Submit pendingText="Lancement…" disabled={toEnrich === 0}>
              Approfondir
            </Submit>
          </form>
        </Step>
        <Step
          n={3}
          title="Rédiger les messages"
          hint={`${toDraft} contact${toDraft > 1 ? "s" : ""} sans message. Canaux : ${campaign.channels.map((c) => CHANNEL_LABEL[c]).join(", ")}. ${drafts} brouillon${drafts > 1 ? "s" : ""} à valider.`}
        >
          <form action={launchDraft}>
            <input type="hidden" name="campaignId" value={id} />
            <input type="hidden" name="back" value={back} />
            <Submit pendingText="Lancement…" disabled={toDraft === 0}>
              Rédiger
            </Submit>
          </form>
        </Step>
      </div>

      <section className="card mt-6">
        <h2 className="border-b border-white/[0.06] px-5 py-4 font-display text-[15px] font-semibold">Activité de l'agent</h2>
        <RunList runs={runs} showCost={isSiteAdmin(ctx.userEmail)} />
      </section>

      <section className="card mt-6 overflow-hidden">
        <h2 className="border-b border-white/[0.06] px-5 py-4 font-display text-[15px] font-semibold">
          Entreprises trouvées <span className="font-normal text-slate-500">· {companies.length}</span>
        </h2>
        {companies.length === 0 ? (
          <p className="px-4 py-6 text-sm text-slate-500">Lancez une recherche pour remplir cette liste.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px]">
              <tbody className="divide-y divide-white/[0.06]">
                {companies.map((c) => (
                  <tr key={c.id}>
                    <td className="td">
                      <TextLink href={`/app/entreprises/${c.id}`}>{c.name}</TextLink>
                      <p className="text-xs text-slate-500">{[c.city, c.industry].filter(Boolean).join(" · ")}</p>
                    </td>
                    <td className="td max-w-md text-xs text-slate-600">{c.scoreReason}</td>
                    <td className="td whitespace-nowrap">
                      <ScoreBadge score={c.score} />
                    </td>
                    <td className="td whitespace-nowrap text-xs text-slate-500">
                      {c._count.contacts} contact{c._count.contacts > 1 ? "s" : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <details className="card mt-6">
        <summary className="cursor-pointer px-4 py-3 text-sm font-semibold">Modifier la cible et l'angle</summary>
        <form action={updateCampaign} className="space-y-4 border-t border-slate-100 p-4">
          <input type="hidden" name="id" value={id} />
          <CampaignFields campaign={campaign} />
          <Submit>Enregistrer</Submit>
        </form>
        <form action={deleteCampaign} className="border-t border-slate-100 p-4">
          <input type="hidden" name="id" value={id} />
          <ConfirmSubmit message="Supprimer cette campagne ? Les entreprises et contacts trouvés sont conservés.">Supprimer la campagne</ConfirmSubmit>
        </form>
      </details>
    </>
  );
}
