# Briefing Nuit - Verticale MCP - 2026-08-09

**L'essentiel : j'ai trouvé un trou qui invalidait une partie des nuits précédentes — les fixtures servant aux dry-runs étaient des faux. Corrigé. Et le graphe pont (`bridges`) existe maintenant pour vrai : premier jet de 9 ponts sur les 15 serveurs de la page 1.**

Contexte : session précédente le 8 août. Josué n'a pas encore collé le SQL ni lancé la collecte réelle, donc je n'ai pas repris la même vérification pour la 5e fois — j'ai attaqué la valeur non faite (B5) et j'ai audité la méthode.

---

## 1. Le trou de méthode (le point important de la nuit)

Les fixtures `prisme\data\registry_real_page_*.json` des nuits du 7 et du 8 août **ne sont pas des copies fidèles du registre**. Comparaison faite ce soir contre la vraie réponse de l'API :

| Champ | Dans la fixture stockée | Dans la vraie réponse |
|---|---|---|
| `description` | `ac.tandem/docs-mcp MCP server` (gabarit) | `Remote MCP server for Tandem docs, install guides, SDKs...` |
| `remotes[].url` | `https://example.invalid/mcp` | `https://tandem.ac/mcp` |
| `websiteUrl` | absent | présent sur 12 serveurs sur 15 |
| `title` | absent | présent |
| `packages[].identifier` | recopie du nom du serveur | `pretrip-mcp`, `@adeu/mcp-server`, `@aetherwealth/mcp` |

Ce qui était réel : les noms, les versions, les dates, les `repository.url`, les `registryType`. **C'est pour ça que les comptes structurels des briefings du 7 et du 8 (12 streamable-http / 3 stdio, 12 remote / 3 local, 6 repo_url, 0 licence) restent bons** — ils ne dépendaient que des champs réels. Ce qui était faux, c'est tout ce qui touche au texte et aux URL. Et c'est précisément la matière de B2 (couche éditoriale) et de B5 (graphe pont).

**Corrigé cette nuit :** `prisme\data\registry_real_page_20260809.json` est reconstruit à partir de la vraie réponse de l'API, 30 entrées, ASCII pur. C'est la première fixture fidèle du lot.

---

## 2. Nouveau livrable - `b5_bridges_mcp.py`

Le graphe pont était le différenciateur du projet et il n'existait qu'en plan. Il tourne maintenant, hors ligne, sans Supabase.

`D:\Emperor\YggNexus\prisme\b5_bridges_mcp.py` construit les lignes `bridges` par signaux explicites (aucun LLM, aucun embedding, aucun réseau) :

- **`wraps`** — serveur MCP vers le SaaS sous-jacent, détecté par nom, description et domaine, sur une table de ~30 SaaS connus.
- **`alternative_of`** — deux serveurs qui enveloppent le même SaaS, ou dont les descriptions se recouvrent (Jaccard, seuil `--threshold` 0.35 par défaut).
- **`depends_on`** — serveur vers son paquet npm/PyPI réel.

Résultat sur la page 1 réelle (15 serveurs uniques) : **9 ponts**.

| Relation | Ponts | Exemples |
|---|---|---|
| `wraps` | 4 | `ai-adramp-google-ads` -> `google-ads` · `ai-adweave-meta-ads-mcp` -> `meta-ads` |
| `alternative_of` | 2 | `ai-adadvisor-mcp-server` <-> `ai-adweave-meta-ads-mcp` (même SaaS) |
| `depends_on` | 3 | `ai-aetherwealth-mcp` -> `npm:@aetherwealth/mcp` |

Chaque ligne porte son `evidence` (`name:google ads`, `desc:meta ads`, `same-saas:meta-ads`, `package:npm`) — l'attribution est traçable, ce qui répond au risque licence/backlash de la section 8 du doc.

**Preuve que la fixture comptait :** le même script sur l'ancienne fixture synthétique du 8 août ne sortait que 2 `wraps` et **0** `alternative_of`. Sur la vraie page : 4 et 2. Le faux jeu de données cachait la moitié du graphe.

Validations : `py_compile` PASS · `--self-test` PASS · ASCII pur · 0 octet nul. Par défaut le script est en dry-run et n'écrit rien.

---

## 3. Collecteur enrichi

`b1_mcp.py` perdait trois informations utiles du registre. Ajoutées (patch écrit via le shell, sauvegarde `b1_mcp.py.bak.20260809`) :

- `package_identifier` — le vrai identifiant npm/PyPI (`pretrip-mcp`, pas le nom du serveur). Ouvre la porte aux téléchargements réels npm/PyPI, donc au score de qualité.
- `package_ids` — liste préfixée (`npm:@adeu/mcp-server`).
- `remote_urls` — les URL des serveurs distants, qui alimentent la détection de domaine de B5.

