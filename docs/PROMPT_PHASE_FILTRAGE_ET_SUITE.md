# Prompt — Phase « Filtrage /tools + suite du projet » YggNexus

> À coller dans une NOUVELLE conversation Cowork branchée sur `D:\Emperor\yggnexus`.
> Repris du travail de la phase Redesign (homepage, logo V2, fond réseau, tokens Tailwind).

---

Tu es lead engineer sur **YggNexus** (www.yggnexus.com), annuaire premium d'outils / agents / automatisations IA. Repo : `D:\Emperor\yggnexus`, frontend dans `frontend/`.

## État réel (déjà fait — NE PAS refaire)

- **Next.js 14.2** App Router, TS 5.5, React 18. NE PAS migrer Next 15.
- **Tailwind intégré** (incrémental, `preflight: false`) + **tokens de la palette verrouillée** dans `tailwind.config.js` (couleurs `bg #0B0F17`, `blue #3B82F6`, `cyan #22D3EE`, `green #22C55E`, + `surface/text/muted/line`, fonts Syne/Inter, radius, ombres premium). Le CSS custom de `app/globals.css` cohabite ; ses variables dark ont été alignées sur la palette → tout le site hérite du look.
- **Primitives shadcn-style** sans dépendance externe : `components/ui/{button,card,input,dialog}.tsx` + `lib/utils.ts` (`cn`).
- **Logo V2** : `public/yn-logo-v2.png` (glyphe) + `public/yn-logo-v2-lockup.png`. Dans header/footer (`app/[locale]/layout.tsx`) et en grand dans le hero de la home.
- **Fond animé** : `components/NodeNetwork.tsx` (réseau de nœuds vivant, liens additifs, impulsions, réactif au curseur, SECRET : maintenir le clic réunit les nœuds → explosion). Remplace l'ancien `StarBackground.tsx` (désormais inutilisé, supprimable).
- **Homepage re-skinnée** (`app/[locale]/page.tsx`) : hero spatial, sections vedettes/derniers/tags, compteur d'outils exact (sans « + »). i18n EN/FR, JSON-LD ItemList, `nav.sr-only` SEO et `revalidate` ISR intacts.
- **ToolCard** re-skinné en Tailwind dark-premium (props/logique inchangées).

## Identité VERROUILLÉE (ne pas rediscuter)

Palette `#0B0F17` / `#3B82F6` / `#22D3EE` / `#22C55E`. Dark premium / spatial UI / « système vivant ». Le logo et le fond réseau matérialisent le thème « arbre = réseau » (Yggdrasil/Nexus).
> Note : `docs/CHARTE_VISUELLE_YGGNEXUS.md §3` décrit encore l'ancien accent OR `#c9a227` + cyan `#00d4ff` — section OBSOLÈTE, à resynchroniser sur la palette verrouillée (pas de redesign).

## Contraintes (impératives)

- Chaque étape : `npm run build` OK + `tsc --noEmit` propre.
- Ne pas casser i18n EN/FR, ni le SEO (JSON-LD, sitemap, robots, ISR), ni les pages existantes.
- Commits petits et fréquents. Index git parfois corrompu → réparer côté Windows : `del .git\index .git\index.lock` puis `git reset`.
- Application des filtres = **paramètres d'URL** (`searchParams`) pour partage + SEO + back/forward.

## CHANTIER A — Refondre le filtrage (priorité)

Problème : le filtrage actuel est trop lourd / mélangeant.
- `/tools` (`components/FilteredToolGrid.tsx`) balance d'un coup : tous les prix + 3 axes de facettes (chaque valeur en chip) + **jusqu'à 60 tags en chips** + select note + select tri. Surcharge.
- La home a un `HomeFilterBar` à 3 menus déroulants (modality/function/audience) + tags + bouton « View tools » → confus.

Décision validée : **Option 1 — recherche d'abord + parcours 1-clic**.

### A1. Home (`app/[locale]/page.tsx` + `components/HomeFilterBar.tsx`)
- **Retirer** le `HomeFilterBar` (les 3 dropdowns + bouton).
- **Remplacer** par une section « Browse by category » : une rangée de **pastilles 1-clic** (les fonctions/catégories principales) → liens vers `/tools?function=<slug>` (param URL). Réutiliser le style pastille déjà en place sur la home (`rounded-full border border-line bg-surface px-3.5 py-1.5 ...`).
- La grosse **recherche reste le point d'entrée principal** du hero.
- Le filtrage fin déménage entièrement sur `/tools`.

### A2. Page `/tools` (`components/FilteredToolGrid.tsx` + `app/[locale]/tools/page.tsx`)
Reco issue d'une étude des concurrents (There's An AI For That, Futurepedia, Toolify, FutureTools) :

