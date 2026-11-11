import Link from "next/link";
import { createCampaign, createCampaignFromIdea, discardIdea, launchIdeas } from "@/app/actions";
import { GOALS } from "@/lib/goals";
import { closeStaleRuns } from "@/lib/agent";
import { requireCtx } from "@/lib/auth";
import { db } from "@/lib/db";
import { agentConfigured } from "@/lib/llm";
import { isTrial, isSiteAdmin } from "@/lib/plan";
import { AutoRefresh, Submit } from "@/components/client";
import { CampaignFields } from "@/components/campaign-fields";
import { Notice, PageHeader, RunList, TrialNotice } from "@/components/ui";

export default async function Page({ searchParams }: { searchParams: Promise<{ msg?: string }> }) {
  const ctx = await requireCtx();
  const { msg } = await searchParams;
  await closeStaleRuns(ctx.orgId);
  const [campaigns, runs, org, trial, ideas] = await Promise.all([
    db.campaign.findMany({ where: { orgId: ctx.orgId }, include: { _count: { select: { companies: true, messages: true } } }, orderBy: { createdAt: "desc" } }),
    db.agentRun.findMany({ where: { orgId: ctx.orgId }, orderBy: { createdAt: "desc" }, take: 12 }),
    db.organization.findUniqueOrThrow({ where: { id: ctx.orgId } }),
    isTrial(ctx.orgId),
    db.idea.findMany({ where: { orgId: ctx.orgId, usedAt: null }, orderBy: [{ createdAt: "desc" }, { rank: "asc" }], take: 8 }),
  ]);
  const ideasRunning = runs.some((r) => r.type === "IDEAS" && r.status === "RUNNING");
  return (
    <>
      <AutoRefresh active={runs.some((r) => r.status === "RUNNING")} />
      <PageHeader title="Agent IA" subtitle="Une campagne décrit une cible. L'agent cherche les entreprises sur le web, les qualifie et rédige les messages." />
      <Notice msg={msg} />
      {trial && <TrialNotice />}
      {!agentConfigured() && (
        <p className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-900">
          L'agent n'est pas encore branché : ajoutez la variable <code>ANTHROPIC_API_KEY</code> sur le serveur. Le reste du CRM fonctionne sans.
        </p>
      )}
      {!org.offer && (
        <p className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-900">
          Décrivez votre offre dans les{" "}
          <Link href="/app/parametres" className="font-medium underline">
            paramètres
          </Link>{" "}
          : sans elle, le ciblage et les messages restent génériques.
        </p>
      )}

      <section className="card relative mb-8 overflow-hidden p-6">
        <div aria-hidden className="pointer-events-none absolute -top-24 -right-24 h-64 w-64 rounded-full bg-violet/25 blur-[90px]" />
        <div className="relative grid gap-6 lg:grid-cols-[1fr_1.3fr]">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-pink">Par où commencer ?</p>
            <h2 className="mt-1 text-xl font-semibold">Trouver des idées de débouchés</h2>
            <p className="mt-2 text-sm text-slate-500">
              Décrivez votre activité : l'agent propose des pistes concrètes de clients, de sous-traitance, de points de vente ou de partenariats. Chaque piste devient une campagne en un clic.
            </p>
            <form action={launchIdeas} className="mt-4 space-y-3">
              <textarea
                className="input"
                name="activity"
                rows={3}
                defaultValue={org.offer}
                placeholder="Exemple : pâtisserie artisanale à Lyon, gâteaux de fête et viennoiseries, livraison possible dans la journée."
                required
              />
              <input className="input" name="location" placeholder="Zone : Lyon et alentours (facultatif)" />
              <Submit pendingText="Lancement…" disabled={ideasRunning}>
                {ideasRunning ? "L'agent réfléchit…" : "Proposer des idées"}
              </Submit>
            </form>
          </div>
          <div>
            {ideas.length === 0 ? (
              <div className="grid h-full place-items-center rounded-2xl border border-dashed border-white/10 p-6 text-center text-sm text-slate-500">
                {ideasRunning ? "L'agent prépare vos pistes…" : "Vos pistes de débouchés apparaîtront ici."}
              </div>
            ) : (
              <ul className="grid gap-3 sm:grid-cols-2">
                {ideas.map((idea) => (
                  <li key={idea.id} className="flex flex-col rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                    <span className="self-start rounded-full bg-violet/20 px-2 py-0.5 text-[11px] font-semibold text-brand-700">{GOALS[idea.goal].short}</span>
                    <p className="mt-2 text-sm font-semibold">{idea.title}</p>
                    <p className="mt-1 flex-1 text-xs text-slate-500">{idea.why}</p>
                    <div className="mt-3 flex gap-2">
                      <form action={createCampaignFromIdea}>
                        <input type="hidden" name="id" value={idea.id} />
                        <Submit className="btn px-3 py-1.5 text-xs" pendingText="Création…">
                          Créer la campagne
                        </Submit>
                      </form>
                      <form action={discardIdea}>
                        <input type="hidden" name="id" value={idea.id} />
                        <Submit className="btn-ghost px-3 py-1.5 text-xs">Écarter</Submit>
                      </form>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section>
          <h2 className="mb-3 text-sm font-semibold">Campagnes</h2>
          {campaigns.length === 0 ? (
            <div className="card px-6 py-8 text-center text-sm text-slate-500">Aucune campagne. Créez la première ci-contre.</div>
          ) : (
            <ul className="space-y-3">
              {campaigns.map((c) => (
                <li key={c.id}>
                  <Link href={`/app/agent/${c.id}`} className="card block p-4 transition hover:border-brand-500">
                    <p className="flex items-center gap-2 font-medium">{c.name}<span className="rounded-full bg-white/10 px-2 py-0.5 text-[11px] font-medium text-slate-600">{GOALS[c.goal].short}</span></p>
                    <p className="mt-0.5 text-sm text-slate-500">{[c.industry, c.location].filter(Boolean).join(" · ")}</p>
                    <p className="mt-2 text-xs text-slate-500">
                      {c._count.companies} entreprise{c._count.companies > 1 ? "s" : ""} · {c._count.messages} message{c._count.messages > 1 ? "s" : ""}
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
          )}
          <h2 className="mb-3 mt-8 text-sm font-semibold">Activité de l'agent</h2>
          <div className="card">
            <RunList runs={runs} showCost={isSiteAdmin(ctx.userEmail)} />
          </div>
        </section>

        <section>
          <h2 className="mb-3 text-sm font-semibold">Nouvelle campagne</h2>
          <form action={createCampaign} className="card space-y-4 p-4">
            <CampaignFields />
            <Submit>Créer la campagne</Submit>
          </form>
        </section>
      </div>
    </>
  );
}
