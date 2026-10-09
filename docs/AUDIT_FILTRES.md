# Audit des filtres — YggNexus (2026-08-16)

Constat de départ de Josué : « les vues de filtres ne sont pas user friendly ». Audit ciblé sur les composants réels du frontend, pas d'exploration large.

## Fichiers audités

- `frontend/components/FilterBar.tsx` — primitives `FilterChip` (chip + popover desktop / bottom-sheet mobile) et `FilterOptionButton`.
- `frontend/components/FilteredToolGrid.tsx` — le vrai moteur de filtrage, utilisé sur `/tools` et `/search`. Facettes (fonction, public), catégories, tags, prix, note, tri, recherche texte, compteurs dynamiques par option, sync URL, pagination incrémentale.
- `frontend/components/HomeFilterBar.tsx` — barre de filtres rapide sur la page d'accueil, système à part.
- `frontend/app/[locale]/tools/page.tsx` — lit les `searchParams` serveur et les passe en `initial*` à `FilteredToolGrid`.
- `frontend/app/[locale]/categories/page.tsx` et `tags/page.tsx` — routes de navigation par catégorie/tag (indépendantes des filtres à facettes).
- `frontend/messages/fr.json`, section `filters` — libellés existants.

## Ce qui existe déjà (et fonctionne bien)

Le système est plus avancé qu'un simple constat négatif ne le laisse penser :
- Compteurs dynamiques par option, recalculés en excluant l'axe qu'on compte (ex. si je regarde le prix, le compteur ignore le filtre prix actif).
- Chips de filtres actifs avec bouton `x` par chip, bouton « Tout effacer » global.
- Sync URL déjà en place (`router.replace` sur chaque changement d'état, lu côté serveur via `searchParams` dans `tools/page.tsx`).
- Recherche instantanée à l'intérieur de la liste de tags (`tagQuery`).
- Compteur global de résultats (« N affichés »).

## Ce qui cloche concrètement

1. **Pas de tiroir mobile unifié.** Chaque `FilterChip` ouvre son propre bottom-sheet indépendant (voir `FilterBar.tsx` lignes 88-124). Sur mobile, il n'y a aucun bouton « Filtres » central qui ouvre TOUS les filtres d'un coup avec un compteur global de filtres actifs — l'utilisateur doit ouvrir/fermer chip par chip, un tiroir à la fois, pour explorer plusieurs axes. C'est le problème le plus visible en usage mobile réel.

2. **Recherche instantanée seulement sur les tags.** `FilteredToolGrid.tsx` a `tagQuery` pour chercher dans les tags (ligne 93, 379-383) mais rien d'équivalent pour la liste de catégories (`visibleCategories`, potentiellement longue) ni pour les facettes par axe. Dès qu'une liste de catégories dépasse une quinzaine d'entrées, il faut scroller à l'oeil dans le popover.

3. **Facettes empilées dans des popovers, pas visibles d'un coup.** Chaque groupe de filtre (prix, catégorie, fonction, public, note, tags, tri) est un chip qu'il faut cliquer pour révéler les options (`FilterChip`, état `open`). Sur desktop, ça reste plus rapide qu'un vrai menu déroulant classique parce que les chips eux-mêmes montrent l'état actif et le compteur de sélection, mais aucune option individuelle n'est visible sans un clic préalable — contrairement à une colonne de facettes toujours ouverte.

4. **`HomeFilterBar.tsx` est un système entièrement différent et plus pauvre.** Sur la page d'accueil, les filtres sont des `<select>` HTML natifs empilés (lignes 99-150) : aucun chip, aucun compteur par option, aucune recherche instantanée, aucun affichage de sélection multiple (chaque `<select>` ne retient qu'une seule valeur). Incohérence d'expérience entre la page d'accueil et `/tools`.

5. **État vide générique.** Le bloc « aucun résultat » (`FilteredToolGrid.tsx` lignes 650-660) propose un bouton `reset` qui efface TOUS les filtres plutôt que de suggérer de retirer seulement le dernier filtre ajouté — ça punit l'utilisateur qui avait 4 filtres valides et n'en a ajouté qu'un seul de trop.

