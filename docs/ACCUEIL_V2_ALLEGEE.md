# YggNexus : Accueil V2 allégée

Écran 1 seulement. Ce document modifie la spec « Accueil V2 : l'arbre comme interface » du 23 octobre 2026. Tout ce qui n'est pas mentionné ici reste tel quel dans la V2.

---

## 1. Le principe

L'arbre vit dans le héros. Le reste de la page est sobre, sur fond uni, et rappelle l'arbre par un seul motif dessiné en code : une ligne de branche fine.

Pourquoi :

- Une seule image par thème au lieu d'un paysage découpé en trois zones raccordées. Faisable avec ChatGPT et de la retouche.
- La charte v1.0 (« la sophistication vient de la retenue ») reste respectée sous le pli. La V2 complète devient une exception de héros, pas un costume sur toute la page.
- Les sections recettes et communauté peuvent être absentes au lancement sans laisser de racines qui ne portent rien.
- Poids des images divisé par trois environ.

---

## 2. Ce qui reste identique à la V2

- Jetons de couleur Forêt et Lumière, contrastes calculés
- Typographie Syne et Inter, tailles et interlignes
- Espacements, rayons, ombres, cibles tactiles
- Tous les composants et leurs états (boutons, tuiles, cartes, champ, menus, badges)
- Comportement de la recherche et messages d'état
- Textes exacts en français, sauf le nom accessible de la marque (section 7)
- En-tête, menu mobile, langue, thème, pied
- Ordre des six besoins dans le DOM
- Règles de fiabilité des recettes et de transparence

---

## 3. Ce qui change

| Élément | V2 complète | V2 allégée |
|---|---|---|
| Illustration | Paysage continu en 3 zones (canopée, tronc, racines) | Une seule image, limitée au héros |
| Sous le héros | Arbre derrière chaque section | Fond `canvas` uni |
| Rappel de l'arbre | Rameaux illustrés autour des cartes | Une ligne de branche SVG fine, dessinée en code, dans la section besoins seulement |
| Besoins desktop | 6 plaques de part et d'autre d'un tronc central | Grille 3 colonnes × 2 rangées |
| Besoins mobile | Colonne le long d'un rail de tronc illustré | Colonne simple, ligne de branche SVG à gauche |
| Raccord sombre / clair | Même géométrie au pixel près | Même zone calme à gauche, le reste peut varier |
| Images décoratives | 550 Ko mobile, 1 Mo desktop | 60 Ko mobile, 100 Ko desktop (mesuré, section 9) |
| Fond `canvas` clair | `#edf1e7` | `#ece9e4`, aligné sur la brume de l'image Lumière (section 4) |
| `surface-hover` clair | `#f3f5ec` | `#f5f2ec`, même raison |
| Chargement différé des racines | Requis | Sans objet |

---

## 4. Le héros

### Composition

- Desktop 1280 : texte et recherche dans la moitié gauche (max. 640 px). Tronc et canopée dans la moitié droite.
- Tablette 768 : même image, recadrée sur le tronc à droite.
- Mobile 375 et tablette sous 768 : **arbre en bandeau**. Voir plus bas.
- Hauteur du héros desktop : son contenu plus 64 px. L'image se cadre dessus (`object-fit: cover`), elle ne dicte pas la hauteur.

### Mobile : l'arbre en bandeau

Le texte ne passe jamais devant l'arbre sur téléphone. L'arbre occupe une bande en haut, le texte commence en dessous, sur le fond uni.

- Image : `hero-<thème>-750`, 750 × 560 px, affichée à 375 × 280
- Bande visible : 240 px de haut sous l'en-tête, image cadrée par le haut (`object-position: top`)
- Le bas de la bande se fond dans `canvas` sur 64 px (masque)
- Le texte (tagline, H1, corps, recherche) commence 24 px sous la bande, sur `canvas`. Plus besoin de support opaque derrière le titre sur mobile
- Hauteur estimée : en-tête 64, bande 240, texte et recherche environ 400. Le bouton Trouver tombe vers 700 px : visible sans défiler sur un iPhone standard (812), pas sur un iPhone SE (667). Si c'est un problème à l'essai, réduire la bande à 200 px

