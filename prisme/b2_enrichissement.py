# -*- coding: utf-8 -*-
"""
b2_enrichissement.py - Batch B2 : enrichissement IA + embeddings.
Lit raw_tools sans enriched_tools (ou hash change), appelle qwen via Ollama,
valide la sortie, calcule l'embedding nomic-embed-text, stocke en staging.

Usage:
    python b2_enrichissement.py
    python b2_enrichissement.py --dry-run
    python b2_enrichissement.py --limit 3
    python b2_enrichissement.py --only n8n
    python b2_enrichissement.py --model qwen2.5:14b-instruct
    python b2_enrichissement.py --workers 8
    python b2_enrichissement.py --timeout 180
    python b2_enrichissement.py --inclure-quarantaine
    python b2_enrichissement.py --run-id 20260701T120000Z
"""
import argparse
import hashlib
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent

import staging
import memoire_prisme
from llm_local import generer_json, embed, MODELE_GEN, MODELE_EMBED, EMBED_DIM, LLMError

PRICING_ENUM = {"free", "freemium", "paid", "open_source", "unknown"}
MAX_EMBED_CHARS = 6000
MAX_ECHECS_AVANT_QUARANTAINE = 3
MAX_SORTIE_FAUTIVE_TRONQUEE = 500  # caracteres inclus dans le prompt de reprise

SYSTEM_PROMPT = (
    "You are a factual technical writer for a SaaS/AI tools directory. "
    "Your task is to produce a JSON object describing a software tool. "
    "Write ONLY in English. Be factual, concise and neutral. "
    "Return ONLY valid JSON with exactly these keys: "
    "short_desc, description_md, pros, cons, faq, seo_title, seo_description, "
    "application_category, pricing, pricing_note, quality_score. "
    "No markdown fences, no extra keys, no comments."
)


def domain_of(url):
    """Extrait le domaine (sans www.) d'une URL. Retourne "" si absent/invalide."""
    try:
        net = urlparse(url or "").netloc.lower().split(":")[0]
    except Exception:
        return ""
    return net[4:] if net.startswith("www.") else net


def nom_ressemble_a_un_slug_domaine(name, url):
    """
    Detecte un nom qui ressemble a un slug de domaine brut (ex: "acmetool-io",
    "my-tool-com") plutot qu'a un vrai nom propre : contient des tirets ET
    (le domaine du site sans tirets/points correspond au nom sans tirets,
    OU le nom se termine par un TLD colle comme -io/-com/-net/-ai/-co).
    """
    n = (name or "").strip().lower()
    if not n:
        return True
    dom = domain_of(url)
    dom_compact = dom.replace(".", "").replace("-", "")
    n_compact = n.replace("-", "").replace(" ", "")
    if dom_compact and n_compact == dom_compact:
        return True
    if "-" in n and re.search(r"-(io|com|net|org|ai|co|app|dev|xyz)$", n):
        return True
    return False


def nom_propre_depuis_domaine(url):
    """
    Derive un nom de presentation propre a partir d'un domaine : retire le
    TLD, remplace les tirets par des espaces, capitalise chaque mot.
    Ex: "acme-tool.io" -> "Acme Tool". Retourne "" si aucun domaine exploitable.
    """
    dom = domain_of(url)
    if not dom:
        return ""
    parts = [p for p in dom.split(".") if p]
    base = parts[-2] if len(parts) >= 2 else (parts[0] if parts else dom)
    mots = [m for m in base.split("-") if m]
    if not mots:
        return ""
    return " ".join(m.capitalize() for m in mots)


def nom_corrige_si_besoin(raw):
    """
    Si raw['name'] manque ou ressemble a un slug/domaine brut, derive un nom
    propre depuis website_url. Retourne (nom_a_utiliser, incertain: bool).
    incertain=True signale que le nom doit etre signale comme non fiable
    dans le prompt (le LLM/juge pourra alors le corriger).
    """
    name = (raw.get("name") or "").strip()
    url = raw.get("website_url", "")
    if not name or nom_ressemble_a_un_slug_domaine(name, url):
        derive = nom_propre_depuis_domaine(url)
        if derive:
            return derive, True
        return name, True
    return name, False


