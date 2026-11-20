# -*- coding: utf-8 -*-
"""
b5_liens.py - Batch B5 : calcul des liens semantiques (alternatives) par similarite cosinus.

Lit les embeddings depuis Supabase (table embeddings, entity_type='tool'),
calcule la similarite cosinus entre tous les outils publies,
et ecrit les top-N alternatives dans la table alternatives.

Raisons d'alternatives : le texte ecrit dans alternatives.reason N'EST PLUS
un texte de debogage cosinus (le frontend filtre /semantic similarity|cosine/i,
cf. frontend/components/ToolCard.tsx). Chaque raison est desormais une phrase
courte et factuelle en anglais (<=140 caracteres), generee :
    - par defaut, via LLM role "arbitre" (llm_local.modele_pour("arbitre")),
      en parallele (ThreadPoolExecutor, --workers) ;
    - en repli propre (--sans-llm, ou Ollama injoignable) via un gabarit
      construit a partir des categories/pricing des deux outils.

Usage:
    python b5_liens.py
    python b5_liens.py --dry-run
    python b5_liens.py --top 5 --threshold 0.55
    python b5_liens.py --only my-tool-slug
    python b5_liens.py --limit 10
    python b5_liens.py --model nomic-embed-text
    python b5_liens.py --workers 4
    python b5_liens.py --sans-llm
    python b5_liens.py --ajouts-seulement --dry-run --montrer --sans-llm
"""
import argparse
import json
import os
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from llm_local import generer_json, modele_pour, LLMError

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY  = os.environ.get("SUPABASE_SERVICE_KEY", "")

MAX_LEN_RAISON = 140
MAX_LEN_RAISON_FR = 180  # le francais est plus long que l'anglais
PAGE_LECTURE = 1000
DOSSIER_TRACES = ROOT.parent / "exports" / "b5"

SYSTEM_PROMPT_RAISON = (
    "You write short, factual one-sentence comparisons between two SaaS/AI "
    "tools for a directory's 'alternatives' section. Output ONLY valid JSON "
    "with exactly one key: \"reason\". The value is a single English sentence, "
    "maximum 140 characters, stating what the alternative tool does that is "
    "comparable to or different from the main tool (category, pricing model, "
    "or a concrete distinguishing feature). Never mention 'cosine', "
    "'similarity', 'embedding', or any internal scoring mechanism. No "
    "markdown, no extra keys, no comments."
)

# ---------------------------------------------------------------------------
# Cosine similarity helpers (numpy required)
# ---------------------------------------------------------------------------

def ensure_numpy():
    """Import numpy, install if missing."""
    try:
        import numpy as np
        return np
    except ImportError:
        import subprocess
        print("[B5] numpy absent -- installation en cours...")
        subprocess.check_call([sys.executable, "-m", "pip", "install",
                               "numpy", "--break-system-packages"],
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)
        import numpy as np
        return np


def cosine_matrix(np, vectors):
    """
    Compute a cosine similarity matrix for a list of vectors.
    vectors: list of 1-D array-like of the same dimension.
    Returns a 2-D numpy array of shape (N, N).
    """
    mat = np.array(vectors, dtype=float)
    # Normalize each row
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    # Avoid division by zero
    norms = np.where(norms == 0, 1.0, norms)
    mat_norm = mat / norms
    # Dot product -> cosine similarity
    return mat_norm @ mat_norm.T


def clamp_similarity(val):
    """Round to 3 decimals and cap at 9.999 (NUMERIC(4,3) constraint)."""
    val = round(float(val), 3)
    return min(val, 9.999)


# ---------------------------------------------------------------------------
# Data loading from Supabase
# ---------------------------------------------------------------------------

