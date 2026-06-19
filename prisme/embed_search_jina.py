# -*- coding: utf-8 -*-
"""embed_search_jina.py - Re-embed des outils publies pour la recherche
semantique, via Jina embeddings v3 (1024 dim, task=retrieval.passage), ecrit
dans la table Supabase search_embeddings. Tourne en local.

Pre-requis dans prisme/.env : SUPABASE_URL, SUPABASE_SERVICE_KEY, JINA_API_KEY.
Cle Jina gratuite (sans carte) : https://jina.ai/embeddings
Usage : python embed_search_jina.py [--dry-run]
"""
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
JINA_KEY = os.environ.get("JINA_API_KEY", "")
MODEL = "jina-embeddings-v3"
DIM = 1024


def make_text(t):
    parts = [t.get("name"), t.get("short_desc"), t.get("description_md")]
    return ". ".join(p for p in parts if p)[:8000]


def embed_batch(inputs, task):
    r = requests.post(
        "https://api.jina.ai/v1/embeddings",
        headers={"Authorization": f"Bearer {JINA_KEY}", "Content-Type": "application/json"},
        json={"model": MODEL, "task": task, "dimensions": DIM, "input": inputs},
        timeout=90,
    )
    r.raise_for_status()
    data = sorted(r.json()["data"], key=lambda d: d["index"])
    return [d["embedding"] for d in data]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not (SUPABASE_URL and SERVICE_KEY and JINA_KEY):
        sys.exit("Requis dans prisme/.env : SUPABASE_URL, SUPABASE_SERVICE_KEY, JINA_API_KEY")

    from supabase import create_client
    sb = create_client(SUPABASE_URL, SERVICE_KEY)

    res = sb.table("tools").select("id, name, short_desc, description_md").eq("status", "published").execute()
    tools = res.data or []
    print(f"[embed] {len(tools)} outil(s) a embed via {MODEL} (task=retrieval.passage, dim={DIM}).")
    if not tools:
        return
    if args.dry_run:
        for t in tools[:3]:
            print(f"  [dry-run] {t['id']} {t.get('name')} -> {make_text(t)[:80]}...")
        print("[embed] dry-run, rien ecrit.")
        return

    now = datetime.now(timezone.utc).isoformat()
    ok = 0
    B = 50
    for i in range(0, len(tools), B):
        chunk = tools[i:i + B]
        vecs = embed_batch([make_text(t) for t in chunk], "retrieval.passage")
        rows = [{"tool_id": t["id"], "embedding": v, "updated_at": now} for t, v in zip(chunk, vecs)]
        sb.table("search_embeddings").upsert(rows).execute()
        ok += len(rows)
        print(f"  upsert {ok}/{len(tools)}")
    print(f"[embed] termine : {ok} embedding(s) ecrits.")


if __name__ == "__main__":
    main()
