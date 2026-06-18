# -*- coding: utf-8 -*-
"""
b2_enrichissement.py - Batch B2 : enrichissement IA + embeddings.
Lit raw_tools sans enriched_tools (ou hash change), appelle qwen via Ollama,
valide la sortie, calcule l'embedding nomic-embed-text, stocke en staging.

Usage:
    python b2_enrichissement.py
    python b2_enrichissement.py --dry-run
    python b2_enrichissement.py --limit 3
    python b2_enrichissement.py --only n8n
    python b2_enrichissement.py --model qwen2.5:14b-instruct
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent

import staging
from llm_local import generer_json, embed, MODELE_GEN, MODELE_EMBED, EMBED_DIM, LLMError

PRICING_ENUM = {"free", "freemium", "paid", "open_source", "unknown"}
MAX_EMBED_CHARS = 6000

SYSTEM_PROMPT = (
    "You are a factual technical writer for a SaaS/AI tools directory. "
    "Your task is to produce a JSON object describing a software tool. "
    "Write ONLY in English. Be factual, concise and neutral. "
    "Return ONLY valid JSON with exactly these keys: "
    "short_desc, description_md, pros, cons, faq, seo_title, seo_description, "
    "application_category, pricing, pricing_note, quality_score. "
    "No markdown fences, no extra keys, no comments."
)


def build_prompt(raw):
    name       = raw.get("name", "")
    vendor     = raw.get("vendor", "")
    url        = raw.get("website_url", "")
    title      = raw.get("raw_title", "")
    meta       = raw.get("raw_meta_desc", "")
    text_snip  = (raw.get("raw_text") or "")[:1000]
    return (
        f"Tool name: {name}\n"
        f"Vendor: {vendor}\n"
        f"Website: {url}\n"
        f"Page title: {title}\n"
        f"Meta description: {meta}\n"
        f"Page text snippet: {text_snip}\n\n"
        "Produce the JSON object as instructed. Rules:\n"
        "- short_desc: max 160 characters, one sentence.\n"
        "- description_md: 2-3 paragraphs in Markdown.\n"
        "- pros: list of 3 to 5 strings.\n"
        "- cons: list of 2 to 4 strings.\n"
        "- faq: list of exactly 3 objects with keys 'q' and 'a'.\n"
        "- seo_title: max 60 characters.\n"
        "- seo_description: max 155 characters.\n"
        "- application_category: one of SoftwareApplication, WebApplication, "
        "BusinessApplication, DeveloperApplication, MultimediaApplication, UtilitiesApplication.\n"
        "- pricing: exactly one of: free, freemium, paid, open_source, unknown.\n"
        "- pricing_note: short string (max 80 chars).\n"
        "- quality_score: integer 0 to 100.\n"
    )


def fake_llm(prompt, system, modele=None, timeout=120, _appel=None):
    """Faux LLM pour --dry-run (ne touche pas au reseau)."""
    return {
        "short_desc": "A great tool for automation and productivity.",
        "description_md": (
            "This tool helps teams automate repetitive tasks.\n\n"
            "It integrates with hundreds of services out of the box.\n\n"
            "Suitable for both beginners and advanced users."
        ),
        "pros": ["Easy to use", "Many integrations", "Good documentation"],
        "cons": ["Pricing can be steep", "Limited on free tier"],
        "faq": [
            {"q": "Is there a free plan?", "a": "Yes, a free tier is available."},
            {"q": "Does it support webhooks?", "a": "Yes, webhooks are supported."},
            {"q": "Can I self-host?", "a": "Depends on the edition."},
        ],
        "seo_title": "Best Tool Review",
        "seo_description": "Read our full review of this tool and see if it fits your workflow.",
        "application_category": "BusinessApplication",
        "pricing": "freemium",
        "pricing_note": "Free tier available, paid plans from $10/mo",
        "quality_score": 75,
    }


def fake_embed(texte, modele=None, timeout=60, _appel=None):
    """Faux embed pour --dry-run."""
    return [0.0] * EMBED_DIM


def sha256(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def content_hash_for(raw):
    parts = (
        (raw.get("name") or "")
        + (raw.get("raw_title") or "")
        + (raw.get("raw_meta_desc") or "")
        + (raw.get("raw_text") or "")
    )
    return sha256(parts)


def validate_enriched(d):
    """Valide et normalise les champs issus du LLM."""
    result = {}
    result["short_desc"]          = str(d.get("short_desc") or "")[:160]
    result["description_md"]      = str(d.get("description_md") or "")
    result["pros_json"]           = d.get("pros") if isinstance(d.get("pros"), list) else []
    result["cons_json"]           = d.get("cons") if isinstance(d.get("cons"), list) else []
    result["faq_json"]            = d.get("faq")  if isinstance(d.get("faq"),  list) else []
    result["seo_title"]           = str(d.get("seo_title") or "")[:60]
    result["seo_description"]     = str(d.get("seo_description") or "")[:155]
    result["application_category"] = str(d.get("application_category") or "")
    pricing = str(d.get("pricing") or "unknown").lower().strip()
    result["pricing"]             = pricing if pricing in PRICING_ENUM else "unknown"
    result["pricing_note"]        = str(d.get("pricing_note") or "")[:80]
    qs = d.get("quality_score", 50)
    try:
        qs = float(qs)
    except (TypeError, ValueError):
        qs = 50.0
    result["quality_score"] = max(0.0, min(100.0, qs))
    return result


def main():
    parser = argparse.ArgumentParser(description="Batch B2 enrichissement")
    parser.add_argument("--dry-run", action="store_true",
                        help="Utilise un faux LLM, n'ecrit pas en staging")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--only",  type=str, default="")
    parser.add_argument("--model", type=str, default=MODELE_GEN,
                        help="Modele Ollama (defaut: " + MODELE_GEN + ")")
    args = parser.parse_args()

    fn_gen   = fake_llm   if args.dry_run else generer_json
    fn_embed = fake_embed if args.dry_run else embed

    staging.init_db()

    raws = list(staging.iter_raw())
    if args.only:
        raws = [r for r in raws if r["slug"] == args.only]
        if not raws:
            sys.exit(f"Slug introuvable dans raw_tools: {args.only}")

    to_enrich = []
    for r in raws:
        chash = content_hash_for(r)
        existing = staging.get_enriched(r["slug"])
        if existing and existing.get("content_hash") == chash:
            continue
        to_enrich.append((r, chash))

    if args.limit > 0:
        to_enrich = to_enrich[: args.limit]

    if not to_enrich:
        print("[B2] Rien a enrichir.")
        return

    nb_ok = 0
    nb_error = 0

    for raw, chash in to_enrich:
        slug = raw["slug"]
        print(f"[B2] enrichissement: {slug}")

        prompt = build_prompt(raw)
        try:
            llm_out = fn_gen(prompt, SYSTEM_PROMPT, modele=args.model)
        except LLMError as e:
            print(f"  ERREUR LLM: {e}")
            nb_error += 1
            continue
        except Exception as e:
            print(f"  ERREUR inattendue LLM: {e}")
            nb_error += 1
            continue

        validated = validate_enriched(llm_out)
        validated["slug"]         = slug
        validated["content_hash"] = chash
        validated["enriched_at"]  = datetime.now(timezone.utc).isoformat()

        embed_text = (
            (raw.get("name") or "")
            + ". "
            + validated["short_desc"]
            + ". "
            + validated["description_md"]
        )[:MAX_EMBED_CHARS]

        try:
            vec = fn_embed(embed_text, modele=MODELE_EMBED)
        except LLMError as e:
            print(f"  ERREUR embed: {e}")
            nb_error += 1
            continue
        except Exception as e:
            print(f"  ERREUR inattendue embed: {e}")
            nb_error += 1
            continue

        if not args.dry_run:
            staging.upsert_enriched(validated)
            staging.upsert_embedding({
                "slug":           slug,
                "model":          MODELE_EMBED,
                "dim":            len(vec),
                "embedding_json": vec,
                "content_hash":   chash,
                "created_at":     datetime.now(timezone.utc).isoformat(),
            })
            print(f"  ok: short_desc={validated['short_desc'][:60]!r}")
        else:
            print(f"  [dry-run] LLM ok, embed dim={len(vec)}, rien ecrit.")

        nb_ok += 1

    print(f"\n[B2] Resume: {nb_ok} enrichi(s), {nb_error} erreur(s).")


if __name__ == "__main__":
    main()
