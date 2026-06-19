# -*- coding: utf-8 -*-
"""
b6_seo.py - Batch B6 : generation SEO des pages de regroupement.

v1 : intros de categorie. Pour chaque categorie publiee, le LLM local redige
un texte d'intro riche (description_md) + raffine seo_title / seo_description,
en s'appuyant sur la liste des outils de la categorie. Ecrit directement dans
la table Supabase `categories`.

Garde-fous : longueur min/max, pas de contenu mince, fallback deterministe.
Cache : content_hash (categorie + outils) dans la table locale b6_category_seo,
pour ne rappeler le LLM que sur le delta (sauf --force).

Dependances conceptuelles : B4 (categories) et B5 (liens) pour le contexte.

Usage:
    python b6_seo.py
    python b6_seo.py --dry-run
    python b6_seo.py --only ai-audio
    python b6_seo.py --force
    python b6_seo.py --model qwen2.5:14b-instruct

NB : les pages "X vs Y" et "alternatives" (prose) = B6 phase 2 (pas de table
de stockage cote schema pour l'instant).
"""
import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

import os
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY  = os.environ.get("SUPABASE_SERVICE_KEY", "")

import staging
from llm_local import generer_json, MODELE_GEN, LLMError

MIN_DESC = 200      # longueur mini de description_md (anti contenu mince)
MAX_DESC = 1400
MAX_TITLE = 60
MAX_SEO_DESC = 155
PROMPT_VERSION = "b6-v1"


SYSTEM_PROMPT = (
    "You write concise, factual SEO intro copy for a directory of AI and SaaS tools. "
    "You are given a category and the list of tools it contains. "
    "Write a helpful category introduction. Be specific and grounded in the tools "
    "provided; never invent tools or features. No fluff, no thin content. "
    "Return ONLY valid JSON with keys: description_md (string, 2 short paragraphs, "
    "plain markdown, no headings), seo_title (string, max 60 chars), "
    "seo_description (string, max 155 chars). No extra keys, no markdown fences."
)


def build_prompt(category, tools):
    """category: dict {slug,name}. tools: list de dicts {name, short_desc}."""
    name = category.get("name", "")
    lignes = "\n".join(
        f"  - {t.get('name','')}: {t.get('short_desc','') or ''}".rstrip()
        for t in tools[:12]
    ) or "  (no tools yet)"
    return (
        f"Category: {name}\n"
        f"Tools in this category:\n{lignes}\n\n"
        "Write the JSON now. description_md must introduce the category and give "
        "the reader a quick sense of what these tools do and how to choose. "
        f"description_md between {MIN_DESC} and {MAX_DESC} characters. "
        f"seo_title max {MAX_TITLE} chars. seo_description max {MAX_SEO_DESC} chars."
    )


def _clean(s):
    return " ".join(str(s or "").split())


def validate_category_content(raw_out, category):
    """
    Retourne (fields_dict, is_thin).
    Applique garde-fous + fallback deterministe.
    """
    name = category.get("name", "") or category.get("slug", "")

    desc = str(raw_out.get("description_md") or "").strip()
    title = _clean(raw_out.get("seo_title"))
    seo_desc = _clean(raw_out.get("seo_description"))

    is_thin = len(desc) < MIN_DESC
    if len(desc) > MAX_DESC:
        desc = desc[:MAX_DESC].rstrip()

    if not title:
        title = f"Best {name} Tools"
    title = title[:MAX_TITLE]

    if not seo_desc:
        seo_desc = _clean(desc) or f"Discover the best {name} tools."
    seo_desc = seo_desc[:MAX_SEO_DESC]

    return {
        "description_md":  desc,
        "seo_title":       title,
        "seo_description": seo_desc,
    }, is_thin