def build_prompt(raw):
    name, nom_incertain = nom_corrige_si_besoin(raw)
    vendor     = raw.get("vendor", "")
    url        = raw.get("website_url", "")
    title      = raw.get("raw_title", "")
    meta       = raw.get("raw_meta_desc", "")
    text_snip  = (raw.get("raw_text") or "")[:1000]
    avertissement_nom = (
        "\nNote: the tool name above was auto-derived from the domain and may be "
        "inaccurate -- infer the real product name from the page title/text if possible.\n"
        if nom_incertain else ""
    )
    return (
        f"Tool name: {name}\n"
        f"Vendor: {vendor}\n"
        f"Website: {url}\n"
        f"Page title: {title}\n"
        f"Meta description: {meta}\n"
        f"Page text snippet: {text_snip}\n"
        f"{avertissement_nom}\n"
        "Produce the JSON object as instructed. Rules:\n"
        "- short_desc: max 160 characters, one sentence.\n"
        "- description_md: 2-3 paragraphs in Markdown.\n"
        "- pros: list of 3 to 5 strings.\n"
        "- cons: list of 2 to 4 strings.\n"
        "- faq: list of exactly 3 objects with keys 'q' and 'a'.\n"
        "- seo_title: max 60 characters.\n"
        "- seo_description: max 155 characters.\n"
        "- application_category: one of SoftwareApplication, WebApplication, "
        "BusinessApplication, DeveloperApplication, MultimediaApplication, UtilitiesApplication.\n"
        "- pricing: exactly one of: free, freemium, paid, open_source, unknown.\n"
        "- pricing_note: short string (max 80 chars).\n"
        "- quality_score: number from 0.0 to 10.0 (one decimal, e.g. 8.5).\n"
    )


def fake_llm(prompt, system, modele=None, timeout=120, _appel=None):
    """Faux LLM pour --dry-run (ne touche pas au reseau)."""
    return {
        "short_desc": "A great tool for automation and productivity.",
        "description_md": (
            "This tool helps teams automate repetitive tasks.\n\n"
            "It integrates with hundreds of services out of the box.\n\n"
            "Suitable for both beginners and advanced users."
        ),
        "pros": ["Easy to use", "Many integrations", "Good documentation"],
        "cons": ["Pricing can be steep", "Limited on free tier"],
        "faq": [
            {"q": "Is there a free plan?", "a": "Yes, a free tier is available."},
            {"q": "Does it support webhooks?", "a": "Yes, webhooks are supported."},
            {"q": "Can I self-host?", "a": "Depends on the edition."},
        ],
        "seo_title": "Best Tool Review",
        "seo_description": "Read our full review of this tool and see if it fits your workflow.",
        "application_category": "BusinessApplication",
        "pricing": "freemium",
        "pricing_note": "Free tier available, paid plans from $10/mo",
        "quality_score": 7.5,
    }


def fake_embed(texte, modele=None, timeout=60, _appel=None):
    """Faux embed pour --dry-run."""
    return [0.0] * EMBED_DIM


