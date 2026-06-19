# -*- coding: utf-8 -*-
"""
run_nightly.py - Orchestrateur nocturne YggNexus.

Enchaine les batchs dans l'ordre, journalise chaque etape,
arrete la chaine sur echec d'une etape critique.

Usage:
    python run_nightly.py
    python run_nightly.py --dry-run
    python run_nightly.py --from export
    python run_nightly.py --dry-run --from enrichissement
    python run_nightly.py --stop-on-warning
"""

import argparse
import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent
LOGS_DIR = ROOT / "logs"

# Definition de la sequence des etapes
# Chaque etape : (cle_nom, script, critique)
# critique=True  -> echec arrete la chaine
# critique=False -> echec journalise un avertissement, chaine continue
STEPS = [
    ("collecte",       "b1_collecte.py",         True),
    ("enrichissement", "b2_enrichissement.py",    True),
    ("dedup",          "b3_dedup.py",             False),
    ("classification", "b4_classification.py",  False),
    ("export",         "export_tools.py",         True),
    ("publish",        "publish.py",              True),
    ("embeddings",     "publish_embeddings.py",   True),
    ("liens",          "b5_liens.py",             False),
    ("sante",          "b8_sante.py",             False),
]

STEP_KEYS = [s[0] for s in STEPS]

# ---------------------------------------------------------------------------
# Journalisation
# ---------------------------------------------------------------------------

_log_file = None


def _ts():
    """Retourne un timestamp formate."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg, level="INFO"):
    """Ecrit une ligne dans le log et affiche a l'ecran."""
    line = "[{}] [{}] {}".format(_ts(), level, msg)
    print(line, flush=True)
    if _log_file is not None:
        try:
            with open(_log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception as exc:
            print("[{}] [WARN] Impossible d'ecrire dans le log : {}".format(_ts(), exc), flush=True)


def init_log():
    """Cree le dossier logs/ et ouvre le fichier de log du jour."""
    global _log_file
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    _log_file = LOGS_DIR / "nightly_{}.log".format(date_str)


# ---------------------------------------------------------------------------
# Execution d'une etape
# ---------------------------------------------------------------------------

def run_step(step_key, script_name, critical, stop_on_warning=False):
    """
    Lance un sous-processus pour l'etape donnee.
    Retourne True si l'etape reussit, False sinon.
    """
    script_path = ROOT / script_name

    # Arguments supplementaires pour b3_dedup.py : mode rapport uniquement
    extra_args = []
    if step_key == "dedup":
        # Pas d'argument --apply : mode rapport seul
        pass

    cmd = [sys.executable, str(script_path)] + extra_args
    log("DEBUT etape '{}' -> {}".format(step_key, script_name))

    start = datetime.now()
    try:
        result = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except Exception as exc:
        elapsed = (datetime.now() - start).total_seconds()
        log("ECHEC etape '{}' - exception au lancement : {} (duree {:.1f}s)".format(
            step_key, exc, elapsed), level="ERROR")
        return False

    elapsed = (datetime.now() - start).total_seconds()

    # Affichage stdout/stderr du sous-processus
    if result.stdout and result.stdout.strip():
        for line in result.stdout.strip().splitlines():
            log("  [stdout] {}".format(line))
    if result.stderr and result.stderr.strip():
        for line in result.stderr.strip().splitlines():
            log("  [stderr] {}".format(line))

    if result.returncode == 0:
        log("OK etape '{}' (duree {:.1f}s, code={})".format(
            step_key, elapsed, result.returncode))
        return True
    else:
        if critical or stop_on_warning:
            log("ECHEC etape '{}' (duree {:.1f}s, code={})".format(
                step_key, elapsed, result.returncode), level="ERROR")
        else:
            log("AVERT etape '{}' non critique echouee (duree {:.1f}s, code={})".format(
                step_key, elapsed, result.returncode), level="WARN")
        return False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Orchestrateur nocturne YggNexus - enchaine les batchs dans l'ordre."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche le plan des etapes sans rien executer.",
    )
    parser.add_argument(
        "--from",
        dest="from_step",
        metavar="ETAPE",
        choices=STEP_KEYS,
        default=None,
        help="Demarre a partir de cette etape. Choix : {}.".format(", ".join(STEP_KEYS)),
    )
    parser.add_argument(
        "--stop-on-warning",
        action="store_true",
        help="Traite les etapes non critiques comme bloquantes en cas d'echec.",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Point d'entree
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    # Filtre de la sequence selon --from
    steps = list(STEPS)
    if args.from_step:
        start_idx = STEP_KEYS.index(args.from_step)
        steps = steps[start_idx:]

    # --- Mode dry-run ---
    if args.dry_run:
        print("=== DRY-RUN : plan d'execution ===")
        print("Dossier : {}".format(ROOT))
        print("Etapes ({}) :".format(len(steps)))
        for i, (key, script, critical) in enumerate(steps, 1):
            criticity = "critique" if critical else "non critique"
            print("  {}. {:15s} -> {:30s} [{}]".format(i, key, script, criticity))
        if args.stop_on_warning:
            print("Option --stop-on-warning active : toutes les etapes sont bloquantes.")
        print("=== FIN DRY-RUN ===")
        return 0

    # --- Execution reelle ---
    init_log()
    log("=== DEBUT orchestrateur nocturne YggNexus ===")
    if args.from_step:
        log("Demarrage a partir de l'etape '{}'.".format(args.from_step))

    total = len(steps)
    success_count = 0

    for key, script, critical in steps:
        ok = run_step(key, script, critical, stop_on_warning=args.stop_on_warning)
        if ok:
            success_count += 1
        else:
            if critical or args.stop_on_warning:
                log("Arret de la chaine apres echec de l'etape '{}' (critique).".format(key), level="ERROR")
                log("=== FIN orchestrateur : {}/{} etapes reussies. ECHEC. ===".format(
                    success_count, total), level="ERROR")
                return 1
            # Etape non critique qui echoue : on continue
            # success_count reste inchange (etape non comptee en succes)

    log("=== FIN orchestrateur : {}/{} etapes reussies. SUCCES. ===".format(
        success_count, total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
