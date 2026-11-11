import { redirect } from "next/navigation";
import { db } from "@/lib/db";
import { Submit } from "@/components/client";
import { AuthShell } from "@/components/auth-shell";

// Page publique : la confirmation passe par un bouton, pour qu'un robot qui suit le lien ne desinscrive personne.
async function optOut(fd: FormData) {
  "use server";
  const token = String(fd.get("token") ?? "");
  const contact = await db.contact.findUnique({ where: { unsubscribeToken: token } });
  if (contact) {
    await db.contact.update({ where: { id: contact.id }, data: { doNotContact: true, status: "NOT_INTERESTED" } });
    await db.message.updateMany({ where: { contactId: contact.id, status: "DRAFT" }, data: { status: "DISCARDED" } });
    await db.activity.create({
      data: { orgId: contact.orgId, contactId: contact.id, kind: "rgpd", summary: "Opposition à la prospection via le lien de désinscription" },
    });
  }
  redirect(`/desinscription/${token}?ok=1`);
}

export default async function Page({ params, searchParams }: { params: Promise<{ token: string }>; searchParams: Promise<{ ok?: string }> }) {
  const { token } = await params;
  const { ok } = await searchParams;
  const contact = await db.contact.findUnique({ where: { unsubscribeToken: token }, include: { org: true } });
  if (!contact) return <AuthShell title="Lien invalide" subtitle="Ce lien de désinscription n'est pas reconnu."><span /></AuthShell>;
  if (ok || contact.doNotContact) {
    return (
      <AuthShell title="C'est noté" subtitle={`Vous ne recevrez plus de messages de prospection de ${contact.org.name}.`}>
        <span />
      </AuthShell>
    );
  }
  return (
    <AuthShell title="Ne plus recevoir nos messages" subtitle={`Confirmez pour ne plus être contacté par ${contact.org.name}.`}>
      <form action={optOut}>
        <input type="hidden" name="token" value={token} />
        <Submit className="btn w-full">Confirmer ma désinscription</Submit>
      </form>
    </AuthShell>
  );
}
