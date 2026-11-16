# SPEC — Fraude carrousel à la TVA

GOAL:    en 60 s, le spectateur comprend le mécanisme (une société encaisse la TVA sans la reverser, une autre la récupère, le circuit recommence) et retient que c'est de l'argent public qui disparaît.
OUTPUT:  HyperFrames, 1080 x 1920, 30 fps.
TIME:    60 s x 30 = 1800 images. La voix est l'horloge ; tant qu'elle n'existe pas, le découpage du scénario fait foi (0-5 / 5-13 / 13-23 / 23-27 / 27-38 / 38-46 / 46-54 / 54-60).

LOOK:    ville miniature en 3D posée sur une carte d'Europe en relief (contours réels simplifiés).
         Bleu nuit #101827 (décor, contours de texte) · blanc cassé #F5F2EB (factures, textes, bâtiments)
         · orange #FF9F1C (TVA, pièces, flux) · rouge #FF4057 (détournement) — rien d'autre, sauf le brun du carton.
         Titres : Archivo Black, capitales, 104 px (90 px sous le compteur), contour bleu nuit 16 px.
         Sous-titres : Montserrat 900, 68 px, contour 14 px, groupes de 3 à 5 mots, mots clés à 112 %.
         Lumière : clé chaude en haut à droite, contre-jour bleu froid + liseré orange sur les avatars.
         L'ambiance s'assombrit : claire jusqu'à 19,4 s, 55 % à 21,5 s, 100 % à 57 s.
OBJECTS: sociétés A, B, C, D = immeubles à fenêtres éclairées et enseigne lumineuse ; carton brun à bande blanche ;
         pièces = cylindres orange (rouges une fois détournées) ; État = bassin rond rempli de piles de pièces,
         qui devient le trou final ; factures = feuilles blanc cassé avec ligne TVA sur fond orange.
MOTION:  entrées en dépassement (back, 0,3 s), déplacements ease-in-out cubique, poses des avatars en 0,42 s
         avec le second bras et la tête en retard de 90 ms. Une action ou un recadrage toutes les 2 s environ.

SHOTS
- 0-5     Avatar 1 en plan rapproché, zoom en 0,5 s ; la ligne TVA de la facture passe à l'orange (2,15 s) puis part en particules (2,9 s). Titre « LA TVA QUI DISPARAÎT ».
- 5-13    Avatar 2 pose le produit sur le comptoir ; bloc 120 € TTC, qui se sépare en 100 € HT + 20 € TVA ; les 20 € deviennent 6 pièces qui volent vers l'État.
- 13-23   Plongée : la caméra suit le carton A -> B -> C ; C paie la TVA à B (pièces orange) ; B s'éteint et s'enfonce, les pièces virent au rouge. Narrateur en incrustation.
- 23-27   Avatar 2 attrape la facture, gros plan surpris, la pousse vers la caméra : elle remplit l'écran.
- 27-38   La feuille devient la facture de la société D ; « TVA réclamée » face à « TVA jamais reversée » ; l'État paie D, le compteur passe à − 20 €.
- 38-46   Les immeubles se rangent en cercle, le carton revient en A, la flèche circulaire se trace, le carton tourne de plus en plus vite.
- 46-54   Compteur en haut ; entreprise honnête à 120 € face au concurrent fraudeur à 99 € ; l'avatar 1 désigne les deux.
- 54-60   Les deux avatars au premier plan ; le bassin devient un trou où tombent les pièces ; titre final ; la dernière pièce devient le point orange qui rejoint la ligne TVA de la facture (boucle).

BANNED:  particules décoratives, halos et néons, cartes en verre, trois cartes en ligne, texte qui bouge pendant qu'on le lit, texte sous 28 px, rien dans les 168 px du haut ni de texte sous 1330 px.
QA:      0,05 s (vignette : visage + facture) · 3,6 · 9,6 · 18,6 · 21 · 24,8 · 33,6 · 44 · 51,3 · 57,8 · 59,9 (raccord de boucle).
