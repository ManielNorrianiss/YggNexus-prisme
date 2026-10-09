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
"""
import argparse
import os
import sys
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

def load_tools(sb):
    """Return list of published tools: [{id, slug, name, pricing,
    pricing_note, application_category}, ...]."""
    res = sb.table("tools") \
            .select("id,slug,name,pricing,pricing_note,application_category") \
            .eq("status", "published") \
            .execute()
    return res.data if (res is not None and res.data) else []


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


def _category_label(application_category):
    """
    Deduit un libelle de categorie lisible a partir de application_category
    (ex: 'BusinessApplication' -> 'business'). Repli generique si vide.
    """
    if not application_category:
        return "ai/saas"
    # Decoupe CamelCase en mots minuscules ("BusinessApplication" -> "business application")
    import re
    mots = re.findall(r"[A-Z][a-z]*|[a-z]+", application_category)
    if not mots:
        return "ai/saas"
    label = " ".join(mots).lower()
    label = label.replace(" application", "").strip()
    return label or "ai/saas"


def raison_gabarit(tool, alt_tool):
    """
    Construit une raison courte (<=140 caracteres) sans LLM, a partir des
    categories/pricing des deux outils. Ne contient jamais 'cosine' ni
    'similarity' -- passe le filtre frontend /semantic similarity|cosine/i.

    tool, alt_tool : dict avec au moins name, pricing, application_category.
    """
    cat_tool = _category_label(tool.get("application_category"))
    cat_alt = _category_label(alt_tool.get("application_category"))
    prix_tool = _pricing_label(tool.get("pricing"))
    prix_alt = _pricing_label(alt_tool.get("pricing"))

    if cat_tool == cat_alt:
        base = f"Both are {cat_tool} tools"
    else:
        base = f"{alt_tool.get('name', 'This tool')} is a {cat_alt} tool, unlike {tool.get('name', 'the main tool')} ({cat_tool})"

    if prix_tool == prix_alt:
        raison = f"{base}, both {prix_alt}."
    else:
        raison = f"{base}; {alt_tool.get('name', 'it')} is {prix_alt} while {tool.get('name', 'the main tool')} is {prix_tool}."

    return raison[:MAX_LEN_RAISON]


def raison_llm(fn_gen, tool, alt_tool, model, timeout=60):
    """
    Demande au LLM (role arbitre par defaut) une raison courte. Leve
    LLMError si Ollama est injoignable / sortie invalide -- l'appelant
    doit retomber sur raison_gabarit en cas d'echec.
    """
    prompt = (
        f"Main tool: {tool.get('name', '')} "
        f"(category: {_category_label(tool.get('application_category'))}, "
        f"pricing: {_pricing_label(tool.get('pricing'))})\n"
        f"Alternative tool: {alt_tool.get('name', '')} "
        f"(category: {_category_label(alt_tool.get('application_category'))}, "
        f"pricing: {_pricing_label(alt_tool.get('pricing'))})\n\n"
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
    return raison[:MAX_LEN_RAISON]


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
