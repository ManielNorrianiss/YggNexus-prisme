# -*- coding: utf-8 -*-
"""
Tests purs du routage de modele dans llm_local.py : modele_pour(role) et
la detection modele_absent(exc). Aucun reseau.
"""
import llm_local as ll


def test_modele_pour_masse_retourne_modele_gen():
    assert ll.modele_pour("masse") == ll.MODELE_GEN


def test_modele_pour_arbitre_retourne_modele_arbitre():
    assert ll.modele_pour("arbitre") == ll.MODELE_ARBITRE


def test_modele_pour_role_inconnu_retombe_sur_modele_gen():
    assert ll.modele_pour("role-invente") == ll.MODELE_GEN


def test_modele_arbitre_par_defaut_est_14b():
    # Valeur par defaut documentee (peut etre overridee par
    # PRISME_MODELE_ARBITRE, mais le defaut du module doit rester 14b).
    assert "14b" in ll.MODELE_ARBITRE


def test_modele_absent_detecte_erreur_not_found():
    e = ll.LLMError("Erreur appel Ollama: model 'qwen2.5:14b-instruct' not found, try pulling it first")
    assert ll.modele_absent(e) is True


def test_modele_absent_detecte_erreur_404():
    e = ll.LLMError("Erreur appel Ollama: HTTP Error 404: Not Found")
    assert ll.modele_absent(e) is True


def test_modele_absent_faux_pour_autre_erreur():
    e = ll.LLMError("Ollama injoignable (http://127.0.0.1:11434/api/generate): timed out")
    assert ll.modele_absent(e) is False
