# -*- coding: utf-8 -*-
"""
b8_sante.py - Batch B8 : verifications de sante du catalogue et du site.

Controles cote base (Supabase) :
  - outils publies sans categorie / sans categorie primaire
  - outils publies sans embedding
  - outils publies avec champs SEO manquants (seo_title / seo_description / description_md)
  - outils avec quality_score hors borne (null, < 0 ou > 10)
  - categories publiees sans aucun outil (orphelines)
  - fraicheur : outils non mis a jour depuis --stale-days jours

Controles cote site (crawl HTTP, sauf si --no-crawl) :
  - liens casses : chaque page /tools/<slug>, /categories/<slug>, /best/<slug>
    publiee doit repondre 200

Sortie : rapport exports/health/<YYYY-MM-DD>.md + resume console.
Code de sortie non nul si le total de problemes depasse --fail-threshold
(utile pour declencher une alerte n8n).

Usage:
    python b8_sante.py
    python b8_sante.py --dry-run         # n'ecrit pas le rapport
    python b8_sante.py --no-crawl        # seulement les controles base
    python b8_sante.py --stale-days 60
    python b8_sante.py --fail-threshold 5
    python b8_sante.py --limit 50        # limite le nombre de pages crawlees
    python b8_sante.py --source staging  # lit staging.db (lecture seule, aucun reseau)
"""
import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY  = os.environ.get("SUPABASE_SERVICE_KEY", "")
SITE_URL     = os.environ.get("SITE_URL", "http://localhost:3000").rstrip("/")

EXPORTS_DIR = ROOT.parent / "exports" / "health"
STAGING_DB = ROOT / "staging.db"


# ---------------------------------------------------------------------------
# Helpers temps
# ---------------------------------------------------------------------------

def parse_dt(value):
    """Parse une date ISO (avec ou sans 'Z') -> datetime aware, ou None."""
    if not value:
        return None
    s = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ---------------------------------------------------------------------------
# Controles base (fonctions PURES -> testables sans reseau)
# ---------------------------------------------------------------------------

def db_checks(tools, categories, tool_cat_rows, embed_tool_ids,
              stale_days, now_dt):
    """
    Retourne une liste de sections (titre, [problemes]).
    - tools          : list de dicts {id, slug, seo_title, seo_description,
                       description_md, quality_score, updated_at}
    - categories     : list de dicts {id, slug}
    - tool_cat_rows  : list de dicts {tool_id, category_id, is_primary}
    - embed_tool_ids : set des tool_id ayant un embedding
    """
    sections = []

    # index categories par tool_id
    cats_by_tool = {}
    primary_by_tool = {}
    for r in tool_cat_rows:
        tid = r.get("tool_id")
        cats_by_tool.setdefault(tid, []).append(r.get("category_id"))
        if r.get("is_primary"):
            primary_by_tool[tid] = True

    # 1. sans categorie
    p = [f"{t['slug']} (id {t['id']})" for t in tools
         if not cats_by_tool.get(t["id"])]
    if False:  # categories retirees (2026-06-21) — controle desactive
        sections.append(("Outils publies sans categorie", p))

    # 2. sans categorie primaire (mais avec au moins une categorie)
    p = [f"{t['slug']} (id {t['id']})" for t in tools
         if cats_by_tool.get(t["id"]) and not primary_by_tool.get(t["id"])]
    if False:  # categories retirees (2026-06-21) — controle desactive
        sections.append(("Outils sans categorie primaire", p))

    # 3. sans embedding
    p = [f"{t['slug']} (id {t['id']})" for t in tools
         if t["id"] not in embed_tool_ids]
    sections.append(("Outils publies sans embedding", p))

    # 4. champs SEO manquants
    def manque(t):
        miss = [f for f in ("seo_title", "seo_description", "description_md")
                if not (t.get(f) or "").strip()]
        return miss
    p = []
    for t in tools:
        miss = manque(t)
        if miss:
            p.append(f"{t['slug']} -> manque {', '.join(miss)}")
    sections.append(("Outils avec champs SEO manquants", p))

    # 5. quality_score hors borne
    p = []
    for t in tools:
        q = t.get("quality_score")
        if q is None:
            p.append(f"{t['slug']} -> quality_score absent")
        else:
            try:
                qf = float(q)
                if qf < 0 or qf > 10:
                    p.append(f"{t['slug']} -> quality_score={qf} (hors 0-10)")
            except (TypeError, ValueError):
                p.append(f"{t['slug']} -> quality_score invalide ({q!r})")
    sections.append(("Outils avec quality_score hors borne", p))

    if False:  # categories retirees (2026-06-21) — check orphelines desactive
        # 6. categories orphelines (aucun outil rattache)
        used_cat_ids = {cid for cids in cats_by_tool.values() for cid in cids}
        p = [f"{c['slug']} (id {c['id']})" for c in categories
             if c["id"] not in used_cat_ids]
        sections.append(("Categories publiees sans aucun outil", p))

    # 7. fraicheur
    limite = now_dt - timedelta(days=stale_days)
    p = []
    for t in tools:
        dt = parse_dt(t.get("updated_at"))
        if dt is not None and dt < limite:
            p.append(f"{t['slug']} -> maj {dt.date()} (> {stale_days} j)")
    sections.append((f"Outils non mis a jour depuis {stale_days} jours", p))

    return sections


