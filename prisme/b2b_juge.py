# -*- coding: utf-8 -*-
"""
b2b_juge.py - Batch B2b : juge de qualite local, entre l'enrichissement (B2)
et la deduplication (B3).

Relit les fiches enriched_tools pas encore jugees (juge_verdict IS NULL) et
demande a un LLM local (via llm_local.generer_json, meme mecanique que B2)
un verdict severe : ok|reprendre, un score 0-10 discriminant, une liste de
problemes, et optionnellement un nom corrige / un quality_score corrige.

Actions selon le verdict :
    - nom_corrige (non nul)         -> corrige raw_tools.name
    - score_qualite_corrige (non nul) -> remplace enriched_tools.quality_score
    - verdict == "reprendre"        -> supprime la fiche enriched (+ embedding)
      pour que B2 la re-traite au prochain passage (voir staging.delete_enriched).
      GARDE-FOU : une seule reprise par fiche (raw_tools.juge_reprises).
      Si le plafond est deja atteint, le verdict "reprendre" est journalise
      mais N'EST PAS applique (pas de boucle infinie) -- la fiche reste
      enriched telle quelle, juste marquee juge_verdict="reprendre" pour
      tracabilite.

Usage:
    python b2b_juge.py
    python b2b_juge.py --dry-run
    python b2b_juge.py --limit 5
    python b2b_juge.py --only n8n
    python b2b_juge.py --model qwen2.5:14b-instruct
    python b2b_juge.py --workers 4
    python b2b_juge.py --run-id 20260701T120000Z

Routage de modele : par defaut, ce batch utilise le role "arbitre"
(MODELE_ARBITRE, qwen2.5:14b-instruct par defaut -- cf. llm_local.py). Le
drapeau --model garde toujours la priorite s'il est fourni explicitement.

Repli automatique : si le modele arbitre n'est pas tire localement (Ollama
repond "model not found"), chaque appel retombe UNE FOIS sur MODELE_GEN et
journalise un evenement run_log type_evenement=modele_absent_repli (niveau
info). Pour eviter ce repli, tirer le modele au prealable :

    ollama pull qwen2.5:14b-instruct
"""
import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent

import staging
from llm_local import generer_json, MODELE_GEN, MODELE_ARBITRE, LLMError, modele_absent

MAX_REPRISES_PAR_FICHE = 1
VERDICT_ENUM = {"ok", "reprendre"}

SYSTEM_PROMPT_JUGE = (
    "You are a strict, skeptical quality auditor for a SaaS/AI tools directory. "
    "You review one already-written tool listing and judge its quality harshly. "
    "You MUST produce real dispersion in your scores: an average listing should "
    "score around 5-6, not 8-9. Reserve 8+ for genuinely excellent, specific, "
    "non-generic listings. Penalize heavily: generic/boilerplate descriptions "
    "that could apply to any tool, vague or duplicated pros/cons, shallow or "
    "templated FAQ answers, and a tool name that looks like a raw domain slug "
    "(hyphens, glued TLD like '-io'/'-com', all-lowercase-with-dashes) instead "
    "of a proper capitalized product name. "
    "Return ONLY valid JSON with exactly these keys: "
    "verdict, score, problemes, nom_corrige, score_qualite_corrige. "
    "No markdown fences, no extra keys, no comments."
)


def build_prompt_juge(raw, enriched):
    """Construit le prompt du juge a partir de la fiche brute + enrichie."""
    name = raw.get("name", "") if raw else ""
    url = raw.get("website_url", "") if raw else ""
    pros = enriched.get("pros_json") or "[]"
    cons = enriched.get("cons_json") or "[]"
    faq = enriched.get("faq_json") or "[]"
    return (
        f"Tool name: {name}\n"
        f"Website: {url}\n"
        f"Short description: {enriched.get('short_desc', '')}\n"
        f"Description (markdown): {enriched.get('description_md', '')}\n"
        f"Pros (JSON): {pros}\n"
        f"Cons (JSON): {cons}\n"
        f"FAQ (JSON): {faq}\n"
        f"SEO title: {enriched.get('seo_title', '')}\n"
        f"SEO description: {enriched.get('seo_description', '')}\n"
        f"Pricing: {enriched.get('pricing', '')} -- {enriched.get('pricing_note', '')}\n"
        f"Current quality_score: {enriched.get('quality_score', '')}\n\n"
        "Judge this listing. Rules:\n"
        "- verdict: exactly one of 'ok' or 'reprendre' (reprendre = must be "
        "regenerated because it is generic, shallow, or has vague/duplicated "
        "content).\n"
        "- score: number from 0.0 to 10.0, ONE DECIMAL. Be severe and spread "
        "your scores realistically -- do not cluster around 8-9.\n"
        "- problemes: short list of strings, concrete issues found (empty list "
        "if none).\n"
        "- nom_corrige: a properly capitalized product name (string) if the "
        "current name looks like a raw domain slug (hyphens, glued TLD) or is "
        "otherwise wrong; null if the current name is already fine.\n"
        "- score_qualite_corrige: number from 0.0 to 10.0 (one decimal) that "
        "should replace quality_score if it is currently miscalibrated "
        "(e.g. uniformly high); null if quality_score is already reasonable.\n"
    )


