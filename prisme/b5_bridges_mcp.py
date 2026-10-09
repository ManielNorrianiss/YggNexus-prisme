"""
b5_bridges_mcp.py - Construction des ponts (table bridges) pour la verticale MCP.

Lit un fichier de staging JSON produit par b1_mcp.py (liste "records" de
serveurs MCP normalises) et deduit, par signaux explicites uniquement (pas
d'embeddings, pas de LLM, pas de reseau), les lignes bridges suivantes :

  1. mcp_server -> saas_tool   (relation "wraps")
     Deduit du domaine du website_url, du nom/slug canonique du serveur, ou
     de sa description, compares a un catalogue ASCII integre d'une
     trentaine de SaaS connus.

  2. mcp_server -> mcp_server  (relation "alternative_of")
     Meme SaaS sous-jacent detecte (signal fort), ou fort recouvrement de
     mots significatifs de la description (indice de Jaccard sur tokens
     filtres par une liste de mots vides ASCII). Lien symetrique ecrit une
     seule fois par paire triee.

  3. mcp_server -> package     (relation "depends_on")
     Si le serveur a un type de paquet npm ou pypi, cible = "npm:<id>" ou
     "pypi:<id>".

Ce script est un dry-run local : il ne parle jamais au reseau, jamais a
Supabase. Le fichier de sortie (--out) est un JSON local dans prisme/data/,
jamais publie automatiquement.

Usage:
  python b5_bridges_mcp.py                          # dry-run, fichier realpage le plus recent
  python b5_bridges_mcp.py --in data/mon_staging.json
  python b5_bridges_mcp.py --threshold 0.4
  python b5_bridges_mcp.py --no-dry-run --out data/bridges_staging.json
  python b5_bridges_mcp.py --self-test
"""

import argparse
import glob
import itertools
import json
import os
import re
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
DEFAULT_OUT = os.path.join(DATA_DIR, "bridges_staging.json")
DEFAULT_THRESHOLD = 0.35

# Poids par signal de detection SaaS (du plus sur au moins sur).
DOMAIN_WEIGHT = 1.0
NAME_WEIGHT = 0.9
DESC_WEIGHT = 0.75

# target_id pour la relation "wraps" reste un slug texte libre (pas un id
# numerique) : la table saas_tool cote MCP n'existe pas encore, la
# resolution vers un id se fera a la propagation Supabase.
SAAS_TARGET_ID_MODE = "slug"

# Aucun champ d'identifiant de paquet explicite (npm/pypi) n'existe dans le
# staging MCP actuel (b1_mcp.py ne capture que package_type/package_types).
# On utilise donc le champ 'name' du serveur comme proxy d'identifiant,
# avec repli sur 'slug' si 'name' est absent.
PACKAGE_ID_FIELDS = ("package_identifier", "name", "slug")

# Types de paquet couverts par la relation depends_on (cf. consigne : npm/pypi).
PACKAGE_RELATION_TYPES = ("npm", "pypi")

# Catalogue ASCII de SaaS connus : slug canonique -> alias de detection.
# Les alias sont recherches en tant que token(s) complets (bornes par des
# espaces apres normalisation), jamais en sous-chaine brute.
SAAS_CATALOG = [
    ("google-ads", ["google ads", "googleads"]),
    ("meta-ads", ["meta ads", "facebook ads", "metaads"]),
    ("stripe", ["stripe"]),
    ("notion", ["notion"]),
    ("slack", ["slack"]),
    ("github", ["github"]),
    ("linear", ["linear"]),
    ("jira", ["jira"]),
    ("supabase", ["supabase"]),
    ("postgres", ["postgres", "postgresql"]),
    ("shopify", ["shopify"]),
    ("hubspot", ["hubspot"]),
    ("salesforce", ["salesforce"]),
    ("airtable", ["airtable"]),
    ("figma", ["figma"]),
    ("gmail", ["gmail"]),
    ("google-drive", ["google drive", "gdrive"]),
    ("google-calendar", ["google calendar", "gcal"]),
    ("sentry", ["sentry"]),
    ("cloudflare", ["cloudflare"]),
    ("aws", ["amazon web services", "aws"]),
    ("vercel", ["vercel"]),
    ("twilio", ["twilio"]),
    ("openai", ["openai", "open ai"]),
    ("anthropic", ["anthropic"]),
    ("exa", ["exa"]),
    ("tavily", ["tavily"]),
    ("firecrawl", ["firecrawl"]),
    ("brightdata", ["bright data", "brightdata"]),
    ("e2b", ["e2b"]),
    ("binance", ["binance"]),
    ("discord", ["discord"]),
]

