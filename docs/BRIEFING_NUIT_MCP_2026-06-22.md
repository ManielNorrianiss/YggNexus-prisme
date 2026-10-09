# Briefing nuit - Verticale MCP (YggNexus)

> Tache planifiee : `yggnexus-ingestion-mcp-nuit`
> Premiere tournee : 2026-06-27. Tournee de verification : 2026-06-28.
> Perimetre : verticale MCP en priorite, sandbox d'autonomie `D:\Emperor\YggNexus` + `D:\ElderBrain`
> Principe : on est seulement le pont. Aucun push prod, aucun Supabase reel, aucun envoi.

---

## Etat au 2026-06-28 (re-verification)

Les deux livrables de la tournee du 2026-06-27 existent et sont re-valides ce soir. Rien a recreer. Le seul element manquant reste le compte reel de serveurs : le bac a sable bloque toujours le reseau sortant vers le registre.

---

## Ce qui existe et a ete re-valide

**1. Modele de donnees (SQL idempotent, pret a coller)**
`D:\Emperor\YggNexus\database\migration_mcp_vertical.sql`

- Table `mcp_servers` : schema canonique du doc section 4 (slug, name canonique `io.github.owner/server`, description, author, repo_url, registry_source, package_type + package_types[], transport + transports[], capabilities[], hosting, version, website_url, license, stars, weekly_downloads, quality_score, status, is_latest, published_at, embedding vector(768), timestamps).
- Table `bridges` : graphe generique (source_type, source_id, target_type, target_id, relation, weight, evidence) + contrainte d'unicite sur le quintuplet pour la dedup des liens.
- 6 index (repo_url, registry_source, status sur mcp_servers ; source, target, relation sur bridges).
- Conforme au skill d'ecriture SQL : ASCII pur (0 octet non-ASCII), zero commentaire, zero NUL byte, dollar-quoting `$t$...$t$` pour les literaux des CHECK, pas de DO/trigger/fonction, `create ... if not exists` partout (idempotent).
- Re-valide au parseur reel PostgreSQL (`pglast`) le 2026-06-28 : **9 instructions, parse sans erreur**.
- **NON execute** : laisse pret a coller dans Supabase par Josue.

**2. Collecteur Python (registre officiel)**
`D:\Emperor\YggNexus\prisme\b1_mcp.py`

- Source primaire : `https://registry.modelcontextprotocol.io` (API publique, sans auth). Essaie `/v0/servers` puis `/v0.1/servers`.
- Pagination par cursor (`metadata.nextCursor`), `limit` 100 par page, `--max-pages` (0 = tout).
- Normalisation vers le modele canonique (parse `server` + `_meta` officiel : status, isLatest, publishedAt ; repository.url ; packages[] -> package_type/transports ; remotes[] -> hosting remote).
- Deduplication par `repo_url` + nom canonique, la version `isLatest` gagne en cas de doublon.
- Enrichissement secondaire OPTIONNEL via GitHub API (`--enrich-github`, lit `GITHUB_TOKEN`) : stars + licence SPDX. Desactive par defaut.
- Sortie : `prisme/data/mcp_servers_staging.json`. Aucune ecriture Supabase (collecte seulement).
- Re-verifie le 2026-06-28 : `py_compile` OK, 100% ASCII, 0 NUL byte, auto-test (`--self-test`) **PASS** (3 normalises, 1 doublon retire, 2 uniques, mappings valides).

---

## Nombre de serveurs recuperes en dry-run

**Toujours non obtenu depuis cet environnement.** Le bac a sable bloque la sortie reseau vers le registre (`Tunnel connection failed: 403 Forbidden`), en direct (urllib) comme via l'outil web. Confirme de nouveau le 2026-06-28. Le collecteur gere ce cas proprement (erreur claire, code de sortie 2, aucun plantage).

Ordre de grandeur attendu (doc `EXTENSION_VERTICALES_AGENTS_SKILLS_MCP.md`, recherche juin 2026) : **registre officiel ~9 652 serveurs**. A confirmer par le dry-run reel sur la machine de Josue.

---

## Ce qui reste a valider / executer par Josue

1. **Coller le SQL dans Supabase** : ouvrir `database\migration_mcp_vertical.sql` dans le Bloc-notes, Ctrl+A / Ctrl+C (le fichier au complet), dans Supabase SQL Editor -> New query -> Ctrl+A puis Suppr pour vider -> Ctrl+V -> Run. Cree `mcp_servers`, `bridges` et les index. Idempotent : rejouable sans risque.
2. **Lancer le collecteur en reel** (depuis sa machine, reseau ouvert) :
   - `python b1_mcp.py` -> ecrit `prisme/data/mcp_servers_staging.json`, affiche `FETCHED N` et `UNIQUE M`. C'est ce run qui donnera le vrai compte.
   - Optionnel : `python b1_mcp.py --enrich-github` (avec `GITHUB_TOKEN` dans l'env) pour stars + licence.
3. **Brancher la propagation Supabase** (etape separee, pas encore faite) : export `mcp_servers_staging.json` -> table `mcp_servers` (sur le modele de `export_tools.py` / `publish.py`), puis B2 enrichissement (qwen + embeddings 768d) et B5 liens vers `bridges`.

---

## Blocages rencontres

- **Reseau sortant bloque dans le bac a sable** vers `registry.modelcontextprotocol.io` (403 sur le tunnel proxy), confirme deux nuits de suite. Impossible de faire le dry-run reel ni de compter les serveurs ici. Conformement au garde-fou, je n'ai pas force : note et continue avec ce qui marche. Tout le reste est verifie.

---

Farevel.