def fake_juge(prompt, system, modele=None, timeout=120, _appel=None):
    """Faux juge pour --dry-run (ne touche pas au reseau). Verdict neutre."""
    return {
        "verdict": "ok",
        "score": 6.0,
        "problemes": [],
        "nom_corrige": None,
        "score_qualite_corrige": None,
    }


def check_sortie_juge(d):
    """
    Validation stricte de la sortie du juge. Retourne None si acceptable,
    sinon un message d'erreur (str).
    """
    if not isinstance(d, dict):
        return f"la sortie n'est pas un objet JSON (type recu: {type(d).__name__})"
    manquantes = [k for k in ("verdict", "score", "problemes",
                               "nom_corrige", "score_qualite_corrige") if k not in d]
    if manquantes:
        return f"cles manquantes dans le JSON: {', '.join(manquantes)}"
    verdict = str(d.get("verdict") or "").lower().strip()
    if verdict not in VERDICT_ENUM:
        return f"la cle 'verdict' contient une valeur hors enum: {d.get('verdict')!r}"
    try:
        float(d.get("score"))
    except (TypeError, ValueError):
        return f"la cle 'score' n'est pas un nombre: {d.get('score')!r}"
    return None


def normaliser_sortie_juge(d):
    """Normalise la sortie du juge (types surs, jamais leve)."""
    verdict = str(d.get("verdict") or "ok").lower().strip()
    if verdict not in VERDICT_ENUM:
        verdict = "ok"
    try:
        score = round(max(0.0, min(10.0, float(d.get("score")))), 1)
    except (TypeError, ValueError):
        score = 5.0
    problemes = d.get("problemes") if isinstance(d.get("problemes"), list) else []
    nom_corrige = d.get("nom_corrige")
    if not isinstance(nom_corrige, str) or not nom_corrige.strip():
        nom_corrige = None
    sqc = d.get("score_qualite_corrige")
    if sqc is not None:
        try:
            sqc = round(max(0.0, min(10.0, float(sqc))), 1)
        except (TypeError, ValueError):
            sqc = None
    return {
        "verdict": verdict,
        "score": score,
        "problemes": problemes,
        "nom_corrige": nom_corrige,
        "score_qualite_corrige": sqc,
    }


def generer_avec_repli(fn_gen, prompt, system, modele, run_id=None, log_fn=None, slug=None):
    """
    Appelle fn_gen(prompt, system, modele=modele). Si Ollama signale que le
    modele est absent (modele_absent(e) via llm_local), retente UNE fois
    avec MODELE_GEN et journalise un evenement run_log
    type_evenement="modele_absent_repli" (niveau info).

    Ne retente PAS si modele == MODELE_GEN deja (rien a replier), ni si
    l'erreur n'est pas une absence de modele (timeout, JSON casse, etc. --
    ces cas remontent tels quels).
    """
    try:
        return fn_gen(prompt, system, modele=modele)
    except LLMError as e:
        if modele == MODELE_GEN or not modele_absent(e):
            raise
        if log_fn is not None:
            try:
                log_fn(run_id=run_id, etape="b2b", type_evenement="modele_absent_repli",
                       detail=f"modele arbitre {modele!r} absent ({e}) -- repli sur {MODELE_GEN!r}",
                       slug=slug, niveau="info")
            except Exception:
                pass
        return fn_gen(prompt, system, modele=MODELE_GEN)


