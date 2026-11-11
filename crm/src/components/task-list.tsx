import Link from "next/link";
import type { Contact, Task } from "@prisma/client";
import { deleteTask, toggleTask } from "@/app/actions";
import { fmtDate, fullName } from "@/lib/labels";

export function TaskList({ tasks, showContact = true }: { tasks: (Task & { contact?: Contact | null })[]; showContact?: boolean }) {
  const now = Date.now();
  return (
    <ul className="divide-y divide-slate-100">
      {tasks.map((task) => {
        const late = !task.doneAt && task.dueAt && task.dueAt.getTime() < now;
        return (
          <li key={task.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
            <form action={toggleTask}>
              <input type="hidden" name="id" value={task.id} />
              <button
                type="submit"
                aria-label={task.doneAt ? "Rouvrir la tâche" : "Terminer la tâche"}
                className={`flex h-5 w-5 cursor-pointer items-center justify-center rounded border text-xs ${
                  task.doneAt ? "border-emerald-500 bg-emerald-500 text-white" : "border-slate-300 bg-white hover:border-brand-500"
                }`}
              >
                {task.doneAt ? "✓" : ""}
              </button>
            </form>
            <div className="min-w-0 flex-1">
              <p className={task.doneAt ? "text-slate-400 line-through" : ""}>{task.title}</p>
              {showContact && task.contact && (
                <Link href={`/app/prospects/${task.contact.id}`} className="text-xs text-slate-500 hover:text-brand-600 hover:underline">
                  {fullName(task.contact)}
                </Link>
              )}
            </div>
            {task.dueAt && <span className={`shrink-0 text-xs ${late ? "font-medium text-rose-600" : "text-slate-500"}`}>{fmtDate(task.dueAt)}</span>}
            <form action={deleteTask}>
              <input type="hidden" name="id" value={task.id} />
              <button type="submit" aria-label="Supprimer la tâche" className="cursor-pointer px-1 text-slate-300 hover:text-rose-600">
                ×
              </button>
            </form>
          </li>
        );
      })}
    </ul>
  );
}
