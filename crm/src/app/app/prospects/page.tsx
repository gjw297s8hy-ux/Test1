import Link from "next/link";
import type { Prisma } from "@prisma/client";
import { createContact, launchDraft } from "@/app/actions";
import { requireCtx } from "@/lib/auth";
import { db } from "@/lib/db";
import { CHANNELS, CHANNEL_LABEL, CONTACT_STATUSES, STATUS_LABEL, fullName } from "@/lib/labels";
import { CheckAll, Submit } from "@/components/client";
import { Empty, Notice, PageHeader, ScoreBadge, StatusBadge, TextLink } from "@/components/ui";

const PAGE = 50;

export default async function Page({ searchParams }: { searchParams: Promise<{ msg?: string; q?: string; statut?: string; page?: string }> }) {
  const ctx = await requireCtx();
  const sp = await searchParams;
  const q = (sp.q ?? "").trim();
  const status = CONTACT_STATUSES.find((s) => s === sp.statut);
  const page = Math.max(1, Number(sp.page) || 1);

  const where: Prisma.ContactWhereInput = {
    orgId: ctx.orgId,
    ...(status ? { status } : {}),
    ...(q
      ? {
          OR: [
            { firstName: { contains: q, mode: "insensitive" } },
            { lastName: { contains: q, mode: "insensitive" } },
            { email: { contains: q, mode: "insensitive" } },
            { jobTitle: { contains: q, mode: "insensitive" } },
            { company: { name: { contains: q, mode: "insensitive" } } },
            { tags: { has: q } },
          ],
        }
      : {}),
  };
  const [contacts, total, companies] = await Promise.all([
    db.contact.findMany({
      where,
      include: { company: true },
      orderBy: [{ company: { score: { sort: "desc", nulls: "last" } } }, { createdAt: "desc" }],
      skip: (page - 1) * PAGE,
      take: PAGE,
    }),
    db.contact.count({ where }),
    db.company.findMany({ where: { orgId: ctx.orgId }, select: { id: true, name: true }, orderBy: { name: "asc" }, take: 500 }),
  ]);
  const query = (p: number) => {
    const u = new URLSearchParams();
    if (q) u.set("q", q);
    if (status) u.set("statut", status);
    if (p > 1) u.set("page", String(p));
    const str = u.toString();
    return `/app/prospects${str ? `?${str}` : ""}`;
  };

  return (
    <>
      <PageHeader title="Contacts" subtitle={`${total} contact${total > 1 ? "s" : ""}`} />
      <Notice msg={sp.msg} />

      <form className="mb-4 flex flex-wrap gap-2">
        <input className="input max-w-xs" type="search" name="q" defaultValue={q} placeholder="Nom, entreprise, e-mail, tag…" aria-label="Rechercher" />
        <select className="input w-auto" name="statut" defaultValue={status ?? ""} aria-label="Étape">
          <option value="">Toutes les étapes</option>
          {CONTACT_STATUSES.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABEL[s]}
            </option>
          ))}
        </select>
        <button className="btn-ghost" type="submit">
          Filtrer
        </button>
      </form>

      {contacts.length === 0 ? (
        <Empty>
          {q || status ? "Aucun contact ne correspond à ce filtre." : "Aucun contact pour l'instant. Laissez l'agent en trouver, ou ajoutez-en un ci-dessous."}
        </Empty>
      ) : (
        <form action={launchDraft} className="card overflow-hidden">
          <input type="hidden" name="back" value={query(page)} />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px]">
              <thead className="border-b border-white/[0.07] bg-white/[0.02]">
                <tr>
                  <th className="th w-8">
                    <CheckAll name="contactId" />
                  </th>
                  <th className="th">Contact</th>
                  <th className="th">Entreprise</th>
                  <th className="th">Score</th>
                  <th className="th">Étape</th>
                  <th className="th">Coordonnées</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.06]">
                {contacts.map((c) => (
                  <tr key={c.id} className="hover:bg-slate-50">
                    <td className="td">
                      <input type="checkbox" name="contactId" value={c.id} aria-label={`Sélectionner ${fullName(c)}`} disabled={c.doNotContact} />
                    </td>
                    <td className="td">
                      <TextLink href={`/app/prospects/${c.id}`}>{fullName(c)}</TextLink>
                      <p className="text-xs text-slate-500">{c.jobTitle}</p>
                    </td>
                    <td className="td">{c.company ? <TextLink href={`/app/entreprises/${c.company.id}`}>{c.company.name}</TextLink> : <span className="text-slate-400">–</span>}</td>
                    <td className="td">
                      <ScoreBadge score={c.company?.score ?? null} />
                    </td>
                    <td className="td">
                      <StatusBadge status={c.status} />
                      {c.doNotContact && <p className="mt-1 text-xs font-medium text-rose-600">Ne pas contacter</p>}
                    </td>
                    <td className="td text-xs text-slate-600">
                      {[c.email && "E-mail", c.phone && "Téléphone", c.linkedinUrl && "LinkedIn"].filter(Boolean).join(" · ") || <span className="text-slate-400">Aucune</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex flex-wrap items-center gap-3 border-t border-white/[0.07] bg-white/[0.02] px-4 py-3 text-sm">
            <span className="text-slate-600">Pour la sélection, rédiger par :</span>
            {CHANNELS.map((ch) => (
              <label key={ch} className="flex items-center gap-1.5">
                <input type="checkbox" name="channels" value={ch} defaultChecked={ch === "EMAIL"} /> {CHANNEL_LABEL[ch]}
              </label>
            ))}
            <Submit pendingText="Lancement…">Rédiger avec l'agent</Submit>
          </div>
        </form>
      )}

      {total > PAGE && (
        <div className="mt-4 flex items-center justify-between text-sm">
          {page > 1 ? <Link className="btn-ghost" href={query(page - 1)}>Précédent</Link> : <span />}
          <span className="text-slate-500">
            Page {page} sur {Math.ceil(total / PAGE)}
          </span>
          {page * PAGE < total ? <Link className="btn-ghost" href={query(page + 1)}>Suivant</Link> : <span />}
        </div>
      )}

      <details className="card mt-6">
        <summary className="cursor-pointer px-4 py-3 text-sm font-semibold">Ajouter un contact à la main</summary>
        <form action={createContact} className="grid gap-3 border-t border-slate-100 p-4 sm:grid-cols-2 lg:grid-cols-3">
          <label><span className="label">Prénom</span><input className="input" name="firstName" /></label>
          <label><span className="label">Nom</span><input className="input" name="lastName" /></label>
          <label><span className="label">Fonction</span><input className="input" name="jobTitle" /></label>
          <label><span className="label">E-mail professionnel</span><input className="input" type="email" name="email" /></label>
          <label><span className="label">Téléphone</span><input className="input" name="phone" /></label>
          <label><span className="label">Profil LinkedIn</span><input className="input" type="url" name="linkedinUrl" placeholder="https://www.linkedin.com/in/…" /></label>
          <label>
            <span className="label">Entreprise</span>
            <select className="input" name="companyId" defaultValue="">
              <option value="">Aucune</option>
              {companies.map((co) => (
                <option key={co.id} value={co.id}>{co.name}</option>
              ))}
            </select>
          </label>
          <div className="flex items-end"><Submit>Ajouter le contact</Submit></div>
        </form>
      </details>
    </>
  );
}
