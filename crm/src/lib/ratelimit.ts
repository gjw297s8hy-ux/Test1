import { headers } from "next/headers";
import { db } from "./db";

/**
 * Adresse IP du visiteur, telle que la transmet l'hebergeur (Vercel), ou null si elle est inconnue.
 * Sans IP, on n'applique pas de limite par connexion : tous les visiteurs partageraient le meme compteur.
 */
export async function clientIp(): Promise<string | null> {
  const h = await headers();
  return h.get("x-real-ip") || h.get("x-forwarded-for")?.split(",")[0]?.trim() || null;
}

/** Vrai si la cle a deja atteint `max` tentatives sur la fenetre. */
export async function tooMany(key: string | null, max: number, windowMs: number): Promise<boolean> {
  if (!key) return false;
  const since = new Date(Date.now() - windowMs);
  return (await db.attempt.count({ where: { key, createdAt: { gte: since } } })) >= max;
}

export async function recordAttempt(...keys: (string | null)[]): Promise<void> {
  const data = keys.filter((k): k is string => Boolean(k)).map((key) => ({ key }));
  if (data.length) await db.attempt.createMany({ data });
  // Menage occasionnel : les tentatives de plus d'un jour ne servent plus.
  if (Math.random() < 0.05) {
    await db.attempt.deleteMany({ where: { createdAt: { lt: new Date(Date.now() - 86_400_000) } } });
  }
}

export async function clearAttempts(key: string): Promise<void> {
  await db.attempt.deleteMany({ where: { key } });
}

export const MIN = 60_000;
export const HOUR = 60 * MIN;
