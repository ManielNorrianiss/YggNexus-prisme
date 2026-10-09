# Briefing nuit - verticale MCP - 2026-07-18

> 14e run. Le prompt planifie porte toujours la date figee du 22 juin ;
> le vrai jour est le 18 juillet 2026.

## Verdict en une phrase

14e statu quo : les deux livrables sont intacts et re-verifies, le dry-run
reste bloque par le reseau du bac a sable, aucun staging produit.

## Etat des livrables (re-verifie ce soir)

1. SQL : database\migration_mcp_vertical.sql (2078 octets)
   - 0 octet nul, 0 caractere non-ASCII. pglast parse OK.
   - Idempotent, dollar-quoting, pas de DO/trigger. mcp_servers + bridges
     (schema canonique du doc, table pont generique). Inchange.
   - NON EXECUTE sur Supabase (reserve a Josue).
2. Collecteur : prisme\b1_mcp.py (13599 octets)
   - py_compile OK. --self-test OK (3 normalises, 1 doublon retire,
     2 uniques, mappings valides). 100% ASCII. Inchange.
   - Toujours PAS branche dans run_nightly.py (grep = 0).

## Dry-run reel : BLOQUE (14e fois)

- Tunnel connection failed: 403 Forbidden sur /v0/servers et /v0.1/servers.
  registry.modelcontextprotocol.io reste hors allowlist du bac a sable.
- web_fetch essaye en secours : refuse (URL hors provenance). Pas de
  contournement force (garde-fou respecte).
- Serveurs MCP recuperes : 0. prisme\data\ : aucun staging.

## Constat net

Rien de neuf a creer : SQL et collecteur existent et passent leurs tests
depuis le 27 juin. Cette tache re-confirme la meme chose chaque nuit et
brule des tokens pour rien. Le deblocage est physiquement impossible d'ici :
le registre n'est joignable que depuis ta machine Windows.

## Reste a executer par Josue (inchange)

1. Coller database\migration_mcp_vertical.sql dans Supabase (SQL Editor,
   New query, vider la fenetre, coller le fichier COMPLET, Run).
2. Terminal Windows : cd D:\Emperor\YggNexus\prisme puis python b1_mcp.py
   -> ecrit data\mcp_servers_staging.json et compte FETCHED / UNIQUE.
3. (Optionnel) python b1_mcp.py --enrich-github avec GITHUB_TOKEN.

## Recommandation (A - B - C)

A : mets cette tache en PAUSE (Parametres > Taches planifiees) jusqu'a ce
    que tu aies lance b1_mcp.py une fois toi-meme. 14 runs identiques, c'est
    assez.
B : donne-moi l'OK pour brancher b1_mcp.py dans run_nightly.py -> le staging
    se remplirait chaque nuit sur ta machine (reseau ok la-bas), sans toi.
C : lance b1_mcp.py toi-meme une fois au clavier -> amorce le staging, puis
    on enchaine sur B2/B3/graphe pont.

Farevel.
