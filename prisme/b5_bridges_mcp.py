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
  python b5_bridges_mcp.py                          # dry-run, collecte fraiche (sinon realpage le plus recent)
  python b5_bridges_mcp.py --in data/mon_staging.json
  python b5_bridges_mcp.py --threshold 0.4
  python b5_bridges_mcp.py --no-dry-run --out data/bridges_staging.json
  python b5_bridges_mcp.py --self-test
"""

import argparse
import glob
import math
import json
import os
import re
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
DEFAULT_OUT = os.path.join(DATA_DIR, "bridges_staging.json")
DEFAULT_THRESHOLD = 0.35
DEFAULT_MAX_ALTERNATIVES = 5

# Filtres de bruit pour le Jaccard des descriptions (mesures sur la collecte
# de 59 297 serveurs, cf. rapport) :
#  - un jeton present dans plus de 1 % des descriptions (592 sur 59 297) est
#    du jargon de domaine (agents, search, x402, usdc, paid...) et ne dit rien
#    de la parente de deux serveurs ; la frequence n'est mesuree que si la
#    collecte compte au moins 2000 serveurs (sinon elle ne veut rien dire) ;
#  - une description d'au moins 2 proprietaires differents est un gabarit ;
#  - une description qui annonce un retrait est ecartee ;
#  - il faut au moins 4 jetons significatifs apres filtre pour porter un sens.
DF_MAX_RATIO = 0.01
DF_MIN_CORPUS = 2000
MIN_DESC_TOKENS = 4

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
    ("openai", ["openai"]),
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


# Jetons d'hebergement de code et de domaine de premier niveau : ils decrivent
# ou le serveur est publie, pas de quoi il parle. "io.github.quelquun/outil"
# n'a rien a voir avec github.
CODE_HOSTS = set(["github", "gitlab", "bitbucket", "codeberg", "sourcehut"])
TLD_TOKENS = set([
    "com", "io", "ai", "org", "net", "dev", "app", "co", "edu", "gov", "xyz",
    "me", "sh", "so", "tech", "cloud", "site", "online", "info", "biz",
    "software", "page", "pages", "run",
])

# Espaces de noms de plateformes d'hebergement, en domaine inverse
# (app.vercel.mon-site = mon-site.vercel.app) : le couple n'est pas le proprietaire.
HOSTING_NAMESPACE_PAIRS = set([
    ("app", "vercel"), ("app", "netlify"), ("app", "onrender"), ("app", "railway"),
    ("app", "replit"), ("dev", "workers"), ("dev", "pages"), ("dev", "fly"),
    ("app", "streamlit"), ("me", "glitch"), ("com", "herokuapp"),
])

# Domaines de depot ou d'hebergement : le site pointe vers le depot ou vers
# la plateforme, pas vers le SaaS. Pour ces suffixes, on ne regarde que les
# etiquettes qui precedent (ex. "mon-stripe-outil.vercel.app" -> stripe oui,
# vercel non). Le domaine nu d'un depot (github.com) n'est aucun signal.
HOSTING_DOMAIN_SUFFIXES = (
    "github.com", "github.io", "gitlab.com", "gitlab.io", "bitbucket.org",
    "vercel.app", "netlify.app", "pages.dev", "workers.dev", "herokuapp.com",
    "onrender.com", "fly.dev", "railway.app", "replit.app", "replit.dev",
    "glitch.me", "ngrok.io", "ngrok-free.app", "azurewebsites.net",
    "web.app", "firebaseapp.com", "streamlit.app", "huggingface.co",
    "readthedocs.io", "gitbook.io", "notion.site", "carrd.co",
)
# Sous-domaines propres du depot qui restent un vrai signal (docs.github.com).
HOSTING_REAL_SUBDOMAINS = ("docs.", "api.", "cli.", "support.", "resources.")

_CODE_HOST_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:github|gitlab|bitbucket)\.(?:com|org|io)\S*", re.I)


def split_name(name):
    """'espace.de.noms/nom-du-serveur' -> (espace de noms, nom du serveur)."""
    name = (name or "").strip()
    if "/" in name:
        ns, srv = name.split("/", 1)
        return ns, srv
    return "", name


def owner_tokens(namespace):
    """Proprietaire d'un espace de noms en domaine inverse, sans l'hebergement.
    io.github.quelquun -> quelquun ; com.stripe -> stripe ; ai.adramp ->
    adramp ; br.com -> (rien)."""
    parts = [p for p in (namespace or "").lower().split(".") if p]
    # Hebergeur de code : on retire le couple (io|com).github et consorts.
    if len(parts) >= 2 and parts[1] in CODE_HOSTS:
        parts = parts[2:]
    elif len(parts) >= 2 and (parts[0], parts[1]) in HOSTING_NAMESPACE_PAIRS:
        parts = parts[2:]
    # Domaine de premier niveau en tete et en queue (io, com, ai, uk, co...),
    # etiquette par etiquette : "mon-site" n'est pas le suffixe "site".
    def est_tld(tok):
        return tok in TLD_TOKENS or (len(tok) == 2 and tok.isalpha())
    while parts and est_tld(parts[0]):
        parts = parts[1:]
    while parts and est_tld(parts[-1]):
        parts = parts[:-1]
    tokens = []
    for part in parts:
        tokens.extend(t for t in re.split(r"[^a-z0-9]+", part) if t)
    return tokens


def clean_slug_tokens(slug):
    """Jetons du slug sans le prefixe d'hebergement (io-github-, com-gitlab-)."""
    parts = [p for p in re.split(r"[^a-z0-9]+", (slug or "").lower()) if p]
    if len(parts) >= 2 and (parts[1] in CODE_HOSTS or (parts[0], parts[1]) in HOSTING_NAMESPACE_PAIRS):
        parts = parts[2:]
    return parts


