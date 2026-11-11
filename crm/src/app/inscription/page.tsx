import Link from "next/link";
import { redirect } from "next/navigation";
import { signup } from "@/app/actions";
import { getCtx } from "@/lib/auth";
import { ActionForm, Submit } from "@/components/client";
import { AuthShell } from "@/components/auth-shell";

export default async function Page() {
  if (await getCtx()) redirect("/app");
  return (
    <AuthShell
      title="Créer un compte"
      subtitle="Un espace par entreprise. Vous pourrez inviter votre équipe ensuite."
      footer={
        <>
          Déjà inscrit ?{" "}
          <Link href="/connexion" className="font-medium text-brand-600 hover:underline">
            Se connecter
          </Link>
        </>
      }
    >
      <ActionForm action={signup} className="space-y-4">
        <label className="block">
          <span className="label">Votre nom</span>
          <input className="input" name="name" autoComplete="name" required />
        </label>
        <label className="block">
          <span className="label">Nom de votre entreprise</span>
          <input className="input" name="orgName" autoComplete="organization" required />
        </label>
        <label className="block">
          <span className="label">Adresse e-mail professionnelle</span>
          <input className="input" type="email" name="email" autoComplete="email" required />
        </label>
        <label className="block">
          <span className="label">Mot de passe (10 caractères minimum)</span>
          <input className="input" type="password" name="password" autoComplete="new-password" minLength={10} required />
        </label>
        <Submit className="btn w-full">Créer mon espace</Submit>
      </ActionForm>
    </AuthShell>
  );
}
