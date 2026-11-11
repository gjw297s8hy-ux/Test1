import type { Campaign } from "@prisma/client";
import { CHANNELS, CHANNEL_LABEL } from "@/lib/labels";
import { GOALS, GOAL_LIST } from "@/lib/goals";

export function CampaignFields({ campaign }: { campaign?: Campaign }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <fieldset className="sm:col-span-2">
        <legend className="label">Objectif</legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {GOAL_LIST.map((g) => (
            <label
              key={g}
              className="flex cursor-pointer items-start gap-3 rounded-xl border border-white/10 bg-white/[0.03] p-3 transition hover:border-white/25 has-[:checked]:border-violet has-[:checked]:bg-violet/15"
            >
              <input type="radio" name="goal" value={g} defaultChecked={(campaign?.goal ?? "CLIENTS") === g} className="mt-1 accent-violet" />
              <span>
                <span className="block text-sm font-semibold">{GOALS[g].label}</span>
                <span className="block text-xs text-slate-500">{GOALS[g].example}</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>
      <label className="sm:col-span-2">
        <span className="label">Nom de la campagne</span>
        <input className="input" name="name" defaultValue={campaign?.name} placeholder="Cafés indépendants, Lyon" required />
      </label>
      <label>
        <span className="label">Type d'entreprise ou d'établissement visé</span>
        <input className="input" name="industry" defaultValue={campaign?.industry} placeholder="Salles de sport, clubs de fitness" />
      </label>
      <label>
        <span className="label">Zone géographique</span>
        <input className="input" name="location" defaultValue={campaign?.location} placeholder="Lyon et agglomération" />
      </label>
      <label>
        <span className="label">Taille d'entreprise</span>
        <input className="input" name="size" defaultValue={campaign?.size} placeholder="Indépendants, 1 à 20 salariés" />
      </label>
      <label>
        <span className="label">Interlocuteurs visés</span>
        <input className="input" name="roles" defaultValue={campaign?.roles} placeholder="Gérant, responsable marketing" />
      </label>
      <label className="sm:col-span-2">
        <span className="label">Autres critères</span>
        <input className="input" name="keywords" defaultValue={campaign?.keywords} placeholder="Actifs sur Instagram, ouverture récente, pas de franchise" />
      </label>
      <label className="sm:col-span-2">
        <span className="label">Angle du message pour cette cible</span>
        <textarea className="input" name="pitch" rows={3} defaultValue={campaign?.pitch} placeholder="Ce que vous leur proposez et pourquoi maintenant" />
      </label>
      <label>
        <span className="label">Ton</span>
        <input className="input" name="tone" defaultValue={campaign?.tone ?? "professionnel et direct"} />
      </label>
      <fieldset>
        <legend className="label">Canaux</legend>
        <div className="flex flex-wrap gap-3 pt-1.5 text-sm">
          {CHANNELS.map((ch) => (
            <label key={ch} className="flex items-center gap-1.5">
              <input type="checkbox" name="channels" value={ch} defaultChecked={campaign ? campaign.channels.includes(ch) : ch === "EMAIL"} /> {CHANNEL_LABEL[ch]}
            </label>
          ))}
        </div>
      </fieldset>
    </div>
  );
}
