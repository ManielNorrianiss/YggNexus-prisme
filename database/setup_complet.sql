CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

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
    status          TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published','archived')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tools (
    id                   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    slug                 TEXT NOT NULL UNIQUE,
    name                 TEXT NOT NULL,
    vendor               TEXT,
    website_url          TEXT,
    affiliate_url        TEXT,
    logo_url             TEXT,
    pricing              TEXT NOT NULL DEFAULT 'unknown' CHECK (pricing IN ('free','freemium','paid','open_source','unknown')),
    pricing_note         TEXT,
    short_desc           TEXT,
    description_md       TEXT,
    pros_jsonb           JSONB,
    cons_jsonb           JSONB,
    seo_title            TEXT,
    seo_description      TEXT,
    faq_jsonb            JSONB,
    rating_value         NUMERIC(2,1),
    rating_count         INTEGER,
    application_category TEXT,
    source_url           TEXT,
    source_hash          TEXT,
    quality_score        NUMERIC(4,2),
    status               TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published','archived')),
    last_enriched_at     TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tags (
    id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    kind TEXT
);

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
    status             TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published','archived')),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS automation_steps (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    automation_id BIGINT NOT NULL REFERENCES automations(id) ON DELETE CASCADE,
    step_number   INTEGER NOT NULL,
    title         TEXT NOT NULL,
    body_md       TEXT,
    tool_id       BIGINT REFERENCES tools(id),
    UNIQUE (automation_id, step_number)
);

CREATE TABLE IF NOT EXISTS tool_categories (
    tool_id     BIGINT NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
    category_id BIGINT NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    is_primary  BOOLEAN NOT NULL DEFAULT false,
    PRIMARY KEY (tool_id, category_id)
);

CREATE TABLE IF NOT EXISTS tool_tags (
    tool_id BIGINT NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
    tag_id  BIGINT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (tool_id, tag_id)
);

CREATE TABLE IF NOT EXISTS automation_tools (
    automation_id BIGINT NOT NULL REFERENCES automations(id) ON DELETE CASCADE,
    tool_id       BIGINT NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
    role          TEXT,
    PRIMARY KEY (automation_id, tool_id)
);

CREATE TABLE IF NOT EXISTS alternatives (
    tool_id        BIGINT NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
    alternative_id BIGINT NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
    similarity     NUMERIC(4,3),
    reason         TEXT,
    PRIMARY KEY (tool_id, alternative_id),
    CHECK (tool_id <> alternative_id)
);

