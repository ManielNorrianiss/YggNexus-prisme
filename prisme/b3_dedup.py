# -*- coding: utf-8 -*-
"""
b3_dedup.py - Batch B3 : detection de doublons (non destructif, reversible).

Detection hybride :
  1. Domaine normalise du website_url (meme host = doublon).
  2. Similarite cosine entre embeddings >= seuil (defaut 0.92).

Les groupes sont construits par union-find (les deux signaux sont fusionne).
Pour chaque groupe >= 2, le canonique = quality_score max (egalite : desc la
plus longue, puis slug alphabetique). Les autres = doublons.

Usage:
    python b3_dedup.py                        # rapport seul, rien n'est ecrit
    python b3_dedup.py --apply                # ecrit dedup_map + status duplicate
    python b3_dedup.py --reset                # restaure statuts + vide dedup_map
    python b3_dedup.py --threshold 0.90       # seuil cosine personnalise
    python b3_dedup.py --limit 50             # limite le nombre d'outils (debug)
"""
import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import staging


# ---------------------------------------------------------------------------
# Union-Find
# ---------------------------------------------------------------------------

class UnionFind:
    """Union-Find path-compressed pour grouper les doublons."""

    def __init__(self):
        self.parent = {}

    def find(self, x):
        if x not in self.parent:
            self.parent[x] = x
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra

    def groups(self):
        """Retourne un dict {racine: [membres]} pour tous les groupes >= 2."""
        buckets = {}
        for node in self.parent:
            root = self.find(node)
            buckets.setdefault(root, set()).add(node)
        return {r: members for r, members in buckets.items() if len(members) >= 2}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_domain(url):
    """Normalise un URL en host minuscule sans schema ni www. ni slash final."""
    if not url:
        return None
    s = url.strip().lower()
    # retirer schema
    if "://" in s:
        s = s.split("://", 1)[1]
    # retirer www.
    if s.startswith("www."):
        s = s[4:]
    # garder seulement le host (avant le premier /)
    s = s.split("/")[0]
    s = s.rstrip("/")
    return s or None


def cosine(v1, v2):
    """Similarite cosine entre deux listes de floats, Python pur."""
    if len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    n1 = math.sqrt(sum(a * a for a in v1))
    n2 = math.sqrt(sum(b * b for b in v2))
    if n1 == 0.0 or n2 == 0.0:
        return 0.0
    return dot / (n1 * n2)


def load_tools(limit=None):
    """Charge raw_tools (dict slug->row) et enriched_tools (dict slug->row)."""
    raws = {}
    for row in staging.iter_raw():
        raws[row["slug"]] = row
        if limit and len(raws) >= limit:
            break
    enriched = {}
    for row in staging.iter_enriched():
        enriched[row["slug"]] = row
    return raws, enriched


def load_embeddings(slugs_set):
    """Charge les embeddings pour les slugs demandes."""
    embs = {}
    for row in staging.iter_embeddings():
        if row["slug"] in slugs_set:
            vec_raw = row.get("embedding_json")
            if vec_raw:
                try:
                    vec = json.loads(vec_raw)
                    embs[row["slug"]] = {"vec": vec, "dim": len(vec)}
                except (json.JSONDecodeError, TypeError):
                    pass
    return embs


def pick_canonical(members, enriched):
    """Choisit le canonique dans un groupe : quality_score max, puis desc longue,
    puis slug alphabetique."""
    def sort_key(slug):
        e = enriched.get(slug) or {}
        qs = e.get("quality_score") or 0.0
        desc_len = len(e.get("description_md") or "")
        return (-qs, -desc_len, slug)
    return sorted(members, key=sort_key)[0]


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def detect_groups(raws, enriched, threshold, limit=None):
    """
    Construit les groupes de doublons par union-find (domaine + cosine).
    Retourne (uf, reasons, scores) :
      - uf       : UnionFind finalise
      - reasons  : dict (slug_a, slug_b) -> 'domain' | 'embedding' | 'domain+embedding'
      - scores   : dict (slug_a, slug_b) -> float cosine ou None
    """
    slugs = list(raws.keys())

    uf = UnionFind()
    # Initialiser tous les noeuds
    for s in slugs:
        uf.find(s)

    # Signal 1 : domaine normalise
    domain_map = {}  # domain -> [slugs]
    for slug, row in raws.items():
        d = normalize_domain(row.get("website_url"))
        if d:
            domain_map.setdefault(d, []).append(slug)

    domain_pairs = set()
    for d, group_slugs in domain_map.items():
        if len(group_slugs) >= 2:
            for i in range(len(group_slugs)):
                for j in range(i + 1, len(group_slugs)):
                    a, b = sorted([group_slugs[i], group_slugs[j]])
                    domain_pairs.add((a, b))
                    uf.union(a, b)

    # Signal 2 : cosine embeddings
    embs = load_embeddings(set(slugs))
    embed_pairs = {}  # (a,b) -> score

    emb_slugs = list(embs.keys())
    for i in range(len(emb_slugs)):
        for j in range(i + 1, len(emb_slugs)):
            a, b = emb_slugs[i], emb_slugs[j]
            ea, eb = embs[a], embs[b]
            if ea["dim"] != eb["dim"]:
                continue
            score = cosine(ea["vec"], eb["vec"])
            if score >= threshold:
                ka, kb = sorted([a, b])
                embed_pairs[(ka, kb)] = score
                uf.union(a, b)

    # Construire reasons et scores par paire detectee
    all_pairs = domain_pairs | set(embed_pairs.keys())
    reasons = {}
    scores = {}
    for pair in all_pairs:
        in_domain = pair in domain_pairs
        in_embed = pair in embed_pairs
        if in_domain and in_embed:
            reasons[pair] = "domain+embedding"
        elif in_domain:
            reasons[pair] = "domain"
        else:
            reasons[pair] = "embedding"
        scores[pair] = embed_pairs.get(pair)

    return uf, reasons, scores


