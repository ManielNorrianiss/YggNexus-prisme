"""
Pont du Prisme - batch B7 (publication).
Lit data/tools.json, met a jour Supabase (tools + tool_categories + changelog),
puis declenche la regeneration des pages touchees (ISR on-demand).

Usage :
    python publish.py            # publie pour de vrai
    python publish.py --dry-run  # montre ce qui serait fait, sans rien ecrire
"""
import json
import os
import sys
import time
import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parent
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SITE_URL = os.environ.get("SITE_URL", "http://localhost:3000").rstrip("/")
REVALIDATE_SECRET = os.environ.get("REVALIDATE_SECRET", "")

TOOL_FIELDS = [
    "slug", "name", "vendor", "website_url", "affiliate_url", "logo_url",
    "pricing", "pricing_note", "short_desc", "description_md",
    "application_category", "quality_score", "status",
    "seo_title", "seo_description", "pros_jsonb", "cons_jsonb", "faq_jsonb",
]


def load_tools():
    path = ROOT / "data" / "tools.json"
    if not path.exists():
        sys.exit(f"Fichier introuvable : {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        sys.exit("data/tools.json doit etre une liste d outils.")
    return data


def tool_row(item):
    row = {k: item.get(k) for k in TOOL_FIELDS if item.get(k) is not None}
    row.setdefault("status", "published")
    return row


def revalidate(paths):
    if not REVALIDATE_SECRET:
        print("  (pas de REVALIDATE_SECRET : revalidation ignoree)")
        return
    import requests
    url = f"{SITE_URL}/api/revalidate"
    try:
        r = requests.post(
            url,
            json={"paths": sorted(set(paths))},
            headers={"Authorization": f"Bearer {REVALIDATE_SECRET}"},
            timeout=10,
        )
        print(f"  revalidate -> {r.status_code} {r.text[:200]}")
    except requests.RequestException as e:
        print(f"  revalidate : site injoignable ({e}). Sans gravite si le site n est pas demarre.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    tools = load_tools()
    print(f"{len(tools)} outil(s) lus dans data/tools.json")

    if args.dry_run:
        for item in tools:
            cats = item.get("categories", [])
            print(f"  [dry-run] upsert {item.get('slug')} "
                  f"(status={item.get('status', 'published')}, categories={cats})")
        print("[dry-run] aucune ecriture, aucune revalidation.")
        return

    if not SUPABASE_URL or not SERVICE_KEY:
        sys.exit("SUPABASE_URL et SUPABASE_SERVICE_KEY requis dans prisme/.env (voir .env.example).")

    from supabase import create_client
    sb = create_client(SUPABASE_URL, SERVICE_KEY)
    paths = ["/", "/categories"]
    cat_slugs = set()
    run_id = f"publish-{int(time.time())}"

    for item in tools:
        row = tool_row(item)
        res = sb.table("tools").upsert(row, on_conflict="slug").execute()
        tool_id = res.data[0]["id"]
        slug = row["slug"]
        print(f"  upsert tool {slug} (id={tool_id})")

        primary = item.get("primary_category")
        for cat_slug in item.get("categories", []):
            cat_slugs.add(cat_slug)
            # --- Modif 3 : .limit(1) remplace .maybe_single() qui peut lever sur 0 ligne ---
            res_cat = sb.table("categories").select("id").eq("slug", cat_slug).limit(1).execute()
            if not res_cat.data:
                print(f"    categorie inconnue, ignoree : {cat_slug}")
                continue
            cat_id = res_cat.data[0]["id"]
            sb.table("tool_categories").upsert(
                {"tool_id": tool_id, "category_id": cat_id,
                 "is_primary": (cat_slug == primary)},
                on_conflict="tool_id,category_id",
            ).execute()

        sb.table("changelog").insert(
            {"entity_type": "tool", "entity_id": tool_id,
             "action": "published", "batch_run_id": run_id}
        ).execute()

        paths.append(f"/tools/{slug}")

    # --- Revalidation des pages de regroupement (/best/<cat> et /categories/<cat>) ---
    # Sans ca, apres une (re)classification ces pages restent en cache perime
    # (revalidate=86400 cote frontend). On revalide toute categorie touchee par la
    # publication ET, par securite, toutes les categories existantes dans Supabase
    # (peu nombreuses) pour couvrir aussi les RETRAITS de categorie : un outil sorti
    # d une categorie ne figure plus dans sa liste, mais sa vieille page de
    # regroupement doit quand meme etre rafraichie.
    try:
        res_all = sb.table("categories").select("slug").execute()
        for r in (res_all.data or []):
            if r.get("slug"):
                cat_slugs.add(r["slug"])
    except Exception as e:
        print(f"  (lecture des categories impossible, on garde les categories touchees : {e})")

    for cat_slug in sorted(cat_slugs):
        paths.append(f"/best/{cat_slug}")
        paths.append(f"/categories/{cat_slug}")

    print("Publication terminee. Declenchement de la revalidation...")
    print(f"  {len(set(paths))} chemin(s) a revalider "
          f"(dont {len(cat_slugs)} categorie(s) -> /best + /categories).")
    revalidate(paths)


if __name__ == "__main__":
    main()