def sha256(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def content_hash_for(raw):
    parts = (
        (raw.get("name") or "")
        + (raw.get("raw_title") or "")
        + (raw.get("raw_meta_desc") or "")
        + (raw.get("raw_text") or "")
    )
    return sha256(parts)


def validate_enriched(d):
    """Valide et normalise les champs issus du LLM."""
    result = {}
    result["short_desc"]          = str(d.get("short_desc") or "")[:160]
    result["description_md"]      = str(d.get("description_md") or "")
    result["pros_json"]           = d.get("pros") if isinstance(d.get("pros"), list) else []
    result["cons_json"]           = d.get("cons") if isinstance(d.get("cons"), list) else []
    result["faq_json"]            = d.get("faq")  if isinstance(d.get("faq"),  list) else []
    result["seo_title"]           = str(d.get("seo_title") or "")[:60]
    result["seo_description"]     = str(d.get("seo_description") or "")[:155]
    result["application_category"] = str(d.get("application_category") or "")
    pricing = str(d.get("pricing") or "unknown").lower().strip()
    result["pricing"]             = pricing if pricing in PRICING_ENUM else "unknown"
    result["pricing_note"]        = str(d.get("pricing_note") or "")[:80]
    qs = d.get("quality_score", 5.0)
    try:
        qs = float(qs)
    except (TypeError, ValueError):
        qs = 5.0
    if qs > 10:                      # echelle 0-100 heritee -> ramener sur 10
        qs = qs / 10.0
    result["quality_score"] = round(max(0.0, min(10.0, qs)), 1)
    return result


REQUIRED_KEYS = (
    "short_desc", "description_md", "pros", "cons", "faq",
    "seo_title", "seo_description", "application_category",
    "pricing", "pricing_note", "quality_score",
)


def check_sortie_llm(d):
    """
    Validation STRICTE de la sortie LLM (distincte de validate_enriched qui,
    elle, normalise avec des defauts surs et ne leve jamais). Sert a decider
    si une auto-correction (re-prompt) doit etre declenchee.

    Retourne None si la sortie est acceptable, ou un message d'erreur
    precis (str) sinon.
    """
    if not isinstance(d, dict):
        return f"la sortie n'est pas un objet JSON (type recu: {type(d).__name__})"
    manquantes = [k for k in REQUIRED_KEYS if k not in d]
    if manquantes:
        return f"cles manquantes dans le JSON: {', '.join(manquantes)}"
    if not isinstance(d.get("pros"), list) or not d.get("pros"):
        return "la cle 'pros' doit etre une liste non vide"
    if not isinstance(d.get("cons"), list) or not d.get("cons"):
        return "la cle 'cons' doit etre une liste non vide"
    if not isinstance(d.get("faq"), list) or len(d.get("faq")) == 0:
        return "la cle 'faq' doit etre une liste non vide"
    if not str(d.get("short_desc") or "").strip():
        return "la cle 'short_desc' est vide"
    if not str(d.get("description_md") or "").strip():
        return "la cle 'description_md' est vide"
    pricing = str(d.get("pricing") or "").lower().strip()
    if pricing not in PRICING_ENUM:
        return f"la cle 'pricing' contient une valeur hors enum: {d.get('pricing')!r}"
    return None


def build_prompt_correction(prompt_original, sortie_fautive, message_erreur):
    """
    Construit un prompt de reprise : rappelle le prompt original, montre la
    sortie fautive (tronquee) et le message d'erreur precis, puis demande
    une correction stricte.
    """
    sortie_tronquee = str(sortie_fautive)[:MAX_SORTIE_FAUTIVE_TRONQUEE]
    return (
        prompt_original
        + "\n\n---\n"
        + "Ta reponse precedente etait invalide pour cette raison : "
        + message_erreur
        + ".\n"
        + f"Sortie fautive (tronquee) : {sortie_tronquee}\n"
        + "Corrige et renvoie uniquement le JSON, sans commentaire ni texte additionnel."
    )


def enrich_one(raw, chash, fn_gen, fn_embed, model, run_id=None, log_fn=None):
    """
    Travail effectue par chaque worker : appelle le LLM puis l'embedding.
    Ne touche PAS a staging (sqlite n'aime pas les ecritures concurrentes) --
    retourne un dict de resultat que le fil principal se charge d'ecrire.

    Auto-correction : si la sortie LLM est invalide (JSON casse ou echec de
    check_sortie_llm), on journalise 'json_invalide' et on refait UN seul
    appel avec un prompt de reprise incluant le message d'erreur precis et
    la sortie fautive tronquee. Si la reprise reussit, on journalise
    'reprise_reussie'. Si elle echoue aussi, l'echec final est retourne
    normalement (le fil principal gere alors la quarantaine).

    Retourne un dict:
        {"slug", "ok": bool, "error": str|None, "validated": dict|None,
         "vec": list|None, "chash": str}
    """
    slug = raw["slug"]
    prompt = build_prompt(raw)

    def _consigner(type_evenement, detail, niveau="erreur"):
        if log_fn is not None:
            try:
                log_fn(run_id=run_id, etape="b2", type_evenement=type_evenement,
                       detail=detail, slug=slug, niveau=niveau)
            except Exception:
                pass  # la journalisation ne doit jamais faire echouer B2

    llm_out = None
    erreur_appel = None
    try:
        llm_out = fn_gen(prompt, SYSTEM_PROMPT, modele=model)
    except LLMError as e:
        erreur_appel = f"ERREUR LLM: {e}"
    except Exception as e:
        erreur_appel = f"ERREUR inattendue LLM: {e}"

    if erreur_appel is not None:
        message_invalide = erreur_appel
    else:
        message_invalide = check_sortie_llm(llm_out)

    if message_invalide is not None:
        _consigner("json_invalide", message_invalide)
        prompt_correction = build_prompt_correction(
            prompt, llm_out if llm_out is not None else erreur_appel, message_invalide
        )
        try:
            llm_out_retry = fn_gen(prompt_correction, SYSTEM_PROMPT, modele=model)
            message_invalide_retry = check_sortie_llm(llm_out_retry)
        except LLMError as e:
            llm_out_retry = None
            message_invalide_retry = f"ERREUR LLM en reprise: {e}"
        except Exception as e:
            llm_out_retry = None
            message_invalide_retry = f"ERREUR inattendue LLM en reprise: {e}"

        if message_invalide_retry is None:
            _consigner("reprise_reussie", "correction acceptee au second essai", niveau="info")
            llm_out = llm_out_retry
        else:
            _consigner("json_invalide", f"echec final apres reprise: {message_invalide_retry}")
            return {"slug": slug, "ok": False,
                    "error": f"ERREUR sortie LLM invalide (apres reprise): {message_invalide_retry}",
                    "validated": None, "vec": None, "chash": chash}

    validated = validate_enriched(llm_out)
    validated["slug"]         = slug
    validated["content_hash"] = chash
    validated["enriched_at"]  = datetime.now(timezone.utc).isoformat()

    embed_text = (
        (raw.get("name") or "")
        + ". "
        + validated["short_desc"]
        + ". "
        + validated["description_md"]
    )[:MAX_EMBED_CHARS]

    try:
        vec = fn_embed(embed_text, modele=MODELE_EMBED)
    except LLMError as e:
        return {"slug": slug, "ok": False, "error": f"ERREUR embed: {e}",
                "validated": None, "vec": None, "chash": chash}
    except Exception as e:
        return {"slug": slug, "ok": False, "error": f"ERREUR inattendue embed: {e}",
                "validated": None, "vec": None, "chash": chash}

    return {"slug": slug, "ok": True, "error": None,
            "validated": validated, "vec": vec, "chash": chash}


def run_enrichment(to_enrich, fn_gen, fn_embed, model, workers, dry_run,
                    run_id=None, log_fn=None):
    """
    Distribue to_enrich sur un ThreadPoolExecutor (workers threads),
    puis ecrit les resultats en staging depuis le fil principal (sequentiel).
    Affiche la progression (n/total, vitesse).

    Sur echec final d'un slug (apres l'auto-correction tentee dans
    enrich_one) : incremente staging.increment_echecs(slug) ; a partir de
    MAX_ECHECS_AVANT_QUARANTAINE, met le slug en quarantaine et journalise
    l'evenement 'quarantaine'. En --dry-run, aucune ecriture staging n'est
    faite (ni echecs, ni quarantaine).

    Retourne (nb_ok, nb_error).
    """
    total = len(to_enrich)
    nb_ok = 0
    nb_error = 0
    done = 0
    t_debut = time.time()

    workers = max(1, workers)

    def _consigner(type_evenement, detail, slug=None, niveau="erreur"):
        if log_fn is not None:
            try:
                log_fn(run_id=run_id, etape="b2", type_evenement=type_evenement,
                       detail=detail, slug=slug, niveau=niveau)
            except Exception:
                pass

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(enrich_one, raw, chash, fn_gen, fn_embed, model,
                             run_id=run_id, log_fn=log_fn): raw["slug"]
            for raw, chash in to_enrich
        }
        for future in as_completed(futures):
            slug = futures[future]
            try:
                res = future.result()
            except Exception as e:
                res = {"slug": slug, "ok": False, "error": f"ERREUR inattendue: {e}",
                       "validated": None, "vec": None, "chash": None}

            done += 1
            elapsed = max(time.time() - t_debut, 1e-9)
            vitesse = done / elapsed

            if res["ok"]:
                validated = res["validated"]
                vec = res["vec"]
                if not dry_run:
                    staging.upsert_enriched(validated)
                    staging.upsert_embedding({
                        "slug":           res["slug"],
                        "model":          MODELE_EMBED,
                        "dim":            len(vec),
                        "embedding_json": vec,
                        "content_hash":   res["chash"],
                        "created_at":     datetime.now(timezone.utc).isoformat(),
                    })
                    print(f"[B2] ({done}/{total}, {vitesse:.2f}/s) ok: {res['slug']} "
                          f"short_desc={validated['short_desc'][:60]!r}")
                else:
                    print(f"[B2] ({done}/{total}, {vitesse:.2f}/s) [dry-run] {res['slug']} "
                          f"LLM ok, embed dim={len(vec)}, rien ecrit.")
                nb_ok += 1
            else:
                print(f"[B2] ({done}/{total}, {vitesse:.2f}/s) {res['slug']}: {res['error']}")
                nb_error += 1
                if not dry_run:
                    nb_echecs = staging.increment_echecs(res["slug"])
                    if nb_echecs >= MAX_ECHECS_AVANT_QUARANTAINE:
                        staging.mettre_en_quarantaine(res["slug"])
                        _consigner("quarantaine",
                                   f"mis en quarantaine apres {nb_echecs} echec(s): {res['error']}",
                                   slug=res["slug"])

    return nb_ok, nb_error


