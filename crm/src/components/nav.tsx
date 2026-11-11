"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon, type IconName } from "./icons";

export function NavLink({ href, label, icon, badge, exact }: { href: string; label: string; icon: IconName; badge?: number; exact?: boolean }) {
  const path = usePathname();
  const active = exact ? path === href : path === href || path.startsWith(`${href}/`);
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={`relative flex shrink-0 items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
        active ? "bg-gradient-to-r from-violet/25 to-violet/[0.04] text-white shadow-[inset_2px_0_0_#8b5cff]" : "text-slate-500 hover:bg-white/[0.05] hover:text-white"
      }`}
    >
      <Icon name={icon} className={`h-[18px] w-[18px] ${active ? "text-white" : ""}`} />
      <span className="whitespace-nowrap">{label}</span>
      {badge ? <span className="ml-auto rounded-full bg-pink px-1.5 text-[11px] font-semibold text-white tabular-nums">{badge}</span> : null}
    </Link>
  );
}
