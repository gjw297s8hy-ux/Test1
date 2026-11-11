"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function NavLink({ href, label, badge, exact }: { href: string; label: string; badge?: number; exact?: boolean }) {
  const path = usePathname();
  const active = exact ? path === href : path === href || path.startsWith(`${href}/`);
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={`flex shrink-0 items-center justify-between gap-2 rounded-lg px-3 py-2 text-sm font-medium transition ${
        active ? "bg-white/10 text-white" : "text-slate-300 hover:bg-white/5 hover:text-white"
      }`}
    >
      {label}
      {badge ? <span className="rounded-full bg-brand-500 px-1.5 text-xs font-semibold text-white tabular-nums">{badge}</span> : null}
    </Link>
  );
}
