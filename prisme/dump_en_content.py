# -*- coding: utf-8 -*-
"""dump_en_content.py - Exporte le contenu EN a traduire (outils + categories +
alternatives) depuis Supabase vers data/i18n_source_en.json. A lancer sur la
machine Windows (le sandbox Cowork n'atteint pas Supabase).

Pre-requis dans prisme/.env : SUPABASE_URL, SUPABASE_SERVICE_KEY.
Usage : python dump_en_content.py
"""
import os, sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

# pricing_note ajoute pour C2 (note de prix traduite).
TOOL_FIELDS = ["slug", "name", "short_desc", "description_md",
               "pricing_note",
               "pros_jsonb", "cons_jsonb", "faq_jsonb",
               "seo_title", "seo_description"]
CAT_FIELDS = ["slug", "name", "description_md", "seo_intro_md",
              "seo_title", "seo_description"]


def dump_alternatives(sb):
    """C3 : raisons d'alternatives a traduire, identifiees par paires de slugs."""
    rows = (sb.table("alternatives")
            .select("reason, t:tool_id(slug), a:alternative_id(slug)")
            .execute().data or [])
    out = []
    for r in rows:
        reason = (r.get("reason") or "").strip()
        ts = (r.get("t") or {}).get("slug")
        als = (r.get("a") or {}).get("slug")
        if reason and ts and als:
            out.append({"tool_slug": ts, "alternative_slug": als, "reason": reason})
    return out


def main():
    if not (SUPABASE_URL and SERVICE_KEY):
        sys.exit("Requis dans prisme/.env : SUPABASE_URL, SUPABASE_SERVICE_KEY")
    from supabase import create_client
    sb = create_client(SUPABASE_URL, SERVICE_KEY)

    tools = (sb.table("tools").select(",".join(TOOL_FIELDS))
             .eq("status", "published").order("slug").execute().data or [])
    cats = (sb.table("categories").select(",".join(CAT_FIELDS))
            .eq("status", "published").order("slug").execute().data or [])
    alternatives = dump_alternatives(sb)

    out = {"tools": tools, "categories": cats, "alternatives": alternatives}
    path = ROOT / "data" / "i18n_source_en.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[dump] {len(tools)} outil(s) + {len(cats)} categorie(s) + "
          f"{len(alternatives)} raison(s) d'alternative -> {path}")


if __name__ == "__main__":
    main()
