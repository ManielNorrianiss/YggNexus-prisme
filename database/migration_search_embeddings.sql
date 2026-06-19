-- YggNexus : recherche semantique (Supabase Edge gte-small, 384 dim)
-- A coller dans Supabase -> SQL Editor -> Run. Idempotent.

create extension if not exists vector;

create table if not exists search_embeddings (
    tool_id    bigint primary key references tools(id) on delete cascade,
    embedding  vector(384),
    updated_at timestamptz not null default now()
);

create index if not exists idx_search_embeddings_hnsw
    on search_embeddings using hnsw (embedding vector_cosine_ops);

alter table search_embeddings enable row level security;

create or replace function match_tools(query_embedding vector(384), match_count int default 10)
returns table (
    id            bigint,
    slug          text,
    name          text,
    short_desc    text,
    quality_score numeric,
    similarity    double precision
)
language sql
stable
security definer
set search_path = public
as $t$
    select t.id, t.slug, t.name, t.short_desc, t.quality_score,
           (1 - (se.embedding <=> query_embedding))::double precision as similarity
    from search_embeddings se
    join tools t on t.id = se.tool_id
    where t.status = 'published'
      and se.embedding is not null
    order by se.embedding <=> query_embedding
    limit match_count
$t$;

grant execute on function match_tools(vector, int) to anon, authenticated;