def load_categories_principales(sb):
    """Return {tool_id: slug de la categorie principale du site}.

    Regle : la categorie principale d'un outil est la ligne de tool_categories
    dont is_primary vaut true (colonne posee par publish.py : is_primary =
    (cat_slug == primary_category)), jointe a categories par category_id pour
    le slug. Un outil sans ligne is_primary n'a pas de categorie principale :
    il est absent du dict. Si, par erreur, un outil avait plusieurs lignes
    is_primary, on garde celle dont category_id est le plus petit (ordre
    deterministe). Lecture seule, paginee."""
    slug_par_cat = {}
    offset = 0
    while True:
        res = sb.table("categories") \
                .select("id,slug") \
                .order("id") \
                .range(offset, offset + PAGE_LECTURE - 1) \
                .execute()
        batch = res.data if (res is not None and res.data) else []
        for row in batch:
            slug_par_cat[row["id"]] = row.get("slug") or ""
        if len(batch) < PAGE_LECTURE:
            break
        offset += PAGE_LECTURE

    principales = {}
    offset = 0
    while True:
        res = sb.table("tool_categories") \
                .select("tool_id,category_id,is_primary") \
                .eq("is_primary", True) \
                .order("tool_id") \
                .order("category_id") \
                .range(offset, offset + PAGE_LECTURE - 1) \
                .execute()
        batch = res.data if (res is not None and res.data) else []
        for row in batch:
            slug = slug_par_cat.get(row["category_id"], "")
            if slug and row["tool_id"] not in principales:
                principales[row["tool_id"]] = slug
        if len(batch) < PAGE_LECTURE:
            break
        offset += PAGE_LECTURE
    return principales


def load_tools(sb):
    """Return list of published tools: [{id, slug, name, pricing,
    pricing_note, categorie_site}, ...]. Pagine jusqu'au bout
    (PostgREST plafonne chaque reponse a 1000 lignes).

    categorie_site : slug de la categorie principale du site (voir
    load_categories_principales), '' si l'outil n'en a pas. Le champ libre
    tools.application_category n'est plus lu : ce n'est pas la categorie du
    site (audit du 2026-11-20)."""
    tools = []
    offset = 0
    while True:
        res = sb.table("tools") \
                .select("id,slug,name,pricing,pricing_note") \
                .eq("status", "published") \
                .order("id") \
                .range(offset, offset + PAGE_LECTURE - 1) \
                .execute()
        batch = res.data if (res is not None and res.data) else []
        tools.extend(batch)
        if len(batch) < PAGE_LECTURE:
            break
        offset += PAGE_LECTURE
    principales = load_categories_principales(sb)
    for t in tools:
        t["categorie_site"] = principales.get(t.get("id"), "")
    return tools


def load_paires_existantes(sb):
    """Return l'ensemble {(tool_id, alternative_id)} deja presentes dans
    alternatives. Lecture seule, paginee."""
    paires = set()
    offset = 0
    while True:
        res = sb.table("alternatives") \
                .select("tool_id,alternative_id") \
                .order("tool_id") \
                .order("alternative_id") \
                .range(offset, offset + PAGE_LECTURE - 1) \
                .execute()
        batch = res.data if (res is not None and res.data) else []
        for row in batch:
            paires.add((row["tool_id"], row["alternative_id"]))
        if len(batch) < PAGE_LECTURE:
            break
        offset += PAGE_LECTURE
    return paires


def load_embeddings(sb, model):
    """
    Return dict {entity_id (int): [float, ...]} for entity_type='tool'.
    Uses pagination to handle large catalogs.
    """
    PAGE = 1000
    offset = 0
    emb_map = {}
    while True:
        res = sb.table("embeddings") \
                .select("entity_id,embedding") \
                .eq("entity_type", "tool") \
                .eq("model", model) \
                .range(offset, offset + PAGE - 1) \
                .execute()
        batch = res.data if (res is not None and res.data) else []
        for row in batch:
            eid = row["entity_id"]
            vec = row["embedding"]
            # embedding may be stored as a list or a JSON string
            if isinstance(vec, str):
                import json
                vec = json.loads(vec)
            if vec:
                emb_map[eid] = vec
        if len(batch) < PAGE:
            break
        offset += PAGE
    return emb_map


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def compute_alternatives(np, tools_with_vec, top_n, threshold):
    """
    Given a list of (tool_id, slug, name, vector), compute alternatives.
    Returns dict: {tool_id: [(alt_id, alt_slug, similarity), ...]}
    sorted descending by similarity, capped at top_n, filtered by threshold.

    Vectorise (matrice x matrice) : le clamp_similarity et le filtrage par
    seuil sont appliques sur toute la matrice d'un coup avec numpy plutot
    qu'avec une double boucle Python -- comportement identique (memes
    valeurs, meme ordre de tri) pour des listes de quelques dizaines
    d'elements ou plus.
    """
    ids    = [t[0] for t in tools_with_vec]
    slugs  = [t[1] for t in tools_with_vec]
    vecs   = [t[3] for t in tools_with_vec]

    sim_mat = cosine_matrix(np, vecs)
    n = len(ids)

    # clamp_similarity vectorise : round a 3 decimales puis cap a 9.999.
    sim_clamped = np.minimum(np.round(sim_mat, 3), 9.999)

    result = {}
    for i in range(n):
        row = sim_clamped[i]
        candidates = [
            (ids[j], slugs[j], float(row[j]))
            for j in range(n)
            if j != i and row[j] >= threshold
        ]
        # Sort descending by similarity
        candidates.sort(key=lambda x: x[2], reverse=True)
        result[ids[i]] = candidates[:top_n]

    return result


