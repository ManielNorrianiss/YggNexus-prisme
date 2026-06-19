-- YggNexus : recherche semantique via Jina embeddings v3 (1024 dim, multilingue).
-- Reconfigure search_embeddings en 1024 et recree match_tools. Table videe au
-- passage (on re-embed tout). A coller dans Supabase SQL Editor. Idempotent.

drop index if exists idx_search_embeddings_hnsw;

truncate table search_embeddings;

alter table search_embeddings alter column embedding type vector(1024);

create index if not exists idx_search_embeddings_hnsw
    on search_embeddings using hnsw (embedding vector_cosine_ops);

create or replace function match_tools(query_embedding vector(1024), match_count int default 10)
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
