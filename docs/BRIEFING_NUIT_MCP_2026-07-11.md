# Briefing de nuit - Verticale MCP (2026-07-11)

> Tache planifiee "yggnexus-ingestion-mcp-nuit". Run autonome, Josue absent.
> Principe YggNexus : on est le pont, jamais l'hebergeur.

## Constat d'ouverture

Huitieme run. Meme verdict que les sept precedents : le SQL et le collecteur
existent depuis fin juin et restent conformes au doc EXTENSION (sec.4 modele de
donnees, sec.9 sequence "MCP en premier"). Je n'ai PAS recree les fichiers, pour
ne pas risquer une corruption multi-octets sur D:. Cette nuit = re-verification
qualite complete + nouvelle tentative de dry-run reseau. Les deux resultats sont
inchanges : livrables sains, reseau toujours bloque.

## Etat des livrables (re-verifie ce soir)

1. SQL : database\migration_mcp_vertical.sql (2078 octets)
   - Verifie au niveau binaire : 0 octet nul, 0 caractere non-ASCII, CRLF,
     aucun " DO ", aucun trigger.
   - Valide par le vrai parseur PostgreSQL (pglast : parse OK ce soir).
   - Idempotent, dollar-quoting $t$...$t$, zero commentaire.
   - Contient mcp_servers (schema canonique doc sec.4) ET bridges (graphe
     generique : source_type, source_id, target_type, target_id, relation,
     weight, evidence + contrainte unique + index).
   - Inchange. NON EXECUTE sur Supabase (reserve a Josue).

2. Collecteur : prisme\b1_mcp.py (13599 octets)
   - ASCII pur, py_compile OK, --self-test OK
     (3 normalises, 1 doublon retire, 2 uniques, mappings valides).
   - Registre officiel en primaire (/v0/servers puis /v0.1/servers), pagination
     par cursor, normalisation canonique, dedup repo_url + nom canonique,
     enrichissement GitHub optionnel (topic:mcp-server) en secondaire.
   - Inchange.

## Dry-run reel : toujours BLOQUE (reseau)

- Bac a sable Linux : registry.modelcontextprotocol.io refuse les deux endpoints
  -> "Tunnel connection failed: 403 Forbidden" (domaine hors allowlist du bac a
  sable). Teste ce soir sur /v0/servers ET /v0.1/servers.
- Outil WebFetch : refuse aussi ("URL not in provenance set").
- Aucun contournement tente (curl/wget/requests interdits par garde-fou). Respecte.
- Aucun data\mcp_servers_staging.json produit : la verticale MCP attend encore
  son premier staging reel.

Chiffre de reference (doc EXTENSION, juin 2026) : ~9 652 serveurs au registre
officiel. Impossible de compter le vrai chiffre depuis le bac a sable ce soir.

## Observation recurrente (8e fois)

b1_mcp.py n'est TOUJOURS PAS branche dans run_nightly.py. Tant que ce pont local
n'est pas fait, cette tache repete le meme constat sans jamais produire de staging.
C'est le seul vrai levier de deblocage, et il vit du cote machine de Josue.

## Reste a executer par Josue (inchange)

1. Coller database\migration_mcp_vertical.sql dans Supabase (SQL Editor, fichier
   complet, Ctrl+A puis coller, Run).
2. Terminal Windows : cd D:\Emperor\YggNexus\prisme puis "python b1_mcp.py"
   -> ecrit data\mcp_servers_staging.json et imprime FETCHED / UNIQUE
   (la machine de Josue a acces au registre, contrairement au bac a sable).
3. (Optionnel) "python b1_mcp.py --enrich-github" avec GITHUB_TOKEN.

## Recommandation (A - B - C)

A : je prepare le patch qui branche b1_mcp.py dans run_nightly.py (un seul ajout
    de tache) et je te le soumets pour validation -> le staging MCP se remplirait
    tout seul chaque nuit sur ta machine. La voie la plus alignee. Ton OK requis
    avant que je touche run_nightly.py.
B : lancer b1_mcp.py une fois a la main demain matin pour amorcer le premier staging.
C : mettre cette tache de nuit en PAUSE jusqu'au premier staging - depuis 8 runs
    elle repete le meme constat de blocage reseau et n'apporte plus de valeur neuve
    tant que le pont local n'est pas branche. C'est la recommandation montante.

Farevel.
