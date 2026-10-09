# Plan référencement YggNexus — visibilité mondiale

*Créé le 2026-07-01. Objectif : faire voir yggnexus.com partout où son public cherche. Exécution maximale par Prisme (Ollama local, qwen2.5:7b + nomic-embed-text) ; le manuel restant est marqué `[JOSUÉ]`.*

*Réalité assumée : l'organique prend 2-4 mois. Ce qu'on contrôle dès aujourd'hui : indexation, annuaires, volume de pages classables.*

---

## Phase A — Fondations d'indexation (jour 1, ~1 h)

### A1. Google Search Console `[JOSUÉ — 20 min]`

1. https://search.google.com/search-console → Ajouter une propriété → type **Domaine** → `yggnexus.com`
2. Vérification DNS : copier l'enregistrement TXT fourni → GoDaddy → DNS de yggnexus.com → ajouter TXT `@`
3. Une fois vérifié : Sitemaps → soumettre `https://www.yggnexus.com/sitemap.xml`
4. Inspection d'URL → demander l'indexation manuelle des 5 pages clés : accueil, /tools, /categories, /automations, 1 fiche outil

### A2. Bing Webmaster Tools `[JOSUÉ — 5 min]`

1. https://www.bing.com/webmasters → « Importer depuis Google Search Console » (hérite la vérification, zéro DNS)
2. Confirmer le sitemap importé

### A3. IndexNow `[PRISME — automatisable à 100 %]`

Indexation instantanée Bing/Yandex/Seznam à chaque publication, branchée sur le pipeline existant.

- **Nouveau module** : `prisme/indexnow.py`
- Générer une clé (32 hex aléatoires) → la déposer en `frontend/public/{clé}.txt` (contenu = la clé) → commit/deploy une fois
- Après chaque `publish.py` réussi : POST `https://api.indexnow.org/indexnow` avec JSON `{host, key, keyLocation, urlList}` — les URLs des outils publiés/modifiés (hôte canonique `www.yggnexus.com`, piège 308 connu)
- Intégrer comme étape 9 de `run_nightly.py` (non critique, même patron que b3/b4/b5)
- Pièges habituels : Python ASCII pur, écrire le .py via shell

### A4. Audit hreflang en/fr `[EMPEROR — 30 min]`

Vérifier que `generateMetadata` émet `alternates.languages` (en, fr, x-default) sur toutes les pages. Si absent : correctif dans `lib/seo.ts`. Sans ça, la moitié du monde (francophone) voit la mauvaise version.

---

## Phase B — Annuaires et lancements (semaines 1-4)

### B1. Kit de soumission `[PRISME — 1 batch]`

- **Nouveau script** : `prisme/b7_submission_kit.py` (ponctuel, pas nocturne)
- qwen génère depuis la mission du site : tagline (60 car.), descriptions 50/150/300 mots (EN), 5 catégories/mots-clés, réponse type « What makes it different » (le pont outils→automatisations→agents/MCP)
- Sortie : `docs/SUBMISSION_KIT.md` + captures d'écran à faire `[JOSUÉ — accueil, /tools filtré, fiche outil]`

### B2. Soumissions prioritaires `[JOSUÉ avec kit — 2-3 par semaine, dans cet ordre]`

| Cible | Pourquoi | Coût |
|:--|:--|:--|
| Product Hunt | Le lancement de référence, pic de trafic + backlink DR91 | gratuit |
| There's An AI For That | Le plus gros annuaire IA (volume de recherche massif) | gratuit/payant |
| AlternativeTo | Backlink solide + trafic « alternatives » durable | gratuit |
| Toolify.ai | Gros annuaire IA, indexe vite | gratuit |
| Futurepedia | Référence annuaire IA | gratuit |
| SaaSHub | Backlink + comparatifs | gratuit |
| Uneed / MicroLaunch | Lancements secondaires faciles | gratuit |
| Show HN (Hacker News) | Si ça prend : pic mondial + backlinks presse | gratuit |
| Reddit r/SideProject, r/artificial | Trafic direct + signaux | gratuit |

Cadence volontairement étalée : un profil de backlinks qui pousse naturellement, pas un mur d'un jour.

