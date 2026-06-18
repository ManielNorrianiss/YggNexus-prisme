# -*- coding: utf-8 -*-
"""
publish_embeddings.py - Pousse les embeddings du staging vers Supabase.

Usage:
    python publish_embeddings.py
    python publish_embeddings.py --dry-run
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

SUPABASE_URL  = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY   = os.environ.get("SUPABASE_SERVICE_KEY", "")

import staging


def parse_vec(val):
    if isinstance(val, list):
        return val
    try:
        return json.loads(val)
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="Publie les embeddings vers Supabase")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    staging.init_db()
    rows = list(staging.iter_embeddings())

    if not rows:
        print("[publish_embeddings] Aucun embedding dans staging.")
        return

    print(f"[publish_embeddings] {len(rows)} embedding(s) trouves dans staging.")

    if args.dry_run:
        for r in rows:
            vec = parse_vec(r.get("embedding_json"))
            dim = len(vec) if vec else 0
            print(f"  [dry-run] {r['slug']} model={r['model']} dim={dim}")
        print("[dry-run] aucune ecriture.")
        return

    if not SUPABASE_URL or not SERVICE_KEY:
        sys.exit("SUPABASE_URL et SUPABASE_SERVICE_KEY requis dans prisme/.env")

    from supabase import create_client
    sb = create_client(SUPABASE_URL, SERVICE_KEY)

    nb_ok = 0
    nb_skip = 0
    nb_error = 0

    for r in rows:
        slug = r["slug"]
        vec  = parse_vec(r.get("embedding_json"))
        if not vec:
            print(f"  {slug}: embedding vide, ignore")
            nb_skip += 1
            continue

        res = sb.table("tools").select("id").eq("slug", slug).limit(1).execute()
        data = res.data if (res is not None and res.data) else []
        if not data:
            print(f"  {slug}: outil absent de Supabase (publie d'abord via publish.py), ignore")
            nb_skip += 1
            continue

        tool_id = data[0]["id"]
        try:
            sb.table("embeddings").upsert(
                {
                    "entity_type":  "tool",
                    "entity_id":    tool_id,
                    "model":        r.get("model", "nomic-embed-text"),
                    "embedding":    vec,
                    "content_hash": r.get("content_hash", ""),
                },
                on_conflict="entity_type,entity_id,model",
            ).execute()
            print(f"  upsert embedding {slug} (tool_id={tool_id})")
            nb_ok += 1
        except Exception as e:
            print(f"  ERREUR upsert {slug}: {e}")
            nb_error += 1

    print(f"\n[publish_embeddings] ok={nb_ok}, ignore={nb_skip}, erreur={nb_error}")


if __name__ == "__main__":
    main()
