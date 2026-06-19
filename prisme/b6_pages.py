# -*- coding: utf-8 -*-
"""
b6_pages.py - Batch B6 phase 2 : prose SEO des pages de regroupement.

Genere un texte d'intro (intro_md) + seo_title/seo_description pour :
  - les pages "X vs Y"        -> page_type='compare',      key='a-vs-b'
  - les pages "alternatives"  -> page_type='alternatives', key='<slug>'
et ecrit dans la table Supabase `page_seo` (voir database/migration_page_seo.sql).

Garde-fous : longueur min/max, anti contenu mince, fallback deterministe.
Cache : content_hash par page (table locale b6_page_seo) -> ne rappelle le LLM
que sur le delta, sauf --force.
Apres ecriture, revalide les pages touchees (ISR on-demand) si REVALIDATE_SECRET.

Pre-requis : migration_page_seo.sql appliquee dans Supabase.

Usage:
    python b6_pages.py
    python b6_pages.py --dry-run
    python b6_pages.py --only compare           # ou: alternatives
    python b6_pages.py --only-key jasper-vs-copy-ai
    python b6_pages.py --force
    python b6_pages.py --model qwen2.5:14b-instruct
"""
import argparse
import hashlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

SUPABASE_URL   = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY    = os.environ.get("SUPABASE_SERVICE_KEY", "")
SITE_URL       = os.environ.get("SITE_URL", "http://localhost:3000").rstrip("/")
REVALIDATE_SECRET = os.environ.get("REVALIDATE_SECRET", "")

import staging
from llm_local import generer_json, MODELE_GEN, LLMError

MIN_INTRO = 200
MAX_INTRO = 1600
MAX_TITLE = 60
MAX_SEO_DESC = 155
PROMPT_VERSION = "b6pages-v1"


# ---------------------------------------------------------------------------
# Fonctions pures (testees)
# ---------------------------------------------------------------------------

def compare_key(slug_a, slug_b):
    """Cle canonique d'une paire, independante de l'ordre (ordre alpha)."""
    x, y = sorted([slug_a, slug_b])
    return f"{x}-vs-{y}"


def _clean(s):
    return " ".join(str(s or "").split())


def validate_intro(raw_out, fallback_title, fallback_desc):
    """
    Applique garde-fous + fallback deterministe.
    Retourne (fields_dict, is_thin).
    """
    desc = str(raw_out.get("intro_md") or "").strip()
    title = _clean(raw_out.get("seo_title"))
    seo_desc = _clean(raw_out.get("seo_description"))

    is_thin = len(desc) < MIN_INTRO
    if len(desc) > MAX_INTRO:
        desc = desc[:MAX_INTRO].rstrip()

    if not title:
        title = fallback_title
    title = title[:MAX_TITLE]

    if not seo_desc:
        seo_desc = _clean(desc) or fallback_desc
    seo_desc = seo_desc[:MAX_SEO_DESC]

    return {
        "intro_md": desc,
        "seo_title": title,
        "seo_description": seo_desc,
    }, is_thin


def _tool_fingerprint(t):
    return "~".join([
        t.get("slug", "") or "",
        t.get("name", "") or "",
        t.get("short_desc", "") or "",
        str(t.get("pricing", "") or ""),
        str(t.get("quality_score", "") if t.get("quality_score") is not None else ""),
    ])


def content_hash_compare(tool_a, tool_b):
    a, b = sorted([tool_a, tool_b], key=lambda t: t.get("slug", ""))
    parts = (PROMPT_VERSION + "|compare|"
             + _tool_fingerprint(a) + "||" + _tool_fingerprint(b))
    return hashlib.sha256(parts.encode("utf-8")).hexdigest()


def content_hash_alternatives(tool, alts):
    alt_part = "|".join(
        _tool_fingerprint(a) for a in sorted(alts, key=lambda t: t.get("slug", ""))
    )
    parts = (PROMPT_VERSION + "|alternatives|"
             + _tool_fingerprint(tool) + "||" + alt_part)
    return hashlib.sha256(parts.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You write concise, factual SEO intro copy for a directory of AI and SaaS tools. "
    "Be specific and grounded ONLY in the data provided; never invent tools, prices, "
    "or features. No fluff, no thin content, neutral and helpful tone. "
    "Return ONLY valid JSON with keys: intro_md (string, 2 short paragraphs, plain "
    "markdown, no headings), seo_title (string, max 60 chars), seo_description "
    "(string, max 155 chars). No extra keys, no markdown fences."
)


