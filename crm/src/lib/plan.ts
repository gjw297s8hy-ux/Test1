import type { Plan } from "@prisma/client";
import { db } from "./db";

/** Lancements de l'agent par mois. L'offre gratuite n'a pas acces a l'agent : chaque lancement coute du credit IA. */
export const MONTHLY_RUNS: Record<Plan, number> = { FREE: 0, PRO: 1000 };

function adminEmails(): string[] {
  return (process.env.ADMIN_EMAILS || "")
    .split(",")
    .map((e) => e.trim().toLowerCase())
    .filter(Boolean);
}

/** Offre reelle de l'organisation : celles des administrateurs du site (ADMIN_EMAILS) comptent comme Pro. */
export async function effectivePlan(orgId: string): Promise<Plan> {
  const org = await db.organization.findUniqueOrThrow({ where: { id: orgId }, select: { plan: true } });
  if (org.plan === "PRO") return "PRO";
  const admins = adminEmails();
  if (admins.length === 0) return org.plan;
  const member = await db.membership.findFirst({ where: { orgId, user: { email: { in: admins } } }, select: { id: true } });
  return member ? "PRO" : org.plan;
}

export async function agentAllowed(orgId: string): Promise<boolean> {
  return MONTHLY_RUNS[await effectivePlan(orgId)] > 0;
}
