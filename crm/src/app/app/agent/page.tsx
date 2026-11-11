import Link from "next/link";
import { createCampaign } from "@/app/actions";
import { closeStaleRuns } from "@/lib/agent";
import { requireCtx } from "@/lib/auth";
import { db } from "@/lib/db";
import { agentConfigured } from "@/lib/llm";
import { AutoRefresh, Submit } from "@/components/client";
import { CampaignFields } from "@/components/campaign-fields";
import { Notice, PageHeader, RunList } from "@/components/ui";

export default async function Page({ searchParams }: { searchParams: Promise<{ msg?: string }> }) {
  const ctx = await requireCtx();
  const { msg } = await searchParams;
  await closeStaleRuns(ctx.orgId);
  const [campaigns, runs, org] = await Promise.all([
    db.campaign.findMany({ where: { orgId: ctx.orgId }, include: { _count: { select: { companies: true, messages: true } } }, orderBy: { createdAt: "desc" } }),
    db.agentRun.findMany({ where: { orgId: ctx.orgId }, orderBy: { createdAt: "desc" }, take: 12 }),
    db.organization.findUniqueOrThrow({ where: { id: ctx.orgId } }),
  ]);
  return (
    <>
      <AutoRefresh active={runs.some((r) => r.status === "RUNNING")} />
      <PageHeader title="Agent IA" subtitle="Une campagne décrit une cible. L'agent cherche les entreprises sur le web, les qualifie et rédige les messages." />
      <Notice msg={msg} />
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
                    <p className="font-medium">{c.name}</p>
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
            <RunList runs={runs} />
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
