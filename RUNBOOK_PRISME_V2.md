# RUNBOOK — Prisme V2 (chantier vitesse + apprentissage + qualité + modèles libres)

*Livré le 2026-07-01. Tout le code est écrit et testé (149/149 tests verts en bac à sable,
py_compile propre, aucun octet nul). Rien n'a touché le live : Ollama, Supabase et PyPI
sont inaccessibles depuis le bac à sable. Ce runbook liste ce qui reste à faire sur Windows.*

---

## Ce qui a changé (résumé)

| Chantier | Quoi |
|---|---|
| Vitesse | b2 et b1 parallèles (`--workers`), b3/b5 vectorisés numpy, sqlite en WAL + index + insertions groupées, reprises exponentielles dans llm_local |
| Apprentissage | table `run_log`, quarantaine après 3 échecs, re-prompt auto sur JSON invalide, `memoire_prisme.py` qui ajuste les paramètres (±25 % max/nuit) et écrit `logs/lecons.md`, étape `apprendre_nightly.py` en fin de nightly |
| Qualité | `b2b_juge.py` (juge local entre b2 et b3) : re-note les quality_score (fini le 8.7 uniforme), corrige les noms-slugs, renvoie les fiches faibles en ré-enrichissement (1 reprise max) |
| Modèles libres | routage 7b (masse) / 14b (arbitre : juge + raisons b5), repli propre si 14b absent, vraies raisons d'alternatives dans b5 (plus jamais « cosine »), pont pgvector pour la recherche sémantique locale |

Nouveaux fichiers : `b2b_juge.py`, `memoire_prisme.py`, `apprendre_nightly.py`,
`publier_embeddings_pgvector.py`, `database/migration_pgvector_search.sql`,
`docs/RECHERCHE_SEMANTIQUE_LOCALE.md`, 6 modules de tests.

---

## Étape 0 — préparation (une fois)

```bat
cd /d D:\Emperor\YggNexus\prisme

:: 1. tirer le modèle arbitre (14b, ~9 Go). sans lui, tout marche quand même (repli 7b journalisé)
ollama pull qwen2.5:14b-instruct

:: 2. permettre le vrai parallélisme côté serveur Ollama (sinon --workers ne sert qu'à moitié)
::    définir la variable d'environnement système puis redémarrer Ollama :
setx OLLAMA_NUM_PARALLEL 4
:: fermer/relancer Ollama après

:: 3. ménage : supprimer la copie orpheline
del /q D:\Emperor\YggNexus\prisme\database\migration_pgvector_search.sql
rmdir D:\Emperor\YggNexus\prisme\database 2>nul

:: 4. tools.json était tronqué (34 Ko, JSON invalide) : ré-exporter avant toute publication
python export_tools.py
```

## Étape 1 — migration Supabase (une fois)

Coller `D:\Emperor\YggNexus\database\migration_pgvector_search.sql` dans
Supabase SQL Editor → Run. Idempotent : index HNSW cosinus sur `embeddings` +
RPC `search_tools_semantic(query_embedding, match_count)`.

## Étape 2 — valider les tests sur Windows (5 min)

```bat
cd /d D:\Emperor\YggNexus\prisme
python tests\check_no_pytest.py
:: attendu : 149 passes, 0 echecs
```

## Étape 3 — vague d'essai prudente

```bat
:: enrichissement parallèle (4 travailleurs par défaut, lus depuis data\parametres_appris.json ensuite)
python b2_enrichissement.py --limit 20 --workers 4

:: juge qualité (utilise le 14b ; repli 7b automatique si absent)
python b2b_juge.py --limit 20

:: reprise des fiches renvoyées par le juge
python b2_enrichissement.py --limit 20

:: suite habituelle
python b3_dedup.py
python b4_classification.py
python b5_liens.py --workers 4        :: vraies raisons LLM ; --sans-llm pour gabarits seulement
python publier_nouveaux.py
python export_tools.py
python publish.py
python publish_embeddings.py
python publier_embeddings_pgvector.py --dry-run   :: vérifier, puis relancer sans --dry-run

:: bilan d'apprentissage du run
python apprendre_nightly.py
type logs\lecons.md
```

## Étape 4 — nightly

`run_nightly.py` intègre déjà les nouvelles étapes : `juge_qualite` après
`enrichissement`, `apprentissage` en toute fin (non critiques). Rien à changer
dans la tâche planifiée.

---

## Comment le Prisme apprend maintenant

1. chaque script journalise ses événements (erreurs, timeouts, pages mortes,
   JSON invalides, quarantaines, replis de modèle) dans la table `run_log` ;
2. quand une sortie LLM est invalide, b2 remontre son erreur au modèle et lui
   redemande UNE fois ; à 3 échecs cumulés, le slug part en quarantaine
   (`--inclure-quarantaine` pour le repêcher) ;
3. `apprendre_nightly.py` lit le journal, ajuste prudemment
   `data\parametres_appris.json` (workers, timeouts — jamais plus de ±25 % par
   nuit) et écrit ses leçons datées dans `logs\lecons.md` ;
4. b1/b2 relisent ces paramètres au démarrage suivant : la boucle est fermée.
   Si plus de 30 % des fiches sont refusées par le juge, la leçon recommande de
   passer b2 au 14b (jamais appliqué automatiquement — ta décision).

## Décision qui t'appartient (recherche sémantique du site)

Le pont pgvector est prêt côté données. Pour que la barre de recherche du site
redevienne sémantique sans service payant, il reste à choisir comment calculer
l'embedding de la requête côté Vercel : options détaillées dans
`docs\RECHERCHE_SEMANTIQUE_LOCALE.md`. Aucun changement frontend n'a été fait.

## Pièges connus (rappel)

- commit : `del .git\index` + `git reset` avant chaque commit (index corrompu déjà vu) ;
- b1 `--workers 8` peut faire bannir par certains sites : réduire si 429/403 en série ;
- WAL crée `staging.db-wal`/`-shm` à côté de la base : normal, ne pas supprimer pendant un run ;
- scripts B0 + runbook ingestion massive toujours pas committés (dette d'avant ce chantier).
