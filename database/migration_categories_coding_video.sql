-- migration_categories_coding_video.sql
-- Ajoute les categories ai-coding et ai-video (taxonomie 7 -> 9).
-- Idempotent : ON CONFLICT (slug) DO NOTHING. A coller dans le SQL Editor Supabase.
-- A passer AVANT de relancer b4/sync (publish/sync ignorent une categorie inconnue).

INSERT INTO categories (slug, name, description_md, seo_title, seo_description, status) VALUES
  ('ai-coding', 'AI Coding', 'AI coding assistants, agents and IDEs that write, complete, refactor and debug code.',
   'Best AI Coding Tools', 'Compare the best AI coding assistants, agents and IDEs.', 'published'),
  ('ai-video',  'AI Video',  'Generate and edit video with AI: text-to-video, avatars, clip editing and motion.',
   'Best AI Video Tools', 'Create and edit video from text prompts with AI.', 'published')
ON CONFLICT (slug) DO NOTHING;