# ---------------------------------------------------------------------------
# Raisons d'alternatives (gabarit + LLM)
# ---------------------------------------------------------------------------

def _pricing_label(pricing):
    """Normalise une valeur pricing_model (enum Supabase) en texte anglais lisible."""
    mapping = {
        "free": "free",
        "freemium": "freemium",
        "paid": "paid",
        "open_source": "open source",
        "unknown": "of unknown pricing",
    }
    return mapping.get((pricing or "").strip().lower(), "of unknown pricing")


# Libelles des neuf categories du site (taxonomie : data/taxonomy.json), un seul
# tableau. "en" : libelle de gabarit (repris de LIBELLE_SITE de
# b5_audit_categories.py). "fr" : nom que le site affiche deja en francais
# (CATEGORY_NAME_FR de frontend/lib/localize.ts), accents en \u pour garder
# ce fichier en ASCII.
CATEGORIES_SITE = {
    "ai-writing":    {"en": "AI writing",        "fr": "R\u00e9daction IA"},
    "automation":    {"en": "automation",        "fr": "Automatisation"},
    "ai-images":     {"en": "AI image",          "fr": "Images IA"},
    "ai-audio":      {"en": "AI audio",          "fr": "Audio IA"},
    "data-scraping": {"en": "data and scraping", "fr": "Donn\u00e9es & Scraping"},
    "productivity":  {"en": "productivity",      "fr": "Productivit\u00e9"},
    "no-code":       {"en": "no-code",           "fr": "No-Code"},
    "ai-coding":     {"en": "AI coding",         "fr": "Codage IA"},
    "ai-video":      {"en": "AI video",          "fr": "Vid\u00e9o IA"},
}


def _category_label(categorie_site, langue="en"):
    """
    Libelle de la categorie du site pour un slug de la taxonomie ('ai-video'
    -> 'AI video' en anglais, 'Vid\u00e9o IA' en francais). Chaine vide si le slug
    est vide ou inconnu : l'appelant n'ecrit alors aucun libelle.
    """
    entree = CATEGORIES_SITE.get((categorie_site or "").strip())
    if not entree:
        return ""
    return entree["fr" if langue == "fr" else "en"]


def _un(libelle):
    """Article indefini anglais : 'an' devant une voyelle ('an AI video'), sinon 'a'."""
    return "an" if libelle[:1].lower() in "aeiou" else "a"


def couper_raison(texte, max_len=MAX_LEN_RAISON):
    """
    Ramene une raison dans max_len caracteres sans jamais couper un mot :
    garde la derniere phrase complete qui tient ; sinon coupe au dernier
    espace, retire la ponctuation pendante et termine par un point.
    """
    texte = " ".join((texte or "").split())
    if len(texte) <= max_len:
        return texte
    morceau = texte[:max_len]
    # derniere fin de phrase qui tient (suivie d'un espace dans le texte
    # complet, pour ne pas couper "3.5")
    fin = -1
    for i, c in enumerate(morceau):
        if c in ".!?" and texte[i + 1:i + 2] == " ":
            fin = i
    if fin >= max_len // 4:
        return texte[:fin + 1]
    # il faut garder une place pour le point final
    limite = max_len - 1
    morceau = texte[:limite]
    if texte[limite] != " ":
        coupe = morceau.rfind(" ")
        if coupe > 0:
            morceau = morceau[:coupe]
    morceau = morceau.rstrip(" ,;:-(&/")
    return (morceau + ".") if morceau else texte[:limite] + "."


