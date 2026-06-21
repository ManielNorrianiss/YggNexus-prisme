# -*- coding: utf-8 -*-
"""
b4_tagging.py - Batch B4b : tagging ouvert (facettes + tags libres).
Lit enriched_tools (joint raw_tools), appelle le LLM local pour attribuer
des facettes controlees (modality/function/audience) et des tags libres.

Usage:
    python b4_tagging.py
    python b4_tagging.py --force
    python b4_tagging.py --only my-tool-slug
    python b4_tagging.py --dry-run
    python b4_tagging.py --model qwen2.5:14b-instruct
"""
import argparse
import hashlib
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent

import staging
from llm_local import generer_json, MODELE_GEN, LLMError

# ---------------------------------------------------------------------------
# Facets loader
# ---------------------------------------------------------------------------

def load_facets():
    """Load facets vocab from data/facets.json. Returns (data, valid_sets).

    valid_sets : dict {axis: set(slugs)}
    """
    path = ROOT / "data" / "facets.json"
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    valid_sets = {}
    for axis, entries in data.items():
        valid_sets[axis] = {e["slug"] for e in entries}
    return data, valid_sets


# ---------------------------------------------------------------------------
# Slugify
# ---------------------------------------------------------------------------

def slugify(text):
    """Convert a tag label to a slug: lowercase ASCII, spaces/underscores to '-',
    strip punctuation, trim, max 40 chars.
    """
    # Normalize unicode -> ASCII
    text = unicodedata.normalize("NFKD", str(text))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    # Espaces et underscores -> tiret
    text = re.sub(r"[\s_]+", "-", text)
    # Supprimer tout ce qui n'est pas alphanum ou tiret
    text = re.sub(r"[^a-z0-9\-]", "", text)
    # Supprimer tirets multiples
    text = re.sub(r"-{2,}", "-", text)
    text = text.strip("-")
    return text[:40]


ACRONYMS = {
    "ai","api","llm","ui","ux","seo","sql","gpt","ocr","3d","ml","nlp","sdk",
    "crm","saas","b2b","b2c","ide","cli","tts","stt","pdf","csv","html","css",
    "js","ar","vr","kpi","etl","rag",
}


def prettify_label(text):
    """Title-case a tag label but keep known acronyms uppercased."""
    words = str(text).strip().replace("-", " ").split()
    out = []
    for w in words:
        lw = w.lower()
        out.append(lw.upper() if lw in ACRONYMS else w.capitalize())
    return " ".join(out)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a precise tagger for an AI and SaaS tools directory. "
    "Given a short tool description, assign:\n"
    "  1. modality: which content types the tool works with. "
    "Choose from: text, image, audio, video, code, data, 3d, multimodal. "
    "At least 1 required when clear.\n"
    "  2. function: the tool's PRIMARY purpose(s). Pick only the 1-2 most central, "
    "do NOT pile on tangential ones. "
    "Choose from: generate, edit, analyze, automate, chat, build. "
    "Definitions: generate=create new content; edit=modify or enhance existing content; "
    "analyze=analyze, search or research data; automate=run workflows or automate tasks across apps; "
    "chat=conversational assistant or copilot; build=build apps or sites WITHOUT code (no-code/low-code only). "
    "At least 1 required when clear.\n"
    "  3. audience: who uses it (optional). "
    "Choose from: developers, marketing, creators, business, research, general.\n"
    "  4. tags: 3 to 6 short lowercase English keywords describing the tool "
    "(technology, use-case). NOT sentences, NOT brand names, NOT category slugs. "
    "Examples: 'text-to-speech', 'voice-cloning', 'api-first', 'no-code'.\n\n"
    "Return ONLY valid JSON with exactly these keys: "
    "modality (array), function (array), audience (array), tags (array of strings). "
    "Use only slugs from the provided lists for modality/function/audience. "
    "No extra keys, no markdown.\n\n"
) + (
    "Examples (input -> output):\n"
    'An AI code editor that writes, completes and refactors code -> '
    '{"modality":["code"],"function":["generate","edit"],"audience":["developers"],"tags":["ai-coding-assistant","code-generation","ide"]}\n'
    'A text-to-image art generator from prompts -> '
    '{"modality":["image"],"function":["generate"],"audience":["creators"],"tags":["text-to-image","image-generation","art"]}\n'
    'A platform that connects apps to automate workflows -> '
    '{"modality":["data"],"function":["automate"],"audience":["business"],"tags":["workflow-automation","integrations","no-code"]}\n'
    'A voice assistant chatbot that answers questions -> '
    '{"modality":["text"],"function":["chat"],"audience":["general"],"tags":["chatbot","conversational-ai","assistant"]}'
)


def build_prompt(raw, enriched, facets_data):
    """Build the tagging prompt for one tool."""
    name      = raw.get("name", "")
    short     = enriched.get("short_desc", "")
    desc_snip = (enriched.get("description_md") or "")[:800]

    # Listes explicites pour le LLM
    def fmt_axis(axis):
        return ", ".join(e["slug"] for e in facets_data[axis])

    return (
        f"Tool name: {name}\n"
        f"Short description: {short}\n"
        f"Description excerpt:\n{desc_snip}\n\n"
        f"Valid modality slugs: {fmt_axis('modality')}\n"
        f"Valid function slugs: {fmt_axis('function')}\n"
        f"Valid audience slugs: {fmt_axis('audience')}\n\n"
        "Return JSON: modality (array), function (array), audience (array), "
        "tags (3-6 lowercase English keywords, no sentences)."
    )


