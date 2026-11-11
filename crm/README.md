# CRM Prospection IA

CRM multi-entreprises (SaaS) avec un agent de prospection IA, pour la prospection B2B en France.

L'agent fait quatre choses, toujours sous votre contrôle :

1. **Trouver** : à partir d'une cible (secteur, zone, taille, interlocuteurs), il cherche des entreprises sur le web, avec leurs interlocuteurs et les pages sources.
2. **Enrichir et scorer** : activité, actualités, signaux d'accroche, score d'adéquation de 0 à 100.
3. **Rédiger** : e-mail, note LinkedIn, SMS, WhatsApp, et relances qui tiennent compte des échanges précédents.
4. **Traiter les réponses** : vous collez la réponse reçue, il la classe, met la fiche à jour, crée la tâche suivante et propose une réponse.

**Rien ne part sans validation humaine** : chaque message est un brouillon que vous relisez, corrigez, puis envoyez.

## Installation

Il faut Node.js 20 ou plus et une base PostgreSQL (locale, [Neon](https://neon.tech) ou [Supabase](https://supabase.com)).

```bash
cd crm
npm install
cp .env.example .env      # puis remplissez les valeurs
npm run db:deploy         # crée les tables
npm run dev               # http://localhost:3000
```

Créez votre compte sur `/inscription`, décrivez votre offre dans **Paramètres**, puis créez une campagne dans **Agent IA**.

## Réglages (`.env`)

| Variable | Rôle |
| --- | --- |
| `DATABASE_URL` | Base PostgreSQL. Obligatoire. |
| `APP_URL` | Adresse publique du site : sert aux liens d'invitation et de désinscription. |
| `ADMIN_EMAILS` | Vos adresses de connexion au CRM, séparées par des virgules. Ces espaces ont toujours accès à l'agent ; l'offre gratuite ne l'a pas. |
| `ANTHROPIC_API_KEY` | Clé de l'agent IA ([console.anthropic.com](https://console.anthropic.com)). Sans elle, le CRM fonctionne mais l'agent est inactif. |
| `ANTHROPIC_MODEL` | Modèle de l'agent (par défaut `claude-opus-5-5`). |
| `SMTP_URL`, `SMTP_FROM` | Envoi direct des e-mails. Sans eux, l'e-mail s'ouvre pré-rempli dans votre messagerie. |
| `TWILIO_*` | Envoi direct des SMS et WhatsApp. Sans eux, le message s'ouvre sur votre téléphone ou dans WhatsApp. |

LinkedIn est toujours manuel : l'application ouvre le profil et copie le texte, parce que l'automatisation est interdite par LinkedIn.

## Mise en ligne

Le plus simple, sans rien installer sur votre ordinateur : [Vercel](https://vercel.com).

1. Sur Vercel, **Add New → Project**, puis importez ce dépôt GitHub.
2. Dans **Root Directory**, choisissez `crm`.
3. Dans l'onglet **Storage** du projet, ajoutez une base **Neon** (Postgres) : Vercel renseigne `DATABASE_URL` tout seul.
4. Dans **Settings → Environment Variables**, ajoutez `ANTHROPIC_API_KEY` et `APP_URL` (l'adresse de votre site, par exemple `https://crm.votredomaine.fr`).
5. Lancez le déploiement. Les tables sont créées automatiquement à chaque mise en ligne.

Une recherche de l'agent dure quelques minutes : dans **Settings → Functions**, réglez la durée maximale sur 300 secondes.

## RGPD

- L'agent ne relève que des coordonnées professionnelles publiées, et enregistre l'URL source de chaque fiche.
- Chaque e-mail porte votre mention légale et un lien de désinscription.
- Une opposition (lien, réponse du prospect, ou case « Ne pas contacter ») bloque tout envoi et écarte les brouillons en attente.
- Un contact se supprime définitivement, avec tout son historique, depuis sa fiche.

Vous restez responsable de votre prospection : tenez votre registre de traitements et vérifiez les données avant de vous en servir.

## Organisation du code

| Chemin | Rôle |
| --- | --- |
| `prisma/schema.prisma` | Modèle de données. Chaque table porte un `orgId`. |
| `src/lib/auth.ts` | Comptes, sessions, rôles. `requireCtx()` ouvre chaque page et chaque action. |
| `src/lib/llm.ts` | Appels à l'API Claude : recherche web et réponses structurées. |
| `src/lib/agent.ts` | Les quatre métiers de l'agent, leurs consignes, et le suivi des lancements. |
| `src/lib/send.ts` | Envoi e-mail (SMTP) et SMS/WhatsApp (Twilio). |
| `src/app/actions.ts` | Toutes les actions serveur. |
| `src/app/app/` | Les écrans. |

Cloisonnement : toute requête est filtrée par l'`orgId` de la session. Une fiche d'une autre entreprise répond 404.

## Sécurité

- Mots de passe hachés (scrypt), sessions dans un cookie `httpOnly`, données cloisonnées par entreprise.
- Connexion : 5 erreurs par compte et 30 par connexion sur 15 minutes, puis attente. Même message et même durée de réponse qu'une adresse ait un compte ou non.
- Inscription : 3 comptes par connexion et par jour, pour freiner les essais gratuits en série.
- En-têtes de sécurité sur toutes les pages : interdiction d'afficher le site dans un cadre, HTTPS forcé, etc.

## Ce qui n'est pas encore fait

- Paiement et abonnements : l'offre (gratuite ou pro) existe en base avec son quota mensuel, sans Stripe.
- Réception automatique des réponses : pour l'instant, on colle la réponse dans la fiche du contact.
- Mot de passe oublié et vérification de l'adresse e-mail à l'inscription (il faut d'abord un service d'envoi d'e-mails).