def raison_gabarit(tool, alt_tool):
    """
    Construit une raison courte (<=140 caracteres) sans LLM, a partir des
    categories/pricing des deux outils. Ne contient jamais 'cosine' ni
    'similarity' -- passe le filtre frontend /semantic similarity|cosine/i.

    tool, alt_tool : dict avec au moins name, pricing, categorie_site (slug de
    la categorie principale du site, '' si aucune). Quand une categorie manque,
    la phrase ne porte ni parenthese ni libelle pour cet outil.
    """
    cat_tool = _category_label(tool.get("categorie_site"))
    cat_alt = _category_label(alt_tool.get("categorie_site"))
    prix_tool = _pricing_label(tool.get("pricing"))
    prix_alt = _pricing_label(alt_tool.get("pricing"))
    nom_tool = tool.get("name", "the main tool")
    nom_alt = alt_tool.get("name", "This tool")

    if cat_tool and cat_alt:
        if cat_tool == cat_alt:
            base = f"Both are {cat_tool} tools"
        else:
            base = f"{nom_alt} is {_un(cat_alt)} {cat_alt} tool, unlike {nom_tool} ({cat_tool})"
    elif cat_alt:
        base = f"{nom_alt} is {_un(cat_alt)} {cat_alt} alternative to {nom_tool}"
    elif cat_tool:
        base = f"{nom_alt} is an alternative to {nom_tool} ({cat_tool})"
    else:
        base = f"{nom_alt} is an alternative to {nom_tool}"

    if prix_tool == prix_alt:
        raison = f"{base}, both {prix_alt}."
    else:
        raison = f"{base}; {alt_tool.get('name', 'it')} is {prix_alt} while {nom_tool} is {prix_tool}."

    # Phrase trop longue (noms longs) : on laisse tomber la proposition sur le
    # prix plutot que de la couper en plein milieu ("... is of unknown pricing
    # while.").
    if len(" ".join(raison.split())) > MAX_LEN_RAISON:
        raison = f"{base}."

    return couper_raison(raison)


# Prix en francais : (singulier, pluriel) par valeur de l'enum pricing_model.
PRIX_FR = {
    "free": ("gratuit", "gratuits"),
    "freemium": ("freemium", "freemium"),
    "paid": ("payant", "payants"),
    "open_source": ("libre", "libres"),
    "unknown": ("\u00e0 prix inconnu", "\u00e0 prix inconnu"),
}


def _prix_fr(pricing):
    return PRIX_FR.get((pricing or "").strip().lower(), PRIX_FR["unknown"])


def raison_gabarit_fr(tool, alt_tool):
    """
    Pendant francais de raison_gabarit (colonne alternatives.reason_fr), meme
    logique : libelle de la categorie du site quand elle existe, rien (ni
    parenthese ni guillemets) quand elle manque. Max MAX_LEN_RAISON_FR.
    """
    cat_tool = _category_label(tool.get("categorie_site"), "fr")
    cat_alt = _category_label(alt_tool.get("categorie_site"), "fr")
    prix_tool = _prix_fr(tool.get("pricing"))
    prix_alt = _prix_fr(alt_tool.get("pricing"))
    nom_tool = tool.get("name", "l'outil principal")
    nom_alt = alt_tool.get("name", "Cet outil")
    g, d = "\u00ab ", " \u00bb"

    if cat_tool and cat_alt:
        if cat_tool == cat_alt:
            base = f"Les deux sont des outils de la cat\u00e9gorie {g}{cat_tool}{d}"
        else:
            base = (f"{nom_alt} rel\u00e8ve de la cat\u00e9gorie {g}{cat_alt}{d}, "
                    f"contrairement \u00e0 {nom_tool} ({g}{cat_tool}{d})")
    elif cat_alt:
        base = f"{nom_alt}, de la cat\u00e9gorie {g}{cat_alt}{d}, est une alternative \u00e0 {nom_tool}"
    elif cat_tool:
        base = f"{nom_alt} est une alternative \u00e0 {nom_tool} ({g}{cat_tool}{d})"
    else:
        base = f"{nom_alt} est une alternative \u00e0 {nom_tool}"

    if prix_tool == prix_alt:
        raison = f"{base}, tous deux {prix_alt[1]}."
    else:
        raison = f"{base} ; {nom_alt} est {prix_alt[0]} alors que {nom_tool} est {prix_tool[0]}."

    # Meme regle qu'en anglais : plutot la phrase de base entiere qu'une
    # proposition sur le prix coupee en plein milieu.
    if len(" ".join(raison.split())) > MAX_LEN_RAISON_FR:
        raison = f"{base}."

    return couper_raison(raison, MAX_LEN_RAISON_FR)


