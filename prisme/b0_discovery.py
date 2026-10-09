# -*- coding: utf-8 -*-
"""
b0_discovery.py - Batch B0 : decouverte d'outils IA depuis des listes GitHub
"awesome-ai-tools" (licence ouverte, markdown). Fetch chaque README, extrait les
liens markdown "- [Nom](url)", normalise/nettoie le domaine, deduplique par
domaine, et ecrit data/candidates.json (entrees brutes a passer dans b0_to_sources.py).

100% gratuit : aucune API payante, juste des fetch HTTP de README publics.
A lancer sur la machine Windows.

Usage :
    python b0_discovery.py --dry-run     # montre le compte par liste, n'ecrit rien
    python b0_discovery.py               # ecrit data/candidates.json
    python b0_discovery.py --out data/candidates_github.json
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent

# README bruts de listes awesome reconnues. Certaines peuvent 404 (branche
# main/master, repo deplace) : le script saute proprement les echecs.
AWESOME_LISTS = [
    "https://raw.githubusercontent.com/mahseema/awesome-ai-tools/main/README.md",
    "https://raw.githubusercontent.com/steven2358/awesome-generative-ai/master/README.md",
    "https://raw.githubusercontent.com/eudk/awesome-ai-tools/main/README.md",
    "https://raw.githubusercontent.com/re50urces/Awesome-AI/main/README.md",
    "https://raw.githubusercontent.com/ai-collection/ai-collection/main/README.md",
    "https://raw.githubusercontent.com/altryne/awesome-ai-tools/main/README.md",
    "https://raw.githubusercontent.com/jamesmurdza/awesome-ai-devtools/main/README.md",
    "https://raw.githubusercontent.com/ai-for-developers/awesome-ai-for-developers/main/README.md",
    "https://raw.githubusercontent.com/GitHubDaily/Awesome-AI-Tools/main/README.md",
    "https://raw.githubusercontent.com/best-of-lists/best-of-ai/main/README.md",
]

# Plateformes / hubs / reseaux : pas des "outils" autonomes a indexer.
PLATFORM_BLOCK = {
    "github.com", "gitlab.com", "huggingface.co", "youtube.com", "youtu.be",
    "twitter.com", "x.com", "discord.com", "discord.gg", "reddit.com",
    "medium.com", "substack.com", "linkedin.com", "facebook.com", "instagram.com",
    "awesome.re", "altern.ai", "newsletter.altern.ai", "theresanai.com",
    "ai.meta.com", "ai.facebook.com", "deepmind.com", "lmsys.org", "arxiv.org",
    "apps.apple.com", "play.google.com", "patreon.com", "ko-fi.com",
    "producthunt.com", "wikipedia.org", "google.com", "notion.site",
}

# Sous-domaines de tracking/affiliation a reduire au domaine racine.
TRACK_SUBS = {"affiliate", "get", "try", "go", "ref", "partner", "link",
              "click", "track", "join", "start", "hi"}

MD_LINK = re.compile(
    r'^\s*[-*]\s*\[([^\]]+)\]\((https?://[^)\s]+)\)', re.MULTILINE)


def clean_domain(url):
    """Domaine racine nettoye (sans www ni sous-domaine de tracking)."""
    try:
        net = urlparse(url).netloc.lower().split(":")[0]
    except Exception:
        return None
    if not net:
        return None
    if net.startswith("www."):
        net = net[4:]
    parts = net.split(".")
    # retire un sous-domaine de tracking en tete (affiliate.notion.so -> notion.so)
    if len(parts) > 2 and parts[0] in TRACK_SUBS:
        parts = parts[1:]
        net = ".".join(parts)
    return net or None


def parse_links(text):
    """Liste de (name, url) depuis le markdown. Fonction pure (testable)."""
    return [(m.group(1).strip(), m.group(2).strip()) for m in MD_LINK.finditer(text)]


def is_tool_domain(domain):
    if not domain or "." not in domain:
        return False
    return not any(domain == b or domain.endswith("." + b) for b in PLATFORM_BLOCK)


def harvest_text(text, source, into):
    added = 0
    for name, url in parse_links(text):
        d = clean_domain(url)
        if not is_tool_domain(d):
            continue
        if d in into:
            into[d]["sources"].append(source)
            continue
        # nom propre : retire les suffixes parasites
        nm = re.sub(r"\s*[-—:].*$", "", name).strip() or d
        into[d] = {
            "domain": d,
            "name": nm[:80],
            "website_url": f"https://{d}",
            "sources": [source],
        }
        added += 1
    return added


def fetch(url):
    import requests
    r = requests.get(url, timeout=20, headers={"User-Agent": "YggNexus-discovery/1.0"})
    r.raise_for_status()
    return r.text


def load_list_urls():
    """URLs des listes : data/awesome_lists.txt si present (1 url/ligne, # = commentaire),
    sinon la liste par defaut AWESOME_LISTS. Permet d'ajouter des sources sans toucher au code."""
    f = ROOT / "data" / "awesome_lists.txt"
    if f.exists():
        urls = []
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
        if urls:
            return urls
    return AWESOME_LISTS


def main():
    ap = argparse.ArgumentParser(description="B0 discovery (GitHub awesome lists)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "data" / "candidates.json"))
    args = ap.parse_args()

    candidates = {}
    lists = load_list_urls()
    print(f"[B0] {len(lists)} liste(s) a moissonner")
    for url in lists:
        name = url.split("/")[3] + "/" + url.split("/")[4]  # owner/repo
        try:
            text = fetch(url)
        except Exception as e:
            print(f"[B0] SKIP {name} ({e})")
            continue
        n = harvest_text(text, name, candidates)
        print(f"[B0] {name}: +{n} nouveaux (total {len(candidates)})")
        time.sleep(1.0)

    print(f"\n[B0] {len(candidates)} candidat(s) unique(s) par domaine.")
    if args.dry_run:
        print("[dry-run] rien ecrit.")
        return
    out = list(candidates.values())
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[B0] ecrit -> {args.out}")


if __name__ == "__main__":
    main()
