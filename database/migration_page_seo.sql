-- ============================================================
--  YggNexus.com — Migration : table page_seo  (B6 phase 2)
--  But   : stocker la prose SEO des pages de regroupement
--          - /compare/<a>-vs-<b>          (page_type='compare')
--          - /tools/<slug>/alternatives   (page_type='alternatives')
--  Cible : PostgreSQL 15+ (Supabase). Idempotent.
--  Usage : Supabase -> SQL Editor -> Run (PAS le terminal noir).
--  Pre-requis : schema.sql deja applique (type content_status + fonction
--               set_updated_at() definie). Cette migration les reutilise.
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS page_seo (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    page_type       TEXT NOT NULL CHECK (page_type IN ('compare', 'alternatives')),
    page_key        TEXT NOT NULL,        -- 'jasper-vs-copy-ai' ou 'jasper'
    intro_md        TEXT,                 -- corps redige (rendu sur la page)
    seo_title       TEXT,
    seo_description TEXT,
    content_hash    TEXT,                 -- pour le cache de regeneration (B6 phase 2)
    status          content_status NOT NULL DEFAULT 'published',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (page_type, page_key)
);

CREATE INDEX IF NOT EXISTS idx_page_seo_lookup ON page_seo(page_type, page_key);

-- updated_at automatique (reutilise la fonction de schema.sql)
DROP TRIGGER IF EXISTS trg_page_seo_updated_at ON page_seo;
CREATE TRIGGER trg_page_seo_updated_at BEFORE UPDATE ON page_seo
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- RLS : la cle anon (frontend) ne lit que les lignes 'published'.
-- Le Prisme ecrit avec la cle service_role qui contourne la RLS.
ALTER TABLE page_seo ENABLE ROW LEVEL SECURITY;
DO $$ BEGIN
    CREATE POLICY p_page_seo_pub ON page_seo
        FOR SELECT USING (status = 'published');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

COMMIT;

-- ============================================================
--  Verification rapide :
--  SELECT page_type, page_key, length(intro_md) AS n
--  FROM page_seo ORDER BY page_type, page_key;
-- ============================================================
