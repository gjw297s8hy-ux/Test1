import { Logo } from "./icons";

export function AuthShell({ title, subtitle, children, footer }: { title: string; subtitle?: string; children: React.ReactNode; footer?: React.ReactNode }) {
  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-10">
      <div aria-hidden className="pointer-events-none absolute -top-40 left-1/2 h-[480px] w-[720px] -translate-x-1/2 rounded-full bg-violet/25 blur-[120px]" />
      <div aria-hidden className="pointer-events-none absolute -bottom-40 right-0 h-[360px] w-[480px] rounded-full bg-pink/15 blur-[120px]" />
      <div className="relative w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center text-center">
          <Logo size="h-12 w-12" />
          <p className="mt-4 font-display text-2xl font-bold">
            Prospect <span className="grad-text">IA</span>
          </p>
          <p className="mt-1 text-sm text-slate-500">Votre agent de prospection, du premier contact au rendez-vous.</p>
        </div>
        <div className="card p-7">
          <h1 className="text-xl font-semibold">{title}</h1>
          {subtitle && <p className="mt-1.5 text-sm text-slate-500">{subtitle}</p>}
          <div className="mt-6">{children}</div>
        </div>
        {footer && <p className="mt-5 text-center text-sm text-slate-500">{footer}</p>}
      </div>
    </main>
  );
}
