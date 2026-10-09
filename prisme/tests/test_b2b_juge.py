# -*- coding: utf-8 -*-
"""
Tests purs de b2b_juge.py : verdicts ok/reprendre/nom_corrige/score_corrige
avec un faux LLM, garde-fou une-seule-reprise. Utilise un fichier SQLite
temporaire (jamais staging.db du montage) via le parametre path=.
"""
import os
import tempfile

import b2b_juge as b2b
import staging


def _tmp_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)
    return path


def _cleanup(path):
    for ext in ("", "-wal", "-shm", "-journal"):
        p = path + ext
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass


def _seed(path, slug="tool-x", name="Tool X"):
    staging.upsert_raw({"slug": slug, "name": name, "website_url": f"https://{slug}.io",
                         "raw_title": f"{name} - site", "raw_meta_desc": "desc",
                         "raw_text": "some text"}, path=path)
    staging.upsert_enriched({
        "slug": slug, "short_desc": "A great tool.", "description_md": "Body.",
        "pros_json": ["a", "b"], "cons_json": ["c"], "faq_json": [{"q": "q", "a": "a"}],
        "seo_title": "T", "seo_description": "D", "application_category": "BusinessApplication",
        "pricing": "freemium", "pricing_note": "note", "quality_score": 8.7,
        "content_hash": "hash1", "enriched_at": "2026-07-01T00:00:00Z",
    }, path=path)


# ---------------------------------------------------------------------------
# check_sortie_juge / normaliser_sortie_juge
# ---------------------------------------------------------------------------

def test_check_sortie_juge_accepte_sortie_valide():
    assert b2b.check_sortie_juge(b2b.fake_juge("", "")) is None


def test_check_sortie_juge_detecte_verdict_hors_enum():
    d = b2b.fake_juge("", "")
    d["verdict"] = "peut-etre"
    msg = b2b.check_sortie_juge(d)
    assert msg is not None
    assert "verdict" in msg


def test_check_sortie_juge_detecte_cles_manquantes():
    d = b2b.fake_juge("", "")
    del d["score"]
    msg = b2b.check_sortie_juge(d)
    assert msg is not None
    assert "score" in msg


# ---------------------------------------------------------------------------
# run_juge : verdict "ok" simple
# ---------------------------------------------------------------------------

def test_run_juge_verdict_ok_ecrit_juge_score_et_verdict():
    path = _tmp_db_path()
    try:
        staging.init_memoire(path)
        staging.init_juge(path)
        _seed(path, "tool-ok")

        def fn_gen(prompt, system, modele=None, timeout=120, _appel=None):
            return {"verdict": "ok", "score": 6.5, "problemes": [],
                    "nom_corrige": None, "score_qualite_corrige": None}

        raw = staging.get_raw("tool-ok", path=path)
        enriched = staging.get_enriched("tool-ok", path=path)
        resume = b2b.run_juge([("tool-ok", raw, enriched)], fn_gen, "fake-model",
                               workers=1, dry_run=False, run_id="run-1",
                               log_fn=lambda **kw: staging.log_evenement(path=path, **kw),
                               path=path)

        assert resume["nb_juges"] == 1
        assert resume["nb_repris"] == 0
        row = staging.get_enriched("tool-ok", path=path)
        assert row["juge_verdict"] == "ok"
        assert row["juge_score"] == 6.5
    finally:
        _cleanup(path)


# ---------------------------------------------------------------------------
# run_juge : nom corrige
# ---------------------------------------------------------------------------

def test_run_juge_nom_corrige_met_a_jour_raw_tools_name():
    path = _tmp_db_path()
    try:
        staging.init_memoire(path)
        staging.init_juge(path)
        _seed(path, "acmetool-io", name="acmetool-io")

        def fn_gen(prompt, system, modele=None, timeout=120, _appel=None):
            return {"verdict": "ok", "score": 7.0, "problemes": ["nom brut"],
                    "nom_corrige": "Acme Tool", "score_qualite_corrige": None}

        raw = staging.get_raw("acmetool-io", path=path)
        enriched = staging.get_enriched("acmetool-io", path=path)
        resume = b2b.run_juge([("acmetool-io", raw, enriched)], fn_gen, "fake-model",
                               workers=1, dry_run=False, run_id="run-2",
                               log_fn=lambda **kw: staging.log_evenement(path=path, **kw),
                               path=path)

        assert resume["nb_noms_corriges"] == 1
        row = staging.get_raw("acmetool-io", path=path)
        assert row["name"] == "Acme Tool"
    finally:
        _cleanup(path)


