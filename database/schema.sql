-- ============================================================
--  YggNexus.com — Schéma de base de données (MVP)
--  Cible   : PostgreSQL 15+ (Supabase) avec pgvector
--  Usage   : coller dans Supabase → SQL Editor → Run
--            (ou : psql "$SUPABASE_DB_URL" -f schema.sql)
--  Idempotent : CREATE ... IF NOT EXISTS + DO blocks pour les ENUM.
--  Réf     : docs/ARCHITECTURE_MVP_YggNexus.md (section 2)
-- ============================================================

BEGIN;

-- ============================================================
--  EXTENSIONS
-- ============================================================
CREATE EXTENSION IF NOT EXISTS vector;     -- pgvector : recherche sémantique / alternatives
CREATE EXTENSION IF NOT EXISTS pg_trgm;    -- similarité de texte : dédup floue + recherche

-- ============================================================
--  TYPES (ENUM)  — créés seulement s'ils n'existent pas
-- ============================================================
DO $$ BEGIN
    CREATE TYPE content_status AS ENUM ('draft', 'published', 'archived');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE entity_type AS ENUM ('tool', 'category', 'automation');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE pricing_model AS ENUM ('free', 'freemium', 'paid', 'open_source', 'unknown');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ============================================================
--  CATEGORIES
-- ============================================================
CREATE TABLE IF NOT EXISTS categories (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    slug            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    parent_id       BIGINT REFERENCES categories(id),
    description_md  TEXT,
    seo_title       TEXT,
    seo_description TEXT,
    seo_intro_md    TEXT,
    faq_jsonb       JSONB,
    status          content_status NOT NULL DEFAULT 'draft',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
--  TOOLS  (entité centrale)
-- ============================================================
CREATE TABLE IF NOT EXISTS tools (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    slug             TEXT NOT NULL UNIQUE,
    name             TEXT NOT NULL,
    vendor           TEXT,
    website_url      TEXT,
    affiliate_url    TEXT,
    logo_url         TEXT,
    pricing          pricing_model NOT NULL DEFAULT 'unknown',
    pricing_note     TEXT,
    short_desc       TEXT,
    description_md   TEXT,
    pros_jsonb       JSONB,
    cons_jsonb       JSONB,
    seo_title        TEXT,
    seo_description  TEXT,
    faq_jsonb        JSONB,
    rating_value     NUMERIC(2,1),
    rating_count     INTEGER,
    application_category TEXT,
    source_url       TEXT,
    source_hash      TEXT,
    quality_score    NUMERIC(4,2),
    status           content_status NOT NULL DEFAULT 'draft',
    last_enriched_at TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
--  TAGS
-- ============================================================
CREATE TABLE IF NOT EXISTS tags (
    id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    kind TEXT
);

-- ============================================================
--  AUTOMATIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS automations (
    id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    slug               TEXT NOT NULL UNIQUE,
    title              TEXT NOT NULL,
    platform           TEXT,
    difficulty         TEXT,
    summary            TEXT,
    description_md     TEXT,
    use_case           TEXT,
    seo_title          TEXT,
    seo_description    TEXT,
    faq_jsonb          JSONB,
    estimated_time_min INTEGER,
    status             content_status NOT NULL DEFAULT 'draft',
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
--  AUTOMATION_STEPS
-- ============================================================
CREATE TABLE IF NOT EXISTS automation_steps (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    automation_id BIGINT NOT NULL REFERENCES automations(id) ON DELETE CASCADE,
    step_number   INTEGER NOT NULL,
    title         TEXT NOT NULL,
    body_md       TEXT,
    tool_id       BIGINT REFERENCES tools(id),
    UNIQUE (automation_id, step_number)
);

-- ============================================================
--  TABLES DE LIAISON (N..N)
-- ============================================================
CREATE TABLE IF NOT EXISTS tool_categories (
    tool_id     BIGINT NOT NULL REFERENCES tools(id)      ON DELETE CASCADE,
    category_id BIGINT NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    is_primary  BOOLEAN NOT NULL DEFAULT false,
    PRIMARY KEY (tool_id, category_id)
);

CREATE TABLE IF NOT EXISTS tool_tags (
    tool_id BIGINT NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
    tag_id  BIGINT NOT NULL REFERENCES tags(id)  ON DELETE CASCADE,
    PRIMARY KEY (tool_id, tag_id)
);

CREATE TABLE IF NOT EXISTS automation_tools (
    automation_id BIGINT NOT NULL REFERENCES automations(id) ON DELETE CASCADE,
    tool_id       BIGINT NOT NULL REFERENCES tools(id)       ON DELETE CASCADE,
    role          TEXT,
    PRIMARY KEY (automation_id, tool_id)
);

-- ============================================================
--  ALTERNATIVES (outil ↔ outil, dirigée + score de similarité)
-- ============================================================
CREATE TABLE IF NOT EXISTS alternatives (
    tool_id        BIGINT NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
    alternative_id BIGINT NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
    similarity     NUMERIC(4,3),
    reason         TEXT,
    PRIMARY KEY (tool_id, alternative_id),
    CHECK (tool_id <> alternative_id)
);

-- ============================================================
--  CHANGELOG (audit + fraîcheur, pilote l'ISR ciblé)
-- ============================================================
CREATE TABLE IF NOT EXISTS changelog (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_type  entity_type NOT NULL,
    entity_id    BIGINT NOT NULL,
    action       TEXT NOT NULL,
    diff_jsonb   JSONB,
    batch_run_id TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
--  EMBEDDINGS (polymorphe — sémantique et recommandation)
--  NB : dimension 1536 = text-embedding-3-small. Ajuster si autre modèle.
-- ============================================================
CREATE TABLE IF NOT EXISTS embeddings (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_type  entity_type NOT NULL,
    entity_id    BIGINT NOT NULL,
    model        TEXT NOT NULL,
    embedding    vector(1536) NOT NULL,
    content_hash TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (entity_type, entity_id, model)
);

-- ============================================================
--  INDEX
-- ============================================================
-- tools
CREATE INDEX IF NOT EXISTS idx_tools_status      ON tools(status);
CREATE INDEX IF NOT EXISTS idx_tools_updated_at  ON tools(updated_at);
CREATE INDEX IF NOT EXISTS idx_tools_name_trgm   ON tools USING gin (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_tools_faq_gin     ON tools USING gin (faq_jsonb);

-- categories
CREATE INDEX IF NOT EXISTS idx_categories_parent ON categories(parent_id);

-- liaisons / relations
CREATE INDEX IF NOT EXISTS idx_toolcat_category  ON tool_categories(category_id);
CREATE INDEX IF NOT EXISTS idx_autotools_tool    ON automation_tools(tool_id);
CREATE INDEX IF NOT EXISTS idx_steps_automation  ON automation_steps(automation_id);
CREATE INDEX IF NOT EXISTS idx_alt_tool          ON alternatives(tool_id);

-- changelog
CREATE INDEX IF NOT EXISTS idx_changelog_entity  ON changelog(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_changelog_created ON changelog(created_at);

-- embeddings : index ANN inutile sous ~10k vecteurs (scan exact suffit au MVP).
-- À ACTIVER plus tard, quand le volume grandit :
-- CREATE INDEX idx_embeddings_hnsw ON embeddings
--   USING hnsw (embedding vector_cosine_ops);

-- ============================================================
--  TRIGGER : updated_at automatique
-- ============================================================
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['categories','tools','automations'] LOOP
        EXECUTE format(
            'DROP TRIGGER IF EXISTS trg_%1$s_updated_at ON %1$s;
             CREATE TRIGGER trg_%1$s_updated_at BEFORE UPDATE ON %1$s
             FOR EACH ROW EXECUTE FUNCTION set_updated_at();', t);
    END LOOP;
END $$;

-- ============================================================
--  ROW LEVEL SECURITY
--  Lecture publique (clé anon) = uniquement les lignes 'published'.
--  Le Prisme écrit avec la clé service_role qui contourne RLS.
-- ============================================================
ALTER TABLE tools       ENABLE ROW LEVEL SECURITY;
ALTER TABLE categories  ENABLE ROW LEVEL SECURITY;
ALTER TABLE automations ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    CREATE POLICY p_tools_pub ON tools
        FOR SELECT USING (status = 'published');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE POLICY p_categories_pub ON categories
        FOR SELECT USING (status = 'published');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE POLICY p_automations_pub ON automations
        FOR SELECT USING (status = 'published');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

COMMIT;

-- ============================================================
--  FIN — vérification rapide :
--  SELECT table_name FROM information_schema.tables
--  WHERE table_schema = 'public' ORDER BY 1;
-- ============================================================