`py_compile` PASS, `--self-test` PASS, ASCII pur, 0 octet nul.

---

## 4. SQL mis à jour

`database\migration_mcp_vertical.sql` reçoit trois `alter table ... add column if not exists` pour les nouveaux champs. Additif et idempotent : coller le fichier deux fois ne casse rien, même si tu l'avais déjà passé.

Contrôles : **`pglast` PASS (12 instructions)** · 0 commentaire · 0 bloc `DO` · ASCII pur · 0 octet nul · 56 fins de ligne CRLF. Sauvegarde `migration_mcp_vertical.sql.bak.20260809`.

Contrôle de cohérence refait : **28 colonnes, 24 champs produits par le collecteur, zéro champ orphelin.**

---

## 5. Le registre a bougé

| Mesure | 8 août | 9 août | Delta |
|---|---|---|---|
| Entrées brutes page 1 | 30 | 30 | 0 |
| Serveurs uniques | 15 | 15 | 0 |
| `nextCursor` | `ai.aetherwealth/mcp:0.2.9` | `ai.aetherwealth/mcp:0.2.7` | a reculé |

**Apparu :** `ai.aetherwealth/mcp` v0.2.14, publiée le 8 août à 11 h 13, devenue la version courante. **Sorti :** v0.2.9, poussée hors de la fenêtre. Aucun serveur nouveau, aucun disparu — une seule publication de version.

---

## 6. Compte de serveurs (dry-run)

| Source | Valeur |
|---|---|
| Page réelle du 9 août | 30 entrées brutes -> **15 uniques** |
| Delta vs 8 août | **0 serveur** (1 version) |
| Total registre (réf. doc section 2) | ~9 652 serveurs (non recompté - pagination indisponible d'ici) |

---

## 7. À faire par Josué

1. **Coller le SQL dans Supabase** (~5 min) - `D:\Emperor\YggNexus\database\migration_mcp_vertical.sql` dans le Bloc-notes, Ctrl+A / Ctrl+C, puis Supabase : SQL Editor -> New query -> Ctrl+A / Suppr -> Ctrl+V -> Run. **Pas** `sql\001_mcp_servers_and_bridges.sql`.
2. **Lancer la collecte réelle** depuis Windows (~15 min) :
   ```
   cd D:\Emperor\YggNexus\prisme
   python b1_mcp.py --limit 100 --max-pages 0
   ```
3. **Lancer le graphe pont** sur la collecte complète, en dry-run d'abord :
   ```
   python b5_bridges_mcp.py --in data\mcp_servers_staging.json
   ```
   Sur 9 652 serveurs au lieu de 15, c'est là qu'on verra si la table de SaaS connus tient ou s'il faut l'élargir.
4. **Deux ménages** (5e nuit que je les redemande) : archiver `sql\001_mcp_servers_and_bridges.sql` (non conforme : commentaires + 4 blocs `DO`) et `prisme\b1_collect_mcp_servers.py` (collecteur doublon).
5. **Un fichier vide à supprimer** : `prisme\data\registry_real_page_20260809.raw.json` — le bac à sable Linux n'a pas le droit d'effacer sur `D:`, je l'ai seulement vidé.
6. **Rythme de la tâche planifiée.** Cette nuit avait de la matière, mais uniquement parce que j'ai changé de sujet. Le reste est bloqué sur les étapes 1 et 2 ci-dessus.
   - **A (recommandé)** - suspendre jusqu'à ce que le SQL soit collé et la collecte réelle lancée. Elle reprend sur B2 avec du vrai volume.
   - **B** - hebdomadaire, le mercredi, avec l'extracteur de skills.
   - **C** - la laisser quotidienne.

---

## 8. Blocages

- **Pagination toujours impossible d'ici** : le fetch autorisé refuse les URL avec `?cursor=`. Impossible de dépasser la page 1 ni de recompter le total. Inchangé depuis le 20 juillet.
- **Proxy du bac à sable 403** sur toute sortie réseau Python. La collecte complète reste sur ta machine.
- **Suppression de fichiers impossible** sur les dossiers `D:` montés depuis le bac à sable (permission refusée). Je peux écrire et vider, pas effacer.
- Aucun push Supabase, GitHub ni Vercel. Aucun envoi. Aucune écriture hors `D:\Emperor\YggNexus`. Garde-fous respectés.

---

*Session autonome Emperor - 2026-08-09. Le nom demandé par la tâche (2026-06-22) existe déjà ; convention du jour d'exécution maintenue.*

Farevel.
