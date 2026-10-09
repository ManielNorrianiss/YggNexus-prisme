# -*- coding: utf-8 -*-
"""
Tests purs des raisons d'alternatives de b5_liens.py : gabarit sans LLM
(--sans-llm), filtre anti-texte-debogage (meme regex que le frontend,
ToolCard.tsx : /semantic similarity|cosine/i), et generation LLM avec
repli propre sur le gabarit en cas d'erreur. Aucun reseau.
"""
import io
import re
from contextlib import redirect_stdout

import b5_liens as b5

FILTRE_FRONTEND = re.compile(r"semantic similarity|cosine", re.IGNORECASE)

TOOL = {"name": "Acme Writer", "pricing": "freemium", "application_category": "BusinessApplication"}
ALT_MEME_CATEGORIE = {"name": "Scribe AI", "pricing": "open_source", "application_category": "BusinessApplication"}
ALT_AUTRE_CATEGORIE = {"name": "PixelGen", "pricing": "paid", "application_category": "MultimediaApplication"}


# ---------------------------------------------------------------------------
# raison_gabarit : jamais de texte cosinus, toujours <= 140 caracteres
# ---------------------------------------------------------------------------

def test_raison_gabarit_respecte_la_longueur_max():
    r = b5.raison_gabarit(TOOL, ALT_MEME_CATEGORIE)
    assert len(r) <= b5.MAX_LEN_RAISON
    r2 = b5.raison_gabarit(TOOL, ALT_AUTRE_CATEGORIE)
    assert len(r2) <= b5.MAX_LEN_RAISON


def test_raison_gabarit_passe_le_filtre_frontend():
    for alt in (ALT_MEME_CATEGORIE, ALT_AUTRE_CATEGORIE):
        r = b5.raison_gabarit(TOOL, alt)
        assert not FILTRE_FRONTEND.search(r), f"raison rejetee par le filtre frontend: {r!r}"


def test_raison_gabarit_mentionne_pricing_different():
    r = b5.raison_gabarit(TOOL, ALT_MEME_CATEGORIE)
    assert "freemium" in r
    assert "open source" in r


def test_raison_gabarit_meme_categorie_dit_both_are():
    r = b5.raison_gabarit(TOOL, ALT_MEME_CATEGORIE)
    assert r.startswith("Both are")


def test_raison_gabarit_categorie_differente_ne_dit_pas_both_are():
    r = b5.raison_gabarit(TOOL, ALT_AUTRE_CATEGORIE)
    assert not r.startswith("Both are")


# ---------------------------------------------------------------------------
# generer_raison : --sans-llm force le gabarit, jamais d'appel LLM
# ---------------------------------------------------------------------------

def test_generer_raison_sans_llm_utilise_le_gabarit():
    appele = []

    def fn_gen_espion(prompt, system, modele=None, timeout=60, _appel=None):
        appele.append(True)
        return {"reason": "ne devrait jamais etre utilise"}

    r = b5.generer_raison(fn_gen_espion, TOOL, ALT_MEME_CATEGORIE, "fake-model", sans_llm=True)
    assert appele == []
    assert r == b5.raison_gabarit(TOOL, ALT_MEME_CATEGORIE)


def test_generer_raison_fn_gen_none_utilise_le_gabarit():
    r = b5.generer_raison(None, TOOL, ALT_MEME_CATEGORIE, "fake-model", sans_llm=False)
    assert r == b5.raison_gabarit(TOOL, ALT_MEME_CATEGORIE)


# ---------------------------------------------------------------------------
# raison_llm / generer_raison : repli propre sur le gabarit si le LLM echoue
# ou renvoie un texte contenant un terme interdit
# ---------------------------------------------------------------------------

def test_generer_raison_llm_ok_retourne_la_phrase_llm():
    def fn_gen(prompt, system, modele=None, timeout=60, _appel=None):
        return {"reason": "Scribe AI is open source while Acme Writer is freemium."}

    r = b5.generer_raison(fn_gen, TOOL, ALT_MEME_CATEGORIE, "fake-model", sans_llm=False)
    assert r == "Scribe AI is open source while Acme Writer is freemium."


def test_generer_raison_llm_echec_retombe_sur_gabarit():
    from llm_local import LLMError

    def fn_gen(prompt, system, modele=None, timeout=60, _appel=None):
        raise LLMError("Ollama injoignable")

    r = b5.generer_raison(fn_gen, TOOL, ALT_MEME_CATEGORIE, "fake-model", sans_llm=False)
    assert r == b5.raison_gabarit(TOOL, ALT_MEME_CATEGORIE)


def test_generer_raison_llm_terme_interdit_retombe_sur_gabarit():
    """Si le LLM produit malgre tout un texte contenant 'cosine' ou
    'semantic similarity', on ne le laisse jamais passer -- repli gabarit."""
    def fn_gen(prompt, system, modele=None, timeout=60, _appel=None):
        return {"reason": "High cosine similarity between these two tools."}

    r = b5.generer_raison(fn_gen, TOOL, ALT_MEME_CATEGORIE, "fake-model", sans_llm=False)
    assert r == b5.raison_gabarit(TOOL, ALT_MEME_CATEGORIE)
    assert not FILTRE_FRONTEND.search(r)


def test_generer_raison_llm_sortie_invalide_retombe_sur_gabarit():
    def fn_gen(prompt, system, modele=None, timeout=60, _appel=None):
        return {"pas_la_bonne_cle": "x"}

    r = b5.generer_raison(fn_gen, TOOL, ALT_MEME_CATEGORIE, "fake-model", sans_llm=False)
    assert r == b5.raison_gabarit(TOOL, ALT_MEME_CATEGORIE)


# ---------------------------------------------------------------------------
# generer_raisons_paire : parallelisation (ThreadPoolExecutor), toutes les
# paires recoivent une raison
# ---------------------------------------------------------------------------

def test_generer_raisons_paire_couvre_toutes_les_paires_en_parallele():
    tools_index = {1: TOOL, 2: ALT_MEME_CATEGORIE, 3: ALT_AUTRE_CATEGORIE}
    paires = [(1, 2), (1, 3)]

    resultat = b5.generer_raisons_paire(None, tools_index, paires, None,
                                         sans_llm=True, workers=2)

    assert set(resultat.keys()) == set(paires)
    for raison in resultat.values():
        assert isinstance(raison, str)
        assert len(raison) <= b5.MAX_LEN_RAISON
        assert not FILTRE_FRONTEND.search(raison)


def test_generer_raisons_paire_liste_vide_retourne_dict_vide():
    resultat = b5.generer_raisons_paire(None, {}, [], None, sans_llm=True, workers=4)
    assert resultat == {}


# ---------------------------------------------------------------------------
# write_alternatives (dry-run) : verifie que la raison utilisee vient bien
# du dict raisons (pas de texte cosinus en repli silencieux). Capture stdout
# via redirect_stdout (fonctionne aussi bien sous pytest que sous le
# harnais stdlib check_no_pytest.py -- pas besoin de la fixture capsys).
# ---------------------------------------------------------------------------

def test_write_alternatives_dry_run_utilise_les_raisons_fournies():
    alts = [(2, "scribe-ai", 0.71)]
    raisons = {(1, 2): "Both are business tools, both freemium."}

    buf = io.StringIO()
    with redirect_stdout(buf):
        n = b5.write_alternatives(None, 1, "acme-writer", alts, dry_run=True, raisons=raisons)
    assert n == 1

    sortie = buf.getvalue()
    assert "Both are business tools, both freemium." in sortie
    assert not FILTRE_FRONTEND.search(sortie.split("reason=", 1)[1])
