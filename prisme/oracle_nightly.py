# -*- coding: utf-8 -*-
"""
oracle_nightly.py - Etape nocturne : tient l'Oracle du Livre du Savoir a jour.

Chaine, dans l'ordre, avec un garde-fou d'etancheite NON negociable :

    1. sync_fleau_from_drive.py  -> integre le contenu neuf du Drive Fleau dans
       le Tome markdown, en visibilite metteur_en_scene UNIQUEMENT (sur par defaut).
    1bis. debrief_ingest.py      -> remonte les fiches .html de l'app Debrief
       (Post-Jeu, PNJ, figurants) en livres XXXIV et XXXV, visibles scenariste+.
    2. build_all.py              -> reconstruit oracle_fleau.db (seulement si le
       Tome a change).
    3. test_etancheite.py        -> PORTE DURE : si une seule fuite est detectee,
       on s'arrete et on ne deploie RIEN.
    4. deploiement (optionnel)   -> si ORACLE_DEPLOY_REPO pointe vers un clone
       local du repo LivreDuSavoir, on y copie oracle_fleau.db + le Tome et on
       commit/push (Render redeploie). Sinon : ignore proprement.

Concu pour etre appele soit en step de run_nightly.py, soit a la main :
    python oracle_nightly.py
    python oracle_nightly.py --dry-run
    python oracle_nightly.py --skip-deploy
    python oracle_nightly.py --max 25

Sortie : 0 = succes (ou ignore proprement). 1 = echec dur (dont fuite detectee).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PRISME = Path(__file__).resolve().parent
# Chemin de l'Oracle, derivable par defaut, surchargeable par env.
ORACLE_DIR = Path(
    os.environ.get(
        "ORACLE_DIR",
        str(PRISME.parent.parent / "universes" / "fleau" / "oracle_v2"),
    )
).resolve()
TOME_MD = ORACLE_DIR.parent / "data" / "tome_maitre_v10_consolide.md"
ORACLE_DB = ORACLE_DIR / "oracle_fleau.db"


def log(msg: str) -> None:
    print(f"[oracle_nightly] {msg}", flush=True)


def run(cmd, cwd, env=None) -> int:
    log("$ " + " ".join(str(c) for c in cmd))
    full_env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    if env:
        full_env.update(env)
    res = subprocess.run(
        cmd, cwd=str(cwd), env=full_env, text=True, encoding="utf-8", errors="replace"
    )
    return res.returncode


def do_deploy() -> int:
    """Copie la DB (et le Tome si le repo a un data/) vers le clone LivreDuSavoir,
    puis commit + push. Render redeploie. Ignore proprement si non configure."""
    deploy_repo = os.environ.get("ORACLE_DEPLOY_REPO", "").strip()
    if not deploy_repo:
        log("ORACLE_DEPLOY_REPO non defini : deploiement ignore. "
            "DB a jour localement ; pousser LivreDuSavoir a la main si voulu.")
        return 0
    repo = Path(deploy_repo)
    if not (repo / ".git").exists():
        log(f"ORACLE_DEPLOY_REPO ne pointe pas vers un clone git : {repo}. Ignore.")
        return 0

    import shutil
    shutil.copy2(ORACLE_DB, repo / "oracle_fleau.db")
    # Le Tome n'est copie que si le repo garde une copie de la source (data/).
    if (repo / "data").is_dir() and TOME_MD.exists():
        try:
            shutil.copy2(TOME_MD, repo / "data" / TOME_MD.name)
        except Exception as exc:
            log(f"(copie du Tome ignoree : {exc})")

    if run(["git", "add", "-A"], cwd=repo) != 0:
        log("git add a echoue. Deploiement abandonne.")
        return 1
    msg = "sync nocturne Oracle Fleau (contenu neuf en quarantaine MeS-only)"
    # 'git commit' renvoie non-zero s'il n'y a rien a committer : on tolere.
    rc_commit = run(["git", "commit", "-m", msg], cwd=repo)
    if rc_commit != 0:
        log("Rien de neuf a committer (DB identique). Aucun push.")
        return 0
    if run(["git", "push"], cwd=repo) != 0:
        log("git push a echoue. A pousser a la main.")
        return 1
    log("Deploiement pousse vers LivreDuSavoir. Render redeploie.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Etape nocturne Oracle Fleau")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-deploy", action="store_true")
    ap.add_argument("--max", type=int, default=0)
    ap.add_argument("--deploy-only", action="store_true",
                    help="Pousse la DB actuelle vers LivreDuSavoir, sans sync ni rebuild (test du cablage).")
    args = ap.parse_args()

    if not ORACLE_DIR.exists():
        log(f"ERREUR : dossier Oracle introuvable : {ORACLE_DIR}")
        return 1
    py = sys.executable

    if args.deploy_only:
        if not ORACLE_DB.exists():
            log(f"ERREUR : base introuvable : {ORACLE_DB}")
            return 1
        return do_deploy()

    # --- 1. SYNC ---
    before = TOME_MD.stat().st_mtime if TOME_MD.exists() else 0
    sync_cmd = [py, str(ORACLE_DIR / "sync_fleau_from_drive.py")]
    if args.dry_run:
        sync_cmd.append("--dry-run")
    if args.max:
        sync_cmd += ["--max", str(args.max)]
    if run(sync_cmd, cwd=ORACLE_DIR) != 0:
        log("ECHEC de la synchro Drive. Arret (pas de rebuild).")
        return 1

    # --- 1bis. FICHES DEBRIEF ---
    # Les fiches de l'app Debrief sont des .html : sync_fleau_from_drive.py ne
    # sait pas les lire et les ignore. debrief_ingest.py les parse et regenere
    # les livres XXXIV (registre qui sait quoi) et XXXV (repertoire des fiches).
    # Bloc delimite par sentinelles : rejouable sans duplication.
    debrief_cmd = [py, str(ORACLE_DIR / "debrief_ingest.py")]
    if args.dry_run:
        debrief_cmd.append("--dry-run")
    if run(debrief_cmd, cwd=ORACLE_DIR) != 0:
        log("ECHEC de la remontee des fiches Debrief. Arret (pas de rebuild).")
        return 1

    after = TOME_MD.stat().st_mtime if TOME_MD.exists() else 0

    if args.dry_run:
        log("[dry-run] arret avant rebuild/deploy.")
        return 0
    if after == before:
        log("Tome inchange : rien a reconstruire ni a deployer.")
        return 0

    # --- 2. REBUILD ---
    if run([py, str(ORACLE_DIR / "build_all.py"), str(TOME_MD)], cwd=ORACLE_DIR) != 0:
        log("ECHEC du rebuild (build_all.py). Arret (pas de deploy).")
        return 1

    # --- 3. PORTE DURE : etancheite ---
    rc = run([py, str(ORACLE_DIR / "test_etancheite.py"), str(ORACLE_DB)], cwd=ORACLE_DIR)
    if rc != 0:
        log("FUITE DETECTEE ou test echoue. DEPLOIEMENT ANNULE. Intervention requise.")
        return 1
    log("Etancheite OK : zero fuite.")

    # --- 4. DEPLOIEMENT (optionnel, garde-fou) ---
    if args.skip_deploy:
        log("Deploiement ignore (--skip-deploy). DB reconstruite localement.")
        return 0
    return do_deploy()


if __name__ == "__main__":
    sys.exit(main())