def juger_un(slug, raw, enriched, fn_gen, model, run_id=None, log_fn=None):
    """
    Travail effectue par chaque worker : appelle le LLM juge. Ne touche PAS
    a staging (memes raisons que b2_enrichissement.enrich_one) -- retourne
    un dict de resultat que le fil principal se charge d'ecrire.

    Retourne un dict:
        {"slug", "ok": bool, "error": str|None, "verdict": dict|None}
    """
    prompt = build_prompt_juge(raw, enriched)

    def _consigner(type_evenement, detail, niveau="erreur"):
        if log_fn is not None:
            try:
                log_fn(run_id=run_id, etape="b2b", type_evenement=type_evenement,
                       detail=detail, slug=slug, niveau=niveau)
            except Exception:
                pass

    try:
        sortie = generer_avec_repli(fn_gen, prompt, SYSTEM_PROMPT_JUGE, model,
                                     run_id=run_id, log_fn=log_fn, slug=slug)
    except LLMError as e:
        return {"slug": slug, "ok": False, "error": f"ERREUR LLM juge: {e}", "verdict": None}
    except Exception as e:
        return {"slug": slug, "ok": False, "error": f"ERREUR inattendue LLM juge: {e}", "verdict": None}

    message_invalide = check_sortie_juge(sortie)
    if message_invalide is not None:
        _consigner("juge_sortie_invalide", message_invalide)
        return {"slug": slug, "ok": False,
                "error": f"ERREUR sortie juge invalide: {message_invalide}", "verdict": None}

    verdict = normaliser_sortie_juge(sortie)
    return {"slug": slug, "ok": True, "error": None, "verdict": verdict}


def run_juge(a_juger, fn_gen, model, workers, dry_run, run_id=None, log_fn=None, path=None):
    """
    Distribue a_juger (liste de (slug, raw, enriched)) sur un
    ThreadPoolExecutor, puis applique les resultats en staging depuis le
    fil principal (sequentiel). Affiche la progression.

    path : chemin staging optionnel (tests uniquement -- en usage reel la
    DB par defaut controlee par STAGING_DB_PATH est utilisee, meme
    convention que b2_enrichissement.py).

    Retourne un dict resume:
        {"nb_juges", "nb_erreurs", "nb_repris", "nb_noms_corriges",
         "nb_scores_corriges"}
    """
    total = len(a_juger)
    nb_juges = nb_erreurs = nb_repris = nb_noms_corriges = nb_scores_corriges = 0
    done = 0
    t_debut = time.time()

    workers = max(1, workers)

    def _consigner(type_evenement, detail, slug=None, niveau="erreur"):
        if log_fn is not None:
            try:
                log_fn(run_id=run_id, etape="b2b", type_evenement=type_evenement,
                       detail=detail, slug=slug, niveau=niveau)
            except Exception:
                pass

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(juger_un, slug, raw, enriched, fn_gen, model,
                             run_id=run_id, log_fn=log_fn): slug
            for slug, raw, enriched in a_juger
        }
        for future in as_completed(futures):
            slug = futures[future]
            try:
                res = future.result()
            except Exception as e:
                res = {"slug": slug, "ok": False, "error": f"ERREUR inattendue: {e}", "verdict": None}

            done += 1
            elapsed = max(time.time() - t_debut, 1e-9)
            vitesse = done / elapsed

            if not res["ok"]:
                print(f"[B2b] ({done}/{total}, {vitesse:.2f}/s) {res['slug']}: {res['error']}")
                nb_erreurs += 1
                continue

            v = res["verdict"]
            print(f"[B2b] ({done}/{total}, {vitesse:.2f}/s) {slug}: verdict={v['verdict']} score={v['score']}")
            nb_juges += 1

            if dry_run:
                continue

            staging.set_juge_verdict(slug, v["score"], v["verdict"], path=path)

            if v["nom_corrige"]:
                staging.update_enriched_name(slug, v["nom_corrige"], path=path)
                nb_noms_corriges += 1
                _consigner("nom_corrige", f"{v['nom_corrige']!r}", slug=slug, niveau="info")

            if v["score_qualite_corrige"] is not None:
                enriched_row = staging.get_enriched(slug, path=path)
                if enriched_row is not None:
                    enriched_row["quality_score"] = v["score_qualite_corrige"]
                    staging.upsert_enriched(enriched_row, path=path)
                nb_scores_corriges += 1
                _consigner("score_corrige", f"{v['score_qualite_corrige']}", slug=slug, niveau="info")

            if v["verdict"] == "reprendre":
                reprises_actuelles = staging.get_juge_reprises(slug, path=path)
                if reprises_actuelles >= MAX_REPRISES_PAR_FICHE:
                    _consigner("fiche_reprise_refusee",
                               f"plafond de {MAX_REPRISES_PAR_FICHE} reprise(s) deja atteint, "
                               "verdict 'reprendre' ignore pour eviter une boucle",
                               slug=slug)
                else:
                    staging.increment_juge_reprises(slug, path=path)
                    staging.delete_enriched(slug, path=path)
                    nb_repris += 1
                    _consigner("fiche_reprise",
                               f"problemes: {v['problemes']}", slug=slug, niveau="info")

    return {
        "nb_juges": nb_juges,
        "nb_erreurs": nb_erreurs,
        "nb_repris": nb_repris,
        "nb_noms_corriges": nb_noms_corriges,
        "nb_scores_corriges": nb_scores_corriges,
    }


