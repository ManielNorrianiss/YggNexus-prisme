# -*- coding: utf-8 -*-
"""
Tests purs de la parallelisation de b2_enrichissement.py (ThreadPoolExecutor,
--workers). Aucun acces reseau ni DB reelle -- utilise fake_llm/fake_embed
(deja fournis par le module pour --dry-run) et un faux staging en memoire
pour verifier les ecritures quand dry_run=False.
"""
import threading

import b2_enrichissement as b2


RAW_A = {"slug": "tool-a", "name": "Tool A", "raw_title": "Tool A - site",
         "raw_meta_desc": "desc a", "raw_text": "some text a"}
RAW_B = {"slug": "tool-b", "name": "Tool B", "raw_title": "Tool B - site",
         "raw_meta_desc": "desc b", "raw_text": "some text b"}
RAW_C = {"slug": "tool-c", "name": "Tool C", "raw_title": "Tool C - site",
         "raw_meta_desc": "desc c", "raw_text": "some text c"}


def _to_enrich(raws):
    return [(r, b2.content_hash_for(r)) for r in raws]


def test_run_enrichment_dry_run_traite_tout_sans_ecrire():
    """En --dry-run, tous les outils sont traites (nb_ok = total) et rien
    n'est ecrit en staging (fake_llm/fake_embed ne touchent pas au reseau)."""
    to_enrich = _to_enrich([RAW_A, RAW_B, RAW_C])
    nb_ok, nb_error = b2.run_enrichment(
        to_enrich, b2.fake_llm, b2.fake_embed, model="fake-model",
        workers=3, dry_run=True,
    )
    assert nb_ok == 3
    assert nb_error == 0


def test_run_enrichment_parallelise_utilise_plusieurs_fils():
    """Verifie que les taches sont bien reparties sur plusieurs fils
    (thread id different d'au moins deux taches) quand workers > 1."""
    thread_ids = []
    lock = threading.Lock()

    def fn_gen_trace(prompt, system, modele=None, timeout=120, _appel=None):
        with lock:
            thread_ids.append(threading.get_ident())
        return b2.fake_llm(prompt, system, modele=modele, timeout=timeout)

    to_enrich = _to_enrich([RAW_A, RAW_B, RAW_C])
    nb_ok, nb_error = b2.run_enrichment(
        to_enrich, fn_gen_trace, b2.fake_embed, model="fake-model",
        workers=3, dry_run=True,
    )
    assert nb_ok == 3
    assert nb_error == 0
    assert len(thread_ids) == 3
    # Au moins deux threads differents ont ete impliques (parallelisme reel,
    # pas juste un seul fil qui traite tout sequentiellement).
    assert len(set(thread_ids)) >= 2


def test_run_enrichment_ecrit_en_staging_via_fil_principal(monkeypatch):
    """Quand dry_run=False, les resultats sont ecrits en staging -- on
    verifie que les ecritures sont serialisees (jamais deux ecritures
    simultanees) meme si le calcul LLM est parallelise."""
    ecritures = []
    ecriture_en_cours = {"actif": False}
    erreurs_concurrence = []

    def fake_upsert_enriched(d):
        if ecriture_en_cours["actif"]:
            erreurs_concurrence.append("upsert_enriched concurrent detecte")
        ecriture_en_cours["actif"] = True
        ecritures.append(("enriched", d["slug"]))
        ecriture_en_cours["actif"] = False

    def fake_upsert_embedding(d):
        if ecriture_en_cours["actif"]:
            erreurs_concurrence.append("upsert_embedding concurrent detecte")
        ecriture_en_cours["actif"] = True
        ecritures.append(("embedding", d["slug"]))
        ecriture_en_cours["actif"] = False

    monkeypatch.setattr(b2.staging, "upsert_enriched", fake_upsert_enriched)
    monkeypatch.setattr(b2.staging, "upsert_embedding", fake_upsert_embedding)

    to_enrich = _to_enrich([RAW_A, RAW_B, RAW_C])
    nb_ok, nb_error = b2.run_enrichment(
        to_enrich, b2.fake_llm, b2.fake_embed, model="fake-model",
        workers=3, dry_run=False,
    )

    assert nb_ok == 3
    assert nb_error == 0
    assert erreurs_concurrence == []
    slugs_ecrits = {s for (_, s) in ecritures}
    assert slugs_ecrits == {"tool-a", "tool-b", "tool-c"}


def test_run_enrichment_erreur_llm_sur_un_outil_ne_bloque_pas_les_autres():
    """Un outil qui echoue au LLM ne doit pas empecher les autres d'etre
    traites (meme logique que B1 : l'echec d'une tache ne tue pas le lot)."""
    def fn_gen_parfois_en_echec(prompt, system, modele=None, timeout=120, _appel=None):
        if "Tool B" in prompt:
            raise b2.LLMError("echec simule pour tool-b")
        return b2.fake_llm(prompt, system, modele=modele, timeout=timeout)

    to_enrich = _to_enrich([RAW_A, RAW_B, RAW_C])
    nb_ok, nb_error = b2.run_enrichment(
        to_enrich, fn_gen_parfois_en_echec, b2.fake_embed, model="fake-model",
        workers=3, dry_run=True,
    )
    assert nb_ok == 2
    assert nb_error == 1


def test_run_enrichment_workers_1_reste_sequentiel_et_correct():
    """workers=1 doit rester fonctionnellement correct (cas degenere du
    pool a un seul fil, equivalent a l'ancien comportement sequentiel)."""
    to_enrich = _to_enrich([RAW_A, RAW_B])
    nb_ok, nb_error = b2.run_enrichment(
        to_enrich, b2.fake_llm, b2.fake_embed, model="fake-model",
        workers=1, dry_run=True,
    )
    assert nb_ok == 2
    assert nb_error == 0