### B3. Registre de suivi `[PRISME ou Monday]`

Petit fichier `docs/registre_soumissions.md` : cible, date, statut, URL de la fiche. Rappel hebdo dans le batch nuit pour relancer les soumissions en attente.

---

## Phase C — Machine à contenu SEO `[PRISME — le cœur, 90 % Ollama]`

C'est le levier qui fait sortir un catalogue dans Google : des centaines de pages longue traîne (« best X for Y », « A vs B », « alternatives to Z »).

### C1. B6 — enrichissement SEO par outil (nocturne)

- **Nouveau** : `prisme/b6_seo.py`, étape entre b4 et export dans `run_nightly.py`
- Pour chaque outil publié sans SEO : qwen génère → meta title (55 car.), meta description (150 car.), 4 questions/réponses FAQ (alimente le FAQPage JSON-LD déjà codé), 3 cas d'usage
- Écrit dans la table `page_seo` (existe déjà) ; bilingue EN puis FR (2 passes qwen)
- Débit réaliste : ~40-60 outils/nuit sur le 7b — suffisant

### C2. Peupler les tables vides (préalable à C3)

- `categories` : descriptions 150 mots par catégorie de `data/taxonomy.json` (qwen, 1 batch ponctuel)
- `automations` : démarrer avec 20-30 automatisations n8n/Make réelles reliées aux outils à fort score (script d'amorçage + validation manuelle `[JOSUÉ — 1 h]`)

### C3. Pages comparatives et classements (nocturne, incrémental)

- `compare/[pair]` : sélectionner les paires depuis la table `alternatives` (B5, cosine la plus haute) → qwen rédige 300 mots de comparatif structuré → 5-10 nouvelles paires/nuit
- `best/[category]` : intro 200 mots par catégorie, régénérée quand le classement bouge
- Chaque page rentre au sitemap automatiquement (déjà codé)

### C4. Maillage interne `[EMPEROR — audit ponctuel]`

Vérifier que chaque fiche outil expose 3+ liens internes (alternatives, catégorie, comparatifs). `RelatedLinks` existe — confirmer qu'il est branché partout.

---

## Phase D — Visibilité IA (AI Overviews, ChatGPT, Perplexity)

Là où « tout le monde » cherche de plus en plus.

- `llms.txt` à la racine : plan du site en markdown pour les crawlers LLM `[EMPEROR — 20 min]`
- Le FAQPage JSON-LD de C1 est exactement ce que les AI Overviews citent
- Arme unique : le graphe `agents → skills → MCP → outils → automatisations` (extension verticales déjà planifiée). Personne d'autre n'a ces données croisées — c'est ce qui fait citer YggNexus comme source par les LLM
- Vérifier que robots.txt n'exclut ni GPTBot, ni ClaudeBot, ni PerplexityBot (état actuel : tout est permis, garder ainsi)

---

## Phase E — Mesure et boucle

- **Rapport hebdo** `[PRISME]` : API Search Console (service account) → impressions, clics, pages indexées → dépôt dans `D:\Emperor\inbox\seo_hebdo_AAAA-MM-JJ.md` via le batch nuit du dimanche
- **Jalons réalistes** : 30 j = pages clés indexées + 5 annuaires en ligne ; 60 j = premières impressions longue traîne ; 90 j = clics organiques en croissance continue, sinon on réoriente C3
- Chaque rapport hebdo se termine par 1 action recommandée, pas un mur de chiffres

---

## Ordre d'exécution recommandé

1. A1-A2 `[JOSUÉ, aujourd'hui]` — sans Search Console, on avance à l'aveugle
2. A3 IndexNow + A4 hreflang — premiers modules à coder
3. C2 puis C1 — la machine de contenu démarre pendant que les annuaires se remplissent
4. B1-B2 — kit puis 2-3 soumissions/semaine
5. C3, D, E — croisière

---

*Signature : Emperor. Les scripts Prisme suivent les pièges connus du projet : shell pour écrire les .py, ASCII pur, hôte canonique www, `.limit(1)` au lieu de `.maybe_single()`.*
