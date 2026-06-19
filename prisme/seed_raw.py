# -*- coding: utf-8 -*-
"""
seed_raw.py - Injecte a la main des entrees raw_tools pour des outils
dont le site bloque le crawl (403 / Cloudflare), afin que B2 puisse les
enrichir + calculer leur embedding sans passer par B1.

Usage:
    python seed_raw.py            # injecte les fiches definies ci-dessous
    python seed_raw.py --dry-run  # montre sans ecrire

Apres : python b2_enrichissement.py --only <slug>  (puis export/publish).
"""
import argparse
import hashlib
from datetime import datetime, timezone

import staging

FICHES = [
    {
        "slug": "make",
        "name": "Make",
        "vendor": "Make (Celonis)",
        "website_url": "https://www.make.com",
        "raw_title": "Make — Visual automation platform",
        "raw_meta_desc": ("Make (formerly Integromat) lets you design, build and "
                          "automate workflows by visually connecting apps."),
        "raw_text": ("Make is a visual no-code / low-code automation platform "
                     "(formerly Integromat). It connects thousands of apps and "
                     "APIs through a drag-and-drop scenario builder with routers, "
                     "filters, iterators and aggregators, so teams can automate "
                     "complex multi-step workflows without writing code."),
        "categories": ["automation", "no-code"],
        "primary_category": "automation",
    },
    {
        "slug": "midjourney",
        "name": "Midjourney",
        "vendor": "Midjourney",
        "website_url": "https://midjourney.com",
        "raw_title": "Midjourney — AI image generation",
        "raw_meta_desc": ("Midjourney turns natural-language text prompts into "
                          "high-quality, artistic images."),
        "raw_text": ("Midjourney is a generative AI tool that creates images from "
                     "natural-language text prompts. It is known for its highly "
                     "artistic, stylized output and is used by designers, artists "
                     "and marketers. It is accessed through Discord and a web app, "
                     "with controls for aspect ratio, style and variations."),
        "categories": ["ai-images"],
        "primary_category": "ai-images",
    },
    {
        "slug": "gamma",
        "name": "Gamma",
        "vendor": "Gamma",
        "website_url": "https://gamma.app",
        "raw_title": "Gamma - AI presentations, documents and websites",
        "raw_meta_desc": ("Gamma uses AI to generate polished presentations, "
                          "documents and websites from a simple prompt or outline."),
        "raw_text": ("Gamma is an AI-powered tool that turns a prompt or outline "
                     "into formatted presentations, documents and webpages. It "
                     "handles layout, design and images automatically, lets you "
                     "edit with flexible card-based blocks, and exports to PDF or "
                     "PowerPoint. Used to create decks and one-pagers fast."),
        "categories": ["productivity"],
        "primary_category": "productivity",
    },
    {
        "slug": "lovable",
        "name": "Lovable",
        "vendor": "Lovable",
        "website_url": "https://lovable.dev",
        "raw_title": "Lovable - AI app builder",
        "raw_meta_desc": ("Lovable turns natural-language prompts into full-stack "
                          "web apps, no coding required."),
        "raw_text": ("Lovable is an AI app builder that generates full-stack web "
                     "applications from natural-language prompts. It produces the "
                     "frontend, backend and database wiring, supports live editing "
                     "and deployment, and targets founders and teams who want to "
                     "ship software without writing code."),
        "categories": ["no-code"],
        "primary_category": "no-code",
    },
    {
        "slug": "leonardo-ai",
        "name": "Leonardo AI",
        "vendor": "Leonardo.Ai",
        "website_url": "https://leonardo.ai",
        "raw_title": "Leonardo.Ai - AI image and art generation",
        "raw_meta_desc": ("Leonardo.Ai generates production-quality images, art and "
                          "game assets from text prompts."),
        "raw_text": ("Leonardo.Ai is a generative AI platform for creating images "
                     "and art from text prompts. It offers fine-tuned and custom "
                     "models, real-time canvas, image-to-image and control tools, "
                     "and is popular for game assets, concept art and marketing "
                     "visuals."),
        "categories": ["ai-images"],
        "primary_category": "ai-images",
    },
    {
        "slug": "adobe-firefly",
        "name": "Adobe Firefly",
        "vendor": "Adobe",
        "website_url": "https://www.adobe.com/products/firefly.html",
        "raw_title": "Adobe Firefly - generative AI for creatives",
        "raw_meta_desc": ("Adobe Firefly is a family of generative AI models for "
                          "images, text effects and video, designed for commercial "
                          "safety and integrated across Creative Cloud."),
        "raw_text": ("Adobe Firefly is Adobe's generative AI for creatives, able to "
                     "produce images, text effects, vectors and video from prompts. "
                     "Trained on licensed and public-domain content for commercial "
                     "safety, it is built into Photoshop, Illustrator and Express "
                     "via Generative Fill and related features."),
        "categories": ["ai-images"],
        "primary_category": "ai-images",
    },
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    now = datetime.now(timezone.utc).isoformat()
    for f in FICHES:
        src_basis = f["website_url"] + f["raw_title"] + f["raw_text"]
        row = {
            "slug": f["slug"],
            "name": f["name"],
            "vendor": f["vendor"],
            "website_url": f["website_url"],
            "source_url": f["website_url"],
            "source_hash": hashlib.sha256(src_basis.encode("utf-8")).hexdigest(),
            "raw_title": f["raw_title"],
            "raw_meta_desc": f["raw_meta_desc"],
            "raw_text": f["raw_text"],
            "categories_json": f["categories"],
            "primary_category": f["primary_category"],
            "status": "published",
            "collected_at": now,
        }
        if args.dry_run:
            print(f"[seed_raw] (dry-run) {f['slug']} pret (status=published)")
        else:
            staging.upsert_raw(row)
            print(f"[seed_raw] injecte raw_tools: {f['slug']}")

    if not args.dry_run:
        print("[seed_raw] termine. Lance maintenant : "
              "python b2_enrichissement.py --only make  (et --only midjourney)")


if __name__ == "__main__":
    main()
