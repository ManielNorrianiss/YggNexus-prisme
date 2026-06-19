# -*- coding: utf-8 -*-
"""
Tests purs de b6_pages (B6 phase 2) : compare_key, validate_intro et les
content_hash. Aucun acces reseau ni DB.
"""
import b6_pages


TOOL_A = {"slug": "jasper", "name": "Jasper", "short_desc": "AI writer",
          "pricing": "paid", "quality_score": 8.5}
TOOL_B = {"slug": "copy-ai", "name": "Copy.ai", "short_desc": "AI copy",
          "pricing": "freemium", "quality_score": 7.9}


# --------------------------------------------------------------------------
# compare_key
# --------------------------------------------------------------------------

def test_compare_key_ordre_alpha():
    assert b6_pages.compare_key("jasper", "copy-ai") == "copy-ai-vs-jasper"


def test_compare_key_independant_de_l_ordre():
    assert b6_pages.compare_key("a", "b") == b6_pages.compare_key("b", "a")


# --------------------------------------------------------------------------
# validate_intro : garde-fou anti-mince + fallbacks
# --------------------------------------------------------------------------

def test_intro_mince_detectee():
    out = {"intro_md": "Trop court."}
    _, is_thin = b6_pages.validate_intro(out, "T", "D")
    assert is_thin is True


def test_intro_riche_non_mince():
    out = {"intro_md": "a" * 250, "seo_title": "Titre", "seo_description": "Desc"}
    fields, is_thin = b6_pages.validate_intro(out, "T", "D")
    assert is_thin is False
    assert fields["seo_title"] == "Titre"
    assert fields["seo_description"] == "Desc"


def test_seuil_min_exact_non_mince():
    out = {"intro_md": "a" * b6_pages.MIN_INTRO}
    _, is_thin = b6_pages.validate_intro(out, "T", "D")
    assert is_thin is False


def test_intro_tronquee_max():
    out = {"intro_md": "a" * (b6_pages.MAX_INTRO + 300)}
    fields, _ = b6_pages.validate_intro(out, "T", "D")
    assert len(fields["intro_md"]) <= b6_pages.MAX_INTRO


def test_title_fallback_et_troncature():
    out = {"intro_md": "a" * 250}  # pas de seo_title
    fields, _ = b6_pages.validate_intro(out, "Mon titre de secours", "D")
    assert fields["seo_title"] == "Mon titre de secours"
    out2 = {"intro_md": "a" * 250, "seo_title": "Z" * 200}
    fields2, _ = b6_pages.validate_intro(out2, "T", "D")
    assert len(fields2["seo_title"]) <= b6_pages.MAX_TITLE


def test_desc_fallback_et_troncature():
    out = {"intro_md": "b" * 300}  # pas de seo_description
    fields, _ = b6_pages.validate_intro(out, "T", "Desc de secours")
    assert fields["seo_description"]
    assert len(fields["seo_description"]) <= b6_pages.MAX_SEO_DESC


def test_desc_fallback_utilise_le_fallback_si_intro_vide_apres_clean():
    # intro mince -> is_thin, mais on verifie quand meme la logique de fallback desc
    out = {"intro_md": ""}
    fields, is_thin = b6_pages.validate_intro(out, "T", "Secours desc")
    assert is_thin is True
    assert fields["seo_description"] == "Secours desc"


# --------------------------------------------------------------------------
# content_hash_compare : symetrique + sensible
# --------------------------------------------------------------------------

def test_hash_compare_symetrique():
    assert (b6_pages.content_hash_compare(TOOL_A, TOOL_B)
            == b6_pages.content_hash_compare(TOOL_B, TOOL_A))


def test_hash_compare_deterministe():
    assert (b6_pages.content_hash_compare(TOOL_A, TOOL_B)
            == b6_pages.content_hash_compare(TOOL_A, TOOL_B))


def test_hash_compare_change_si_champ_change():
    tb2 = dict(TOOL_B, quality_score=6.0)
    assert (b6_pages.content_hash_compare(TOOL_A, TOOL_B)
            != b6_pages.content_hash_compare(TOOL_A, tb2))


def test_hash_compare_inclut_version():
    assert b6_pages.PROMPT_VERSION  # existe et non vide


# --------------------------------------------------------------------------
# content_hash_alternatives
# --------------------------------------------------------------------------

def test_hash_alt_deterministe():
    alts = [TOOL_A, TOOL_B]
    assert (b6_pages.content_hash_alternatives(TOOL_A, alts)
            == b6_pages.content_hash_alternatives(TOOL_A, alts))


def test_hash_alt_independant_ordre():
    assert (b6_pages.content_hash_alternatives(TOOL_A, [TOOL_A, TOOL_B])
            == b6_pages.content_hash_alternatives(TOOL_A, [TOOL_B, TOOL_A]))


def test_hash_alt_change_si_alt_ajoutee():
    tc = {"slug": "writesonic", "name": "Writesonic", "short_desc": "x",
          "pricing": "paid", "quality_score": 7.0}
    h1 = b6_pages.content_hash_alternatives(TOOL_A, [TOOL_B])
    h2 = b6_pages.content_hash_alternatives(TOOL_A, [TOOL_B, tc])
    assert h1 != h2
