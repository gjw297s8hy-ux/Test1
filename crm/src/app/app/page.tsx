import Link from "next/link";
import { closeStaleRuns } from "@/lib/agent";
import { requireCtx } from "@/lib/auth";
import { db } from "@/lib/db";
import { CHANNELS, CHANNEL_LABEL, CONTACT_STATUSES, STATUS_LABEL } from "@/lib/labels";
import { isSiteAdmin } from "@/lib/plan";
import { AutoRefresh } from "@/components/client";
import { Icon } from "@/components/icons";
import { TaskList } from "@/components/task-list";
import { RunList, ScoreBadge } from "@/components/ui";

function Stat({ label, value, hint, href, grad }: { label: string; value: string; hint?: string; href?: string; grad?: boolean }) {
  const inner = (
    <div className="card h-full p-5 transition hover:border-white/20">
      <p className="text-[13px] text-slate-500">{label}</p>
      <p className={`mt-2 font-display text-[32px] font-bold leading-none tabular-nums ${grad ? "grad-text" : ""}`}>{value}</p>
      {hint && <p className="mt-2 text-xs text-mint">{hint}</p>}
    </div>
  );
  return href ? <Link href={href}>{inner}</Link> : inner;
}

function SectionHead({ title, href, link, icon }: { title: string; href?: string; link?: string; icon?: "fire" }) {
  return (
    <div className="flex items-center justify-between border-b border-white/[0.06] px-5 py-4">
      <h2 className="flex items-center gap-2 text-[15px] font-semibold">
        {icon && <Icon name={icon} className="h-[18px] w-[18px] text-pink" />}
        {title}
      </h2>
      {href && (
        <Link href={href} className="text-xs font-medium text-slate-500 hover:text-white">
          {link} →
        </Link>
      )}
    </div>
  );
}

