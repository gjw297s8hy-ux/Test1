import { closeStaleRuns } from "@/lib/agent";
import { requireCtx } from "@/lib/auth";
import { db } from "@/lib/db";
import { CHANNELS, CHANNEL_LABEL } from "@/lib/labels";
import Link from "next/link";
import { AutoRefresh } from "@/components/client";
import { DraftCard } from "@/components/draft-card";
import { Empty, Notice, PageHeader } from "@/components/ui";

export default async function Page({ searchParams }: { searchParams: Promise<{ msg?: string; canal?: string }> }) {
  const ctx = await requireCtx();
  const { msg, canal } = await searchParams;
  await closeStaleRuns(ctx.orgId);
  const channel = CHANNELS.find((c) => c === canal);
  const [org, drafts, running] = await Promise.all([
    db.organization.findUniqueOrThrow({ where: { id: ctx.orgId } }),
    db.message.findMany({
      where: { orgId: ctx.orgId, status: "DRAFT", ...(channel ? { channel } : {}) },
      include: { contact: { include: { company: true } } },
      orderBy: { createdAt: "desc" },
      take: 50,
    }),
    db.agentRun.count({ where: { orgId: ctx.orgId, status: "RUNNING", type: { in: ["DRAFT", "REPLY"] } } }),
  ]);
  const back = `/app/messages${channel ? `?canal=${channel}` : ""}`;
  return (
    <>
      <AutoRefresh active={running > 0} />
      <PageHeader title="Messages à valider" subtitle="L'agent propose, vous décidez : relisez, corrigez, puis envoyez. Rien ne part sans votre accord." />
      <Notice msg={msg} />
      <div className="mb-4 flex flex-wrap gap-2 text-sm">
        {[undefined, ...CHANNELS].map((c) => (
          <Link
            key={c ?? "tous"}
            href={c ? `/app/messages?canal=${c}` : "/app/messages"}
            className={`rounded-full border px-3 py-1 ${c === channel ? "border-transparent bg-gradient-to-r from-pink to-violet text-white" : "border-white/12 bg-white/[0.04] text-slate-700 hover:bg-white/[0.08]"}`}
          >
            {c ? CHANNEL_LABEL[c] : "Tous"}
          </Link>
        ))}
      </div>
      {running > 0 && <p className="mb-4 text-sm text-amber-700">L'agent rédige en ce moment : la liste se met à jour toute seule.</p>}
      {drafts.length === 0 ? (
        <Empty>
          Aucun brouillon en attente. Lancez une rédaction depuis une{" "}
          <Link href="/app/agent" className="font-medium text-brand-600 hover:underline">
            campagne
          </Link>{" "}
          ou depuis la fiche d'un contact.
        </Empty>
      ) : (
        <div className="space-y-4">
          {drafts.map((m) => (
            <DraftCard key={m.id} message={m} contact={m.contact} legalFooter={org.legalFooter} back={back} />
          ))}
        </div>
      )}
    </>
  );
}