def domain_for_detection(domain_raw):
    """Domaine a comparer aux alias, ou '' si le site n'est qu'un depot ou une
    plateforme d'hebergement. Pour une plateforme, ne garde que les etiquettes
    qui precedent le suffixe."""
    d = (domain_raw or "").lower()
    if not d:
        return ""
    for suf in HOSTING_DOMAIN_SUFFIXES:
        if d == suf:
            return ""
        if d.endswith("." + suf):
            prefix = d[: -(len(suf) + 1)]
            if suf in ("github.com", "gitlab.com") and (prefix + ".").startswith(HOSTING_REAL_SUBDOMAINS):
                return d
            return prefix
    return d


def _contains(haystack_pad, alias):
    alias_norm = normalize_pad(alias)
    return bool(alias_norm and haystack_pad and alias_norm in haystack_pad)


def detect_saas(record):
    """
    Cherche un SaaS connu dans le domaine du site, puis le nom du serveur, le
    proprietaire et le slug (sans la partie hebergement), puis la description.
    Retourne (saas_slug, evidence, weight) ou None. Priorite globale :
    domaine > nom/proprietaire/slug > description. Recherche par jetons
    complets, jamais en sous-chaine au milieu d'un mot.
    """
    domain_raw = extract_domain(record.get("website_url"))
    hs_domain = normalize_pad(domain_for_detection(domain_raw))

    namespace, srv = split_name(record.get("name"))
    owner = owner_tokens(namespace)
    slug_tokens = clean_slug_tokens(record.get("slug"))
    hs_name = normalize_pad(" ".join([srv] + owner + slug_tokens))

    desc = _CODE_HOST_URL_RE.sub(" ", record.get("description") or "")
    hs_desc = normalize_pad(desc)

    for saas_slug, aliases in SAAS_CATALOG:
        for alias in aliases:
            if _contains(hs_domain, alias):
                return saas_slug, "domain:" + domain_raw, DOMAIN_WEIGHT

    for saas_slug, aliases in SAAS_CATALOG:
        for alias in aliases:
            if _contains(hs_name, alias):
                return saas_slug, "name:" + alias, NAME_WEIGHT

    for saas_slug, aliases in SAAS_CATALOG:
        for alias in aliases:
            if _contains(hs_desc, alias):
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


RETIREMENT_RE = re.compile(
    r"^\s*(retired|deprecated|moved to|this (server|package|project|repo|repository|mcp)"
    r" (has been|is|was) (moved|deprecated|retired|archived))", re.I)


def normalize_description(description):
    return " ".join(re.findall(r"[a-z0-9]+", (description or "").lower()))


def is_retirement_description(description):
    return bool(RETIREMENT_RE.match(description or ""))


