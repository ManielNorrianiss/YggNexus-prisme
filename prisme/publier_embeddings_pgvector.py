# -*- coding: utf-8 -*-
"""
publier_embeddings_pgvector.py - Pont pgvector : pousse les embeddings
nomic-embed-text (768 dim) du staging local vers la table Supabase
`embeddings` (colonne pgvector deja portee a vector(768), cf.
database/migration_embeddings_dim_768.sql), par lots, pour alimenter la RPC
search_tools_semantic (database/migration_pgvector_search.sql).

Complementaire de publish_embeddings.py (meme source, meme table cible) :
ce script est dedie au chantier de recherche semantique locale -- il ajoute
--limit/--only pour des republications ciblees et un affichage plus verbeux
du payload envoye, utile pour verifier le pont pgvector independamment du
run nightly complet.

Usage:
    python publier_embeddings_pgvector.py
    python publier_embeddings_pgvector.py --dry-run
    python publier_embeddings_pgvector.py --limit 50
    python publier_embeddings_pgvector.py --only mon-outil-slug
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
from llm_local import EMBED_DIM

BATCH_SIZE = 100


def parse_vec(val):
    """Parse une valeur d'embedding stockee en staging (liste ou JSON str)."""
    if isinstance(val, list):
        return val
    try:
        return json.loads(val)
    except Exception:
        return None


def charger_lignes(only=None, limit=0):
    """
    Charge les lignes d'embeddings depuis staging (tool_embeddings),
    optionnellement filtrees par slug (--only) et bornees (--limit).
    Retourne une liste de dicts {slug, model, embedding_json, content_hash}.
    """
    rows = list(staging.iter_embeddings())
    if only:
        rows = [r for r in rows if r["slug"] == only]
    if limit and limit > 0:
        rows = rows[:limit]
    return rows


def construire_payload(slug, tool_id, vec, model, content_hash):
    """
    Construit le dict envoye a sb.table("embeddings").upsert(...) pour une
    ligne. Isole ici (sans reseau) pour etre teste directement.
    """
    return {
        "entity_type":  "tool",
        "entity_id":    tool_id,
        "model":        model,
        "embedding":    vec,
        "content_hash": content_hash or "",
    }


def resoudre_tool_ids(sb, slugs):
    """
    Resout {slug: tool_id} pour un ensemble de slugs via une seule requete
    Supabase paginee implicitement par la clause .in_().
    """
    mapping = {}
    CHUNK = 200
    slugs = list(slugs)
    for i in range(0, len(slugs), CHUNK):
        chunk = slugs[i:i + CHUNK]
        res = sb.table("tools").select("id,slug").in_("slug", chunk).execute()
        data = res.data if (res is not None and res.data) else []
        for row in data:
            mapping[row["slug"]] = row["id"]
    return mapping


def publier_par_lots(sb, rows, dry_run=False, batch_size=BATCH_SIZE):
    """
    Publie les lignes (deja jointes a tool_id) par lots de batch_size via
    upsert Supabase. rows : liste de payloads (sortie de construire_payload).
    Retourne (nb_ok, nb_error).
    """
    nb_ok = 0
    nb_error = 0
    for i in range(0, len(rows), batch_size):
        lot = rows[i:i + batch_size]
        if dry_run:
            nb_ok += len(lot)
            continue
        try:
            sb.table("embeddings").upsert(
                lot, on_conflict="entity_type,entity_id,model"
            ).execute()
            nb_ok += len(lot)
            print(f"  upsert lot {i // batch_size + 1} ({len(lot)} ligne(s))")
        except Exception as e:
            print(f"  ERREUR upsert lot {i // batch_size + 1}: {e}")
            nb_error += len(lot)
    return nb_ok, nb_error


def main():
    parser = argparse.ArgumentParser(
        description="Pont pgvector : publie les embeddings nomic 768d du staging vers Supabase (table embeddings)."
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Affiche ce qui serait publie, n'ecrit rien.")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limite le nombre de lignes traitees (0 = toutes, defaut).")
    parser.add_argument("--only", type=str, default="",
                        help="Limiter a un seul outil (slug).")
    args = parser.parse_args()

    staging.init_db()
    rows = charger_lignes(only=args.only or None, limit=args.limit)

    if not rows:
        print("[pgvector] Aucun embedding trouve dans staging (filtre applique).")
        return

    print(f"[pgvector] {len(rows)} embedding(s) trouve(s) dans staging.")

    if args.dry_run:
        for r in rows:
            vec = parse_vec(r.get("embedding_json"))
            dim = len(vec) if vec else 0
            statut = "OK" if dim == EMBED_DIM else f"DIM INATTENDUE (attendu {EMBED_DIM})"
            print(f"  [dry-run] {r['slug']} model={r.get('model')} dim={dim} {statut}")
        print("[dry-run] aucune ecriture.")
        return

    if not SUPABASE_URL or not SERVICE_KEY:
        sys.exit("SUPABASE_URL et SUPABASE_SERVICE_KEY requis dans prisme/.env")

    from supabase import create_client
    sb = create_client(SUPABASE_URL, SERVICE_KEY)

    slugs = [r["slug"] for r in rows]
    print("[pgvector] Resolution des tool_id Supabase...")
    tool_ids = resoudre_tool_ids(sb, slugs)

    payloads = []
    nb_skip = 0
    for r in rows:
        slug = r["slug"]
        vec = parse_vec(r.get("embedding_json"))
        if not vec:
            print(f"  {slug}: embedding vide, ignore")
            nb_skip += 1
            continue
        tool_id = tool_ids.get(slug)
        if tool_id is None:
            print(f"  {slug}: outil absent de Supabase (publie d'abord via publish.py), ignore")
            nb_skip += 1
            continue
        payloads.append(construire_payload(
            slug, tool_id, vec, r.get("model", "nomic-embed-text"), r.get("content_hash", "")
        ))

    print(f"[pgvector] {len(payloads)} ligne(s) pretes pour l'upsert par lots (taille lot={BATCH_SIZE}).")
    nb_ok, nb_error = publier_par_lots(sb, payloads)

    print(f"\n[pgvector] ok={nb_ok}, ignore={nb_skip}, erreur={nb_error}")


if __name__ == "__main__":
    main()
