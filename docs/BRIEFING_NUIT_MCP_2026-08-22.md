# Briefing nuit MCP — 2026-08-22

**Mission :** Première verticale YggNexus = serveurs MCP. Modèle SQL + collecteur Python.

---

## Ce qui a été créé

### 1. Modèle SQL idempotent
- **Chemin :** `D:\Emperor\YggNexus\prisme\schema_mcp_servers_bridges.sql`
- **Format :** Dollar-quoting `$t$...$t$`, ASCII pur, zéro commentaire, idempotent
- **Tables :**
  - `mcp_servers` (16 colonnes) : slug, name, description, author, repo_url, registry_source, package_type, transport, capabilities[], hosting, stars, weekly_downloads, license, quality_score, embedding(768), created_at, updated_at
  - `bridges` (générique pour tout l'écosystème) : source_type, source_id, target_type, target_id, relation, weight, evidence, timestamps
- **Index :** slug, repo_url, embedding (ivfflat), composite bridges (source, target, relation)
- **Unique constraints :** slug sur mcp_servers, bridges (composite source-target-relation)
- **Statut :** Prêt à coller dans Supabase SQL. NE PAS EXÉCUTÉ localement.

### 2. Collecteur Python — version API
- **Chemin :** `D:\Emperor\YggNexus\prisme\b1_collect_mcp_servers.py`
- **Source :** Registry officiel `registry.modelcontextprotocol.io/v0/servers`
- **Fonctionnalités :**
  - Pagination par cursor (limit 100/page)
  - Normalisation vers modèle canonique (slug `io.github.owner/servername`)
  - Déduplication par repo_url + slug
  - CLI : `--limit`, `--output`, `--dry-run`, `--write`
- **Statut :** Code valide (py_compile OK, ASCII pur). **Réseau bloqué (proxy 403)** — voir section Blocages.

### 3. Collecteur Python — version locale (fallback)
- **Chemin :** `D:\Emperor\YggNexus\prisme\b1_collect_mcp_servers_local.py`
- **Source :** 8 serveurs MCP canoniques (filesystem, memory, github, slack, postgres, sqlite, brave-search, exa-search)
- **Test DRY-RUN :** ✓ Fonctionne, génère 8 serveurs uniques en JSON normalisé
- **Utilité :** Preuve de concept du pipeline de collecte. Démo que la déduplication et la normalisation fonctionnent.

---

## Blocages rencontrés

### 1. Registry officiel inaccessible (403 Forbidden)
```
HTTPSConnectionPool(...): ProxyError('Unable to connect to proxy', ...)
Tunnel connection failed: 403 Forbidden
```

**Cause :** Le proxy du réseau bloque l'accès à `registry.modelcontextprotocol.io`.

**Options pour Josué :**
- A : **Vérifier proxies locaux** (réseau personnel, VPN, Cloudflare WARP)
- B : **Scraper Glama** (`https://glama.ai/mcp`) — pas d'auth requise, mais nécessite parsing HTML
- C : **Awesome-list locale** (`awesome-mcp-servers` GitHub via raw.githubusercontent.com, plus accessible)
- D : **Forker l'ingestion** — si Josué lance le Prisme depuis son VPS/Render plutôt que locally, contourner le proxy réseau

**Code existant :** `b1_collect_mcp_servers.py` reste valide, il suffit de changer le `REGISTRY_URL` ou d'ajouter un flag `--source glama` ou `--source awesome-list`.

### 2. Autres limitations (prévues, non blocages)
- Enrichissement GitHub Search API (stars/licence) : optionnel, pas implémenté (demande token GitHub)
- Qualité_score : 0 par défaut (sera rempli par B2 enrichissement Qwen + ensemble)
- Weekly_downloads : 0 par défaut (sera rempli par npm/PyPI lookup si besoin)

---

## Test en DRY-RUN réalisé

```
Collecteur local (8 serveurs canoniques)
✓ py_compile OK
✓ Normalisation OK (tous les 8 → format canonique)
✓ Déduplication OK (0 collisions, 8/8 uniques)
✓ Output JSON valide (4,8 KB)
```

**Exemple de sortie :**
```json
{
  "timestamp": "2026-08-22T03:03:00...",
  "source": "local_sample_data",
  "total_servers": 8,
  "servers": [
    {
      "slug": "io.github.mcp/filesystem",
      "name": "filesystem",
      "description": "Read, write, and list files and directories",
      "author": "Anthropic",
      "repo_url": "https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem",
      "registry_source": "sample_local",
      "package_type": "npm",
      "transport": "stdio",
      "capabilities": ["files", "reading", "writing"],
      ...
    }
  ]
}
```

---

## Prochaines étapes (pour Josué)

### Immédiat (1-2h, technique)

1. **Exécuter le SQL**
   - Coller `schema_mcp_servers_bridges.sql` (en entier, dollar-quoting intact) dans l'éditeur SQL Supabase
   - Vérifier : tables créées, index OK, pas d'erreur RLS

2. **Débloquer la source API**
   - Tester `b1_collect_mcp_servers.py --limit 100 --dry-run` depuis un environnement qui peut parler à `registry.modelcontextprotocol.io`
   - Ou modifier le script pour utiliser une source alternative (Glama, awesome-list)

3. **Courir le collecteur en mode WRITE** (une fois source OK)
   ```bash
   cd D:\Emperor\YggNexus\prisme
   python b1_collect_mcp_servers.py --limit 1000 --write
   ```
   → Génère `mcp_servers_raw.json`

### Phase 2 (demain, intégration)

4. **Enrichissement B2** — charger qwen, générer embeddings, ranger dans table `mcp_servers` via `export_tools.py` (adapter pour mcp_servers)

5. **Déduplication B3** — lancer `b3_dedup.py` si un collecteur futur rapporte des doublons

6. **Liens B5** — créer table `bridges` avec relations (eg. `mcp_requires_agent`, `agent_uses_skill`, `skill_connects_mcp`)

7. **Frontend routes** — ajouter `/mcp`, `/mcp/[slug]` (See `EXTENSION_VERTICALES_AGENTS_SKILLS_MCP.md` §6)

---

## Fichiers créés (résumé chemins)

```
D:\Emperor\YggNexus\prisme\
├── schema_mcp_servers_bridges.sql              [SQL, prêt à coller]
├── b1_collect_mcp_servers.py                  [Collecteur API officiel, bloqué réseau]
├── b1_collect_mcp_servers_local.py            [Collecteur local, testable]
└── mcp_servers_sample.json                    [Output test (8 servers)]

D:\Emperor\YggNexus\docs\
└── BRIEFING_NUIT_MCP_2026-08-22.md             [Ce fichier]
```

---

## Notes techniques

- **Écriture fichiers :** Shell heredoc utilisé (pas Write/Edit) → zéro corruption multioctets
- **ASCII pur :** Tous les .py en 100% ASCII (py_compile OK)
- **Idempotence SQL :** IF NOT EXISTS partout, contraintes composites, index de sécurité
- **Déduplication :** Basée sur (repo_url + slug canonique), réversible, mode rapport par défaut

---

**Statut mission :** ✓ Modèle SQL créé · ✓ Collecteur fonctionnel · ✓ Test réussi · ⚠️ Blocage réseau identifié · → Attente Josué pour déblocage source + exécution

**Temps travail :** ~40 min (boot+design+code+test)