def build_report(raws, enriched, threshold, limit=None):
    """
    Retourne une liste de groupes, chacun etant un dict :
      {canonical, duplicates: [{slug, reason, score}]}
    """
    uf, reasons, scores = detect_groups(raws, enriched, threshold, limit)
    groups_raw = uf.groups()

    report = []
    for root, members in groups_raw.items():
        canonical = pick_canonical(members, enriched)
        dups = []
        for slug in sorted(members):
            if slug == canonical:
                continue
            # Trouver la raison pour ce doublon (via toute paire avec canonical)
            pair = tuple(sorted([slug, canonical]))
            reason = reasons.get(pair, "unknown")
            score = scores.get(pair)

            # Si pas de paire directe, chercher via d'autres membres du groupe
            if reason == "unknown":
                for other in members:
                    if other == slug:
                        continue
                    p = tuple(sorted([slug, other]))
                    if p in reasons:
                        reason = reasons[p]
                        score = scores.get(p)
                        break

            dups.append({"slug": slug, "reason": reason, "score": score})
        report.append({"canonical": canonical, "duplicates": dups})

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def print_report(report, raws, enriched):
    """Affiche les groupes detectes."""
    if not report:
        print("[B3] Aucun doublon detecte.")
        return
    for g in report:
        canon = g["canonical"]
        e = enriched.get(canon) or {}
        qs = e.get("quality_score") or 0.0
        print(f"\n  CANONIQUE : {canon}  (quality_score={qs})")
        for d in g["duplicates"]:
            score_str = f"  cosine={d['score']:.4f}" if d["score"] is not None else ""
            print(f"    DOUBLON  : {d['slug']}  [{d['reason']}{score_str}]")


def cmd_report(args):
    """Mode rapport : detection seule, aucune ecriture."""
    raws, enriched = load_tools(limit=args.limit)
    report = build_report(raws, enriched, args.threshold, args.limit)
    print_report(report, raws, enriched)
    total_dups = sum(len(g["duplicates"]) for g in report)
    print(f"\n[B3] Resume: {len(report)} groupe(s), {total_dups} doublon(s).")


def cmd_apply(args):
    """Mode apply : ecrit dedup_map et passe les doublons a status='duplicate'."""
    staging.init_dedup()
    raws, enriched = load_tools(limit=args.limit)
    report = build_report(raws, enriched, args.threshold, args.limit)

    now = datetime.now(timezone.utc).isoformat()
    written = 0
    for g in report:
        for d in g["duplicates"]:
            slug = d["slug"]
            prev_status = (raws.get(slug) or {}).get("status", "draft")
            staging.upsert_dedup({
                "slug": slug,
                "canonical_slug": g["canonical"],
                "reason": d["reason"],
                "score": d["score"],
                "prev_status": prev_status,
                "detected_at": now,
            })
            staging.set_raw_status(slug, "duplicate")
            written += 1

    total_dups = sum(len(g["duplicates"]) for g in report)
    print(f"[B3] Resume: {len(report)} groupe(s), {total_dups} doublon(s).")
    print(f"[B3] Apply : {written} lignes ecrites dans dedup_map, statuts -> 'duplicate'.")


def cmd_reset(args):
    """Mode reset : restaure les statuts et vide dedup_map."""
    # Charger toutes les lignes avant d'ecrire (eviter db locked avec curseur ouvert)
    rows = list(staging.iter_dedup())
    restored = 0
    for row in rows:
        staging.set_raw_status(row["slug"], row["prev_status"])
        restored += 1
    staging.clear_dedup()
    print(f"[B3] Reset : {restored} statut(s) restaure(s), dedup_map vide.")


def main():
    parser = argparse.ArgumentParser(
        description="B3 dedup - detection de doublons dans le catalogue YggNexus."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Ecrire dedup_map et marquer les doublons comme 'duplicate' dans raw_tools.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Restaurer les statuts originaux et vider dedup_map.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.92,
        help="Seuil de similarite cosine (defaut: 0.92).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Nombre max d'outils a considerer (debug).",
    )
    args = parser.parse_args()

    if args.reset and args.apply:
        print("[B3] Erreur : --apply et --reset sont mutuellement exclusifs.")
        sys.exit(1)

    if args.reset:
        cmd_reset(args)
    elif args.apply:
        cmd_apply(args)
    else:
        cmd_report(args)


if __name__ == "__main__":
    main()
