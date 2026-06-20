# -*- coding: utf-8 -*-
"""
revalidate_paths.py - revalide (ISR on-demand) une liste de chemins passes en argument.
Utile apres un changement de CONTENU direct dans Supabase (intro SEO d'une categorie,
etc.) qui ne passe ni par publish.py ni par sync_categories.py.

Usage :
    python revalidate_paths.py /categories/ai-coding /categories/ai-video /categories
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

SITE_URL = os.environ.get("SITE_URL", "http://localhost:3000").rstrip("/")
REVALIDATE_SECRET = os.environ.get("REVALIDATE_SECRET", "")


def main():
    paths = [a for a in sys.argv[1:] if a.startswith("/")]
    if not paths:
        sys.exit("Donne au moins un chemin, ex: python revalidate_paths.py /categories/ai-coding")
    if not REVALIDATE_SECRET:
        sys.exit("REVALIDATE_SECRET manquant dans prisme/.env")
    import requests
    try:
        r = requests.post(
            f"{SITE_URL}/api/revalidate",
            json={"paths": sorted(set(paths))},
            headers={"Authorization": f"Bearer {REVALIDATE_SECRET}"},
            timeout=20,
        )
        print(f"revalidate -> {r.status_code} {r.text[:300]}")
    except Exception as e:
        sys.exit(f"site injoignable : {e}")


if __name__ == "__main__":
    main()
