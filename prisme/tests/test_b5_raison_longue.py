"""B5 : une raison trop longue garde une phrase entiere, et --exclure ecarte
les paires qui touchent un slug donne. Aucun reseau."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import b5_liens  # noqa: E402


LONG = {"name": "Algorithmia AI Model Deployment", "pricing": "unknown", "categorie_site": ""}
OPENAI = {"name": "OpenAI", "pricing": "freemium", "categorie_site": "ai-writing"}
WORKATO = {"name": "Workato", "pricing": "paid", "categorie_site": "automation"}


def _finit_proprement(phrase):
    dernier = phrase.rstrip(".").split()[-1].lower()
    return dernier not in ("while", "of", "is", "alors", "que", "prix", "est", "à")


def test_raison_anglaise_trop_longue_garde_la_phrase_de_base():
    raison = b5_liens.raison_gabarit(OPENAI, LONG)
    assert raison == "Algorithmia AI Model Deployment is an alternative to OpenAI (AI writing)."
    assert len(raison) <= b5_liens.MAX_LEN_RAISON
    assert _finit_proprement(raison)


def test_raison_anglaise_trop_longue_avec_categorie_de_l_alternative():
    raison = b5_liens.raison_gabarit(LONG, WORKATO)
    assert raison == "Workato is an automation alternative to Algorithmia AI Model Deployment."
    assert _finit_proprement(raison)


def test_raison_francaise_trop_longue_garde_la_phrase_de_base():
    raison = b5_liens.raison_gabarit_fr(LONG, WORKATO)
    assert raison.endswith("est une alternative à Algorithmia AI Model Deployment.")
    assert len(raison) <= b5_liens.MAX_LEN_RAISON_FR
    assert _finit_proprement(raison)


def test_raison_courte_garde_la_proposition_sur_le_prix():
    a = {"name": "Mem", "pricing": "paid", "categorie_site": "productivity"}
    b = {"name": "Notion", "pricing": "freemium", "categorie_site": "productivity"}
    assert b5_liens.raison_gabarit(b, a) == "Both are productivity tools; Mem is paid while Notion is freemium."


def test_exclure_ecarte_les_paires_qui_touchent_un_slug():
    nouvelles = [
        (1, "portkey", 2, "ciodive", 0.73),
        (3, "huyenchip", 4, "bbycroft", 0.76),
        (5, "pika", 6, "krea", 0.77),
    ]
    gardees, nb = b5_liens.filtrer_exclues(nouvelles, ["ciodive", " huyenchip "])
    assert gardees == [(5, "pika", 6, "krea", 0.77)]
    assert nb == 2


def test_exclure_vide_ne_change_rien():
    nouvelles = [(5, "pika", 6, "krea", 0.77)]
    assert b5_liens.filtrer_exclues(nouvelles, [""]) == (nouvelles, 0)
    assert b5_liens.filtrer_exclues(nouvelles, None) == (nouvelles, 0)
