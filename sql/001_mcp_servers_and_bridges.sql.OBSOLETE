-- Idempotent schema for MCP servers and graphe pont (bridges).
-- Created 2026-07-19, autonomous run. Dollar-quoting throughout.

-- Create enum for package types
DO $do_pkg$ BEGIN
  CREATE TYPE package_type_enum AS ENUM ('npm', 'pypi', 'docker', 'other');
EXCEPTION WHEN duplicate_object THEN NULL;
END $do_pkg$;

-- Create enum for transport types
DO $do_trans$ BEGIN
  CREATE TYPE transport_enum AS ENUM ('stdio', 'http', 'sse', 'other');
EXCEPTION WHEN duplicate_object THEN NULL;
END $do_trans$;

-- Create enum for hosting
DO $do_host$ BEGIN
  CREATE TYPE hosting_enum AS ENUM ('local', 'remote', 'hybrid', 'unknown');
EXCEPTION WHEN duplicate_object THEN NULL;
END $do_host$;

-- Create enum for bridge relations
DO $do_rel$ BEGIN
  CREATE TYPE bridge_relation_enum AS ENUM ('requires', 'connects_to', 'wraps', 'alternative_of', 'integrates_with', 'depends_on', 'complements');
EXCEPTION WHEN duplicate_object THEN NULL;
END $do_rel$;

CREATE TABLE IF NOT EXISTS mcp_servers (
  id BIGSERIAL PRIMARY KEY,
  slug TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  author TEXT,
  repo_url TEXT UNIQUE,
  registry_source TEXT,
  package_type package_type_enum DEFAULT 'other'::package_type_enum,
  transport transport_enum DEFAULT 'stdio'::transport_enum,
  capabilities TEXT[],
  hosting hosting_enum DEFAULT 'unknown'::hosting_enum,
  stars INTEGER DEFAULT 0,
  weekly_downloads INTEGER DEFAULT 0,
  license TEXT,
  quality_score NUMERIC(4, 2),
  embedding_768d VECTOR(768),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mcp_servers_slug ON mcp_servers(slug);
CREATE INDEX IF NOT EXISTS idx_mcp_servers_repo_url ON mcp_servers(repo_url);
CREATE INDEX IF NOT EXISTS idx_mcp_servers_registry_source ON mcp_servers(registry_source);

CREATE TABLE IF NOT EXISTS bridges (
  id BIGSERIAL PRIMARY KEY,
  source_type TEXT NOT NULL,
  source_id BIGINT NOT NULL,
  target_type TEXT NOT NULL,
  target_id BIGINT NOT NULL,
  relation bridge_relation_enum NOT NULL,
  weight NUMERIC(4, 2) DEFAULT 0.50,
  evidence TEXT,
  inferred BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE (source_type, source_id, target_type, target_id, relation)
);

CREATE INDEX IF NOT EXISTS idx_bridges_source ON bridges(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_bridges_target ON bridges(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_bridges_relation ON bridges(relation);

CREATE TABLE IF NOT EXISTS mcp_servers_staging (
  id BIGSERIAL PRIMARY KEY,
  slug TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  author TEXT,
  repo_url TEXT,
  registry_source TEXT,
  package_type TEXT,
  transport TEXT,
  capabilities TEXT[],
  hosting TEXT,
  stars INTEGER,
  weekly_downloads INTEGER,
  license TEXT,
  quality_score NUMERIC(4, 2),
  dedup_status TEXT DEFAULT 'new',
  dedup_canonical_id BIGINT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mcp_servers_staging_repo ON mcp_servers_staging(repo_url);
CREATE INDEX IF NOT EXISTS idx_mcp_servers_staging_status ON mcp_servers_staging(dedup_status);
