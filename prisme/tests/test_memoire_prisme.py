# -*- coding: utf-8 -*-
"""
Tests purs des regles d'ajustement de memoire_prisme.py : bornes +/-25% par
nuit, plafonds/planchers (b2_workers <= 8, b1_workers >= 2), et
charger_parametres/sauver_parametres. Utilise des chemins temporaires
(jamais data/parametres_appris.json ni logs/lecons.md du depot) via
monkeypatch des constantes de module.
"""
import json
import os
import tempfile
from pathlib import Path

import memoire_prisme as mp
import staging


def _tmp_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)
    return path


def _cleanup_db(path):
    for ext in ("", "-wal", "-shm", "-journal"):
        p = path + ext
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass


def _patch_fichiers(monkeypatch, tmp_dir):
    params_path = Path(tmp_dir) / "parametres_appris.json"
    lecons_path = Path(tmp_dir) / "lecons.md"
    monkeypatch.setattr(mp, "PARAMETRES_PATH", params_path)
    monkeypatch.setattr(mp, "LECONS_PATH", lecons_path)
    return params_path, lecons_path


# ---------------------------------------------------------------------------
# charger_parametres / sauver_parametres
# ---------------------------------------------------------------------------

def test_charger_parametres_defaut_si_absent(monkeypatch, tmp_path):
    _patch_fichiers(monkeypatch, tmp_path)
    params = mp.charger_parametres()
    assert params["b2_workers"] == mp.DEFAUTS["b2_workers"]
    assert params["b1_workers"] == mp.DEFAUTS["b1_workers"]
    assert params["historique"] == []


def test_sauver_puis_charger_parametres_round_trip(monkeypatch, tmp_path):
    _patch_fichiers(monkeypatch, tmp_path)
    params = mp.charger_parametres()
    params["b2_workers"] = 6
    mp.sauver_parametres(params)
    relu = mp.charger_parametres()
    assert relu["b2_workers"] == 6
    assert relu["derniere_maj"] is not None


# ---------------------------------------------------------------------------
# _clamp_ajustement : bornes +/-25%
# ---------------------------------------------------------------------------

def test_clamp_ajustement_refuse_saut_trop_grand():
    # valeur actuelle 4, visee 100 -> doit rester dans +/-25% de 4 (ecart max = 1)
    r = mp._clamp_ajustement(4, 100, plancher=1, plafond=20)
    assert r == 5  # 4 + max(1, round(4*0.25)) = 4 + 1


def test_clamp_ajustement_respecte_plafond():
    r = mp._clamp_ajustement(8, 9, plancher=1, plafond=8)
    assert r == 8


def test_clamp_ajustement_respecte_plancher():
    r = mp._clamp_ajustement(2, 0, plancher=2, plafond=16)
    assert r == 2


# ---------------------------------------------------------------------------
# analyser_run : regles d'ajustement
# ---------------------------------------------------------------------------

def test_analyser_run_trop_de_timeouts_b2_reduit_les_workers(monkeypatch, tmp_path):
    _patch_fichiers(monkeypatch, tmp_path)
    db_path = _tmp_db_path()
    try:
        run_id = "run-timeout"
        # 10 evenements b2, 3 timeouts (30% > seuil 15%)
        for i in range(7):
            staging.log_evenement(run_id, "b2", "ok", f"ok {i}", niveau="info", path=db_path)
        for i in range(3):
            staging.log_evenement(run_id, "b2", "timeout", f"timeout {i}", path=db_path)

        params_avant = mp.charger_parametres()
        assert params_avant["b2_workers"] == 4

        resultat = mp.analyser_run(run_id, path=db_path)
        params_apres = resultat["parametres"]

        assert params_apres["b2_workers"] < params_avant["b2_workers"]
        assert len(resultat["ajustements"]) >= 1
        assert any(a["parametre"] == "b2_workers" for a in resultat["ajustements"])
    finally:
        _cleanup_db(db_path)


def test_analyser_run_erreur_quasi_nulle_augmente_workers_dun_cran(monkeypatch, tmp_path):
    _patch_fichiers(monkeypatch, tmp_path)
    db_path = _tmp_db_path()
    try:
        run_id = "run-propre"
        for i in range(20):
            staging.log_evenement(run_id, "b2", "ok", f"ok {i}", niveau="info", path=db_path)

        resultat = mp.analyser_run(run_id, path=db_path)
        params_apres = resultat["parametres"]

        assert params_apres["b2_workers"] == mp.DEFAUTS["b2_workers"] + 1
        assert any(a["parametre"] == "b2_workers" and a["apres"] > a["avant"]
                   for a in resultat["ajustements"])
    finally:
        _cleanup_db(db_path)