# ---------------------------------------------------------------------------
# Controles site (crawl)
# ---------------------------------------------------------------------------

def crawl_checks(urls, limit=0):
    """Verifie que chaque URL repond 200. Retourne (titre, [problemes])."""
    import requests
    if limit and limit > 0:
        urls = urls[:limit]
    problems = []
    sess = requests.Session()
    sess.headers.update({"User-Agent": "YggNexus-B8-HealthCheck"})
    for u in urls:
        try:
            r = sess.get(u, timeout=15, allow_redirects=True)
            if r.status_code != 200:
                problems.append(f"{u} -> HTTP {r.status_code}")
        except requests.RequestException as e:
            problems.append(f"{u} -> erreur reseau ({e.__class__.__name__})")
    return (f"Liens internes casses ({len(urls)} pages verifiees)", problems)


def build_urls(site, tool_slugs, cat_slugs):
    """Construit la liste des URL internes a verifier."""
    urls = [site + "/"]
    urls += [f"{site}/tools/{s}" for s in tool_slugs]
    # categories retirees (2026-06-21) — /categories et /best retires (routes supprimees)
    # urls += [f"{site}/categories/{s}" for s in cat_slugs]
    # urls += [f"{site}/best/{s}" for s in cat_slugs]
    return urls


# ---------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------

def render_report(sections, now_dt, site, crawled):
    total = sum(len(p) for _, p in sections)
    lines = []
    lines.append(f"# Rapport de sante YggNexus — {now_dt.date()}")
    lines.append("")
    lines.append(f"Genere le {now_dt.isoformat(timespec='seconds')}")
    lines.append(f"Site : {site}")
    lines.append(f"Crawl : {'oui' if crawled else 'non (--no-crawl)'}")
    lines.append("")
    lines.append(f"**Total de problemes : {total}**")
    lines.append("")
    lines.append("## Resume")
    lines.append("")
    lines.append("| Controle | Problemes |")
    lines.append("|---|---|")
    for titre, p in sections:
        lines.append(f"| {titre} | {len(p)} |")
    lines.append("")
    for titre, p in sections:
        lines.append(f"## {titre} — {len(p)}")
        lines.append("")
        if not p:
            lines.append("Aucun probleme. ✅")
        else:
            for item in p:
                lines.append(f"- {item}")
        lines.append("")
    return total, "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Acces Supabase
# ---------------------------------------------------------------------------

def _fetch_all(query_builder, page=1000):
    """Pagine par .range() : Supabase plafonne chaque reponse a 1000 lignes
    (max-rows), donc .limit(100000) seul tronque silencieusement."""
    rows, start = [], 0
    while True:
        chunk = query_builder.range(start, start + page - 1).execute().data or []
        rows.extend(chunk)
        if len(chunk) < page:
            return rows
        start += page


def fetch_from_supabase():
    """Lit tools/categories/tool_categories/embeddings publies depuis Supabase."""
    from supabase import create_client
    sb = create_client(SUPABASE_URL, SERVICE_KEY)

    tools = _fetch_all(sb.table("tools").select(
        "id, slug, seo_title, seo_description, description_md, "
        "quality_score, updated_at"
    ).eq("status", "published").order("id"))

    categories = _fetch_all(sb.table("categories").select(
        "id, slug"
    ).eq("status", "published").order("id"))

    tool_cat = _fetch_all(sb.table("tool_categories").select(
        "tool_id, category_id, is_primary"
    ).order("tool_id"))

    emb = _fetch_all(sb.table("embeddings").select(
        "entity_id"
    ).eq("entity_type", "tool").order("entity_id"))
    embed_ids = {r["entity_id"] for r in emb}

    return tools, categories, tool_cat, embed_ids


