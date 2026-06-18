# -*- coding: utf-8 -*-
"""
llm_local.py - Module reutilisable Ollama (generation JSON + embeddings).
"""
import json
import urllib.request
import urllib.error

OLLAMA = "http://127.0.0.1:11434"
MODELE_GEN = "qwen2.5:7b-instruct"
MODELE_EMBED = "nomic-embed-text"
EMBED_DIM = 768


class LLMError(Exception):
    """Erreur retournee par les appels Ollama."""
    pass


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


def generer_json(prompt, system, modele=None, timeout=120, _appel=None):
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
        raw = fn(url, payload, timeout)
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


def embed(texte, modele=None, timeout=60, _appel=None):
    """
    Calcule l'embedding d'un texte via Ollama.
    Retourne une liste de floats (dim EMBED_DIM).
    Leve LLMError en cas d'echec.

    Parametres:
        texte   : str  - texte a encoder
        modele  : str  - override du modele (defaut MODELE_EMBED)
        timeout : int  - timeout HTTP en secondes
        _appel  : callable optionnel pour injection de test
    """
    m = modele or MODELE_EMBED
    payload = {"model": m, "prompt": texte}
    fn = _appel or _appel_http_defaut
    url = f"{OLLAMA}/api/embeddings"
    try:
        raw = fn(url, payload, timeout)
    except urllib.error.URLError as e:
        raise LLMError(f"Ollama injoignable ({url}): {e}") from e
    except Exception as e:
        raise LLMError(f"Erreur appel Ollama embed: {e}") from e

    vec = raw.get("embedding")
    if not vec:
        raise LLMError("Ollama a retourne un embedding vide.")
    return vec
