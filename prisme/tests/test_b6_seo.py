# -*- coding: utf-8 -*-
"""
Tests purs du content_hash et du garde-fou anti-mince (validate_category_content)
de b6_seo. Aucun acces reseau ni Supabase : on appelle uniquement les fonctions
pures.
"""
import b6_seo


CAT = {"slug": "ai-writing", "name": "AI Writing"}


# --------------------------------------------------------------------------
# content_hash_for
# --------------------------------------------------------------------------

def test_hash_deterministe():
    tools = [{"slug": "jasper"}, {"slug": "copy-ai"}]
    assert b6_seo.content_hash_for(CAT, tools) == b6_seo.content_hash_for(CAT, tools)


def test_hash_insensible_ordre_des_outils():
    h1 = b6_seo.content_hash_for(CAT, [{"slug": "a"}, {"slug": "b"}])
    h2 = b6_seo.content_hash_for(CAT, [{"slug": "b"}, {"slug": "a"}])
    assert h1 == h2


def test_hash_change_si_outil_ajoute():
    h1 = b6_seo.content_hash_for(CAT, [{"slug": "a"}])
    h2 = b6_seo.content_hash_for(CAT, [{"slug": "a"}, {"slug": "b"}])
    assert h1 != h2


def test_hash_change_si_categorie_differente():
    tools = [{"slug": "a"}]
    autre = {"slug": "automation", "name": "Automation"}
    assert b6_seo.content_hash_for(CAT, tools) != b6_seo.content_hash_for(autre, tools)


def test_hash_inclut_la_version_de_prompt():
    # Le prefixe PROMPT_VERSION doit faire partie du materiau hashe.
    assert b6_seo.PROMPT_VERSION  # existe
    import hashlib
    tools = [{"slug": "a"}]
    parts = (b6_seo.PROMPT_VERSION + CAT["slug"] + CAT["name"] + "a")
    attendu = hashlib.sha256(parts.encode("utf-8")).hexdigest()
    assert b6_seo.content_hash_for(CAT, tools) == attendu


# --------------------------------------------------------------------------
# validate_category_content : garde-fou anti-mince + fallbacks
# --------------------------------------------------------------------------

def test_contenu_mince_detecte():
    out = {"intro_md": "Trop court.", "seo_title": "T", "seo_description": "D"}
    _, is_thin = b6_seo.validate_category_content(out, CAT)
    assert is_thin is True


def test_contenu_riche_non_mince():
    intro = "Ce regroupement couvre des outils utiles. " * 8  # > 200 car
    out = {"intro_md": intro, "seo_title": "Titre", "seo_description": "Desc"}
    fields, is_thin = b6_seo.validate_category_content(out, CAT)
    assert is_thin is False
    assert fields["seo_intro_md"]
    assert fields["seo_title"] == "Titre"


def test_seuil_min_desc_exact_non_mince():
    intro = "a" * b6_seo.MIN_DESC
    _, is_thin = b6_seo.validate_category_content({"intro_md": intro}, CAT)
    assert is_thin is False


def test_intro_tronquee_a_max_desc():
    intro = "a" * (b6_seo.MAX_DESC + 500)
    fields, _ = b6_seo.validate_category_content({"intro_md": intro}, CAT)
    assert len(fields["seo_intro_md"]) <= b6_seo.MAX_DESC


def test_title_fallback_quand_absent():
    intro = "a" * b6_seo.MIN_DESC
    fields, _ = b6_seo.validate_category_content({"intro_md": intro}, CAT)
    assert fields["seo_title"] == "Best AI Writing Tools"


def test_title_tronque_a_60():
    intro = "a" * b6_seo.MIN_DESC
    out = {"intro_md": intro, "seo_title": "Z" * 200}
    fields, _ = b6_seo.validate_category_content(out, CAT)
    assert len(fields["seo_title"]) <= b6_seo.MAX_TITLE


def test_seo_description_fallback_et_tronquee():
    intro = "b" * 400  # riche
    out = {"intro_md": intro}  # pas de seo_description
    fields, _ = b6_seo.validate_category_content(out, CAT)
    assert fields["seo_description"]
    assert len(fields["seo_description"]) <= b6_seo.MAX_SEO_DESC