# ---------------------------------------------------------------------------
# Source staging.db (lecture seule, aucun reseau)
# ---------------------------------------------------------------------------

def fetch_from_staging(db_path=None):
    """
    Lit la base locale de preparation en LECTURE SEULE (mode=ro).
    Retourne (tools, categories, tool_cat, embed_ids, brut) : memes formes que
    fetch_from_supabase (id = slug), plus `brut`, un dict de lignes pour
    staging_checks.
    """
    chemin = Path(db_path or STAGING_DB)
    if not chemin.exists():
        raise FileNotFoundError(f"staging.db introuvable : {chemin}")
    con = sqlite3.connect(f"file:{chemin.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        tools = [dict(r, id=r["slug"]) for r in con.execute(
            "SELECT slug, seo_title, seo_description, description_md, "
            "quality_score, enriched_at AS updated_at FROM enriched_tools "
            "ORDER BY slug")]
        tool_cat = [{"tool_id": r["tool_slug"], "category_id": r["category_slug"],
                     "is_primary": bool(r["is_primary"])}
                    for r in con.execute(
                        "SELECT tool_slug, category_slug, is_primary "
                        "FROM tool_categories")]
        categories = [{"id": c, "slug": c} for c in
                      sorted({r["category_id"] for r in tool_cat})]
        emb = [dict(r) for r in con.execute(
            "SELECT slug, model, dim, embedding_json FROM tool_embeddings")]
        embed_ids = {e["slug"] for e in emb}
        brut = {
            "raw": [dict(r) for r in con.execute(
                "SELECT slug, status, echecs FROM raw_tools")],
            "embeddings": emb,
            "tagging": [r["tool_slug"] for r in con.execute(
                "SELECT tool_slug FROM tool_tagging")],
            "dedup": [dict(r) for r in con.execute(
                "SELECT slug, canonical_slug FROM dedup_map")],
        }
    finally:
        con.close()
    return tools, categories, tool_cat, embed_ids, brut


def staging_checks(tools, tool_cat, brut):
    """
    Controles propres a staging.db (fonctions PURES). Retourne une liste de
    sections (titre, [problemes]).
    """
    sections = []
    slugs_enrichis = {t["slug"] for t in tools}
    slugs_bruts = {r["slug"] for r in brut["raw"]}

    sections.append(("Fiches enrichies sans ligne brute",
                     sorted(slugs_enrichis - slugs_bruts)))
    sections.append(("Lignes brutes sans fiche enrichie",
                     sorted(slugs_bruts - slugs_enrichis)))

    p = sorted({f"{r['tool_id']} -> {r['category_id']}" for r in tool_cat
                if r["tool_id"] not in slugs_enrichis})
    sections.append(("Classements pointant vers un outil inconnu", p))

    sections.append(("Outils enrichis sans etiquetage",
                     sorted(slugs_enrichis - set(brut["tagging"]))))

    # embeddings : orphelins, JSON illisible, dimension incoherente
    p = []
    dims = {}
    for e in brut["embeddings"]:
        if e["slug"] not in slugs_enrichis:
            p.append(f"{e['slug']} -> embedding sans fiche enrichie")
        try:
            v = json.loads(e.get("embedding_json") or "null")
        except (TypeError, ValueError):
            p.append(f"{e['slug']} -> embedding_json illisible")
            continue
        if not isinstance(v, list) or not v:
            p.append(f"{e['slug']} -> embedding vide")
            continue
        dims.setdefault(len(v), []).append(e["slug"])
        if e.get("dim") not in (None, len(v)):
            p.append(f"{e['slug']} -> dim declaree {e.get('dim')} != {len(v)}")
    if len(dims) > 1:
        majoritaire = max(dims, key=lambda d: len(dims[d]))
        for d, lst in dims.items():
            if d != majoritaire:
                p += [f"{s} -> dimension {d} (majoritaire : {majoritaire})"
                      for s in lst]
    sections.append(("Embeddings incoherents", p))

    # doublons : canonique absent ou boucle
    canon = {r["slug"]: r["canonical_slug"] for r in brut["dedup"]}
    p = []
    for s, c in canon.items():
        if canon.get(c) == s:
            p.append(f"{s} <-> {c} -> boucle de doublons")
        elif c not in slugs_bruts:
            p.append(f"{s} -> canonique {c} absent")
    sections.append(("Doublons : canonique absent ou boucle", sorted(p)))

    # titres SEO en double
    vus = {}
    for t in tools:
        k = (t.get("seo_title") or "").strip().lower()
        if k:
            vus.setdefault(k, []).append(t["slug"])
    p = [f"{', '.join(sorted(v))} -> meme seo_title"
         for v in vus.values() if len(v) > 1]
    sections.append(("Titres SEO en double", sorted(p)))
    return sections


