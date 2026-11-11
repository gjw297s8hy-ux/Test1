import Link from "next/link";
import { acceptInvitation } from "@/app/actions";
import { hashToken } from "@/lib/auth";
import { db } from "@/lib/db";
import { ActionForm, Submit } from "@/components/client";
import { AuthShell } from "@/components/auth-shell";

export default async function Page({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const invitation = await db.invitation.findUnique({ where: { tokenHash: hashToken(token) }, include: { org: true } });
  if (!invitation || invitation.acceptedAt || invitation.expiresAt < new Date()) {
    return (
      <AuthShell title="Invitation expirée" subtitle="Demandez un nouveau lien à l'administrateur de votre équipe.">
        <Link href="/connexion" className="btn w-full">
          Aller à la connexion
        </Link>
      </AuthShell>
    );
  }
  const existing = await db.user.findUnique({ where: { email: invitation.email } });
  return (
    <AuthShell
      title={`Rejoindre ${invitation.org.name}`}
      subtitle={existing ? `Connectez-vous avec ${invitation.email} pour rejoindre l'équipe.` : `Créez votre compte pour ${invitation.email}.`}
    >
      <ActionForm action={acceptInvitation} className="space-y-4">
        <input type="hidden" name="token" value={token} />
        {!existing && (
          <label className="block">
            <span className="label">Votre nom</span>
            <input className="input" name="name" autoComplete="name" required />
          </label>
        )}
        <label className="block">
          <span className="label">{existing ? "Mot de passe" : "Mot de passe (10 caractères minimum)"}</span>
          <input className="input" type="password" name="password" autoComplete={existing ? "current-password" : "new-password"} required />
        </label>
        <Submit className="btn w-full">Rejoindre l'équipe</Submit>
      </ActionForm>
    </AuthShell>
  );
}
