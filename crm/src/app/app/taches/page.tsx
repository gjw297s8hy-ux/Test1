import { createTask } from "@/app/actions";
import { requireCtx } from "@/lib/auth";
import { db } from "@/lib/db";
import { Submit } from "@/components/client";
import { TaskList } from "@/components/task-list";
import { Notice, PageHeader } from "@/components/ui";

export default async function Page({ searchParams }: { searchParams: Promise<{ msg?: string }> }) {
  const ctx = await requireCtx();
  const { msg } = await searchParams;
  const [open, done] = await Promise.all([
    db.task.findMany({ where: { orgId: ctx.orgId, doneAt: null }, include: { contact: true }, orderBy: [{ dueAt: "asc" }, { createdAt: "asc" }], take: 200 }),
    db.task.findMany({ where: { orgId: ctx.orgId, doneAt: { not: null } }, include: { contact: true }, orderBy: { doneAt: "desc" }, take: 15 }),
  ]);
  const now = Date.now();
  const endOfToday = new Date();
  endOfToday.setHours(23, 59, 59, 999);
  const late = open.filter((t) => t.dueAt && t.dueAt.getTime() < now);
  const today = open.filter((t) => t.dueAt && t.dueAt.getTime() >= now && t.dueAt <= endOfToday);
  const later = open.filter((t) => !t.dueAt || t.dueAt > endOfToday);
  const groups = [
    { title: "En retard", tasks: late },
    { title: "Aujourd'hui", tasks: today },
    { title: "À venir", tasks: later },
  ].filter((g) => g.tasks.length);

  return (
    <>
      <PageHeader title="Tâches et relances" subtitle="Une relance est planifiée à J+4 après chaque envoi, et close dès que le prospect répond." />
      <Notice msg={msg} />
      <form action={createTask} className="card mb-6 flex flex-wrap items-end gap-3 p-4">
        <label className="min-w-56 flex-1">
          <span className="label">Nouvelle tâche</span>
          <input className="input" name="title" placeholder="Rappeler le cabinet Durand" required />
        </label>
        <label>
          <span className="label">Échéance</span>
          <input className="input" type="date" name="dueAt" />
        </label>
        <Submit>Ajouter</Submit>
      </form>
      {groups.length === 0 && <div className="card px-6 py-10 text-center text-sm text-slate-500">Aucune tâche en attente.</div>}
      <div className="space-y-6">
        {groups.map((g) => (
          <section key={g.title} className="card">
            <h2 className="border-b border-white/[0.06] px-5 py-4 font-display text-[15px] font-semibold">
              {g.title} <span className="font-normal text-slate-500">· {g.tasks.length}</span>
            </h2>
            <TaskList tasks={g.tasks} />
          </section>
        ))}
        {done.length > 0 && (
          <section className="card">
            <h2 className="border-b border-white/[0.06] px-5 py-4 font-display text-[15px] font-semibold">Terminées récemment</h2>
            <TaskList tasks={done} />
          </section>
        )}
      </div>
    </>
  );
}
