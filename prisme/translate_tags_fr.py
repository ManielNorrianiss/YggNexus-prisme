# -*- coding: utf-8 -*-
"""translate_tags_fr.py - traduit le libelle EN des tags visibles vers name_fr.

On ne traduit QUE les tags visibles : status='published' ET canonical_id IS NULL.
Les alias archives (canonical_id renseigne) ne sont jamais traduits.

Pre-requis dans prisme/.env : SUPABASE_URL, SUPABASE_SERVICE_KEY, REVALIDATE_SECRET, SITE_URL.

Flux humain :
    1) python translate_tags_fr.py            # dump (defaut), ecrit data/tags_to_translate.json
    2) traduction : remplir data/tags_fr.json (name -> name_fr)
    3) python translate_tags_fr.py --apply    # ecrit name_fr dans Supabase + revalide /fr

Options :
    --dump           Dump explicite (defaut).
    --apply          Applique data/tags_fr.json (sinon dump).
    --force          (avec --dump) inclut aussi les tags ayant deja un name_fr.
    --no-revalidate  Saute la revalidation ISR.
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
except Exception:
    pass

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SITE_URL = os.environ.get("SITE_URL", "http://localhost:3000").rstrip("/")
REVALIDATE_SECRET = os.environ.get("REVALIDATE_SECRET", "")

DUMP_PATH = ROOT / "data" / "tags_to_translate.json"
FR_PATH = ROOT / "data" / "tags_fr.json"

REVAL_PATHS = ["/fr", "/fr/tags", "/fr/tools"]


def fetch_visible_tags(sb, force):
    """Lecture paginee des tags visibles (PostgREST plafonne a 1000 lignes)."""
    out = []
    start = 0
    page = 1000
    while True:
        q = (sb.table("tags").select("id,slug,name,name_fr")
             .eq("status", "published").is_("canonical_id", "null"))
        rows = q.range(start, start + page - 1).execute().data or []
        out.extend(rows)
        if len(rows) < page:
            break
        start += page
    out = [t for t in out if t.get("id") is not None]
    if not force:
        out = [t for t in out if not (t.get("name_fr") or "").strip()]
    return out


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
    except requests.RequestException as e:
        print(f"  revalidate : site injoignable ({e}).")


def run_dump(sb, force):
    tags = fetch_visible_tags(sb, force)
    payload = sorted(
        ({"id": int(t["id"]), "slug": t["slug"], "name": t["name"]} for t in tags),
        key=lambda d: d["slug"],
    )
    DUMP_PATH.parent.mkdir(parents=True, exist_ok=True)
    DUMP_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    mode = "tous" if force else "name_fr IS NULL"
    print(f"== translate_tags_fr [DUMP] ({mode}) ==")
    print(f"  tags a traduire : {len(payload)}")
    print(f"  ecrit -> {DUMP_PATH}")
    print("  AUCUNE ecriture DB. Remplis data/tags_fr.json, puis relance avec --apply.")


def load_fr_map():
    """Accepte un dict {\"<id>\": \"<name_fr>\"} OU une liste [{\"id\":..,\"name_fr\":..}]."""
    if not FR_PATH.exists():
        sys.exit(f"{FR_PATH} absent : fais d'abord un dump, traduis, puis relance --apply.")
    raw = FR_PATH.read_bytes().rstrip(b"\x00").rstrip()
    data = json.loads(raw)
    fr = {}
    if isinstance(data, dict):
        for k, v in data.items():
            name_fr = (v or "").strip() if isinstance(v, str) else ""
            try:
                tid = int(k)
            except (TypeError, ValueError):
                continue
            if name_fr:
                fr[tid] = name_fr
    elif isinstance(data, list):
        for row in data:
            if not isinstance(row, dict):
                continue
            try:
                tid = int(row.get("id"))
            except (TypeError, ValueError):
                continue
            name_fr = (row.get("name_fr") or "").strip()
            if name_fr:
                fr[tid] = name_fr
    else:
        sys.exit("data/tags_fr.json doit etre un dict {id: name_fr} ou une liste d'objets.")
    return fr


def run_apply(sb, do_revalidate):
    fr = load_fr_map()
    if not fr:
        sys.exit("data/tags_fr.json ne contient aucune traduction utilisable.")
    items = sorted(fr.items())
    total = len(items)
    updated = 0
    skipped = 0
    for tid, name_fr in items:
        value = (name_fr or "").strip()
        if not value:
            skipped += 1
            continue
        (sb.table("tags")
         .update({"name_fr": value})
         .eq("id", tid)
         .execute())
        updated += 1
        if updated % 200 == 0:
            print(f"  ... {updated}/{total}")
    print("== translate_tags_fr --apply ==")
    print(f"  tags mis a jour (name_fr) : {updated}")
    if skipped:
        print(f"  entrees ignorees (valeur vide) : {skipped}")
    if do_revalidate:
        revalidate(REVAL_PATHS)
    else:
        print("  (--no-revalidate : revalidation ignoree)")
    print("Termine.")


def main():
    ap = argparse.ArgumentParser(
        description="Traduit name (EN) -> name_fr pour les tags visibles."
    )
    ap.add_argument("--apply", action="store_true", help="Applique data/tags_fr.json (sinon dump).")
    ap.add_argument("--dump", action="store_true", help="Dump explicite (defaut).")
    ap.add_argument("--force", action="store_true",
                    help="(avec --dump) inclut aussi les tags ayant deja un name_fr.")
    ap.add_argument("--no-revalidate", action="store_true", help="Saute la revalidation ISR.")
    args = ap.parse_args()

    if not SUPABASE_URL or not SERVICE_KEY:
        sys.exit("SUPABASE_URL / SUPABASE_SERVICE_KEY requis dans prisme/.env")

    from supabase import create_client
    sb = create_client(SUPABASE_URL, SERVICE_KEY)

    if args.apply:
        run_apply(sb, do_revalidate=not args.no_revalidate)
    else:
        run_dump(sb, args.force)


if __name__ == "__main__":
    main()
