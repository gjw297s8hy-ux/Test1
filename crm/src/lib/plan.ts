import type { Plan, RunType } from "@prisma/client";
import { cache } from "react";
import { db } from "./db";

/** Lancements de l'agent par mois pour les abonnes. */
export const MONTHLY_RUNS = 1000;

/** Offre gratuite : un seul essai par etape, sur un seul element, pour decouvrir l'agent. */
export const TRIAL_SIZE = 1;

function adminEmails(): string[] {
  return (process.env.ADMIN_EMAILS || "")
    .split(",")
    .map((e) => e.trim().toLowerCase())
    .filter(Boolean);
}

/** Administrateur du site (ADMIN_EMAILS) : seul a voir ce que coute l'agent. */
export function isSiteAdmin(email: string): boolean {
  return adminEmails().includes(email.trim().toLowerCase());
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

/** Etapes de l'essai deja utilisees. Un lancement en echec ne compte pas : l'essai reste disponible. */
export async function trialUsed(orgId: string): Promise<Set<RunType>> {
  const runs = await db.agentRun.findMany({
    where: { orgId, status: { in: ["RUNNING", "DONE"] } },
    select: { type: true },
    distinct: ["type"],
  });
  return new Set(runs.map((r) => r.type));
}

export const isTrial = cache(async (orgId: string): Promise<boolean> => (await effectivePlan(orgId)) === "FREE");
