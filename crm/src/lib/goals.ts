import type { CampaignGoal } from "@prisma/client";

/**
 * Ce que cherche une campagne. Chaque objectif change ce que l'agent cherche, les signaux qu'il releve,
 * l'interlocuteur vise et le ton du message : trouver un point de vente n'est pas vendre une prestation.
 */
export const GOALS: Record<
  CampaignGoal,
  { label: string; short: string; example: string; find: string; signals: string; roles: string; score: string; message: string }
> = {
  CLIENTS: {
    label: "Trouver des clients",
    short: "Clients",
    example: "Une agence qui cherche des salles de sport à qui vendre ses visuels",
    find: "des entreprises qui ont besoin de notre offre et pourraient l'acheter",
    signals: "ouverture, lancement, recrutement, nouveau site, levée de fonds, déménagement, événement à venir",
    roles: "dirigeant ou responsable du service concerné par l'offre",
    score: "l'entreprise correspond nettement à la cible et montre un signal de besoin",
    message: "Le message propose notre offre comme réponse à un besoin probable du destinataire.",
  },
  SUBCONTRACTING: {
    label: "Trouver de la sous-traitance",
    short: "Sous-traitance",
    example: "Un livreur de colis qui cherche des transporteurs et e-commerçants qui sous-traitent",
    find: "des donneurs d'ordre : des entreprises qui confient une partie de leur activité à des prestataires ou indépendants, dans le domaine de notre offre",
    signals: "recherche de prestataires ou d'indépendants, appels d'offres, offres d'emploi en volume, pics d'activité, nouveaux marchés, croissance rapide, plateformes qui référencent des partenaires",
    roles: "responsable des opérations, des achats, de la logistique ou des partenariats",
    score: "l'entreprise sous-traite déjà ou montre un besoin de capacité dans le domaine de notre offre",
    message: "Le message propose nos services en renfort ou en sous-traitance : capacité, réactivité, zone couverte, conditions simples pour un premier essai.",
  },
  OUTLETS: {
    label: "Trouver des points de vente",
    short: "Points de vente",
    example: "Une pâtisserie qui cherche des cafés, épiceries fines et hôtels où vendre ses gâteaux",
    find: "des lieux et des commerces qui pourraient vendre, servir ou utiliser nos produits sans les fabriquer eux-mêmes : revendeurs, boutiques, restaurants, hôtels, entreprises clientes",
    signals: "produits d'artisans locaux déjà proposés, offre de produits faits maison absente ou achetée à l'extérieur, ouverture récente, mise en avant du local et de l'artisanal, événements, clientèle compatible",
    roles: "gérant, responsable des achats ou de l'approvisionnement",
    score: "le lieu vend ou sert déjà des produits comparables, ou sa clientèle correspond nettement à nos produits",
    message: "Le message propose de référencer nos produits : dépôt-vente, dégustation, échantillons ou première commande d'essai, avec ce qui les distingue.",
  },
  PARTNERS: {
    label: "Trouver des partenaires",
    short: "Partenariats",
    example: "Une créatrice de contenu fitness qui cherche des marques pour une série de vidéos",
    find: "des entreprises ou des marques avec qui monter un partenariat gagnant-gagnant autour de notre projet : co-promotion, sponsoring, collaboration de contenu, offre commune",
    signals: "partenariats ou collaborations déjà annoncés, travail avec des créateurs ou influenceurs, lancement de produit, campagne en cours, valeurs ou public communs avec nous",
    roles: "responsable marketing, communication, partenariats ou influence",
    score: "l'entreprise fait déjà des partenariats comparables et son public recoupe nettement le nôtre",
    message: "Le message propose une collaboration concrète : l'idée, ce que chacun y gagne, et une prochaine étape simple.",
  },
};

export const GOAL_LIST = Object.keys(GOALS) as CampaignGoal[];

export function goalBrief(goal: CampaignGoal): string {
  const g = GOALS[goal];
  return `Objectif de la campagne : ${g.label.toLowerCase()}.
Tu cherches ${g.find}.
Signaux qui comptent : ${g.signals}.
Interlocuteur à viser en priorité : ${g.roles}.`;
}