Le bandeau est recadré dans l'image desktop du même thème. Les deux thèmes ont donc exactement la même géométrie, et l'image Lumière mobile n'a pas à être générée.

### Fond clair ajusté

Le brouillard de l'image Lumière est un ivoire neutre (mesuré : `#ebe8e5` à `#e7e4e2` dans le bas à gauche). Le `canvas` clair passe de `#edf1e7` à `#ece9e4` pour que le fondu ne fasse pas de couture.

Contrastes recalculés sur le nouveau `canvas` clair :

| Paire | Avant | Après | Seuil |
|---|---|---|---|
| `text` | 13,65:1 | 12,91:1 | 4,5 |
| `text-muted` | 5,65:1 | 5,34:1 | 4,5 |
| `link` | 6,79:1 | 6,42:1 | 4,5 |
| `accent` utilisé en texte | 4,93:1 | 4,66:1 | 4,5 |
| `border-control` | 3,56:1 | 3,36:1 | 3 |

Tout reste conforme. Le `canvas` sombre `#07110e` est déjà collé au bas de l'image Forêt (`#040a0c`, écart 1,04:1) : pas de changement.

### Fondu vers la page

Le bas de l'image se fond dans `canvas` sur 96 px desktop / 64 px mobile. C'est un masque de transparence, pas un dégradé coloré.

### Ce que l'image doit contenir

- Une zone calme et sombre (Forêt) ou claire (Lumière) sur toute la moitié gauche, sans feuille qui passe derrière le titre
- Le tronc et la canopée à droite
- Aucun texte, aucun logo, aucun cadre de carte, aucun anneau runique
- Pas de halo doré autour de quoi que ce soit : la lumière est dans la scène, pas autour de l'interface

### La recherche

Le panneau de recherche garde son support opaque. Pas de branche illustrée qui l'entoure. Une ombre `shadow-card` suffit à le détacher.

---

## 5. La ligne de branche (motif SVG)

Un seul tracé organique, dessiné en code, épaisseur 1,5 px, couleur `border-control`. Il n'est pas une image.

### Desktop 1280

- Une ligne horizontale ondulée qui part du bord gauche du conteneur, passe sous le titre « Choisis ta branche » et se termine au bord droit
- De cette ligne descendent six courts rameaux, un vers le milieu du bord haut de chaque tuile
- Rameaux de 16 à 24 px de long, légèrement courbés, jamais rectilignes

### Mobile 375

- Une ligne verticale ondulée dans un rail de 16 px à gauche des tuiles
- Un court rameau horizontal vers le milieu du bord gauche de chaque tuile
- Tuiles : 343 − 16 − 8 = 319 px de large

### États

- Survol ou focus d'une tuile : son rameau passe en couleur `accent`. Pas d'animation, transition de couleur 120 ms.
- Mouvement réduit : aucune transition.
- Le SVG est décoratif : `aria-hidden="true"`, `pointer-events: none`.

### Pourquoi en code

Il suit la position réelle des tuiles, même quand un libellé passe sur deux lignes ou que la langue change. Il pèse moins de 2 Ko. Il prend la couleur du thème automatiquement.

---

## 6. Les autres sections

Fond `canvas` uni. Cartes sur `surface`, contour `border-subtle`, ombre `shadow-card`. Aucun décor.

| Section | Desktop 1280 | Mobile 375 | Au lancement |
|---|---|---|---|
| Besoins | Grille 3 × 2, tuiles égales, gap 24 | Colonne, gap 12 | Affichée |
| Outils | 3 cartes égales | 3 cartes empilées | Affichée |
| Recettes | 2 cartes égales | 2 cartes empilées | Omise tant qu'aucune recette n'est publiée |
| Communauté | Panneau, texte à gauche, bouton à droite | Empilé | Omise tant qu'il n'y a pas de vraie destination |
| Pied | Comme la V2 | Comme la V2 | Affiché |

Ordre des besoins dans la grille desktop, ligne par ligne :

1. Créer un site web
2. Créer du contenu
3. Trouver des clients
4. Gérer mon activité
5. Analyser mes données
6. Automatiser une tâche

---