def filtered_description_tokens(records, df_max_ratio=DF_MAX_RATIO,
                                min_tokens=MIN_DESC_TOKENS):
    """Jetons de description par slug, sans le bruit : jetons trop frequents,
    descriptions de gabarit (partagees par plusieurs proprietaires, ou
    annonce de retrait), descriptions trop pauvres. Un serveur ecarte recoit
    un ensemble vide (il n'entre dans aucun lien desc-jaccard). Retourne
    (tokens_by_slug, stats)."""
    raw = {}
    for r in records:
        raw.setdefault(r["slug"], description_tokens(r.get("description")))

    owners_by_desc = {}
    for r in records:
        norm = normalize_description(r.get("description"))
        if norm:
            owners_by_desc.setdefault(norm, set()).add(
                split_name(r.get("name"))[0].lower() or r["slug"])

    df = {}
    for toks in raw.values():
        for t in toks:
            df[t] = df.get(t, 0) + 1
    n = len(raw)
    too_frequent = set()
    if n >= DF_MIN_CORPUS:
        limit = df_max_ratio * n
        too_frequent = set(t for t, c in df.items() if c > limit)

    stats = {"jetons_trop_frequents": len(too_frequent), "gabarits": 0,
             "retraits": 0, "trop_courts": 0}
    out = {}
    seen = set()
    for r in records:
        slug = r["slug"]
        if slug in seen:
            continue
        seen.add(slug)
        desc = r.get("description")
        if is_retirement_description(desc):
            stats["retraits"] += 1
            out[slug] = set()
            continue
        if len(owners_by_desc.get(normalize_description(desc), ())) >= 2:
            stats["gabarits"] += 1
            out[slug] = set()
            continue
        toks = raw[slug] - too_frequent
        if len(toks) < min_tokens:
            stats["trop_courts"] += 1
            toks = set()
        out[slug] = toks
    return out, stats


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


def _prefix_length(size, threshold):
    """Longueur du prefixe indexe pour garantir de trouver tout couple dont
    le Jaccard est >= threshold (filtrage par prefixe, exact)."""
    need = int(math.ceil(threshold * size - 1e-9))
    return max(1, min(size, size - need + 1))


def _trim(partners, max_alternatives):
    partners.sort(key=lambda p: (-p[0], p[1]))
    del partners[max_alternatives:]