def selectionner_a_juger(path=None):
    """
    Selectionne les (slug, raw, enriched) pas encore juges
    (enriched_tools.juge_verdict IS NULL). raw peut etre None si la ligne
    raw_tools correspondante a disparu (cas limite, on juge quand meme
    avec un raw vide).
    """
    a_juger = []
    for enriched in staging.iter_enriched_a_juger(path=path):
        slug = enriched["slug"]
        raw = staging.get_raw(slug, path=path) or {"slug": slug}
        a_juger.append((slug, raw, enriched))
    return a_juger


def main():
    parser = argparse.ArgumentParser(description="Batch B2b juge de qualite")
    parser.add_argument("--dry-run", action="store_true",
                        help="Utilise un faux juge, n'ecrit rien en staging")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--only", type=str, default="")
    parser.add_argument("--model", type=str, default=MODELE_ARBITRE,
                        help="Modele Ollama (defaut role arbitre: " + MODELE_ARBITRE + ")")
    parser.add_argument("--workers", type=int, default=4,
                        help="Nombre de fils paralleles (defaut: 4)")
    parser.add_argument("--run-id", type=str, default="",
                        help="Identifiant de run partage (defaut: horodatage genere)")
    args = parser.parse_args()

    fn_gen = fake_juge if args.dry_run else generer_json

    staging.init_db()
    staging.init_memoire()
    staging.init_juge()

    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    a_juger = selectionner_a_juger()
    if args.only:
        a_juger = [t for t in a_juger if t[0] == args.only]
        if not a_juger:
            sys.exit(f"Slug introuvable parmi les fiches a juger: {args.only}")
    if args.limit > 0:
        a_juger = a_juger[: args.limit]

    if not args.dry_run:
        staging.log_evenement(run_id, "b2b", "debut",
                               f"{len(a_juger)} fiche(s) a juger, workers={args.workers}",
                               niveau="info")

    if not a_juger:
        print("[B2b] Rien a juger.")
        return

    print(f"[B2b] run_id={run_id} {len(a_juger)} fiche(s) a juger, workers={args.workers}")

    resume = run_juge(a_juger, fn_gen, args.model, args.workers, args.dry_run,
                       run_id=run_id, log_fn=None if args.dry_run else staging.log_evenement)

    if not args.dry_run:
        staging.log_evenement(
            run_id, "b2b", "fin",
            f"{resume['nb_juges']} juge(s), {resume['nb_erreurs']} erreur(s), "
            f"{resume['nb_repris']} repris(es), {resume['nb_noms_corriges']} nom(s) corrige(s), "
            f"{resume['nb_scores_corriges']} score(s) corrige(s)",
            niveau="info",
        )

    print(f"\n[B2b] Resume: {resume['nb_juges']} juge(s), {resume['nb_erreurs']} erreur(s), "
          f"{resume['nb_repris']} repris(es), {resume['nb_noms_corriges']} nom(s) corrige(s), "
          f"{resume['nb_scores_corriges']} score(s) corrige(s).")


if __name__ == "__main__":
    main()
