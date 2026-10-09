# -*- coding: utf-8 -*-
"""
fusion_tags.py - regroupe les quasi-doublons parmi les tags publies via
embeddings Jina v3, designe un tag CANONIQUE par grappe et archive les alias.

Strategie BATCH (idempotent) pour eviter l'epuisement des streams HTTP/2 :
on supprime / reinsere tool_tags par paquets, jamais ligne par ligne.

Pre-requis dans prisme/.env : SUPABASE_URL, SUPABASE_SERVICE_KEY, JINA_API_KEY.

Flux humain :
    1) python fusion_tags.py                 # dry-run (defaut), ecrit data/tag_merges.json
    2) revue manuelle de data/tag_merges.json (source de verite de l'application)
    3) python fusion_tags.py --apply         # applique le JSON tel quel

Options :
    --threshold 0.88   seuil de cosine pour le clustering (dry-run seulement)
    --only SLUG        restreint le clustering aux grappes touchant ce slug
    --no-revalidate    saute la revalidation ISR
"""
import os
import sys
import json
import math
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

import requests

SUPABASE_URL      = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY       = os.environ.get("SUPABASE_SERVICE_KEY", "")
JINA_KEY          = os.environ.get("JINA_API_KEY", "")
SITE_URL          = os.environ.get("SITE_URL", "http://localhost:3000").rstrip("/")
REVALIDATE_SECRET = os.environ.get("REVALIDATE_SECRET", "")

MODEL = "jina-embeddings-v3"
DIM = 1024
CHUNK = 500          # paquets d'ecriture Supabase
EMBED_BATCH = 100    # labels par requete Jina
MERGES_PATH = ROOT / "data" / "tag_merges.json"

REVAL_PATHS = ["/", "/tools", "/tags", "/fr", "/fr/tools", "/fr/tags"]


