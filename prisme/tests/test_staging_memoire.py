# -*- coding: utf-8 -*-
"""
Tests purs de la memoire d'erreurs dans staging.py : log_evenement,
stats_run, increment_echecs, mettre_en_quarantaine. Utilise un fichier
SQLite temporaire (jamais staging.db du montage) via le parametre path=.
"""
import os
import tempfile

import staging


def _tmp_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)  # on veut juste un chemin libre, sqlite cree le fichier
    return path


def _cleanup(path):
    for ext in ("", "-wal", "-shm", "-journal"):
        p = path + ext
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass


def test_log_evenement_et_stats_run_comptent_correctement():
    path = _tmp_db_path()
    try:
        staging.init_memoire(path)
        staging.log_evenement("run-1", "b1", "page_morte", "timeout sur x", slug="tool-x", path=path)
        staging.log_evenement("run-1", "b2", "json_invalide", "cle manquante", slug="tool-y", path=path)
        staging.log_evenement("run-1", "b2", "reprise_reussie", "ok au 2e essai", slug="tool-y",
                               niveau="info", path=path)
        staging.log_evenement("run-2", "b1", "page_morte", "autre run", slug="tool-z", path=path)

        stats = staging.stats_run("run-1", path=path)
        assert stats["run_id"] == "run-1"
        assert stats["total"] == 3
        assert stats["par_etape"]["b1"]["total"] == 1
        assert stats["par_etape"]["b1"]["erreurs"] == 1
        assert stats["par_etape"]["b2"]["total"] == 2
        assert stats["par_etape"]["b2"]["erreurs"] == 1  # json_invalide=erreur, reprise_reussie=info
        assert stats["par_type"]["page_morte"] == 1
        assert stats["par_type"]["json_invalide"] == 1
        assert stats["par_type"]["reprise_reussie"] == 1

        # run-2 est isole de run-1
        stats2 = staging.stats_run("run-2", path=path)
        assert stats2["total"] == 1
    finally:
        _cleanup(path)


def test_stats_run_run_id_inconnu_retourne_vide():
    path = _tmp_db_path()
    try:
        staging.init_memoire(path)
        stats = staging.stats_run("run-inexistant", path=path)
        assert stats["total"] == 0
        assert stats["par_etape"] == {}
        assert stats["par_type"] == {}
        assert stats["slugs_quarantaine"] == []
    finally:
        _cleanup(path)


def test_increment_echecs_incremente_et_retourne_le_compte():
    path = _tmp_db_path()
    try:
        staging.upsert_raw({"slug": "tool-a", "name": "Tool A"}, path=path)
        n1 = staging.increment_echecs("tool-a", path=path)
        n2 = staging.increment_echecs("tool-a", path=path)
        n3 = staging.increment_echecs("tool-a", path=path)
        assert (n1, n2, n3) == (1, 2, 3)
        row = staging.get_raw("tool-a", path=path)
        assert row["echecs"] == 3
    finally:
        _cleanup(path)


def test_increment_echecs_slug_inexistant_retourne_zero():
    path = _tmp_db_path()
    try:
        staging.init_memoire(path)
        n = staging.increment_echecs("fantome", path=path)
        assert n == 0
    finally:
        _cleanup(path)


def test_mettre_en_quarantaine_apres_3_echecs():
    """Simule le comportement de b2_enrichissement : 3 echecs -> quarantaine."""
    path = _tmp_db_path()
    try:
        staging.upsert_raw({"slug": "tool-b", "name": "Tool B", "status": "draft"}, path=path)
        for _ in range(3):
            n = staging.increment_echecs("tool-b", path=path)
        assert n == 3
        staging.mettre_en_quarantaine("tool-b", path=path)
        row = staging.get_raw("tool-b", path=path)
        assert row["status"] == "quarantaine"
    finally:
        _cleanup(path)


def test_migrate_raw_tools_echecs_est_idempotente():
    """Appeler la migration plusieurs fois ne doit jamais lever."""
    path = _tmp_db_path()
    try:
        staging.migrate_raw_tools_echecs(path=path)
        staging.migrate_raw_tools_echecs(path=path)
        staging.migrate_raw_tools_echecs(path=path)  # 3e appel, doit rester silencieux
        staging.upsert_raw({"slug": "tool-c"}, path=path)
        row = staging.get_raw("tool-c", path=path)
        assert row["echecs"] == 0
    finally:
        _cleanup(path)
