# -*- coding: utf-8 -*-
"""
Tests purs (sans reseau, sans DB) du filet score /10 et du filet SEO
de export_tools.build_entry.

build_entry appelle staging.get_tool_categories(); on le neutralise pour
qu'il retombe sur le fallback sources.json (categories vides ici).
"""
import pytest

import export_tools


@pytest.fixture(autouse=True)
def _no_db(monkeypatch):
    # Empeche tout acces a staging.db : B4 vide -> fallback sources.json.
    monkeypatch.setattr(export_tools.staging, "get_tool_categories", lambda slug: [])


def _build(raw_extra=None, enr_extra=None):
    raw = {"slug": "demo", "name": "Demo Tool", "status": "published"}
    if raw_extra:
        raw.update(raw_extra)
    enr = {"short_desc": "Un outil de demonstration."}
    if enr_extra:
        enr.update(enr_extra)
    return export_tools.build_entry(raw, enr)


# --------------------------------------------------------------------------
# Filet score /10
# --------------------------------------------------------------------------

def test_score_echelle_100_ramene_sur_10():
    assert _build(enr_extra={"quality_score": 85})["quality_score"] == 8.5


def test_score_deja_sur_10_inchange():
    assert _build(enr_extra={"quality_score": 7.3})["quality_score"] == 7.3


def test_score_borne_haute_clampe_a_10():
    # 120 -> /10 = 12 -> clamp 10.0
    assert _build(enr_extra={"quality_score": 120})["quality_score"] == 10.0


def test_score_negatif_clampe_a_0():
    assert _build(enr_extra={"quality_score": -5})["quality_score"] == 0.0


def test_score_none_reste_none():
    assert _build(enr_extra={"quality_score": None})["quality_score"] is None


def test_score_non_numerique_devient_none():
    assert _build(enr_extra={"quality_score": "abc"})["quality_score"] is None


def test_score_limite_exacte_10_inchange():
    assert _build(enr_extra={"quality_score": 10})["quality_score"] == 10.0


# --------------------------------------------------------------------------
# Filet SEO deterministe
# --------------------------------------------------------------------------

def test_seo_title_derive_du_nom_et_desc_quand_absent():
    e = _build(enr_extra={"short_desc": "Ecriture assistee par IA"})
    assert e["seo_title"]
    assert e["seo_title"].startswith("Demo Tool")
    assert "Ecriture assistee par IA" in e["seo_title"]


def test_seo_title_tronque_a_60():
    long_desc = "x" * 200
    e = _build(enr_extra={"short_desc": long_desc})
    assert len(e["seo_title"]) <= 60


def test_seo_description_derivee_quand_absente():
    e = _build(enr_extra={"short_desc": "Resume court de l outil."})
    assert e["seo_description"]
    assert len(e["seo_description"]) <= 155


def test_seo_description_tronquee_a_155():
    e = _build(enr_extra={"short_desc": "y" * 400})
    assert len(e["seo_description"]) <= 155


def test_seo_fournis_par_llm_sont_conserves():
    e = _build(enr_extra={
        "seo_title": "Titre manuel",
        "seo_description": "Description manuelle.",
    })
    assert e["seo_title"] == "Titre manuel"
    assert e["seo_description"] == "Description manuelle."


def test_seo_title_fallback_sur_slug_si_aucun_nom():
    e = export_tools.build_entry({"slug": "zapier", "status": "published"},
                                 {"short_desc": ""})
    # ni name ni short_desc -> titre = slug
    assert e["seo_title"] == "zapier"