def _same_saas_pairs(groups, tokens_by_slug, max_alternatives):
    """Pour chaque SaaS, chaque membre garde ses meilleurs partenaires
    (similarite de description decroissante, puis slug). Retourne un
    dictionnaire {(slug_a, slug_b): saas} avec slug_a < slug_b."""
    pairs = {}
    for saas, members in groups.items():
        members = sorted(members)
        size = len(members)
        if size < 2:
            continue
        if size - 1 <= max_alternatives:
            for i in range(size):
                for j in range(i + 1, size):
                    pairs[(members[i], members[j])] = saas
            continue
        # Index inverse de jetons dans le groupe. Les jetons presents chez
        # trop de membres ne servent pas a trouver des candidats : ils sont
        # ignores ici seulement, le score reste calcule sur les ensembles
        # complets.
        cap = max(50, size // 10)
        postings = {}
        for slug in members:
            for tok in tokens_by_slug[slug]:
                postings.setdefault(tok, []).append(slug)
        for slug in members:
            toks = tokens_by_slug[slug]
            cands = set()
            for tok in toks:
                plist = postings[tok]
                if len(plist) <= cap:
                    cands.update(plist)
            cands.discard(slug)
            scored = [(jaccard(toks, tokens_by_slug[o]), o) for o in cands]
            scored.sort(key=lambda p: (-p[0], p[1]))
            chosen = [o for _, o in scored[:max_alternatives]]
            if len(chosen) < max_alternatives:
                taken = set(chosen)
                taken.add(slug)
                for o in members:
                    if len(chosen) >= max_alternatives:
                        break
                    if o not in taken:
                        chosen.append(o)
            for o in chosen:
                key = (slug, o) if slug < o else (o, slug)
                pairs[key] = saas
    return pairs


def _jaccard_pairs(slugs, tokens_by_slug, wraps, threshold, max_alternatives):
    """Couples (slug_a < slug_b) dont le Jaccard de description est >= seuil,
    limites aux max_alternatives meilleurs partenaires de chaque serveur.
    Index inverse sur le prefixe des jetons les plus rares (filtrage par
    prefixe) : aucun produit cartesien. Retourne {(a, b): score}."""
    df = {}
    for slug in slugs:
        for tok in tokens_by_slug[slug]:
            df[tok] = df.get(tok, 0) + 1
    ordered = {}
    for slug in slugs:
        ordered[slug] = sorted(tokens_by_slug[slug], key=lambda t: (df[t], t))

    index = {}
    partners = {}
    prune_at = max(50 * max_alternatives, 200)
    for slug in slugs:
        toks = tokens_by_slug[slug]
        size = len(toks)
        if size == 0:
            continue
        prefix = ordered[slug][:_prefix_length(size, threshold)]
        cands = set()
        for tok in prefix:
            plist = index.get(tok)
            if plist:
                cands.update(plist)
        my_saas = wraps.get(slug, (None,))[0]
        for other in cands:
            o_toks = tokens_by_slug[other]
            o_size = len(o_toks)
            if o_size < threshold * size or size < threshold * o_size:
                continue
            if my_saas is not None and wraps.get(other, (None,))[0] == my_saas:
                continue
            score = jaccard(toks, o_toks)
            if score < threshold:
                continue
            partners.setdefault(slug, []).append((score, other))
            theirs = partners.setdefault(other, [])
            theirs.append((score, slug))
            if len(theirs) > prune_at:
                _trim(theirs, max_alternatives)
        if len(partners.get(slug, ())) > prune_at:
            _trim(partners[slug], max_alternatives)
        for tok in prefix:
            index.setdefault(tok, []).append(slug)

    pairs = {}
    for slug, lst in partners.items():
        _trim(lst, max_alternatives)
        for score, other in lst:
            key = (slug, other) if slug < other else (other, slug)
            pairs[key] = score
    return pairs


def build_alternative_of(records, wraps, threshold, max_alternatives=DEFAULT_MAX_ALTERNATIVES,
                         tokens_by_slug=None):
    """Ponts alternative_of sans produit cartesien. Chaque serveur garde au
    plus max_alternatives partenaires de meme SaaS et au plus
    max_alternatives partenaires par Jaccard ; un pont existe s'il figure
    dans la liste d'au moins un des deux serveurs."""
    slugs = sorted(set(r["slug"] for r in records))
    if tokens_by_slug is None:
        tokens_by_slug = {}
        for r in records:
            tokens_by_slug.setdefault(r["slug"], description_tokens(r.get("description")))

    groups = {}
    for slug in slugs:
        w = wraps.get(slug)
        if w:
            groups.setdefault(w[0], []).append(slug)

    saas_pairs = _same_saas_pairs(groups, tokens_by_slug, max_alternatives)
    jac_pairs = _jaccard_pairs(slugs, tokens_by_slug, wraps, threshold, max_alternatives)

    bridges = []
    for (a, b), saas in sorted(saas_pairs.items()):
        bridges.append(make_bridge(
            "mcp_server", a, "mcp_server", b,
            "alternative_of", 1.0, "same-saas:" + saas,
        ))
    for (a, b), score in sorted(jac_pairs.items()):
        bridges.append(make_bridge(
            "mcp_server", a, "mcp_server", b,
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


def build_bridges(records, threshold, max_alternatives=DEFAULT_MAX_ALTERNATIVES,
                  filtrer_bruit=True):
    seen_slugs = set()
    kept = []
    for r in records:
        if isinstance(r, dict) and r.get("slug") and r["slug"] not in seen_slugs:
            seen_slugs.add(r["slug"])
            kept.append(r)
    records = kept
    wraps, wraps_bridges = build_wraps(records)
    tokens = None
    if filtrer_bruit:
        tokens, _ = filtered_description_tokens(records)
    alt_bridges = build_alternative_of(records, wraps, threshold, max_alternatives, tokens)
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
    collecte = os.path.join(DATA_DIR, "mcp_servers_staging.json")
    if os.path.exists(collecte):
        return collecte
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
                    help="fichier staging JSON (defaut: data/mcp_servers_staging.json, sinon le realpage le plus recent)")
    ap.add_argument("--out", default=DEFAULT_OUT,
                    help="fichier bridges de sortie (defaut: data/bridges_staging.json)")
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                    help="seuil de Jaccard pour alternative_of (defaut: 0.35)")
    ap.add_argument("--max-alternatives", type=int, default=DEFAULT_MAX_ALTERNATIVES,
                    help="plafond de partenaires alternative_of gardes par serveur (defaut: 5)")
    ap.add_argument("--dry-run", dest="dry_run", action=argparse.BooleanOptionalAction,
                    default=True,
                    help="n'ecrit pas --out, imprime seulement les compteurs (actif par defaut)")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    if args.threshold <= 0 or args.max_alternatives < 1:
        sys.stderr.write("ERREUR: --threshold doit etre > 0 et --max-alternatives >= 1\n")
        return 2

    in_path = args.in_path or find_default_input()
    if not in_path or not os.path.exists(in_path):
        sys.stderr.write("ERREUR: fichier d'entree introuvable (" + str(in_path) + ")\n")
        return 2

    try:
        records = load_staging(in_path)
    except Exception as e:
        sys.stderr.write("ERREUR lecture staging: " + type(e).__name__ + ": " + str(e) + "\n")
        return 2

    bridges, wraps = build_bridges(records, args.threshold, args.max_alternatives)

    counts = {}
    for b in bridges:
        counts[b["relation"]] = counts.get(b["relation"], 0) + 1

    print("IN " + in_path)
    print("RECORDS " + str(len(records)))
    print("SEUIL jaccard " + str(args.threshold))
    print("PLAFOND alternatives par serveur " + str(args.max_alternatives))
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
        "max_alternatives": args.max_alternatives,
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
