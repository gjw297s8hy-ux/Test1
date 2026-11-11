import Link from "next/link";
import type { Prisma } from "@prisma/client";
import { createCompany, launchEnrich } from "@/app/actions";
import { requireCtx } from "@/lib/auth";
import { db } from "@/lib/db";
import { CheckAll, Submit } from "@/components/client";
import { Empty, Notice, PageHeader, ScoreBadge, TextLink } from "@/components/ui";

const PAGE = 50;

export default async function Page({ searchParams }: { searchParams: Promise<{ msg?: string; q?: string; page?: string }> }) {
  const ctx = await requireCtx();
  const sp = await searchParams;
  const q = (sp.q ?? "").trim();
  const page = Math.max(1, Number(sp.page) || 1);
  const where: Prisma.CompanyWhereInput = {
    orgId: ctx.orgId,
    ...(q
      ? {
          OR: [
            { name: { contains: q, mode: "insensitive" } },
            { city: { contains: q, mode: "insensitive" } },
            { industry: { contains: q, mode: "insensitive" } },
            { tags: { has: q } },
          ],
        }
      : {}),
  };
  const [companies, total] = await Promise.all([
    db.company.findMany({
      where,
      include: { _count: { select: { contacts: true } } },
      orderBy: [{ score: { sort: "desc", nulls: "last" } }, { createdAt: "desc" }],
      skip: (page - 1) * PAGE,
      take: PAGE,
    }),
    db.company.count({ where }),
  ]);
  const query = (p: number) => {
    const u = new URLSearchParams();
    if (q) u.set("q", q);
    if (p > 1) u.set("page", String(p));
    const str = u.toString();
    return `/app/entreprises${str ? `?${str}` : ""}`;
  };

  return (
    <>
      <PageHeader title="Entreprises" subtitle={`${total} entreprise${total > 1 ? "s" : ""}, classées par score`} />
      <Notice msg={sp.msg} />
      <form className="mb-4 flex flex-wrap gap-2">
        <input className="input max-w-xs" type="search" name="q" defaultValue={q} placeholder="Nom, ville, secteur, tag…" aria-label="Rechercher" />
        <button className="btn-ghost" type="submit">
          Filtrer
        </button>
      </form>

      {companies.length === 0 ? (
        <Empty>{q ? "Aucune entreprise ne correspond." : "Aucune entreprise pour l'instant."}</Empty>
      ) : (
        <form action={launchEnrich} className="card overflow-hidden">
          <input type="hidden" name="back" value={query(page)} />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px]">
              <thead className="border-b border-slate-200 bg-slate-50">
                <tr>
                  <th className="th w-8">
                    <CheckAll name="companyId" />
                  </th>
                  <th className="th">Entreprise</th>
                  <th className="th">Secteur</th>
                  <th className="th">Ville</th>
                  <th className="th">Score</th>
                  <th className="th">Contacts</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {companies.map((c) => (
                  <tr key={c.id} className="hover:bg-slate-50">
                    <td className="td">
                      <input type="checkbox" name="companyId" value={c.id} aria-label={`Sélectionner ${c.name}`} />
                    </td>
                    <td className="td">
                      <TextLink href={`/app/entreprises/${c.id}`}>{c.name}</TextLink>
                      <p className="text-xs text-slate-500">{c.domain}</p>
                    </td>
                    <td className="td text-slate-600">{c.industry}</td>
                    <td className="td text-slate-600">{c.city}</td>
                    <td className="td">
                      <ScoreBadge score={c.score} />
                    </td>
                    <td className="td tabular-nums text-slate-600">{c._count.contacts}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex flex-wrap items-center gap-3 border-t border-slate-200 bg-slate-50 px-4 py-3 text-sm">
            <span className="text-slate-600">Pour la sélection (15 au plus par lancement) :</span>
            <Submit pendingText="Lancement…">Enrichir et scorer avec l'agent</Submit>
          </div>
        </form>
      )}

      {total > PAGE && (
        <div className="mt-4 flex items-center justify-between text-sm">
          {page > 1 ? <Link className="btn-ghost" href={query(page - 1)}>Précédent</Link> : <span />}
          <span className="text-slate-500">Page {page} sur {Math.ceil(total / PAGE)}</span>
          {page * PAGE < total ? <Link className="btn-ghost" href={query(page + 1)}>Suivant</Link> : <span />}
        </div>
      )}

      <details className="card mt-6">
        <summary className="cursor-pointer px-4 py-3 text-sm font-semibold">Ajouter une entreprise à la main</summary>
        <form action={createCompany} className="grid gap-3 border-t border-slate-100 p-4 sm:grid-cols-2 lg:grid-cols-3">
          <label><span className="label">Nom</span><input className="input" name="name" required /></label>
          <label><span className="label">Site web</span><input className="input" name="website" placeholder="exemple.fr" /></label>
          <label><span className="label">Secteur</span><input className="input" name="industry" /></label>
          <label><span className="label">Ville</span><input className="input" name="city" /></label>
          <label><span className="label">Taille</span><input className="input" name="size" /></label>
          <div className="flex items-end"><Submit>Ajouter l'entreprise</Submit></div>
        </form>
      </details>
    </>
  );
}
