# Prompt de reprise — YggNexus (mis a jour 2026-06-19)

> Copie-colle ce bloc dans une nouvelle conversation Cowork (space Emperor, branche sur D:\Emperor) pour continuer le projet sans recharger tout le contexte.

---

Reprends le projet YggNexus.com avec moi.

Avant de repondre, lis tes memoires YggNexus : `yggnexus-repos`, `yggnexus-pipeline-execution`, `yggnexus-etat`, et `montage-windows-tronque-fichiers` (dans D:\Emperor\memory). Architecture, etat a jour, pieges — pas besoin que je reexplique.

## Etat actuel (2026-06-19)
- Catalogue : 40 outils publies sur https://www.yggnexus.com. Taxonomie 7 categories.
- B6 phase 2 (prose compare + alternatives) : LIVE.
- Recherche : LIVE. /search + barre dans le header. (1) plein-texte (searchTools ILIKE, wildcard * dans .or). (2) semantique : table search_embeddings vector(1024) + RPC match_tools ; embeddings via Jina v3 (retrieval.passage/query, multilingue) ; script local prisme/embed_search_jina.py ; /search embed la requete via Jina + repli texte. JINA_API_KEY dans prisme/.env ET en var Vercel.
- Deux repos : pipeline = D:\Emperor\YggNexus (GitHub YggNexus-prisme) ; frontend = D:\Emperor\YggNexus\frontend (GitHub YggNexus, Vercel).
- Le pipeline tourne sur ma machine Windows (Supabase/PyPI bloques dans le sandbox Cowork) : je lance, tu guides UNE etape a la fois avec des boutons.

## Pieges confirmes (importants)
- Supabase Edge gte-small (Supabase.ai.Session) plante en WORKER_RESOURCE_LIMIT meme pour 1 embedding -> charger un modele dans l'Edge worker = non viable sur ce plan. On embed via API distante (Jina).
- Deux repos git imbriques : toujours verifier le prompt (...\prisme> vs ...\frontend>) AVANT git add. Source de plusieurs "pathspec did not match" / "Everything up-to-date".
- b1_collecte insere en status=draft ; la run de nuit republie -> verifier l'etat reel avec prisme/etat_sources.py.

## A finir / menage
- Supprimer dans Supabase les Edge Functions semantic-search et reindex-tools (deployees mais inutiles, l'approche Edge a ete abandonnee).
- del les fichiers obsoletes : prisme/embed_search_openai.py, database/migration_search_embeddings_openai.sql.
- Recherche : seuil de similarite optionnel dans match_tools (renvoie toujours match_count resultats). Re-lancer embed_search_jina.py apres ajout d'outils.

## Prochaines etapes (on priorise ensemble)
- Continuer a grossir le catalogue (nouvelles sources, B1->B5 + embed_search_jina.py).
- Resserrer le prompt compare B6 (GTM=Go-To-Market) ; reclasser Runway hors ai-audio.
- Brancher la barre de recherche/UX (autocomplete, seuil), analytics, etc.

## Facon de travailler
Francais quebecois, ton humain, resultat avant le chemin, UNE etape a la fois avec des boutons (jamais de texte libre a remplir), zero jargon inutile. Editer le code sous D:\ via le terminal bash (Edit/Write tronque). Verifier (JSON/tsc/py_compile/pglast) avant les commandes de push. Donner les commandes git a Josue (verrous .lock si commit depuis le sandbox). Fin d'etape : maj memoire + nouveau prompt de reprise.

Confirme que tu as le contexte, puis propose la prochaine etape.

---
