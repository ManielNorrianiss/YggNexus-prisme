CREATE TABLE IF NOT EXISTS facets (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    axis       TEXT NOT NULL,
    slug       TEXT NOT NULL,
    name       TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    status     content_status NOT NULL DEFAULT 'published',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (axis, slug)
);

CREATE TABLE IF NOT EXISTS tool_facets (
    tool_id  BIGINT NOT NULL REFERENCES tools(id)  ON DELETE CASCADE,
    facet_id BIGINT NOT NULL REFERENCES facets(id) ON DELETE CASCADE,
    PRIMARY KEY (tool_id, facet_id)
);

ALTER TABLE tags ADD COLUMN IF NOT EXISTS name_fr      TEXT;
ALTER TABLE tags ADD COLUMN IF NOT EXISTS canonical_id BIGINT REFERENCES tags(id);
ALTER TABLE tags ADD COLUMN IF NOT EXISTS tool_count   INTEGER NOT NULL DEFAULT 0;
ALTER TABLE tags ADD COLUMN IF NOT EXISTS status       content_status NOT NULL DEFAULT 'published';

ALTER TABLE tool_tags ADD COLUMN IF NOT EXISTS confidence REAL;

CREATE INDEX IF NOT EXISTS idx_facets_axis      ON facets (axis);
CREATE INDEX IF NOT EXISTS idx_tool_facets_facet ON tool_facets (facet_id);
CREATE INDEX IF NOT EXISTS idx_tags_kind        ON tags (kind);
CREATE INDEX IF NOT EXISTS idx_tags_canonical   ON tags (canonical_id);
CREATE INDEX IF NOT EXISTS idx_tool_tags_tag    ON tool_tags (tag_id);

ALTER TABLE facets ENABLE ROW LEVEL SECURITY;
ALTER TABLE tool_facets ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS public_read_facets ON facets;
CREATE POLICY public_read_facets ON facets FOR SELECT TO anon, authenticated USING (status = 'published');

DROP POLICY IF EXISTS public_read_tool_facets ON tool_facets;
CREATE POLICY public_read_tool_facets ON tool_facets FOR SELECT TO anon, authenticated USING (true);

INSERT INTO facets (axis, slug, name, sort_order) VALUES
  ('modality', 'text',       'Text',             1),
  ('modality', 'image',      'Image',            2),
  ('modality', 'audio',      'Audio',            3),
  ('modality', 'video',      'Video',            4),
  ('modality', 'code',       'Code',             5),
  ('modality', 'data',       'Data',             6),
  ('modality', '3d',         '3D',               7),
  ('modality', 'multimodal', 'Multimodal',       8),
  ('function', 'generate',   'Generate',         1),
  ('function', 'edit',       'Edit & Enhance',   2),
  ('function', 'automate',   'Automate',         3),
  ('function', 'analyze',    'Analyze & Research',4),
  ('function', 'chat',       'Assist & Chat',    5),
  ('function', 'build',      'Build (No-Code)',  6),
  ('audience', 'developers', 'Developers',       1),
  ('audience', 'marketing',  'Marketing',        2),
  ('audience', 'creators',   'Creators',         3),
  ('audience', 'business',   'Business & Ops',   4),
  ('audience', 'research',   'Research & Students',5),
  ('audience', 'general',    'General',          6)
ON CONFLICT (axis, slug) DO NOTHING;
