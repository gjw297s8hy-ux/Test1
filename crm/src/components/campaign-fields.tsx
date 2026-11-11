import type { Campaign } from "@prisma/client";
import { CHANNELS, CHANNEL_LABEL } from "@/lib/labels";

export function CampaignFields({ campaign }: { campaign?: Campaign }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <label className="sm:col-span-2">
        <span className="label">Nom de la campagne</span>
        <input className="input" name="name" defaultValue={campaign?.name} placeholder="Salles de sport indépendantes, Lyon" required />
      </label>
      <label>
        <span className="label">Secteur visé</span>
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