export default async function Dashboard() {
  const ctx = await requireCtx();
  const orgId = ctx.orgId;
  await closeStaleRuns(orgId);
  const since = new Date(Date.now() - 30 * 86_400_000);
  const weekAgo = new Date(Date.now() - 7 * 86_400_000);

  const [byStatus, sent30, sentByChannel, contacted, replied, drafts, tasks, runs, companies, newCompanies, hot] = await Promise.all([
    db.contact.groupBy({ by: ["status"], where: { orgId }, _count: true }),
    db.message.count({ where: { orgId, status: "SENT", sentAt: { gte: since } } }),
    db.message.groupBy({ by: ["channel"], where: { orgId, status: "SENT", sentAt: { gte: since } }, _count: true }),
    db.contact.count({ where: { orgId, messages: { some: { status: "SENT" } } } }),
    db.contact.count({ where: { orgId, messages: { some: { status: "SENT" } }, AND: { messages: { some: { status: "RECEIVED" } } } } }),
    db.message.count({ where: { orgId, status: "DRAFT" } }),
    db.task.findMany({ where: { orgId, doneAt: null }, include: { contact: true }, orderBy: [{ dueAt: "asc" }, { createdAt: "asc" }], take: 6 }),
    db.agentRun.findMany({ where: { orgId }, orderBy: { createdAt: "desc" }, take: 5 }),
    db.company.count({ where: { orgId } }),
    db.company.count({ where: { orgId, createdAt: { gte: weekAgo } } }),
    db.company.findMany({
      where: { orgId, score: { not: null } },
      orderBy: [{ score: "desc" }, { createdAt: "desc" }],
      take: 5,
      select: { id: true, name: true, city: true, industry: true, score: true, insights: true, scoreReason: true },
    }),
  ]);

  const count = Object.fromEntries(byStatus.map((s) => [s.status, s._count])) as Record<string, number>;
  const total = byStatus.reduce((n, s) => n + s._count, 0);
  const hotCount = (count.INTERESTED ?? 0) + (count.MEETING ?? 0);
  const max = Math.max(1, ...byStatus.map((s) => s._count));
  const channelCount = Object.fromEntries(sentByChannel.map((c) => [c.channel, c._count])) as Record<string, number>;
  const empty = total === 0 && companies === 0;
  // Premiere ligne des signaux, sans l'URL : c'est l'accroche a montrer.
  const signal = (c: (typeof hot)[number]) =>
    (c.insights.split("\n").find((l) => l.trim()) ?? c.scoreReason).replace(/https?:\/\/\S+/g, "").replace(/[\s(–-]+$/, "").trim();

  return (
    <>
      <AutoRefresh active={runs.some((r) => r.status === "RUNNING")} />
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[30px] font-bold leading-tight">Bonjour {ctx.userName.split(" ")[0]} 👋</h1>
          <p className="mt-1.5 text-sm text-slate-500">
            {newCompanies > 0
              ? `Votre agent a trouvé ${newCompanies} nouvelle${newCompanies > 1 ? "s" : ""} entreprise${newCompanies > 1 ? "s" : ""} cette semaine.`
              : "Votre prospection en un coup d'œil."}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          <form action="/app/prospects" className="relative max-sm:w-full">
            <Icon name="search" className="pointer-events-none absolute top-1/2 left-3.5 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input name="q" type="search" placeholder="Rechercher un prospect…" aria-label="Rechercher un prospect" className="input w-64 pl-10 max-sm:w-full" />
          </form>
          <Link href="/app/agent" className="btn">
            <Icon name="agent" className="h-4 w-4" /> Lancer l'agent
          </Link>
        </div>
      </div>

      {empty && (
        <div className="card relative mb-8 overflow-hidden p-6">
          <div aria-hidden className="pointer-events-none absolute -top-20 -right-20 h-60 w-60 rounded-full bg-violet/30 blur-[80px]" />
          <p className="font-display text-lg font-semibold">Pour démarrer</p>
          <ol className="mt-3 space-y-2 text-sm text-slate-600">
            <li>
              <span className="mr-2 font-display font-bold text-pink">1</span>Décrivez votre offre dans les{" "}
              <Link className="font-medium text-brand-600 underline" href="/app/parametres">paramètres</Link> : l'agent s'en sert pour cibler et rédiger.
            </li>
            <li>
              <span className="mr-2 font-display font-bold text-violet">2</span>Créez une campagne dans{" "}
              <Link className="font-medium text-brand-600 underline" href="/app/agent">Agent IA</Link> et lancez une recherche.
            </li>
            <li>
              <span className="mr-2 font-display font-bold text-cyan">3</span>Relisez les brouillons dans « Messages à valider » : rien ne part sans votre accord.
            </li>
          </ol>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Entreprises trouvées" value={String(companies)} hint={`${total} contact${total > 1 ? "s" : ""}`} href="/app/entreprises" grad />
        <Stat label="Messages envoyés" value={String(sent30)} hint="30 derniers jours" />
        <Stat
          label="Taux de réponse"
          value={contacted ? `${Math.round((replied / contacted) * 100)} %` : "–"}
          hint={contacted ? `${replied} réponse${replied > 1 ? "s" : ""} sur ${contacted} contacté${contacted > 1 ? "s" : ""}` : "Aucun contact joint"}
          grad
        />
        <Stat label="Intéressés et RDV" value={String(hotCount)} hint={`${drafts} message${drafts > 1 ? "s" : ""} à valider`} href="/app/prospects?statut=INTERESTED" />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1.25fr_1fr]">
        <div className="space-y-6">
          <section className="card">
            <SectionHead title="Prospects les plus chauds" icon="fire" href="/app/entreprises" link="Tout voir" />
            {hot.length === 0 ? (
              <p className="px-5 py-6 text-sm text-slate-500">Les entreprises scorées par l'agent apparaîtront ici, les plus prometteuses en premier.</p>
            ) : (
              <ul className="divide-y divide-white/[0.06]">
                {hot.map((c) => (
                  <li key={c.id}>
                    <Link href={`/app/entreprises/${c.id}`} className="flex items-center gap-3.5 px-5 py-3.5 transition hover:bg-white/[0.03]">
                      <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-violet/40 to-cyan/20 font-display font-bold">
                        {c.name.slice(0, 1).toUpperCase()}
                      </span>
                      <div className="w-48 min-w-0 shrink-0 max-sm:flex-1">
                        <p className="truncate text-sm font-semibold">{c.name}</p>
                        <p className="truncate text-xs text-slate-500">{[c.industry, c.city].filter(Boolean).join(" · ")}</p>
                      </div>
                      <p className="line-clamp-2 min-w-0 flex-1 text-[13px] text-slate-600 max-sm:hidden">{signal(c)}</p>
                      <ScoreBadge score={c.score} />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="card">
            <SectionHead title="Activité de l'agent" href="/app/agent" link="Historique" />
            <RunList runs={runs} showCost={isSiteAdmin(ctx.userEmail)} />
          </section>
        </div>

        <div className="space-y-6">
          <section className="card">
            <SectionHead title="Entonnoir de prospection" />
            <ul className="space-y-3 px-5 py-4">
              {CONTACT_STATUSES.map((st) => (
                <li key={st}>
                  <Link href={`/app/prospects?statut=${st}`} className="group flex items-center gap-3 text-[13px]">
                    <span className="w-28 shrink-0 text-slate-600 group-hover:text-white">{STATUS_LABEL[st]}</span>
                    <span className="h-2.5 flex-1 overflow-hidden rounded-full bg-white/[0.07]">
                      <span className="grad-bar block h-full rounded-full" style={{ width: `${Math.max(count[st] ? 3 : 0, ((count[st] ?? 0) / max) * 100)}%` }} />
                    </span>
                    <span className="w-8 shrink-0 text-right font-semibold tabular-nums">{count[st] ?? 0}</span>
                  </Link>
                </li>
              ))}
            </ul>
            <div className="flex flex-wrap gap-x-5 gap-y-1 border-t border-white/[0.06] px-5 py-3.5 text-xs text-slate-500">
              <span className="font-medium text-slate-600">Envois sur 30 jours :</span>
              {CHANNELS.map((ch) => (
                <span key={ch}>
                  {CHANNEL_LABEL[ch]} <span className="font-semibold text-white tabular-nums">{channelCount[ch] ?? 0}</span>
                </span>
              ))}
            </div>
          </section>

          <section className="card">
            <SectionHead title="À faire" href="/app/taches" link="Toutes les tâches" />
            {tasks.length ? <TaskList tasks={tasks} /> : <p className="px-5 py-6 text-sm text-slate-500">Aucune tâche en attente.</p>}
          </section>
        </div>
      </div>
    </>
  );
}
