import Link from "next/link";
import type { AgentRun, ContactStatus } from "@prisma/client";
import { RUN_LABEL, STATUS_LABEL, STATUS_TONE, fmtDateTime } from "@/lib/labels";
import { estimateCostUsd } from "@/lib/llm";

export function PageHeader({ title, subtitle, children }: { title: string; subtitle?: string; children?: React.ReactNode }) {
  return (
    <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-[28px] font-bold leading-tight">{title}</h1>
        {subtitle && <p className="mt-1.5 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  );
}

export function Notice({ msg }: { msg?: string }) {
  if (!msg) return null;
  return (
    <p role="status" className="mb-5 rounded-xl border border-brand-100 bg-brand-50 px-4 py-3 text-sm text-brand-700">
      {msg}
    </p>
  );
}

export function StatusBadge({ status }: { status: ContactStatus }) {
  return <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_TONE[status]}`}>{STATUS_LABEL[status]}</span>;
}

export function ScoreBadge({ score }: { score: number | null }) {
  if (score == null) return <span className="text-xs text-slate-400">Non évalué</span>;
  const tone = score >= 75 ? "bg-emerald-100 text-mint" : score >= 50 ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-500";
  return <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold tabular-nums ${tone}`}>{score}</span>;
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="card px-6 py-12 text-center text-sm text-slate-500">{children}</div>;
}

export function Field({ label, children, className = "" }: { label: string; children: React.ReactNode; className?: string }) {
  return (
    <label className={`block ${className}`}>
      <span className="label">{label}</span>
      {children}
    </label>
  );
}

/** showCost : reserve a l'administrateur du site. Les clients ne doivent pas voir le cout de revient. */
export function RunList({ runs, showCost = false }: { runs: AgentRun[]; showCost?: boolean }) {
  if (runs.length === 0) return <p className="px-5 py-6 text-sm text-slate-500">L'agent n'a encore rien lancé.</p>;
  return (
    <ul className="divide-y divide-white/[0.06]">
      {runs.map((run) => (
        <li key={run.id} className="flex items-start gap-3 px-5 py-3.5 text-sm">
          <span
            className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
              run.status === "RUNNING" ? "animate-pulse bg-amber-500 shadow-[0_0_10px_#ffcc4d]" : run.status === "DONE" ? "bg-cyan shadow-[0_0_10px_#22e4ff]" : "bg-rose-500 shadow-[0_0_10px_#ff3d9a]"
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
          <span className="shrink-0 text-right text-xs text-slate-400">
            {fmtDateTime(run.createdAt)}
            {showCost && <CostLine run={run} />}
          </span>
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
    <p className="mb-5 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
      Essai gratuit : vous pouvez lancer chaque étape une fois, sur une seule entreprise et un seul contact, pour voir comment l'agent travaille. Abonnez-vous pour prospecter sans limite.
    </p>
  );
}

const usd = new Intl.NumberFormat("fr-FR", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** Cout estime d'un lancement termine, d'apres les jetons et les recherches web comptes par l'API. */
function CostLine({ run }: { run: AgentRun }) {
  if (run.status === "RUNNING") return null;
  const cost = estimateCostUsd(run);
  if (cost == null || cost === 0) return null;
  return (
    <span className="block tabular-nums" title={`${run.inputTokens} jetons lus, ${run.outputTokens} écrits, ${run.webSearches} recherches web`}>
      ≈ {usd.format(cost)}
    </span>
  );
}
