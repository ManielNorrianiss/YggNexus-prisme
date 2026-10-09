create table if not exists page_seo (
    id bigint generated always as identity primary key,
    page_type text not null check (page_type in ('compare', 'alternatives')),
    page_key text not null,
    intro_md text,
    seo_title text,
    seo_description text,
    content_hash text,
    status content_status not null default 'published',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (page_type, page_key)
);

create index if not exists idx_page_seo_lookup on page_seo(page_type, page_key);

drop trigger if exists trg_page_seo_updated_at on page_seo;

create trigger trg_page_seo_updated_at before update on page_seo
    for each row execute function set_updated_at();

alter table page_seo enable row level security;

drop policy if exists p_page_seo_pub on page_seo;

create policy p_page_seo_pub on page_seo
    for select using (status = 'published');