# ---------------------------------------------------------------------------
# run_juge : score corrige
# ---------------------------------------------------------------------------

def test_run_juge_score_corrige_remplace_quality_score():
    path = _tmp_db_path()
    try:
        staging.init_memoire(path)
        staging.init_juge(path)
        _seed(path, "tool-score")

        def fn_gen(prompt, system, modele=None, timeout=120, _appel=None):
            return {"verdict": "ok", "score": 5.0, "problemes": ["score trop uniforme"],
                    "nom_corrige": None, "score_qualite_corrige": 5.5}

        raw = staging.get_raw("tool-score", path=path)
        enriched = staging.get_enriched("tool-score", path=path)
        resume = b2b.run_juge([("tool-score", raw, enriched)], fn_gen, "fake-model",
                               workers=1, dry_run=False, run_id="run-3",
                               log_fn=lambda **kw: staging.log_evenement(path=path, **kw),
                               path=path)

        assert resume["nb_scores_corriges"] == 1
        row = staging.get_enriched("tool-score", path=path)
        assert row["quality_score"] == 5.5
    finally:
        _cleanup(path)


# ---------------------------------------------------------------------------
# run_juge : verdict "reprendre" -> fiche supprimee (re-file b2)
# ---------------------------------------------------------------------------

def test_run_juge_verdict_reprendre_supprime_enriched_pour_re_traitement_b2():
    path = _tmp_db_path()
    try:
        staging.init_memoire(path)
        staging.init_juge(path)
        _seed(path, "tool-mauvais")

        def fn_gen(prompt, system, modele=None, timeout=120, _appel=None):
            return {"verdict": "reprendre", "score": 3.0,
                    "problemes": ["description generique", "FAQ creuse"],
                    "nom_corrige": None, "score_qualite_corrige": None}

        raw = staging.get_raw("tool-mauvais", path=path)
        enriched = staging.get_enriched("tool-mauvais", path=path)
        resume = b2b.run_juge([("tool-mauvais", raw, enriched)], fn_gen, "fake-model",
                               workers=1, dry_run=False, run_id="run-4",
                               log_fn=lambda **kw: staging.log_evenement(path=path, **kw),
                               path=path)

        assert resume["nb_repris"] == 1
        # La ligne enriched a disparu : b2_enrichissement.py la reverra
        # (staging.get_enriched(slug) redevient None -> "existing" est None
        # dans la boucle de selection de b2_enrichissement.main()).
        assert staging.get_enriched("tool-mauvais", path=path) is None
        assert staging.get_juge_reprises("tool-mauvais", path=path) == 1
    finally:
        _cleanup(path)


def test_run_juge_garde_fou_une_seule_reprise_par_fiche():
    """Si juge_reprises a deja atteint le plafond, un nouveau verdict
    'reprendre' est journalise mais N'EST PAS applique (pas de suppression,
    pas de boucle infinie)."""
    path = _tmp_db_path()
    try:
        staging.init_memoire(path)
        staging.init_juge(path)
        _seed(path, "tool-boucle")
        staging.increment_juge_reprises("tool-boucle", path=path)  # deja repris une fois
        assert staging.get_juge_reprises("tool-boucle", path=path) == 1

        evenements = []

        def fn_gen(prompt, system, modele=None, timeout=120, _appel=None):
            return {"verdict": "reprendre", "score": 2.0, "problemes": ["toujours mauvais"],
                    "nom_corrige": None, "score_qualite_corrige": None}

        def log_fn(run_id, etape, type_evenement, detail, slug=None, niveau="erreur"):
            evenements.append(type_evenement)
            staging.log_evenement(run_id, etape, type_evenement, detail, slug=slug,
                                   niveau=niveau, path=path)

        raw = staging.get_raw("tool-boucle", path=path)
        enriched = staging.get_enriched("tool-boucle", path=path)
        resume = b2b.run_juge([("tool-boucle", raw, enriched)], fn_gen, "fake-model",
                               workers=1, dry_run=False, run_id="run-5", log_fn=log_fn,
                               path=path)

        assert resume["nb_repris"] == 0
        assert "fiche_reprise_refusee" in evenements
        # La fiche enriched N'A PAS ete supprimee (garde-fou respecte).
        assert staging.get_enriched("tool-boucle", path=path) is not None
        # Le compteur n'a pas bouge non plus.
        assert staging.get_juge_reprises("tool-boucle", path=path) == 1
    finally:
        _cleanup(path)


