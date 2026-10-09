# -*- coding: utf-8 -*-
"""
memoire_prisme.py - Memoire d'erreurs et auto-ajustement du Prisme.

Gere les parametres appris (data/parametres_appris.json), analyse un run
(via staging.run_log / stats_run) pour en tirer des ajustements PRUDENTS
des parametres (workers, timeout, taille de vague), et ecrit un journal
lisible par un humain (logs/lecons.md).

Regles d'ajustement (toutes prudentes, jamais plus de +/-25% par nuit) :
    - trop de timeouts b2                 -> reduire b2_workers OU augmenter b2_timeout
    - taux d'erreur quasi nul + vitesse OK -> augmenter b2_workers d'un cran (plafond 8)
    - trop de pages mortes b1              -> reduire b1_workers (plancher 2)
    - modele arbitre absent (b2b, repli)   -> jamais d'auto-ajustement de parametre,
      juste une lecon rappelant de tirer le modele 14b (voir MODELE_ARBITRE
      dans llm_local.py)

Usage (bibliotheque, pas de CLI ici -- voir apprendre_nightly.py) :
    from memoire_prisme import charger_parametres, sauver_parametres, analyser_run, ecrire_lecons
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import staging

ROOT = Path(__file__).resolve().parent
PARAMETRES_PATH = ROOT / "data" / "parametres_appris.json"
LECONS_PATH = ROOT / "logs" / "lecons.md"

# Bornes de securite
AJUSTEMENT_MAX = 0.25  # jamais plus de +/-25% par nuit
B2_WORKERS_PLAFOND = 8
B2_WORKERS_PLANCHER = 1
B1_WORKERS_PLANCHER = 2
B1_WORKERS_PLAFOND = 16
B2_TIMEOUT_PLANCHER = 30
B2_TIMEOUT_PLAFOND = 600

DEFAUTS = {
    "b2_workers":   4,
    "b2_timeout":   120,
    "b1_workers":   8,
    "taille_vague": 0,
    "derniere_maj": None,
    "historique":   [],
}

# Seuils de decision (proportions d'evenements sur le total de l'etape)
SEUIL_TIMEOUT_HAUT = 0.15   # >15% de timeouts b2 -> on ajuste
SEUIL_ERREUR_BAS = 0.02     # <=2% d'erreurs -> on considere le run "propre"
SEUIL_PAGE_MORTE_HAUT = 0.15  # >15% de pages mortes b1 -> on ajuste
SEUIL_REPRISES_JUGE_HAUT = 0.30  # >30% de verdicts "reprendre" b2b -> lecon (pas d'auto-ajustement)
MODELE_B2_RECOMMANDE_SI_REPRISES_HAUT = "qwen2.5:14b-instruct"


def _copie_defauts():
    """Copie profonde suffisante de DEFAUTS (evite le partage de la liste
    'historique' entre appels -- bug de reference partagee sinon)."""
    out = dict(DEFAUTS)
    out["historique"] = list(DEFAUTS.get("historique") or [])
    return out


def charger_parametres():
    """
    Charge data/parametres_appris.json. Retourne les valeurs par defaut
    (copie independante, jamais de reference partagee) si le fichier est
    absent ou illisible.
    """
    if not PARAMETRES_PATH.exists():
        return _copie_defauts()
    try:
        data = json.loads(PARAMETRES_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _copie_defauts()
    out = _copie_defauts()
    out.update(data)
    if not isinstance(out.get("historique"), list):
        out["historique"] = []
    return out


def sauver_parametres(params):
    """Ecrit params dans data/parametres_appris.json (cree le dossier au besoin)."""
    PARAMETRES_PATH.parent.mkdir(parents=True, exist_ok=True)
    params = dict(params)
    params["derniere_maj"] = datetime.now(timezone.utc).isoformat()
    PARAMETRES_PATH.write_text(
        json.dumps(params, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return params


def _clamp_ajustement(valeur_actuelle, valeur_visee, plancher, plafond):
    """
    Limite l'ecart entre valeur_actuelle et valeur_visee a +/-AJUSTEMENT_MAX
    (proportion de valeur_actuelle), puis clamp entre plancher et plafond.
    Retourne un entier.
    """
    if valeur_actuelle <= 0:
        base = 1
    else:
        base = valeur_actuelle
    ecart_max = max(1, round(base * AJUSTEMENT_MAX))
    borne_basse = valeur_actuelle - ecart_max
    borne_haute = valeur_actuelle + ecart_max
    visee = max(borne_basse, min(borne_haute, valeur_visee))
    visee = max(plancher, min(plafond, visee))
    return int(round(visee))


def analyser_run(run_id, path=None):
    """
    Lit run_log pour run_id, calcule les taux d'erreur par etape/type et
    applique les regles d'ajustement prudentes. Met a jour et sauvegarde
    les parametres appris. Retourne un dict:
        {
          "run_id": str,
          "stats": dict (sortie de staging.stats_run),
          "ajustements": [{"parametre", "avant", "apres", "raison"}, ...],
          "parametres": dict (nouveaux parametres, deja sauvegardes),
        }
    """
    stats = staging.stats_run(run_id, path=path)
    params = charger_parametres()
    ajustements = []

    par_etape = stats.get("par_etape", {})
    par_type = stats.get("par_type", {})
    total = max(1, stats.get("total", 0))

    # --- b2 : timeouts ---
    b2_total = par_etape.get("b2", {}).get("total", 0)
    b2_timeouts = par_type.get("timeout", 0)
    if b2_total > 0:
        taux_timeout = b2_timeouts / b2_total
        if taux_timeout > SEUIL_TIMEOUT_HAUT:
            avant_workers = int(params.get("b2_workers", DEFAUTS["b2_workers"]))
            avant_timeout = int(params.get("b2_timeout", DEFAUTS["b2_timeout"]))
            # Priorite : reduire les workers (moins de charge concurrente sur Ollama).
            if avant_workers > B2_WORKERS_PLANCHER:
                apres = _clamp_ajustement(
                    avant_workers, avant_workers - 1,
                    B2_WORKERS_PLANCHER, B2_WORKERS_PLAFOND,
                )
                params["b2_workers"] = apres
                ajustements.append({
                    "parametre": "b2_workers",
                    "avant": avant_workers,
                    "apres": apres,
                    "raison": f"taux de timeouts b2 eleve ({taux_timeout:.0%}) -> reduction des workers",
                })
            else:
                apres = _clamp_ajustement(
                    avant_timeout, int(avant_timeout * 1.25),
                    B2_TIMEOUT_PLANCHER, B2_TIMEOUT_PLAFOND,
                )
                params["b2_timeout"] = apres
                ajustements.append({
                    "parametre": "b2_timeout",
                    "avant": avant_timeout,
                    "apres": apres,
                    "raison": f"taux de timeouts b2 eleve ({taux_timeout:.0%}), workers deja au plancher -> augmentation du timeout",
                })
        else:
            taux_erreur_b2 = par_etape.get("b2", {}).get("erreurs", 0) / b2_total
            if taux_erreur_b2 <= SEUIL_ERREUR_BAS:
                avant_workers = int(params.get("b2_workers", DEFAUTS["b2_workers"]))
                if avant_workers < B2_WORKERS_PLAFOND:
                    apres = _clamp_ajustement(
                        avant_workers, avant_workers + 1,
                        B2_WORKERS_PLANCHER, B2_WORKERS_PLAFOND,
                    )
                    params["b2_workers"] = apres
                    ajustements.append({
                        "parametre": "b2_workers",
                        "avant": avant_workers,
                        "apres": apres,
                        "raison": f"taux d'erreur b2 quasi nul ({taux_erreur_b2:.0%}) -> augmentation d'un cran",
                    })

    # --- b1 : pages mortes ---
    b1_total = par_etape.get("b1", {}).get("total", 0)
    b1_pages_mortes = par_type.get("page_morte", 0)
    if b1_total > 0:
        taux_page_morte = b1_pages_mortes / b1_total
        if taux_page_morte > SEUIL_PAGE_MORTE_HAUT:
            avant_workers = int(params.get("b1_workers", DEFAUTS["b1_workers"]))
            if avant_workers > B1_WORKERS_PLANCHER:
                apres = _clamp_ajustement(
                    avant_workers, avant_workers - 1,
                    B1_WORKERS_PLANCHER, B1_WORKERS_PLAFOND,
                )
                params["b1_workers"] = apres
                ajustements.append({
                    "parametre": "b1_workers",
                    "avant": avant_workers,
                    "apres": apres,
                    "raison": f"taux de pages mortes b1 eleve ({taux_page_morte:.0%}) -> reduction des workers",
                })

    # --- b2b : verdicts "reprendre" du juge de qualite ---
    # Ne change JAMAIS le modele automatiquement : note seulement une
    # recommandation journalisee dans lecons.md (voir ecrire_lecons), a
    # appliquer manuellement (--model sur b2_enrichissement.py) si jugee
    # pertinente par le createur.
    b2b_total = par_etape.get("b2b", {}).get("total", 0)
    b2b_reprises = par_type.get("fiche_reprise", 0)
    if b2b_total > 0:
        taux_reprises = b2b_reprises / b2b_total
        if taux_reprises > SEUIL_REPRISES_JUGE_HAUT:
            ajustements.append({
                "parametre": "b2_model (recommandation, non applique)",
                "avant": "modele courant",
                "apres": MODELE_B2_RECOMMANDE_SI_REPRISES_HAUT,
                "raison": f"part de verdicts 'reprendre' du juge b2b elevee ({taux_reprises:.0%} > "
                          f"{SEUIL_REPRISES_JUGE_HAUT:.0%}) -> recommandation de passer b2 a "
                          f"{MODELE_B2_RECOMMANDE_SI_REPRISES_HAUT} (a appliquer manuellement)",
            })

    # --- b2b : modele arbitre absent (repli automatique vers MODELE_GEN) ---
    # Jamais d'auto-ajustement de parametre ici non plus : juste une lecon
    # qui rappelle de tirer le modele 14b localement (ollama pull). Le
    # repli lui-meme est deja gere par b2b_juge.generer_avec_repli -- cette
    # regle sert uniquement a rendre le probleme visible dans lecons.md.
    nb_modele_absent = par_type.get("modele_absent_repli", 0)
    if nb_modele_absent > 0:
        ajustements.append({
            "parametre": "modele_arbitre (lecon, non applique)",
            "avant": "absent localement",
            "apres": "a tirer : ollama pull qwen2.5:14b-instruct",
            "raison": f"{nb_modele_absent} repli(s) vers MODELE_GEN detecte(s) car le modele arbitre "
                      "n'est pas disponible sur cette machine Ollama -- tirer le modele pour "
                      "retrouver le jugement de qualite complet.",
        })

    # Journalisation dans l'historique (toujours, meme si aucun ajustement).
    entree_historique = {
        "run_id": run_id,
        "date": datetime.now(timezone.utc).isoformat(),
        "ajustements": ajustements,
        "total_evenements": stats.get("total", 0),
    }
    historique = params.get("historique", [])
    if not isinstance(historique, list):
        historique = []
    historique.append(entree_historique)
    params["historique"] = historique[-100:]  # borne la taille de l'historique

    params = sauver_parametres(params)

    return {
        "run_id": run_id,
        "stats": stats,
        "ajustements": ajustements,
        "parametres": params,
    }


def ecrire_lecons(run_id, path=None, resultat_analyse=None):
    """
    Ajoute une section datee dans logs/lecons.md avec un resume du run :
    erreurs dominantes, ajustements faits et pourquoi, slugs mis en
    quarantaine. Cree le fichier s'il n'existe pas.

    Si resultat_analyse est fourni (sortie de analyser_run), on l'utilise
    tel quel ; sinon on appelle analyser_run(run_id) nous-memes.
    """
    if resultat_analyse is None:
        resultat_analyse = analyser_run(run_id, path=path)

    stats = resultat_analyse["stats"]
    ajustements = resultat_analyse["ajustements"]

    LECONS_PATH.parent.mkdir(parents=True, exist_ok=True)

    lignes = []
    lignes.append(f"## Run {run_id} -- {datetime.now(timezone.utc).isoformat()}")
    lignes.append("")
    lignes.append(f"- Evenements totaux journalises : {stats.get('total', 0)}")

    par_etape = stats.get("par_etape", {})
    if par_etape:
        lignes.append("- Par etape :")
        for etape, d in sorted(par_etape.items()):
            lignes.append(f"  - {etape} : {d['total']} evenement(s), {d['erreurs']} erreur(s)")

    par_type = stats.get("par_type", {})
    if par_type:
        types_domines = sorted(par_type.items(), key=lambda kv: -kv[1])[:5]
        lignes.append("- Types d'evenements dominants :")
        for t, n in types_domines:
            lignes.append(f"  - {t or '(non precise)'} : {n}")

    if ajustements:
        lignes.append("- Ajustements appliques :")
        for a in ajustements:
            lignes.append(
                f"  - {a['parametre']} : {a['avant']} -> {a['apres']} ({a['raison']})"
            )
    else:
        lignes.append("- Aucun ajustement de parametre applique ce run.")

    slugs_quarantaine = stats.get("slugs_quarantaine", [])
    if slugs_quarantaine:
        lignes.append(f"- Slugs mis en quarantaine ({len(slugs_quarantaine)}) : " +
                       ", ".join(slugs_quarantaine))
    else:
        lignes.append("- Aucun slug mis en quarantaine ce run.")

    lignes.append("")

    entete = ""
    if not LECONS_PATH.exists():
        entete = "# Lecons du Prisme\n\nJournal lisible des runs, erreurs dominantes et ajustements automatiques.\n\n"

    with open(LECONS_PATH, "a", encoding="utf-8") as f:
        if entete:
            f.write(entete)
        f.write("\n".join(lignes) + "\n")

    return str(LECONS_PATH)
