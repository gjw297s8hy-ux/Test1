import Link from "next/link";
import { closeStaleRuns } from "@/lib/agent";
import { requireCtx } from "@/lib/auth";
import { db } from "@/lib/db";
import { CHANNELS, CHANNEL_LABEL, CONTACT_STATUSES, STATUS_LABEL } from "@/lib/labels";
import { AutoRefresh } from "@/components/client";
import { TaskList } from "@/components/task-list";
import { PageHeader, RunList } from "@/components/ui";

function Stat({ label, value, hint, href }: { label: string; value: string; hint?: string; href?: string }) {
  const inner = (
    <div className="card h-full p-4 transition hover:border-slate-300">
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold tracking-tight tabular-nums">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-slate-500">{hint}</p>}
    </div>
  );
  return href ? <Link href={href}>{inner}</Link> : inner;
}

export default async function Dashboard() {
  const ctx = await requireCtx();
  const orgId = ctx.orgId;
  await closeStaleRuns(orgId);
  const since = new Date(Date.now() - 30 * 86_400_000);

  const [byStatus, sent30, sentByChannel, contacted, replied, drafts, tasks, runs, companies] = await Promise.all([
    db.contact.groupBy({ by: ["status"], where: { orgId }, _count: true }),
    db.message.count({ where: { orgId, status: "SENT", sentAt: { gte: since } } }),
    db.message.groupBy({ by: ["channel"], where: { orgId, status: "SENT", sentAt: { gte: since } }, _count: true }),
    db.contact.count({ where: { orgId, messages: { some: { status: "SENT" } } } }),
    db.contact.count({ where: { orgId, messages: { some: { status: "SENT" } }, AND: { messages: { some: { status: "RECEIVED" } } } } }),
    db.message.count({ where: { orgId, status: "DRAFT" } }),
    db.task.findMany({ where: { orgId, doneAt: null }, include: { contact: true }, orderBy: [{ dueAt: "asc" }, { createdAt: "asc" }], take: 8 }),
    db.agentRun.findMany({ where: { orgId }, orderBy: { createdAt: "desc" }, take: 6 }),
    db.company.count({ where: { orgId } }),
  ]);

  const count = Object.fromEntries(byStatus.map((s) => [s.status, s._count])) as Record<string, number>;
  const total = byStatus.reduce((n, s) => n + s._count, 0);
  const hot = (count.INTERESTED ?? 0) + (count.MEETING ?? 0);
  const max = Math.max(1, ...byStatus.map((s) => s._count));
  const channelCount = Object.fromEntries(sentByChannel.map((c) => [c.channel, c._count])) as Record<string, number>;
  const empty = total === 0 && companies === 0;

  return (
    <>
      <AutoRefresh active={runs.some((r) => r.status === "RUNNING")} />
      <PageHeader title={`Bonjour ${ctx.userName.split(" ")[0]}`} subtitle="Votre prospection en un coup d'œil.">
        <Link href="/app/agent" className="btn">
          Lancer l'agent
        </Link>
      </PageHeader>

      {empty && (
        <div className="card mb-6 border-brand-100 bg-brand-50 p-5">
          <p className="font-medium">Pour démarrer</p>
          <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-slate-700">
            <li>
              Décrivez votre offre dans les <Link className="font-medium text-brand-700 underline" href="/app/parametres">paramètres</Link> : l'agent s'en sert pour cibler et rédiger.
            </li>
            <li>
              Créez une campagne dans <Link className="font-medium text-brand-700 underline" href="/app/agent">Agent IA</Link> et lancez une recherche de prospects.
            </li>
            <li>Relisez les brouillons dans « Messages à valider » : rien ne part sans votre accord.</li>
          </ol>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Stat label="Contacts" value={String(total)} hint={`${companies} entreprises`} href="/app/prospects" />
        <Stat label="Messages envoyés" value={String(sent30)} hint="30 derniers jours" />
        <Stat
          label="Taux de réponse"
          value={contacted ? `${Math.round((replied / contacted) * 100)} %` : "–"}
          hint={contacted ? `${replied} réponse${replied > 1 ? "s" : ""} sur ${contacted} contacté${contacted > 1 ? "s" : ""}` : "Aucun contact joint"}
        />
        <Stat label="Intéressés et RDV" value={String(hot)} hint={`${count.CUSTOMER ?? 0} clients`} href="/app/prospects?statut=INTERESTED" />
        <Stat label="À valider" value={String(drafts)} hint="brouillons en attente" href="/app/messages" />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <section className="card">
          <h2 className="border-b border-slate-100 px-4 py-3 text-sm font-semibold">Contacts par étape</h2>
          <ul className="space-y-2 p-4">
            {CONTACT_STATUSES.map((st) => (
              <li key={st}>
                <Link href={`/app/prospects?statut=${st}`} className="group flex items-center gap-3 text-sm">
                  <span className="w-28 shrink-0 text-slate-600 group-hover:text-brand-600">{STATUS_LABEL[st]}</span>
                  <span className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                    <span className="block h-full rounded-full bg-brand-500" style={{ width: `${((count[st] ?? 0) / max) * 100}%` }} />
                  </span>
                  <span className="w-8 shrink-0 text-right font-medium tabular-nums">{count[st] ?? 0}</span>
                </Link>
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap gap-x-5 gap-y-1 border-t border-slate-100 px-4 py-3 text-xs text-slate-500">
            <span className="font-medium text-slate-600">Envois sur 30 jours :</span>
            {CHANNELS.map((ch) => (
              <span key={ch}>
                {CHANNEL_LABEL[ch]} <span className="font-semibold text-slate-800 tabular-nums">{channelCount[ch] ?? 0}</span>
              </span>
            ))}
          </div>
        </section>

        <section className="card">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
            <h2 className="text-sm font-semibold">Prochaines tâches</h2>
            <Link href="/app/taches" className="text-xs font-medium text-brand-600 hover:underline">
              Tout voir
            </Link>
          </div>
          {tasks.length ? <TaskList tasks={tasks} /> : <p className="px-4 py-6 text-sm text-slate-500">Aucune tâche en attente.</p>}
        </section>
      </div>

      <section className="card mt-6">
        <h2 className="border-b border-slate-100 px-4 py-3 text-sm font-semibold">Activité de l'agent</h2>
        <RunList runs={runs} />
      </section>
    </>
  );
}
