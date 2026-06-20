# -*- coding: utf-8 -*-
"""
collect_logos.py - Chantier A : logos des outils.
Cascade : Clearbit -> DuckDuckGo (ip3, vrai logo HD) -> favicon Google.

Lit les outils publies (slug, website_url, logo_url) depuis Supabase, derive le
domaine depuis website_url, tente dans l'ordre : le logo Clearbit
(logo.clearbit.com), puis l'icone DuckDuckGo (icons.duckduckgo.com/ip3, qui
renvoie souvent l'apple-touch-icon HD), puis le favicon Google
(google.com/s2/favicons, dernier recours). UPSERT du resultat dans
tools.logo_url, puis revalidation ISR des fiches touchees (EN + FR) et de l'accueil.

A lancer sur la machine Windows (le sandbox Cowork n'atteint pas Supabase /
Clearbit / DuckDuckGo / Google).

Pre-requis dans prisme/.env : SUPABASE_URL, SUPABASE_SERVICE_KEY,
REVALIDATE_SECRET, SITE_URL.

Usage :
    python collect_logos.py --dry-run        # tableau outil -> source -> URL, rien ecrit
    python collect_logos.py                   # RAFRAICHIT TOUS les logos (defaut)
    python collect_logos.py --only notion     # un seul outil
    python collect_logos.py --only-missing    # ne touche que les outils sans logo
    python collect_logos.py --force           # explicite : ecrase meme un logo existant
"""
import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SITE_URL = os.environ.get("SITE_URL", "http://localhost:3000").rstrip("/")
REVALIDATE_SECRET = os.environ.get("REVALIDATE_SECRET", "")

CLEARBIT = "https://logo.clearbit.com/{domain}?size=128"
DUCKDUCKGO = "https://icons.duckduckgo.com/ip3/{domain}.ico"
GFAVICON = "https://www.google.com/s2/favicons?domain={domain}&sz=128"

# Taille minimale (octets) pour considerer une image comme reelle (evite de
# stocker une page d'erreur, une image vide ou un placeholder 1x1).
MIN_IMAGE_BYTES = 100
# DuckDuckGo renvoie une petite icone generique quand il ne connait pas le
# domaine ; on exige un peu plus gros pour ne garder que les vrais logos HD.
MIN_DDG_BYTES = 400


def derive_domain(website_url):
    """Extrait un domaine propre (sans www) depuis une URL d'outil."""
    if not website_url:
        return None
    url = website_url.strip()
    if "://" not in url:
        url = "https://" + url
    netloc = urlparse(url).netloc.lower()
    if not netloc:
        return None
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc.split(":")[0] or None


def _is_image(resp):
    ct = resp.headers.get("Content-Type", "").lower()
    return ct.startswith("image/")


def probe_clearbit(session, domain):
    """Retourne l'URL Clearbit si elle renvoie une vraie image, sinon None."""
    url = CLEARBIT.format(domain=domain)
    try:
        r = session.get(url, timeout=10, allow_redirects=True)
    except Exception:
        return None
    if r.status_code == 200 and _is_image(r) and len(r.content) >= MIN_IMAGE_BYTES:
        return url
    return None


def probe_duckduckgo(session, domain):
    """Retourne l'URL DuckDuckGo si elle renvoie une icone consequente, sinon None."""
    url = DUCKDUCKGO.format(domain=domain)
    try:
        r = session.get(url, timeout=10, allow_redirects=True)
    except Exception:
        return None
    if r.status_code == 200 and _is_image(r) and len(r.content) >= MIN_DDG_BYTES:
        return url
    return None


def probe_google(session, domain):
    """Retourne l'URL favicon Google si 200 + image (globe par defaut accepte)."""
    url = GFAVICON.format(domain=domain)
    try:
        r = session.get(url, timeout=10, allow_redirects=True)
    except Exception:
        return None
    if r.status_code == 200 and _is_image(r):
        return url
    return None


def resolve_logo(session, domain):
    """Cascade Clearbit -> DuckDuckGo -> favicon Google. Retourne (source, url)."""
    cb = probe_clearbit(session, domain)
    if cb:
        return "clearbit", cb
    ddg = probe_duckduckgo(session, domain)
    if ddg:
        return "duckduckgo", ddg
    gg = probe_google(session, domain)
    if gg:
        return "google", gg
    return None, None


