# Auto shop Telegram (produits numériques, paiement crypto)

Un bot Telegram qui vend des produits numériques et les livre tout seul. Les clients paient
directement sur **vos propres adresses** crypto : aucun intermédiaire, aucune commission, et le
bot n'a jamais accès à vos clés privées (il ne fait que lire la blockchain).

## Ce que fait le bot

- **Client** : catalogue, choix de la quantité, choix de la crypto, puis une adresse et un montant
  exact à payer. Dès que le paiement est confirmé, le produit arrive dans la conversation.
- **Admin** (`/admin`) : ajouter des produits, charger du stock, changer un prix, masquer ou
  supprimer un produit, valider ou annuler une commande à la main, voir les statistiques.
- Deux types de produits :
  - **Articles uniques** (clés, codes, licences) : une ligne = un article, chaque vente en consomme un.
  - **Fichier ou texte** : le même contenu pour chaque acheteur, sans limite de stock.

## Installation

Il faut Python 3.10 ou plus récent.

```bash
cd telegram-autoshop
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # puis remplissez .env
python -m bot
```

À mettre dans `.env` :

1. `BOT_TOKEN` : créez le bot avec [@BotFather](https://t.me/BotFather) (`/newbot`) et copiez le jeton.
2. `ADMIN_IDS` : votre identifiant Telegram numérique (demandez-le à [@userinfobot](https://t.me/userinfobot)).
3. Vos adresses : `WALLET_BTC`, `WALLET_LTC`, `WALLET_USDT_TRC20`. Laissez vide ce que vous n'utilisez pas.

Ensuite, ouvrez le bot dans Telegram, envoyez `/start` puis `/admin` pour créer votre premier produit.

Le bot doit tourner en continu : lancez-le sur un petit serveur (VPS), pas sur votre téléphone.
Le dossier contient un fichier `shop.db` (produits, stock, commandes) : sauvegardez-le régulièrement.

## Comment le paiement est reconnu

Tous les clients paient sur la même adresse, donc le bot identifie une commande par son
**montant** : chaque commande reçoit un montant légèrement différent (quelques centimes au plus),
unique parmi les commandes en cours. Le bot interroge la blockchain toutes les 30 secondes et
livre quand il voit une transaction de ce montant exact.

| Monnaie | Vérification | Source |
| --- | --- | --- |
| Bitcoin | automatique | mempool.space |
| Litecoin | automatique | litecoinspace.org |
| USDT (TRC20) | automatique | TronGrid |
| Autres (`EXTRA_WALLETS`) | manuelle : le client envoie l'identifiant de transaction, un admin valide | — |

À savoir :

- **Le montant doit être exact.** Si un client envoie un autre montant (frais déduits par une
  plateforme d'échange, par exemple), le paiement n'est pas reconnu. Retrouvez la commande dans
  `/admin` → « Commandes à traiter » et validez-la à la main après avoir vérifié la réception.
- **Paiement en retard** : une commande expire après `ORDER_TTL_MIN` minutes et son stock est
  remis en vente, mais un paiement qui arrive dans les 6 heures suivantes est encore reconnu et
  livré. S'il n'y a plus de stock, vous recevez une alerte : rechargez le stock et appuyez sur
  « Réessayer la livraison », ou remboursez le client.
- **Confirmations** : `MIN_CONFIRMATIONS=1` attend qu'une transaction soit dans un bloc
  (environ 10 min en Bitcoin, 2,5 min en Litecoin). Mettre 0 livre plus vite mais expose à la
  double dépense.
- Les prix sont fixés en euros (ou dollars, `FIAT=USD`) et convertis au cours CoinGecko au moment
  de la commande.
- Les remboursements se font à la main, depuis votre portefeuille.

## Mini app (boutique en 3D dans Telegram)

Le dossier `miniapp/` contient une page de boutique qui s'ouvre dans Telegram : fond en 3D temps
réel (océan au coucher du soleil), produits en cartes, choix de la quantité et de la crypto.
Elle est facultative : sans elle, le bot fonctionne avec ses boutons habituels.

La page n'a pas de serveur. Le bot lui transmet le catalogue dans le lien du bouton, et la page
renvoie le choix du client au bot, qui répond dans la conversation avec l'adresse et le montant.

Mise en place :

1. Mettez le dossier `miniapp/` en ligne sur un hébergeur de pages statiques en `https`
   (Netlify, Cloudflare Pages...). Sur Netlify : créez un compte gratuit, puis
   « Add new site » → « Deploy manually » et glissez-y le dossier `miniapp`.
2. Copiez l'adresse obtenue dans `.env` : `MINIAPP_URL=https://votre-adresse.netlify.app/`
3. Relancez le bot et envoyez `/start` : un bouton « 🌴 Ouvrir la boutique » apparaît en bas de l'écran.

À savoir :

- Le catalogue affiché est celui du dernier `/start` du client. Le bot revérifie toujours le
  stock réel au moment de la commande.
- Le lien ne peut pas contenir un catalogue illimité : au-delà d'une vingtaine de produits, les
  descriptions puis les derniers produits sont retirés de la mini app (ils restent dans le
  catalogue à boutons).
- La page ne contient ni jeton ni adresse crypto.
- `miniapp/scene.js` est généré à partir de `miniapp/src/scene.js` avec la bibliothèque
  [three.js](https://threejs.org) (licence MIT), dont provient aussi `waternormals.jpg`.
  Pour le régénérer : `npm i three esbuild` puis
  `npx esbuild src/scene.js --bundle --minify --format=iife --outfile=scene.js`.

## Tests

```bash
pip install pytest
pytest
```

Les tests tournent sans Telegram ni réseau : ils simulent un client et un admin de bout en bout
(achat, paiement détecté, livraison, expiration, paiement en retard, validation manuelle).

## Structure

| Fichier | Rôle |
| --- | --- |
| `bot/__main__.py` | Démarrage |
| `bot/config.py` | Lecture de `.env` |
| `bot/db.py` | Base SQLite : produits, stock, commandes |
| `bot/chains.py` | Taux de change et lecture des paiements sur la blockchain |
| `bot/payments.py` | Surveillance des paiements et livraison |
| `bot/handlers/user.py` | Menus client |
| `bot/handlers/admin.py` | Menus admin |
| `bot/miniapp.py` | Lien et bouton de la mini app |
| `miniapp/` | La page de la mini app (à héberger) |
