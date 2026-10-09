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
    python b1_collecte.py --workers 8
    python b1_collecte.py --run-id 20260701T120000Z
"""
import argparse
import hashlib
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
import memoire_prisme


UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
}
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
        r = _requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        r.raise_for_status()
        return r.content, r.url
    else:
        import urllib.request
        req = urllib.request.Request(url, headers=HEADERS)
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


def collect_one(src, dry_run):
    """
    Travail effectue par chaque worker : fetch + extraction seulement.
    Ne touche PAS a staging (ecritures reservees au fil principal).
    L'echec d'une page ne doit jamais lever -- toujours retourner un dict.

    Retourne un dict:
        {"slug", "status": "collected"|"skipped"|"error",
         "row": dict|None, "message": str}
    """
    slug = src["slug"]
    url  = src["website_url"]

    if dry_run:
        return {"slug": slug, "status": "skipped", "row": None,
                "message": "[dry-run] skip fetch, upsert ignore"}

    try:
        html, final_url = fetch_page(url)
    except Exception as e:
        return {"slug": slug, "status": "error", "row": None,
                "message": f"ERREUR fetch: {e}"}

    h = sha256(html)
    existing = staging.get_raw(slug)
    if existing and existing.get("source_hash") == h:
        return {"slug": slug, "status": "skipped", "row": None,
                "message": "inchange (hash identique), skip"}

    try:
        title, meta_desc, raw_text = extract(html)
    except Exception as e:
        return {"slug": slug, "status": "error", "row": None,
                "message": f"ERREUR extraction: {e}"}

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
    return {"slug": slug, "status": "collected", "row": row,
            "message": f"collecte: title={title[:60]!r}"}


def run_collecte(sources, workers, dry_run, run_id=None, log_fn=None):
    """
    Distribue sources sur un ThreadPoolExecutor (workers threads) pour les
    requetes HTTP + extraction. Les ecritures en staging (upsert_raw) se
    font depuis le fil principal, sequentiellement, a mesure que les
    resultats arrivent. L'echec d'une page (fetch/extraction) ne tue jamais
    le lot -- il est compte comme erreur et le traitement continue.

    Les echecs de fetch/extraction sont journalises dans run_log sous le
    type d'evenement 'page_morte' (si log_fn est fourni et dry_run=False).

    Retourne (nb_collect, nb_skip, nb_error).
    """
    total = len(sources)
    nb_collect = 0
    nb_skip = 0
    nb_error = 0
    done = 0
    t_debut = time.time()

    workers = max(1, workers)

    def _consigner(type_evenement, detail, slug=None, niveau="erreur"):
        if log_fn is not None:
            try:
                log_fn(run_id=run_id, etape="b1", type_evenement=type_evenement,
                       detail=detail, slug=slug, niveau=niveau)
            except Exception:
                pass

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(collect_one, src, dry_run): src["slug"]
            for src in sources
        }
        for future in as_completed(futures):
            slug = futures[future]
            try:
                res = future.result()
            except Exception as e:
                res = {"slug": slug, "status": "error", "row": None,
                       "message": f"ERREUR inattendue: {e}"}

            done += 1
            elapsed = max(time.time() - t_debut, 1e-9)
            vitesse = done / elapsed

            print(f"[B1] ({done}/{total}, {vitesse:.2f}/s) {res['slug']}: {res['message']}")

            if res["status"] == "collected":
                staging.upsert_raw(res["row"])
                nb_collect += 1
            elif res["status"] == "skipped":
                if not dry_run:
                    nb_skip += 1
                else:
                    nb_collect += 1
            else:
                nb_error += 1
                if not dry_run:
                    _consigner("page_morte", res["message"], slug=res["slug"])

    return nb_collect, nb_skip, nb_error


def main():
    parser = argparse.ArgumentParser(description="Batch B1 collecte")
    parser.add_argument("--dry-run", action="store_true", help="N'ecrit pas en staging")
    parser.add_argument("--limit", type=int, default=0, help="Nombre max d'outils a traiter")
    parser.add_argument("--only", type=str, default="", help="Traiter seulement ce slug")
    parser.add_argument("--workers", type=int, default=None,
                        help="Nombre de fils paralleles pour les requetes HTTP "
                             "(defaut: valeur apprise dans data/parametres_appris.json, sinon 8)")
    parser.add_argument("--run-id", type=str, default="",
                        help="Identifiant de run partage (defaut: horodatage genere)")
    args = parser.parse_args()

    sources = load_sources()
    if args.only:
        sources = [s for s in sources if s["slug"] == args.only]
        if not sources:
            sys.exit(f"Slug introuvable dans sources.json: {args.only}")
    if args.limit > 0:
        sources = sources[: args.limit]

    staging.init_db()
    staging.init_memoire()

    params_appris = memoire_prisme.charger_parametres()
    workers = args.workers if args.workers is not None else int(params_appris.get("b1_workers", 8))

    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    log_fn = None if args.dry_run else staging.log_evenement

    if not args.dry_run:
        staging.log_evenement(run_id, "b1", "debut",
                               f"{len(sources)} source(s) a traiter, workers={workers}",
                               niveau="info")

    print(f"[B1] run_id={run_id} {len(sources)} source(s) a traiter, workers={workers}")

    nb_collect, nb_skip, nb_error = run_collecte(
        sources, workers, args.dry_run, run_id=run_id, log_fn=log_fn
    )

    if not args.dry_run:
        staging.log_evenement(run_id, "b1", "fin",
                               f"{nb_collect} collecte(s), {nb_skip} inchange(s), {nb_error} erreur(s)",
                               niveau="info")

    print(f"\n[B1] Resume: {nb_collect} collecte(s), {nb_skip} inchange(s), {nb_error} erreur(s).")


if __name__ == "__main__":
    main()
