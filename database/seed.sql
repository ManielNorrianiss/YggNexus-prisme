-- ============================================================
--  YggNexus.com — Données d'exemple (seed) pour tester le MVP
--  Cible    : exécuter APRÈS schema.sql
--  Usage    : Supabase → SQL Editor → Run  (ou psql -f seed.sql)
--  Idempotent : ON CONFLICT (slug) DO NOTHING ; relations via slug.
--  Contenu  : 4 catégories, 6 outils, 6 tags, 2 automatisations,
--             liaisons + alternatives. Tout en 'published' pour
--             voir les pages s'afficher immédiatement.
--  NB : les embeddings ne sont PAS seedés ici — c'est le Prisme (B2)
--       qui les calcule. Les `alternatives` sont mises à la main
--       pour le test ; en prod c'est B5 qui les génère.
-- ============================================================

BEGIN;

-- ---------- CATEGORIES ----------
INSERT INTO categories (slug, name, description_md, seo_title, seo_description, status) VALUES
  ('ai-writing',     'AI Writing',     'Tools that generate and edit text with AI.',        'Best AI Writing Tools',     'Compare the best AI writing assistants.',     'published'),
  ('automation',     'Automation',     'No-code/low-code automation platforms.',            'Best Automation Tools',     'Connect your apps and automate workflows.',   'published'),
  ('ai-images',      'AI Images',      'Generate and edit images with AI.',                 'Best AI Image Generators',  'Create visuals from text prompts.',           'published'),
  ('data-scraping',  'Data & Scraping','Collect, enrich and structure data.',               'Best Data Tools',           'Scrape, clean and enrich datasets.',          'published'),
  ('productivity',   'Productivity',   'Workspaces and tools to organize work and collaborate.', 'Best Productivity Tools', 'Organize work and collaborate with AI.', 'published'),
  ('no-code',        'No-Code',        'Build apps and workflows without writing code.',         'Best No-Code Tools',      'Build apps and automate without code.',  'published')
ON CONFLICT (slug) DO NOTHING;

-- ---------- TAGS ----------
INSERT INTO tags (slug, name, kind) VALUES
  ('no-code',        'No-Code',          'feature'),
  ('api',            'API',              'feature'),
  ('content-team',   'Content Teams',    'industry'),
  ('solo-founder',   'Solo Founders',    'industry'),
  ('webhooks',       'Webhooks',         'feature'),
  ('free-tier',      'Free Tier',        'feature')
ON CONFLICT (slug) DO NOTHING;

-- ---------- TOOLS ----------
INSERT INTO tools (slug, name, vendor, website_url, pricing, pricing_note, short_desc, description_md, application_category, quality_score, status) VALUES
  ('zapier',     'Zapier',     'Zapier Inc.',  'https://zapier.com',     'freemium', 'Free tier, paid from $19.99/mo', 'Connect 6000+ apps without code.',          'Zapier links your apps and automates repetitive tasks across thousands of integrations.',     'BusinessApplication', 9.2, 'published'),
  ('make',       'Make',       'Celonis',      'https://make.com',       'freemium', 'Free tier, paid from $9/mo',     'Visual automation with advanced logic.',    'Make (ex-Integromat) builds complex visual scenarios with routers, filters and iterators.',   'BusinessApplication', 9.0, 'published'),
  ('n8n',        'n8n',        'n8n GmbH',     'https://n8n.io',         'open_source','Self-host free, cloud from $20/mo','Source-available workflow automation.',     'n8n is a fair-code automation tool you can self-host, with code nodes and 400+ integrations.', 'DeveloperApplication',8.8, 'published'),
  ('jasper',     'Jasper',     'Jasper AI',    'https://jasper.ai',      'paid',     'From $39/mo',                    'AI content platform for marketing teams.',  'Jasper generates on-brand marketing copy, blog posts and campaigns with AI.',                  'BusinessApplication', 8.1, 'published'),
  ('copy-ai',    'Copy.ai',    'Copy.ai',      'https://copy.ai',        'freemium', 'Free tier, paid from $49/mo',    'AI copywriting and GTM workflows.',          'Copy.ai writes marketing copy and automates go-to-market content workflows.',                  'BusinessApplication', 7.9, 'published'),
  ('midjourney', 'Midjourney', 'Midjourney',   'https://midjourney.com', 'paid',     'From $10/mo',                    'Text-to-image generation via Discord/web.',  'Midjourney turns text prompts into high-quality images, known for its artistic style.',        'MultimediaApplication',9.1, 'published')
ON CONFLICT (slug) DO NOTHING;

-- ---------- TOOL_CATEGORIES (primaire + secondaires) ----------
INSERT INTO tool_categories (tool_id, category_id, is_primary)
SELECT t.id, c.id, v.is_primary
FROM (VALUES
  ('zapier','automation', true),
  ('make','automation', true),
  ('n8n','automation', true),
  ('n8n','data-scraping', false),
  ('jasper','ai-writing', true),
  ('copy-ai','ai-writing', true),
  ('midjourney','ai-images', true)
) AS v(tool_slug, cat_slug, is_primary)
JOIN tools t      ON t.slug = v.tool_slug
JOIN categories c ON c.slug = v.cat_slug
ON CONFLICT (tool_id, category_id) DO NOTHING;

