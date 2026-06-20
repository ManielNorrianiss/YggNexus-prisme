# -*- coding: utf-8 -*-
"""
sync_categories.py - resynchronise Supabase.tool_categories pour qu'il MATCHE
EXACTEMENT data/tools.json (etat desire produit par b4 + export_tools).

Comble le trou de publish.py : publish fait des UPSERT (jamais de DELETE), donc
apres une reclassification les vieilles etiquettes restent collees. Ce script :
  - ajoute/maj les liens manquants (avec is_primary correct),
  - SUPPRIME les liens Supabase qui ne sont plus dans tools.json,
  - revalide /best/<cat>, /categories/<cat>, /tools/<slug>, / et /categories.

Usage :
    python sync_categories.py --dry-run   # montre le plan, n'ecrit rien
    python sync_categories.py             # applique + revalidation

Prerequis : categories nouvelles deja inserees dans Supabase (sinon ignorees),
tools.json a jour (python export_tools.py).
"""
import os
import sys
import json
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


def load_tools():
    path = ROOT / "data" / "tools.json"
    raw = path.read_bytes().rstrip(b"\x00").rstrip()
    data = json.loads(raw)
    if not isinstance(data, list):
        sys.exit("data/tools.json doit etre une liste.")
    return data


def revalidate(paths):
    if not REVALIDATE_SECRET:
        print("  (pas de REVALIDATE_SECRET : revalidation ignoree)")
        return
    import requests
    try:
        r = requests.post(
            f"{SITE_URL}/api/revalidate",
            json={"paths": sorted(set(paths))},
            headers={"Authorization": f"Bearer {REVALIDATE_SECRET}"},
            timeout=20,
        )
        print(f"  revalidate -> {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"  revalidate : injoignable ({e})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    dry = args.dry_run

    if not SUPABASE_URL or not SERVICE_KEY:
        sys.exit("SUPABASE_URL / SUPABASE_SERVICE_KEY requis dans prisme/.env")

    tools = load_tools()
    from supabase import create_client
    sb = create_client(SUPABASE_URL, SERVICE_KEY)

    cats = sb.table("categories").select("id,slug").execute().data or []
    slug2id = {c["slug"]: c["id"] for c in cats}
    id2slug = {c["id"]: c["slug"] for c in cats}
    db_tools = sb.table("tools").select("id,slug").execute().data or []
    slug2tid = {t["slug"]: t["id"] for t in db_tools}

    n_add, n_del, n_primary = 0, 0, 0
    touched_cats, touched_tools, missing_cat = set(), set(), set()

    for item in tools:
        if (item.get("status") or "published") != "published":
            continue
        slug = item.get("slug")
        tid = slug2tid.get(slug)
        if not tid:
            continue  # outil pas encore dans Supabase
        primary = item.get("primary_category") or ""
        desired = {}
        for cs in item.get("categories", []):
            cid = slug2id.get(cs)
            if cid is None:
                missing_cat.add(cs)
                continue
            desired[cid] = (cs == primary)
        if not desired:
            continue  # filet : ne jamais vider toutes les categories d'un outil

        current = sb.table("tool_categories").select("category_id,is_primary") \
            .eq("tool_id", tid).execute().data or []
        cur = {r["category_id"]: bool(r["is_primary"]) for r in current}

        # suppressions (dans Supabase, plus dans tools.json)
        for cid in list(cur):
            if cid not in desired:
                touched_cats.add(id2slug.get(cid, str(cid)))
                touched_tools.add(slug)
                n_del += 1
                if not dry:
                    sb.table("tool_categories").delete() \
                        .eq("tool_id", tid).eq("category_id", cid).execute()

        # ajouts / maj is_primary
        for cid, isp in desired.items():
            if cid not in cur:
                touched_cats.add(id2slug.get(cid, str(cid)))
                touched_tools.add(slug)
                n_add += 1
                if not dry:
                    sb.table("tool_categories").upsert(
                        {"tool_id": tid, "category_id": cid, "is_primary": isp},
                        on_conflict="tool_id,category_id",
                    ).execute()
            elif cur[cid] != isp:
                touched_cats.add(id2slug.get(cid, str(cid)))
                touched_tools.add(slug)
                n_primary += 1
                if not dry:
                    sb.table("tool_categories").update({"is_primary": isp}) \
                        .eq("tool_id", tid).eq("category_id", cid).execute()

    tag = " [DRY-RUN]" if dry else ""
    print(f"== sync_categories{tag} ==")
    print(f"  +{n_add} lien(s) ajoute(s), -{n_del} retire(s), {n_primary} is_primary maj.")
    print(f"  {len(touched_tools)} outil(s) touche(s), {len(touched_cats)} categorie(s).")
    if touched_tools:
        print("  outils :", ", ".join(sorted(touched_tools)))
    if missing_cat:
        print("  ! categories absentes de Supabase (ignorees, A INSERER) :",
              ", ".join(sorted(missing_cat)))

    if not dry and (touched_tools or touched_cats):
        paths = ["/", "/categories"]
        for c in touched_cats:
            paths += [f"/best/{c}", f"/categories/{c}"]
        for s in touched_tools:
            paths.append(f"/tools/{s}")
        print("Revalidation...")
        revalidate(paths)

    print("Termine." + (" (rien ecrit, dry-run)" if dry else ""))


if __name__ == "__main__":
    main()
