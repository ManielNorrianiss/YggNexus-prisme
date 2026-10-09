# 🌉 Extension YggNexus — Agents · Skills · MCP servers

> **Type :** Document stratégique + plan technique
> **Complète :** `KIT_STRATEGIQUE_YGGNEXUS.md`
> **Principe directeur :** YggNexus est **le pont**, jamais l'hébergeur ni le constructeur. On indexe, on relie, on explique quoi faire avec — on ne possède pas la ressource.
> **Version :** 1.0 — 2026-06-21 (recherche GitHub/web de juin 2026)

---

## 1. La thèse en une phrase

> **Personne ne relie les agents, les skills et les serveurs MCP dans un seul graphe de découverte.** Le marché est en silos. YggNexus devient le pont qui connecte `agent → skills requis → connecteurs MCP → outil SaaS sous-jacent → automatisation`.

C'est le prolongement naturel de la mission (*Turn any AI tool into a working automation*) : un agent ne tourne pas seul — il a besoin de skills, de connecteurs MCP et d'outils. YggNexus est la carte qui montre l'assemblage complet.

---

## 2. Le paysage (état juin 2026)

### Verticale A — AI agents

- **Volume :** ~20 000 dépôts GitHub tagués `ai-agents` ; annuaires web établis (aiagentsdirectory.com 1 300+, aiagentslist.com 600+, AI Agent Store).
- **Source de référence :** `e2b-dev/awesome-ai-agents` (27,8k ★).
- **Métadonnées type :** name, description, url, catégorie, pricing, framework (LangChain/CrewAI/AutoGen…), repo GitHub (stars/forks/last_commit), licence, topics.
- **Friction marché :** fragmentation totale (8+ marketplaces sans recherche croisée), pas de standard de qualité, metadata incohérente, lock-in plateforme.

### Verticale B — Skills / plugins

- **Standard émergent :** `SKILL.md` (format cross-agents publié par Anthropic déc. 2025, 26+ outils adoptés). Frontmatter YAML (name, description, license, compatibility, allowed-tools, author, version) + corps markdown.
- **Volume :** signal curé ~3 600–7 000 skills (agentskill.club, SkillHub) ; bruit massif côté scrape brut (SkillsMP ~1,7 M). GPT Store : 3 M+ GPTs mais quasi-illisible.
- **Friction marché :** zéro portabilité cross-plateforme (un skill Claude ≠ Cursor ≠ Codex), qualité inconsistante, funnel contrôlé par les éditeurs.

### Verticale C — MCP servers / connecteurs

- **Volume :** Glama 39 305 serveurs · mcp.so 22 606 · PulseMCP ~19 000 · Smithery 11 245 · **Registre officiel `registry.modelcontextprotocol.io` 9 652** (API REST publique, sans auth). Awesome-list de facto : `punkpeye/awesome-mcp-servers` (89,5k ★).
- **Dynamique :** MCP lancé nov. 2024, ~3-4× de croissance en 6 mois, SDK à 97 M+ téléchargements/mois, 41 % des orgs logicielles en production.
- **Friction marché :** aucun signal qualité universel, config manuelle, zéro déduplication entre registres (même serveur listé 5 fois avec metadata divergente), READMEs souvent vides.

### Concurrents à connaître (et leur trou)

| Acteur | Couvre | Faiblesse |
| --- | --- | --- |
| Glama | MCP (39k) | Registre pur, pas d'agents ni skills, zéro couche éditoriale |
| Smithery | MCP (11k) + amorce skills | Pas d'agents, pas de reco croisée |
| **Agensi** | Skills + MCP | Le plus proche, mais **pas d'agents** et pas de couche décisionnelle |
| There's An AI For That | Outils IA (90M users) | Zéro MCP, zéro skills |
| AI Agents Directory | Agents (1 300+) | Zéro MCP, zéro skills, pas de logique pont |

