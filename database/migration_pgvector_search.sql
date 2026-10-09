-- migration_pgvector_search.sql
-- YggNexus : recherche semantique locale via pgvector, sur les embeddings
-- nomic-embed-text (768 dim) deja produits par le Prisme (llm_local.py,
-- table `embeddings`, entity_type='tool', model='nomic-embed-text' -- voir
-- migration_embeddings_dim_768.sql qui a deja porte cette colonne a
-- vector(768)).
--
-- Remplace la dependance a Jina (search_embeddings, 1024 dim, payant) par
-- une RPC qui interroge directement `embeddings`, sans nouvelle colonne ni
-- nouvelle table : on reutilise ce qui existe deja et que publish_embeddings.py
-- alimente a chaque run nightly (etape "embeddings", avant "liens").
--
-- Idempotent. A coller dans Supabase -> SQL Editor -> Run. ASCII pur.

create extension if not exists vector;

-- Index ANN (HNSW) sur les embeddings d'outils nomic 768d. Filtre partiel
-- (entity_type='tool') pour ne pas indexer d'eventuels futurs embeddings
-- de categories/automations avec une autre dimension logique.
-- NB : un index HNSW pgvector ne peut pas etre partiel avec predicat sur une
-- colonne non-vecteur si on veut l'utiliser via l'operateur <=> directement
-- dans ORDER BY -- Postgres/pgvector supporte les index partiels sur les
-- tables classiques, on le fait donc simplement filtrer a la requete (voir
-- la clause WHERE de la fonction ci-dessous) : l'index reste global sur la
-- colonne embedding, ce qui est suffisant au volume actuel (quelques
-- milliers de lignes).
create index if not exists idx_embeddings_hnsw_cosine
    on embeddings using hnsw (embedding vector_cosine_ops);

-- Fonction RPC : recherche semantique locale (nomic-embed-text, 768 dim).
-- Remplace/complete match_tools (Jina 1024 dim) sans y toucher -- les deux
-- coexistent le temps de la transition (cf. docs/RECHERCHE_SEMANTIQUE_LOCALE.md).
drop function if exists search_tools_semantic(vector(768), int);

create or replace function search_tools_semantic(
    query_embedding vector(768),
    match_count int default 10
)
returns table (
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
    select t.slug, t.name, t.short_desc, t.quality_score,
           (1 - (e.embedding <=> query_embedding))::double precision as similarity
    from embeddings e
    join tools t on t.id = e.entity_id
    where e.entity_type = 'tool'
      and e.model = 'nomic-embed-text'
      and t.status = 'published'
      and e.embedding is not null
    order by e.embedding <=> query_embedding
    limit match_count
$t$;

grant execute on function search_tools_semantic(vector, int) to anon, authenticated;

-- ============================================================
-- FIN -- verification rapide :
-- select proname, pronargs from pg_proc where proname = 'search_tools_semantic';
-- select count(*) from embeddings where entity_type='tool' and model='nomic-embed-text';
-- ============================================================
