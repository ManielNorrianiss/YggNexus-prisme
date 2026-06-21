# -*- coding: utf-8 -*-
"""
sync_tags_facets.py - synchronise Supabase tags/tool_tags/tool_facets depuis
data/tools.json (produit par b4_tagging + export_tools).

Strategie BATCH (full re-sync, idempotent) pour eviter l'epuisement des streams
HTTP/2 : on charge les maps en quelques lectures, on s'assure que les tags
existent (insert groupe des manquants), puis on VIDE tool_tags / tool_facets et
on REINSERE en paquets. tools.json est la source de verite.

Usage:
    python sync_tags_facets.py --dry-run
    python sync_tags_facets.py
    python sync_tags_facets.py --prune
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

SUPABASE_URL      = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY       = os.environ.get("SUPABASE_SERVICE_KEY", "")
SITE_URL          = os.environ.get("SITE_URL", "http://localhost:3000").rstrip("/")
REVALIDATE_SECRET = os.environ.get("REVALIDATE_SECRET", "")

CHUNK = 500


def load_tools():
    path = ROOT / "data" / "tools.json"
    raw = path.read_bytes().rstrip(b"\x00").rstrip()
    data = json.loads(raw)
    if not isinstance(data, list):
        sys.exit("data/tools.json doit etre une liste.")
    return data


def fetch_all(sb, table, columns):
    """Lecture paginee (PostgREST plafonne a 1000 lignes/requete)."""
    out = []
    start = 0
    page = 1000
    while True:
        rows = sb.table(table).select(columns).range(start, start + page - 1).execute().data or []
        out.extend(rows)
        if len(rows) < page:
            break
        start += page
    return out


def chunked(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


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
    ap = argparse.ArgumentParser(description="Sync tags/facets vers Supabase (batched)")
    ap.add_argument("--dry-run", action="store_true", help="N'ecrit rien, log les cibles")
    ap.add_argument("--prune", action="store_true", help="Supprime les tags orphelins (tool_count=0)")
    args = ap.parse_args()
    dry = args.dry_run

    if not SUPABASE_URL or not SERVICE_KEY:
        sys.exit("SUPABASE_URL / SUPABASE_SERVICE_KEY requis dans prisme/.env")

    tools = load_tools()
    from supabase import create_client
    sb = create_client(SUPABASE_URL, SERVICE_KEY)

    # --- Maps (quelques lectures paginees) ---
    db_facets = fetch_all(sb, "facets", "id,axis,slug")
    facet_key2id = {(f["axis"], f["slug"]): f["id"] for f in db_facets}
    db_tools = fetch_all(sb, "tools", "id,slug")
    slug2tid = {t["slug"]: t["id"] for t in db_tools}
    db_tags = fetch_all(sb, "tags", "id,slug")
    tag_slug2id = {t["slug"]: t["id"] for t in db_tags}

    # --- Outils publies + tags desires ---
    desired_tag_labels = {}
    pub = []
    missing_facets = set()
    for item in tools:
        if (item.get("status") or "published") != "published":
            continue
        slug = item.get("slug")
        tid = slug2tid.get(slug)
        if not tid:
            continue
        pub.append((slug, tid, item))
        for tag in (item.get("tags") or []):
            ts = tag.get("slug", "")
            if ts:
                desired_tag_labels.setdefault(ts, tag.get("label", ts))

    # --- S'assurer que les tags existent (insert groupe des manquants) ---
    missing_tags = [s for s in desired_tag_labels if s not in tag_slug2id]
    n_tags_add = len(missing_tags)
    if dry:
        print(f"  [dry] {n_tags_add} tag(s) a creer")
    else:
        rows = [{"slug": s, "name": desired_tag_labels[s], "name_fr": None,
                 "kind": "tag", "status": "published"} for s in missing_tags]
        for ch in chunked(rows, CHUNK):
            sb.table("tags").insert(ch).execute()
        if missing_tags:
            db_tags = fetch_all(sb, "tags", "id,slug")
            tag_slug2id = {t["slug"]: t["id"] for t in db_tags}

    # --- Construire les lignes de liaison desirees (dedupliquees) ---
    tt_seen = set()
    tf_seen = set()
    tt_rows = []
    tf_rows = []
    tag_count = {}
    for slug, tid, item in pub:
        for tag in (item.get("tags") or []):
            tgid = tag_slug2id.get(tag.get("slug", ""))
            if tgid is None:
                continue
            key = (tid, tgid)
            if key in tt_seen:
                continue
            tt_seen.add(key)
            tt_rows.append({"tool_id": tid, "tag_id": tgid})
            tag_count[tgid] = tag_count.get(tgid, 0) + 1
        for axis, slug_list in (item.get("facets") or {}).items():
            for fslug in (slug_list or []):
                fid = facet_key2id.get((axis, fslug))
                if fid is None:
                    missing_facets.add(f"{axis}/{fslug}")
                    continue
                key = (tid, fid)
                if key in tf_seen:
                    continue
                tf_seen.add(key)
                tf_rows.append({"tool_id": tid, "facet_id": fid})

    print(f"  cibles: {len(tt_rows)} tool_tags, {len(tf_rows)} tool_facets, {len(pub)} outils")

    if dry:
        print("  [dry] aucune ecriture (wipe + bulk insert au vrai run).")
    else:
        print("  wipe tool_tags / tool_facets...")
        sb.table("tool_tags").delete().gte("tool_id", 0).execute()
        sb.table("tool_facets").delete().gte("tool_id", 0).execute()
        print("  insert tool_tags...")
        for ch in chunked(tt_rows, CHUNK):
            sb.table("tool_tags").insert(ch).execute()
        print("  insert tool_facets...")
        for ch in chunked(tf_rows, CHUNK):
            sb.table("tool_facets").insert(ch).execute()
        print("  maj tags.tool_count...")
        for tgid, cnt in tag_count.items():
            sb.table("tags").update({"tool_count": cnt}).eq("id", tgid).execute()
        used = set(tag_count.keys())
        for t in db_tags:
            if t["id"] not in used:
                sb.table("tags").update({"tool_count": 0}).eq("id", t["id"]).execute()

    if args.prune and not dry:
        print("  prune tags orphelins (tool_count=0)...")
        orphans = sb.table("tags").select("id,slug").eq("tool_count", 0).execute().data or []
        for o in orphans:
            sb.table("tags").delete().eq("id", o["id"]).execute()
            print(f"    DELETE {o['slug']}")

    suffix = " [DRY-RUN]" if dry else ""
    print(f"== sync_tags_facets{suffix} ==")
    print(f"  tags crees: +{n_tags_add}")
    print(f"  tool_tags: {len(tt_rows)} | tool_facets: {len(tf_rows)} | outils: {len(pub)}")
    if missing_facets:
        print(f"  ! facettes inconnues (ignorees): {', '.join(sorted(missing_facets))}")

    if not dry:
        revalidate(["/", "/tools", "/tags"])
    print("Termine." + (" (rien ecrit, dry-run)" if dry else ""))


if __name__ == "__main__":
    main()