**Le graphe `agent ↔ skill ↔ MCP ↔ outil ↔ automatisation` n'existe nulle part.** C'est la case vide que YggNexus occupe.

---

## 3. Mise à jour stratégique

### Positionnement élargi (toujours « le pont »)

YggNexus passe de « catalogue d'outils IA » à **« la couche de découverte de tout l'écosystème agentic »** : outils, agents, skills, connecteurs MCP — reliés entre eux. On ne devient pas une plateforme d'hébergement (ça resterait hors principe). On reste la carte et le mode d'emploi.

### Impact sur le Flywheel

Le moteur **Content Machine** gagne 3 nouvelles sources de contenu quasi infinies et structurées (registres avec API). Le moteur **Compounding Reinvest** prend tout son sens : le graphe pont est l'actif qui compose — chaque nouvelle entrée enrichit les liens des autres.

### Delta SWOT

- **Force ajoutée :** position de pont unique (le seul à relier les 3 verticales) + sources à API publique (registre MCP officiel) faciles à ingérer.
- **Opportunité ajoutée :** explosion MCP/agents (3-4×/6 mois) = flux de contenu structuré gratuit, exactement ce que les AI Overviews récompensent.
- **Menace ajoutée :** ressentiment dev contre les agrégateurs (« The Great MCP Aggregation Heist »), risques de licence/attribution, pénalités SEO de contenu dupliqué. Mitigations en §6.

---

## 4. Modèle de données (Supabase)

Principe : un **modèle canonique YggNexus** dans lequel on mappe chaque format source (registre MCP officiel, SKILL.md, agent-card.json…). On ne se lie à aucun schéma externe.

### Nouvelles tables (calquées sur `tools`)

- `agents` — slug, name, description, author, url, repo_url, stars, framework, pricing, license, quality_score, embedding(768).
- `skills` — slug, name, description, author, repo_url, license, compatibility[], allowed_tools[], source_format ('skill_md'), quality_score, embedding(768).
- `mcp_servers` — slug, name (canonique `io.github.owner/server`), description, author, repo_url, registry_source, package_type (npm/pypi/docker), transport (stdio/http/sse), capabilities[], hosting (local/remote), stars, weekly_downloads, license, quality_score, embedding(768).

### La table pont (le graphe)