def raison_llm(fn_gen, tool, alt_tool, model, timeout=60):
    """
    Demande au LLM (role arbitre par defaut) une raison courte. Leve
    LLMError si Ollama est injoignable / sortie invalide -- l'appelant
    doit retomber sur raison_gabarit en cas d'echec.
    """
    def _fiche(t):
        cat = _category_label(t.get("categorie_site"))
        morceaux = ([f"category: {cat}"] if cat else []) + [f"pricing: {_pricing_label(t.get('pricing'))}"]
        return f"{t.get('name', '')} ({', '.join(morceaux)})"

    prompt = (
        f"Main tool: {_fiche(tool)}\n"
        f"Alternative tool: {_fiche(alt_tool)}\n\n"
        "Write the one-sentence reason (JSON key \"reason\")."
    )
    sortie = fn_gen(prompt, SYSTEM_PROMPT_RAISON, modele=model, timeout=timeout)
    if not isinstance(sortie, dict):
        raise LLMError("sortie raison non-dict")
    raison = sortie.get("reason")
    if not isinstance(raison, str) or not raison.strip():
        raise LLMError("cle 'reason' manquante ou vide")
    raison = raison.strip()
    if _contient_terme_interdit(raison):
        raise LLMError("raison LLM contient un terme interdit (cosine/similarity)")
    return couper_raison(raison)


def _contient_terme_interdit(texte):
    """Meme filtre que le frontend (ToolCard.tsx) : /semantic similarity|cosine/i."""
    import re
    return re.search(r"semantic similarity|cosine", texte, re.IGNORECASE) is not None


def generer_raison(fn_gen, tool, alt_tool, model, sans_llm):
    """
    Point d'entree unique pour obtenir une raison d'alternative.
    sans_llm=True ou fn_gen=None -> gabarit direct.
    Sinon tente le LLM, retombe sur le gabarit a la moindre erreur.
    """
    if sans_llm or fn_gen is None:
        return raison_gabarit(tool, alt_tool)
    try:
        return raison_llm(fn_gen, tool, alt_tool, model)
    except Exception:
        return raison_gabarit(tool, alt_tool)


def generer_raisons_paire(fn_gen, tools_index, paires, model, sans_llm, workers):
    """
    Genere les raisons pour une liste de paires (tool_id, alt_id) en
    parallele (ThreadPoolExecutor). Retourne un dict
    {(tool_id, alt_id): raison}.

    tools_index : dict {tool_id: {id, slug, name, pricing, ...}}
    """
    resultat = {}
    if not paires:
        return resultat

    def _travail(paire):
        tool_id, alt_id = paire
        tool = tools_index.get(tool_id, {})
        alt_tool = tools_index.get(alt_id, {})
        return paire, generer_raison(fn_gen, tool, alt_tool, model, sans_llm)

    workers = max(1, workers)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for paire, raison in executor.map(_travail, paires):
            resultat[paire] = raison

    return resultat


def generer_raisons_fr_paire(tools_index, paires):
    """{(tool_id, alt_id): raison francaise} par gabarit (jamais de LLM)."""
    return {(t, a): raison_gabarit_fr(tools_index.get(t, {}), tools_index.get(a, {}))
            for (t, a) in paires}


def construire_apercu(nouvelles, tools_index, raisons, raisons_fr):
    """
    Lignes d'apercu du mode --ajouts-seulement : pour chaque paire a ajouter,
    le nom des deux outils, la categorie imprimee de chacun ('aucune' si
    l'outil n'a pas de categorie du site) et les deux raisons completes.
    nouvelles : liste de (tool_id, slug, alt_id, alt_slug, sim).
    """
    def _cat(t):
        return _category_label(t.get("categorie_site")) or "aucune"

    apercu = []
    for tool_id, slug, alt_id, alt_slug, sim in nouvelles:
        t = tools_index.get(tool_id, {})
        a = tools_index.get(alt_id, {})
        apercu.append({
            "outil": t.get("name", slug),
            "outil_slug": slug,
            "categorie_outil": _cat(t),
            "alternative": a.get("name", alt_slug),
            "alternative_slug": alt_slug,
            "categorie_alternative": _cat(a),
            "similarity": sim,
            "reason": raisons.get((tool_id, alt_id), ""),
            "reason_fr": raisons_fr.get((tool_id, alt_id), ""),
        })
    return apercu


def ecrire_apercu(apercu, dossier=None, horodatage=None):
    """Ecrit exports/b5/apercu_<horodatage>.json (fichier local, aucune
    ecriture en base). Retourne le chemin."""
    dossier = Path(dossier or DOSSIER_TRACES)
    dossier.mkdir(parents=True, exist_ok=True)
    horodatage = horodatage or datetime.now().strftime("%Y-%m-%d_%H%M%S")
    chemin = dossier / f"apercu_{horodatage}.json"
    chemin.write_text(json.dumps({
        "etape": "b5_liens --ajouts-seulement --montrer",
        "horodatage": horodatage,
        "nb_paires": len(apercu),
        "paires": apercu,
    }, indent=1, ensure_ascii=False), encoding="utf-8")
    return chemin


