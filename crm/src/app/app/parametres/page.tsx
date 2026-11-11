import { inviteMember, logout, removeMember, revokeInvitation, switchOrg, updateOrg } from "@/app/actions";
import { isAdmin, requireCtx } from "@/lib/auth";
import { db } from "@/lib/db";
import { fmtDate } from "@/lib/labels";
import { agentConfigured } from "@/lib/llm";
import { effectivePlan } from "@/lib/plan";
import { smtpConfigured, twilioConfigured } from "@/lib/send";
import { ConfirmSubmit, CopyButton, Submit } from "@/components/client";
import { Notice, PageHeader } from "@/components/ui";

const ROLE_LABEL = { OWNER: "Propriétaire", ADMIN: "Administrateur", MEMBER: "Membre" } as const;

function Integration({ name, ok, on, off }: { name: string; ok: boolean; on: string; off: string }) {
  return (
    <li className="flex items-start gap-3 px-4 py-3 text-sm">
      <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${ok ? "bg-emerald-500" : "bg-slate-300"}`} />
      <div>
        <p className="font-medium">{name}</p>
        <p className="text-slate-500">{ok ? on : off}</p>
      </div>
    </li>
  );
}

export default async function Page({ searchParams }: { searchParams: Promise<{ msg?: string; invitation?: string; bienvenue?: string }> }) {
  const ctx = await requireCtx();
  const sp = await searchParams;
  const admin = isAdmin(ctx);
  const [org, members, invitations, otherOrgs, plan] = await Promise.all([
    db.organization.findUniqueOrThrow({ where: { id: ctx.orgId } }),
    db.membership.findMany({ where: { orgId: ctx.orgId }, include: { user: true }, orderBy: { id: "asc" } }),
    db.invitation.findMany({ where: { orgId: ctx.orgId, acceptedAt: null, expiresAt: { gt: new Date() } }, orderBy: { createdAt: "desc" } }),
    db.membership.findMany({ where: { userId: ctx.userId, orgId: { not: ctx.orgId } }, include: { org: true } }),
    effectivePlan(ctx.orgId),
  ]);

  return (
    <>
      <PageHeader title="Paramètres" subtitle={org.name} />
      <Notice msg={sp.bienvenue ? "Bienvenue ! Décrivez votre offre ci-dessous : c'est ce qui guide l'agent." : sp.msg} />
      {sp.invitation && (
        <div className="mb-4 rounded-lg border border-brand-100 bg-brand-50 p-4 text-sm">
          <p className="font-medium text-brand-700">Invitation créée. Transmettez ce lien, valable 7 jours ; il ne sera plus affiché.</p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <code className="min-w-0 flex-1 break-all rounded bg-white px-2 py-1.5 text-xs">{sp.invitation}</code>
            <CopyButton text={sp.invitation} label="Copier le lien" />
          </div>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <form action={updateOrg} className="card space-y-4 p-4 lg:col-span-2">
          <h2 className="text-sm font-semibold">Votre entreprise et votre offre</h2>
          <fieldset disabled={!admin} className="space-y-4">
            <label className="block">
              <span className="label">Nom de l'entreprise</span>
              <input className="input" name="name" defaultValue={org.name} required />
            </label>
            <label className="block">
              <span className="label">Votre offre : ce que vous vendez, à qui, et ce qui vous distingue</span>
              <textarea
                className="input"
                name="offer"
                rows={5}
                defaultValue={org.offer}
                placeholder="Exemple : agence de création visuelle. Nous réalisons flyers, teasers vidéo et publicités pour les salles de sport, clubs et organisateurs d'événements. Livraison en 72 h, tarifs au forfait."
              />
            </label>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="label">Nom de l'expéditeur</span>
                <input className="input" name="senderName" defaultValue={org.senderName} placeholder="Prénom Nom" />
              </label>
              <label className="block">
                <span className="label">Adresse de réponse</span>
                <input className="input" type="email" name="replyTo" defaultValue={org.replyTo} />
              </label>
            </div>
            <label className="block">
              <span className="label">Signature des e-mails</span>
              <textarea className="input" name="signature" rows={3} defaultValue={org.signature} placeholder={"Prénom Nom\nFonction, Entreprise\n06 00 00 00 00"} />
            </label>
            <label className="block">
              <span className="label">Mention légale en pied d'e-mail (raison sociale, adresse, SIREN)</span>
              <textarea className="input" name="legalFooter" rows={2} defaultValue={org.legalFooter} />
            </label>
            {admin ? <Submit>Enregistrer</Submit> : <p className="text-sm text-slate-500">Seuls les administrateurs peuvent modifier ces réglages.</p>}
          </fieldset>
        </form>

        <div className="space-y-6">
          <section className="card">
            <h2 className="border-b border-slate-100 px-4 py-3 text-sm font-semibold">Connexions</h2>
            <ul className="divide-y divide-slate-100">
              <Integration name="Agent IA" ok={agentConfigured()} on="Clé API Anthropic présente." off="Ajoutez ANTHROPIC_API_KEY sur le serveur." />
              <Integration name="E-mail" ok={smtpConfigured()} on="Envoi direct depuis l'application." off="Sans SMTP_URL : l'e-mail s'ouvre dans votre messagerie." />
              <Integration name="SMS" ok={twilioConfigured("SMS")} on="Envoi direct par Twilio." off="Sans Twilio : envoi depuis votre téléphone." />
              <Integration name="WhatsApp" ok={twilioConfigured("WHATSAPP")} on="Envoi direct par Twilio." off="Sans Twilio : le message s'ouvre dans WhatsApp." />
              <Integration name="LinkedIn" ok={false} on="" off="Toujours manuel : l'automatisation est interdite par LinkedIn." />
            </ul>
          </section>

          <section className="card p-4 text-sm">
            <h2 className="text-sm font-semibold">Offre</h2>
            <p className="mt-1 text-slate-600">
              {plan === "PRO" ? "Pro : 1 000 lancements de l'agent par mois." : "Gratuite : le CRM complet et un essai de l'agent IA sur une entreprise."}
            </p>
          </section>
        </div>
      </div>

      <section className="card mt-6">
        <h2 className="border-b border-slate-100 px-4 py-3 text-sm font-semibold">Équipe</h2>
        <ul className="divide-y divide-slate-100">
          {members.map((m) => (
            <li key={m.id} className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm">
              <div className="min-w-0 flex-1">
                <p className="font-medium">{m.user.name}</p>
                <p className="text-xs text-slate-500">{m.user.email}</p>
              </div>
              <span className="text-xs text-slate-500">{ROLE_LABEL[m.role]}</span>
              {admin && m.role !== "OWNER" && m.userId !== ctx.userId && (
                <form action={removeMember}>
                  <input type="hidden" name="id" value={m.id} />
                  <ConfirmSubmit message={`Retirer ${m.user.name} de l'équipe ?`}>Retirer</ConfirmSubmit>
                </form>
              )}
            </li>
          ))}
          {invitations.map((inv) => (
            <li key={inv.id} className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm">
              <div className="min-w-0 flex-1">
                <p className="text-slate-700">{inv.email}</p>
                <p className="text-xs text-slate-500">Invitation en attente, expire le {fmtDate(inv.expiresAt)}</p>
              </div>
              {admin && (
                <form action={revokeInvitation}>
                  <input type="hidden" name="id" value={inv.id} />
                  <Submit className="btn-ghost">Annuler</Submit>
                </form>
              )}
            </li>
          ))}
        </ul>
        {admin && (
          <form action={inviteMember} className="flex flex-wrap items-end gap-3 border-t border-slate-100 p-4">
            <label className="min-w-56 flex-1">
              <span className="label">Inviter par e-mail</span>
              <input className="input" type="email" name="email" required />
            </label>
            <label>
              <span className="label">Rôle</span>
              <select className="input" name="role" defaultValue="MEMBER">
                <option value="MEMBER">Membre</option>
                <option value="ADMIN">Administrateur</option>
              </select>
            </label>
            <Submit>Créer l'invitation</Submit>
          </form>
        )}
      </section>

      <section className="card mt-6 p-4 text-sm">
        <h2 className="text-sm font-semibold">Votre compte</h2>
        <p className="mt-1 text-slate-600">
          {ctx.userName} · {ctx.userEmail}
        </p>
        {otherOrgs.map((m) => (
          <form key={m.id} action={switchOrg} className="mt-3">
            <input type="hidden" name="orgId" value={m.orgId} />
            <Submit className="btn-ghost">Basculer vers {m.org.name}</Submit>
          </form>
        ))}
        <form action={logout} className="mt-3">
          <button type="submit" className="btn-ghost">
            Se déconnecter
          </button>
        </form>
      </section>
    </>
  );
}
