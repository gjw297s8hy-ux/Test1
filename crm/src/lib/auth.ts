import { createHash, randomBytes, scrypt, timingSafeEqual } from "node:crypto";
import { promisify } from "node:util";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";
import type { Role } from "@prisma/client";
import { db } from "./db";

const scryptAsync = promisify(scrypt) as (pw: string, salt: Buffer, len: number) => Promise<Buffer>;

const COOKIE = "crm_session";
const SESSION_DAYS = 30;

export async function hashPassword(password: string): Promise<string> {
  const salt = randomBytes(16);
  const key = await scryptAsync(password, salt, 64);
  return `${salt.toString("hex")}:${key.toString("hex")}`;
}

// Hachage factice : verifier un compte inexistant prend le meme temps qu'un vrai,
// pour ne pas reveler quelles adresses ont un compte.
const DUMMY_HASH = "00000000000000000000000000000000:" + "0".repeat(128);

export async function verifyPasswordOrDummy(password: string, stored: string | undefined): Promise<boolean> {
  const ok = await verifyPassword(password, stored ?? DUMMY_HASH);
  return Boolean(stored) && ok;
}

export async function verifyPassword(password: string, stored: string): Promise<boolean> {
  const [saltHex, keyHex] = stored.split(":");
  if (!saltHex || !keyHex) return false;
  const expected = Buffer.from(keyHex, "hex");
  const actual = await scryptAsync(password, Buffer.from(saltHex, "hex"), expected.length);
  return timingSafeEqual(expected, actual);
}

export function newToken(): string {
  return randomBytes(32).toString("base64url");
}

export function hashToken(token: string): string {
  return createHash("sha256").update(token).digest("hex");
}

export async function createSession(userId: string, orgId: string): Promise<void> {
  const token = newToken();
  const expiresAt = new Date(Date.now() + SESSION_DAYS * 86_400_000);
  await db.session.create({ data: { tokenHash: hashToken(token), userId, orgId, expiresAt } });
  const jar = await cookies();
  jar.set(COOKIE, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    expires: expiresAt,
  });
}

export async function destroySession(): Promise<void> {
  const jar = await cookies();
  const token = jar.get(COOKIE)?.value;
  if (token) await db.session.deleteMany({ where: { tokenHash: hashToken(token) } });
  jar.delete(COOKIE);
}

export type Ctx = {
  userId: string;
  userName: string;
  userEmail: string;
  orgId: string;
  orgName: string;
  role: Role;
};

/** Session courante, ou null. Verifie que l'utilisateur est toujours membre de l'organisation. */
export const getCtx = cache(async (): Promise<Ctx | null> => {
  const jar = await cookies();
  const token = jar.get(COOKIE)?.value;
  if (!token) return null;
  const session = await db.session.findUnique({
    where: { tokenHash: hashToken(token) },
    include: { user: true, org: true },
  });
  if (!session || session.expiresAt < new Date()) return null;
  const membership = await db.membership.findUnique({
    where: { userId_orgId: { userId: session.userId, orgId: session.orgId } },
  });
  if (!membership) return null;
  return {
    userId: session.userId,
    userName: session.user.name,
    userEmail: session.user.email,
    orgId: session.orgId,
    orgName: session.org.name,
    role: membership.role,
  };
});

/** A appeler en tete de chaque page et de chaque action : toutes les requetes sont filtrees par ctx.orgId. */
export async function requireCtx(): Promise<Ctx> {
  const ctx = await getCtx();
  if (!ctx) redirect("/connexion");
  return ctx;
}

export function isAdmin(ctx: Ctx): boolean {
  return ctx.role === "OWNER" || ctx.role === "ADMIN";
}