# ---------------------------------------------------------------------------
# Supabase writes
# ---------------------------------------------------------------------------

def write_alternatives(sb, tool_id, tool_slug, alts, dry_run, raisons=None):
    """
    Delete existing rows for tool_id, then insert new alternatives.
    alts: list of (alt_id, alt_slug, similarity)
    raisons: dict optionnel {(tool_id, alt_id): raison}. Si absent ou si une
    paire manque, repli sur une raison de gabarit minimale (jamais de texte
    cosinus).
    """
    raisons = raisons or {}

    if dry_run:
        print(f"  [dry-run] {tool_slug} -> {len(alts)} alternative(s):")
        for alt_id, alt_slug, sim in alts:
            reason = raisons.get((tool_id, alt_id), "")
            print(f"    {alt_slug} sim={sim} reason=\"{reason}\"")
        return len(alts)

    # Delete existing links for this tool
    sb.table("alternatives") \
      .delete() \
      .eq("tool_id", tool_id) \
      .execute()

    if not alts:
        return 0

    rows = []
    for alt_id, alt_slug, sim in alts:
        reason = raisons.get((tool_id, alt_id), "")
        rows.append({
            "tool_id":        tool_id,
            "alternative_id": alt_id,
            "similarity":     sim,
            "reason":         reason,
        })

    sb.table("alternatives").insert(rows).execute()
    return len(rows)


def filtrer_exclues(nouvelles, slugs_exclus):
    """
    Retire des paires a ajouter celles dont l'outil ou l'alternative porte un
    slug exclu (option --exclure : fiches publiees qui ne sont pas des outils).
    nouvelles : liste de (tool_id, slug, alt_id, alt_slug, sim).
    Retourne (paires_gardees, nb_ecartees).
    """
    exclus = {s.strip() for s in (slugs_exclus or []) if s and s.strip()}
    if not exclus:
        return list(nouvelles), 0
    gardees = [n for n in nouvelles if n[1] not in exclus and n[3] not in exclus]
    return gardees, len(nouvelles) - len(gardees)


