# -*- coding: utf-8 -*-
"""
b1_collecte.py - Batch B1 : collecte des pages web des outils.
Lit data/sources.json, fetche chaque site, extrait titre/meta/texte,
calcule source_hash, stocke dans staging.db (raw_tools).

Usage:
    python b1_collecte.py
    python b1_collecte.py --dry-run
    python b1_collecte.py --limit 3
    python b1_collecte.py --only n8n
"""
import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# --- import optionnel beautifulsoup4 ---
try:
    from bs4 import BeautifulSoup
    _BS4 = True
except ImportError:
    _BS4 = False

try:
    import requests as _requests
    _REQUESTS = True
except ImportError:
    _REQUESTS = False

import staging


UA = "YggNexusBot/1.0 (+https://yggnexus.com/bot)"
TIMEOUT = 15
SLEEP_BETWEEN = 1.0
MAX_TEXT = 2000


def load_sources():
    path = ROOT / "data" / "sources.json"
    if not path.exists():
        sys.exit(f"Introuvable: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_page(url):
    """Fetche l'URL et retourne (content_bytes, final_url)."""
    if _REQUESTS:
        r = _requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT, allow_redirects=True)
        r.raise_for_status()
        return r.content, r.url
    else:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read(), resp.url


def _extract_bs4(html_bytes):
    soup = BeautifulSoup(html_bytes, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    meta_desc = ""
    for tag in soup.find_all("meta"):
        n = tag.get("name", "").lower()
        p = tag.get("property", "").lower()
        if n == "description" or p == "og:description":
            meta_desc = tag.get("content", "")
            if meta_desc:
                break
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    raw_text = soup.get_text(separator=" ", strip=True)[:MAX_TEXT]
    return title, meta_desc, raw_text


def _extract_regex(html_bytes):
    import re
    html = html_bytes.decode("utf-8", errors="replace")
    title = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if m:
        title = re.sub(r"<[^>]+>", "", m.group(1)).strip()
    meta_desc = ""
    m2 = re.search(
        r'<meta[^>]+(?:name=["\']description["\']|property=["\']og:description["\'])[^>]+content=["\']([^"\']*)["\']',
        html, re.IGNORECASE,
    )
    if not m2:
        m2 = re.search(
            r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:name=["\']description["\']|property=["\']og:description["\'])',
            html, re.IGNORECASE,
        )
    if m2:
        meta_desc = m2.group(1).strip()
    clean = re.sub(r"<[^>]+>", " ", html)
    clean = re.sub(r"\s+", " ", clean).strip()
    raw_text = clean[:MAX_TEXT]
    return title, meta_desc, raw_text


def extract(html_bytes):
    if _BS4:
        return _extract_bs4(html_bytes)
    return _extract_regex(html_bytes)


def sha256(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description="Batch B1 collecte")
    parser.add_argument("--dry-run", action="store_true", help="N'ecrit pas en staging")
    parser.add_argument("--limit", type=int, default=0, help="Nombre max d'outils a traiter")
    parser.add_argument("--only", type=str, default="", help="Traiter seulement ce slug")
    args = parser.parse_args()

    sources = load_sources()
    if args.only:
        sources = [s for s in sources if s["slug"] == args.only]
        if not sources:
            sys.exit(f"Slug introuvable dans sources.json: {args.only}")
    if args.limit > 0:
        sources = sources[: args.limit]

    staging.init_db()

    nb_collect = 0
    nb_skip = 0
    nb_error = 0

    for src in sources:
        slug = src["slug"]
        url  = src["website_url"]
        print(f"[B1] {slug} <- {url}")

        if args.dry_run:
            print(f"  [dry-run] skip fetch, upsert ignore")
            nb_collect += 1
            continue

        try:
            html, final_url = fetch_page(url)
        except Exception as e:
            print(f"  ERREUR fetch: {e}")
            nb_error += 1
            time.sleep(SLEEP_BETWEEN)
            continue

        h = sha256(html)
        existing = staging.get_raw(slug)
        if existing and existing.get("source_hash") == h:
            print(f"  inchange (hash identique), skip")
            nb_skip += 1
            time.sleep(SLEEP_BETWEEN)
            continue

        try:
            title, meta_desc, raw_text = extract(html)
        except Exception as e:
            print(f"  ERREUR extraction: {e}")
            nb_error += 1
            time.sleep(SLEEP_BETWEEN)
            continue

        cats = src.get("categories", [])
        row = {
            "slug":             slug,
            "name":             src.get("name", slug),
            "vendor":           src.get("vendor", ""),
            "website_url":      url,
            "source_url":       final_url,
            "source_hash":      h,
            "raw_title":        title,
            "raw_meta_desc":    meta_desc,
            "raw_text":         raw_text,
            "categories_json":  json.dumps(cats),
            "primary_category": src.get("primary_category", ""),
            "status":           "draft",
            "collected_at":     datetime.now(timezone.utc).isoformat(),
        }
        staging.upsert_raw(row)
        print(f"  collecte: title={title[:60]!r}")
        nb_collect += 1
        time.sleep(SLEEP_BETWEEN)

    print(f"\n[B1] Resume: {nb_collect} collecte(s), {nb_skip} inchange(s), {nb_error} erreur(s).")


if __name__ == "__main__":
    main()
