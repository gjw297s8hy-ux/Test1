import { logout } from "@/app/actions";
import { requireCtx } from "@/lib/auth";
import { db } from "@/lib/db";
import { MONTHLY_RUNS, effectivePlan } from "@/lib/plan";
import { Icon, Logo } from "@/components/icons";
import { NavLink } from "@/components/nav";

// Les travaux de l'agent tournent apres la reponse (after) : ils ont besoin de temps sur un hebergement serverless.
export const maxDuration = 300;

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const ctx = await requireCtx();
  const monthStart = new Date();
  monthStart.setUTCDate(1);
  monthStart.setUTCHours(0, 0, 0, 0);
  const [drafts, tasksDue, plan, runsThisMonth] = await Promise.all([
    db.message.count({ where: { orgId: ctx.orgId, status: "DRAFT" } }),
    db.task.count({ where: { orgId: ctx.orgId, doneAt: null, dueAt: { lte: new Date() } } }),
    effectivePlan(ctx.orgId),
    db.agentRun.count({ where: { orgId: ctx.orgId, createdAt: { gte: monthStart } } }),
  ]);
  const left = Math.max(0, MONTHLY_RUNS - runsThisMonth);

  return (
    <div className="md:flex md:min-h-screen">
      <aside className="border-white/[0.07] bg-white/[0.025] backdrop-blur-xl max-md:border-b md:sticky md:top-0 md:flex md:h-screen md:w-64 md:shrink-0 md:flex-col md:border-r">
        <div className="flex items-center gap-3 px-5 pt-5 pb-4 md:pb-7">
          <Logo />
          <div className="min-w-0">
            <p className="font-display text-[15px] font-bold leading-tight">Prospect IA</p>
            <p className="truncate text-xs text-slate-500">{ctx.orgName}</p>
          </div>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-1 md:flex-col md:overflow-visible">
          <NavLink href="/app" label="Tableau de bord" icon="dashboard" exact />
          <NavLink href="/app/agent" label="Agent IA" icon="agent" />
          <NavLink href="/app/messages" label="Messages à valider" icon="mail" badge={drafts} />
          <NavLink href="/app/prospects" label="Contacts" icon="contacts" />
          <NavLink href="/app/entreprises" label="Entreprises" icon="companies" />
          <NavLink href="/app/taches" label="Tâches et relances" icon="tasks" badge={tasksDue} />
          <NavLink href="/app/parametres" label="Paramètres" icon="settings" />
        </nav>
        <div className="hidden px-4 pb-4 md:block">
          <div className="rounded-2xl border border-white/10 bg-gradient-to-br from-pink/15 to-violet/15 p-4 text-[13px] text-slate-600">
            {plan === "PRO" ? (
              <>
                <p className="font-display text-sm font-semibold text-white">Offre Pro</p>
                <p className="mt-0.5">{left} lancements de l'agent restants ce mois-ci</p>
                <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/10">
                  <div className="grad-bar h-full rounded-full" style={{ width: `${Math.max(4, (left / MONTHLY_RUNS) * 100)}%` }} />
                </div>
              </>
            ) : (
              <>
                <p className="font-display text-sm font-semibold text-white">Essai gratuit</p>
                <p className="mt-0.5">Testez l'agent sur une entreprise, puis passez à l'offre Pro.</p>
              </>
            )}
          </div>
          <form action={logout} className="mt-4 flex items-center justify-between gap-2 px-1">
            <div className="flex min-w-0 items-center gap-2.5">
              <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-white/10 text-xs font-semibold">
                {ctx.userName.slice(0, 1).toUpperCase()}
              </span>
              <span className="truncate text-sm text-slate-700">{ctx.userName}</span>
            </div>
            <button type="submit" title="Se déconnecter" aria-label="Se déconnecter" className="cursor-pointer rounded-lg p-1.5 text-slate-500 hover:bg-white/10 hover:text-white">
              <Icon name="logout" className="h-[18px] w-[18px]" />
            </button>
          </form>
        </div>
      </aside>
      <main className="min-w-0 flex-1 px-4 py-6 md:px-10 md:py-9">
        <div className="mx-auto max-w-6xl">{children}</div>
      </main>
    </div>
  );
}
