# Briefing de nuit - Verticale MCP (2026-06-30)

> Tache planifiee "yggnexus-ingestion-mcp-nuit". Run autonome, Josue absent.
> Principe YggNexus : on est le pont, jamais l'hebergeur. Verticale prioritaire = serveurs MCP (voir EXTENSION_VERTICALES_AGENTS_SKILLS_MCP.md, section 9).

## Constat d'ouverture

Le travail de cette verticale etait deja amorce lors d'un run anterieur (fichiers dates du 28 juin, posterieurs au premier briefing du 22 juin). Les deux livrables existaient deja et sont conformes au plan. Cette nuit = verification de bout en bout, comptage tente, et consignation. Aucun ecrasement de travail plus recent.

## Etat des livrables

### 1. Modele de donnees (SQL)

Fichier : `D:\Emperor\YggNexus\database\migration_mcp_vertical.sql`

Contenu : tables `mcp_servers` (schema canonique section 4, enrichi : package_types[], transports[], capabilities[], hosting, version, is_latest, published_at, embedding vector(768)) et `bridges` (graphe generique : source_type, source_id, target_type, target_id, relation, weight, evidence + contrainte unique + 3 index).

Conformite au skill d'ecriture SQL : VERIFIE.
- ASCII pur (0 octet non-ASCII, 0 octet nul).
- Idempotent (`create table if not exists`, `create index if not exists`, `create extension if not exists vector`).
- Dollar-quoting `$t$...$t$` pour les valeurs texte des CHECK.
- Zero commentaire, zero bloc DO, zero trigger, zero point-virgule dans une chaine.
- Parse PostgreSQL reel via pglast : OK (9 statements).

NON EXECUTE sur Supabase. Pret a coller par Josue.

### 2. Collecteur Python

Fichier : `D:\Emperor\YggNexus\prisme\b1_mcp.py`

Capacites : collecte du registre officiel `registry.modelcontextprotocol.io` (resolution auto de l'endpoint /v0/servers ou /v0.1/servers), pagination par cursor (limit 100), normalisation vers le modele canonique, deduplication par repo_url + nom canonique (la version is_latest gagne), enrichissement secondaire optionnel via GitHub API (stars + licence SPDX) sous `--enrich-github`, et un `--self-test` sur fixture locale. Ecrit un staging JSON (`data/mcp_servers_staging.json`), aucune ecriture Supabase.

Qualite : VERIFIE.
- ASCII pur (0 octet non-ASCII, 0 octet nul).
- `py_compile` : OK.
- `--self-test` : OK (3 normalises, 1 doublon retire, 2 uniques, mappings slug/author/package_type/transport/hosting/version valides).

## Dry-run reel : BLOQUE (a faire par Josue)

Le comptage live des serveurs MCP n'a PAS pu etre obtenu en autonomie.
- Depuis le bac a sable Linux : `registry.modelcontextprotocol.io` n'est pas sur l'allowlist reseau. Le proxy renvoie `Tunnel connection failed: 403 Forbidden`.
- web_fetch : refuse l'URL (hors ensemble de provenance, aucune URL fournie par un message utilisateur).
- Conformement aux garde-fous (ne pas forcer une API restreinte), je me suis arrete la sans contournement.

Chiffre de reference (recherche de juin 2026, doc section 2C) : le registre officiel listait ~9 652 serveurs. A confirmer en live.

Action Josue : lancer depuis le terminal Windows (ou le registre est joignable) :
```
cd D:\Emperor\YggNexus\prisme
python b1_mcp.py
```
Cela ecrit `data\mcp_servers_staging.json` et imprime FETCHED / UNIQUE / duplicates_dropped. Option enrichissement (lent, rate-limit GitHub) : ajouter `--enrich-github` avec `GITHUB_TOKEN` dans l'environnement.

## Reste a valider / executer par Josue

1. Coller `database\migration_mcp_vertical.sql` dans Supabase (SQL Editor, fichier au complet, fenetre videe d'abord) pour creer `mcp_servers` + `bridges`.
2. Lancer `python b1_mcp.py` en reel pour obtenir le staging JSON et le compte live.
3. (Optionnel) `--enrich-github` pour stars + licence.
4. Brancher la propagation staging JSON -> Supabase (etape B-suivante, calquee sur export_tools.py / publish.py, reservee a Josue) ; aucune ne va dans mcp_servers tant que ce pont n'est pas ecrit.
5. Plus tard (section 5 du doc) : B5 graphe `bridges` (signaux explicites README/allowed-tools + cosinus), puis verticales skills et agents.

## Blocages rencontres

- Reseau du bac a sable : domaine du registre MCP non allowliste -> dry-run reel impossible en autonomie (seul vrai blocage de la nuit).
- Aucun staging anterieur present dans `prisme\data\` : le collecteur n'a donc jamais tourne en reel a ce jour ; premier run reel a faire par Josue.

## Verification effectuee cette nuit

pglast (parse PostgreSQL reel) sur le SQL : OK. Controle ASCII/octets nuls sur .sql et .py : OK. py_compile : OK. self-test du collecteur : OK. Tentative de dry-run reel : bloquee reseau, documentee.

Farevel.
