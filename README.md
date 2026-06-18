# YggNexus.com

Catalogue intelligent reliant outils IA/SaaS et automatisations n8n/Make. Pensé pour le SEO organique, les AI Overviews et un futur moteur de recommandation sémantique. Conçu pour tourner en quasi-autonomie : un système Python local (« le Prisme ») collecte, enrichit et relie les données chaque nuit, puis republie les pages.

> **Modèle mental** : le Prisme (local) **pense** la nuit ; le site (Vercel) est une **photo statique** publiée. La donnée circule dans un seul sens — `Prisme → Supabase → Vercel`.

---

## Arborescence

```
YggNexus/
├─ docs/        Documentation : architecture, concept, plan 12 mois, scoring
├─ prisme/      Batchs Python nocturnes (B1→B8) — le cerveau
├─ database/    Schéma SQL + données d'exemple
├─ frontend/    Application Next.js (App Router, SSG/ISR)
├─ scripts/     Utilitaires (cron, déploiement, maintenance)
├─ exports/     Sorties des batchs (données brutes, rapports santé)
└─ assets/      Logos, images, gabarits OG
```

---

## Documents (`/docs`)

| Fichier | Contenu |
|---|---|
| `ARCHITECTURE_MVP_YggNexus.md` | **Plan d'architecture technique complet** : composants, modèle de données SQL, frontend Next.js, SEO, batchs nocturnes, API, MVP, roadmap. Source de vérité technique. |
| `ASSET_concept_schema_EN.md` | Schéma de concept de l'actif (anglais). |
| `Plan_actifs_numeriques_12mois.docx` | Plan stratégique 12 mois du portefeuille d'actifs numériques. |
| `Grille_scoring_creneaux.xlsx` | Grille de scoring pour évaluer les créneaux. |

---

## Base de données (`/database`)

| Fichier | Rôle |
|---|---|
| `schema.sql` | Schéma complet, idempotent (tables, types, index, trigger `updated_at`, RLS). |
| `seed.sql` | Données d'exemple : 4 catégories, 6 outils, 6 tags, 2 automatisations + liaisons et alternatives. |

Les deux scripts sont validés par le parseur PostgreSQL officiel (libpg_query).

### Tester en local / sur Supabase

1. Crée un projet Supabase (PostgreSQL 15+, pgvector dispo par défaut).
2. Ouvre **SQL Editor → New query**, colle le contenu de `schema.sql`, **Run**.
3. Nouvelle requête, colle `seed.sql`, **Run**.
4. Vérifie :

   ```sql
   SELECT count(*) FROM tools;        -- attendu : 6
   SELECT count(*) FROM automations;  -- attendu : 2
   SELECT t.name, c.name AS categorie
   FROM tools t
   JOIN tool_categories tc ON tc.tool_id = t.id AND tc.is_primary
   JOIN categories c ON c.id = tc.category_id;
   ```

En ligne de commande (si `psql` configuré) :

```bash
psql "$SUPABASE_DB_URL" -f database/schema.sql
psql "$SUPABASE_DB_URL" -f database/seed.sql
```

> **Note** : `seed.sql` met tout en `status='published'` pour que les pages s'affichent tout de suite. Les `embeddings` ne sont pas seedés — c'est le batch B2 du Prisme qui les calcule ; les `alternatives` du seed sont saisies à la main pour le test (en prod, c'est B5 qui les génère).

---

## Pipeline nocturne (le Prisme)

```
B1 Collecte → B2 Enrichissement IA → B3 Dédup → B4 Classification
   → B5 Liens entre entités → B6 Génération SEO → B7 Publication → B8 Santé
```

Chaque batch est isolé et idempotent (rejouable). Détail complet : section 5 de `docs/ARCHITECTURE_MVP_YggNexus.md`.

---

## Stack

| Couche | Techno |
|---|---|
| Frontend | Next.js (App Router, SSG/ISR) sur Vercel |
| Base de données | PostgreSQL + pgvector (Supabase) |
| Batchs | Python local (cron / Planificateur Windows) |
| Newsletter | Beehiiv |
| Orchestration / colle | n8n (et éventuellement Make) |

---

## Statut

- [x] Architecture MVP rédigée
- [x] Schéma SQL + seed (validés syntaxiquement)
- [ ] Projet Supabase créé + schéma appliqué
- [ ] Frontend Next.js squelette (page `/tools/[slug]` en SSG)
- [ ] Prisme MVP (B1, B2, B7) — 50 outils de bout en bout

Roadmap détaillée : section 8 de l'architecture.
