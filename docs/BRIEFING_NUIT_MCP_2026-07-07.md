# Briefing de nuit - Verticale MCP (2026-07-07)

> Tache planifiee "yggnexus-ingestion-mcp-nuit". Run autonome, Josue absent.
> Principe YggNexus : on est le pont, jamais l'hebergeur.

## Constat d'ouverture

Rien de neuf a construire : SQL et collecteur existent et restent conformes. Cette nuit = re-verification qualite + nouvelle tentative de dry-run + inspection du staging local (nouveaute : le batch nocturne local tourne chaque nuit, verifie jusqu'au 7 juillet).

## Etat des livrables (re-verifie ce soir)

1. SQL : `D:\Emperor\YggNexus\database\migration_mcp_vertical.sql` - 2078 octets, ASCII pur, idempotent, dollar-quoting, zero commentaire. Inchange. NON EXECUTE sur Supabase.
2. Collecteur : `D:\Emperor\YggNexus\prisme\b1_mcp.py` - 13599 octets, ASCII pur, py_compile OK, --self-test OK (3 normalises, 1 doublon retire, 2 uniques, mappings valides).

## Dry-run reel : toujours BLOQUE (reseau)

- Bac a sable Linux : aucune connexion vers registry.modelcontextprotocol.io (domaine hors allowlist).
- web_fetch : refuse (provenance).

Garde-fou respecte : arret sans contournement. Chiffre de reference (doc, juin 2026) : ~9 652 serveurs au registre officiel.

## Observation nouvelle cette nuit

Le batch nocturne local (run_nightly, pipeline tools) tourne bien chaque nuit sur la machine de Josue (logs 07-01 a 07-07, tools.json regenere le 7 a 03h22). Mais `b1_mcp.py` n'y est PAS branche : aucune trace mcp dans le log de nuit, aucune table mcp dans staging.db, aucun `data\mcp_servers_staging.json`. La verticale MCP attend donc toujours son premier staging.

## Reste a executer par Josue (inchange + 1 option)

1. Coller `database\migration_mcp_vertical.sql` dans Supabase (SQL Editor, fichier au complet).
2. Terminal Windows : `cd D:\Emperor\YggNexus\prisme` puis `python b1_mcp.py` -> ecrit `data\mcp_servers_staging.json` et imprime FETCHED / UNIQUE.
3. (Optionnel) `python b1_mcp.py --enrich-github` avec GITHUB_TOKEN.
4. Option structurante : ajouter une etape b1_mcp au batch_nuit local (la machine de Josue a acces au registre, contrairement au bac a sable) - un seul ajout dans run_nightly.py et le staging MCP se remplirait tout seul chaque nuit.

## Suggestion

Quatrieme run avec le meme blocage reseau. Recommandation A : brancher b1_mcp.py dans run_nightly.py local (option 4 ci-dessus), c'est la voie qui debloque sans effort recurrent. B : lancer une fois a la main. C : mettre cette tache en pause jusqu'au premier staging.

Farevel.
