Mission : phase 3 de YggNexus.com — le DESIGN du site et l'ARCHITECTURE DE
L'INFORMATION. Le catalogue (110 outils, 9 categories) est complet, bilingue
(EN a /, FR a /fr) et live ; on passe de "fonctionnel" a "beau et bien organise".
Lis d'abord dans D:\Emperor\memory : project_yggnexus_etat, project_yggnexus_repos,
project_yggnexus_pipeline_execution, feedback_montage_windows_tronque_fichiers.

=== ETAT ACTUEL (tout live, 2026-06-20) ===
- Catalogue : 110 outils publies, 9 categories (ai-writing, automation, ai-images,
  ai-audio, data-scraping, productivity, no-code, ai-coding, ai-video).
- Recherche texte + semantique (Jina v3, 1024d), bilingue (match_tools EN, match_tools_lang FR).
- i18n complet : habillage + CONTENU traduits (fiches, pros/cons/faq, intros de categories,
  metas SEO). Bouton EN/FR + theme clair/sombre/auto dans le header. Logo dans le header.
- Pages : accueil (hero recherche + chips + LISTE A PUCES de 50 outils), /tools/[slug],
  /categories (+[slug]), /best/[cat], /compare/[pair], /tools/[slug]/alternatives, /search.

=== ETAT DU DESIGN (le point de depart honnete) ===
- ACQUIS : systeme de variables CSS dans app/globals.css (--bg/--fg/--muted/--accent/
  --border/--card/--hover/--shadow), 3 themes (clair, sombre, auto) calibres WCAG, hero
  d'accueil avec grosse barre de recherche + chips, autocomplete, classes .tldr/.badge/
  .chip/.searchbox. Conteneur etroit max-width 800px (layout.tsx).
- MANQUE : pas de composant carte d'outil (les listes sont des <ul> nom + courte desc),
  pas de grille, pas de logos d'outils affiches, pas de badges prix/categorie/note dans les
  listes, decouverte par categories faible (pas de grille de categories en page d'accueil),
  pas de filtres ni de tri, hierarchie visuelle minimale (h1/h2/listes/tableaux bruts).
- CSS = vanilla (variables + classes), PAS de Tailwind. Next.js 14 App Router.

=== ARCHITECTURE (rappel) ===
- Deux repos sous D:\Emperor\YggNexus :
  - Frontend Next.js : D:\Emperor\YggNexus\frontend, repo github.com/ManielNorrianiss/YggNexus,
    deploie sur Vercel a chaque push. Lit Supabase, 100% data-driven. Routes sous app/[locale]/.
  - Pipeline (prisme) : racine D:\Emperor\YggNexus, repo YggNexus-prisme. Batches Python,
    SQLite staging.db, secrets dans prisme/.env.
- Supabase (Postgres) = source de verite du contenu. Tables : tools, categories,
  tool_categories, alternatives, page_seo, search_embeddings(+_fr). Le champ logo_url existe
  dans tools mais est souvent vide.
- Le pipeline tourne sur la machine Windows de Josue (Supabase et PyPI bloques dans le
  sandbox). Emperor edite le code et guide UNE etape a la fois avec boutons ; Josue lance.

=== PIEGES CONNUS (importants) ===
- Montage Windows : editer le code sous D:\ via Edit/Write TRONQUE les fichiers. Toujours
  passer par le terminal bash (python3 heredoc, sed). Lecture OK avec Read. Verifier apres
  ecriture (tsc --noEmit pour le frontend ; node_modules + typescript sont presents).
- Le SQL Supabase se colle dans le SQL Editor du SITE WEB, jamais dans le terminal noir.
  SQL idempotent, ASCII pur, dollar-quoting $t$.
- Le sandbox NE joint PAS Supabase (tunnel 403) : toute lecture/ecriture de donnees passe par
  un script lance sur Windows. Le site live (Vercel) est joignable par fetch pour verifier.
- Le frontend est data-driven : changer le design = repo frontend uniquement ; les pages
  EN et FR partagent les memes composants (les libelles passent par next-intl messages/).
- Ne pas casser l'i18n : tout nouveau libelle d'interface va dans messages/en.json + fr.json.

=== A CADRER AVEC MOI AVANT DE CODER (pose-moi les questions par boutons) ===
1. Direction visuelle : epure facon "produit tech" (style Linear/Vercel), chaleureux/editorial,
   ou dense facon annuaire pro (style G2/Product Hunt) ? Donne-moi une reco + une maquette
   d'apercu si possible.
2. Colonne vertebrale de la decouverte : recherche-first (actuel), navigation par categories
   (grille de cartes), ou filtres+tri (prix, categorie, note) au-dessus d'une grille ?
3. Composant carte d'outil (ToolCard) reutilisable partout (accueil, categorie, best,
   recherche, alternatives) : quoi afficher ? (logo, nom, courte desc, badge categorie,
   badge prix, note /10, lien). Le creer en premier comme brique de base ?
4. Logos d'outils : logo_url est souvent vide. On les collecte via le pipeline (favicon/
   Clearbit) ou on part d'un fallback elegant (monogramme/initiale colore) ?
5. Page d'accueil : nouvelle structure (hero recherche -> categories en grille -> outils
   vedettes/recents -> sections par categorie) vs la liste plate actuelle ?
6. Outillage CSS : on reste en CSS vanilla (variables + classes, zero dependance) ou on
   introduit Tailwind / CSS Modules ? (impact sur la vitesse de design et la maintenance)
7. Largeur/layout : garder le conteneur etroit 800px (confort de lecture) ou elargir avec
   une vraie grille responsive pour la decouverte ?
8. Portee de la 1re iteration : refonte du design system (tokens, typo, espacements, etats)
   + ToolCard + grille categories d'abord, puis le reste page par page ? Ou autre ordre ?

=== FACON DE TRAVAILLER ===
Francais quebecois, ton humain, resultat avant le chemin, UNE etape a la fois avec boutons.
Maquettes/apercus visuels bienvenus pour trancher la direction. Taches lourdes deleguees a un
sous-agent sonnet. Verifier en live par fetch apres chaque deploiement. Frontend : tsc --noEmit
avant de pousser. Fin d'etape = mise a jour memoire + prompt de reprise.
