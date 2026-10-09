Ilsen.

Tu travailles sur YggNexus.com (annuaire d'outils IA). Lis d'abord la mémoire
YggNexus ([[yggnexus-etat]], [[yggnexus-repos]], [[yggnexus-pipeline-execution]],
[[yggnexus-ingestion-massive]], [[montage-windows-tronque-fichiers]]) puis ce
prompt. Deux repos sous D:\Emperor\YggNexus : le PIPELINE (racine, repo
ManielNorrianiss/YggNexus-prisme, prisme/ + database/) et le FRONTEND
(D:\Emperor\YggNexus\frontend, repo ManielNorrianiss/YggNexus, Next.js + next-intl
EN/FR, Vercel). Le pipeline tourne sur cette machine Windows (Supabase + Ollama y
sont accessibles ; le bac à sable Cowork ne les atteint PAS — moi j'écris/teste,
toi tu exécutes et tu pousses). État actuel : ~1 000 outils publiés.

== MISSION 1 (prioritaire) : RETIRER LES 9 CATÉGORIES ==

La taxonomie fermée à 9 catégories (ai-writing, automation, ai-images, ai-audio,
data-scraping, productivity, no-code, ai-coding, ai-video) ne convient pas à tous
les outils : 336 tombent en « unclassified ». On la retire. On trouvera un autre
système de classement plus tard.

Contraintes NON NÉGOCIABLES :
- Le catalogue (~1 000 outils) reste INTACT et 100 % navigable (page /tools + recherche).
- Le site ne doit PAS casser (aucune route en 500, sitemap valide, nav cohérente, EN + FR).
- RÉVERSIBLE : ne PAS hard-delete les données catégories sans mon OK explicite.
  Approche recommandée par défaut = NEUTRALISER (masquer l'UI + découpler la nav),
  garder les tables `categories`/`tool_categories` en place. On décidera ensemble
  si on supprime vraiment les données plus tard.

DÉMARCHE (une étape à la fois, montre dry-run/diffs AVANT d'écrire, demande mon OK
avant toute action destructive ou tout push) :

1. CARTOGRAPHIE d'abord. Vérifie dans le code réel (ne te fie pas aveuglément à
   cette liste, confirme chaque fichier) où vivent les 9 catégories :
   - Pipeline : prisme/data/taxonomy.json, prisme/b4_classification.py,
     prisme/sync_categories.py, prisme/export_tools.py (champ categories),
     prisme/publish.py (upsert tool_categories).
   - Supabase : tables `categories` (9 lignes) et `tool_categories` (liens).
   - Frontend : lib/realms.ts (REALM_SLUGS / REALM_MAP), components/RealmGrid.tsx,
     app/[locale]/page.tsx (section « Nine Realms » + badges catégorie des cartes),
     app/[locale]/categories/page.tsx, app/[locale]/categories/[slug]/page.tsx,
     app/[locale]/best/[category]/page.tsx, components/ToolCard.tsx (badge
     category_name), lib/localize.ts (CATEGORY_NAME_FR, localizeCategoryName,
     localizeCategory), lib/queries.ts (getPublishedCategories, getCategoryBySlug,
     getToolsByCategorySlug, getBestToolsByCategory, getToolCategories), le sitemap
     (app .../sitemap.ts), messages/en.json + fr.json (clés nineRealms, libellés),
     la navigation/footer.

2. PROPOSE-MOI un plan de retrait précis (par fichier), avec ce qui devient de la
   nav « sans catégories » : page d'accueil sans la section des 9 royaumes, /tools
   et la recherche comme entrées principales, cartes d'outils sans badge catégorie,
   /categories et /best/<slug> masquées (404 propre ou redirection vers /tools), liens
   de nav/sitemap retirés. Le filtre catégorie de FilteredToolGrid disparaît tout
   seul s'il n'y a plus de catégories.

3. Côté pipeline : on cesse de classifier (b4) et de synchroniser (sync_categories)
   dans les vagues d'ingestion ; les nouveaux outils n'ont plus de catégorie. Ne
   casse pas export_tools/publish (ils doivent continuer à publier les outils sans
   catégorie — c'est déjà le cas pour les unclassified).

4. EXÉCUTION par étapes après mon OK : frontend d'abord (tsc exit 0, je pousse →
   Vercel), puis revalidation EN + FR, puis on tranche pour les données Supabase.

PIÈGES À RESPECTER (cf. mémoire) :
- L'outil Edit TRONQUE la fin des fichiers sous D:\. Écris le code via terminal
  (python heredoc / sed), puis vérifie (wc -c, tsc, py_compile). >16 Ko : 2 morceaux + cat.
- Index git corrompu dans les 2 repos : avant chaque commit, dans le repo concerné,
  `del .git\index` puis `git reset`, puis add/commit/push. C'est MOI (Josué) qui pousse.
- SQL = à coller dans le SQL Editor WEB de Supabase. Idempotent, ASCII. Pas de
  hard-delete sans mon OK.
- Revalidation : après tout changement frontend/contenu, revalider EN ET FR via
  prisme/revalidate_paths.py (SITE_URL doit viser www.yggnexus.com direct).
- Tout est local/gratuit (Ollama, pas de Jina payant). La recherche sémantique
  reste en repli texte.

À la fin de la mission : mets à jour la mémoire YggNexus et donne-moi un prompt de
reprise. Et NE refais pas l'erreur classique : `publier_nouveaux.py` doit tourner
entre b1 et export_tools, sinon les nouveaux outils restent en draft (cf.
[[yggnexus-pipeline-execution]]).

Commence par la CARTOGRAPHIE (lecture seule) et présente-moi le plan de retrait
avant de toucher quoi que ce soit.