def main_staging(args):
    """Rapport de sante sur staging.db : aucun reseau, aucune ecriture en base."""
    now_dt = datetime.now(timezone.utc)
    print("[B8] lecture staging.db (lecture seule)...")
    tools, categories, tool_cat, embed_ids, brut = fetch_from_staging()
    print(f"[B8] {len(tools)} outils, {len(categories)} categories, "
          f"{len(tool_cat)} classements, {len(embed_ids)} embeddings.")
    sections = db_checks(tools, categories, tool_cat, embed_ids,
                         args.stale_days, now_dt)
    sections += staging_checks(tools, tool_cat, brut)
    total, report = render_report(sections, now_dt, "staging.db", False)
    report = report.replace("Crawl : non (--no-crawl)",
                            "Crawl : non (source staging)")
    if not args.dry_run:
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out = EXPORTS_DIR / f"{now_dt.date()}_staging.md"
        out.write_text(report, encoding="utf-8")
        print(f"[B8] rapport ecrit : {out}")
    else:
        print("[B8] --dry-run : rapport non ecrit. Apercu :\n")
        print(report)
    print(f"\n[B8] Resume : {total} probleme(s).")
    for titre, p in sections:
        flag = "ok" if not p else f"!! {len(p)}"
        print(f"   [{flag}] {titre}")
    if args.fail_threshold and total > args.fail_threshold:
        print(f"[B8] total ({total}) > seuil ({args.fail_threshold}) -> sortie 1.")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Batch B8 - sante")
    parser.add_argument("--dry-run", action="store_true",
                        help="N'ecrit pas le fichier rapport.")
    parser.add_argument("--no-crawl", action="store_true",
                        help="Saute les controles HTTP (base seulement).")
    parser.add_argument("--stale-days", type=int, default=90)
    parser.add_argument("--fail-threshold", type=int, default=0,
                        help="Code de sortie 1 si total de problemes > seuil "
                             "(0 = jamais echouer).")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limite le nombre de pages crawlees.")
    parser.add_argument("--source", choices=("supabase", "staging"),
                        default="supabase",
                        help="supabase (defaut : lecture + crawl du site) ou "
                             "staging (staging.db en lecture seule, sans reseau).")
    args = parser.parse_args()

    # Console Windows (cp1252) : le rapport contient des emojis (--dry-run).
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    if args.source == "staging":
        return main_staging(args)

    if not SUPABASE_URL or not SERVICE_KEY:
        sys.exit("SUPABASE_URL et SUPABASE_SERVICE_KEY requis dans prisme/.env.")

    now_dt = datetime.now(timezone.utc)

    print("[B8] lecture Supabase...")
    tools, categories, tool_cat, embed_ids = fetch_from_supabase()
    print(f"[B8] {len(tools)} outils, {len(categories)} categories, "
          f"{len(tool_cat)} liens tool-categorie, {len(embed_ids)} embeddings.")

    sections = db_checks(tools, categories, tool_cat, embed_ids,
                         args.stale_days, now_dt)

    crawled = not args.no_crawl
    if crawled:
        urls = build_urls(SITE_URL,
                          [t["slug"] for t in tools],
                          [c["slug"] for c in categories])
        print(f"[B8] crawl de {len(urls)} pages sur {SITE_URL}...")
        sections.append(crawl_checks(urls, limit=args.limit))

    total, report = render_report(sections, now_dt, SITE_URL, crawled)

    if not args.dry_run:
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out = EXPORTS_DIR / f"{now_dt.date()}.md"
        out.write_text(report, encoding="utf-8")
        print(f"[B8] rapport ecrit : {out}")
    else:
        print("[B8] --dry-run : rapport non ecrit. Apercu :\n")
        print(report)

    print(f"\n[B8] Resume : {total} probleme(s).")
    for titre, p in sections:
        flag = "ok" if not p else f"!! {len(p)}"
        print(f"   [{flag}] {titre}")

    if args.fail_threshold and total > args.fail_threshold:
        print(f"[B8] total ({total}) > seuil ({args.fail_threshold}) -> sortie 1.")
        sys.exit(1)


if __name__ == "__main__":
    main()
