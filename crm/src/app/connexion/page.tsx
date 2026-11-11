import Link from "next/link";
import { redirect } from "next/navigation";
import { login } from "@/app/actions";
import { getCtx } from "@/lib/auth";
import { ActionForm, Submit } from "@/components/client";
import { AuthShell } from "@/components/auth-shell";

export default async function Page() {
  if (await getCtx()) redirect("/app");
  return (
    <AuthShell
      title="Connexion"
      footer={
        <>
          Pas encore de compte ?{" "}
          <Link href="/inscription" className="font-medium text-brand-600 hover:underline">
            Créer un compte
          </Link>
        </>
      }
    >
      <ActionForm action={login} className="space-y-4">
        <label className="block">
          <span className="label">Adresse e-mail</span>
          <input className="input" type="email" name="email" autoComplete="email" required />
        </label>
        <label className="block">
          <span className="label">Mot de passe</span>
          <input className="input" type="password" name="password" autoComplete="current-password" required />
        </label>
        <Submit className="btn w-full">Se connecter</Submit>
      </ActionForm>
    </AuthShell>
  );
}
