# -*- coding: utf-8 -*-
"""
apprendre_nightly.py - CLI d'apprentissage nocturne du Prisme.

Appelle memoire_prisme.analyser_run() puis memoire_prisme.ecrire_lecons()
pour le run le plus recent (ou un run_id donne), et affiche un resume.
Concu pour etre une etape NON critique en fin de run_nightly.py : un echec
ici ne doit jamais faire echouer la chaine nocturne.

Usage:
    python apprendre_nightly.py
    python apprendre_nightly.py --run-id 20260701T120000Z
    python apprendre_nightly.py --dry-run
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

import staging
import memoire_prisme


def dernier_run_id(path=None):
    """
    Retourne le run_id le plus recent present dans run_log (par created_at
    decroissant), ou None si run_log est vide/absent.
    """
    staging.init_run_log(path)
    db = staging.connect(path)
    row = db.execute(
        "SELECT run_id FROM run_log ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    return row["run_id"] if row else None


def main():
    parser = argparse.ArgumentParser(
        description="Analyse un run du Prisme et met a jour la memoire d'erreurs / parametres appris."
    )
    parser.add_argument("--run-id", type=str, default="",
                        help="Run a analyser (defaut: le plus recent dans run_log)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Calcule et affiche le resume sans ecrire parametres_appris.json ni logs/lecons.md")
    args = parser.parse_args()

    run_id = args.run_id or dernier_run_id()
    if not run_id:
        print("[APPRENDRE] Aucun run_id trouve dans run_log -- rien a analyser.")
        return 0

    if args.dry_run:
        stats = staging.stats_run(run_id)
        print(f"[APPRENDRE] (dry-run) run_id={run_id}")
        print(f"[APPRENDRE] Evenements totaux : {stats['total']}")
        for etape, d in sorted(stats["par_etape"].items()):
            print(f"[APPRENDRE]   etape={etape}: total={d['total']} erreurs={d['erreurs']}")
        for t, n in sorted(stats["par_type"].items(), key=lambda kv: -kv[1])[:10]:
            print(f"[APPRENDRE]   type={t or '(non precise)'}: {n}")
        if stats["slugs_quarantaine"]:
            print(f"[APPRENDRE]   slugs en quarantaine: {', '.join(stats['slugs_quarantaine'])}")
        print("[APPRENDRE] (dry-run) aucun fichier ecrit.")
        return 0

    resultat = memoire_prisme.analyser_run(run_id)
    chemin_lecons = memoire_prisme.ecrire_lecons(run_id, resultat_analyse=resultat)

    print(f"[APPRENDRE] run_id={run_id}")
    print(f"[APPRENDRE] Evenements totaux : {resultat['stats']['total']}")
    if resultat["ajustements"]:
        print("[APPRENDRE] Ajustements appliques :")
        for a in resultat["ajustements"]:
            print(f"[APPRENDRE]   {a['parametre']}: {a['avant']} -> {a['apres']} ({a['raison']})")
    else:
        print("[APPRENDRE] Aucun ajustement de parametre applique.")
    slugs_q = resultat["stats"].get("slugs_quarantaine", [])
    if slugs_q:
        print(f"[APPRENDRE] Slugs en quarantaine ce run : {', '.join(slugs_q)}")
    print(f"[APPRENDRE] Lecons ecrites dans : {chemin_lecons}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