def ajouter_paires_absentes(sb, lignes, dry_run, dossier_traces=None, horodatage=None):
    """
    Mode --ajouts-seulement : insere les lignes (dicts tool_id, alternative_id,
    similarity, reason). N'appelle jamais delete ni update. Ecrit un fichier
    de trace JSON listant exactement les paires inserees (hors dry-run).
    Retourne (nb_inserees, chemin_trace ou None).
    """
    if dry_run or not lignes:
        return 0, None
    dossier = Path(dossier_traces or DOSSIER_TRACES)
    dossier.mkdir(parents=True, exist_ok=True)
    horodatage = horodatage or datetime.now().strftime("%Y-%m-%d_%H%M%S")
    chemin = dossier / f"ajouts_{horodatage}.json"
    trace = {
        "etape": "b5_liens --ajouts-seulement",
        "horodatage": horodatage,
        "table": "alternatives",
        "paires": [],
    }
    nb = 0
    for i in range(0, len(lignes), 200):
        lot = lignes[i:i + 200]
        sb.table("alternatives").insert(lot).execute()
        nb += len(lot)
        # trace ecrite apres chaque lot reussi : meme si un lot echoue plus
        # loin, ce qui est deja entre en base est consigne
        trace["paires"].extend(
            {"tool_id": r["tool_id"], "alternative_id": r["alternative_id"]} for r in lot
        )
        chemin.write_text(json.dumps(trace, indent=1), encoding="utf-8")
    return nb, chemin


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="Batch B5 liens semantiques")
    parser.add_argument("--dry-run",    action="store_true",
                        help="Calcule et affiche les resultats, n'ecrit rien.")
    parser.add_argument("--top",        type=int,   default=5,
                        help="Nb max d'alternatives par outil (defaut: 5)")
    parser.add_argument("--threshold",  type=float, default=0.55,
                        help="Seuil cosinus minimum (defaut: 0.55)")
    parser.add_argument("--only",       type=str,   default="",
                        help="Limiter a un seul outil (slug)")
    parser.add_argument("--limit",      type=int,   default=0,
                        help="Limiter le nb d'outils traites")
    parser.add_argument("--model",      type=str,   default="nomic-embed-text",
                        help="Modele d'embedding (defaut: nomic-embed-text)")
    parser.add_argument("--workers",    type=int,   default=4,
                        help="Nb de fils paralleles pour la generation des raisons (defaut: 4)")
    parser.add_argument("--sans-llm",   action="store_true",
                        help="Desactive le LLM pour les raisons -- gabarit uniquement.")
    parser.add_argument("--ajouts-seulement", action="store_true",
                        help="N'insere que les paires (outil, alternative) absentes de "
                             "alternatives : aucun delete, aucune mise a jour. Ecrit la "
                             "liste des paires inserees dans exports/b5/.")
    parser.add_argument("--exclure", type=str, default="",
                        help="Avec --ajouts-seulement : slugs separes par des virgules ; "
                             "aucune paire touchant un de ces slugs n'est ajoutee.")
    parser.add_argument("--montrer", action="store_true",
                        help="Avec --ajouts-seulement --dry-run : affiche chaque paire a "
                             "ajouter (noms, categories imprimees, raisons) et ecrit "
                             "exports/b5/apercu_<horodatage>.json. Sans effet en reel.")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    # Validate Supabase creds (only required for real writes)
    if not args.dry_run:
        if not SUPABASE_URL or not SERVICE_KEY:
            sys.exit("SUPABASE_URL et SUPABASE_SERVICE_KEY requis dans prisme/.env")

    np = ensure_numpy()

    if not SUPABASE_URL or not SERVICE_KEY:
        print("[B5] Mode dry-run sans credentials Supabase -- simulation locale uniquement.")
        print("[B5] Resume: 0 outil traite, 0 lien ecrit, 0 ignore.")
        return

    from supabase import create_client
    sb = create_client(SUPABASE_URL, SERVICE_KEY)

    # 1. Load published tools
    print("[B5] Chargement des outils publies...")
    tools = load_tools(sb)
    if not tools:
        print("[B5] Aucun outil publie trouve. Arret.")
        return

    print(f"[B5] {len(tools)} outil(s) publie(s) charge(s).")
    tools_index = {t["id"]: t for t in tools}

    # 2. Load embeddings
    print(f"[B5] Chargement des embeddings (model={args.model})...")
    emb_map = load_embeddings(sb, args.model)
    print(f"[B5] {len(emb_map)} embedding(s) charge(s).")

    # 3. Join tools with embeddings
    tools_with_vec = []
    for t in tools:
        vec = emb_map.get(t["id"])
        if vec:
            tools_with_vec.append((t["id"], t["slug"], t["name"], vec))

    nb_no_emb = len(tools) - len(tools_with_vec)
    if nb_no_emb > 0:
        print(f"[B5] {nb_no_emb} outil(s) sans embedding ignore(s).")

    if len(tools_with_vec) < 2:
        print("[B5] Moins de 2 outils avec embedding -- impossible de calculer des alternatives. Arret.")
        return

    print(f"[B5] {len(tools_with_vec)} outil(s) avec embedding pret(s) pour le calcul.")

    # 4. Apply --only filter
    if args.only:
        found = [t for t in tools_with_vec if t[1] == args.only]
        if not found:
            print(f"[B5] Slug '{args.only}' introuvable ou sans embedding. Arret.")
            sys.exit(1)

    # 5. Compute full similarity matrix (always on full set for correctness)
    print("[B5] Calcul de la matrice de similarite cosinus...")
    alternatives_map = compute_alternatives(np, tools_with_vec, args.top, args.threshold)

    # 6. Determine which tools to process/write
    ids_index = {t[0]: t for t in tools_with_vec}

    if args.only:
        slug_to_id = {t[1]: t[0] for t in tools_with_vec}
        target_id  = slug_to_id[args.only]
        to_process = [ids_index[target_id]]
    else:
        to_process = list(tools_with_vec)

    if args.limit > 0:
        to_process = to_process[:args.limit]

    # 6b. Mode ajouts seulement : on ne garde que les paires absentes
    if args.ajouts_seulement:
        existantes = load_paires_existantes(sb)
        print(f"[B5] --ajouts-seulement : {len(existantes)} paire(s) deja presente(s) (lecture seule).")
        nouvelles = []  # (tool_id, slug, alt_id, alt_slug, sim)
        for tool_id, slug, name, _ in to_process:
            for alt_id, alt_slug, sim in alternatives_map.get(tool_id, []):
                if (tool_id, alt_id) not in existantes:
                    nouvelles.append((tool_id, slug, alt_id, alt_slug, sim))
        nouvelles, nb_exclues = filtrer_exclues(nouvelles, args.exclure.split(","))
        if nb_exclues:
            print(f"[B5] --exclure : {nb_exclues} paire(s) ecartee(s).")
        outils_touches = {n[0] for n in nouvelles}
        print(f"[B5] {len(nouvelles)} paire(s) a ajouter pour {len(outils_touches)} outil(s).")
        paires = [(n[0], n[2]) for n in nouvelles]
        if args.sans_llm:
            fn_gen, model_raison = None, None
        else:
            fn_gen, model_raison = generer_json, modele_pour("arbitre")
        raisons = generer_raisons_paire(fn_gen, tools_index, paires, model_raison,
                                         args.sans_llm, args.workers)
        raisons_fr = generer_raisons_fr_paire(tools_index, paires)
        lignes = [{"tool_id": n[0], "alternative_id": n[2], "similarity": n[4],
                   "reason": raisons.get((n[0], n[2]), ""),
                   "reason_fr": raisons_fr.get((n[0], n[2]), "")} for n in nouvelles]
        if args.dry_run and args.montrer:
            apercu = construire_apercu(nouvelles, tools_index, raisons, raisons_fr)
            for i, ligne in enumerate(apercu, 1):
                print(f"  [apercu {i}/{len(apercu)}] {ligne['outil']} ({ligne['categorie_outil']}) "
                      f"-> {ligne['alternative']} ({ligne['categorie_alternative']}) "
                      f"sim={ligne['similarity']}")
                print(f"      EN : {ligne['reason']}")
                print(f"      FR : {ligne['reason_fr']}")
            sans_cat = sum(1 for l in apercu if "aucune" in (l["categorie_outil"], l["categorie_alternative"]))
            print(f"[B5] Apercu : {len(apercu)} paire(s) a ajouter, dont {sans_cat} "
                  f"avec au moins un outil sans categorie du site.")
            print(f"[B5] Apercu ecrit : {ecrire_apercu(apercu)}")
        elif args.dry_run:
            for n in nouvelles[:5]:
                print(f"  [dry-run] {n[1]} -> {n[3]} sim={n[4]} "
                      f"reason=\"{raisons.get((n[0], n[2]), '')}\"")
        nb, chemin = ajouter_paires_absentes(sb, lignes, args.dry_run)
        mode_label = "[dry-run] " if args.dry_run else ""
        print(f"\n[B5] {mode_label}Resume ajouts : {len(nouvelles)} paire(s), "
              f"{len(outils_touches)} outil(s), {nb} inseree(s)."
              + (f" Trace : {chemin}" if chemin else ""))
        return

    # 7. Generer les raisons (LLM role arbitre en parallele, ou gabarit si --sans-llm)
    paires = []
    for tool_id, slug, name, _ in to_process:
        for alt_id, alt_slug, sim in alternatives_map.get(tool_id, []):
            paires.append((tool_id, alt_id))

    if args.sans_llm:
        print(f"[B5] Generation de {len(paires)} raison(s) par gabarit (--sans-llm)...")
        fn_gen = None
        model_raison = None
    else:
        print(f"[B5] Generation de {len(paires)} raison(s) via LLM role arbitre (workers={args.workers})...")
        fn_gen = generer_json
        model_raison = modele_pour("arbitre")

    raisons = generer_raisons_paire(fn_gen, tools_index, paires, model_raison,
                                     args.sans_llm, args.workers)

    # 8. Write (or dry-run display)
    nb_written = 0
    nb_ignored = 0

    for tool_id, slug, name, _ in to_process:
        alts = alternatives_map.get(tool_id, [])
        if alts:
            print(f"[B5] {slug}: {len(alts)} alternative(s) trouvee(s)")
            nb_written += write_alternatives(sb, tool_id, slug, alts, args.dry_run, raisons=raisons)
        else:
            print(f"[B5] {slug}: aucune alternative (seuil={args.threshold})")
            if not args.dry_run:
                # Clean up any stale links
                sb.table("alternatives").delete().eq("tool_id", tool_id).execute()
            nb_ignored += 1

    mode_label = "[dry-run] " if args.dry_run else ""
    print(
        f"\n[B5] {mode_label}Resume: {len(to_process)} outil(s) traite(s), "
        f"{nb_written} lien(s) ecrit(s), {nb_ignored} ignore(s) (sous seuil)."
    )


if __name__ == "__main__":
    main()
