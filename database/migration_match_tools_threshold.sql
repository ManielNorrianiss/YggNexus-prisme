-- YggNexus : seuil de similarite parametrable dans match_tools.
-- Ajoute un 3e parametre match_threshold (defaut 0.3) qui coupe la queue de
-- resultats peu pertinents (cosine similarity < seuil). Ajustable en re-collant
-- ce fichier avec une autre valeur par defaut, sans redeploiement du frontend.
-- A coller dans Supabase -> SQL Editor -> Run. Idempotent. ASCII pur.

-- On retire les anciennes signatures pour eviter toute ambiguite de surcharge
-- quand le frontend appelle avec 2 arguments nommes.
drop function if exists match_tools(vector(1024), int);
drop function if exists match_tools(vector(1024), int, double precision);

create or replace function match_tools(
    query_embedding vector(1024),
    match_count int default 10,
    match_threshold double precision default 0.3
)
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
      and (1 - (se.embedding <=> query_embedding)) >= match_threshold
    order by se.embedding <=> query_embedding
    limit match_count
$t$;

grant execute on function match_tools(vector, int, double precision) to anon, authenticated;
