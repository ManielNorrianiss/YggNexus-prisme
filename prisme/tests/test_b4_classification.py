# -*- coding: utf-8 -*-
"""
Tests purs de la validation de b4_classification (validate_classification),
plus taxonomy_slugs et content_hash_for. Aucun acces reseau ni DB.
"""
import b4_classification as b4

VALID = {"ai-writing", "automation", "ai-images", "ai-audio",
         "data-scraping", "productivity", "no-code"}
THRESHOLD = 0.45


def test_cas_nominal():
    out = {"primary": "ai-writing", "secondary": ["automation"], "confidence": 0.82}
    primary, secondary, conf, unclass = b4.validate_classification(out, VALID, THRESHOLD)
    assert primary == "ai-writing"
    assert secondary == ["automation"]
    assert conf == 0.82
    assert unclass is False


def test_primary_invalide_devient_none_et_unclassified():
    out = {"primary": "inexistant", "secondary": [], "confidence": 0.9}
    primary, _, _, unclass = b4.validate_classification(out, VALID, THRESHOLD)
    assert primary is None
    assert unclass is True


def test_confidence_sous_seuil_unclassified():
    out = {"primary": "ai-writing", "secondary": [], "confidence": 0.30}
    primary, _, _, unclass = b4.validate_classification(out, VALID, THRESHOLD)
    assert primary == "ai-writing"
    assert unclass is True


def test_confidence_clampee_haut():
    out = {"primary": "ai-writing", "secondary": [], "confidence": 5}
    _, _, conf, _ = b4.validate_classification(out, VALID, THRESHOLD)
    assert conf == 1.0


def test_confidence_clampee_bas():
    out = {"primary": "ai-writing", "secondary": [], "confidence": -2}
    _, _, conf, _ = b4.validate_classification(out, VALID, THRESHOLD)
    assert conf == 0.0


def test_confidence_non_numerique_devient_zero():
    out = {"primary": "ai-writing", "secondary": [], "confidence": "haut"}
    _, _, conf, unclass = b4.validate_classification(out, VALID, THRESHOLD)
    assert conf == 0.0
    assert unclass is True  # 0 < seuil


def test_secondary_filtre_invalides_et_doublon_primary():
    out = {"primary": "ai-writing",
           "secondary": ["automation", "bidon", "ai-writing"],
           "confidence": 0.8}
    _, secondary, _, _ = b4.validate_classification(out, VALID, THRESHOLD)
    assert secondary == ["automation"]  # bidon vire, ai-writing == primary vire


def test_secondary_max_2():
    out = {"primary": "ai-writing",
           "secondary": ["automation", "ai-images", "no-code"],
           "confidence": 0.8}
    _, secondary, _, _ = b4.validate_classification(out, VALID, THRESHOLD)
    assert len(secondary) == 2
    assert secondary == ["automation", "ai-images"]


def test_secondary_dedup_garde_ordre():
    out = {"primary": "ai-writing",
           "secondary": ["automation", "automation", "no-code"],
           "confidence": 0.8}
    _, secondary, _, _ = b4.validate_classification(out, VALID, THRESHOLD)
    assert secondary == ["automation", "no-code"]


def test_secondary_non_liste_devient_vide():
    out = {"primary": "ai-writing", "secondary": "automation", "confidence": 0.8}
    _, secondary, _, _ = b4.validate_classification(out, VALID, THRESHOLD)
    assert secondary == []


def test_primary_none_explicite():
    out = {"primary": None, "secondary": [], "confidence": 0.9}
    primary, _, _, unclass = b4.validate_classification(out, VALID, THRESHOLD)
    assert primary is None
    assert unclass is True


def test_champs_manquants_defaut_surs():
    primary, secondary, conf, unclass = b4.validate_classification({}, VALID, THRESHOLD)
    assert primary is None
    assert secondary == []
    assert conf == 0.0
    assert unclass is True


# --- helpers ---

def test_taxonomy_slugs():
    taxo = [{"slug": "ai-writing", "name": "x", "description": "d"},
            {"slug": "automation", "name": "y", "description": "d"}]
    assert b4.taxonomy_slugs(taxo) == {"ai-writing", "automation"}


def test_content_hash_deterministe_et_sensible():
    raw = {"name": "Demo"}
    enr = {"short_desc": "s", "description_md": "d", "application_category": "c"}
    h1 = b4.content_hash_for(raw, enr, "v1")
    h2 = b4.content_hash_for(raw, enr, "v1")
    h3 = b4.content_hash_for(raw, enr, "v2")  # version differente
    assert h1 == h2
    assert h1 != h3
