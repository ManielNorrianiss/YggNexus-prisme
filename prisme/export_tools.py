# -*- coding: utf-8 -*-
"""
export_tools.py - Exporte staging.db vers data/tools.json pour publish.py.
Joint raw_tools + enriched_tools par slug.

IMPORTANT: par defaut --merge est actif. Le staging gagne sur les conflits.
Sans --merge, tools.json est entierement ecrase par le contenu du staging.
Les outils existants dans tools.json sans entree staging sont perdus si --no-merge.

Usage:
    python export_tools.py
    python export_tools.py --out data/tools.json
    python export_tools.py --status draft
    python export_tools.py --no-merge
    python export_tools.py --dry-run
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

import staging


PRICING_ENUM = {"free", "freemium", "paid", "open_source", "unknown"}
DEFAULT_OUT = ROOT / "data" / "tools.json"


def load_existing(path):
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return {item["slug"]: item for item in data if "slug" in item}
    except Exception:
        pass
    return {}


def parse_json_field(val, default=None):
    if val is None:
        return default
    if isinstance(val, (list, dict)):
        return val
    try:
        return json.loads(val)
    except Exception:
        return default


def build_entry(raw, enriched):
    """Construit un dict au format attendu par publish.py."""
    pricing = (enriched.get("pricing") or "unknown").lower().strip()
    if pricing not in PRICING_ENUM:
        pricing = "unknown"

    qs = enriched.get("quality_score")
    try:
        qs = float(qs) if qs is not None else None
    except (TypeError, ValueError):
        qs = None
    if qs is not None:
        if qs > 10:                  # echelle 0-100 heritee -> ramener sur 10
            qs = qs / 10.0
        qs = round(max(0.0, min(10.0, qs)), 1)

    # categories retirees (2026-06-21)
    cats = []
    primary = ""

    entry = {
        "slug":                 raw["slug"],
        "name":                 raw.get("name") or "",
        "vendor":               raw.get("vendor") or "",
        "website_url":          raw.get("website_url") or "",
        "source_url":           raw.get("source_url") or "",
        "pricing":              pricing,
        "pricing_note":         enriched.get("pricing_note") or "",
        "short_desc":           enriched.get("short_desc") or "",
        "description_md":       enriched.get("description_md") or "",
        "application_category": enriched.get("application_category") or "",
        "quality_score":        qs,
        "status":               raw.get("status") or "draft",
        "seo_title":            enriched.get("seo_title") or "",
        "seo_description":      enriched.get("seo_description") or "",
        "pros_jsonb":           parse_json_field(enriched.get("pros_json"), default=[]),
        "cons_jsonb":           parse_json_field(enriched.get("cons_json"), default=[]),
        "faq_jsonb":            parse_json_field(enriched.get("faq_json"),  default=[]),
        "categories":           cats,
        "primary_category":     primary,
    }

    # --- Modif 3 : filet SEO deterministe (si le LLM n'a pas produit les champs) ---
    if not (entry["seo_title"] or "").strip():
        base = entry["name"] or entry["slug"]
        titre = base
        if entry["short_desc"]:
            titre = f"{base} — {entry['short_desc']}"
        entry["seo_title"] = titre.strip(" —")[:60]
    if not (entry["seo_description"] or "").strip():
        src_txt = entry["short_desc"] or entry["description_md"] or entry["name"]
        entry["seo_description"] = " ".join(src_txt.split())[:155]

    return entry


def main():
    parser = argparse.ArgumentParser(description="Export staging -> tools.json")
    parser.add_argument("--out", type=str, default=str(DEFAULT_OUT))
    parser.add_argument("--status", type=str, default="published",
                        help="Filtre par status (published|draft). defaut: published")
    parser.add_argument("--no-merge", dest="merge", action="store_false",
                        help="Ecrase tools.json sans fusionner les outils existants")
    parser.add_argument("--dry-run", action="store_true")
    parser.set_defaults(merge=True)
    args = parser.parse_args()

    out_path = Path(args.out)
    staging.init_db()

    raws = {r["slug"]: r for r in staging.iter_raw()
            if args.status == "all" or r.get("status") == args.status or args.status == "draft"}

    if args.status == "published":
        raws = {s: r for s, r in raws.items() if r.get("status") == "published"}

    enriched_map = {e["slug"]: e for e in staging.iter_enriched()}

    # --- entries published (comportement original) ---
    entries_staging = {}
    for slug, raw in raws.items():
        enr = enriched_map.get(slug)
        if enr is None:
            continue
        entries_staging[slug] = build_entry(raw, enr)

    # --- Modif 2 : ajouter les doublons (status==duplicate) en status archived ---
    all_raws = {r["slug"]: r for r in staging.iter_raw()}
    dup_entries = {}
    for slug, raw in all_raws.items():
        if raw.get("status") != "duplicate":
            continue
        enr = enriched_map.get(slug)
        if enr is None:
            continue  # pas d enrichi : ignore
        if slug in entries_staging:
            continue  # deja present (cas theorique)
        entry = build_entry(raw, enr)
        entry["status"] = "archived"  # force archived pour Supabase
        dup_entries[slug] = entry

    if args.merge:
        existing = load_existing(out_path)
        merged = dict(existing)
        merged.update(entries_staging)
        merged.update(dup_entries)
        final = list(merged.values())
    else:
        final = list(entries_staging.values()) + list(dup_entries.values())

    if args.dry_run:
        published_n = len(entries_staging)
        archived_n  = len(dup_entries)
        print(f"[export] --dry-run: {len(final)} outil(s) seraient ecrits dans {out_path}")
        print(f"  dont {published_n} published, {archived_n} archives (doublons B3)")
        for e in final:
            if e["slug"] in entries_staging:
                origin = "staging"
            elif e["slug"] in dup_entries:
                origin = "archived-dup"
            else:
                origin = "existant"
            print(f"  {e['slug']} ({origin}, status={e.get('status')})")
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(final, indent=2, ensure_ascii=False), encoding="utf-8")
    published_n = len(entries_staging)
    archived_n  = len(dup_entries)
    print(f"[export] {len(final)} outil(s) ecrits dans {out_path}")
    existing_count = len(final) - published_n - archived_n if args.merge else 0
    print(f"  dont {published_n} published, {archived_n} archives (doublons B3), {existing_count} depuis tools.json existant")


if __name__ == "__main__":
    main()