# Mots vides ASCII pour le calcul de Jaccard sur les descriptions. Inclut
# des mots vides anglais generiques et du bruit propre aux fiches MCP
# ("mcp", "server", "api", "tool"...).
STOPWORDS = set([
    "a", "an", "and", "any", "are", "as", "at", "be", "by", "for", "from",
    "has", "have", "in", "into", "is", "it", "its", "of", "on", "or",
    "that", "the", "this", "to", "via", "with", "your", "you", "using",
    "use", "used", "mcp", "server", "servers", "api", "tool", "tools",
    "official",
])


# ---------------------------------------------------------------------------
# Normalisation / detection SaaS
# ---------------------------------------------------------------------------

def normalize_pad(text):
    """Minuscule, non-alnum -> espace, borne par des espaces. '' si vide."""
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    if not text:
        return ""
    return " " + text + " "


def extract_domain(url):
    """Retourne le netloc en minuscule (sans www.), ou '' si absent/invalide."""
    if not url:
        return ""
    url = url.strip()
    if not url:
        return ""
    if "//" not in url:
        url = "//" + url
    try:
        netloc = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return ""
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def detect_saas(record):
    """
    Cherche un SaaS connu dans le domaine, puis le nom/slug, puis la
    description du serveur MCP. Retourne (saas_slug, evidence, weight) ou
    None. Priorite globale : domaine > nom/slug > description.
    """
    domain_raw = extract_domain(record.get("website_url"))
    hs_domain = normalize_pad(domain_raw)
    hs_name_slug = normalize_pad((record.get("name") or "") + " " + (record.get("slug") or ""))
    hs_desc = normalize_pad(record.get("description"))

    for saas_slug, aliases in SAAS_CATALOG:
        for alias in aliases:
            alias_norm = normalize_pad(alias)
            if alias_norm and hs_domain and alias_norm in hs_domain:
                return saas_slug, "domain:" + domain_raw, DOMAIN_WEIGHT

    for saas_slug, aliases in SAAS_CATALOG:
        for alias in aliases:
            alias_norm = normalize_pad(alias)
            if alias_norm and hs_name_slug and alias_norm in hs_name_slug:
                return saas_slug, "name:" + alias, NAME_WEIGHT

    for saas_slug, aliases in SAAS_CATALOG:
        for alias in aliases:
            alias_norm = normalize_pad(alias)
            if alias_norm and hs_desc and alias_norm in hs_desc:
                return saas_slug, "desc:" + alias, DESC_WEIGHT

    return None


# ---------------------------------------------------------------------------
# Jaccard sur descriptions
# ---------------------------------------------------------------------------

def description_tokens(description):
    words = re.findall(r"[a-z0-9]+", (description or "").lower())
    return set(w for w in words if w not in STOPWORDS and len(w) > 2)


def jaccard(tokens_a, tokens_b):
    if not tokens_a or not tokens_b:
        return 0.0
    inter = tokens_a & tokens_b
    union = tokens_a | tokens_b
    if not union:
        return 0.0
    return len(inter) / float(len(union))


# ---------------------------------------------------------------------------
# Construction des bridges
# ---------------------------------------------------------------------------

def make_bridge(source_type, source_id, target_type, target_id, relation, weight, evidence):
    return {
        "source_type": source_type,
        "source_id": source_id,
        "target_type": target_type,
        "target_id": target_id,
        "relation": relation,
        "weight": round(float(weight), 4),
        "evidence": evidence,
    }


def package_identifier(record):
    for field in PACKAGE_ID_FIELDS:
        value = (record.get(field) or "").strip()
        if value:
            return value
    return ""


def build_wraps(records):
    """Retourne (wraps_par_slug, liste_bridges_wraps)."""
    wraps = {}
    bridges = []
    for r in records:
        detection = detect_saas(r)
        if not detection:
            continue
        saas_slug, evidence, weight = detection
        wraps[r["slug"]] = (saas_slug, evidence, weight)
        bridges.append(make_bridge(
            "mcp_server", r["slug"], "saas_tool", saas_slug,
            "wraps", weight, evidence,
        ))
    return wraps, bridges


