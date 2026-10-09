# Briefing de nuit - Verticale MCP (2026-07-08)

> Tache planifiee "yggnexus-ingestion-mcp-nuit". Run autonome, Josue absent.
> Principe YggNexus : on est le pont, jamais l'hebergeur.

## Constat d'ouverture

Cinquieme run. Rien de neuf a construire : le SQL et le collecteur existent depuis fin juin et restent conformes. Cette nuit = re-verification qualite, nouvelle tentative de dry-run reseau, inspection de l'etat local.

## Etat des livrables (re-verifie ce soir)

1. SQL : `D:\Emperor\YggNexus\database\migration_mcp_vertical.sql` - 2078 octets, ASCII pur, CRLF, idempotent, dollar-quoting, zero commentaire. Contient bien `mcp_servers` (schema canonique doc sec.4) ET `bridges` (graphe generique source_type/source_id/target_type/target_id/relation/weight/evidence) avec leurs index. Inchange. NON EXECUTE sur Supabase.
2. Collecteur : `D:\Emperor\YggNexus\prisme\b1_mcp.py` - 13599 octets, ASCII pur, py_compile OK, --self-test OK (3 normalises, 1 doublon retire, 2 uniques, mappings valides). Dedup par repo_url + nom canonique en place.

## Dry-run reel : toujours BLOQUE (reseau)

- Bac a sable Linux : `registry.modelcontextprotocol.io/v0/servers` refuse -> Tunnel connection failed: 403 Forbidden (domaine hors allowlist).
- Aucun contournement tente (garde-fou respecte).

Chiffre de reference (doc, juin 2026) : ~9 652 serveurs au registre officiel. Impossible de compter le vrai chiffre depuis le bac a sable.

## Observation cette nuit

- Le batch nocturne local a bien tourne aujourd'hui (log `nightly_2026-07-08.log` present).
- `b1_mcp.py` n'est TOUJOURS PAS branche dans `run_nightly.py` (aucune trace mcp).
- Aucun `data\mcp_servers_staging.json` : la verticale MCP attend encore son premier staging reel.
- Note : lecture de `staging.db` en erreur I/O ce soir (fichier verrouille par le batch local en cours) - sans consequence, simple concurrence d'acces.

## Reste a executer par Josue (inchange)

1. Coller `database\migration_mcp_vertical.sql` dans Supabase (SQL Editor, fichier au complet).
2. Terminal Windows : `cd D:\Emperor\YggNexus\prisme` puis `python b1_mcp.py` -> ecrit `data\mcp_servers_staging.json` et imprime FETCHED / UNIQUE (la machine de Josue a acces au registre, contrairement au bac a sable).
3. (Optionnel) `python b1_mcp.py --enrich-github` avec GITHUB_TOKEN pour stars/licence.

## Recommandation (A - B - C)

A : brancher `b1_mcp.py` dans `run_nightly.py` local (un seul ajout) -> le staging MCP se remplirait tout seul chaque nuit sur la machine de Josue, ce qui debloque sans effort recurrent. C'est la voie la plus alignee.
B : lancer `b1_mcp.py` une fois a la main pour amorcer le premier staging.
C : mettre cette tache de nuit en pause jusqu'au premier staging, puisqu'elle repete le meme constat de blocage reseau depuis 5 runs.

Farevel.