-- ---------- TOOL_TAGS ----------
INSERT INTO tool_tags (tool_id, tag_id)
SELECT t.id, g.id
FROM (VALUES
  ('zapier','no-code'),   ('zapier','free-tier'),
  ('make','no-code'),     ('make','webhooks'),
  ('n8n','api'),          ('n8n','webhooks'),
  ('jasper','content-team'),
  ('copy-ai','free-tier'),('copy-ai','content-team'),
  ('midjourney','solo-founder')
) AS v(tool_slug, tag_slug)
JOIN tools t ON t.slug = v.tool_slug
JOIN tags  g ON g.slug = v.tag_slug
ON CONFLICT (tool_id, tag_id) DO NOTHING;

-- ---------- ALTERNATIVES (saisie manuelle pour le test) ----------
INSERT INTO alternatives (tool_id, alternative_id, similarity, reason)
SELECT a.id, b.id, v.sim, v.reason
FROM (VALUES
  ('zapier','make',  0.95, 'Both are no-code automation platforms connecting many apps.'),
  ('zapier','n8n',   0.88, 'n8n is a source-available alternative with self-hosting.'),
  ('make','zapier',  0.95, 'Zapier offers more integrations with a simpler UI.'),
  ('make','n8n',     0.90, 'n8n offers self-hosting and code nodes.'),
  ('n8n','make',     0.90, 'Make is a hosted visual alternative.'),
  ('jasper','copy-ai',0.92,'Both are AI copywriting platforms for marketing.'),
  ('copy-ai','jasper',0.92,'Jasper is a more enterprise-focused alternative.')
) AS v(tool_slug, alt_slug, sim, reason)
JOIN tools a ON a.slug = v.tool_slug
JOIN tools b ON b.slug = v.alt_slug
ON CONFLICT (tool_id, alternative_id) DO NOTHING;

-- ---------- AUTOMATIONS ----------
INSERT INTO automations (slug, title, platform, difficulty, summary, description_md, use_case, estimated_time_min, status) VALUES
  ('sync-airtable-to-notion', 'Sync Airtable to Notion', 'make', 'intermediate',
   'Keep a Notion database in sync with Airtable records.',
   'This automation watches an Airtable base and mirrors new or updated records into a Notion database.',
   'Keep a content calendar in sync across tools.', 15, 'published'),
  ('rss-to-newsletter', 'Turn an RSS feed into a newsletter draft', 'n8n', 'beginner',
   'Collect new RSS items and draft a newsletter automatically.',
   'This automation polls an RSS feed, summarizes new items with AI and prepares a newsletter draft.',
   'Automate a weekly curated newsletter.', 20, 'published')
ON CONFLICT (slug) DO NOTHING;

-- ---------- AUTOMATION_STEPS ----------
INSERT INTO automation_steps (automation_id, step_number, title, body_md, tool_id)
SELECT a.id, v.step_number, v.title, v.body_md, t.id
FROM (VALUES
  ('sync-airtable-to-notion', 1, 'Trigger on new Airtable record', 'Watch the Airtable base for new or updated rows.', 'make'),
  ('sync-airtable-to-notion', 2, 'Map fields to Notion',          'Match each Airtable column to a Notion property.', 'make'),
  ('sync-airtable-to-notion', 3, 'Create or update the Notion page','Upsert the record into the target Notion database.', 'make'),
  ('rss-to-newsletter',       1, 'Poll the RSS feed',             'Fetch the feed every hour and detect new items.', 'n8n'),
  ('rss-to-newsletter',       2, 'Summarize with AI',             'Send each item to an LLM node for a short summary.', 'n8n'),
  ('rss-to-newsletter',       3, 'Build the newsletter draft',    'Assemble summaries into a draft ready to send.', 'n8n')
) AS v(auto_slug, step_number, title, body_md, tool_slug)
JOIN automations a ON a.slug = v.auto_slug
LEFT JOIN tools  t ON t.slug = v.tool_slug
ON CONFLICT (automation_id, step_number) DO NOTHING;

-- ---------- AUTOMATION_TOOLS ----------
INSERT INTO automation_tools (automation_id, tool_id, role)
SELECT a.id, t.id, v.role
FROM (VALUES
  ('sync-airtable-to-notion', 'make', 'trigger'),
  ('rss-to-newsletter',       'n8n',  'trigger')
) AS v(auto_slug, tool_slug, role)
JOIN automations a ON a.slug = v.auto_slug
JOIN tools       t ON t.slug = v.tool_slug
ON CONFLICT (automation_id, tool_id) DO NOTHING;

COMMIT;

-- ============================================================
--  Vérifications rapides après seed :
--    SELECT count(*) FROM tools;            -- attendu : 6
--    SELECT count(*) FROM automations;      -- attendu : 2
--    SELECT t.name, c.name FROM tools t
--      JOIN tool_categories tc ON tc.tool_id=t.id AND tc.is_primary
--      JOIN categories c ON c.id=tc.category_id;
-- ============================================================
