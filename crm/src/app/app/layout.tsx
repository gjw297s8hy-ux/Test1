import { logout } from "@/app/actions";
import { requireCtx } from "@/lib/auth";
import { db } from "@/lib/db";
import { NavLink } from "@/components/nav";

// Les travaux de l'agent tournent apres la reponse (after) : ils ont besoin de temps sur un hebergement serverless.
export const maxDuration = 300;

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const ctx = await requireCtx();
  const [drafts, tasksDue] = await Promise.all([
    db.message.count({ where: { orgId: ctx.orgId, status: "DRAFT" } }),
    db.task.count({ where: { orgId: ctx.orgId, doneAt: null, dueAt: { lte: new Date() } } }),
  ]);
  return (
    <div className="md:flex md:min-h-screen">
      <aside className="bg-ink text-white md:sticky md:top-0 md:flex md:h-screen md:w-60 md:shrink-0 md:flex-col">
        <div className="px-5 pt-5 pb-3">
          <p className="text-sm font-semibold tracking-tight">CRM Prospection IA</p>
          <p className="truncate text-xs text-slate-400">{ctx.orgName}</p>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-1 md:flex-col md:overflow-visible">
          <NavLink href="/app" label="Tableau de bord" exact />
          <NavLink href="/app/agent" label="Agent IA" />
          <NavLink href="/app/messages" label="Messages à valider" badge={drafts} />
          <NavLink href="/app/prospects" label="Contacts" />
          <NavLink href="/app/entreprises" label="Entreprises" />
          <NavLink href="/app/taches" label="Tâches et relances" badge={tasksDue} />
          <NavLink href="/app/parametres" label="Paramètres" />
        </nav>
        <form action={logout} className="hidden border-t border-white/10 px-5 py-4 md:block">
          <p className="truncate text-xs text-slate-400">{ctx.userName}</p>
          <button type="submit" className="mt-1 cursor-pointer text-sm text-slate-300 hover:text-white">
            Se déconnecter
          </button>
        </form>
      </aside>
      <main className="min-w-0 flex-1 px-4 py-6 md:px-8 md:py-8">
        <div className="mx-auto max-w-6xl">{children}</div>
      </main>
    </div>
  );
}
