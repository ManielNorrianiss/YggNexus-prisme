# -*- coding: utf-8 -*-
"""
llm_local.py - Module reutilisable Ollama (generation JSON + embeddings).

Routage deux niveaux :
    - role "masse"   -> MODELE_GEN (qwen2.5:7b-instruct) : volume, B2/B5 gabarits.
    - role "arbitre"  -> MODELE_ARBITRE (qwen2.5:14b-instruct) : jugement fin,
      B2b (juge de qualite) et B5 (raisons d'alternatives) par defaut.

Le modele arbitre (14b) N'EST PAS tire par defaut sur une machine Ollama
fraiche. Avant le premier usage reel, executer :

    ollama pull qwen2.5:14b-instruct

Si le modele est absent, Ollama repond une erreur "model not found" (HTTP 404).
generer_json() la remonte comme LLMError. Le code appelant (b2b_juge.py) DOIT
attraper ce cas et retomber proprement sur MODELE_GEN, en journalisant un
evenement run_log de type "modele_absent_repli" (voir b2b_juge.py::generer_avec_repli).
"""
import json
import os
import time
import urllib.request
import urllib.error

OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MODELE_GEN = "qwen2.5:7b-instruct"
MODELE_ARBITRE = os.environ.get("PRISME_MODELE_ARBITRE", "qwen2.5:14b-instruct")
MODELE_EMBED = "nomic-embed-text"
EMBED_DIM = 768

ROLES = {
    "masse": MODELE_GEN,
    "arbitre": MODELE_ARBITRE,
}


def modele_pour(role):
    """
    Retourne le nom de modele Ollama associe a un role logique.

    Roles connus :
        "masse"   -> MODELE_GEN (volume, cout faible)
        "arbitre" -> MODELE_ARBITRE (jugement plus fin, plus lent/couteux)

    Role inconnu -> retombe sur MODELE_GEN (comportement le plus sur).
    """
    return ROLES.get(role, MODELE_GEN)


class LLMError(Exception):
    """Erreur retournee par les appels Ollama."""
    pass


def modele_absent(exc):
    """
    Heuristique : determine si une LLMError correspond a un modele Ollama
    absent (pas tire localement -- HTTP 404 "model ... not found").
    Utilisee par b2b_juge.py pour declencher le repli MODELE_GEN.
    """
    msg = str(exc).lower()
    return "not found" in msg or "404" in msg


def _appel_http_defaut(url, payload, timeout):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _avec_reprise(fn_appel, url, payload, timeout, retries, delai_base):
    """
    Execute fn_appel(url, payload, timeout) avec reprise et attente
    exponentielle en cas d'echec. retries = nombre de tentatives
    SUPPLEMENTAIRES apres le premier essai (donc retries=2 => 3 essais max).
    Leve la derniere exception rencontree si tous les essais echouent.
    """
    derniere_exc = None
    nb_essais = max(1, retries + 1)
    for tentative in range(nb_essais):
        try:
            return fn_appel(url, payload, timeout)
        except Exception as e:
            derniere_exc = e
            if tentative < nb_essais - 1:
                attente = delai_base * (2 ** tentative)
                time.sleep(attente)
            else:
                raise
    # Ne devrait pas etre atteint (raise ci-dessus au dernier essai).
    raise derniere_exc


def generer_json(prompt, system, modele=None, timeout=120, _appel=None, retries=2):
    """
    Appelle Ollama en mode generation JSON strict.
    Retourne un dict parse depuis la cle "response".
    Leve LLMError si Ollama est injoignable ou si le JSON est casse.

    Parametres:
        prompt  : str  - prompt utilisateur
        system  : str  - system prompt
        modele  : str  - override du modele (defaut MODELE_GEN)
        timeout : int  - timeout HTTP en secondes
        _appel  : callable optionnel pour injection de test
                  signature: (url, payload, timeout) -> dict
        retries : int  - nombre de tentatives supplementaires en cas
                  d'echec reseau, avec attente exponentielle (defaut 2)
    """
    m = modele or MODELE_GEN
    payload = {
        "model": m,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.0},
    }
    fn = _appel or _appel_http_defaut
    url = f"{OLLAMA}/api/generate"
    try:
        raw = _avec_reprise(fn, url, payload, timeout, retries, delai_base=1.0)
    except urllib.error.URLError as e:
        raise LLMError(f"Ollama injoignable ({url}): {e}") from e
    except Exception as e:
        raise LLMError(f"Erreur appel Ollama: {e}") from e

    response_str = raw.get("response", "")
    if not response_str:
        raise LLMError("Ollama a retourne une reponse vide.")
    try:
        return json.loads(response_str)
    except json.JSONDecodeError as e:
        raise LLMError(f"JSON casse dans la reponse Ollama: {e}\nReponse brute: {response_str[:300]}") from e


def embed(texte, modele=None, timeout=60, _appel=None, retries=2):
    """
    Calcule l'embedding d'un texte via Ollama.
    Retourne une liste de floats (dim EMBED_DIM).
    Leve LLMError en cas d'echec.

    Parametres:
        texte   : str  - texte a encoder
        modele  : str  - override du modele (defaut MODELE_EMBED)
        timeout : int  - timeout HTTP en secondes
        _appel  : callable optionnel pour injection de test
        retries : int  - nombre de tentatives supplementaires en cas
                  d'echec reseau, avec attente exponentielle (defaut 2)
    """
    m = modele or MODELE_EMBED
    payload = {"model": m, "prompt": texte}
    fn = _appel or _appel_http_defaut
    url = f"{OLLAMA}/api/embeddings"
    try:
        raw = _avec_reprise(fn, url, payload, timeout, retries, delai_base=1.0)
    except urllib.error.URLError as e:
        raise LLMError(f"Ollama injoignable ({url}): {e}") from e
    except Exception as e:
        raise LLMError(f"Erreur appel Ollama embed: {e}") from e

    vec = raw.get("embedding")
    if not vec:
        raise LLMError("Ollama a retourne un embedding vide.")
    return vec
