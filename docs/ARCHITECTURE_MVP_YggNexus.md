# Architecture MVP — YggNexus.com

> **Rôle du document** : plan d'architecture technique complet du MVP, rédigé du point de vue d'un CTO/architecte pour un *solo builder*. Priorité absolue : simplicité, maintenabilité, SEO, et préparation au futur moteur de recommandation sémantique.
>
> **Stack retenue** : Next.js (App Router, SSG/ISR) · PostgreSQL + pgvector · Vercel + Supabase · batchs Python locaux (« le Prisme ») · Beehiiv · n8n/Make.
>
> **Principe directeur** : *la solution la plus simple qui peut évoluer*. Aucun composant n'est ajouté tant qu'il n'est pas indispensable au MVP. On évite le sur-engineering.

---

## Table des matières

1. [Architecture globale](#1-architecture-globale)
2. [Modèle de données](#2-modèle-de-données)
3. [Architecture du frontend](#3-architecture-du-frontend)
4. [Architecture SEO](#4-architecture-seo)
5. [Batchs nocturnes (le Prisme)](#5-batchs-nocturnes-le-prisme)
6. [API interne](#6-api-interne)
7. [Définition du MVP](#7-définition-du-mvp)
8. [Roadmap technique](#8-roadmap-technique)
9. [Décisions d'architecture résumées](#9-décisions-darchitecture-résumées-adr)

---

## 1. Architecture globale

### 1.1 Principe : un cerveau local, une vitrine statique

YggNexus repose sur une séparation nette entre **deux mondes** :

- **Le Prisme (local, Python)** : c'est le cerveau. Il collecte, enrichit avec l'IA, déduplique, classe, relie les entités, génère le contenu SEO et calcule les embeddings. Il tourne la nuit sur ta machine. Aucune logique métier lourde ne vit en ligne.
- **La vitrine (Vercel + Supabase)** : statique et passive. Next.js lit la base, génère des pages statiques (SSG) régénérées de façon incrémentale (ISR). Supabase héberge la donnée. C'est juste une « photo publiée » de ce que le Prisme a calculé.

Cette séparation est le choix structurant : **toute la complexité reste sur ta machine**, là où c'est facile à déboguer, gratuit en compute, et sans contrainte de temps d'exécution (contrairement aux serverless functions). La partie en ligne est aussi bête que possible.

### 1.2 Diagramme logique des composants

```
                              ┌──────────────────────────────────────────────┐
                              │            LE PRISME (local, Python)           │
                              │                                                │
   Sources externes          │   ┌──────────┐   ┌──────────┐   ┌──────────┐   │
  ┌────────────────┐         │   │ B1       │   │ B2       │   │ B3       │   │
  │ APIs produits  │────────►│   │ Collecte │──►│ Enrich.  │──►│ Dédup.   │   │
  │ RSS / scraping │         │   │          │   │ IA (LLM) │   │          │   │
  │ listes seed    │         │   └──────────┘   └────┬─────┘   └────┬─────┘   │
  └────────────────┘         │                       │              │         │
                             │   ┌──────────┐   ┌────▼─────┐   ┌────▼─────┐   │
  ┌────────────────┐         │   │ B6       │   │ B5       │   │ B4       │   │
  │ LLM API        │◄───────►│   │ Génér.   │◄──│ Liens    │◄──│ Classif. │   │
  │ (OpenAI/Claude)│         │   │ SEO      │   │ entités  │   │          │   │
  └────────────────┘         │   └────┬─────┘   └──────────┘   └──────────┘   │
                             │        │                                        │
  ┌────────────────┐         │   ┌────▼─────┐   ┌──────────┐                   │
  │ Embeddings API │◄───────►│   │ B7       │   │ B8       │                   │
  └────────────────┘         │   │ Publish  │   │ Santé    │                   │
                             │   └────┬─────┘   └──────────┘                   │
                             └────────┼───────────────────────────────────────┘
                                      │ écrit (UPSERT SQL + Storage)
                                      ▼
        ┌───────────────────────────────────────────────────────────┐
        │                    SUPABASE (en ligne)                      │
        │   ┌─────────────────────┐      ┌──────────────────────┐     │
        │   │ PostgreSQL          │      │ Storage (images,      │     │
        │   │  + pgvector         │      │  logos, OG images)    │     │
        │   │  (tables métier)    │      └──────────────────────┘     │
        │   └──────────┬──────────┘                                   │
        │              │ lecture seule (build + ISR)                  │
        └──────────────┼──────────────────────────────────────────────┘
                       │
                       │  webhook revalidation ◄─── B7 déclenche
                       ▼
        ┌───────────────────────────────────────────────────────────┐
        │                  VERCEL — Next.js (App Router)              │
        │   ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐   │
        │   │ Pages SSG    │  │ ISR (revalid.│  │ Route handlers  │   │
        │   │ (tool, cat., │  │ on-demand)   │  │ (sitemap, RSS,  │   │
        │   │  automation) │  │              │  │  API lecture)   │   │
        │   └──────────────┘  └──────────────┘  └─────────────────┘   │
        └───────────────────────────┬───────────────────────────────┘
                                     │
                ┌────────────────────┼────────────────────┐
                ▼                    ▼                     ▼
         ┌────────────┐      ┌──────────────┐      ┌──────────────┐
         │ Utilisateur│      │ Googlebot /  │      │  Beehiiv     │
         │ humain     │      │ AI Overviews │      │ (newsletter) │
         └────────────┘      └──────────────┘      └──────────────┘

   n8n / Make : orchestration légère (déclencheurs, webhooks, envoi Beehiiv,
                notifications) — colle entre les services, pas de logique métier.
```

### 1.3 Flux de données (cycle nominal d'une nuit)

```
  1. Prisme B1  : tire les nouvelles sources  ───────────►  fichiers bruts /exports
  2. Prisme B2-6: enrichit, dédup, classe, relie, rédige ─►  staging local (SQLite ou DataFrame)
  3. Prisme B7  : UPSERT vers Supabase Postgres ──────────►  tables `tools`, `automations`, ...
                  + upload images vers Supabase Storage
                  + POST webhook revalidation vers Vercel
  4. Vercel ISR : régénère uniquement les pages touchées ─►  HTML statique servi au CDN
  5. n8n        : si nouveautés notables ─────────────────►  Beehiiv (newsletter) + log
  6. Prisme B8  : crawl de contrôle (liens, orphelines) ──►  rapport /exports + alerte
```

**Point clé** : la donnée circule dans un seul sens en production — *Prisme → Supabase → Vercel*. Le frontend ne fait **jamais** d'écriture. Cela élimine toute une classe de bugs (concurrence, validation, auth en écriture côté web).

### 1.4 Responsabilités de chaque composant

| Composant | Responsabilité | Ne fait PAS |
|---|---|---|
| **Le Prisme (Python local)** | Tout le travail lourd : collecte, enrichissement IA, dédup, classification, liens, rédaction SEO, embeddings, publication, contrôle qualité | Servir des pages, gérer des utilisateurs |
| **Supabase / Postgres** | Stockage durable des entités, relations, embeddings (pgvector), texte SEO généré | Calculer du contenu, héberger de la logique |
| **Supabase Storage** | Logos, captures, images OG générées | — |
| **Next.js / Vercel** | Rendu SSG/ISR, métadonnées, JSON-LD, sitemap, maillage interne, API lecture seule | Écrire en base, appeler des LLM en direct |
| **n8n / Make** | Orchestration : déclenche les batchs, relaie webhooks, pousse vers Beehiiv, alertes | Logique métier, transformation lourde de données |
| **Beehiiv** | Newsletter, capture d'emails, envoi | — |
| **LLM / Embeddings API** | Génération de texte et de vecteurs, à la demande du Prisme | — |

### 1.5 Recommandation d'architecture (et pourquoi)

> **Recommandé : architecture « cerveau local + vitrine statique », un seul Postgres comme source de vérité publiée.**
>
> **Pourquoi plutôt qu'un back-end Node/Python en ligne ?** Un solo builder n'a pas le temps d'opérer un serveur applicatif 24/7, de gérer la montée en charge, les workers, les files d'attente. En gardant le compute la nuit en local et en ne publiant qu'une *photo statique*, tu obtiens : coût quasi nul en production, débogage facile (tout est sur ta machine), robustesse (un site statique ne tombe pas), et un SEO optimal (HTML pré-rendu, ultra-rapide). L'évolution future (recommandation sémantique) est déjà prévue car pgvector vit dans le même Postgres.

---

## 2. Modèle de données

### 2.1 Vue d'ensemble (diagramme entité-relation)

```
                          ┌─────────────┐
                          │ categories  │
                          └──────┬──────┘
                                 │ 1
                                 │
                          (tool_categories) N..N
                                 │
                                 │ N
      ┌──────────┐         ┌─────▼──────┐         ┌──────────────┐
      │   tags   │ N..N    │   tools    │  N..N   │ alternatives │
      │          ├────────►│            │◄────────┤ (self-ref    │
      └──────────┘         └─────┬──────┘         │  tool↔tool)  │
        (tool_tags)              │                └──────────────┘
                                 │ N
                                 │
                        (automation_tools) N..N
                                 │
                                 │ N
                          ┌──────▼─────────┐
                          │  automations   │
                          └──────┬─────────┘
                                 │ 1
                                 │ N
                          ┌──────▼──────────┐
                          │ automation_steps│
                          └─────────────────┘

   ┌──────────────┐        ┌──────────────┐
   │  embeddings  │        │  changelog   │
   │ (polymorphe: │        │ (audit/SEO   │
   │  tool/cat/   │        │  freshness)  │
   │  automation) │        │              │
   └──────────────┘        └──────────────┘
```

### 2.2 Conventions générales

| Convention | Choix | Justification |
|---|---|---|
| Clé primaire | `BIGINT GENERATED ALWAYS AS IDENTITY` | Simple, rapide en jointure et en index. (UUID seulement si tu crains les collisions multi-source — pas le cas ici.) |
| Identifiant public | `slug TEXT UNIQUE` | Sert d'URL SEO stable, découplé de l'ID interne |
| Horodatage | `created_at`, `updated_at` (TIMESTAMPTZ) | Fraîcheur = signal SEO ; pilote l'ISR |
| Texte long généré | colonnes dédiées (`description_md`, `seo_*`) | Séparer la donnée brute du contenu rédigé par l'IA |
| Statut éditorial | `status` ENUM (`draft`/`published`/`archived`) | Seul `published` est rendu en ligne |
| Soft delete | `archived` via `status` | On ne supprime jamais (historique, redirections) |

### 2.3 Schéma SQL complet

```sql
-- ============================================================
--  EXTENSIONS
-- ============================================================
CREATE EXTENSION IF NOT EXISTS vector;        -- pgvector
CREATE EXTENSION IF NOT EXISTS pg_trgm;        -- recherche floue / dédup par similarité de texte

-- ============================================================
--  TYPES
-- ============================================================
CREATE TYPE content_status AS ENUM ('draft', 'published', 'archived');
CREATE TYPE entity_type    AS ENUM ('tool', 'category', 'automation');
CREATE TYPE pricing_model  AS ENUM ('free', 'freemium', 'paid', 'open_source', 'unknown');

-- ============================================================
--  CATEGORIES
-- ============================================================
CREATE TABLE categories (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    slug            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    parent_id       BIGINT REFERENCES categories(id),   -- arbre de catégories (1 niveau au MVP)
    description_md  TEXT,                                -- intro éditoriale (générée)
    -- champs SEO
    seo_title       TEXT,
    seo_description TEXT,
    seo_intro_md    TEXT,                                -- texte d'en-tête de la page catégorie
    faq_jsonb       JSONB,                               -- [{q, a}] pour FAQ schema
    status          content_status NOT NULL DEFAULT 'draft',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
--  TOOLS  (entité centrale)
-- ============================================================
CREATE TABLE tools (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    slug            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    vendor          TEXT,                                -- éditeur
    website_url     TEXT,
    affiliate_url   TEXT,                                -- monétisation
    logo_url        TEXT,                                -- pointe vers Supabase Storage
    pricing         pricing_model NOT NULL DEFAULT 'unknown',
    pricing_note    TEXT,                                -- "à partir de 19$/mo"
    short_desc      TEXT,                                -- 1 phrase (cartes, méta)
    description_md  TEXT,                                -- description longue (générée IA)
    pros_jsonb      JSONB,                               -- ["...", "..."]
    cons_jsonb      JSONB,
    -- champs SEO / données structurées (SoftwareApplication)
    seo_title       TEXT,
    seo_description TEXT,
    faq_jsonb       JSONB,                               -- FAQ schema
    rating_value    NUMERIC(2,1),                        -- pour AggregateRating (optionnel)
    rating_count    INTEGER,
    application_category TEXT,                            -- ex "BusinessApplication"
    -- gouvernance / fraîcheur
    source_url      TEXT,                                -- d'où vient la donnée brute
    source_hash     TEXT,                                -- détection de changement à la collecte
    quality_score   NUMERIC(4,2),                        -- score interne (complétude, fiabilité)
    status          content_status NOT NULL DEFAULT 'draft',
    last_enriched_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
--  TAGS
-- ============================================================
CREATE TABLE tags (
    id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    slug    TEXT NOT NULL UNIQUE,
    name    TEXT NOT NULL,
    kind    TEXT                                          -- "use_case", "feature", "industry"...
);

-- ============================================================
--  AUTOMATIONS  (recettes n8n/Make reliant des outils)
-- ============================================================
CREATE TABLE automations (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    slug            TEXT NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    platform        TEXT,                                -- "n8n", "make", "both"
    difficulty      TEXT,                                -- "beginner"/"intermediate"/"advanced"
    summary         TEXT,                                -- 1 phrase
    description_md  TEXT,                                -- explication longue (générée)
    use_case        TEXT,
    -- champs SEO
    seo_title       TEXT,
    seo_description TEXT,
    faq_jsonb       JSONB,
    estimated_time_min INTEGER,                           -- pour HowTo schema
    status          content_status NOT NULL DEFAULT 'draft',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
--  AUTOMATION_STEPS  (étapes ordonnées d'une automatisation)
-- ============================================================
CREATE TABLE automation_steps (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    automation_id   BIGINT NOT NULL REFERENCES automations(id) ON DELETE CASCADE,
    step_number     INTEGER NOT NULL,
    title           TEXT NOT NULL,
    body_md         TEXT,                                -- détail de l'étape (généré)
    tool_id         BIGINT REFERENCES tools(id),         -- outil utilisé à cette étape (optionnel)
    UNIQUE (automation_id, step_number)
);

-- ============================================================
--  TABLES DE LIAISON (N..N)
-- ============================================================
CREATE TABLE tool_categories (
    tool_id     BIGINT NOT NULL REFERENCES tools(id)      ON DELETE CASCADE,
    category_id BIGINT NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    is_primary  BOOLEAN NOT NULL DEFAULT false,           -- catégorie canonique (1 par outil)
    PRIMARY KEY (tool_id, category_id)
);

CREATE TABLE tool_tags (
    tool_id BIGINT NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
    tag_id  BIGINT NOT NULL REFERENCES tags(id)  ON DELETE CASCADE,
    PRIMARY KEY (tool_id, tag_id)
);

CREATE TABLE automation_tools (
    automation_id BIGINT NOT NULL REFERENCES automations(id) ON DELETE CASCADE,
    tool_id       BIGINT NOT NULL REFERENCES tools(id)       ON DELETE CASCADE,
    role          TEXT,                                       -- "trigger", "action", "transform"
    PRIMARY KEY (automation_id, tool_id)
);

-- ============================================================
--  ALTERNATIVES  (relation outil ↔ outil, dirigée + score)
-- ============================================================
CREATE TABLE alternatives (
    tool_id         BIGINT NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
    alternative_id  BIGINT NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
    similarity      NUMERIC(4,3),                         -- 0..1 (issu des embeddings)
    reason          TEXT,                                  -- justification générée
    PRIMARY KEY (tool_id, alternative_id),
    CHECK (tool_id <> alternative_id)
);

-- ============================================================
--  CHANGELOG  (audit + fraîcheur, pilote l'ISR et le SEO)
-- ============================================================
CREATE TABLE changelog (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_type entity_type NOT NULL,
    entity_id   BIGINT NOT NULL,
    action      TEXT NOT NULL,                            -- "created","updated","enriched","relinked"
    diff_jsonb  JSONB,                                    -- ce qui a changé
    batch_run_id TEXT,                                    -- id du run nocturne
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
--  EMBEDDINGS  (polymorphe — sémantique et recommandation)
-- ============================================================
CREATE TABLE embeddings (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_type   entity_type NOT NULL,
    entity_id     BIGINT NOT NULL,
    model         TEXT NOT NULL,                          -- "text-embedding-3-small"
    embedding     vector(1536) NOT NULL,                  -- dimension selon le modèle
    content_hash  TEXT,                                   -- évite de recalculer si inchangé
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (entity_type, entity_id, model)
);
```

### 2.4 Index recommandés

| Table | Index | But |
|---|---|---|
| `tools` | `UNIQUE(slug)` (auto) | Résolution d'URL |
| `tools` | `INDEX(status)` | Filtrer `published` au build |
| `tools` | `INDEX(updated_at)` | ISR / pages « récemment mis à jour » |
| `tools` | `GIN(pros_jsonb)`, `GIN(faq_jsonb)` | Requêtes sur JSONB (optionnel MVP) |
| `tools` | `GIN(name gin_trgm_ops)` | Dédup floue + recherche |
| `categories` | `UNIQUE(slug)`, `INDEX(parent_id)` | Navigation arbre |
| `tool_categories` | `INDEX(category_id)` | Lister outils d'une catégorie |
| `automation_tools` | `INDEX(tool_id)` | « automatisations utilisant cet outil » |
| `automation_steps` | `INDEX(automation_id)` | Étapes ordonnées |
| `alternatives` | `INDEX(tool_id)` | Page « Alternatives to X » |
| `changelog` | `INDEX(entity_type, entity_id)`, `INDEX(created_at)` | Audit, fraîcheur |
| `embeddings` | `ivfflat (embedding vector_cosine_ops)` ou `hnsw` | Recherche sémantique ANN |

> **Recommandation pgvector** : au MVP, avec quelques centaines de vecteurs, **un simple scan exact suffit** (pas d'index ANN). Ajoute un index `hnsw` seulement au-delà de ~10 000 vecteurs. `hnsw` > `ivfflat` pour la qualité de rappel, au prix d'un build un peu plus lent — acceptable car calculé la nuit.

### 2.5 Colonnes dédiées au SEO et à la génération de contenu

| Besoin | Colonnes |
|---|---|
| Balises `<title>`/`<meta>` | `seo_title`, `seo_description` |
| Contenu rédactionnel long | `description_md`, `seo_intro_md`, `automation_steps.body_md` |
| FAQ Schema | `faq_jsonb` (sur tools, categories, automations) |
| SoftwareApplication Schema | `pricing`, `pricing_note`, `application_category`, `rating_value`, `rating_count` |
| HowTo Schema (automatisations) | `automation_steps`, `estimated_time_min`, `difficulty` |
| Fraîcheur (signal Google) | `updated_at`, `last_enriched_at`, table `changelog` |
| Maillage interne | `alternatives`, `tool_categories`, `automation_tools`, `tags` |

---

## 3. Architecture du frontend

### 3.1 Structure des dossiers Next.js (App Router)

```
frontend/
├─ app/
│  ├─ layout.tsx                 # layout racine, <head> global, JSON-LD Organization
│  ├─ page.tsx                   # accueil
│  ├─ globals.css
│  │
│  ├─ tools/
│  │  ├─ page.tsx                # index des outils (liste paginée)
│  │  └─ [slug]/
│  │     ├─ page.tsx             # page outil (SSG + ISR)
│  │     └─ opengraph-image.tsx  # image OG générée à la volée
│  │
│  ├─ categories/
│  │  └─ [slug]/page.tsx         # page catégorie
│  │
│  ├─ automations/
│  │  └─ [slug]/page.tsx         # page automatisation (HowTo schema)
│  │
│  ├─ best/
│  │  └─ [slug]/page.tsx         # "Best AI Tools for X" (programmatique)
│  │
│  ├─ compare/
│  │  └─ [slug]/page.tsx         # "X vs Y"  (slug = "toolA-vs-toolB")
│  │
│  ├─ alternatives/
│  │  └─ [slug]/page.tsx         # "Alternatives to X"
│  │
│  ├─ sitemap.ts                 # sitemap dynamique (route handler)
│  ├─ robots.ts                  # robots.txt
│  └─ api/
│     └─ revalidate/route.ts     # webhook ISR on-demand (POST par le Prisme)
│
├─ components/                   # cartes, schema, breadcrumb, maillage interne
│  ├─ ToolCard.tsx
│  ├─ JsonLd.tsx
│  ├─ Breadcrumbs.tsx
│  └─ RelatedLinks.tsx
│
├─ lib/
│  ├─ db.ts                      # client Supabase (lecture seule, clé anon/service au build)
│  ├─ queries.ts                 # toutes les requêtes SQL/PostgREST centralisées
│  ├─ seo.ts                     # helpers métadonnées
│  └─ schema.ts                  # générateurs JSON-LD typés
│
├─ next.config.js
└─ package.json
```

> **Recommandation** : garder **toutes** les requêtes dans `lib/queries.ts`. Un seul endroit qui parle à la base = maintenabilité maximale pour un solo builder. Les pages ne font qu'appeler ces fonctions.

### 3.2 Routes recommandées

| Route | Type de page | Rendu | Volume MVP |
|---|---|---|---|
| `/` | Accueil | SSG | 1 |
| `/tools` | Index outils | SSG + ISR | 1 |
| `/tools/[slug]` | Fiche outil | SSG + ISR | = nb d'outils |
| `/categories/[slug]` | Catégorie | SSG + ISR | = nb de catégories |
| `/automations/[slug]` | Recette d'automatisation | SSG + ISR | = nb d'automatisations |
| `/best/[slug]` | « Best AI Tools for X » | SSG + ISR | = nb de créneaux |
| `/compare/[slug]` | « X vs Y » | SSG + ISR (à la demande) | sous-ensemble curé |
| `/alternatives/[slug]` | « Alternatives to X » | SSG + ISR | = nb d'outils |

### 3.3 SSG vs ISR — stratégie

```
   ┌───────────────────────────────────────────────────────────────┐
   │  Au build (déploiement)                                         │
   │  ─ generateStaticParams() lit tous les slugs `published`        │
   │  ─ Next pré-rend chaque page en HTML statique                   │
   └───────────────────────────────────────────────────────────────┘
                              │
                              ▼
   ┌───────────────────────────────────────────────────────────────┐
   │  En production (entre deux déploiements)                        │
   │  ─ export const revalidate = 86400   // filet de sécurité 24h   │
   │  ─ Le Prisme POST /api/revalidate après chaque nuit             │
   │      → revalidatePath('/tools/[slug]')  (ISR on-demand ciblé)   │
   │  → seules les pages réellement modifiées sont régénérées        │
   └───────────────────────────────────────────────────────────────┘
```

| Mécanisme | Quand | Recommandation |
|---|---|---|
| `generateStaticParams` | Au build | Liste les slugs publiés — pages pré-rendues |
| `revalidate = 86400` | Filet passif | Tout se rafraîchit au pire en 24h |
| **ISR on-demand** (`revalidatePath`) | Push du Prisme | **Méthode principale** : précis, instantané, économe |

> **Recommandation forte** : ne pas tout reconstruire chaque nuit. Le Prisme connaît exactement les entités modifiées (via `changelog`) et n'appelle `/api/revalidate` que pour celles-là. C'est l'approche la plus simple qui passe à l'échelle de milliers de pages sans rallonger le build Vercel.

### 3.4 Gestion des métadonnées

Chaque page exporte `generateMetadata()` qui lit la base et produit `title`, `description`, canonical, OpenGraph et Twitter.

```typescript
// app/tools/[slug]/page.tsx
export async function generateMetadata({ params }): Promise<Metadata> {
  const tool = await getToolBySlug(params.slug);
  return {
    title: tool.seo_title ?? `${tool.name} — Review, Pricing & Alternatives`,
    description: tool.seo_description ?? tool.short_desc,
    alternates: { canonical: `https://yggnexus.com/tools/${tool.slug}` },
    openGraph: {
      title: tool.seo_title, description: tool.seo_description,
      url: `https://yggnexus.com/tools/${tool.slug}`,
      images: [`/tools/${tool.slug}/opengraph-image`],
      type: 'article',
    },
  };
}
```

### 3.5 JSON-LD et données structurées

Un composant `<JsonLd>` injecte le balisage. Mapping par type de page :

| Page | Schema(s) JSON-LD |
|---|---|
| Fiche outil | `SoftwareApplication` (+ `AggregateRating` si dispo) + `FAQPage` + `BreadcrumbList` |
| Catégorie | `CollectionPage` + `ItemList` + `FAQPage` + `BreadcrumbList` |
| Automatisation | `HowTo` (étapes) + `FAQPage` + `BreadcrumbList` |
| « Best X » | `ItemList` + `FAQPage` + `BreadcrumbList` |
| « X vs Y » | `FAQPage` + `BreadcrumbList` (+ 2× `SoftwareApplication`) |
| Accueil / global | `Organization` + `WebSite` (avec `SearchAction`) |

```typescript
// lib/schema.ts — exemple SoftwareApplication
export function softwareApplicationLd(tool) {
  return {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    "name": tool.name,
    "applicationCategory": tool.application_category ?? "BusinessApplication",
    "operatingSystem": "Web",
    "offers": { "@type": "Offer", "price": tool.pricing === 'free' ? "0" : undefined,
                "priceCurrency": "USD" },
    ...(tool.rating_value && { "aggregateRating": {
        "@type": "AggregateRating",
        "ratingValue": tool.rating_value, "ratingCount": tool.rating_count }}),
  };
}
```

> **Recommandation** : générer le `faq_jsonb` côté Prisme (l'IA rédige 3–5 Q/R par entité) et le restituer **à la fois** dans le HTML visible **et** dans le `FAQPage` JSON-LD. C'est l'angle le plus payant pour les AI Overviews : une question/réponse propre, factuelle, balisée.

---

## 4. Architecture SEO

### 4.1 Structure idéale des URLs

```
https://yggnexus.com/
├─ /tools/{tool-slug}                         ex: /tools/zapier
├─ /categories/{category-slug}                ex: /categories/ai-writing
├─ /automations/{automation-slug}             ex: /automations/sync-airtable-to-notion
├─ /best/{topic-slug}                          ex: /best/ai-tools-for-customer-support
├─ /compare/{toolA}-vs-{toolB}                 ex: /compare/zapier-vs-make
└─ /alternatives/{tool-slug}                  ex: /alternatives/zapier
```

| Règle d'URL | Choix | Pourquoi |
|---|---|---|
| Forme | minuscules, mots séparés par `-`, pas de `_` ni de paramètres | Lisibilité humaine + Google |
| Profondeur | 2 segments max | Plat = mieux crawlé |
| Stabilité | le `slug` ne change jamais après publication | Évite les redirections |
| Pas de date dans l'URL | oui | Permet la mise à jour « evergreen » sans changer l'URL |

### 4.2 Pages générées automatiquement

| Type de page | Gabarit de titre | Source des données | Intention de recherche |
|---|---|---|---|
| **Tool page** | `{Tool} — Review, Pricing & Alternatives (2026)` | `tools` + relations | Navigationnelle / évaluative |
| **Category page** | `Best {Category} Tools` | `categories` + `tool_categories` | Commerciale (liste) |
| **Automation page** | `How to {use_case} (n8n/Make)` | `automations` + `automation_steps` | Transactionnelle / how-to |
| **Best AI Tools for X** | `Best AI Tools for {X} in 2026` | requête sur `tags`/`categories` | Commerciale forte |
| **X vs Y** | `{X} vs {Y}: Which Is Better?` | 2 `tools` + `alternatives` | Comparative (haute intention) |
| **Alternatives to X** | `Top {N} Alternatives to {X}` | `alternatives` (embeddings) | Comparative / substitution |

> **Recommandation de priorité SEO** : pour un nouveau site, les pages **« X vs Y »** et **« Alternatives to X »** captent l'intention la plus chaude et la moins concurrentielle au début. Génère-les en priorité, mais **seulement** quand les deux outils ont une fiche riche (sinon contenu mince = pénalité). Garde un seuil de qualité (`quality_score`) avant publication.

### 4.3 Maillage interne automatique

```
   Une fiche outil (/tools/zapier) lie automatiquement vers :
   ┌──────────────────────────────────────────────────────────┐
   │ ▸ ses catégories          → /categories/...               │
   │ ▸ ses alternatives        → /alternatives/zapier + fiches  │
   │ ▸ comparaisons clés       → /compare/zapier-vs-make        │
   │ ▸ automatisations liées   → /automations/... (via          │
   │                              automation_tools)             │
   │ ▸ tags                    → pages /best/... pertinentes     │
   └──────────────────────────────────────────────────────────┘
```

Le maillage n'est **jamais écrit à la main** : un composant `<RelatedLinks>` interroge les tables de liaison et `alternatives` (triées par `similarity`) pour afficher 5–10 liens contextuels par page. Les embeddings garantissent que les liens sont sémantiquement pertinents, pas aléatoires.

| Bloc de liens | Source | Nb de liens cible |
|---|---|---|
| « In these categories » | `tool_categories` | 1–3 |
| « Top alternatives » | `alternatives` (par `similarity`) | 5–8 |
| « Compare with » | `alternatives` → `/compare/` | 2–4 |
| « Used in automations » | `automation_tools` | 3–6 |

### 4.4 Sitemap, robots, canonical

```
  /sitemap.xml          → généré par app/sitemap.ts (lit tous les slugs `published`)
  /sitemap-index.xml    → si > 50 000 URL, segmenter (tools, categories, automations…)
  /robots.txt           → app/robots.ts
  <link rel=canonical>  → généré par generateMetadata (URL absolue, sans paramètre)
```

```typescript
// app/robots.ts
export default function robots() {
  return {
    rules: { userAgent: '*', allow: '/', disallow: ['/api/'] },
    sitemap: 'https://yggnexus.com/sitemap.xml',
    host: 'https://yggnexus.com',
  };
}
```

| Élément | Recommandation |
|---|---|
| **Canonical** | Toujours absolu, une seule URL canonique par contenu. `/compare/a-vs-b` canonique unique (ne pas créer aussi `/compare/b-vs-a` : rediriger 301 vers l'ordre alphabétique). |
| **Sitemap** | Inclure `lastmod` = `updated_at` (signal de fraîcheur). Régénéré à chaque build + ISR. |
| **robots.txt** | Autoriser tout sauf `/api/`. **Ne pas bloquer** les bots IA (GPTBot, ClaudeBot, PerplexityBot) — c'est le cœur de la stratégie AI Overviews. |
| **AI Overviews** | Réponses courtes et factuelles en haut de page, FAQ balisée, tableaux comparatifs HTML lisibles, fraîcheur visible (« Updated June 2026 »). |

### 4.5 Optimisation pour les LLM et AI Overviews (spécifique)

| Levier | Mise en œuvre |
|---|---|
| Réponse directe en tête | Chaque page commence par un paragraphe « TL;DR » de 2–3 phrases répondant à l'intention |
| Données structurées riches | `SoftwareApplication`, `FAQPage`, `HowTo`, `ItemList` systématiques |
| Tableaux comparatifs | HTML `<table>` propre (les LLM les parsent très bien) — pas d'images |
| Fraîcheur explicite | « Last updated: {date} » visible + `lastmod` sitemap + `dateModified` dans le schema |
| Entités nommées claires | Noms d'outils, vendeurs, prix en texte brut, pas dans des images |
| Pas de JS pour le contenu | SSG = contenu dans le HTML, accessible aux bots qui n'exécutent pas JS |

---

## 5. Batchs nocturnes (le Prisme)

### 5.1 Vue d'ensemble du pipeline

```
  B1 Collecte ─► B2 Enrichissement IA ─► B3 Détection doublons ─► B4 Classification
                                                                        │
  B8 Santé ◄─ B7 Publication ◄─ B6 Génération SEO ◄─ B5 Liens entre entités ◄┘

  Légende : ──► dépendance séquentielle   ║ parallélisable
```

Orchestration recommandée : un script `run_night.py` qui exécute les batchs dans l'ordre, chaque batch étant un module isolé et **idempotent** (rejouable sans dégât). Un `batch_run_id` (timestamp) trace tout dans `changelog`.

> **Recommandation outil d'orchestration** : au MVP, **un simple script Python + cron/Planificateur Windows** suffit. Pas besoin d'Airflow ni de Prefect. n8n sert juste de déclencheur/colle externe (ex. : « quand le run finit, envoie-moi un résumé »). On ajoute Prefect seulement si la reprise sur erreur fine devient un vrai besoin.

### 5.2 Détail par batch

#### B1 — Collecte

| Aspect | Détail |
|---|---|
| **Entrées** | Listes seed (CSV d'outils à suivre), APIs publiques, flux RSS, pages produits (scraping léger et respectueux) |
| **Traitements** | Récupère les données brutes, calcule un `source_hash`, ignore si inchangé (delta only), dépose en `/exports/raw/{date}/` |
| **Sorties** | Fichiers bruts JSON + lignes candidates en staging |
| **Dépendances** | Aucune (point d'entrée) |
| **Parallélisable** | ✅ Oui — une tâche par source (asyncio / pool) |

#### B2 — Enrichissement IA

| Aspect | Détail |
|---|---|
| **Entrées** | Lignes brutes de B1 (uniquement les nouvelles/modifiées) |
| **Traitements** | LLM normalise : `short_desc`, `pros/cons`, `pricing`, `application_category`. Validation par schéma (JSON strict). Calcule les **embeddings** (texte concaténé nom+desc) |
| **Sorties** | Entités enrichies + vecteurs en staging |
| **Dépendances** | B1 |
| **Parallélisable** | ✅ Oui — batché par lots de N appels LLM (respecter le rate limit) |

#### B3 — Détection des doublons

| Aspect | Détail |
|---|---|
| **Entrées** | Entités enrichies (avec embeddings) |
| **Traitements** | Double filtre : (1) similarité de nom via `pg_trgm`, (2) similarité cosinus des embeddings > seuil. Fusionne ou marque pour revue manuelle |
| **Sorties** | Entités dédupliquées (clé canonique par outil) |
| **Dépendances** | B2 (a besoin des embeddings) |
| **Parallélisable** | ⚠️ Partiel — le calcul de similarité oui, la décision de fusion doit être sérialisée |

#### B4 — Classification

| Aspect | Détail |
|---|---|
| **Entrées** | Entités dédupliquées |
| **Traitements** | Assigne catégories (`is_primary`) et tags via LLM + règles. Une catégorie primaire obligatoire |
| **Sorties** | `tool_categories`, `tool_tags` peuplées |
| **Dépendances** | B3 |
| **Parallélisable** | ✅ Oui — par entité |

#### B5 — Création des liens entre entités

| Aspect | Détail |
|---|---|
| **Entrées** | Toutes les entités + embeddings |
| **Traitements** | Calcule les `alternatives` (k plus proches voisins par cosinus, même catégorie), relie `automation_tools`, génère `reason` (LLM) |
| **Sorties** | `alternatives`, `automation_tools` |
| **Dépendances** | B4 (catégories nécessaires pour filtrer les voisins) |
| **Parallélisable** | ✅ Oui — recherche ANN par lot |

#### B6 — Génération SEO

| Aspect | Détail |
|---|---|
| **Entrées** | Entités + liens |
| **Traitements** | LLM rédige `description_md`, `seo_title`, `seo_description`, `faq_jsonb`, intros de catégorie, pages « best/vs/alternatives ». Garde-fous : longueur, ton, factualité, pas de contenu mince |
| **Sorties** | Tous les champs SEO remplis, pages programmatiques en staging |
| **Dépendances** | B5 (le contenu « vs »/« alternatives » a besoin des liens) |
| **Parallélisable** | ✅ Oui — par page |

#### B7 — Publication

| Aspect | Détail |
|---|---|
| **Entrées** | Staging complet validé |
| **Traitements** | `UPSERT` transactionnel vers Supabase, upload images vers Storage, écrit `changelog`, passe `status=published` si `quality_score` ≥ seuil, **POST `/api/revalidate`** avec la liste des chemins modifiés |
| **Sorties** | Base de prod à jour + pages Vercel régénérées (ISR) |
| **Dépendances** | B6 |
| **Parallélisable** | ⚠️ Limité — UPSERT en transaction ; la revalidation peut être batchée |

#### B8 — Vérifications de santé

| Aspect | Détail |
|---|---|
| **Entrées** | Site publié + base |
| **Traitements** | Crawl interne : liens cassés (404/500), pages orphelines (sans lien entrant), entités sans catégorie/embedding, erreurs de schema (validation JSON-LD), dérive de fraîcheur |
| **Sorties** | Rapport `/exports/health/{date}.md` + alerte (n8n → email/Slack) si seuil dépassé |
| **Dépendances** | B7 |
| **Parallélisable** | ✅ Oui — crawl concurrent |

### 5.3 Carte de parallélisation

```
  Temps ──────────────────────────────────────────────────────►

  B1  [■■■■]  (sources en parallèle)
  B2        [■■■■■■]  (lots LLM en parallèle)
  B3                [■■■]  (décision sérialisée)
  B4                     [■■■]  (par entité)
  B5                          [■■■]  (ANN par lot)
  B6                               [■■■■■■]  (par page, gros volume LLM)
  B7                                        [■■]  (transaction)
  B8                                           [■■■]  (crawl concurrent)

  Goulots : B2 et B6 (appels LLM). Optimisation = concurrence contrôlée
            + cache par content_hash (ne ré-enrichir/ré-rédiger que le delta).
```

> **Recommandation coût** : le poste de dépense, c'est le LLM en B2/B6. Le `content_hash` est la pièce maîtresse : tant qu'une source n'a pas changé, on ne rappelle jamais le LLM. En régime permanent, une nuit ne traite que le delta (quelques dizaines d'entités), donc le coût reste marginal.

### 5.4 Structure de code du Prisme

```
prisme/
├─ run_night.py            # orchestrateur (séquence B1→B8, batch_run_id, logs)
├─ config.py               # secrets (.env), seuils, modèles
├─ db.py                   # connexion Supabase (psycopg / SQLAlchemy)
├─ batches/
│  ├─ b1_collect.py
│  ├─ b2_enrich.py
│  ├─ b3_dedup.py
│  ├─ b4_classify.py
│  ├─ b5_link.py
│  ├─ b6_seo.py
│  ├─ b7_publish.py
│  └─ b8_health.py
├─ llm/                    # wrappers LLM + embeddings + retry/rate-limit
├─ staging/                # SQLite local de transit (avant UPSERT prod)
└─ tests/
```

---

## 6. API interne

### 6.1 Principe : presque pas d'API

Le site étant statique, **il n'y a quasiment pas d'API à exposer**. La quasi-totalité des lectures se fait au build/ISR, directement contre Postgres. On n'expose que le strict minimum.

### 6.2 Endpoints recommandés

| Endpoint | Méthode | Accès | Rôle |
|---|---|---|---|
| `/api/revalidate` | POST | **Admin** (secret) | Le Prisme déclenche l'ISR ciblé après publication |
| `/api/search` | GET | Public (lecture) | Recherche site (optionnel MVP — peut être client-side) |
| `/sitemap.xml` | GET | Public | Route handler, pas vraiment une API |
| `/feed.xml` | GET | Public | Flux RSS des nouveautés (utile pour Beehiiv/IA) |

> **Recommandation** : au MVP, **ne construis que `/api/revalidate`**. La recherche peut être faite côté client sur un petit JSON pré-généré, ou reportée. Pas de CRUD en ligne : toute écriture passe par le Prisme via la connexion directe à Supabase.

### 6.3 Lecture seule vs administration

```
  ┌─────────────────────────────────────────────────────────────┐
  │  LECTURE (public)                                             │
  │  ─ Build/ISR : clé `anon` Supabase, RLS en lecture seule      │
  │  ─ Aucune mutation possible depuis le web                     │
  ├─────────────────────────────────────────────────────────────┤
  │  ADMINISTRATION (Prisme uniquement)                           │
  │  ─ Écriture : clé `service_role` Supabase, jamais exposée     │
  │      au client, vit dans le .env local du Prisme              │
  │  ─ /api/revalidate protégé par un header secret partagé       │
  └─────────────────────────────────────────────────────────────┘
```

### 6.4 Authentification

| Surface | Auth | Détail |
|---|---|---|
| Pages publiques | Aucune | Site public |
| `/api/revalidate` | `Authorization: Bearer <REVALIDATE_SECRET>` | Secret en variable d'env Vercel + Prisme |
| Écriture Supabase | `service_role` key | Jamais côté client ; RLS active par défaut |
| Lecture Supabase (build) | `anon` key + politiques RLS lecture | Au cas où une lecture runtime serait nécessaire |

> **Recommandation** : activer Row Level Security sur toutes les tables, n'autoriser que `SELECT` sur les lignes `status='published'` pour la clé `anon`. Le Prisme contourne RLS avec `service_role`. Pas de comptes utilisateurs au MVP.

---

## 7. Définition du MVP

### 7.1 Périmètre publiable v1

| Élément | Cible MVP | Justification |
|---|---|---|
| **Outils** | 50–80 | Assez pour des catégories crédibles et du maillage, pas trop pour la curation manuelle initiale |
| **Catégories** | 8–12 | Couvre les grands usages (writing, images, automation, data…) |
| **Automatisations** | 10–15 | Le différenciateur du site ; qualité > quantité |
| **Tags** | 30–50 | Alimente les pages « best for X » |

### 7.2 Pages minimales à livrer

```
  ✅ Accueil
  ✅ /tools/[slug]            × 50–80
  ✅ /categories/[slug]       × 8–12
  ✅ /automations/[slug]      × 10–15
  ✅ /alternatives/[slug]     × 50–80  (auto, via embeddings)
  ✅ /best/[slug]             × 8–12  (1 par catégorie au départ)
  ⏳ /compare/[a]-vs-[b]      × 10–20  (seulement paires à fort volume + fiches riches)
  ✅ sitemap.xml, robots.txt, JSON-LD partout
```

### 7.3 Fonctionnalités incluses au MVP

| Inclus | Reporté après MVP |
|---|---|
| Pipeline Prisme B1→B8 complet (mais sources limitées) | Sources multiples / scraping avancé |
| SSG + ISR on-demand | Recherche sémantique exposée à l'utilisateur |
| JSON-LD (SoftwareApplication, FAQ, HowTo, ItemList) | Moteur de recommandation personnalisé |
| Maillage interne automatique | Comptes utilisateurs, favoris |
| Embeddings calculés et stockés (mais usage interne : alternatives) | Page de recherche vectorielle publique |
| Capture email Beehiiv + 1 newsletter | Multilingue |
| Health check B8 | Dashboard d'analytics interne |
| Monétisation : liens affiliés (`affiliate_url`) | Espace sponsorisé / annuaire payant |

> **Recommandation** : embeddings **calculés dès le MVP** (peu coûteux, sert déjà aux `alternatives`) mais **non exposés** publiquement. Ainsi le moteur de recommandation sémantique futur n'est qu'une **lecture de données déjà présentes** — pas une refonte. C'est exactement « la solution simple qui peut évoluer ».

---

## 8. Roadmap technique

Découpage en phases de 1 à 2 semaines, du point de vue d'un solo builder. Ordre optimal : **d'abord le tuyau de bout en bout sur peu de données**, ensuite le volume et le raffinement.

### 8.1 Vue Gantt (ASCII)

```
  Phase                              S1   S2   S3   S4   S5   S6   S7   S8
  ─────────────────────────────────────────────────────────────────────
  P0 Fondations (DB + repo)          ███
  P1 Frontend squelette + SSG             ███
  P2 Prisme MVP (B1,B2,B7)                ███  ███
  P3 SEO & données structurées                 ███
  P4 Liens & enrichissement (B3-B6)                 ███  ███
  P5 Santé, sitemap, ISR (B8)                            ███
  P6 Contenu programmatique + lancement                       ███  ███
```

### 8.2 Détail des phases

| Phase | Durée | Livrables | Dépend de |
|---|---|---|---|
| **P0 — Fondations** | 1 sem | Projet Supabase, schéma SQL appliqué, pgvector activé, repo Git, `.env`, connexion Prisme↔DB testée | — |
| **P1 — Frontend squelette** | 1 sem | Next.js App Router, layout, `lib/db` + `lib/queries`, page `/tools/[slug]` en SSG lisant la base, déploiement Vercel | P0 |
| **P2 — Prisme MVP** | 2 sem | B1 (1–2 sources seed), B2 (enrichissement + embeddings), B7 (UPSERT + revalidate). 50 outils en base, visibles en ligne | P0, P1 |
| **P3 — SEO & schema** | 1 sem | `generateMetadata`, JSON-LD (SoftwareApplication, FAQ), canonical, OG images, intro TL;DR | P1, P2 |
| **P4 — Liens & enrichissement** | 2 sem | B3 (dédup), B4 (classification), B5 (alternatives via embeddings), B6 (génération SEO complète + FAQ), maillage interne `<RelatedLinks>` | P2 |
| **P5 — Santé & robustesse** | 1 sem | B8 (liens cassés, orphelines), `sitemap.ts`, `robots.ts`, ISR on-demand fiabilisé, alertes n8n | P2, P4 |
| **P6 — Contenu programmatique & lancement** | 2 sem | Pages `/best`, `/alternatives`, `/compare` curées, automatisations rédigées, Beehiiv branché, 1re newsletter, soumission Search Console | P3, P4, P5 |

### 8.3 Chemin critique et ordre optimal

```
  P0 ──► P1 ──► P2 ──► P4 ──► P6
         └──► P3 ─────────────┘
                P2 ──► P5 ─────┘

  Règle d'or : ne JAMAIS attendre d'avoir 50 outils pour brancher le tuyau.
  En P2, fais circuler 3 outils de bout en bout (collecte → base → page en ligne)
  AVANT de monter en volume. Le tuyau d'abord, le débit ensuite.
```

> **Recommandation de séquençage** : P3 (SEO) peut avancer **en parallèle** de P4 dès que P2 livre des données. Pour un solo builder, ne pas paralléliser plus de deux fronts à la fois. Viser un **site public minimal mais réel dès la fin de P2** (~4 semaines) : 50 outils, pages indexables, sitemap soumis — puis itérer.

---

## 9. Décisions d'architecture résumées (ADR)

| # | Décision | Alternative écartée | Pourquoi |
|---|---|---|---|
| 1 | Compute lourd en local (Prisme) | Back-end serverless/worker en ligne | Coût nul, débogage simple, pas de limite de temps d'exécution |
| 2 | Site statique SSG + ISR on-demand | SSR à chaque requête | Vitesse, SEO, robustesse, économie |
| 3 | Un seul Postgres (Supabase) + pgvector | Base relationnelle + base vectorielle séparée | Une seule source de vérité, moins d'ops, évolution sémantique gratuite |
| 4 | Pas d'API CRUD publique | API REST/GraphQL complète | Inutile pour un catalogue en lecture ; surface d'attaque réduite |
| 5 | ISR ciblé via `changelog` | Rebuild complet chaque nuit | Builds courts, scalable à des milliers de pages |
| 6 | Embeddings dès le MVP, usage interne | Les ajouter plus tard | Évite une refonte ; alimente déjà les `alternatives` |
| 7 | Orchestration = script Python + cron | Airflow/Prefect | Sur-engineering au MVP ; n8n suffit pour la colle externe |
| 8 | `content_hash` pour éviter les appels LLM | Tout ré-enrichir chaque nuit | Maîtrise du coût IA, le poste le plus cher |

---

*Document d'architecture — YggNexus.com · MVP · rédigé pour un solo builder. Source de vérité technique : ce fichier + le schéma SQL de la section 2. À versionner dans `YggNexus/docs/`.*