def build_alternative_of(records, wraps, threshold):
    bridges = []
    tokens_by_slug = {r["slug"]: description_tokens(r.get("description")) for r in records}
    for rec_a, rec_b in itertools.combinations(records, 2):
        slug_a, slug_b = rec_a["slug"], rec_b["slug"]
        if slug_a > slug_b:
            slug_a, slug_b = slug_b, slug_a

        wrap_a = wraps.get(slug_a)
        wrap_b = wraps.get(slug_b)
        if wrap_a and wrap_b and wrap_a[0] == wrap_b[0]:
            bridges.append(make_bridge(
                "mcp_server", slug_a, "mcp_server", slug_b,
                "alternative_of", 1.0, "same-saas:" + wrap_a[0],
            ))
            continue

        score = jaccard(tokens_by_slug.get(slug_a, set()), tokens_by_slug.get(slug_b, set()))
        if score >= threshold:
            bridges.append(make_bridge(
                "mcp_server", slug_a, "mcp_server", slug_b,
                "alternative_of", score, "desc-jaccard:" + format(round(score, 2), ".2f"),
            ))
    return bridges


def build_depends_on(records):
    bridges = []
    for r in records:
        types = set(r.get("package_types") or [])
        if r.get("package_type"):
            types.add(r["package_type"])
        ident = package_identifier(r)
        if not ident:
            continue
        for pkg_type in PACKAGE_RELATION_TYPES:
            if pkg_type in types:
                target_id = pkg_type + ":" + ident
                bridges.append(make_bridge(
                    "mcp_server", r["slug"], "package", target_id,
                    "depends_on", 1.0, "package:" + pkg_type,
                ))
    return bridges


