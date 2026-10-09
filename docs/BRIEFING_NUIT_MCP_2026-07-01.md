# Briefing de nuit - Verticale MCP (2026-07-01)

> Tache planifiee "yggnexus-ingestion-mcp-nuit". Run autonome, Josue absent.
> Principe YggNexus : on est le pont, jamais l'hebergeur. Verticale prioritaire = serveurs MCP (voir EXTENSION_VERTICALES_AGENTS_SKILLS_MCP.md, section 9).

## Constat d'ouverture

Les deux livrables de la verticale MCP existaient deja et sont conformes au plan (crees le 28 juin, verifies le 30 juin). Cette nuit = re-verification complete de bout en bout et nouvelle tentative de dry-run reel. Rien de plus recent n'a ete ecrase, rien n'a ete duplique.

## Etat des livrables (re-verifie ce soir)

### 1. Modele de donnees (SQL)

Fichier : `D:\Emperor\YggNexus\database\migration_mcp_vertical.sql`

Contenu : table `mcp_servers` (schema canonique section 4, enrichi : package_types[], transports[], capabilities[], hosting, version, is_latest, published_at, embedding vector(768), quality_score, stars, weekly_downloads) et table `bridges` (graphe generique : source_type, source_id, target_type, target_id, relation, weight, evidence + contrainte unique + 3 index). 3 index aussi sur mcp_servers.

Conformite skill SQL : VERIFIE ce soir.
- ASCII pur : 0 octet non-ASCII, 0 octet nul, 2078 octets.
- Idempotent : create table if not exists, create index if not exists, create extension if not exists vector.
- Dollar-quoting `$t$...$t$` pour toutes les valeurs texte des CHECK et defaults.
- Zero commentaire, zero bloc DO, zero trigger, zero point-virgule dans une chaine.
- Parse PostgreSQL reel (pglast) : OK, 9 statements.

NON EXECUTE sur Supabase. Pret a coller par Josue.

### 2. Collecteur Python

Fichier : `D:\Emperor\YggNexus\prisme\b1_mcp.py`

Capacites : collecte du registre officiel `registry.modelcontextprotocol.io` (resolution auto endpoint /v0/servers ou /v0.1/servers), pagination par cursor (limit 100), normalisation vers le modele canonique, deduplication par repo_url + nom canonique (la version is_latest gagne), enrichissement secondaire optionnel via GitHub API (stars + licence SPDX) sous `--enrich-github`, et un `--self-test` sur fixture locale. Ecrit un staging JSON (`data/mcp_servers_staging.json`), aucune ecriture Supabase.

Qualite : VERIFIE ce soir.
- ASCII pur : 0 octet non-ASCII, 0 octet nul.
- py_compile : OK.
- --self-test : OK (3 normalises, 1 doublon retire, 2 uniques, mappings slug/author/package_type/transport/hosting/version valides).

## Dry-run reel : toujours BLOQUE (reseau)

Le comptage live des serveurs MCP n'a toujours pas pu etre obtenu en autonomie. Deux canaux testes ce soir, tous deux refuses :
- Bac a sable Linux, urllib direct sur `registry.modelcontextprotocol.io/v0/servers` : `Tunnel connection failed: 403 Forbidden` (domaine hors allowlist reseau).
- web_fetch : `URL not in provenance set` (l'URL ne vient pas d'un message utilisateur).

Conformement au garde-fou (ne pas forcer une API restreinte), arret sans contournement. Aucun staging n'a jamais ete produit en reel a ce jour.

Chiffre de reference (recherche juin 2026, doc section 2C) : le registre officiel listait ~9 652 serveurs. A confirmer en live par Josue.

## Reste a valider / executer par Josue

1. Coller `database\migration_mcp_vertical.sql` dans Supabase (SQL Editor, fichier au complet, fenetre videe d'abord) pour creer `mcp_servers` + `bridges`.
2. Lancer le collecteur en reel depuis le terminal Windows (ou le registre est joignable) :
   cd D:\Emperor\YggNexus\prisme
   python b1_mcp.py
   -> ecrit data\mcp_servers_staging.json et imprime FETCHED / UNIQUE / duplicates_dropped.
3. (Optionnel) `--enrich-github` avec `GITHUB_TOKEN` dans l'environnement pour stars + licence.
4. Ecrire le pont staging JSON -> Supabase (etape B-suivante, calquee sur export_tools.py / publish.py). Rien ne va dans mcp_servers tant que ce pont n'est pas ecrit.
5. Plus tard (section 5 du doc) : B5 graphe `bridges` (signaux explicites README/allowed-tools + cosinus), puis verticales skills et agents.

## Blocage unique de la nuit

Reseau du bac a sable : domaine du registre MCP non allowliste, et web_fetch limite aux URLs de provenance. Dry-run reel impossible en autonomie, comme les nuits precedentes. Tout le reste (SQL + collecteur + qualite) est vert.

## Verification effectuee ce soir

pglast (parse PostgreSQL reel) sur le SQL : OK, 9 statements. Controle ASCII/octets nuls sur .sql et .py : OK. py_compile : OK. self-test du collecteur : OK. Deux tentatives de dry-run reel (urllib + web_fetch) : bloquees, documentees.

Farevel.
