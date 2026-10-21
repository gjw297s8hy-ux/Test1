# MG Studio · Site de commande (flyers, teasers, publicités)

Site vitrine avec rendu 3D (Three.js) et un onglet **Commander** où les clients décrivent leur besoin et laissent leurs coordonnées.

- `index.html` : accueil avec scène 3D, services, réalisations, étapes
- `commande.html` : formulaire de commande (besoin + coordonnées)
- `js/config.js` : **le seul fichier à modifier** (Formspree, e-mail, réseaux)
- `js/scene.js` : la scène 3D · `js/form.js` : l'envoi du formulaire · `styles.css` : le style

Aucun outil à installer : ce sont des fichiers HTML/CSS/JS simples.

## 1. Recevoir les commandes par e-mail (Formspree, gratuit)

1. Créez un compte sur [formspree.io](https://formspree.io) avec l'adresse où vous voulez recevoir les demandes.
2. Cliquez sur **+ New Form**, donnez-lui un nom (ex. « Commandes site »).
3. Formspree affiche une adresse du type `https://formspree.io/f/abcdwxyz`. Copiez la fin (`abcdwxyz`).
4. Ouvrez `js/config.js` et remplacez `VOTRE_ID_FORMSPREE` par ce code.
5. Remplacez aussi `contact@exemple.fr` par votre e-mail et mettez vos liens Instagram / TikTok.

Chaque demande arrive alors dans votre boîte mail et dans le tableau de bord Formspree (offre gratuite : 50 demandes par mois). Le bouton « Répondre » de l'e-mail répond directement au client.

Tant que Formspree n'est pas configuré, le formulaire ouvre l'application e-mail du visiteur avec la demande pré-remplie, donc rien n'est perdu.

## 2. Mettre le site en ligne (GitHub Pages, gratuit)

1. Sur GitHub, allez dans **Settings → Pages** du dépôt.
2. Dans « Build and deployment », choisissez **Deploy from a branch**, branche `main`, dossier `/ (root)`, puis **Save**.
3. Après une minute, le site est en ligne à l'adresse affichée (ex. `https://<votre-compte>.github.io/Test1/`).

Netlify ou Vercel fonctionnent aussi : glissez-déposez le dossier, rien à configurer.

## 3. Personnaliser

- Le nom « MG Studio » apparaît dans `index.html` et `commande.html` (logo, titre, pied de page).
- Les réalisations (Soirée BOHO, vidéos salle de sport) utilisent des visuels de démonstration : remplacez les blocs `.thumb` par vos images.
- Les flyers qui flottent dans la scène 3D se changent dans `js/scene.js` (liste `posters`).