Disposition **hybride topbar + sidebar gauche rétractable** :
- **Topbar** (peu d'éléments, toujours visible) : barre de recherche à gauche + **tri en segments** + **compteur de résultats** intégré au titre/à la barre + bouton **Reset** (visible seulement si filtre actif) + rangée de **chips « filtres actifs »** retirables.
- **Sidebar gauche** (desktop) pour les facettes ; sur **mobile**, même contenu dans un **drawer « Filtres (n) »**.

Filtres à GARDER (sidebar, dans cet ordre) :
1. **Pricing** (free / freemium / paid / open_source) — multi-sélection (le filtre n°1 attendu).
2. **Function** — multi-sélection.
3. **Modality** — multi-sélection.
4. **Audience** — multi-sélection (réduire si peu de valeurs).
5. **Note `quality_score`** — un seul seuil simple `≥ 7` / `≥ 8` (pas de slider 0-10 libre).

À NE PAS faire :
- Ne PAS afficher des dizaines de tags en vrac (l'erreur Toolify). Mettre les **tags dans une boîte « Tags » repliée et cherchable** : champ de recherche + les ~10-12 tags les plus fréquents **avec leur compteur** (pattern TAAFT), puis « + Voir plus ». Les tags sont des facettes **secondaires**.
- Pas de filtre date brut → `updated_at` seulement comme **option de tri**.

Tri (topbar, segments, instantané) : **Pertinence** (défaut) · **Mieux notés** (`quality_score`) · **Récents** (`updated_at`). Ne PAS inventer « Populaire/Tendances » tant qu'il n'y a pas de signaux d'usage (PostHog en V2).

Comportements : multi-sélection partout, **application instantanée**, chaque facette = un param URL, **compteur live**, **chips filtres actifs** retirables, **Reset** contextuel, **état vide** explicite (« Aucun outil ne correspond » + bouton reset). Sur chaque carte : logo, nom, 1 ligne desc, badge pricing, note, **max 3 tags**.

Données disponibles par outil : facettes 3 axes (`modality`/`function`/`audience` via `getAllToolFacets`), tags (`getAllToolTags`), `pricing`, `quality_score`, `updated_at`. Voir `lib/queries.ts`, `lib/localize.ts`, `lib/types.ts`.

Garder l'i18n : les libellés passent déjà par `messages/en.json` + `fr.json` (namespace `filters`). Ajouter les clés manquantes (recherche tags, voir plus, filtres actifs, drawer mobile) dans les DEUX fichiers.

## CHANTIER B — Suite du projet (après le filtrage)

Dans l'ordre, en gardant l'esthétique dark premium :
1. **System Overview** — nouvelle route `app/[locale]/overview/page.tsx`, page vitrine « système vivant » (statique/SEO, esthétique des écrans verrouillés en lecture seule). Ajouter au sitemap + lien nav.
2. **Capture email** : table Supabase `subscribers` (+ RLS insert anon), endpoint `app/api/subscribe/route.ts`, composant `EmailCapture` (Resend ou Beehiiv).
3. **PostHog** (pageviews + events : recherche, clic outil, soumission email).
4. **OG images dynamiques** : `app/[locale]/tools/[slug]/opengraph-image.tsx`.
5. **Compléter le FR** (outils + facettes/catégories) + activer la prose `page_seo`.
6. **Affiliation** (`affiliate_url` déjà en colonne) + QA SEO finale (sitemap, JSON-LD, OG, robots, Core Web Vitals).
Détail complet : `docs/RECONCILIATION_ARCHI_CHATGPT_VS_REEL.md`.

## Environnement / méthode (important)

- Le `next build` réel doit tourner **sous Windows** (binaire natif `@next/swc` Windows ; Supabase non joignable hors prod). Le sandbox sert à `tsc --noEmit` (fiable) et à des aperçus HTML autonomes.
- Pour valider visuellement sans la DB : compiler le CSS Tailwind et générer un `preview_*.html` autonome (cf. `preview_home.html` à la racine — aperçu de la home actuelle).
- Surveiller une **troncature occasionnelle des écritures de gros fichiers** : après écriture, vérifier `wc -l` / fin de fichier ; réécrire via shell si besoin.
- Valider chaque page visuellement avant de passer à la suivante ; demander validation entre étapes.

## Premier livrable attendu

Un plan numéroté (fichiers, ordre) pour le **Chantier A** (home Option 1 + refonte `/tools`), puis l'implémentation de la home Option 1 et de la nouvelle `/tools`. `tsc` vert + aperçu HTML à chaque étape. Demander validation avant le Chantier B.
