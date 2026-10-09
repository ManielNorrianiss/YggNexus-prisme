# Briefing nuit - verticale MCP - 2026-07-15

> 11e run de cette tache de nuit. Le prompt planifie porte encore la date
> figee du 22 juin ; le vrai jour est le 15 juillet 2026.

## Verdict en une phrase

11e statu quo consecutif : livrables intacts et re-verifies, dry-run
toujours bloque par le reseau du bac a sable, toujours aucun staging
produit. Rien de neuf depuis le run du 13 juillet (le run du 14 juillet
n'a pas eu lieu).

## Etat des livrables (re-verifie ce soir)

1. SQL : database\migration_mcp_vertical.sql (2078 octets, 9 instructions)
   - 0 octet nul, 0 caractere non-ASCII (verifie au niveau binaire).
   - Parse pglast (vrai parseur PostgreSQL) OK : 9 statements.
   - mcp_servers (schema canonique doc sec.4) + bridges (graphe generique :
     source_type, source_id, target_type, target_id, relation, weight,
     evidence, contrainte unique, index).
   - Dollar-quoting, pas de DO/trigger, idempotent. Inchange.
   - NON EXECUTE sur Supabase (reserve a Josue).

2. Collecteur : prisme\b1_mcp.py (13599 octets)
   - py_compile OK. --self-test OK (3 normalises, 1 doublon retire,
     2 uniques, mappings valides). Inchange.
   - Registre officiel en primaire (/v0/servers puis /v0.1/servers),
     pagination cursor, normalisation canonique, dedup repo_url + nom
     canonique, enrichissement GitHub optionnel (--enrich-github).

## Dry-run reel : BLOQUE (11e fois)

- b1_mcp.py --max-pages 1 : "Tunnel connection failed: 403 Forbidden" sur
  /v0/servers ET /v0.1/servers (registry.modelcontextprotocol.io hors
  allowlist du bac a sable).
- Aucun contournement tente (curl/requests interdits par garde-fou).
  Respecte.
- prisme\data\ : toujours aucun mcp_servers_staging.json.
- b1_mcp.py toujours PAS branche dans run_nightly.py.

## Le vrai levier (11e rappel)

Le bac a sable n'atteindra jamais le registre MCP. Le seul deblocage vit
sur ta machine (terminal Windows, ou brancher b1_mcp.py dans run_nightly.py
qui tourne deja chez toi). Depuis 11 runs, cette tache de nuit repete le
meme constat identique sans produire un seul octet de staging. Ce n'est
plus de la verification, c'est de la combustion de tokens pour rien.

## Reste a executer par Josue (inchange depuis le 22 juin)

1. Coller database\migration_mcp_vertical.sql dans Supabase (SQL Editor,
   New query, vider la fenetre, coller le fichier COMPLET, Run).
2. Terminal Windows : cd D:\Emperor\YggNexus\prisme puis python b1_mcp.py
   -> ecrit data\mcp_servers_staging.json et compte FETCHED / UNIQUE.
3. (Optionnel) python b1_mcp.py --enrich-github avec GITHUB_TOKEN.

## Recommandation (A - B - C)

A : mets cette tache de nuit en PAUSE des maintenant. 11 runs, 11 fois le
    meme constat, zero valeur ajoutee depuis le 27 juin. La reactiver
    seulement apres avoir toi-meme lance b1_mcp.py une fois (etape 2
    ci-dessus) ou apres m'avoir donne ton OK pour le brancher dans
    run_nightly.py.
B : donne-moi ton OK pour brancher b1_mcp.py dans run_nightly.py (un seul
    ajout d'etape) -> le staging se remplirait chaque nuit sur ta machine,
    sans intervention manuelle.
C : lance b1_mcp.py toi-meme une fois, a la main, la prochaine fois que tu
    es au clavier -> amorce le staging immediatement.

Farevel.