def test_analyser_run_plafond_b2_workers_jamais_depasse(monkeypatch, tmp_path):
    _patch_fichiers(monkeypatch, tmp_path)
    db_path = _tmp_db_path()
    try:
        # Pre-charge des parametres avec b2_workers deja au plafond
        params = mp.charger_parametres()
        params["b2_workers"] = mp.B2_WORKERS_PLAFOND
        mp.sauver_parametres(params)

        run_id = "run-plafond"
        for i in range(20):
            staging.log_evenement(run_id, "b2", "ok", f"ok {i}", niveau="info", path=db_path)

        resultat = mp.analyser_run(run_id, path=db_path)
        assert resultat["parametres"]["b2_workers"] <= mp.B2_WORKERS_PLAFOND
    finally:
        _cleanup_db(db_path)


def test_analyser_run_trop_de_pages_mortes_b1_reduit_workers(monkeypatch, tmp_path):
    _patch_fichiers(monkeypatch, tmp_path)
    db_path = _tmp_db_path()
    try:
        run_id = "run-pages-mortes"
        for i in range(6):
            staging.log_evenement(run_id, "b1", "ok", f"ok {i}", niveau="info", path=db_path)
        for i in range(4):
            staging.log_evenement(run_id, "b1", "page_morte", f"page morte {i}", path=db_path)

        params_avant = mp.charger_parametres()
        resultat = mp.analyser_run(run_id, path=db_path)
        params_apres = resultat["parametres"]

        assert params_apres["b1_workers"] < params_avant["b1_workers"]
        assert any(a["parametre"] == "b1_workers" for a in resultat["ajustements"])
    finally:
        _cleanup_db(db_path)


def test_analyser_run_plancher_b1_workers_jamais_depasse(monkeypatch, tmp_path):
    _patch_fichiers(monkeypatch, tmp_path)
    db_path = _tmp_db_path()
    try:
        params = mp.charger_parametres()
        params["b1_workers"] = mp.B1_WORKERS_PLANCHER
        mp.sauver_parametres(params)

        run_id = "run-plancher"
        for i in range(4):
            staging.log_evenement(run_id, "b1", "page_morte", f"page morte {i}", path=db_path)

        resultat = mp.analyser_run(run_id, path=db_path)
        assert resultat["parametres"]["b1_workers"] >= mp.B1_WORKERS_PLANCHER
    finally:
        _cleanup_db(db_path)


def test_analyser_run_historique_journalise_chaque_appel(monkeypatch, tmp_path):
    _patch_fichiers(monkeypatch, tmp_path)
    db_path = _tmp_db_path()
    try:
        run_id = "run-historique"
        staging.log_evenement(run_id, "b1", "ok", "rien de special", niveau="info", path=db_path)

        resultat = mp.analyser_run(run_id, path=db_path)
        historique = resultat["parametres"]["historique"]
        assert len(historique) == 1
        assert historique[0]["run_id"] == run_id
    finally:
        _cleanup_db(db_path)


# ---------------------------------------------------------------------------
# ecrire_lecons
# ---------------------------------------------------------------------------

def test_ecrire_lecons_cree_le_fichier_et_ajoute_une_section(monkeypatch, tmp_path):
    params_path, lecons_path = _patch_fichiers(monkeypatch, tmp_path)
    db_path = _tmp_db_path()
    try:
        run_id = "run-lecons"
        staging.log_evenement(run_id, "b2", "json_invalide", "cle manquante", slug="tool-a", path=db_path)
        staging.log_evenement(run_id, "b2", "quarantaine", "3 echecs", slug="tool-a", path=db_path)

        chemin = mp.ecrire_lecons(run_id, path=db_path)
        assert Path(chemin) == lecons_path
        assert lecons_path.exists()
        contenu = lecons_path.read_text(encoding="utf-8")
        assert run_id in contenu
        assert "tool-a" in contenu
    finally:
        _cleanup_db(db_path)


def test_ecrire_lecons_deux_runs_accumulent_dans_le_meme_fichier(monkeypatch, tmp_path):
    _, lecons_path = _patch_fichiers(monkeypatch, tmp_path)
    db_path = _tmp_db_path()
    try:
        staging.log_evenement("run-x", "b1", "ok", "rien", niveau="info", path=db_path)
        staging.log_evenement("run-y", "b1", "ok", "rien", niveau="info", path=db_path)

        mp.ecrire_lecons("run-x", path=db_path)
        mp.ecrire_lecons("run-y", path=db_path)

        contenu = lecons_path.read_text(encoding="utf-8")
        assert "run-x" in contenu
        assert "run-y" in contenu
        assert contenu.count("## Run") == 2
    finally:
        _cleanup_db(db_path)


