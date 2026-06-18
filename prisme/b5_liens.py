# -*- coding: utf-8 -*-
"""
b5_liens.py - Batch B5 : calcul des liens semantiques (alternatives) par similarite cosinus.

Lit les embeddings depuis Supabase (table embeddings, entity_type='tool'),
calcule la similarite cosinus entre tous les outils publies,
et ecrit les top-N alternatives dans la table alternatives.

Usage:
    python b5_liens.py
    python b5_liens.py --dry-run
    python b5_liens.py --top 5 --threshold 0.55
    python b5_liens.py --only my-tool-slug
    python b5_liens.py --limit 10
    python b5_liens.py --model nomic-embed-text
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY  = os.environ.get("SUPABASE_SERVICE_KEY", "")

# ---------------------------------------------------------------------------
# Cosine similarity helpers (numpy required)
# ---------------------------------------------------------------------------

def ensure_numpy():
    """Import numpy, install if missing."""
    try:
        import numpy as np
        return np
    except ImportError:
        import subprocess
        print("[B5] numpy absent -- installation en cours...")
        subprocess.check_call([sys.executable, "-m", "pip", "install",
                               "numpy", "--break-system-packages"],
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)
        import numpy as np
        return np


def cosine_matrix(np, vectors):
    """
    Compute a cosine similarity matrix for a list of vectors.
    vectors: list of 1-D array-like of the same dimension.
    Returns a 2-D numpy array of shape (N, N).
    """
    mat = np.array(vectors, dtype=float)
    # Normalize each row
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    # Avoid division by zero
    norms = np.where(norms == 0, 1.0, norms)
    mat_norm = mat / norms
    # Dot product -> cosine similarity
    return mat_norm @ mat_norm.T


def clamp_similarity(val):
    """Round to 3 decimals and cap at 9.999 (NUMERIC(4,3) constraint)."""
    val = round(float(val), 3)
    return min(val, 9.999)


# ---------------------------------------------------------------------------
# Data loading from Supabase
# ---------------------------------------------------------------------------

def load_tools(sb):
    """Return list of published tools: [{id, slug, name}, ...]."""
    res = sb.table("tools") \
            .select("id,slug,name") \
            .eq("status", "published") \
            .execute()
    return res.data if (res is not None and res.data) else []


def load_embeddings(sb, model):
    """
    Return dict {entity_id (int): [float, ...]} for entity_type='tool'.
    Uses pagination to handle large catalogs.
    """
    PAGE = 1000
    offset = 0
    emb_map = {}
    while True:
        res = sb.table("embeddings") \
                .select("entity_id,embedding") \
                .eq("entity_type", "tool") \
                .eq("model", model) \
                .range(offset, offset + PAGE - 1) \
                .execute()
        batch = res.data if (res is not None and res.data) else []
        for row in batch:
            eid = row["entity_id"]
            vec = row["embedding"]
            # embedding may be stored as a list or a JSON string
            if isinstance(vec, str):
                import json
                vec = json.loads(vec)
            if vec:
                emb_map[eid] = vec
        if len(batch) < PAGE:
            break
        offset += PAGE
    return emb_map


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def compute_alternatives(np, tools_with_vec, top_n, threshold):
    """
    Given a list of (tool_id, slug, name, vector), compute alternatives.
    Returns dict: {tool_id: [(alt_id, alt_slug, similarity), ...]}
    sorted descending by similarity, capped at top_n, filtered by threshold.
    """
    ids    = [t[0] for t in tools_with_vec]
    slugs  = [t[1] for t in tools_with_vec]
    vecs   = [t[3] for t in tools_with_vec]

    sim_mat = cosine_matrix(np, vecs)
    n = len(ids)

    result = {}
    for i in range(n):
        candidates = []
        for j in range(n):
            if i == j:
                continue
            sim = clamp_similarity(sim_mat[i][j])
            if sim >= threshold:
                candidates.append((ids[j], slugs[j], sim))
        # Sort descending by similarity
        candidates.sort(key=lambda x: x[2], reverse=True)
        result[ids[i]] = candidates[:top_n]

    return result


# ---------------------------------------------------------------------------
# Supabase writes
# ---------------------------------------------------------------------------

def write_alternatives(sb, tool_id, tool_slug, alts, dry_run):
    """
    Delete existing rows for tool_id, then insert new alternatives.
    alts: list of (alt_id, alt_slug, similarity)
    """
    if dry_run:
        print(f"  [dry-run] {tool_slug} -> {len(alts)} alternative(s):")
        for alt_id, alt_slug, sim in alts:
            reason = "semantic similarity (cosine {:.3f})".format(sim)
            print(f"    {alt_slug} sim={sim} reason=\"{reason}\"")
        return len(alts)

    # Delete existing links for this tool
    sb.table("alternatives") \
      .delete() \
      .eq("tool_id", tool_id) \
      .execute()

    if not alts:
        return 0

    rows = []
    for alt_id, alt_slug, sim in alts:
        reason = "semantic similarity (cosine {:.3f})".format(sim)
        rows.append({
            "tool_id":        tool_id,
            "alternative_id": alt_id,
            "similarity":     sim,
            "reason":         reason,
        })

    sb.table("alternatives").insert(rows).execute()
    return len(rows)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="Batch B5 liens semantiques")
    parser.add_argument("--dry-run",    action="store_true",
                        help="Calcule et affiche les resultats, n'ecrit rien.")
    parser.add_argument("--top",        type=int,   default=5,
                        help="Nb max d'alternatives par outil (defaut: 5)")
    parser.add_argument("--threshold",  type=float, default=0.55,
                        help="Seuil cosinus minimum (defaut: 0.55)")
    parser.add_argument("--only",       type=str,   default="",
                        help="Limiter a un seul outil (slug)")
    parser.add_argument("--limit",      type=int,   default=0,
                        help="Limiter le nb d'outils traites")
    parser.add_argument("--model",      type=str,   default="nomic-embed-text",
                        help="Modele d'embedding (defaut: nomic-embed-text)")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    # Validate Supabase creds (only required for real writes)
    if not args.dry_run:
        if not SUPABASE_URL or not SERVICE_KEY:
            sys.exit("SUPABASE_URL et SUPABASE_SERVICE_KEY requis dans prisme/.env")

    np = ensure_numpy()

    if not SUPABASE_URL or not SERVICE_KEY:
        print("[B5] Mode dry-run sans credentials Supabase -- simulation locale uniquement.")
        print("[B5] Resume: 0 outil traite, 0 lien ecrit, 0 ignore.")
        return

    from supabase import create_client
    sb = create_client(SUPABASE_URL, SERVICE_KEY)

    # 1. Load published tools
    print("[B5] Chargement des outils publies...")
    tools = load_tools(sb)
    if not tools:
        print("[B5] Aucun outil publie trouve. Arret.")
        return

    print(f"[B5] {len(tools)} outil(s) publie(s) charge(s).")

    # 2. Load embeddings
    print(f"[B5] Chargement des embeddings (model={args.model})...")
    emb_map = load_embeddings(sb, args.model)
    print(f"[B5] {len(emb_map)} embedding(s) charge(s).")

    # 3. Join tools with embeddings
    tools_with_vec = []
    for t in tools:
        vec = emb_map.get(t["id"])
        if vec:
            tools_with_vec.append((t["id"], t["slug"], t["name"], vec))

    nb_no_emb = len(tools) - len(tools_with_vec)
    if nb_no_emb > 0:
        print(f"[B5] {nb_no_emb} outil(s) sans embedding ignore(s).")

    if len(tools_with_vec) < 2:
        print("[B5] Moins de 2 outils avec embedding -- impossible de calculer des alternatives. Arret.")
        return

    print(f"[B5] {len(tools_with_vec)} outil(s) avec embedding pret(s) pour le calcul.")

    # 4. Apply --only filter
    if args.only:
        found = [t for t in tools_with_vec if t[1] == args.only]
        if not found:
            print(f"[B5] Slug '{args.only}' introuvable ou sans embedding. Arret.")
            sys.exit(1)

    # 5. Compute full similarity matrix (always on full set for correctness)
    print("[B5] Calcul de la matrice de similarite cosinus...")
    alternatives_map = compute_alternatives(np, tools_with_vec, args.top, args.threshold)

    # 6. Determine which tools to process/write
    ids_index = {t[0]: t for t in tools_with_vec}

    if args.only:
        slug_to_id = {t[1]: t[0] for t in tools_with_vec}
        target_id  = slug_to_id[args.only]
        to_process = [ids_index[target_id]]
    else:
        to_process = list(tools_with_vec)

    if args.limit > 0:
        to_process = to_process[:args.limit]

    # 7. Write (or dry-run display)
    nb_written = 0
    nb_ignored = 0

    for tool_id, slug, name, _ in to_process:
        alts = alternatives_map.get(tool_id, [])
        if alts:
            print(f"[B5] {slug}: {len(alts)} alternative(s) trouvee(s)")
            nb_written += write_alternatives(sb, tool_id, slug, alts, args.dry_run)
        else:
            print(f"[B5] {slug}: aucune alternative (seuil={args.threshold})")
            if not args.dry_run:
                # Clean up any stale links
                sb.table("alternatives").delete().eq("tool_id", tool_id).execute()
            nb_ignored += 1

    mode_label = "[dry-run] " if args.dry_run else ""
    print(
        f"\n[B5] {mode_label}Resume: {len(to_process)} outil(s) traite(s), "
        f"{nb_written} lien(s) ecrit(s), {nb_ignored} ignore(s) (sous seuil)."
    )


if __name__ == "__main__":
    main()