6. **Format des compteurs incohérent.** Le format demandé « Gratuit (142) » n'est pas respecté : le code produit `"Gratuit " + count` sans parenthèses (`FilteredToolGrid.tsx` ligne 488 et suivantes) — petit détail mais visible partout dans les popovers.

## Ce que propose la maquette

Fichier : `YggNexus/preview_filtres_v2.html` (autonome, HTML+CSS+JS en dur, 30 outils fictifs, aucune dépendance externe).

- Colonne de facettes toujours visible sur desktop (prix, catégorie, fonction, public, note, tags) — plus besoin de cliquer pour voir les options existantes.
- Chips de filtres actifs en haut avec `x` individuel + bouton « Tout effacer », uniquement si des filtres sont actifs.
- Compteur de résultats en direct + compteur par option au format `Option (12)`, y compris pour les options à 0 résultat (grisées, non cliquables) une fois qu'un autre filtre les exclut.
- Recherche instantanée sur catégories ET tags (pas seulement les tags).
- État reflété dans l'URL (`?q=&price=&category=&fn=&aud=&min=&tags=&sort=`), relu au chargement — un lien partagé restitue exactement la même vue.
- Version mobile : un seul bouton « Filtres » avec pastille de compte, qui ouvre un tiroir unique contenant tous les groupes de filtres, plus un bouton « Voir les résultats » fixe en bas. Media query réelle à 860px (`aside.facets` disparaît, `.mobile-filter-btn` apparaît).
- État vide qui propose « Retirer le dernier filtre » en plus de « Tout effacer », au lieu d'une page morte.

## Fichiers frontend à modifier pour l'intégration (avec effort estimé)

| Fichier | Changement requis | Effort |
|---|---|---|
| `components/FilterBar.tsx` | Remplacer le modèle "chip ouvre un popover isolé" par une primitive qui peut être rendue soit en colonne fixe (desktop) soit dans un tiroir unique partagé (mobile). Probablement une réécriture du composant plutôt qu'une extension. | Élevé (0,5–1 jour) |
| `components/FilteredToolGrid.tsx` | Ajouter : état de recherche par section (catégories en plus des tags), layout à deux colonnes desktop (facettes fixes + grille), état "tiroir mobile ouvert" avec bouton flottant et compteur, logique "retirer le dernier filtre" dans l'état vide, format `Option (N)` uniforme. La logique de comptage/URL existante est réutilisable telle quelle. | Élevé (1 jour) |
| `components/HomeFilterBar.tsx` | Aligner sur le même modèle de chips/compteurs que `/tools`, ou clarifier que la page d'accueil reste volontairement un raccourci simplifié (décision produit à trancher avec Josué avant de coder). | Moyen (0,5 jour) si alignement complet, sinon rien à faire |
| `messages/fr.json` / `messages/en.json`, section `filters` | Ajouter les nouvelles clés : recherche par catégorie, bouton "Filtres" mobile, "Retirer le dernier filtre", `activeFilters` déjà présent mais inutilisé — à vérifier. | Faible (15-30 min) |
| `app/[locale]/tools/page.tsx`, `app/[locale]/search/page.tsx` | Aucun changement de fond attendu — la sync URL et les `initial*` props restent compatibles avec la nouvelle UI si l'API de `FilteredToolGrid` (props) ne change pas. | Faible, à vérifier seulement |
| Styles Tailwind (`tailwind.config.js` si des couleurs/tokens manquent) | Vérifier que les tokens `surface`, `line`, `blue`, `bg` utilisés dans la maquette existent déjà dans le thème (ils sont repris tels quels de `FilterBar.tsx`/`FilteredToolGrid.tsx` actuels, donc a priori oui). | Nul à faible |

Total estimé pour l'intégration réelle (hors QA/tests) : environ 2 à 2,5 jours-personne, la majorité du travail étant la réécriture de `FilterBar.tsx` et `FilteredToolGrid.tsx` pour passer du modèle "chip + popover individuel" au modèle "colonne fixe desktop / tiroir unique mobile" démontré dans la maquette.

## Fichiers produits par cet audit

- `YggNexus/preview_filtres_v2.html`
- `YggNexus/docs/AUDIT_FILTRES.md` (ce fichier)

Aucun fichier existant du frontend n'a été modifié.