# ---------------------------------------------------------------------------
# analyser_run : regle b2b (part de verdicts "reprendre" > 30% -> lecon,
# jamais d'auto-ajustement de parametre reellement applique)
# ---------------------------------------------------------------------------

def test_analyser_run_reprises_juge_elevees_note_une_recommandation(monkeypatch, tmp_path):
    _patch_fichiers(monkeypatch, tmp_path)
    db_path = _tmp_db_path()
    try:
        run_id = "run-juge-severe"
        # 10 evenements b2b, 4 "fiche_reprise" (40% > seuil 30%)
        for i in range(6):
            staging.log_evenement(run_id, "b2b", "ok", f"ok {i}", niveau="info", path=db_path)
        for i in range(4):
            staging.log_evenement(run_id, "b2b", "fiche_reprise", f"reprise {i}",
                                   niveau="info", path=db_path)

        resultat = mp.analyser_run(run_id, path=db_path)

        assert any(
            a["parametre"].startswith("b2_model") and mp.MODELE_B2_RECOMMANDE_SI_REPRISES_HAUT in a["apres"]
            for a in resultat["ajustements"]
        )
        # La recommandation n'est PAS un parametre reellement applique :
        # aucune cle b2_model dans les parametres sauvegardes.
        assert "b2_model" not in resultat["parametres"]
    finally:
        _cleanup_db(db_path)


def test_analyser_run_reprises_juge_basses_ne_note_rien(monkeypatch, tmp_path):
    _patch_fichiers(monkeypatch, tmp_path)
    db_path = _tmp_db_path()
    try:
        run_id = "run-juge-ok"
        for i in range(9):
            staging.log_evenement(run_id, "b2b", "ok", f"ok {i}", niveau="info", path=db_path)
        for i in range(1):
            staging.log_evenement(run_id, "b2b", "fiche_reprise", f"reprise {i}",
                                   niveau="info", path=db_path)

        resultat = mp.analyser_run(run_id, path=db_path)

        assert not any(a["parametre"].startswith("b2_model") for a in resultat["ajustements"])
    finally:
        _cleanup_db(db_path)


# ---------------------------------------------------------------------------
# analyser_run : regle modele_absent_repli -> lecon (jamais d'auto-ajustement)
# ---------------------------------------------------------------------------

def test_analyser_run_modele_absent_repli_note_une_lecon(monkeypatch, tmp_path):
    _patch_fichiers(monkeypatch, tmp_path)
    db_path = _tmp_db_path()
    try:
        run_id = "run-modele-absent"
        staging.log_evenement(run_id, "b2b", "ok", "ok", niveau="info", path=db_path)
        staging.log_evenement(run_id, "b2b", "modele_absent_repli",
                               "modele arbitre absent -- repli sur MODELE_GEN",
                               niveau="info", path=db_path)

        resultat = mp.analyser_run(run_id, path=db_path)

        entree = next(
            (a for a in resultat["ajustements"] if a["parametre"].startswith("modele_arbitre")),
            None,
        )
        assert entree is not None
        assert "ollama pull" in entree["apres"]
        # Toujours une lecon, jamais un parametre reellement applique.
        assert "modele_arbitre" not in resultat["parametres"]
    finally:
        _cleanup_db(db_path)


def test_analyser_run_sans_modele_absent_repli_ne_note_rien(monkeypatch, tmp_path):
    _patch_fichiers(monkeypatch, tmp_path)
    db_path = _tmp_db_path()
    try:
        run_id = "run-modele-ok"
        staging.log_evenement(run_id, "b2b", "ok", "ok", niveau="info", path=db_path)

        resultat = mp.analyser_run(run_id, path=db_path)

        assert not any(a["parametre"].startswith("modele_arbitre") for a in resultat["ajustements"])
    finally:
        _cleanup_db(db_path)


def test_ecrire_lecons_modele_absent_repli_apparait_dans_lecons_md(monkeypatch, tmp_path):
    _, lecons_path = _patch_fichiers(monkeypatch, tmp_path)
    db_path = _tmp_db_path()
    try:
        run_id = "run-lecons-modele"
        staging.log_evenement(run_id, "b2b", "modele_absent_repli",
                               "modele arbitre absent", slug="tool-x",
                               niveau="info", path=db_path)

        mp.ecrire_lecons(run_id, path=db_path)
        contenu = lecons_path.read_text(encoding="utf-8")
        assert "modele_arbitre" in contenu
        assert "ollama pull" in contenu
    finally:
        _cleanup_db(db_path)
