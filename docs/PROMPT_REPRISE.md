# Prompt de reprise - YggNexus (a coller dans une nouvelle conversation)

Tu reprends le projet YggNexus.com avec moi. Voici le contexte complet ; continue a partir d'ou on est rendu.

## Le projet
YggNexus.com : un actif numerique anglophone, catalogue intelligent reliant des outils IA/SaaS a des automatisations n8n/Make. Objectifs : SEO organique (Google), visibilite dans les AI Overviews, knowledge graph, et a terme un moteur de recommandation semantique. Je suis solo builder. Priorite : simplicite, maintenabilite, faible cout. Le site doit etre largement autonome : un systeme Python local ("le Prisme") collecte/enrichit/publie chaque nuit.

## Stack
Next.js (App Router, SSG/ISR) sur Vercel - PostgreSQL + pgvector sur Supabase - batchs Python locaux (le Prisme) - Beehiiv (infolettre) - n8n/Make (orchestration).

## Ou vivent les fichiers
Tout est dans `D:\Emperor\YggNexus\` :
- `docs/` : ARCHITECTURE_MVP_YggNexus.md (architecture technique complete, source de verite), plus le plan 12 mois, le concept, la grille de scoring, et ce prompt.
- `database/` : setup_complet.sql (schema + donnees d'exemple, a coller dans Supabase), schema.sql, seed.sql.
- `frontend/` : appli Next.js.
- `prisme/` : publish.py (le pont de publication, batch B7), data/tools.json, requirements.txt.
- `scripts/ exports/ assets/` : vides pour l'instant.

## Ce qui est DEJA fait et fonctionne
1. Architecture MVP complete redigee (docs/ARCHITECTURE_MVP_YggNexus.md) : composants, modele de donnees, frontend, SEO, batchs B1-B8, API, MVP, roadmap.
2. Base de donnees creee sur Supabase (projet ref biykachrofudlvdgtbvo) via setup_complet.sql. 11 tables (tools, categories, automations, automation_steps, tool_categories, tool_tags, automation_tools, alternatives, changelog, embeddings, tags). Note : version simplifiee = TEXT + CHECK au lieu d'ENUM, PAS de triggers ni de RLS pour l'instant (reportes volontairement).
3. Frontend Next.js qui tourne en local (npm run dev), branche a Supabase via frontend/.env.local. Page d'accueil = liste des outils. Page /tools/[slug] = fiche complete avec JSON-LD (SoftwareApplication, FAQPage, BreadcrumbList), maillage interne vers les alternatives. sitemap.ts, robots.ts, et /api/revalidate (ISR on-demand) en place.
4. Pont du Prisme (prisme/publish.py) : lit data/tools.json, fait un upsert vers Supabase (tools + tool_categories + changelog), puis declenche la revalidation des pages. Teste : le site est passe de 6 a 8 outils apres un publish. La boucle bout en bout fonctionne en local.

## Ce qui RESTE a faire (options pour la suite)
- Mettre le site en ligne (deploiement Vercel).
- Construire les autres batchs du Prisme : B1 collecte, B2 enrichissement IA + embeddings, B3 dedup, B4 classification, B5 liens/alternatives via embeddings, B6 generation SEO, B8 controle de sante.
- Ajouter les pages frontend manquantes : categories, automations, "Best AI Tools for X", "X vs Y", "Alternatives to X".
- Securiser : reactiver la RLS et passer le pont sur la cle service_role proprement.
- Remplir les embeddings (pgvector) pour la recherche semantique et les recommandations.

## Pieges techniques deja appris (a respecter)
- SQL destine a un copier-coller dans Supabase : texte libre en dollar-quoting $t$...$t$, zero commentaire, ASCII pur, idempotent, AUCUN bloc DO / trigger / point-virgule a l'interieur d'une chaine, et coller le fichier AU COMPLET. (cf. skill ecriture_sql)
- Ecrire les fichiers code (.py, .sql) via le shell, pas l'editeur, sur le dossier monte D:\ (sinon troncature / octets nuls).

## Comment je veux que tu me parles
Francais quebecois, ton humain. Quand j'ai une action a faire : etapes techniques en bullet points D'ABORD, puis une explication en analogie du quotidien ENSUITE. Resultat avant le chemin. Questions en boutons quand c'est pertinent.

Commence par me confirmer que tu as bien le contexte, puis propose-moi les prochaines etapes.
