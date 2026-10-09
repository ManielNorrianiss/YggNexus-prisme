"""
IndexNow - notification instantanee des moteurs (Bing, Yandex, Seznam)
apres publication. Etape non critique du run_nightly, apres 'pages'.

Usage :
    python indexnow.py --init     # genere la cle, l ecrit dans .env et frontend/public/<cle>.txt
    python indexnow.py            # ping les outils publies modifies depuis 36h + pages coeur
    python indexnow.py --all      # ping tous les outils publies
    python indexnow.py --hours 12 # fenetre personnalisee
    python indexnow.py --dry-run  # montre les URLs sans rien envoyer
"""
import argparse
import json
import os
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SITE_URL = os.environ.get("SITE_URL", "https://www.yggnexus.com").rstrip("/")
INDEXNOW_KEY = os.environ.get("INDEXNOW_KEY", "")

ENDPOINT = "https://api.indexnow.org/indexnow"
CORE_PATHS = ["/", "/tools", "/fr", "/fr/tools"]
PUBLIC_DIR = ROOT.parent / "frontend" / "public"


def init_key():
    key = secrets.token_hex(16)
    env_path = ROOT / ".env"
    content = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    if "INDEXNOW_KEY=" in content:
        print("INDEXNOW_KEY existe deja dans .env : rien a faire.")
        return 0
    with open(env_path, "a", encoding="utf-8") as f:
        if content and not content.endswith("\n"):
            f.write("\n")
        f.write("INDEXNOW_KEY={}\n".format(key))
    key_file = PUBLIC_DIR / "{}.txt".format(key)
    key_file.write_text(key, encoding="utf-8")
    print("Cle generee.")
    print("Fichier public : {}".format(key_file))
    print("IMPORTANT : commit + push du frontend pour deployer le fichier de cle.")
    return 0


def recent_slugs(hours, all_tools=False):
    import requests
    params = {"select": "slug", "status": "eq.published"}
    if not all_tools:
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        params["updated_at"] = "gte.{}".format(since)
    r = requests.get(
        "{}/rest/v1/tools".format(SUPABASE_URL),
        params=params,
        headers={"apikey": SERVICE_KEY, "Authorization": "Bearer {}".format(SERVICE_KEY)},
        timeout=30,
    )
    r.raise_for_status()
    return [row["slug"] for row in r.json() if row.get("slug")]


def build_urls(slugs):
    urls = [SITE_URL + p for p in CORE_PATHS]
    for slug in slugs:
        urls.append("{}/tools/{}".format(SITE_URL, slug))
        urls.append("{}/fr/tools/{}".format(SITE_URL, slug))
    return sorted(set(urls))


def ping(urls, dry_run=False):
    import requests
    host = SITE_URL.split("//", 1)[-1]
    payload = {
        "host": host,
        "key": INDEXNOW_KEY,
        "keyLocation": "{}/{}.txt".format(SITE_URL, INDEXNOW_KEY),
        "urlList": urls[:10000],
    }
    if dry_run:
        print("DRY-RUN : {} URLs seraient envoyees a IndexNow.".format(len(urls)))
        for u in urls[:20]:
            print("  " + u)
        if len(urls) > 20:
            print("  ... (+{})".format(len(urls) - 20))
        return 0
    r = requests.post(ENDPOINT, json=payload, timeout=30)
    if r.status_code in (200, 202):
        print("IndexNow OK ({}) : {} URLs notifiees.".format(r.status_code, len(payload["urlList"])))
        return 0
    print("IndexNow ECHEC {} : {}".format(r.status_code, r.text[:300]))
    return 1


def main():
    parser = argparse.ArgumentParser(description="Ping IndexNow apres publication.")
    parser.add_argument("--init", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--hours", type=int, default=36)
    args = parser.parse_args()

    if args.init:
        return init_key()
    if not INDEXNOW_KEY:
        print("INDEXNOW_KEY absent : lancer 'python indexnow.py --init' puis deployer le frontend.")
        return 1
    if not SUPABASE_URL or not SERVICE_KEY:
        print("SUPABASE_URL / SUPABASE_SERVICE_KEY manquants dans .env.")
        return 1
    slugs = recent_slugs(args.hours, all_tools=args.all)
    if not slugs and not args.all:
        print("Aucun outil modifie depuis {}h : ping des pages coeur seulement.".format(args.hours))
    urls = build_urls(slugs)
    return ping(urls, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
