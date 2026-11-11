import Link from "next/link";
import type { AgentRun, ContactStatus } from "@prisma/client";
import { RUN_LABEL, STATUS_LABEL, STATUS_TONE, fmtDateTime } from "@/lib/labels";

export function PageHeader({ title, subtitle, children }: { title: string; subtitle?: string; children?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  );
}

export function Notice({ msg }: { msg?: string }) {
  if (!msg) return null;
  return (
    <p role="status" className="mb-4 rounded-lg border border-brand-100 bg-brand-50 px-4 py-2.5 text-sm text-brand-700">
      {msg}
    </p>
  );
}

export function StatusBadge({ status }: { status: ContactStatus }) {
  return <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_TONE[status]}`}>{STATUS_LABEL[status]}</span>;
}

export function ScoreBadge({ score }: { score: number | null }) {
  if (score == null) return <span className="text-xs text-slate-400">Non évalué</span>;
  const tone = score >= 75 ? "bg-emerald-100 text-emerald-800" : score >= 50 ? "bg-amber-100 text-amber-800" : "bg-slate-100 text-slate-600";
  return <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums ${tone}`}>{score}/100</span>;
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="card px-6 py-10 text-center text-sm text-slate-500">{children}</div>;
}

export function Field({ label, children, className = "" }: { label: string; children: React.ReactNode; className?: string }) {
  return (
    <label className={`block ${className}`}>
      <span className="label">{label}</span>
      {children}
    </label>
  );
}

export function RunList({ runs }: { runs: AgentRun[] }) {
  if (runs.length === 0) return <p className="px-4 py-6 text-sm text-slate-500">L'agent n'a encore rien lancé.</p>;
  return (
    <ul className="divide-y divide-slate-100">
      {runs.map((run) => (
        <li key={run.id} className="flex items-start gap-3 px-4 py-3 text-sm">
          <span
            className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
              run.status === "RUNNING" ? "animate-pulse bg-amber-500" : run.status === "DONE" ? "bg-emerald-500" : "bg-rose-500"
            }`}
          />
          <div className="min-w-0 flex-1">
            <p className="font-medium">
              {RUN_LABEL[run.type]} <span className="font-normal text-slate-500">· {run.label}</span>
            </p>
            <p className={run.status === "FAILED" ? "text-rose-700" : "text-slate-600"}>
              {run.status === "RUNNING" ? "En cours…" : run.status === "DONE" ? run.summary : run.error}
            </p>
          </div>
          <span className="shrink-0 text-xs text-slate-400">{fmtDateTime(run.createdAt)}</span>
        </li>
      ))}
    </ul>
  );
}

export function ExtLink({ href, children }: { href: string; children: React.ReactNode }) {
  if (!/^https?:\/\//.test(href)) return <span>{children}</span>;
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-brand-600 underline-offset-2 hover:underline">
      {children}
    </a>
  );
}

export function TextLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link href={href} className="font-medium text-slate-900 underline-offset-2 hover:text-brand-600 hover:underline">
      {children}
    </Link>
  );
}

export function TrialNotice() {
  return (
    <p className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-900">
      Essai gratuit : vous pouvez lancer chaque étape une fois, sur une seule entreprise et un seul contact, pour voir comment l'agent travaille. Abonnez-vous pour prospecter sans limite.
    </p>
  );
}
