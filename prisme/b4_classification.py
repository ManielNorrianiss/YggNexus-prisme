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
    "assign the SINGLE best matching primary category, plus at most ONE "
    "secondary category only when the tool clearly has a distinct second function. "
    "Be conservative: prefer fewer, high-precision tags over many loose ones. "
    "Critical rules: "
    "(1) 'automation' is ONLY for genuine workflow/integration/orchestration "
    "platforms (Zapier-style: connecting apps, building automated workflows). "
    "Do NOT use 'automation' just because a tool 'automates' a task or mentions "
    "workflows in marketing copy. "
    "(2) Code editors, AI coding assistants, coding agents and dev IDEs -> 'ai-coding'. "
    "(3) Tools that generate or edit video (text-to-video, avatars, clips) -> 'ai-video'. "
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
        "Reminders: 'automation' = workflow/integration platforms only; "
        "coding/IDE/code-agent tools = 'ai-coding'; video generation/editing = 'ai-video'. "
        "Use at most ONE secondary, and only if clearly warranted.\n\n"
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

# ---------------------------------------------------------------------------
# Couche deterministe (le LLM local est faible : on verrouille les cas connus)
# ---------------------------------------------------------------------------

# 'automation' reserve aux vraies plateformes d'orchestration.
AUTOMATION_WHITELIST = {
    "zapier", "make", "n8n", "workato", "pipedream", "ifttt",
    "activepieces", "gumloop", "bardeen", "lindy", "relevance-ai",
}
# Outils dont la categorie principale est certaine (override du LLM).
CODING_SLUGS = {
    "cursor", "devin", "windsurf", "github-copilot", "replit",
}
VIDEO_SLUGS = {
    "runway", "synthesia", "heygen", "pika", "luma-dream-machine",
    "kling", "capcut", "invideo", "d-id", "opus-clip", "hailuo",
}
# Cluster productivite (espaces de travail, notes, reunions, recherche) :
# pas de meilleure niche dans la taxonomie fermee.
PRIMARY_OVERRIDE = {
    "airtable": "productivity", "notion": "productivity", "coda": "productivity",
    "clickup": "productivity", "todoist": "productivity", "motion": "productivity",
    "reclaim": "productivity", "superhuman": "productivity", "mem": "productivity",
    "tana": "productivity", "notebooklm": "productivity", "fathom": "productivity",
    "fireflies-ai": "productivity", "tldv": "productivity", "otter-ai": "productivity",
    "consensus": "productivity", "elicit": "productivity",
    # LLM generalistes : foyer ai-writing (sinon orphelins quand un tag ferme tombe)
    "openai": "ai-writing", "claude": "ai-writing", "gemini": "ai-writing",
    "mistral": "ai-writing", "deepseek": "ai-writing",
    "microsoft-copilot": "ai-writing", "perplexity": "ai-writing",
    # audio/podcast
    "podcastle": "ai-audio",
    # --- Chantier B (reclassement force, 2026-06-20) ---
    # NB slugs : verifier dans Supabase avant le run (cf. runbook). Si un slug
    # reel differe (ex. "wellsaid-labs"), corriger la cle ci-dessous.
    "wellsaid": "ai-audio",
    "canva": "ai-images",
    "freepik": "ai-images",
    # "tana": deja force vers "productivity" plus haut.
}


def steer(slug, primary, secondary):
    """Applique les overrides deterministes. Retourne (primary, secondary, forced)."""
    forced = False
    if slug in CODING_SLUGS:
        primary = "ai-coding"; forced = True
    elif slug in VIDEO_SLUGS:
        primary = "ai-video"; forced = True
    elif slug in PRIMARY_OVERRIDE:
        primary = PRIMARY_OVERRIDE[slug]; forced = True

    # Categories FERMEES : seuls les ensembles cures peuvent porter ces tags
    # (le LLM local les colle a tort en secondaire un peu partout).
    closed = {
        "automation": AUTOMATION_WHITELIST,
        "ai-coding":  CODING_SLUGS,
        "ai-video":   VIDEO_SLUGS,
    }
    for cat, allowed in closed.items():
        if slug not in allowed:
            if primary == cat:
                primary = None
            secondary = [x for x in secondary if x != cat]

    # repli : si plus de primary mais un secondaire dispo, le promouvoir
    if primary is None and secondary:
        primary = secondary[0]
        secondary = secondary[1:]

    # nettoyage : pas de doublon avec primary, max 2
    secondary = [x for x in dict.fromkeys(secondary) if x and x != primary][:2]
    return primary, secondary, forced


def resteer_all(dry_run=False):
    """Re-applique steer() sur tout le staging tool_categories, sans LLM."""
    bytool = {}
    for r in staging.iter_tool_categories():
        bytool.setdefault(r["tool_slug"], []).append(r)
    nb_changed = 0
    for slug, rows in bytool.items():
        valid = [r for r in rows if not r.get("is_unclassified") and r.get("category_slug")]
        if not valid:
            continue
        prim_rows = [r for r in valid if r.get("is_primary")]
        primary = prim_rows[0]["category_slug"] if prim_rows else valid[0]["category_slug"]
        secondary = [r["category_slug"] for r in valid if r["category_slug"] != primary]
        new_primary, new_secondary, _ = steer(slug, primary, secondary)
        before = (primary, tuple(secondary))
        after = (new_primary, tuple(new_secondary))
        if before == after:
            continue
        nb_changed += 1
        meta = valid[0]
        conf = meta.get("confidence", 0.0)
        chash = meta.get("content_hash", "")
        cat_at = meta.get("classified_at", "")
        print(f"[resteer] {slug}: {before} -> {after}")
        if dry_run or new_primary is None:
            if new_primary is None:
                print(f"  ! {slug} sans primary apres steer -> laisse tel quel")
            continue
        out = [{"category_slug": new_primary, "is_primary": 1, "confidence": conf,
                "is_unclassified": 0, "classified_at": cat_at, "content_hash": chash}]
        for sec in new_secondary:
            out.append({"category_slug": sec, "is_primary": 0, "confidence": conf,
                        "is_unclassified": 0, "classified_at": cat_at, "content_hash": chash})
        staging.replace_tool_categories(slug, out)
    print(f"[resteer] {nb_changed} outil(s) modifie(s)." + (" (dry-run)" if dry_run else ""))


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
    parser.add_argument("--resteer",   action="store_true",
                        help="Re-applique la couche deterministe (steer) sur le staging "
                             "existant, SANS appeler le LLM. Rapide, pour propager un "
                             "changement des ensembles cures.")
    args = parser.parse_args()

    if args.resteer:
        resteer_all(args.dry_run)
        return

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
        # Couche deterministe (verrouille coding/video, purge automation hors whitelist)
        primary, secondary, forced = steer(slug, primary, secondary)
        is_unclassified = (primary is None) or (not forced and confidence < args.threshold)

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
