# -*- coding: utf-8 -*-
"""dump_en_content.py - Exporte le contenu EN a traduire (outils + categories)
depuis Supabase vers data/i18n_source_en.json. A lancer sur la machine Windows
(le sandbox Cowork n'atteint pas Supabase).

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

TOOL_FIELDS = ["slug", "name", "short_desc", "description_md",
               "pros_jsonb", "cons_jsonb", "faq_jsonb",
               "seo_title", "seo_description"]
CAT_FIELDS = ["slug", "name", "description_md", "seo_intro_md",
              "seo_title", "seo_description"]


def main():
    if not (SUPABASE_URL and SERVICE_KEY):
        sys.exit("Requis dans prisme/.env : SUPABASE_URL, SUPABASE_SERVICE_KEY")
    from supabase import create_client
    sb = create_client(SUPABASE_URL, SERVICE_KEY)

    tools = (sb.table("tools").select(",".join(TOOL_FIELDS))
             .eq("status", "published").order("slug").execute().data or [])
    cats = (sb.table("categories").select(",".join(CAT_FIELDS))
            .eq("status", "published").order("slug").execute().data or [])

    out = {"tools": tools, "categories": cats}
    path = ROOT / "data" / "i18n_source_en.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[dump] {len(tools)} outil(s) + {len(cats)} categorie(s) -> {path}")


if __name__ == "__main__":
    main()
