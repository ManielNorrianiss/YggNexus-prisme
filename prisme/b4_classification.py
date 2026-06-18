# -*- coding: utf-8 -*-
"""
b4_classification.py - Batch B4 : classification par taxonomie fermee.
Lit enriched_tools (joint raw_tools), appelle le LLM local pour attribuer
primary / secondary slugs depuis data/taxonomy.json.

Usage:
    python b4_classification.py
    python b4_classification.py --dry-run
    python b4_classification.py --limit 5
    python b4_classification.py --only my-tool-slug
    python b4_classification.py --threshold 0.6
    python b4_classification.py --force
    python b4_classification.py --model qwen2.5:14b-instruct
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent

import staging
from llm_local import generer_json, MODELE_GEN, LLMError

# ---------------------------------------------------------------------------
# Taxonomy loader
# ---------------------------------------------------------------------------

def load_taxonomy():
    """Load list of category dicts from data/taxonomy.json."""
    path = ROOT / "data" / "taxonomy.json"
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def taxonomy_slugs(taxonomy):
    """Return a set of valid slugs from the taxonomy list."""
    return {cat["slug"] for cat in taxonomy}


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a precise classifier for an AI and SaaS tools directory. "
    "Given a tool description and a closed list of categories, "
    "you assign the best matching category slugs. "
    "Return ONLY valid JSON with exactly these keys: "
    "primary (string slug or null), secondary (array of slugs, max 2), "
    "confidence (float 0 to 1). "
    "Use only slugs from the provided category list. No extra keys, no markdown."
)


def build_prompt(raw, enriched, taxonomy):
    """Build the classification prompt for one tool."""
    name     = raw.get("name", "")
    website  = raw.get("website_url", "")
    short    = enriched.get("short_desc", "")
    app_cat  = enriched.get("application_category", "")
    desc_snip = (enriched.get("description_md") or "")[:600]

    cats_lines = "\n".join(
        f'  - {c["slug"]}: {c["name"]} — {c["description"]}'
        for c in taxonomy
    )

    return (
        f"Tool name: {name}\n"
        f"Website: {website}\n"
        f"Short description: {short}\n"
        f"Application category: {app_cat}\n"
        f"Description excerpt:\n{desc_snip}\n\n"
        "Available categories (use ONLY these slugs):\n"
        f"{cats_lines}\n\n"
        "Return JSON with keys: primary (slug or null), "
        "secondary (array of up to 2 slugs, excluding primary), "
        "confidence (float 0..1)."
    )


# ---------------------------------------------------------------------------
# Fake LLM for --dry-run
# ---------------------------------------------------------------------------

def fake_llm(prompt, system, modele=None, timeout=120, _appel=None):
    """Fake LLM for --dry-run: always returns ai-writing as primary."""
    return {
        "primary": "ai-writing",
        "secondary": ["automation"],
        "confidence": 0.82,
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_classification(raw_out, valid_slugs, threshold):
    """
    Validate and sanitize LLM output.
    Returns (rows, is_unclassified) where rows is a list of dicts
    ready for replace_tool_categories.
    """
    primary    = raw_out.get("primary")
    secondary  = raw_out.get("secondary") or []
    confidence = raw_out.get("confidence", 0.0)

    # Clamp confidence
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    # Filter primary
    if primary not in valid_slugs:
        primary = None

    # Filter secondary: must be valid, no dup with primary, max 2
    if not isinstance(secondary, list):
        secondary = []
    secondary = [
        s for s in secondary
        if isinstance(s, str) and s in valid_slugs and s != primary
    ]
    secondary = list(dict.fromkeys(secondary))[:2]  # deduplicate, keep order

    # Decide unclassified
    is_unclassified = (primary is None) or (confidence < threshold)

    return primary, secondary, confidence, is_unclassified


# ---------------------------------------------------------------------------
# Content hash
# ---------------------------------------------------------------------------

def sha256(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def content_hash_for(raw, enriched, taxonomy_version):
    """Hash of fields that, if changed, should trigger re-classification."""
    parts = (
        (raw.get("name") or "")
        + (enriched.get("short_desc") or "")
        + (enriched.get("description_md") or "")
        + (enriched.get("application_category") or "")
        + taxonomy_version
    )
    return sha256(parts)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Batch B4 classification")
    parser.add_argument("--dry-run",   action="store_true",
                        help="Fake LLM, write nothing to staging")
    parser.add_argument("--limit",     type=int,   default=0)
    parser.add_argument("--only",      type=str,   default="")
    parser.add_argument("--model",     type=str,   default=MODELE_GEN,
                        help="Ollama model (default: " + MODELE_GEN + ")")
    parser.add_argument("--threshold", type=float, default=0.45,
                        help="Min confidence to accept classification (default 0.45)")
    parser.add_argument("--force",     action="store_true",
                        help="Re-classify even if content_hash is unchanged")
    args = parser.parse_args()

    fn_gen = fake_llm if args.dry_run else generer_json

    # Load taxonomy
    taxonomy = load_taxonomy()
    valid_slugs = taxonomy_slugs(taxonomy)
    # Stable version string for hashing
    taxonomy_version = json.dumps(taxonomy, sort_keys=True)

    # Ensure table exists
    staging.init_tool_categories()

    # Build list of (raw, enriched) pairs
    enriched_all = {r["slug"]: r for r in staging.iter_enriched()}
    raw_all      = {r["slug"]: r for r in staging.iter_raw()}

    slugs = list(enriched_all.keys())
    if args.only:
        if args.only not in enriched_all:
            sys.exit(f"[B4] Slug introuvable dans enriched_tools: {args.only}")
        slugs = [args.only]

    to_classify = []
    nb_skip = 0

    for slug in slugs:
        enriched = enriched_all[slug]
        raw      = raw_all.get(slug, {})
        chash    = content_hash_for(raw, enriched, taxonomy_version)

        if not args.force:
            existing = staging.get_tool_categories(slug)
            if existing and existing[0].get("content_hash") == chash:
                nb_skip += 1
                continue

        to_classify.append((slug, raw, enriched, chash))

    if args.limit > 0:
        to_classify = to_classify[:args.limit]

    if not to_classify:
        print(f"[B4] Resume: 0 classe(s), 0 unclassified, {nb_skip} skip(s), 0 erreur(s).")
        return

    nb_ok          = 0
    nb_unclassified = 0
    nb_error       = 0
    now_iso        = datetime.now(timezone.utc).isoformat()

    for slug, raw, enriched, chash in to_classify:
        print(f"[B4] classifying: {slug}")
        prompt = build_prompt(raw, enriched, taxonomy)

        try:
            llm_out = fn_gen(prompt, SYSTEM_PROMPT, modele=args.model)
        except LLMError as e:
            print(f"  ERREUR LLM: {e}")
            nb_error += 1
            continue
        except Exception as e:
            print(f"  ERREUR inattendue: {e}")
            nb_error += 1
            continue

        primary, secondary, confidence, is_unclassified = validate_classification(
            llm_out, valid_slugs, args.threshold
        )

        if is_unclassified:
            nb_unclassified += 1
            rows = [{
                "category_slug":   "",
                "is_primary":      0,
                "confidence":      confidence,
                "is_unclassified": 1,
                "classified_at":   now_iso,
                "content_hash":    chash,
            }]
            print(f"  unclassified (primary={primary!r}, confidence={confidence:.2f})")
        else:
            nb_ok += 1
            rows = [{
                "category_slug":   primary,
                "is_primary":      1,
                "confidence":      confidence,
                "is_unclassified": 0,
                "classified_at":   now_iso,
                "content_hash":    chash,
            }]
            for sec in secondary:
                rows.append({
                    "category_slug":   sec,
                    "is_primary":      0,
                    "confidence":      confidence,
                    "is_unclassified": 0,
                    "classified_at":   now_iso,
                    "content_hash":    chash,
                })
            print(
                f"  primary={primary!r}, secondary={secondary!r}, "
                f"confidence={confidence:.2f}"
            )

        if not args.dry_run:
            staging.replace_tool_categories(slug, rows)
        else:
            print(f"  [dry-run] rien ecrit.")

    print(
        f"\n[B4] Resume: {nb_ok} classe(s), {nb_unclassified} unclassified, "
        f"{nb_skip} skip(s), {nb_error} erreur(s)."
    )


if __name__ == "__main__":
    main()
