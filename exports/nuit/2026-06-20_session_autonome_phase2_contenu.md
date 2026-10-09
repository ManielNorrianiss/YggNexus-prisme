# Nuit autonome — Phase 2 FR, etape 2 (CONTENU) — 2026-06-20

Decisions cadrees avec Josue avant de coder :
- Stockage : **colonnes _fr** sur tools/categories.
- Moteur : **sous-agent Claude** (pas Ollama) — gratuit, gere markdown+JSON+marques, zero hallu.
- Perimetre : **complet** (contenu + metas SEO). Marques/URLs/slugs restent EN.
- Recherche : **re-embed FR** (table isolee search_embeddings_fr, match_tools EN intact).
- Frontend : helper localize* qui superpose _fr avec repli EN ; pages EN inchangees.

## Ce qui est FAIT cette nuit (code livre + verifie)
- **Migration colonnes _fr** : DEJA APPLIQUEE dans Supabase (Josue, etape 1). 11 colonnes.
- **Frontend** (tsc --noEmit exit 0) :
  - `lib/localize.ts` (localizeTool/localizeTools/localizeCategory, repli EN).
  - `lib/types.ts` : champs _fr ajoutes a Tool et Category.
  - `lib/queries.ts` : searchTools + searchToolsSemantic prennent `locale` ; EN -> match_tools (inchange), FR -> match_tools_lang.
  - 6 pages cablees : tools/[slug], categories/[slug], best/[category], compare/[pair], tools/[slug]/alternatives, search.
  - **Logo** : `public/yn-logo.svg` + header (layout.tsx) affiche le logo + le nom.
- **DB / pipeline** :
  - `database/migration_search_embeddings_fr.sql` (table search_embeddings_fr + RPC match_tools_lang, idempotent, ASCII).
  - `prisme/dump_en_content.py` (exporte le contenu EN a traduire).
  - `prisme/publish_translations.py` (charge translations_fr.json -> colonnes _fr + revalide /fr).
  - `prisme/embed_search_jina_fr.py` (embeddings FR -> search_embeddings_fr).
  - py_compile OK pour les 3 scripts.

## Pourquoi la TRADUCTION n'est pas encore faite
Le sandbox Cowork est coupe de Supabase (tunnel 403) et `tools.json` sur disque est mort
(tronque). Le contenu EN courant des 110 outils n'est recuperable que depuis ta machine.
=> 1 commande le matin (dump), puis je traduis dans la foulee.

## RUNBOOK matin (ordre)

> Le frontend peut etre deploye AVANT les traductions sans risque : repli EN partout,
> et la recherche FR retombe sur le texte si la migration FR n'est pas encore passee.

1. **(si besoin) index git prisme corrompu** (Windows, dans D:\Emperor\YggNexus) :
   `del .git\index`  puis  `git reset`

2. **Migration recherche FR** — SQL Editor WEB Supabase (PAS le terminal) :
   coller `database/migration_search_embeddings_fr.sql` -> Run.

3. **Dump du contenu EN** (terminal, dossier prisme) :
   `cd prisme && python dump_en_content.py`
   -> cree `data/i18n_source_en.json` (110 outils + 9 categories).

4. **Reviens vers moi** (cette conversation ou une nouvelle dans le space Emperor) et dis
   "i18n_source_en.json est pret". Je lance la traduction par sous-agents et je produis
   `data/translations_fr.json`.

5. **Charger les traductions** :
   `python publish_translations.py --dry-run`  puis  `python publish_translations.py`

6. **Embeddings FR** :
   `python embed_search_jina_fr.py --dry-run`  puis  `python embed_search_jina_fr.py`

7. **Deploy** (les deux repos) :
   - frontend : `cd frontend && git add lib/localize.ts lib/types.ts lib/queries.ts app public && git commit -m "i18n: contenu FR (repli EN) + logo header" && git push`
   - prisme  : `git add database/migration_search_embeddings_fr.sql prisme/dump_en_content.py prisme/publish_translations.py prisme/embed_search_jina_fr.py database/migration_translations_fr.sql && git commit -m "i18n: dump EN, chargeur trad FR, embed FR" && git push`

8. **Verif live** : /fr/tools/<slug> (contenu FR), /fr/categories/<slug> (intro FR),
   recherche FR (requete FR -> resultats via match_tools_lang). Ajouter `?v=1` pour
   contourner le cache si besoin.

## Pieges respectes
- Tous les fichiers sous D:\ ecrits via terminal (heredoc/python), jamais Edit/Write (tronque).
- match_tools (EN) NON modifie ; search_embeddings (EN) NON touche -> zero regression EN.
- SQL idempotent + ASCII pur, a coller dans le SQL Editor WEB.
- Je n'ai pas committe moi-meme (le mount laisse des verrous .lock) -> commandes git ci-dessus.
