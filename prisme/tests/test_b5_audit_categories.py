# -*- coding: utf-8 -*-
"""Essais de b5_audit_categories.py : verdicts, propositions, regle. Aucun reseau."""
import b5_audit_categories as a


def outil(slug, cat, modalite=(), tags=(), desc="", name=None):
    return {
        "slug": slug, "name": name or slug, "short_desc": desc,
        "application_category": cat,
        "facets": {"modality": list(modalite), "function": [], "audience": []},
        "tags": [{"slug": t, "label": t} for t in tags],
    }


def test_label_gabarit_copie_fidele():
    assert a.label_gabarit("MultimediaApplication") == "multimedia"
    assert a.label_gabarit("WebApplication") == "web"
    assert a.label_gabarit("") == "ai/saas"
    assert a.label_gabarit(None) == "ai/saas"


def test_generique_toujours_signale():
    v, _ = a.verdict_valeur(outil("x", "SoftwareApplication"), "ai-video")
    assert v == "generique"


def test_multimedia_vague_pour_video_fausse_pour_ecriture():
    assert a.verdict_valeur(outil("x", "MultimediaApplication"), "ai-video")[0] == "vague"
    assert a.verdict_valeur(outil("x", "MultimediaApplication"), "ai-writing")[0] == "fausse"


def test_developer_ok_avec_ai_coding_fausse_pour_audio():
    assert a.verdict_valeur(outil("x", "DeveloperApplication"), "ai-coding")[0] == "ok"
    assert a.verdict_valeur(outil("x", "DeveloperApplication"), "ai-audio")[0] == "fausse"


def test_sans_categorie_du_site_developer_plausible_si_signal():
    o = outil("x", "DeveloperApplication", modalite=["code"])
    assert a.verdict_valeur(o, None)[0] == "plausible"
    assert a.verdict_valeur(outil("y", "DeveloperApplication"), None)[0] == "fausse"


def test_proposition_prend_la_categorie_du_site_et_jamais_une_valeur_inventee():
    o = outil("pika-test", "MultimediaApplication", modalite=["video"], desc="video generator")
    prop, v, _ = a.proposer(o, "ai-video", [], {"ai-video": "AI Video"})
    assert prop["valeur_proposee"] == "ai-video"
    assert prop["confiance"] == "sur"
    assert prop["valeur_proposee"] in a.LIBELLE_SITE


def test_sans_site_et_sans_signal_rien_n_est_propose():
    o = outil("vide", "SoftwareApplication", desc="Temporary service unavailable notice.")
    prop, _, _ = a.proposer(o, None, [], {})
    assert prop["valeur_proposee"] is None
    assert prop["confiance"] == "a voir"


def test_jugement_l_emporte_sur_le_site():
    prop, _, _ = a.proposer(outil("trae", "DeveloperApplication"), "productivity", [],
                            {"ai-coding": "AI Coding"})
    assert prop["valeur_proposee"] == "ai-coding"
    assert prop["source"] == "jugement"


def test_tout_slug_propose_existe_dans_la_taxonomie():
    tax = {c["slug"] for c in a.charger_taxonomie()}
    assert set(a.LIBELLE_SITE) == tax
    for valeur, _ in a.JUGEMENT.values():
        assert valeur is None or valeur in tax
