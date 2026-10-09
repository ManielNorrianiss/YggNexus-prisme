$t$
-- Idempotent schema for MCP servers and bridges (YggNexus verticale MCP)
-- Format: dollar-quoting for safety, no comments, no DO/trigger blocks
-- Paste entire file into Supabase SQL editor

-- Create mcp_servers table if not exists
CREATE TABLE IF NOT EXISTS mcp_servers (
  id BIGSERIAL PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  description TEXT,
  author TEXT,
  repo_url TEXT UNIQUE,
  registry_source TEXT,
  package_type TEXT,
  transport TEXT,
  capabilities TEXT[],
  hosting TEXT,
  stars INTEGER DEFAULT 0,
  weekly_downloads INTEGER DEFAULT 0,
  license TEXT,
  quality_score NUMERIC(4,2),
  embedding vector(768),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Create index on slug for fast lookups
CREATE INDEX IF NOT EXISTS idx_mcp_servers_slug ON mcp_servers(slug);

-- Create index on repo_url for deduplication
CREATE INDEX IF NOT EXISTS idx_mcp_servers_repo_url ON mcp_servers(repo_url);

-- Create index on embedding for similarity search
CREATE INDEX IF NOT EXISTS idx_mcp_servers_embedding ON mcp_servers USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Create bridges table (generic graph for all verticales)
CREATE TABLE IF NOT EXISTS bridges (
  id BIGSERIAL PRIMARY KEY,
  source_type TEXT NOT NULL,
  source_id BIGINT NOT NULL,
  target_type TEXT NOT NULL,
  target_id BIGINT NOT NULL,
  relation TEXT NOT NULL,
  weight NUMERIC(4,2) DEFAULT 1.0,
  evidence TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Create composite index for fast lookups by source
CREATE INDEX IF NOT EXISTS idx_bridges_source ON bridges(source_type, source_id);

-- Create composite index for fast lookups by target
CREATE INDEX IF NOT EXISTS idx_bridges_target ON bridges(target_type, target_id);

-- Create index on relation type
CREATE INDEX IF NOT EXISTS idx_bridges_relation ON bridges(relation);

-- Create unique constraint to prevent duplicate bridges
CREATE UNIQUE INDEX IF NOT EXISTS idx_bridges_unique ON bridges(source_type, source_id, target_type, target_id, relation);

-- Grant permissions (adjust role names as needed)
ALTER TABLE mcp_servers OWNER TO postgres;
ALTER TABLE bridges OWNER TO postgres;
$t$
