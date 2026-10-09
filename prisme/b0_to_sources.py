# -*- coding: utf-8 -*-
"""
b0_to_sources.py - Transforme data/candidates.json en entrees sources.json,
en dedupliquant, en filtrant par CREDIBILITE (nb de listes qui citent l'outil),
et optionnellement en VERIFIANT que le site repond (liveness HTTP).

Credibilite : chaque candidat porte "sources" = listes qui le mentionnent.
Plus il apparait dans de listes, plus il est credible. Les nouvelles entrees
sont triees par credibilite decroissante (on ingere les plus solides d'abord).

Ecrit data/sources_new.json (a relire), ou fusionne dans sources.json avec --append.

Usage :
    python b0_to_sources.py --check-supabase --dry-run
    python b0_to_sources.py --check-supabase --min-lists 2      # garde les cites >= 2 fois
    python b0_to_sources.py --check-supabase --verify           # drop les sites morts (HTTP)
    python b0_to_sources.py --check-supabase --verify --append  # fusionne dans sources.json
    python b0_to_sources.py --limit 300                         # plafonne (les + credibles)
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
SOURCES = ROOT / "data" / "sources.json"


def slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return re.sub(r"-{2,}", "-", s)


def domain_of(url):
    try:
        net = urlparse(url).netloc.lower().split(":")[0]
    except Exception:
        return ""
    return net[4:] if net.startswith("www.") else net


def slug_from_domain(domain):
    parts = [p for p in domain.split(".") if p]
    base = parts[-2] if len(parts) >= 2 else (parts[0] if parts else domain)
    sl = slugify(base)
    if len(sl) < 2:
        sl = slugify(domain.replace(".", "-"))
    return sl


def load_json(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def supabase_published():
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except Exception:
        pass
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not (url and key):
        print("  (Supabase non configure, --check-supabase ignore)")
        return set(), set()
    from supabase import create_client
    sb = create_client(url, key)
    rows = sb.table("tools").select("slug, website_url").execute().data or []
    return ({r["slug"] for r in rows},
            {domain_of(r.get("website_url") or "") for r in rows} - {""})


def alive(url):
    """True si le site repond (statut < 400). GET leger, poli, tolerant."""
    import requests
    try:
        r = requests.get(url, timeout=8, allow_redirects=True, stream=True,
                         headers={"User-Agent": "Mozilla/5.0 YggNexus-verify/1.0"})
        ok = r.status_code < 400
        r.close()
        return ok
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", default=str(ROOT / "data" / "candidates.json"))
    ap.add_argument("--out", default=str(ROOT / "data" / "sources_new.json"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--append", action="store_true", help="Ajoute dans sources.json")
    ap.add_argument("--check-supabase", action="store_true")
    ap.add_argument("--min-lists", type=int, default=1,
                    help="Credibilite mini : nb de listes distinctes citant l'outil (defaut 1)")
    ap.add_argument("--verify", action="store_true",
                    help="Verifie que chaque site repond (HTTP) avant de garder. LENT mais propre.")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    cands = load_json(args.infile, [])
    existing = load_json(SOURCES, [])
    print(f"{len(cands)} candidat(s), {len(existing)} source(s) existante(s)")

    used_slugs = {s["slug"] for s in existing}
    used_domains = {domain_of(s.get("website_url") or "") for s in existing} - {""}

    if args.check_supabase:
        sb_slugs, sb_domains = supabase_published()
        if sb_slugs:
            used_slugs |= sb_slugs
            used_domains |= sb_domains
            print(f"  + {len(sb_slugs)} slug(s) publie(s) Supabase exclus")

    # credibilite = nb de listes distinctes ; tri decroissant
    def cred(c):
        return len(set(c.get("sources") or []))
    cands = sorted(cands, key=cred, reverse=True)

    new_entries = []
    nb_dup_domain = nb_dup_slug = nb_lowcred = nb_dead = 0
    for c in cands:
        dom = c.get("domain") or domain_of(c.get("website_url") or "")
        if not dom:
            continue
        if cred(c) < args.min_lists:
            nb_lowcred += 1
            continue
        if dom in used_domains:
            nb_dup_domain += 1
            continue
        slug = slug_from_domain(dom)
        if slug in used_slugs:
            slug2 = f"{slug}-{dom.split('.')[-1]}"
            if slug2 in used_slugs:
                nb_dup_slug += 1
                continue
            slug = slug2
        url = c.get("website_url") or f"https://{dom}"
        if args.verify:
            if not alive(url):
                nb_dead += 1
                used_domains.add(dom)  # ne pas re-tester
                continue
            time.sleep(0.3)
        new_entries.append({
            "slug": slug,
            "name": (c.get("name") or slug).strip()[:80],
            "vendor": "",
            "website_url": url,
            "categories": [],
            "primary_category": "",
            "_cred": cred(c),
        })
        used_slugs.add(slug)
        used_domains.add(dom)
        if args.limit and len(new_entries) >= args.limit:
            break

    print(f"-> {len(new_entries)} NOUVELLE(S) | {nb_dup_domain} domaine(s) connu(s), "
          f"{nb_dup_slug} collision(s) slug, {nb_lowcred} sous le seuil credibilite"
          + (f", {nb_dead} site(s) mort(s)" if args.verify else ""))

    # retire le champ technique _cred avant ecriture (sources.json = schema fixe)
    clean = [{k: v for k, v in e.items() if k != "_cred"} for e in new_entries]

    if args.dry_run:
        for e in new_entries[:15]:
            print(f"   [{e['_cred']}listes] {e['slug']:22} {e['website_url']}")
        print("[dry-run] rien ecrit.")
        return

    if args.append:
        merged = existing + clean
        SOURCES.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[append] sources.json -> {len(merged)} entrees")
    else:
        Path(args.out).write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[ecrit] {args.out} ({len(clean)} entrees, triees par credibilite)")


if __name__ == "__main__":
    main()