## 7. Corrections aux maquettes et à la spec V2

Ces écarts sont à corriger dans les prochaines maquettes, qu'on garde la V2 complète ou l'allégée.

- [ ] Retirer les halos dorés autour des cartes et de la recherche (desktop)
- [ ] Mot-symbole : reprendre le logo actuel, pas la police à empattements générée
- [ ] Liens « Explorer l'outil » en mode clair : vert forêt `#315b40`, pas or
- [ ] Texte communauté desktop : reprendre celui de la spec (« Échange des idées, partage tes essais et avance avec d'autres créateurs. »)
- [ ] Logos Framer, Notion, Make : monogrammes F, N, M tant que les vrais logos ne viennent pas du catalogue
- [ ] Nom accessible de la marque : « YggNexus, accueil » (la V2 utilisait un tiret)

---

## 8. Produire l'image du héros avec ChatGPT

**État au 23 octobre 2026 : terminé.** Forêt desktop et Lumière desktop validées. Les bandeaux mobiles sont recadrés dans ces deux images. L'image Forêt mobile fournie n'est pas utilisée. La procédure ci-dessous reste comme référence pour une prochaine image.

Deux images à produire : une Forêt (sombre), une Lumière (claire). Chacune en deux cadrages : desktop et mobile.

### Étapes

1. Ouvrir ChatGPT et coller la consigne ci-dessous, avec tes deux images d'Yggdrasil de référence.
2. Générer la version Forêt en format paysage. Recommencer jusqu'à ce que la moitié gauche soit vraiment vide et calme.
3. Dans la même conversation, demander la version Lumière « du même arbre, même cadrage, lumière de jour ». Elle ne sera pas identique au pixel. Ce n'est pas grave : seule la zone calme à gauche doit rester au même endroit.
4. Pour chaque version, générer aussi un cadrage portrait pour le mobile, avec la canopée en haut à droite et le bas de l'image calme.
5. Ouvrir chaque image dans ton logiciel d'image. Effacer toute feuille, branche ou lueur qui dépasse dans la zone du texte.
6. Vérifier qu'il n'y a ni texte, ni rune, ni logo, ni cadre dans l'image. Les effacer s'il y en a.
7. Exporter :
   - desktop : 1600 px de large
   - mobile : 750 px de large
8. Me les envoyer. Je m'occupe de la conversion en AVIF et WebP, du poids et de l'intégration.

### Consigne à coller dans ChatGPT

> Illustration de fond pour l'en-tête d'un site web. Un arbre-monde monumental inspiré d'Yggdrasil, écorce sculptée, feuillage vert, lumière dorée douce venant de l'arrière. Le tronc et la canopée occupent le tiers droit de l'image. Toute la moitié gauche est une zone calme : ciel ou forêt lointaine très sombre, sans feuille ni branche au premier plan, pour y poser du texte. Aucun texte, aucune rune, aucun symbole, aucun cadre, aucun halo lumineux autour d'objets. Style peinture numérique réaliste, retenu, pas de couleurs néon. Format paysage 16:9.

Pour la version Lumière, remplacer la deuxième phrase par : « Lumière de jour, brume claire, ciel pâle peu contrasté, bois brun et feuillage vert naturel. » et la zone calme par « très claire ».

---

## 9. Budget et performance

- Une seule image téléchargée : celle du thème actif et de la largeur d'écran
- Héros mobile : 180 Ko maximum en AVIF, WebP de secours
- Héros desktop : 300 Ko maximum en AVIF, WebP de secours

Poids réels des exports (AVIF qualité 55, WebP qualité 60) :

| Fichier | AVIF | WebP |
|---|---|---|
| `hero-foret-1600` | 82 Ko | 93 Ko |
| `hero-lumiere-1600` | 98 Ko | 116 Ko |
| `hero-foret-750` | 55 Ko | 67 Ko |
| `hero-lumiere-750` | 60 Ko | 76 Ko |

Entre trois et cinq fois sous le budget. Rien à alléger.
- Images servies telles quelles, sans passer par l'optimisation d'images de Vercel (plan gratuit déjà saturé)
- Dimensions réservées pour éviter les déplacements au chargement
- Le site reste lisible et utilisable si l'image ne charge pas

---

## 10. À vérifier à l'intégration

- [ ] Aucun débordement à 320, 375, 768 et 1280 px
- [ ] Lecture à 200 % de zoom
- [ ] Navigation au clavier et au lecteur d'écran, ordre des besoins
- [ ] Rameaux qui suivent les tuiles quand un libellé passe sur deux lignes
- [ ] Thème clair et sombre sans flash au chargement
- [ ] Poids réel des images sous le budget
- [ ] Sections recettes et communauté bien omises si vides

---

## 11. Intégration du 24 octobre 2026 : ce qui est en ligne et les écarts

En production sur www.yggnexus.com depuis le 24 octobre 2026, 00:11.

### Livré

- [x] Palette Forêt et Lumière sur tout le site, plus aucun cyan ni halo
- [x] Héros avec l'image du thème actif (une seule image téléchargée), bandeau sur mobile
- [x] Recherche du héros : label, bouton Trouver, effacement, message si vide, état « Recherche… »
- [x] Six besoins reliés par la ligne de branche SVG, rameaux qui passent à l'or au survol
- [x] Besoins branchés sur les vraies facettes du catalogue (voir tableau)
- [x] Trois outils vedettes : Framer, Canva, n8n
- [x] En-tête et pied refaits, mot-symbole en Syne, thème automatique par défaut
- [x] Ancien fond Yggdrasil retiré (parallaxe, lanterne, runes)
- [x] Recettes et communauté omises, lien « Recettes » masqué
- [x] Textes anglais adaptés

| Besoin | Destination |
|---|---|
| Créer un site web | `/tools?function=build` |
| Créer du contenu | `/tools?function=generate` |
| Trouver des clients | `/tools?audience=marketing` |
| Gérer mon activité | `/tools?audience=business` |
| Analyser mes données | `/tools?function=analyze` |
| Automatiser une tâche | `/tools?function=automate` |

### Écarts volontaires par rapport à la spec

| Spec | Ce qui est en ligne | Raison |
|---|---|---|
| En-tête : Outils, Recettes, À propos | Outils seulement | Les pages Recettes et À propos n'existent pas. Pas de faux lien |
| Menu mobile en dialogue | Pas de menu, lien Outils visible | Un menu pour un seul lien n'apporte rien. À ajouter quand À propos existera |
| Menus Langue et Apparence | Boutons qui basculent | Comportement existant conservé. Noms accessibles conformes (« Apparence : automatique ») |
| Pied : Confidentialité, Nous joindre | Outils, Tags, Recherche | Pages absentes |
| Recherche compacte absente de l'en-tête | Gardée à partir de 1024 px | Les pages intérieures en ont besoin |
| Support opaque derrière le titre | Pas de support | Le titre ne passe jamais devant l'arbre : zone calme mesurée sur desktop, texte sous le bandeau sur mobile |
| Bande mobile de 240 px | 260 px, image 750 × 560 | Rendu vérifié à 375 px : le bouton Trouver reste visible sans défiler sur un iPhone standard |

### Vérifié en production

- [x] Desktop sombre, mobile clair (375 × 812)
- [x] Recherche vide : message affiché, focus conservé
- [x] Recherche « monter un podcast » : 12 résultats
- [x] Tuile « Trouver des clients » : 56 outils filtrés
- [ ] Lecteur d'écran et zoom 200 % : non testés

---

## Journal de versions

| Version | Date | Auteur | Changement |
|---|---|---|---|
| 1.0 | 2026-10-23 | Claude | Création. Version allégée de l'accueil V2 : arbre limité au héros, ligne de branche SVG, grille de besoins, corrections aux maquettes, brief d'image pour ChatGPT avec retouche |
| 1.1 | 2026-10-23 | Claude | Images du héros validées et exportées (AVIF et WebP, poids mesurés). Mobile en bandeau recadré du desktop. `canvas` clair `#ece9e4` et `surface-hover` clair `#f5f2ec`, contrastes recalculés |
| 1.2 | 2026-10-24 | Claude | Intégration en production. Correspondance besoins et facettes, écarts volontaires, vérifications faites |