- `bridges` — `source_type`, `source_id`, `target_type`, `target_id`, `relation` (ex: `requires`, `connects_to`, `wraps`, `alternative_of`), `weight`, `evidence` (d'où vient le lien : README, allowed-tools, embedding). C'est l'objet différenciateur. Générique → scale à toutes les combinaisons.

### Réutilisation

- `categories` : ajouter un discriminant `resource_type` pour partager la taxonomie entre les 4 types.
- `embeddings` : déjà en place → liens sémantiques cross-type gratuits.

---

## 5. Pipeline de collecte (le Prisme)

| Verticale | Sources d'ingestion | Méthode |
| --- | --- | --- |
| MCP | Registre officiel `registry.modelcontextprotocol.io/v0/servers` (cursor) → enrichi par scrape Glama (catégories+scores) → GitHub Search `topic:mcp-server` (stars/licence) → npm/PyPI (downloads réels) → seed `awesome-mcp-servers` | API publique en primaire, scrape en complément |
| Agents | GitHub Search `topic:ai-agents` → `awesome-ai-agents` (markdown) → Hugging Face Spaces API → aiagentsdirectory (scrape) | API GitHub + parse markdown |
| Skills | GitHub code search `filename:SKILL.md` (parse frontmatter YAML) → agentskill.club → `agentskills.io/llms.txt` | Parse frontmatter |

Étapes Prisme (réutilise l'existant B1→B5) :

1. **B1 collecte** — un collecteur par source, normalisé vers le modèle canonique.
2. **B2 enrichissement** — qwen + embeddings, **+ couche éditoriale originale** (« pourquoi ce serveur, dans quel workflow, avec quels agents ») — résout à la fois la valeur et le risque SEO.
3. **B3 dedup** — *critique pour MCP* : le même serveur existe sur 5 registres. Dédup par repo_url + nom canonique + cosinus.
4. **B4 classification** — taxonomie unifiée (resource_type + catégorie).
5. **B5 liens / graphe pont** — construit la table `bridges` : signaux explicites (README → SaaS sous-jacent ; `allowed-tools` d'un SKILL.md → MCP ; deps d'un agent → frameworks) **+** similarité cosinus pour les liens implicites.

---

## 6. Frontend (Next.js, i18n EN/FR)

Nouvelles routes (même patron que `tools`) :

- `/[locale]/agents` + `/agents/[slug]`
- `/[locale]/skills` + `/skills/[slug]`
- `/[locale]/mcp` + `/mcp/[slug]`
- Vues pont : sur une fiche agent → « skills requis + MCP nécessaires + outils sous-jacents » ; sur une fiche MCP → « à utiliser avec ces agents/skills ».
- Reprendre `best/[category]`, `compare/[pair]`, `alternatives` par type.
- Maillage interne knowledge-graph (puissant pour SEO + AI Overviews).

**Sur chaque fiche, non négociable (mitigation légale) :** licence source affichée en évidence + lien profond vers le repo original en élément de premier plan, jamais en note de bas de page.

---

## 7. Monétisation par verticale

- **Affiliation sur le SaaS sous-jacent** (le vrai filon) : la plupart des MCP/skills wrappent une API payante — Exa, Tavily, Firecrawl, Bright Data, Stripe, OpenRouter, E2B… programmes affiliés établis (10-30 %, souvent récurrents).
- **Listings sponsorisés / featured** sur les pages catégories (modèle prouvé chez mcp.so, aiagentsdirectory).
- **Newsletter** (digest hebdo agents/MCP, modèle PulseMCP) → sponsorships une fois l'audience établie.
- **Badge « YggNexus Verified »** (revue accélérée payante) plus tard.
- *Hors principe pour l'instant :* hébergement managé (Glama/Smithery le font) — ce serait quitter le rôle de pont.

---

## 8. Risques et mitigations

| Risque | Mitigation |
| --- | --- |
| Licences / attribution (~70 % des repos sans licence claire ; précédent Doe v. GitHub) | Afficher la licence + lien source en premier plan, jamais retirer les attributions |
| Contenu dupliqué (READMEs verbatim → pénalité Google) | Couche éditoriale originale sur chaque fiche (= l'angle pont, résout les deux d'un coup) |
| Backlash dev contre les agrégateurs | Attribution explicite, lien retour, soumission directe des créateurs en voie principale, scrape en complément |
| Dépendance aux registres tiers (ToS, rate limits) | Registre officiel MCP (API publique) en source primaire + partenariats/soumissions directes |
| Fragmentation des standards (SKILL.md vs OpenAI vs Google) | Modèle canonique YggNexus, mapping depuis chaque format — aucun couplage |

---

## 9. Séquence recommandée (par où commencer)

1. **MCP servers en premier** : c'est la verticale la plus structurée (API publique officielle, scores Glama, dédup faisable), la plus en croissance, et la plus alignée avec « le pont ».
2. **Skills ensuite** : SKILL.md est parseable proprement, volume curé raisonnable.
3. **Agents en dernier** : le plus fragmenté, mais c'est le sommet du graphe (un agent tire skills + MCP + outils) — donc l'ajouter ferme la boucle du pont.

> Tout ça reste branché au Swimlane : chaque verticale = des projets rattachés au moteur Content Machine, trimestrialisés.

---

*Source de la recherche : registre officiel MCP, Glama, Smithery, mcp.so, awesome-mcp-servers, awesome-ai-agents, agentskill.club, agensi.io, theresanaiforthat, aiagentsdirectory, docs MCP — consultés en juin 2026. Détails et URLs dans le rapport de recherche associé.*
