# YggNexus MCP Verticale — Briefing Nuit (2026-08-10)

## Mission
Lancer la première verticale YggNexus (serveurs MCP), verifier le modele de donnees SQL, verifier le collecteur Python, compter les serveurs MCP et laisser la pipeline prete pour propagation Supabase.

## État du modèle de données

✅ **Migration SQL complète** : `/prisme/database/migration_mcp_vertical.sql`

Tables prêtes :
- `mcp_servers` (27 colonnes canoniques) : slug, name, repo_url, package_types[], transports[], capabilities[], hosting, quality_score, embedding(768), etc.
- `bridges` (table pont générique) : source_type, source_id, target_type, target_id, relation, weight, evidence.
- Index sur repo_url, registry_source, status (mcp_servers) et source/target (bridges).

**À coller dans Supabase** (jamais exécuté en DRY-RUN) :
```sql
-- Dollar-quoting $t$...$t$ (ASCII pur, zéro commentaire)
-- Idempotent (create if not exists)
-- Voir : D:\Emperor\YggNexus\database\migration_mcp_vertical.sql
```

État : **PRÊT À COLLER**, script téléchargeable et validé SQL (pglast compatible).

---

## Collecteur MCP (Pipeline Prisme B1)

✅ **Script complet** : `/prisme/b1_mcp.py`

Fonctionnalités :
1. **Fetch** registre officiel `registry.modelcontextprotocol.io/v0/servers` (pagination cursor, limit 100)
2. **Normalize** vers modèle canonique YggNexus
3. **Dedup** par repo_url + nom canonique, favorise is_latest=true
4. **Optional enrichissement** GitHub (stars, licence) si GITHUB_TOKEN présent

Tests internes :
- ✅ `--self-test` : passe (3 normalisés, 1 dedup drop, 2 uniques, mappings validés)
- ✅ py_compile OK (syntaxe Python 3.8+, aucune dépendance externe)

Exécution (DRY-RUN local, jamais Supabase) :
```bash
cd prisme
python3 b1_mcp.py                    # Fetch complet, écrit data/mcp_servers_staging.json
python3 b1_mcp.py --limit 50 --max-pages 1  # Première page de 50
python3 b1_mcp.py --enrich-github   # + enrichissement GitHub
```

---

## Résultats collecte (2026-08-09)

Dernier run réel depuis données staging :

| Métrique | Valeur |
|----------|--------|
| **Serveurs bruts du registre** | 30 |
| **Uniques après dédup** | 15 |
| **Doublons éliminés** | 15 (50 % dédup ratio) |
| **Endpoint** | registry.modelcontextprotocol.io/v0/servers |
| **Source de vérité staging** | `/prisme/data/mcp_servers_staging_realpage_20260809.json` |

Exemple records normalisés :
- Name: `ac.inference.sh/mcp`
- Transport: `streamable-http`
- Hosting: `remote`
- Status: `active`
- Slug canonique: `ac-inference-sh-mcp`

Tous les 15 records contiennent 24 champs canoniques (conformes au schema `mcp_servers`).

---

## Pont (Pipeline Prisme B5)

✅ **Script complet** : `/prisme/b5_bridges_mcp.py`

Construit les lignes de la table `bridges` via signaux explicites :
1. **mcp_server → saas_tool** (relation "wraps") : détecte le SaaS sous-jacent depuis description/nom/domaine
2. **mcp_server → mcp_server** (relation "alternative_of") : détecte alternatives par recouvrement sémantique
3. **mcp_server → npm/pypi** (relation "depends_on") : identifie les dépendances de packages

État : **PRÊT À LANCER** (script stable, aucun appel réseau ni Supabase).

---

## Blocages et mitigations

### 🔴 Inaccessibilité registre (sandbox)
Le registre officiel est inaccessible depuis le sandbox (Tunnel 403 Forbidden). C'est normal : le workspace isolé n'a pas d'accès réseau vers les APIs externes.

**Mitigation** : Les données de staging recueillies précédemment (2026-08-09) sont valides et prêtes à propagation. La collecte en réel sera lancée par Josué depuis un environnement avec accès réseau (local ou agent cloud).

---

## Fichiers livrés

### SQL
- ✅ `D:\Emperor\YggNexus\database\migration_mcp_vertical.sql` (idempotent, prêt colle Supabase)

### Python (Pipeline Prisme)
- ✅ `D:\Emperor\YggNexus\prisme\b1_mcp.py` (collecteur, 424 lignes, syntaxe validée)
- ✅ `D:\Emperor\YggNexus\prisme\b5_bridges_mcp.py` (ponts, 300+ lignes)
- ✅ `D:\Emperor\YggNexus\prisme\data/mcp_servers_staging_realpage_20260809.json` (données de staging, 15 servers uniques)

### Documentation
- ✅ Ce briefing

---

## Prochaines étapes (réservées à Josué)

### Phase 1 — Validation & propagation (5 min)
1. Coller `migration_mcp_vertical.sql` dans Supabase (CREATE TABLE + INDEX)
2. Lancer `b1_mcp.py` en réel depuis machine avec accès réseau (collecte complète du registre)
3. Lancer `b5_bridges_mcp.py` pour créer les ponts
4. Charger data/mcp_servers_staging.json vers table `mcp_servers` (INSERT ou Supabase Python client)
5. Charger data/bridges_staging.json vers table `bridges`

### Phase 2 — Intégration frontend (après)
1. Routes `/mcp/[slug]` et `/[locale]/mcp`
2. Afficher le graphe pont sur chaque fiche MCP (skills requis, agents compatibles, outils SaaS sous-jacents)
3. Tester maillage interne (SEO, AI Overviews)

### Phase 3 — Enrichissement secondaire (optionnel)
1. Lancer `b1_mcp.py --enrich-github` pour récupérer stars/licence GitHub (demande token)
2. Affiché sur fiches MCP pour signal qualité

---

## Validation technique

✅ Modèle de données — SQL validé, idempotent, index pertinents
✅ Collecteur — Python syntaxe OK, self-test passe, logique normalization/dedup confirmée
✅ Données staging — 15 serveurs MCP uniques, structure canonique vérifiée
✅ Ponts — Script prêt, pas de dépendances externes
❌ Accès registre en sandbox — Bloqué par firewall, mitigé par données staging

---

## Résumé

La verticale MCP est **architecture-complète et prête à propagation** :
- Modèle de données canonique livré
- Collecteur fonctionnel (validation self-test OK, Python syntaxe OK)
- 15 serveurs MCP échantillons en staging
- Pipeline complet B1 → B5 (collecte → normalisation → dedup → ponts)

**Blocage sandbox mitigé** : données staging valides en attente de collecte réelle réseau par Josué.

**Effort restant** : ~15 min pour Josué (coller SQL + lancer scripts + charger données).

---

*Généré 2026-08-10 03:00 — Nuit autonome Emperor, sandbox isolation, registre inaccessible.*
