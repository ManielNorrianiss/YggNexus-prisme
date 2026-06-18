# Asset foundation — "The Solo Builder OS"
### Concept + English data schema (tools ↔ automations graph)

> Marché : anglophone d'abord (contenu, marque, SEO 100 % en anglais), version FR défensive plus tard.
> Pilotage : moteur Prisme (collecte + enrichissement en local la nuit, cloud léger pour l'infolettre, humain pour les décisions).
> Fondation regénérable. Lié au plan : `D:\Emperor\Plan_actifs_numeriques_12mois.docx`.

---

## 1. Le concept en une phrase

A searchable database where every **tool** a solo builder needs is connected to the ready-made **automations** that use it — and vice versa. The graph between the two *is* the moat.

Personne ne relie les deux aujourd'hui : les annuaires d'outils ignorent les automatisations, les annuaires d'automatisations ignorent les outils. Ce lien, c'est ta donnée propriétaire (même logique que Mycelium : la valeur est dans les connexions, pas dans la liste).

## 2. Positionnement (working brand angle, EN)

- **Promise:** "Stop researching tools. Find the stack *and* the automation, ready to copy."
- **Audience:** solo founders, indie hackers, no-code builders, small agencies (English-speaking).
- **Tone:** practical, no-hype, builder-to-builder, faceless brand.
- **Name direction** (à valider en Phase 0, anonyme, .com dispo) : type "StackForge", "SoloStack", "BuilderGraph", "StackRecipes", "WireUp". → on tranchera avec dispo de domaine.

## 3. Monétisation (rappel)

Recurring SaaS affiliation (n8n 30% recurring, Cursor, Lovable, Supabase, Resend…) · newsletter sponsorships · later: a self-serve paid tool. Same audience, same affiliate pool for both faces.

---

## 4. Data schema — table A : TOOLS

Chaque outil du catalogue. Noms de champs en anglais (= colonnes réelles du produit).

| Field | Type | Description (FR) | Example |
|---|---|---|---|
| `name` | text | nom de l'outil | "n8n" |
| `slug` | text | id URL unique | "n8n" |
| `category` | enum | famille principale | "Automation" |
| `subcategory` | enum | sous-famille | "Workflow engine" |
| `one_liner` | text | ce que ça fait, 1 phrase | "Self-hostable workflow automation." |
| `best_for_stage` | enum | étape projet | idea · MVP · launch · scale |
| `pricing_model` | enum | modèle | free · freemium · paid |
| `starting_price_usd` | number | prix d'entrée /mo | 0 |
| `has_free_tier` | bool | offre gratuite? | true |
| `affiliate` | bool | programme d'affiliation? | true |
| `affiliate_terms` | text | conditions | "30% recurring, 12 months" |
| `affiliate_url` | link | ton lien tracké | … |
| `our_rating` | number 1-5 | ta note éditoriale | 5 |
| `popularity_signal` | text | preuve sociale | "149k GitHub stars" |
| `linked_automations` | relation → AUTOMATIONS | recettes qui l'utilisent | [r1, r2…] |
| `tags` | multi | filtres libres | ["open-source","dev"] |
| `last_verified` | date | dernière vérif | 2026-06-15 |
| `source_url` | link | source de la donnée | … |

**Catégories de départ (EN) :** AI Coding · Hosting & Database · Email & Comms · Payments & Billing · Automation · Analytics · Design & Assets · No-code Builder · AI Agents · Marketing & SEO.

## 5. Data schema — table B : AUTOMATIONS

Chaque recette d'automatisation, classée par **résultat business**.

| Field | Type | Description (FR) | Example |
|---|---|---|---|
| `title` | text | titre orienté résultat | "Auto-send weekly SEO report to clients" |
| `slug` | text | id URL | "weekly-seo-report" |
| `outcome` | text | le résultat concret livré | "Clients get a branded report every Monday, zero manual work." |
| `target_persona` | enum | pour qui | solo founder · agency · ecommerce · creator |
| `platform` | enum | plateforme | n8n · Make · Zapier |
| `difficulty` | number 1-5 | niveau technique | 2 |
| `tools_required` | relation → TOOLS | outils nécessaires | [n8n, Google Sheets, Resend] |
| `trigger` | text | déclencheur | "Every Monday 8am" |
| `steps_summary` | long text | résumé des étapes | "Pull data → format → email" |
| `template_url` | link | gabarit / JSON | … |
| `our_rating` | number 1-5 | ta note | 4 |
| `tags` | multi | filtres | ["reporting","agency"] |
| `last_verified` | date | dernière vérif | 2026-06-15 |
| `source_url` | link | source | … |

## 6. Le graphe (le cœur défensif)

`TOOLS.linked_automations` ⇄ `AUTOMATIONS.tools_required` = relation bidirectionnelle.

Résultat côté visiteur :
- Sur une fiche **outil** → "12 ready-made automations using n8n" (et chaque clic = un lien d'affiliation potentiel vers les autres outils requis).
- Sur une fiche **automation** → "Tools you need: n8n + Resend + Google Sheets" (chaque outil = lien d'affiliation).

Chaque page se vend l'autre. C'est ça qui fait que le trafic circule et que les commissions s'empilent.

---

## 7. Comment Prisme alimente ce schéma (rappel opérationnel)

| Tâche récurrente | Niveau | Où dans Prisme |
|---|---|---|
| Collecte nouveaux outils + nouveaux templates n8n/Make | 1 | fetch externe → file `thralls\jobs\` |
| Remplir/enrichir les champs (category, one_liner, best_for, tags) | 1 | thralls 7b local, `batch_nuit` (nuit, gratuit) |
| Déduire les liens outils↔automatisations | 1-2 | classement local 7b/14b |
| Brouillons d'éditions d'infolettre | 2 | Synapse → Haiku |
| Décisions (priorités, repositionnement, version FR) | 3 | session humaine / Opus |
| Suivi catalogue + revenus | — | boards Monday déjà montés |
| Mémoire/recherche du catalogue | — | Mycelium (ponté à Prisme) |

~80 % de l'entretien tourne en local, la nuit, à coût nul.

---

## 8. Prochaines décisions (Phase 0 — débloque tout)

1. Choisir le **nom de marque anglais** + vérifier domaine `.com` dispo.
2. Créer le **courriel dédié** de la marque (anonyme).
3. Ouvrir le compte **beehiiv** (infolettre).
4. Choisir le **stack technique** de l'annuaire (base de données + frontend) — recommandation à venir.

Une fois ces 4 points faits, Prisme peut commencer à remplir le catalogue.