def content_hash_for(category, tools):
    parts = (
        PROMPT_VERSION
        + (category.get("slug") or "")
        + (category.get("name") or "")
        + "|".join(sorted(t.get("slug", "") for t in tools))
    )
    return hashlib.sha256(parts.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Cache local (content_hash par categorie)
# ---------------------------------------------------------------------------

def init_cache():
    db = staging.connect()
    db.execute("""
        CREATE TABLE IF NOT EXISTS b6_category_seo (
            slug         TEXT PRIMARY KEY,
            content_hash TEXT,
            generated_at TEXT
        )
    """)
    db.commit()
    return db


def get_cached_hash(db, slug):
    row = db.execute(
        "SELECT content_hash FROM b6_category_seo WHERE slug=?", (slug,)
    ).fetchone()
    return row["content_hash"] if row else None


def set_cached_hash(db, slug, chash, now):
    db.execute("""
        INSERT INTO b6_category_seo (slug, content_hash, generated_at)
        VALUES (?,?,?)
        ON CONFLICT(slug) DO UPDATE SET
            content_hash=excluded.content_hash, generated_at=excluded.generated_at
    """, (slug, chash, now))
    db.commit()


# ---------------------------------------------------------------------------
# Faux LLM pour --dry-run
# ---------------------------------------------------------------------------

def fake_llm(prompt, system, modele=None, timeout=120, _appel=None):
    return {
        "description_md": ("This category groups tools that help with the task at "
                           "hand. " * 8).strip(),
        "seo_title": "Best Demo Tools",
        "seo_description": "Compare the best tools in this category.",
    }


# ---------------------------------------------------------------------------
# Acces Supabase
# ---------------------------------------------------------------------------

def fetch_categories_and_tools():
    from supabase import create_client
    sb = create_client(SUPABASE_URL, SERVICE_KEY)

    cats = sb.table("categories").select(
        "id, slug, name, description_md, seo_title, seo_description"
    ).eq("status", "published").limit(10000).execute().data or []

    tcat = sb.table("tool_categories").select(
        "tool_id, category_id"
    ).limit(100000).execute().data or []

    tools = sb.table("tools").select(
        "id, slug, name, short_desc"
    ).eq("status", "published").limit(10000).execute().data or []
    tools_by_id = {t["id"]: t for t in tools}

    # index outils par categorie
    by_cat = {}
    for r in tcat:
        t = tools_by_id.get(r["tool_id"])
        if t:
            by_cat.setdefault(r["category_id"], []).append(t)

    return sb, cats, by_cat


def update_category(sb, cat_id, fields):
    sb.table("categories").update(fields).eq("id", cat_id).execute()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Batch B6 - intros de categorie")
    parser.add_argument("--dry-run", action="store_true",
                        help="Faux LLM, n'ecrit ni Supabase ni cache.")
    parser.add_argument("--only", type=str, default="")
    parser.add_argument("--force", action="store_true",
                        help="Regenerer meme si content_hash inchange.")
    parser.add_argument("--model", type=str, default=MODELE_GEN)
    args = parser.parse_args()

    fn_gen = fake_llm if args.dry_run else generer_json

    if not args.dry_run and (not SUPABASE_URL or not SERVICE_KEY):
        sys.exit("SUPABASE_URL et SUPABASE_SERVICE_KEY requis dans prisme/.env.")

    sb, cats, by_cat = fetch_categories_and_tools()
    if args.only:
        cats = [c for c in cats if c["slug"] == args.only]
        if not cats:
            sys.exit(f"[B6] Categorie introuvable (publiee) : {args.only}")

    db = init_cache()
    now = datetime.now(timezone.utc).isoformat()

    nb_ok = nb_skip = nb_thin = nb_err = 0

    for c in cats:
        tools = by_cat.get(c["id"], [])
        chash = content_hash_for(c, tools)

        if not args.force and not args.dry_run:
            if get_cached_hash(db, c["slug"]) == chash:
                nb_skip += 1
                continue

        print(f"[B6] redaction intro: {c['slug']} ({len(tools)} outil(s))")
        prompt = build_prompt(c, tools)
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

        fields, is_thin = validate_category_content(out, c)
        if is_thin:
            nb_thin += 1
            print(f"  contenu mince (desc {len(fields['description_md'])} car) "
                  f"-> ignore, pas d'ecriture.")
            continue

        if args.dry_run:
            print(f"  [dry-run] title={fields['seo_title']!r} "
                  f"desc_md={len(fields['description_md'])} car")
        else:
            update_category(sb, c["id"], fields)
            set_cached_hash(db, c["slug"], chash, now)
            print(f"  ecrit (title={fields['seo_title']!r}).")
        nb_ok += 1

    print(f"\n[B6] Resume: {nb_ok} ecrite(s), {nb_skip} skip(s), "
          f"{nb_thin} mince(s) ignoree(s), {nb_err} erreur(s).")


if __name__ == "__main__":
    main()
