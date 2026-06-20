-- YggNexus : recherche semantique FR (Jina v3, 1024 dim).
-- Auto-suffisant : (re)cree d'abord les colonnes _fr (idempotent), puis la table
-- search_embeddings_fr isolee + RPC match_tools_lang filtrant par langue.
-- A coller dans le SQL Editor WEB Supabase. Idempotent. Ne touche ni match_tools
-- ni search_embeddings (EN intact).

alter table tools      add column if not exists short_desc_fr      text;
alter table tools      add column if not exists description_md_fr  text;
alter table tools      add column if not exists pros_jsonb_fr      jsonb;
alter table tools      add column if not exists cons_jsonb_fr      jsonb;
alter table tools      add column if not exists faq_jsonb_fr       jsonb;
alter table tools      add column if not exists seo_title_fr       text;
alter table tools      add column if not exists seo_description_fr text;
alter table categories add column if not exists description_md_fr  text;
alter table categories add column if not exists seo_intro_md_fr    text;
alter table categories add column if not exists seo_title_fr       text;
alter table categories add column if not exists seo_description_fr text;

create extension if not exists vector;

create table if not exists search_embeddings_fr (
    tool_id    bigint primary key references tools(id) on delete cascade,
    embedding  vector(1024),
    updated_at timestamptz not null default now()
);

create index if not exists idx_search_embeddings_fr_hnsw
    on search_embeddings_fr using hnsw (embedding vector_cosine_ops);

alter table search_embeddings_fr enable row level security;

create or replace function match_tools_lang(query_embedding vector(1024), match_count int default 12, match_lang text default 'en')
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
    select t.id, t.slug, t.name,
           case when match_lang = 'fr'
                then coalesce(nullif(t.short_desc_fr, ''), t.short_desc)
                else t.short_desc end as short_desc,
           t.quality_score,
           (1 - (se.embedding <=> query_embedding))::double precision as similarity
    from (
        select tool_id, embedding from search_embeddings    where match_lang = 'en'
        union all
        select tool_id, embedding from search_embeddings_fr where match_lang = 'fr'
    ) se
    join tools t on t.id = se.tool_id
    where t.status = 'published'
      and se.embedding is not null
    order by se.embedding <=> query_embedding
    limit match_count
$t$;

grant execute on function match_tools_lang(vector, int, text) to anon, authenticated;