def build_bridges(records, threshold):
    records = [r for r in records if isinstance(r, dict) and r.get("slug")]
    wraps, wraps_bridges = build_wraps(records)
    alt_bridges = build_alternative_of(records, wraps, threshold)
    dep_bridges = build_depends_on(records)

    all_bridges = wraps_bridges + alt_bridges + dep_bridges

    seen = set()
    deduped = []
    for b in all_bridges:
        key = (b["source_type"], b["source_id"], b["target_type"], b["target_id"], b["relation"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(b)
    return deduped, wraps


# ---------------------------------------------------------------------------
# Chargement du staging
# ---------------------------------------------------------------------------

def find_default_input():
    pattern = os.path.join(DATA_DIR, "mcp_servers_staging_realpage_*.json")
    candidates = sorted(glob.glob(pattern))
    if not candidates:
        return None
    return candidates[-1]


def load_staging(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        records = data.get("records") or []
    else:
        records = data
    return list(records)


# ---------------------------------------------------------------------------
# Self-test (fixture integree, aucun fichier externe)
# ---------------------------------------------------------------------------

SELF_TEST_RECORDS = [
    {
        "slug": "ai-adramp-google-ads",
        "name": "ai.adramp/google-ads",
        "description": "Google Ads MCP server for campaign management.",
        "website_url": "https://adramp.ai",
        "package_type": None,
        "package_types": [],
    },
    {
        "slug": "ai-adself-ads-manager",
        "name": "ai.adself/ads-manager",
        "description": "Manage Google Ads campaigns and keywords via API.",
        "website_url": None,
        "package_type": None,
        "package_types": [],
    },
    {
        "slug": "ai-adeu-adeu",
        "name": "ai.adeu/adeu",
        "description": "Automated DOCX redlining engine for contracts.",
        "website_url": None,
        "package_type": "npm",
        "package_types": ["npm"],
    },
    {
        "slug": "ai-scrapekit-crawler",
        "name": "ai.scrapekit/crawler",
        "description": "Web scraping and crawling tool for extracting structured data from websites at scale.",
        "website_url": None,
        "package_type": None,
        "package_types": [],
    },
    {
        "slug": "ai-webharvest-crawler",
        "name": "ai.webharvest/crawler",
        "description": "Web scraping and crawling tool for extracting structured data from any website reliably.",
        "website_url": None,
        "package_type": None,
        "package_types": [],
    },
    {
        "slug": "ai-notesync-notes",
        "name": "ai.notesync/notes",
        "description": "Sync personal notes and reminders across devices with offline support.",
        "website_url": None,
        "package_type": None,
        "package_types": [],
    },
    {
        "slug": "ai-metriqpy-metrics",
        "name": "ai.metriqpy/metrics",
        "description": "Python metrics exporter for observability pipelines.",
        "website_url": None,
        "package_type": "pypi",
        "package_types": ["pypi"],
    },
]


def self_test():
    bridges, wraps = build_bridges(SELF_TEST_RECORDS, DEFAULT_THRESHOLD)

    assert wraps.get("ai-adramp-google-ads", (None,))[0] == "google-ads", wraps.get("ai-adramp-google-ads")
    assert wraps.get("ai-adself-ads-manager", (None,))[0] == "google-ads", wraps.get("ai-adself-ads-manager")
    assert "ai-adeu-adeu" not in wraps
    assert "ai-scrapekit-crawler" not in wraps
    assert "ai-notesync-notes" not in wraps
    assert "ai-metriqpy-metrics" not in wraps

    wraps_pairs = set(
        (b["source_id"], b["target_id"]) for b in bridges if b["relation"] == "wraps"
    )
    expected_wraps = set([
        ("ai-adramp-google-ads", "google-ads"),
        ("ai-adself-ads-manager", "google-ads"),
    ])
    assert wraps_pairs == expected_wraps, wraps_pairs

    alt_pairs = set(
        (b["source_id"], b["target_id"]) for b in bridges if b["relation"] == "alternative_of"
    )
    expected_alt = set([
        ("ai-adramp-google-ads", "ai-adself-ads-manager"),
        ("ai-scrapekit-crawler", "ai-webharvest-crawler"),
    ])
    assert alt_pairs == expected_alt, alt_pairs

    same_saas = [b for b in bridges if b["relation"] == "alternative_of" and b["evidence"].startswith("same-saas")]
    assert len(same_saas) == 1 and same_saas[0]["weight"] == 1.0, same_saas

    jaccard_alt = [b for b in bridges if b["relation"] == "alternative_of" and b["evidence"].startswith("desc-jaccard")]
    assert len(jaccard_alt) == 1, jaccard_alt
    assert jaccard_alt[0]["weight"] >= DEFAULT_THRESHOLD, jaccard_alt[0]

    dep_pairs = set(
        (b["source_id"], b["target_id"]) for b in bridges if b["relation"] == "depends_on"
    )
    expected_dep = set([
        ("ai-adeu-adeu", "npm:ai.adeu/adeu"),
        ("ai-metriqpy-metrics", "pypi:ai.metriqpy/metrics"),
    ])
    assert dep_pairs == expected_dep, dep_pairs

    assert len(bridges) == 6, len(bridges)

    print("SELF-TEST OK: 2 wraps, 2 alternative_of (1 same-saas + 1 desc-jaccard), 2 depends_on, total 6")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Batch B5 bridges MCP (dry-run local) - YggNexus"
    )
    ap.add_argument("--in", dest="in_path", default=None,
                    help="fichier staging JSON (defaut: mcp_servers_staging_realpage_*.json le plus recent)")
    ap.add_argument("--out", default=DEFAULT_OUT,
                    help="fichier bridges de sortie (defaut: data/bridges_staging.json)")
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                    help="seuil de Jaccard pour alternative_of (defaut: 0.35)")
    ap.add_argument("--dry-run", dest="dry_run", action=argparse.BooleanOptionalAction,
                    default=True,
                    help="n'ecrit pas --out, imprime seulement les compteurs (actif par defaut)")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    in_path = args.in_path or find_default_input()
    if not in_path or not os.path.exists(in_path):
        sys.stderr.write("ERREUR: fichier d'entree introuvable (" + str(in_path) + ")\n")
        return 2

    try:
        records = load_staging(in_path)
    except Exception as e:
        sys.stderr.write("ERREUR lecture staging: " + type(e).__name__ + ": " + str(e) + "\n")
        return 2

    bridges, wraps = build_bridges(records, args.threshold)

    counts = {}
    for b in bridges:
        counts[b["relation"]] = counts.get(b["relation"], 0) + 1

    print("IN " + in_path)
    print("RECORDS " + str(len(records)))
    print("SEUIL jaccard " + str(args.threshold))
    for rel in ("wraps", "alternative_of", "depends_on"):
        print(rel.upper() + " " + str(counts.get(rel, 0)))
    print("TOTAL bridges " + str(len(bridges)))

    if args.dry_run:
        print("DRY-RUN: aucune ecriture locale ni Supabase. Rien n'est publie.")
        return 0

    os.makedirs(DATA_DIR, exist_ok=True)
    payload = {
        "source_file": in_path,
        "threshold": args.threshold,
        "generated": len(bridges),
        "by_relation": counts,
        "bridges": bridges,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print("WROTE " + args.out)
    print("Propagation Supabase reservee a Josue (hors de ce script).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
