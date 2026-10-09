# -*- coding: utf-8 -*-
"""
b9_submission_kit.py - Kit de soumission annuaires (une fois).

Genere via qwen (Ollama local) les textes de soumission pour Product Hunt,
There's An AI For That, AlternativeTo, etc. et ecrit docs/SUBMISSION_KIT.md.
Auto-skip si le fichier existe deja (etape nocturne inoffensive).

Usage:
    python b9_submission_kit.py
    python b9_submission_kit.py --force
    python b9_submission_kit.py --dry-run
"""
import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / "docs" / "SUBMISSION_KIT.md"

from llm_local import generer_json, MODELE_GEN, LLMError

SYSTEM_PROMPT = (
    "You are a product marketing copywriter for developer and AI tools. "
    "Write ONLY in English. Direct, concrete, zero hype words like 'revolutionary'. "
    "Return ONLY valid JSON with exactly these keys: "
    "tagline, desc_50w, desc_150w, desc_300w, keywords, differentiator, ph_maker_comment. "
    "No markdown fences, no extra keys."
)

PROMPT = (
    "Product: YggNexus (https://www.yggnexus.com)\n"
    "Mission: Turn any AI tool into a working automation.\n"
    "Vision: The trusted map of the AI tooling universe.\n"
    "What it is: a curated, searchable catalog of AI/SaaS tools connected to "
    "ready-to-use n8n/Make automations. Unique angle: it maps the bridge "
    "agents -> skills -> MCP servers -> tools -> automations, so users do not "
    "just discover a tool, they leave with a working workflow.\n"
    "Audience: builders, automation freelancers, ops teams, indie hackers.\n\n"
    "Produce the JSON. Rules:\n"
    "- tagline: max 60 characters.\n"
    "- desc_50w: about 50 words.\n"
    "- desc_150w: about 150 words.\n"
    "- desc_300w: about 300 words, may use 2-3 short paragraphs.\n"
    "- keywords: list of exactly 6 short keyword strings.\n"
    "- differentiator: about 100 words answering 'what makes it different'.\n"
    "- ph_maker_comment: about 150 words, first-person maker comment for a "
    "Product Hunt launch, honest solo-builder tone, ends with a question to readers.\n"
)

TARGETS = """| Cible | URL de soumission | Priorite |
|:--|:--|:--|
| Product Hunt | https://www.producthunt.com/posts/new | 1 |
| There's An AI For That | https://theresanaiforthat.com/get-featured/ | 1 |
| AlternativeTo | https://alternativeto.net/manage-item/ | 1 |
| Toolify.ai | https://www.toolify.ai/submit | 2 |
| Futurepedia | https://www.futurepedia.io/submit-tool | 2 |
| SaaSHub | https://www.saashub.com/submit | 2 |
| Uneed | https://www.uneed.best/submit-a-tool | 3 |
| MicroLaunch | https://microlaunch.net | 3 |
| Show HN | https://news.ycombinator.com/submit | 3 |"""


def main():
    parser = argparse.ArgumentParser(description="Kit de soumission annuaires")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--model", type=str, default=MODELE_GEN)
    args = parser.parse_args()

    if OUT.exists() and not args.force:
        print("[B9] {} existe deja : rien a faire.".format(OUT.name))
        return 0

    if args.dry_run:
        print("[B9] dry-run : appellerait qwen puis ecrirait {}".format(OUT))
        return 0

    try:
        out = generer_json(PROMPT, SYSTEM_PROMPT, modele=args.model, timeout=240)
    except LLMError as e:
        print("[B9] ERREUR LLM: {}".format(e))
        return 1

    def s(k):
        return str(out.get(k) or "").strip()

    kws = out.get("keywords") if isinstance(out.get("keywords"), list) else []
    if not s("tagline") or not s("desc_150w"):
        print("[B9] Sortie LLM incomplete, rien ecrit.")
        return 1

    md = []
    md.append("# Kit de soumission YggNexus\n")
    md.append("*Genere par Prisme (qwen) le {}. Textes EN prets a coller.*\n".format(date.today().isoformat()))
    md.append("## Tagline (60 car.)\n\n" + s("tagline") + "\n")
    md.append("## Description courte (~50 mots)\n\n" + s("desc_50w") + "\n")
    md.append("## Description moyenne (~150 mots)\n\n" + s("desc_150w") + "\n")
    md.append("## Description longue (~300 mots)\n\n" + s("desc_300w") + "\n")
    md.append("## Mots-cles\n\n" + ", ".join(str(k) for k in kws) + "\n")
    md.append("## What makes it different\n\n" + s("differentiator") + "\n")
    md.append("## Commentaire maker Product Hunt\n\n" + s("ph_maker_comment") + "\n")
    md.append("## Cibles prioritaires\n\n" + TARGETS + "\n")
    md.append("## Captures a preparer [JOSUE]\n\n"
              "1. Accueil avec l'arbre Yggdrasil\n"
              "2. /tools avec filtres actifs\n"
              "3. Une fiche outil complete\n"
              "4. Logo 240x240 + banniere 1270x760 (Product Hunt)\n")
    OUT.write_text("\n".join(md), encoding="utf-8")
    print("[B9] Kit ecrit : {}".format(OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
