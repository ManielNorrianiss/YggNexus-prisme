# Prompt de reprise — YggNexus.com

> Copie-colle tout ce qui suit dans une nouvelle conversation pour continuer le projet.

---

Tu reprends le projet YggNexus.com avec moi. Voici le contexte complet et a jour ; continue a partir d'ou on est rendu.

## Le projet
YggNexus.com : un actif numerique anglophone, catalogue intelligent reliant des outils IA/SaaS a des automatisations n8n/Make. Objectifs : SEO organique, visibilite dans les AI Overviews, knowledge graph, et a terme un moteur de recommandation semantique. Je suis solo builder. Priorite : simplicite, maintenabilite, faible cout. Le site est largement autonome : un systeme Python local (« le Prisme ») publie.

## Stack
Next.js (App Router, SSG/ISR) sur Vercel — PostgreSQL + pgvector sur Supabase — batchs Python locaux — Beehiiv — n8n/Make. Modeles IA en LOCAL via Ollama : qwen2.5:7b-instruct (texte) + nomic-embed-text (embeddings, 768 dimensions).

## Ou vivent les fichiers
Tout est dans `D:\Emperor\YggNexus\` : docs, database, frontend, prisme, scripts, exports, assets.

## CE QUI FONCTIONNE DEJA (a jour)
1. Architecture MVP complete : `docs/ARCHITECTURE_MVP_YggNexus.md`
2. Base de donnees sur Supabase (projet `biykachrofudlvdgtbvo`), 11 tables, version simplifiee TEXT+CHECK. Table embeddings migree en `vector(768)`.
3. SECURITE appliquee : `database/securite_rls.sql` execute -> RLS actif sur les 11 tables, lecture publique limitee aux contenus status=published, tables changelog/embeddings invisibles au public, aucune ecriture anon. Le Prisme ecrit avec la cle service_role (passe par-dessus le RLS).
4. Frontend Next.js DEPLOYE sur Vercel depuis un repo GitHub dedie `ManielNorrianiss/YggNexus` (on ne pousse que le dossier frontend/). Page d'accueil + fiches /tools/[slug] avec JSON-LD, sitemap, robots, /api/revalidate.
5. Le Prisme — chaine B1 -> B2 batie et roulee de bout en bout :
   - `prisme/llm_local.py` : appels Ollama (qwen JSON strict + embeddings nomic)
   - `prisme/staging.py` : staging SQLite local (raw_tools, enriched_tools, tool_embeddings)
   - `prisme/b1_collecte.py` : lit data/sources.json, fetch metadata des sites, upsert raw avec source_hash
   - `prisme/b2_enrichissement.py` : qwen redige (desc, pros/cons, FAQ, SEO, quality_score) + embeddings
   - `prisme/export_tools.py` : staging -> data/tools.json (--merge garde l'existant)
   - `prisme/publish.py` : upsert vers Supabase (etendu avec seo_title, seo_description, pros_jsonb, cons_jsonb, faq_jsonb)
   - `prisme/publish_embeddings.py` : pousse les vecteurs vers la table embeddings
   - Sequence : ollama pull nomic-embed-text -> migration SQL -> b1 -> b2 -> export -> publish -> publish_embeddings

## CE QUI RESTE
- Brancher le domaine yggnexus.com dans Vercel (Settings -> Domains) + config DNS chez le registraire
- Bloc C : mettre `SITE_URL=https://yggnexus.com` dans `prisme/.env` une fois le domaine actif (pour que la revalidation vise la prod)
- Autres batchs du Prisme : B3 dedup, B4 classification, B5 liens/alternatives, B6 generation SEO, B8 sante
- Pages frontend manquantes : categories, automatisations, « Best X », « X vs Y », « Alternatives to X »
- Automatiser la chaine la nuit (la brancher sur le batch de nuit existant)
- Remplir/exploiter les embeddings pour la recherche semantique

## PIEGES DEJA APPRIS (importants)
- SQL a coller dans Supabase : dollar-quoting `$t$...$t$` pour le texte libre, zero commentaire, ASCII pur, idempotent, aucun bloc DO/trigger/point-virgule dans une chaine, coller le fichier au complet.
- Ecrire les fichiers code (.py, .sql) via le SHELL, pas l'editeur (corruption multioctets sur D:). Code 100% ASCII (pas d'accents dans le code).
- supabase-py : eviter `.maybe_single().execute()` (retourne None sur 0 ligne) -> utiliser `.limit(1).execute()` et lire `res.data` comme une liste.
- Colonne quality_score = NUMERIC(4,2), max 99.99 -> plafonner les scores (l'export le fait deja).
- Python 3.14 sur ma machine (recent) ; si un paquet bloque, signaler.
- staging.db : si « disk I/O error » sur Windows, definir `set STAGING_DB_PATH=C:\staging_yggnexus.db`.
- Pour deployer sur Vercel : les variables NEXT_PUBLIC_* sont « cuites » au build -> apres ajout/modif, il faut Redeploy.

## COMMENT ME PARLER
Francais quebecois, ton humain. Quand j'ai une action a faire : etapes techniques en bullets D'ABORD, analogie du quotidien ENSUITE. Resultat avant le chemin. Questions en boutons. Quand tu m'expliques quoi faire, fais-le etape par etape, tres clair, et donne-moi des cases a cocher pour suivre ma progression.

Confirme-moi que tu as le contexte, puis propose-moi les prochaines etapes.