def build_compare_prompt(tool_a, tool_b):
    def line(t):
        return (f"  - {t.get('name','')} ({t.get('slug','')}): "
                f"{t.get('short_desc','') or 'no description'} | "
                f"pricing={t.get('pricing','unknown')} | "
                f"score={t.get('quality_score')}")
    return (
        f"Two tools to compare:\n{line(tool_a)}\n{line(tool_b)}\n\n"
        "Write the JSON now. intro_md should help the reader understand how these two "
        "tools differ and who each is best for, grounded in the data above. "
        f"intro_md between {MIN_INTRO} and {MAX_INTRO} characters. "
        f"seo_title like '{tool_a.get('name','')} vs {tool_b.get('name','')}', "
        f"max {MAX_TITLE} chars. seo_description max {MAX_SEO_DESC} chars."
    )


def build_alternatives_prompt(tool, alts):
    lignes = "\n".join(
        f"  - {a.get('name','')} ({a.get('slug','')}): {a.get('short_desc','') or ''}".rstrip()
        for a in alts[:10]
    ) or "  (no alternatives yet)"
    return (
        f"Tool: {tool.get('name','')} ({tool.get('slug','')}) — "
        f"{tool.get('short_desc','') or 'no description'}\n"
        f"Alternatives to introduce:\n{lignes}\n\n"
        "Write the JSON now. intro_md should explain why someone might look for an "
        "alternative and what kinds of options exist, grounded in the list above. "
        f"intro_md between {MIN_INTRO} and {MAX_INTRO} characters. "
        f"seo_title like 'Best {tool.get('name','')} Alternatives', max {MAX_TITLE} chars. "
        f"seo_description max {MAX_SEO_DESC} chars."
    )


# ---------------------------------------------------------------------------
# Faux LLM pour --dry-run
# ---------------------------------------------------------------------------

def fake_llm(prompt, system, modele=None, timeout=120, _appel=None):
    return {
        "intro_md": ("These tools solve overlapping problems but differ in focus, "
                     "pricing and depth. Pick based on your workflow and budget. " * 4).strip(),
        "seo_title": "Demo Intro Title",
        "seo_description": "A concise demo description for this grouping page.",
    }


# ---------------------------------------------------------------------------
# Cache local (content_hash par page)
# ---------------------------------------------------------------------------

def init_cache():
    db = staging.connect()
    db.execute("""
        CREATE TABLE IF NOT EXISTS b6_page_seo (
            page_type    TEXT,
            page_key     TEXT,
            content_hash TEXT,
            generated_at TEXT,
            PRIMARY KEY (page_type, page_key)
        )
    """)
    db.commit()
    return db


def get_cached_hash(db, page_type, page_key):
    row = db.execute(
        "SELECT content_hash FROM b6_page_seo WHERE page_type=? AND page_key=?",
        (page_type, page_key),
    ).fetchone()
    return row["content_hash"] if row else None


def set_cached_hash(db, page_type, page_key, chash, now):
    db.execute("""
        INSERT INTO b6_page_seo (page_type, page_key, content_hash, generated_at)
        VALUES (?,?,?,?)
        ON CONFLICT(page_type, page_key) DO UPDATE SET
            content_hash=excluded.content_hash, generated_at=excluded.generated_at
    """, (page_type, page_key, chash, now))
    db.commit()


# ---------------------------------------------------------------------------
# Acces Supabase
# ---------------------------------------------------------------------------

def fetch_context():
    from supabase import create_client
    sb = create_client(SUPABASE_URL, SERVICE_KEY)

    tools = sb.table("tools").select(
        "id, slug, name, short_desc, pricing, quality_score"
    ).eq("status", "published").limit(10000).execute().data or []
    by_id = {t["id"]: t for t in tools}
    by_slug = {t["slug"]: t for t in tools}

    alts = sb.table("alternatives").select(
        "tool_id, alternative_id, similarity"
    ).limit(100000).execute().data or []

    # paires compare (canoniques, dedupliquees, deux outils publies)
    seen = set()
    pairs = []
    for r in alts:
        a = by_id.get(r["tool_id"])
        b = by_id.get(r["alternative_id"])
        if not a or not b or a["slug"] == b["slug"]:
            continue
        key = compare_key(a["slug"], b["slug"])
        if key in seen:
            continue
        seen.add(key)
        pairs.append((key, a, b))

    # alternatives par outil (trie par similarite desc)
    alts_by_tool = {}
    for r in sorted(alts, key=lambda x: (x.get("similarity") or 0), reverse=True):
        t = by_id.get(r["tool_id"])
        a = by_id.get(r["alternative_id"])
        if not t or not a:
            continue
        alts_by_tool.setdefault(t["slug"], (t, []))[1].append(a)

    return sb, pairs, alts_by_tool