def test_run_juge_dry_run_n_ecrit_rien():
    path = _tmp_db_path()
    try:
        staging.init_memoire(path)
        staging.init_juge(path)
        _seed(path, "tool-dry")

        def fn_gen(prompt, system, modele=None, timeout=120, _appel=None):
            return {"verdict": "reprendre", "score": 2.0, "problemes": ["x"],
                    "nom_corrige": "Nouveau Nom", "score_qualite_corrige": 3.0}

        raw = staging.get_raw("tool-dry", path=path)
        enriched = staging.get_enriched("tool-dry", path=path)
        resume = b2b.run_juge([("tool-dry", raw, enriched)], fn_gen, "fake-model",
                               workers=1, dry_run=True, run_id="run-6", path=path)

        assert resume["nb_juges"] == 1
        # Rien ecrit : la fiche enriched existe toujours, inchangee.
        row = staging.get_enriched("tool-dry", path=path)
        assert row is not None
        assert row["juge_verdict"] is None
        assert row["quality_score"] == 8.7
        assert staging.get_raw("tool-dry", path=path)["name"] == "Tool X"
    finally:
        _cleanup(path)


# ---------------------------------------------------------------------------
# selectionner_a_juger : ne reprend pas les fiches deja jugees
# ---------------------------------------------------------------------------

def test_selectionner_a_juger_ignore_les_fiches_deja_jugees():
    path = _tmp_db_path()
    try:
        staging.init_memoire(path)
        staging.init_juge(path)
        _seed(path, "tool-a")
        _seed(path, "tool-b")
        staging.set_juge_verdict("tool-a", 7.0, "ok", path=path)

        a_juger = b2b.selectionner_a_juger(path=path)
        slugs = [s for (s, _, _) in a_juger]
        assert "tool-b" in slugs
        assert "tool-a" not in slugs
    finally:
        _cleanup(path)


# ---------------------------------------------------------------------------
# generer_avec_repli : routage arbitre -> repli MODELE_GEN si modele absent
# ---------------------------------------------------------------------------

def test_generer_avec_repli_utilise_le_modele_arbitre_si_disponible():
    appels = []

    def fn_gen(prompt, system, modele=None, timeout=120, _appel=None):
        appels.append(modele)
        return {"verdict": "ok", "score": 6.0, "problemes": [],
                "nom_corrige": None, "score_qualite_corrige": None}

    sortie = b2b.generer_avec_repli(fn_gen, "prompt", "system", "qwen2.5:14b-instruct")
    assert sortie["verdict"] == "ok"
    assert appels == ["qwen2.5:14b-instruct"]


def test_generer_avec_repli_retombe_sur_modele_gen_si_modele_absent():
    from llm_local import LLMError, MODELE_GEN

    appels = []

    def fn_gen(prompt, system, modele=None, timeout=120, _appel=None):
        appels.append(modele)
        if modele != MODELE_GEN:
            raise LLMError("model 'qwen2.5:14b-instruct' not found, try pulling it first")
        return {"verdict": "ok", "score": 6.0, "problemes": [],
                "nom_corrige": None, "score_qualite_corrige": None}

    evenements = []

    def log_fn(run_id, etape, type_evenement, detail, slug=None, niveau="erreur"):
        evenements.append(type_evenement)

    sortie = b2b.generer_avec_repli(fn_gen, "prompt", "system", "qwen2.5:14b-instruct",
                                     run_id="run-repli", log_fn=log_fn, slug="tool-x")

    assert sortie["verdict"] == "ok"
    assert appels == ["qwen2.5:14b-instruct", MODELE_GEN]
    assert "modele_absent_repli" in evenements


def test_generer_avec_repli_ne_retombe_pas_si_erreur_autre_que_modele_absent():
    from llm_local import LLMError

    def fn_gen(prompt, system, modele=None, timeout=120, _appel=None):
        raise LLMError("Ollama injoignable: timed out")

    try:
        b2b.generer_avec_repli(fn_gen, "prompt", "system", "qwen2.5:14b-instruct")
        assert False, "aurait du lever LLMError"
    except LLMError as e:
        assert "timed out" in str(e)


def test_generer_avec_repli_ne_boucle_pas_si_deja_modele_gen():
    from llm_local import LLMError, MODELE_GEN

    appels = []

    def fn_gen(prompt, system, modele=None, timeout=120, _appel=None):
        appels.append(modele)
        raise LLMError("model not found")

    try:
        b2b.generer_avec_repli(fn_gen, "prompt", "system", MODELE_GEN)
        assert False, "aurait du lever LLMError"
    except LLMError:
        pass
    # Un seul appel : pas de deuxieme tentative puisqu'on etait deja sur MODELE_GEN.
    assert appels == [MODELE_GEN]
