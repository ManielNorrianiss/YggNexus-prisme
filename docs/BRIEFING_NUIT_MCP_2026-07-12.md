# Briefing nuit - verticale MCP - 2026-07-12

> 9e run de cette tache de nuit. Le prompt planifie porte encore la date
> figee du 22 juin ; le vrai jour est le 12 juillet 2026.

## Verdict en une phrase

Rien de neuf : les deux livrables sont deja crees, re-verifies et intacts ;
le dry-run reel reste bloque par le reseau du bac a sable, comme aux 8 runs
precedents. Aucune valeur nouvelle produite ce soir.

## Etat des livrables (re-verifie ce soir)

1. SQL : database\migration_mcp_vertical.sql (2078 octets, 9 instructions)
   - 0 octet nul (verifie au niveau binaire), 0 caractere non-ASCII.
   - Aucun DO, aucun trigger. Dollar-quoting $t$...$t$. Idempotent.
   - Valide par le vrai parseur PostgreSQL (pglast : parse OK, 9 statements).
   - Contient mcp_servers (schema canonique doc sec.4) ET bridges (graphe
     generique : source_type, source_id, target_type, target_id, relation,
     weight, evidence + contrainte unique + index).
   - Inchange. NON EXECUTE sur Supabase (reserve a Josue).

2. Collecteur : prisme\b1_mcp.py (13599 octets)
   - ASCII pur (0 octet > 127), py_compile OK, --self-test OK
     (3 normalises, 1 doublon retire, 2 uniques, mappings valides).
   - Registre officiel en primaire (/v0/servers puis /v0.1/servers), pagination
     par cursor, normalisation canonique, dedup repo_url + nom canonique,
     enrichissement GitHub optionnel (--enrich-github, topic:mcp-server).
   - Inchange.

## Dry-run reel : toujours BLOQUE (reseau)

- Collecteur lance (b1_mcp.py --max-pages 1) : "Tunnel connection failed:
  403 Forbidden" sur /v0/servers ET /v0.1/servers. Le domaine
  registry.modelcontextprotocol.io est hors allowlist du bac a sable.
- Outil WebFetch : refuse aussi ("URL not in provenance set").
- Aucun contournement (curl/wget/requests) : interdit par garde-fou. Respecte.
- Aucun data\mcp_servers_staging.json produit. La verticale MCP attend encore
  son premier staging reel.

Chiffre de reference (doc EXTENSION, juin 2026) : ~9 652 serveurs au registre
officiel. Impossible de compter le vrai chiffre depuis le bac a sable ce soir.

## Le vrai levier (9e rappel)

b1_mcp.py n'est TOUJOURS PAS branche dans run_nightly.py, et le bac a sable
n'atteindra jamais le registre. Le seul deblocage possible vit du cote machine
de Josue. Tant que le pont local n'est pas fait, cette tache repete le meme
constat sans jamais produire de staging.

## Reste a executer par Josue (inchange)

1. Coller database\migration_mcp_vertical.sql dans Supabase (SQL Editor, fichier
   complet, Ctrl+A puis coller, Run).
2. Terminal Windows : cd D:\Emperor\YggNexus\prisme puis "python b1_mcp.py"
   -> ecrit data\mcp_servers_staging.json et imprime FETCHED / UNIQUE
   (ta machine a acces au registre, contrairement au bac a sable).
3. (Optionnel) "python b1_mcp.py --enrich-github" avec GITHUB_TOKEN.

## Recommandation (A - B - C)

A : mettre cette tache de nuit en PAUSE jusqu'au premier staging reel. Depuis
    9 runs elle repete le meme blocage reseau et n'apporte plus rien de neuf.
    La voie la plus honnete : elle brule des tokens pour un constat identique.
B : je prepare le patch qui branche b1_mcp.py dans run_nightly.py (un seul ajout
    de tache) et je te le soumets pour validation -> le staging se remplirait
    tout seul chaque nuit sur ta machine. Ton OK requis avant que je touche
    run_nightly.py.
C : lancer b1_mcp.py une fois a la main demain matin pour amorcer le staging.

Farevel.
