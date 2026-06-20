# -*- coding: utf-8 -*-
"""
nettoyage_automation.py - retire le tag 'automation' parasite (sur-etiquetage B4).
Garde 'automation' UNIQUEMENT pour la whitelist (vraies plateformes d'orchestration).
Nettoie Supabase ET staging.db, promeut un nouveau primary si besoin,
garde-fou anti-orphelin (ne retire jamais la derniere categorie d'un outil),
puis revalide les pages touchees.

Usage:
    python nettoyage_automation.py --dry-run   # montre tout, n'ecrit rien
    python nettoyage_automation.py             # applique (Supabase + staging) + revalidation
    python nettoyage_automation.py --skip-staging   # Supabase seulement
"""
import os
import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

import staging

WHITELIST = {
    "zapier", "make", "n8n", "workato", "pipedream", "ifttt",
    "activepieces", "gumloop", "bardeen", "lindy", "relevance-ai",
}
TARGET = "automation"

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SITE_URL = os.environ.get("SITE_URL", "http://localhost:3000").rstrip("/")
REVALIDATE_SECRET = os.environ.get("REVALIDATE_SECRET", "")


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
            timeout=15,
        )
        print(f"  revalidate -> {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"  revalidate : injoignable ({e})")


def clean_supabase(dry):
    from supabase import create_client
    sb = create_client(SUPABASE_URL, SERVICE_KEY)
    rc = sb.table("categories").select("id").eq("slug", TARGET).limit(1).execute()
    if not rc.data:
        print("Categorie 'automation' introuvable dans Supabase.")
        return [], []
    auto_id = rc.data[0]["id"]
    cats = sb.table("categories").select("id,slug").execute().data or []
    id2slug = {c["id"]: c["slug"] for c in cats}
    tools = sb.table("tools").select("id,slug").execute().data or []
    tid2slug = {t["id"]: t["slug"] for t in tools}
    links = (sb.table("tool_categories").select("tool_id,is_primary")
             .eq("category_id", auto_id).execute().data or [])

    removed, orphans = [], []
    for ln in links:
        tid = ln["tool_id"]
        slug = tid2slug.get(tid, str(tid))
        if slug in WHITELIST:
            continue
        allrows = (sb.table("tool_categories").select("category_id,is_primary")
                   .eq("tool_id", tid).execute().data or [])
        others = [r for r in allrows if r["category_id"] != auto_id]
        if not others:
            orphans.append(slug)
            continue
        was_primary = any(r["category_id"] == auto_id and r["is_primary"] for r in allrows)
        new_primary_id = None
        if was_primary and not any(r["is_primary"] for r in others):
            new_primary_id = sorted(others, key=lambda r: r["category_id"])[0]["category_id"]
        removed.append((slug, id2slug.get(new_primary_id) if new_primary_id else None))
        if dry:
            continue
        sb.table("tool_categories").delete().eq("tool_id", tid).eq("category_id", auto_id).execute()
        if new_primary_id:
            (sb.table("tool_categories").update({"is_primary": True})
             .eq("tool_id", tid).eq("category_id", new_primary_id).execute())
    return removed, orphans


def clean_staging(dry):
    try:
        rows = list(staging.iter_tool_categories())
    except Exception as e:
        print(f"  staging illisible ({e}) -> nettoyage staging saute")
        return [], []
    bytool = {}
    for r in rows:
        bytool.setdefault(r["tool_slug"], []).append(r)
    removed, orphans = [], []
    for slug, trows in bytool.items():
        if slug in WHITELIST:
            continue
        if not any(r["category_slug"] == TARGET for r in trows):
            continue
        others = [r for r in trows if r["category_slug"] != TARGET]
        if not others:
            orphans.append(slug)
            continue
        was_primary = any(r["category_slug"] == TARGET and r.get("is_primary") for r in trows)
        if was_primary and not any(r.get("is_primary") for r in others):
            np = sorted(others, key=lambda r: r["category_slug"])[0]
            np["is_primary"] = 1
        removed.append(slug)
        if not dry:
            staging.replace_tool_categories(slug, others)
    return removed, orphans


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-staging", action="store_true")
    ap.add_argument("--skip-supabase", action="store_true")
    args = ap.parse_args()
    dry = args.dry_run
    tag = " [DRY-RUN]" if dry else ""
    print(f"== Nettoyage 'automation' (whitelist={len(WHITELIST)} outils){tag} ==")

    sup_removed, sup_orphans = [], []
    if not args.skip_supabase:
        if not SUPABASE_URL or not SERVICE_KEY:
            print("SUPABASE_URL / SUPABASE_SERVICE_KEY manquants -> Supabase saute")
        else:
            sup_removed, sup_orphans = clean_supabase(dry)

    st_removed, st_orphans = [], []
    if not args.skip_staging:
        st_removed, st_orphans = clean_staging(dry)

    print(f"\nSupabase : {len(sup_removed)} tag(s) automation retire(s), "
          f"{len(sup_orphans)} orphelin(s) garde(s).")
    for slug, np in sorted(sup_removed):
        extra = f"  (nouveau primary: {np})" if np else ""
        print(f"  - {slug}{extra}")
    if sup_orphans:
        print("  ! orphelins (automation = seule categorie, A RECLASSER, non touches) :")
        for s in sorted(sup_orphans):
            print(f"      {s}")

    print(f"\nstaging.db : {len(st_removed)} tag(s) retire(s), {len(st_orphans)} orphelin(s).")
    for s in sorted(st_removed):
        print(f"  - {s}")
    if st_orphans:
        print("  ! orphelins staging :", ", ".join(sorted(st_orphans)))

    if not dry and not args.skip_supabase and (sup_removed or sup_orphans):
        paths = ["/", "/categories", f"/best/{TARGET}", f"/categories/{TARGET}"]
        for slug, np in sup_removed:
            paths.append(f"/tools/{slug}")
            if np:
                paths += [f"/best/{np}", f"/categories/{np}"]
        print("\nRevalidation...")
        revalidate(paths)

    print("\nTermine." + (" (rien ecrit, dry-run)" if dry else ""))


if __name__ == "__main__":
    main()