CREATE TABLE IF NOT EXISTS changelog (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_type  TEXT NOT NULL CHECK (entity_type IN ('tool','category','automation')),
    entity_id    BIGINT NOT NULL,
    action       TEXT NOT NULL,
    diff_jsonb   JSONB,
    batch_run_id TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS embeddings (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_type  TEXT NOT NULL CHECK (entity_type IN ('tool','category','automation')),
    entity_id    BIGINT NOT NULL,
    model        TEXT NOT NULL,
    embedding    vector(1536) NOT NULL,
    content_hash TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (entity_type, entity_id, model)
);

CREATE INDEX IF NOT EXISTS idx_tools_status ON tools(status);
CREATE INDEX IF NOT EXISTS idx_tools_updated_at ON tools(updated_at);
CREATE INDEX IF NOT EXISTS idx_tools_name_trgm ON tools USING gin (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_categories_parent ON categories(parent_id);
CREATE INDEX IF NOT EXISTS idx_toolcat_category ON tool_categories(category_id);
CREATE INDEX IF NOT EXISTS idx_autotools_tool ON automation_tools(tool_id);
CREATE INDEX IF NOT EXISTS idx_steps_automation ON automation_steps(automation_id);
CREATE INDEX IF NOT EXISTS idx_alt_tool ON alternatives(tool_id);
CREATE INDEX IF NOT EXISTS idx_changelog_entity ON changelog(entity_type, entity_id);

INSERT INTO categories (slug, name, description_md, seo_title, seo_description, status) VALUES
  ('ai-writing',    'AI Writing',     'Tools that generate and edit text with AI.', 'Best AI Writing Tools',    'Compare the best AI writing assistants.',   'published'),
  ('automation',    'Automation',     'No-code and low-code automation platforms.', 'Best Automation Tools',    'Connect your apps and automate workflows.', 'published'),
  ('ai-images',     'AI Images',      'Generate and edit images with AI.',          'Best AI Image Generators', 'Create visuals from text prompts.',         'published'),
  ('ai-audio',      'AI Audio',       'Generate voice, speech and music with AI.',  'Best AI Audio Tools',      'AI voice, speech and music generators.',    'published'),
  ('data-scraping', 'Data & Scraping','Collect, enrich and structure data.',        'Best Data Tools',          'Scrape, clean and enrich datasets.',        'published'),
  ('productivity',  'Productivity',   'Workspaces and tools to organize work and collaborate.', 'Best Productivity Tools', 'Organize work and collaborate with AI.', 'published'),
  ('no-code',       'No-Code',        'Build apps and workflows without writing code.',         'Best No-Code Tools',      'Build apps and automate without code.',  'published')
ON CONFLICT (slug) DO NOTHING;

INSERT INTO tags (slug, name, kind) VALUES
  ('no-code',      'No-Code',       'feature'),
  ('api',          'API',           'feature'),
  ('content-team', 'Content Teams', 'industry'),
  ('solo-founder', 'Solo Founders', 'industry'),
  ('webhooks',     'Webhooks',      'feature'),
  ('free-tier',    'Free Tier',     'feature')
ON CONFLICT (slug) DO NOTHING;

INSERT INTO tools (slug, name, vendor, website_url, pricing, pricing_note, short_desc, description_md, application_category, quality_score, status) VALUES
  ('zapier',     'Zapier',     'Zapier Inc.', 'https://zapier.com',     'freemium',    'Free tier, paid from 19.99/mo',    'Connect 6000+ apps without code.',         'Zapier links your apps and automates repetitive tasks across thousands of integrations.', 'BusinessApplication',  9.2, 'published'),
  ('make',       'Make',       'Celonis',     'https://make.com',       'freemium',    'Free tier, paid from 9/mo',        'Visual automation with advanced logic.',   'Make builds complex visual scenarios with routers, filters and iterators.',               'BusinessApplication',  9.0, 'published'),
  ('n8n',        'n8n',        'n8n GmbH',    'https://n8n.io',         'open_source', 'Self-host free, cloud from 20/mo', 'Source-available workflow automation.',    'n8n is a fair-code automation tool you can self-host, with code nodes and 400+ integrations.', 'DeveloperApplication', 8.8, 'published'),
  ('jasper',     'Jasper',     'Jasper AI',   'https://jasper.ai',      'paid',        'From 39/mo',                       'AI content platform for marketing teams.', 'Jasper generates on-brand marketing copy, blog posts and campaigns with AI.',             'BusinessApplication',  8.1, 'published'),
  ('copy-ai',    'Copy.ai',    'Copy.ai',     'https://copy.ai',        'freemium',    'Free tier, paid from 49/mo',       'AI copywriting and GTM workflows.',        'Copy.ai writes marketing copy and automates go-to-market content workflows.',             'BusinessApplication',  7.9, 'published'),
  ('midjourney', 'Midjourney', 'Midjourney',  'https://midjourney.com', 'paid',        'From 10/mo',                       'Text-to-image generation.',                'Midjourney turns text prompts into high-quality images, known for its artistic style.',   'MultimediaApplication',9.1, 'published')
ON CONFLICT (slug) DO NOTHING;

INSERT INTO tool_categories (tool_id, category_id, is_primary)
SELECT t.id, c.id, v.is_primary
FROM (VALUES
  ('zapier','automation', true),
  ('make','automation', true),
  ('n8n','automation', true),
  ('jasper','ai-writing', true),
  ('copy-ai','ai-writing', true),
  ('midjourney','ai-images', true)
) AS v(tool_slug, cat_slug, is_primary)
JOIN tools t ON t.slug = v.tool_slug
JOIN categories c ON c.slug = v.cat_slug
ON CONFLICT (tool_id, category_id) DO NOTHING;

INSERT INTO tool_tags (tool_id, tag_id)
SELECT t.id, g.id
FROM (VALUES
  ('zapier','no-code'),
  ('zapier','free-tier'),
  ('make','no-code'),
  ('make','webhooks'),
  ('n8n','api'),
  ('n8n','webhooks'),
  ('jasper','content-team'),
  ('copy-ai','free-tier'),
  ('copy-ai','content-team'),
  ('midjourney','solo-founder')
) AS v(tool_slug, tag_slug)
JOIN tools t ON t.slug = v.tool_slug
JOIN tags g ON g.slug = v.tag_slug
ON CONFLICT (tool_id, tag_id) DO NOTHING;

INSERT INTO alternatives (tool_id, alternative_id, similarity, reason)
SELECT a.id, b.id, v.sim, v.reason
FROM (VALUES
  ('zapier','make',   0.95, 'Both are no-code automation platforms connecting many apps.'),
  ('zapier','n8n',    0.88, 'n8n is a source-available alternative with self-hosting.'),
  ('make','zapier',   0.95, 'Zapier offers more integrations with a simpler interface.'),
  ('make','n8n',      0.90, 'n8n offers self-hosting and code nodes.'),
  ('n8n','make',      0.90, 'Make is a hosted visual alternative.'),
  ('jasper','copy-ai',0.92, 'Both are AI copywriting platforms for marketing.'),
  ('copy-ai','jasper',0.92, 'Jasper is a more enterprise-focused alternative.')
) AS v(tool_slug, alt_slug, sim, reason)
JOIN tools a ON a.slug = v.tool_slug
JOIN tools b ON b.slug = v.alt_slug
ON CONFLICT (tool_id, alternative_id) DO NOTHING;

INSERT INTO automations (slug, title, platform, difficulty, summary, description_md, use_case, estimated_time_min, status) VALUES
  ('sync-airtable-to-notion', 'Sync Airtable to Notion', 'make', 'intermediate', 'Keep a Notion database in sync with Airtable records.', 'This automation watches an Airtable base and mirrors new or updated records into a Notion database.', 'Keep a content calendar in sync across tools.', 15, 'published'),
  ('rss-to-newsletter', 'Turn an RSS feed into a newsletter draft', 'n8n', 'beginner', 'Collect new RSS items and draft a newsletter automatically.', 'This automation polls an RSS feed, summarizes new items with AI and prepares a newsletter draft.', 'Automate a weekly curated newsletter.', 20, 'published')
ON CONFLICT (slug) DO NOTHING;

INSERT INTO automation_steps (automation_id, step_number, title, body_md, tool_id) VALUES
  ((SELECT id FROM automations WHERE slug = $t$sync-airtable-to-notion$t$), 1, $t$Trigger on new Airtable record$t$, $t$Watch the Airtable base for new or updated rows.$t$, (SELECT id FROM tools WHERE slug = $t$make$t$)),
  ((SELECT id FROM automations WHERE slug = $t$sync-airtable-to-notion$t$), 2, $t$Map fields to Notion$t$, $t$Match each Airtable column to a Notion property.$t$, (SELECT id FROM tools WHERE slug = $t$make$t$)),
  ((SELECT id FROM automations WHERE slug = $t$sync-airtable-to-notion$t$), 3, $t$Create or update the Notion page$t$, $t$Upsert the record into the target Notion database.$t$, (SELECT id FROM tools WHERE slug = $t$make$t$)),
  ((SELECT id FROM automations WHERE slug = $t$rss-to-newsletter$t$), 1, $t$Poll the RSS feed$t$, $t$Fetch the feed every hour and detect new items.$t$, (SELECT id FROM tools WHERE slug = $t$n8n$t$)),
  ((SELECT id FROM automations WHERE slug = $t$rss-to-newsletter$t$), 2, $t$Summarize with AI$t$, $t$Send each item to a language model for a short summary.$t$, (SELECT id FROM tools WHERE slug = $t$n8n$t$)),
  ((SELECT id FROM automations WHERE slug = $t$rss-to-newsletter$t$), 3, $t$Build the newsletter draft$t$, $t$Assemble summaries into a draft ready to send.$t$, (SELECT id FROM tools WHERE slug = $t$n8n$t$))
ON CONFLICT (automation_id, step_number) DO NOTHING;

INSERT INTO automation_tools (automation_id, tool_id, role)
SELECT a.id, t.id, v.role
FROM (VALUES
  ('sync-airtable-to-notion', 'make', 'trigger'),
  ('rss-to-newsletter',       'n8n',  'trigger')
) AS v(auto_slug, tool_slug, role)
JOIN automations a ON a.slug = v.auto_slug
JOIN tools t ON t.slug = v.tool_slug
ON CONFLICT (automation_id, tool_id) DO NOTHING;
