# -*- coding: utf-8 -*-
"""dump_en_content.py - Exporte le contenu EN a traduire (outils + categories +
alternatives) depuis Supabase vers data/i18n_source_en.json. A lancer sur la
machine Windows (le sandbox Cowork n'atteint pas Supabase).

Pre-requis dans prisme/.env : SUPABASE_URL, SUPABASE_SERVICE_KEY.
Usage : python dump_en_content.py
        python dump_en_content.py --seulement-manquants

--seulement-manquants : ne garde, parmi les outils published, que ceux dont
la traduction FR n'existe pas encore (short_desc_fr vide/null cote Supabase).
Le champ short_desc_fr sert uniquement au filtrage cote client ; il n'est
jamais inclus dans le JSON de sortie (qui reste compose des seuls
TOOL_FIELDS, pour rester compatible avec publish_translations.py).
"""
import argparse
import os, sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

# pricing_note ajoute pour C2 (note de prix traduite).
TOOL_FIELDS = ["slug", "name", "short_desc", "description_md",
               "pricing_note",
               "pros_jsonb", "cons_jsonb", "faq_jsonb",
               "seo_title", "seo_description"]
CAT_FIELDS = ["slug", "name", "description_md", "seo_intro_md",
              "seo_title", "seo_description"]

# Champ ajoute temporairement a la requete Supabase pour filtrer les outils
# deja traduits ; retire du JSON de sortie avant ecriture (cf strip_filter_field).
_FILTRE_FR_FIELD = "short_desc_fr"


def filtrer_non_traduits(tools):
    """Ne garde que les outils dont short_desc_fr est vide/None/whitespace.

    Fonction pure (pas de reseau, pas de DB) pour rester testable isolement.
    """
    manquants = []
    for t in tools:
        valeur = (t.get(_FILTRE_FR_FIELD) or "")
        if not valeur.strip():
            manquants.append(t)
    return manquants


def strip_filter_field(tools):
    """Retire _FILTRE_FR_FIELD des dicts avant l'ecriture du JSON de sortie,
    pour que le format reste limite a TOOL_FIELDS (compat publish_translations.py)."""
    out = []
    for t in tools:
        t2 = dict(t)
        t2.pop(_FILTRE_FR_FIELD, None)
        out.append(t2)
    return out


def dump_alternatives(sb):
    """C3 : raisons d'alternatives a traduire, identifiees par paires de slugs."""
    rows = (sb.table("alternatives")
            .select("reason, t:tool_id(slug), a:alternative_id(slug)")
            .execute().data or [])
    out = []
    for r in rows:
        reason = (r.get("reason") or "").strip()
        ts = (r.get("t") or {}).get("slug")
        als = (r.get("a") or {}).get("slug")
        if reason and ts and als:
            out.append({"tool_slug": ts, "alternative_slug": als, "reason": reason})
    return out


def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        description="Exporte le contenu EN a traduire vers data/i18n_source_en.json.")
    ap.add_argument("--seulement-manquants", action="store_true",
                     help="Ne garde que les outils published sans traduction FR "
                          "(short_desc_fr vide/null).")
    return ap.parse_args(argv)


def main():
    args = parse_args()

    if not (SUPABASE_URL and SERVICE_KEY):
        sys.exit("Requis dans prisme/.env : SUPABASE_URL, SUPABASE_SERVICE_KEY")
    from supabase import create_client
    sb = create_client(SUPABASE_URL, SERVICE_KEY)

    tool_select_fields = list(TOOL_FIELDS)
    if args.seulement_manquants:
        tool_select_fields = tool_select_fields + [_FILTRE_FR_FIELD]

    tools = (sb.table("tools").select(",".join(tool_select_fields))
             .eq("status", "published").order("slug").execute().data or [])
    total_published = len(tools)

    if args.seulement_manquants:
        tools = filtrer_non_traduits(tools)
        tools = strip_filter_field(tools)

    cats = (sb.table("categories").select(",".join(CAT_FIELDS))
            .eq("status", "published").order("slug").execute().data or [])
    alternatives = dump_alternatives(sb)

    out = {"tools": tools, "categories": cats, "alternatives": alternatives}
    path = ROOT / "data" / "i18n_source_en.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.seulement_manquants:
        print(f"[dump] --seulement-manquants actif : {len(tools)} outil(s) non "
              f"traduit(s) retenu(s) sur {total_published} published "
              f"+ {len(cats)} categorie(s) + {len(alternatives)} raison(s) "
              f"d'alternative -> {path}")
    else:
        print(f"[dump] {len(tools)} outil(s) + {len(cats)} categorie(s) + "
              f"{len(alternatives)} raison(s) d'alternative -> {path}")


if __name__ == "__main__":
    main()