# ---------------------------------------------------------------------------
# Validation deterministe
# ---------------------------------------------------------------------------

AXIS_CAP = {"modality": 3, "function": 2, "audience": 2}


def validate_tagging(llm_out, valid_sets):
    """Validate and sanitize LLM output.

    Returns (facets_dict, tags_list) where:
      facets_dict : {axis: [slug, ...]}  (only valid slugs, deduped)
      tags_list   : [{"slug": ..., "label": ...}]  (slugified, max 6, len 2..40)
    """
    facets = {}
    for axis, valid in valid_sets.items():
        raw_list = llm_out.get(axis) or []
        if not isinstance(raw_list, list):
            raw_list = []
        # Garde uniquement les slugs valides, deduplique, conserve l'ordre
        seen = set()
        cleaned = []
        for s in raw_list:
            if isinstance(s, str) and s in valid and s not in seen:
                cleaned.append(s)
                seen.add(s)
        cap = AXIS_CAP.get(axis)
        facets[axis] = cleaned[:cap] if cap else cleaned

    raw_tags = llm_out.get("tags") or []
    if not isinstance(raw_tags, list):
        raw_tags = []

    seen_slugs = set()
    tags_list = []
    for t in raw_tags:
        if not isinstance(t, str):
            continue
        slug = slugify(t)
        # longueur min 2
        if len(slug) < 2:
            continue
        # deduplique
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        # Label : Title Case leger (premiere lettre de chaque mot apres '-')
        label = prettify_label(t)
        tags_list.append({"slug": slug, "label": label})
        if len(tags_list) >= 6:
            break

    return facets, tags_list


# ---------------------------------------------------------------------------
# Content hash
# ---------------------------------------------------------------------------

def content_hash_for(raw, enriched):
    """Hash of fields that, if changed, should trigger re-tagging."""
    parts = (
        (raw.get("name") or "")
        + (enriched.get("short_desc") or "")
        + (enriched.get("description_md") or "")
    )
    return hashlib.sha256(parts.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Fake LLM for --dry-run
# ---------------------------------------------------------------------------

def fake_llm(prompt, system, modele=None, timeout=120, _appel=None):
    """Fake LLM for --dry-run."""
    return {
        "modality": ["text"],
        "function": ["generate"],
        "audience": ["general"],
        "tags": ["ai-writing", "text-generation", "productivity"],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Batch B4b tagging (facets + free tags)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fake LLM, write nothing to staging")
    parser.add_argument("--only",  type=str, default="",
                        help="Process a single tool slug")
    parser.add_argument("--force", action="store_true",
                        help="Re-tag even if content_hash is unchanged")
    parser.add_argument("--model", type=str, default=MODELE_GEN,
                        help="Ollama model (default: " + MODELE_GEN + ")")
    args = parser.parse_args()

    fn_gen = fake_llm if args.dry_run else generer_json

    # Load facets vocab
    facets_data, valid_sets = load_facets()

    # Ensure table exists
    staging.init_tool_tagging()

    # Build maps
    enriched_all = {r["slug"]: r for r in staging.iter_enriched()}
    raw_all      = {r["slug"]: r for r in staging.iter_raw()}

    slugs = list(enriched_all.keys())
    if args.only:
        if args.only not in enriched_all:
            sys.exit(f"[B4-tagging] Slug introuvable dans enriched_tools: {args.only}")
        slugs = [args.only]

    to_tag = []
    nb_skip = 0

    for slug in slugs:
        enriched = enriched_all[slug]
        raw      = raw_all.get(slug, {})
        chash    = content_hash_for(raw, enriched)

        if not args.force:
            existing = staging.get_tool_tagging(slug)
            # Si deja tague avec le meme hash -> skip
            db = staging.init_tool_tagging()
            row = db.execute(
                "SELECT content_hash FROM tool_tagging WHERE tool_slug=?", (slug,)
            ).fetchone()
            if row and row["content_hash"] == chash:
                nb_skip += 1
                continue

        to_tag.append((slug, raw, enriched, chash))

    if not to_tag:
        print(f"[B4-tagging] Resume: 0 tague(s), {nb_skip} skip(s), 0 erreur(s).")
        return

    nb_ok    = 0
    nb_error = 0
    now_iso  = datetime.now(timezone.utc).isoformat()

    for slug, raw, enriched, chash in to_tag:
        print(f"[B4-tagging] tagging: {slug}")
        prompt = build_prompt(raw, enriched, facets_data)

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

        facets_dict, tags_list = validate_tagging(llm_out, valid_sets)

        print(
            f"  facets={facets_dict}, tags={[t['slug'] for t in tags_list]}"
        )

        if not args.dry_run:
            staging.replace_tool_tagging(slug, facets_dict, tags_list, chash)
        else:
            print("  [dry-run] rien ecrit.")

        nb_ok += 1

    print(
        f"\n[B4-tagging] Resume: {nb_ok} tague(s), "
        f"{nb_skip} skip(s), {nb_error} erreur(s)."
    )


if __name__ == "__main__":
    main()
