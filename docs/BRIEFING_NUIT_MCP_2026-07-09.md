# Briefing de nuit - Verticale MCP (2026-07-09)

> Tache planifiee "yggnexus-ingestion-mcp-nuit". Run autonome, Josue absent.
> Principe YggNexus : on est le pont, jamais l'hebergeur.

## Constat d'ouverture

Sixieme run. Toujours rien de neuf a construire : le SQL et le collecteur existent
depuis fin juin et restent conformes au doc EXTENSION (sec.4 et sec.9). Cette nuit =
re-verification qualite complete, nouvelle tentative de dry-run reseau, inspection
de l'etat local.

## Etat des livrables (re-verifie ce soir)

1. SQL : database\migration_mcp_vertical.sql (2078 octets)
   - ASCII pur (verifie), dollar-quoting $t$...$t$, zero commentaire, idempotent,
     aucun DO/trigger.
   - Contient bien mcp_servers (schema canonique doc sec.4 : slug, name canonique,
     description, author, repo_url, registry_source, package_type/transport/hosting
     avec CHECK, capabilities[], stars, weekly_downloads, quality_score, embedding
     vector(768)) ET bridges (graphe generique : source_type, source_id, target_type,
     target_id, relation, weight, evidence + contrainte unique + 3 index).
   - Inchange. NON EXECUTE sur Supabase (reserve a Josue).

2. Collecteur : prisme\b1_mcp.py (13599 octets)
   - ASCII pur (verifie), py_compile OK, --self-test OK
     (3 normalises, 1 doublon retire, 2 uniques, mappings valides).
   - Pagination par cursor (limit 100), normalisation vers le modele canonique,
     dedup par repo_url + nom canonique, enrichissement GitHub optionnel
     (topic:mcp-server) en secondaire.

## Dry-run reel : toujours BLOQUE (reseau)

- Bac a sable Linux : registry.modelcontextprotocol.io/v0/servers refuse
  -> "Tunnel connection failed: 403 Forbidden" (domaine hors allowlist).
- Outil WebFetch : refuse aussi ("URL not in provenance set").
- Aucun contournement tente (curl/wget/requests interdits par garde-fou). Respecte.

Chiffre de reference (doc, juin 2026) : ~9 652 serveurs au registre officiel.
Impossible de compter le vrai chiffre depuis le bac a sable ce soir.

## Observations cette nuit

- Le batch nocturne local a bien tourne aujourd'hui (log nightly_2026-07-09.log present).
- b1_mcp.py n'est TOUJOURS PAS branche dans run_nightly.py (aucune trace "mcp").
- Aucun data\mcp_servers_staging.json : la verticale MCP attend encore son premier
  staging reel.

## Reste a executer par Josue (inchange)

1. Coller database\migration_mcp_vertical.sql dans Supabase (SQL Editor, fichier complet).
2. Terminal Windows : cd D:\Emperor\YggNexus\prisme puis "python b1_mcp.py"
   -> ecrit data\mcp_servers_staging.json et imprime FETCHED / UNIQUE
   (la machine de Josue a acces au registre, contrairement au bac a sable).
3. (Optionnel) "python b1_mcp.py --enrich-github" avec GITHUB_TOKEN pour stars/licence.

## Recommandation (A - B - C)

A : brancher b1_mcp.py dans run_nightly.py (un seul ajout) -> le staging MCP se
    remplirait tout seul chaque nuit sur la machine de Josue, ce qui debloque sans
    effort recurrent. La voie la plus alignee. Je peux preparer le patch, Josue valide.
B : lancer b1_mcp.py une fois a la main pour amorcer le premier staging.
C : mettre cette tache de nuit en pause jusqu'au premier staging - elle repete le
    meme constat de blocage reseau depuis 6 runs et n'apporte plus de valeur neuve
    tant que le pont local n'est pas branche.

Farevel.
