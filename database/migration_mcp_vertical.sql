create extension if not exists vector;

create table if not exists mcp_servers (
  id bigint generated always as identity primary key,
  slug text not null unique,
  name text not null unique,
  description text,
  author text,
  repo_url text,
  registry_source text,
  package_type text check (package_type in ($t$npm$t$,$t$pypi$t$,$t$oci$t$,$t$docker$t$,$t$nuget$t$,$t$mcpb$t$,$t$unknown$t$)),
  package_types text[] not null default array[]::text[],
  transport text check (transport in ($t$stdio$t$,$t$http$t$,$t$sse$t$,$t$streamable-http$t$,$t$unknown$t$)),
  transports text[] not null default array[]::text[],
  capabilities text[] not null default array[]::text[],
  hosting text check (hosting in ($t$local$t$,$t$remote$t$,$t$hybrid$t$,$t$unknown$t$)),
  version text,
  website_url text,
  license text,
  stars integer,
  weekly_downloads integer,
  quality_score numeric(4,2),
  status text not null default $t$active$t$,
  is_latest boolean not null default true,
  published_at timestamptz,
  embedding vector(768),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_mcp_servers_repo_url on mcp_servers (repo_url);
create index if not exists idx_mcp_servers_registry_source on mcp_servers (registry_source);
create index if not exists idx_mcp_servers_status on mcp_servers (status);

create table if not exists bridges (
  id bigint generated always as identity primary key,
  source_type text not null,
  source_id text not null,
  target_type text not null,
  target_id text not null,
  relation text not null,
  weight numeric(5,4) not null default 1.0,
  evidence text,
  created_at timestamptz not null default now(),
  unique (source_type, source_id, target_type, target_id, relation)
);

create index if not exists idx_bridges_source on bridges (source_type, source_id);
create index if not exists idx_bridges_target on bridges (target_type, target_id);
create index if not exists idx_bridges_relation on bridges (relation);

alter table mcp_servers add column if not exists package_identifier text;

alter table mcp_servers add column if not exists package_ids text[] not null default array[]::text[];

alter table mcp_servers add column if not exists remote_urls text[] not null default array[]::text[];
