# -*- coding: utf-8 -*-
"""publish_translations.py - Charge data/translations_fr.json dans Supabase :
remplit les colonnes _fr de tools et categories, les raisons _fr des alternatives,
puis revalide les pages /fr. A lancer sur la machine Windows.

Format attendu de data/translations_fr.json :
{
  "tools":      { "<slug>": { "short_desc_fr": "...", "description_md_fr": "...",
                              "pricing_note_fr": "...",
                              "pros_jsonb_fr": [...], "cons_jsonb_fr": [...],
                              "faq_jsonb_fr": [{"q":"...","a":"..."}],
                              "seo_title_fr": "...", "seo_description_fr": "..." } },
  "categories": { "<slug>": { "description_md_fr": "...", "seo_intro_md_fr": "...",
                              "seo_title_fr": "...", "seo_description_fr": "..." } },
  "alternatives": [ { "tool_slug": "...", "alternative_slug": "...",
                      "reason_fr": "..." } ]
}
Champs absents = laisses tels quels (repli EN cote frontend).

Pre-requis dans prisme/.env : SUPABASE_URL, SUPABASE_SERVICE_KEY, REVALIDATE_SECRET, SITE_URL.
Usage : python publish_translations.py [--dry-run]
"""
import os, sys, json, argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SITE_URL = os.environ.get("SITE_URL", "http://localhost:3000").rstrip("/")
REVALIDATE_SECRET = os.environ.get("REVALIDATE_SECRET", "")

TOOL_FR = ["short_desc_fr", "description_md_fr", "pricing_note_fr",
           "pros_jsonb_fr", "cons_jsonb_fr",
           "faq_jsonb_fr", "seo_title_fr", "seo_description_fr"]
CAT_FR = ["description_md_fr", "seo_intro_md_fr", "seo_title_fr", "seo_description_fr"]


def clean(row, allowed):
    return {k: v for k, v in row.items() if k in allowed and v not in (None, "")}


def revalidate(paths):
    if not REVALIDATE_SECRET:
        print("  (pas de REVALIDATE_SECRET : revalidation ignoree)")
        return
    import requests
    try:
        r = requests.post(f"{SITE_URL}/api/revalidate",
                          json={"paths": sorted(set(paths))},
                          headers={"Authorization": f"Bearer {REVALIDATE_SECRET}"},
                          timeout=15)
        print(f"  revalidate -> {r.status_code} {r.text[:200]}")
    except requests.RequestException as e:
        print(f"  revalidate : site injoignable ({e}).")


def publish_alternatives(sb, alts, dry_run, paths):
    """C3 : ecrit reason_fr sur les paires (tool_slug, alternative_slug)."""
    if not alts:
        return 0
    # map slug -> id (un seul aller-retour)
    rows = sb.table("tools").select("id, slug").execute().data or []
    id_by_slug = {r["slug"]: r["id"] for r in rows}
    nb = 0
    for a in alts:
        ts, als = a.get("tool_slug"), a.get("alternative_slug")
        reason_fr = (a.get("reason_fr") or "").strip()
        if not (ts and als and reason_fr):
            continue
        tid, aid = id_by_slug.get(ts), id_by_slug.get(als)
        if tid is None or aid is None:
            print(f"  alt ignoree (slug inconnu) : {ts} -> {als}")
            continue
        if dry_run:
            nb += 1
            continue
        (sb.table("alternatives").update({"reason_fr": reason_fr})
         .eq("tool_id", tid).eq("alternative_id", aid).execute())
        paths.append(f"/fr/tools/{ts}")
        paths.append(f"/fr/tools/{ts}/alternatives")
        nb += 1
    return nb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--in", dest="infile", default=str(ROOT / "data" / "translations_fr.json"))
    args = ap.parse_args()

    data = json.loads(Path(args.infile).read_text(encoding="utf-8"))
    tools = data.get("tools", {})
    cats = data.get("categories", {})
    alts = data.get("alternatives", [])
    print(f"{len(tools)} outil(s) + {len(cats)} categorie(s) + {len(alts)} "
          f"raison(s) d'alternative depuis {args.infile}")

    if args.dry_run:
        for slug, row in list(tools.items())[:5]:
            print(f"  [dry-run] tool {slug}: {sorted(clean(row, TOOL_FR).keys())}")
        for slug, row in list(cats.items())[:5]:
            print(f"  [dry-run] cat {slug}: {sorted(clean(row, CAT_FR).keys())}")
        nb_alt = sum(1 for a in alts if (a.get("reason_fr") or "").strip())
        print(f"  [dry-run] alternatives avec reason_fr : {nb_alt}")
        print("[dry-run] aucune ecriture.")
        return

    if not (SUPABASE_URL and SERVICE_KEY):
        sys.exit("Requis dans prisme/.env : SUPABASE_URL, SUPABASE_SERVICE_KEY")
    from supabase import create_client
    sb = create_client(SUPABASE_URL, SERVICE_KEY)

    paths = ["/fr", "/fr/categories"]
    for slug, row in tools.items():
        payload = clean(row, TOOL_FR)
        if not payload:
            continue
        sb.table("tools").update(payload).eq("slug", slug).execute()
        paths.append(f"/fr/tools/{slug}")
        print(f"  tool {slug} <- {sorted(payload.keys())}")
    for slug, row in cats.items():
        payload = clean(row, CAT_FR)
        if not payload:
            continue
        sb.table("categories").update(payload).eq("slug", slug).execute()
        paths.append(f"/fr/categories/{slug}")
        paths.append(f"/fr/best/{slug}")
        print(f"  cat {slug} <- {sorted(payload.keys())}")

    nb_alt = publish_alternatives(sb, alts, args.dry_run, paths)
    if nb_alt:
        print(f"  {nb_alt} raison(s) d'alternative <- reason_fr")

    print(f"Traductions ecrites. Revalidation de {len(set(paths))} chemin(s) /fr...")
    revalidate(paths)


if __name__ == "__main__":
    main()