def chunked(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def fetch_all(sb, table, columns, status=None, canonical_null=False):
    """Lecture paginee (PostgREST plafonne a 1000 lignes/requete)."""
    out = []
    start = 0
    page = 1000
    while True:
        q = sb.table(table).select(columns)
        if status is not None:
            q = q.eq("status", status)
        if canonical_null:
            q = q.is_("canonical_id", "null")
        rows = q.range(start, start + page - 1).execute().data or []
        out.extend(rows)
        if len(rows) < page:
            break
        start += page
    return out


def embed_labels(labels):
    """Embed des labels via Jina v3, en chunkant les appels (EMBED_BATCH)."""
    vecs = []
    for ch in chunked(labels, EMBED_BATCH):
        r = requests.post(
            "https://api.jina.ai/v1/embeddings",
            headers={"Authorization": f"Bearer {JINA_KEY}", "Content-Type": "application/json"},
            json={"model": MODEL, "task": "retrieval.passage", "dimensions": DIM, "input": ch},
            timeout=90,
        )
        r.raise_for_status()
        data = sorted(r.json()["data"], key=lambda d: d["index"])
        vecs.extend(d["embedding"] for d in data)
    return vecs


def normalize(v):
    n = math.sqrt(sum(x * x for x in v))
    if n == 0:
        return v
    return [x / n for x in v]


def cosine_norm(a, b):
    # a et b deja normalises -> cosine = produit scalaire
    return sum(x * y for x, y in zip(a, b))


def pick_canonical(tags):
    """Canonique = plus gros tool_count ; egalite -> slug le plus court ; puis alpha."""
    return sorted(
        tags,
        key=lambda t: (-(t.get("tool_count") or 0), len(t["slug"]), t["slug"]),
    )[0]


def cluster(tags, vecs, threshold):
    """Clustering greedy par cosine >= threshold. Retourne une liste de grappes
    (chaque grappe = liste de tags)."""
    n = len(tags)
    norms = [normalize(v) for v in vecs]
    assigned = [False] * n
    clusters = []
    for i in range(n):
        if assigned[i]:
            continue
        members = [i]
        assigned[i] = True
        for j in range(i + 1, n):
            if assigned[j]:
                continue
            if cosine_norm(norms[i], norms[j]) >= threshold:
                members.append(j)
                assigned[j] = True
        clusters.append([tags[k] for k in members])
    return clusters


def build_merges(tags, vecs, threshold, only_slug):
    clusters = cluster(tags, vecs, threshold)
    merges = []
    for grp in clusters:
        if len(grp) < 2:
            continue
        if only_slug and not any(t["slug"] == only_slug for t in grp):
            continue
        canon = pick_canonical(grp)
        if canon.get("id") is None:
            continue
        cnorm = normalize(next(v for t, v in zip(tags, vecs) if t["id"] == canon["id"]))
        aliases = []
        for t in grp:
            if t["id"] == canon["id"]:
                continue
            tnorm = normalize(next(v for tt, v in zip(tags, vecs) if tt["id"] == t["id"]))
            score = round(cosine_norm(cnorm, tnorm), 4)
            aliases.append({
                "id": t["id"], "slug": t["slug"], "name": t["name"],
                "tool_count": t.get("tool_count") or 0, "score": score,
            })
        merges.append({
            "canonical": {
                "id": canon["id"], "slug": canon["slug"], "name": canon["name"],
                "tool_count": canon.get("tool_count") or 0,
            },
            "aliases": sorted(aliases, key=lambda a: -a["score"]),
        })
    return merges


def revalidate():
    if not REVALIDATE_SECRET:
        print("  (pas de REVALIDATE_SECRET : revalidation ignoree)")
        return
    try:
        r = requests.post(
            f"{SITE_URL}/api/revalidate",
            json={"paths": sorted(set(REVAL_PATHS))},
            headers={"Authorization": f"Bearer {REVALIDATE_SECRET}"},
            timeout=20,
        )
        print(f"  revalidate -> {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"  revalidate : injoignable ({e})")


def run_dry(sb, threshold, only_slug):
    tags = fetch_all(sb, "tags", "id,slug,name,tool_count",
                     status="published", canonical_null=True)
    tags = [t for t in tags if t.get("id") is not None]
    print(f"[fusion] {len(tags)} tag(s) publie(s) sans canonical_id.")
    if not tags:
        return
    if not JINA_KEY:
        sys.exit("JINA_API_KEY requis dans prisme/.env pour le clustering.")
    print(f"[fusion] embed via {MODEL} (task=retrieval.passage, dim={DIM})...")
    vecs = embed_labels([t["name"] for t in tags])
    merges = build_merges(tags, vecs, threshold, only_slug)

    n_clusters = len(merges)
    n_merged = sum(len(m["aliases"]) for m in merges)
    remaining = len(tags) - n_merged
    MERGES_PATH.parent.mkdir(parents=True, exist_ok=True)
    MERGES_PATH.write_text(
        json.dumps(merges, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"== fusion_tags [DRY-RUN] (threshold={threshold}) ==")
    print(f"  grappes (>=2): {n_clusters}")
    print(f"  tags fusionnes (alias): {n_merged}")
    print(f"  tags restants apres fusion: {remaining}")
    print(f"  ecrit -> {MERGES_PATH}")
    print("  AUCUNE ecriture DB. Revois le JSON, puis relance avec --apply.")


def fetch_tag_status(sb):
    rows = fetch_all(sb, "tags", "id,status")
    return {r["id"]: r.get("status") for r in rows}


def count_distinct_tools(sb, tag_id):
    rows = []
    start = 0
    page = 1000
    while True:
        chunk = (sb.table("tool_tags").select("tool_id")
                 .eq("tag_id", tag_id).range(start, start + page - 1)
                 .execute().data or [])
        rows.extend(chunk)
        if len(chunk) < page:
            break
        start += page
    return len({r["tool_id"] for r in rows})


def run_apply(sb, do_revalidate):
    if not MERGES_PATH.exists():
        sys.exit(f"{MERGES_PATH} absent : lance d'abord un dry-run, puis revois le JSON.")
    raw = MERGES_PATH.read_bytes().rstrip(b"\x00").rstrip()
    merges = json.loads(raw)
    if not isinstance(merges, list):
        sys.exit("data/tag_merges.json doit etre une liste.")

    status_map = fetch_tag_status(sb)
    applied = 0
    skipped = 0
    for m in merges:
        canon = m.get("canonical") or {}
        cid = canon.get("id")
        if cid is None:
            print("  ! grappe sans canonical.id -> sautee")
            continue
        aliases = [a for a in (m.get("aliases") or []) if a.get("id") is not None]
        # alias deja archives -> sautes (idempotence)
        live_aliases = [a for a in aliases if status_map.get(a["id"]) != "archived"]
        if not live_aliases:
            skipped += 1
            continue
        alias_ids = [a["id"] for a in live_aliases]

        # a. tool_id des alias a rattacher au canonical
        tool_ids = set()
        for aid in alias_ids:
            start = 0
            page = 1000
            while True:
                chunk = (sb.table("tool_tags").select("tool_id")
                         .eq("tag_id", aid).range(start, start + page - 1)
                         .execute().data or [])
                tool_ids.update(r["tool_id"] for r in chunk)
                if len(chunk) < page:
                    break
                start += page

        # b. supprimer les lignes alias en BATCH, puis upsert (ignore) vers canonical
        for ch in chunked(alias_ids, CHUNK):
            sb.table("tool_tags").delete().in_("tag_id", ch).execute()
        new_rows = [{"tool_id": tid, "tag_id": cid} for tid in sorted(tool_ids)]
        for ch in chunked(new_rows, CHUNK):
            (sb.table("tool_tags")
             .upsert(ch, on_conflict="tool_id,tag_id", ignore_duplicates=True)
             .execute())

        # c. archiver les alias
        for aid in alias_ids:
            sb.table("tags").update(
                {"canonical_id": cid, "status": "archived"}
            ).eq("id", aid).execute()
            status_map[aid] = "archived"

        # d. recalculer tool_count du canonical
        cnt = count_distinct_tools(sb, cid)
        sb.table("tags").update({"tool_count": cnt}).eq("id", cid).execute()

        applied += 1
        print(f"  fusion -> canonical {canon.get('slug')} (#{cid}) "
              f"| {len(alias_ids)} alias | tool_count={cnt}")

    print(f"== fusion_tags --apply ==")
    print(f"  grappes appliquees: {applied} | grappes deja faites (sautees): {skipped}")

    if do_revalidate:
        revalidate()
    else:
        print("  (--no-revalidate : revalidation ignoree)")
    print("Termine.")


def main():
    ap = argparse.ArgumentParser(description="Fusion des quasi-doublons de tags via embeddings Jina.")
    ap.add_argument("--apply", action="store_true", help="Applique data/tag_merges.json (sinon dry-run).")
    ap.add_argument("--dry-run", action="store_true", help="Dry-run explicite (defaut).")
    ap.add_argument("--threshold", type=float, default=0.88, help="Seuil cosine (dry-run).")
    ap.add_argument("--only", metavar="SLUG", default=None, help="Restreint aux grappes touchant ce slug.")
    ap.add_argument("--no-revalidate", action="store_true", help="Saute la revalidation ISR.")
    args = ap.parse_args()

    if not SUPABASE_URL or not SERVICE_KEY:
        sys.exit("SUPABASE_URL / SUPABASE_SERVICE_KEY requis dans prisme/.env")

    from supabase import create_client
    sb = create_client(SUPABASE_URL, SERVICE_KEY)

    if args.apply:
        run_apply(sb, do_revalidate=not args.no_revalidate)
    else:
        run_dry(sb, args.threshold, args.only)


if __name__ == "__main__":
    main()
