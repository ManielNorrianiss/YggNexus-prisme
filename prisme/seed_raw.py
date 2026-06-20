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
    {
        "slug": 'quillbot',
        "name": 'QuillBot',
        "vendor": 'QuillBot (Learneo)',
        "website_url": 'https://quillbot.com',
        "raw_title": 'QuillBot - AI paraphrasing and grammar',
        "raw_meta_desc": 'QuillBot paraphrases, summarizes and checks grammar in your text with AI.',
        "raw_text": 'QuillBot is an AI writing assistant best known for its paraphrasing and summarizing tools. It rewrites sentences in different tones and lengths, fixes grammar and punctuation, checks for plagiarism, and offers a citation generator. Used by students, writers and professionals to polish and rephrase text.',
        "categories": ['ai-writing'],
        "primary_category": 'ai-writing',
    },
    {
        "slug": 'rytr',
        "name": 'Rytr',
        "vendor": 'Rytr',
        "website_url": 'https://rytr.me',
        "raw_title": 'Rytr - affordable AI writer',
        "raw_meta_desc": 'Rytr is an affordable AI writer for short-form marketing and content copy.',
        "raw_text": 'Rytr is an AI writing tool focused on generating short-form content such as ad copy, emails, product descriptions and social posts. It offers dozens of use-case templates, multiple tones and languages, and a low-cost pricing model, making it popular with solo marketers and small businesses.',
        "categories": ['ai-writing'],
        "primary_category": 'ai-writing',
    },
    {
        "slug": 'krea-ai',
        "name": 'Krea AI',
        "vendor": 'Krea',
        "website_url": 'https://www.krea.ai',
        "raw_title": 'Krea AI - real-time image generation',
        "raw_meta_desc": 'Krea AI generates and enhances images in real time, with upscaling and style control.',
        "raw_text": 'Krea AI is a generative image platform with real-time generation, image enhancement and upscaling. It lets creators sketch or type prompts and see results update live, control style and composition, and upscale outputs to high resolution. Used for concept art, marketing visuals and rapid iteration.',
        "categories": ['ai-images'],
        "primary_category": 'ai-images',
    },
    {
        "slug": 'clipdrop',
        "name": 'Clipdrop',
        "vendor": 'Stability AI',
        "website_url": 'https://clipdrop.co',
        "raw_title": 'Clipdrop - AI image editing by Stability AI',
        "raw_meta_desc": 'Clipdrop offers AI image tools: background removal, relight, upscale and Stable Diffusion.',
        "raw_text": 'Clipdrop, by Stability AI, is a suite of AI image-editing tools including background removal, cleanup, relighting, uncrop, upscaling and text-to-image via Stable Diffusion. Available as a web app, API and plugins, it is used by designers and marketers to edit and generate visuals quickly.',
        "categories": ['ai-images'],
        "primary_category": 'ai-images',
    },
    {
        "slug": 'play-ht',
        "name": 'PlayHT',
        "vendor": 'PlayHT',
        "website_url": 'https://play.ht',
        "raw_title": 'PlayHT - AI text-to-speech and voice cloning',
        "raw_meta_desc": 'PlayHT turns text into lifelike speech and clones voices for AI voice generation.',
        "raw_text": 'PlayHT is an AI text-to-speech and voice generation platform. It produces natural-sounding voiceovers in many languages and accents, supports ultra-realistic voice cloning, and offers an API and a real-time voice agent product. Used for podcasts, audio content, IVR and conversational AI.',
        "categories": ['ai-audio', 'ai-voice'],
        "primary_category": 'ai-audio',
    },
    {
        "slug": 'resemble-ai',
        "name": 'Resemble AI',
        "vendor": 'Resemble AI',
        "website_url": 'https://www.resemble.ai',
        "raw_title": 'Resemble AI - voice cloning and speech generation',
        "raw_meta_desc": 'Resemble AI clones voices and generates speech, with deepfake audio detection.',
        "raw_text": 'Resemble AI is a voice generation platform that creates custom AI voices and clones from short samples. It offers real-time speech synthesis, multilingual dubbing, speech-to-speech, an API, and tools to watermark and detect AI-generated audio. Used for games, media, dubbing and accessibility.',
        "categories": ['ai-audio', 'ai-voice'],
        "primary_category": 'ai-audio',
    },
    {
        "slug": 'activepieces',
        "name": 'Activepieces',
        "vendor": 'Activepieces',
        "website_url": 'https://www.activepieces.com',
        "raw_title": 'Activepieces - open-source no-code automation',
        "raw_meta_desc": 'Activepieces is an open-source, no-code automation platform and Zapier alternative.',
        "raw_text": 'Activepieces is an open-source no-code automation tool that connects apps and APIs through visual flows. It can be self-hosted or used in the cloud, supports AI steps and custom pieces written in TypeScript, and is positioned as an open alternative to Zapier and Make for automating workflows.',
        "categories": ['automation', 'no-code'],
        "primary_category": 'automation',
    },
    {
        "slug": 'phantombuster',
        "name": 'PhantomBuster',
        "vendor": 'PhantomBuster',
        "website_url": 'https://phantombuster.com',
        "raw_title": 'PhantomBuster - lead extraction and outreach automation',
        "raw_meta_desc": 'PhantomBuster automates lead extraction and outreach from web and social platforms.',
        "raw_text": "PhantomBuster is a code-free data extraction and automation platform. It runs ready-made 'phantoms' that scrape profiles and lists from sites like LinkedIn, enrich contact data, and automate outreach sequences. Used by sales and growth teams to build lead lists and automate prospecting.",
        "categories": ['data-scraping', 'automation'],
        "primary_category": 'data-scraping',
    },
    {
        "slug": 'softr',
        "name": 'Softr',
        "vendor": 'Softr',
        "website_url": 'https://www.softr.io',
        "raw_title": 'Softr - no-code apps on Airtable',
        "raw_meta_desc": 'Softr builds client portals, internal tools and web apps on top of Airtable or Google Sheets.',
        "raw_text": 'Softr is a no-code app builder that turns Airtable, Google Sheets or its own database into web apps, client portals, internal tools and directories. It offers drag-and-drop blocks, user authentication, permissions and payments, letting non-developers ship functional apps fast.',
        "categories": ['no-code', 'productivity'],
        "primary_category": 'no-code',
    },
    {
        "slug": 'taskade',
        "name": 'Taskade',
        "vendor": 'Taskade',
        "website_url": 'https://www.taskade.com',
        "raw_title": 'Taskade - AI workspace for tasks and agents',
        "raw_meta_desc": 'Taskade combines AI agents, tasks, notes and mind maps in one collaborative workspace.',
        "raw_text": 'Taskade is an AI-powered productivity workspace that unifies tasks, notes, outlines, mind maps and chat. It lets teams build and run custom AI agents on their projects, automate workflows, and collaborate in real time across multiple views. Used for project management and AI-assisted teamwork.',
        "categories": ['productivity', 'no-code'],
        "primary_category": 'productivity',
    },
    {
        "slug": 'freepik',
        "name": 'Freepik',
        "vendor": 'Freepik Company',
        "website_url": 'https://www.freepik.com',
        "raw_title": 'Freepik - AI image generation and graphic resources',
        "raw_meta_desc": 'Freepik offers AI image generation plus a huge library of stock photos, vectors, icons and templates.',
        "raw_text": 'Freepik is a graphic resources platform that pairs a large library of stock photos, vectors, icons and templates with an AI suite. Its AI tools turn text prompts into images, upscale and retouch visuals, remove or replace backgrounds and generate video, helping designers and marketers create assets fast.',
        "categories": ['ai-images'],
        "primary_category": 'ai-images',
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