def main():
    parser = argparse.ArgumentParser(description="Batch B2 enrichissement")
    parser.add_argument("--dry-run", action="store_true",
                        help="Utilise un faux LLM, n'ecrit pas en staging")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--only",  type=str, default="")
    parser.add_argument("--model", type=str, default=MODELE_GEN,
                        help="Modele Ollama (defaut: " + MODELE_GEN + ")")
    parser.add_argument("--force", action="store_true",
                        help="Re-enrichir meme si le content_hash est inchange")
    parser.add_argument("--workers", type=int, default=None,
                        help="Nombre de fils paralleles pour l'enrichissement "
                             "(defaut: valeur apprise dans data/parametres_appris.json, sinon 4)")
    parser.add_argument("--timeout", type=int, default=None,
                        help="Timeout HTTP Ollama en secondes "
                             "(defaut: valeur apprise, sinon 120)")
    parser.add_argument("--inclure-quarantaine", action="store_true",
                        help="Inclut les slugs en quarantaine dans la selection a enrichir")
    parser.add_argument("--run-id", type=str, default="",
                        help="Identifiant de run partage (defaut: horodatage genere)")
    args = parser.parse_args()

    fn_gen   = fake_llm   if args.dry_run else generer_json
    fn_embed = fake_embed if args.dry_run else embed

    staging.init_db()
    staging.init_memoire()

    params_appris = memoire_prisme.charger_parametres()
    workers = args.workers if args.workers is not None else int(params_appris.get("b2_workers", 4))
    timeout = args.timeout if args.timeout is not None else int(params_appris.get("b2_timeout", 120))

    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    raws = list(staging.iter_raw())
    if args.only:
        raws = [r for r in raws if r["slug"] == args.only]
        if not raws:
            sys.exit(f"Slug introuvable dans raw_tools: {args.only}")
    elif not args.inclure_quarantaine:
        raws = [r for r in raws if r.get("status") != "quarantaine"]

    to_enrich = []
    for r in raws:
        chash = content_hash_for(r)
        existing = staging.get_enriched(r["slug"])
        if not args.force and existing and existing.get("content_hash") == chash:
            continue
        to_enrich.append((r, chash))

    if args.limit > 0:
        to_enrich = to_enrich[: args.limit]

    if not args.dry_run:
        staging.log_evenement(run_id, "b2", "debut",
                               f"{len(to_enrich)} outil(s) a enrichir, workers={workers}, timeout={timeout}",
                               niveau="info")

    if not to_enrich:
        print("[B2] Rien a enrichir.")
        return

    print(f"[B2] run_id={run_id} {len(to_enrich)} outil(s) a enrichir, workers={workers}, timeout={timeout}s")

    def fn_gen_avec_timeout(prompt, system, modele=None, **kw):
        kw.setdefault("timeout", timeout)
        return fn_gen(prompt, system, modele=modele, **kw)

    log_fn = None if args.dry_run else staging.log_evenement

    nb_ok, nb_error = run_enrichment(
        to_enrich, fn_gen_avec_timeout, fn_embed, args.model, workers, args.dry_run,
        run_id=run_id, log_fn=log_fn,
    )

    if not args.dry_run:
        staging.log_evenement(run_id, "b2", "fin",
                               f"{nb_ok} enrichi(s), {nb_error} erreur(s)",
                               niveau="info")

    print(f"\n[B2] Resume: {nb_ok} enrichi(s), {nb_error} erreur(s).")


if __name__ == "__main__":
    main()