def upsert_page_seo(sb, page_type, page_key, fields):
    sb.table("page_seo").upsert(
        {"page_type": page_type, "page_key": page_key,
         "intro_md": fields["intro_md"],
         "seo_title": fields["seo_title"],
         "seo_description": fields["seo_description"],
         "status": "published"},
        on_conflict="page_type,page_key",
    ).execute()


def revalidate(paths):
    if not REVALIDATE_SECRET:
        print("  (pas de REVALIDATE_SECRET : revalidation ignoree)")
        return
    if not paths:
        return
    import requests
    try:
        r = requests.post(
            f"{SITE_URL}/api/revalidate",
            json={"paths": sorted(set(paths))},
            headers={"Authorization": f"Bearer {REVALIDATE_SECRET}"},
            timeout=15,
        )
        print(f"  revalidate -> {r.status_code} {r.text[:200]}")
    except requests.RequestException as e:
        print(f"  revalidate : site injoignable ({e}). Sans gravite si pas demarre.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Batch B6 phase 2 - prose compare/alternatives")
    parser.add_argument("--dry-run", action="store_true",
                        help="Faux LLM, n'ecrit ni Supabase ni cache.")
    parser.add_argument("--only", choices=["compare", "alternatives"], default="",
                        help="Limiter a un type de page.")
    parser.add_argument("--only-key", type=str, default="",
                        help="Limiter a une seule cle (ex: jasper-vs-copy-ai ou jasper).")
    parser.add_argument("--force", action="store_true",
                        help="Regenerer meme si content_hash inchange.")
    parser.add_argument("--model", type=str, default=MODELE_GEN)
    args = parser.parse_args()

    fn_gen = fake_llm if args.dry_run else generer_json

    if not args.dry_run and (not SUPABASE_URL or not SERVICE_KEY):
        sys.exit("SUPABASE_URL et SUPABASE_SERVICE_KEY requis dans prisme/.env.")

    sb, pairs, alts_by_tool = fetch_context()
    db = init_cache()
    now = datetime.now(timezone.utc).isoformat()

    nb_ok = nb_skip = nb_thin = nb_err = 0
    touched_paths = []

    # --- jobs : (page_type, page_key, content_hash, prompt, fallback_title, fallback_desc, path)
    jobs = []

    if args.only in ("", "compare"):
        for key, a, b in pairs:
            if args.only_key and key != args.only_key:
                continue
            chash = content_hash_compare(a, b)
            prompt = build_compare_prompt(a, b)
            ftitle = f"{a.get('name','')} vs {b.get('name','')}"
            fdesc = f"Compare {a.get('name','')} and {b.get('name','')}."
            jobs.append(("compare", key, chash, prompt, ftitle, fdesc, f"/compare/{key}"))

    if args.only in ("", "alternatives"):
        for slug, (tool, alts) in alts_by_tool.items():
            if args.only_key and slug != args.only_key:
                continue
            if not alts:
                continue
            chash = content_hash_alternatives(tool, alts)
            prompt = build_alternatives_prompt(tool, alts)
            ftitle = f"Best {tool.get('name','')} Alternatives"
            fdesc = f"Discover the best alternatives to {tool.get('name','')}."
            jobs.append(("alternatives", slug, chash, prompt, ftitle, fdesc,
                         f"/tools/{slug}/alternatives"))

    for page_type, page_key, chash, prompt, ftitle, fdesc, path in jobs:
        if not args.force and not args.dry_run:
            if get_cached_hash(db, page_type, page_key) == chash:
                nb_skip += 1
                continue

        print(f"[B6p2] {page_type}: {page_key}")
        try:
            out = fn_gen(prompt, SYSTEM_PROMPT, modele=args.model)
        except LLMError as e:
            print(f"  ERREUR LLM: {e}")
            nb_err += 1
            continue
        except Exception as e:
            print(f"  ERREUR inattendue: {e}")
            nb_err += 1
            continue

        fields, is_thin = validate_intro(out, ftitle, fdesc)
        if is_thin:
            nb_thin += 1
            print(f"  contenu mince ({len(fields['intro_md'])} car) -> ignore.")
            continue

        if args.dry_run:
            print(f"  [dry-run] title={fields['seo_title']!r} "
                  f"intro_md={len(fields['intro_md'])} car")
        else:
            upsert_page_seo(sb, page_type, page_key, fields)
            set_cached_hash(db, page_type, page_key, chash, now)
            touched_paths.append(path)
            print(f"  ecrit (title={fields['seo_title']!r}).")
        nb_ok += 1

    if not args.dry_run and touched_paths:
        print("Revalidation des pages touchees...")
        revalidate(touched_paths)

    print(f"\n[B6p2] Resume: {nb_ok} ecrite(s), {nb_skip} skip(s), "
          f"{nb_thin} mince(s) ignoree(s), {nb_err} erreur(s).")


if __name__ == "__main__":
    main()