def revalidate(paths):
    if not REVALIDATE_SECRET:
        print("  (pas de REVALIDATE_SECRET : revalidation ignoree)")
        return
    import requests
    try:
        r = requests.post(
            f"{SITE_URL}/api/revalidate",
            json={"paths": sorted(set(paths))},
            headers={"Authorization": f"Bearer {REVALIDATE_SECRET}"},
            timeout=20,
        )
        print(f"  revalidate -> {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"  revalidate : site injoignable ({e}).")


def main():
    ap = argparse.ArgumentParser(description="Chantier A : logos Clearbit -> DuckDuckGo -> Google")
    ap.add_argument("--dry-run", action="store_true",
                    help="Montre le tableau outil -> source -> URL sans rien ecrire.")
    ap.add_argument("--only", type=str, default="",
                    help="Limite a un seul slug d'outil.")
    ap.add_argument("--only-missing", action="store_true",
                    help="Ne traite que les outils sans logo_url (mode sur).")
    ap.add_argument("--force", action="store_true",
                    help="Ecrase meme un logo existant (le defaut le fait deja).")
    args = ap.parse_args()

    if not (SUPABASE_URL and SERVICE_KEY):
        sys.exit("Requis dans prisme/.env : SUPABASE_URL, SUPABASE_SERVICE_KEY")

    import requests
    from supabase import create_client

    sb = create_client(SUPABASE_URL, SERVICE_KEY)

    q = (sb.table("tools")
         .select("id, slug, name, website_url, logo_url")
         .eq("status", "published"))
    if args.only:
        q = q.eq("slug", args.only)
    tools = q.order("slug").execute().data or []

    if args.only and not tools:
        sys.exit(f"[logos] slug introuvable (ou non publie) : {args.only}")

    if args.only_missing:
        tools = [t for t in tools if not (t.get("logo_url") or "").strip()]

    print(f"[logos] {len(tools)} outil(s) a traiter"
          + (" (mode --only-missing)" if args.only_missing else " (rafraichit tout)"))

    session = requests.Session()
    session.headers.update({"User-Agent": "YggNexus-logo-bot/1.0"})

    touched = []
    nb_clearbit = nb_ddg = nb_google = nb_none = nb_nodomain = 0

    print(f"{'OUTIL':24} {'SOURCE':11} URL")
    print("-" * 80)
    for t in tools:
        slug = t["slug"]
        domain = derive_domain(t.get("website_url"))
        if not domain:
            nb_nodomain += 1
            print(f"{slug:24} {'-':11} (pas de domaine, website_url={t.get('website_url')!r})")
            continue
        source, url = resolve_logo(session, domain)
        if source == "clearbit":
            nb_clearbit += 1
        elif source == "duckduckgo":
            nb_ddg += 1
        elif source == "google":
            nb_google += 1
        else:
            nb_none += 1
            print(f"{slug:24} {'-':11} (aucune image pour {domain})")
            continue

        print(f"{slug:24} {source:11} {url}")

        if not args.dry_run:
            sb.table("tools").update({"logo_url": url}).eq("slug", slug).execute()
            touched.append(slug)

    print("-" * 80)
    print(f"[logos] clearbit={nb_clearbit}  duckduckgo={nb_ddg}  google={nb_google}  "
          f"aucune={nb_none}  sans_domaine={nb_nodomain}")

    if args.dry_run:
        print("[dry-run] aucune ecriture, aucune revalidation.")
        return

    if not touched:
        print("[logos] rien ecrit, pas de revalidation.")
        return

    paths = ["/", "/en", "/fr"]
    for slug in touched:
        paths.append(f"/tools/{slug}")
        paths.append(f"/en/tools/{slug}")
        paths.append(f"/fr/tools/{slug}")
    print(f"[logos] {len(touched)} logo(s) ecrit(s). Revalidation de {len(set(paths))} chemin(s)...")
    revalidate(paths)


if __name__ == "__main__":
    main()
