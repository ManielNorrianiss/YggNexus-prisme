# -*- coding: utf-8 -*-
"""
Tests purs de l'auto-correction b2_enrichissement.py : quand la sortie LLM
est invalide (JSON casse ou echec de check_sortie_llm), un seul re-prompt
est tente avec le message d'erreur precis + la sortie fautive tronquee.
Aucun acces reseau -- injection de fonctions fn_gen fictives.
"""
import b2_enrichissement as b2


RAW = {"slug": "tool-x", "name": "Tool X", "raw_title": "Tool X - site",
       "raw_meta_desc": "desc x", "raw_text": "some text x"}


def _chash():
    return b2.content_hash_for(RAW)


# ---------------------------------------------------------------------------
# check_sortie_llm : validation stricte
# ---------------------------------------------------------------------------

def test_check_sortie_llm_accepte_sortie_valide():
    assert b2.check_sortie_llm(b2.fake_llm("", "")) is None


def test_check_sortie_llm_detecte_cles_manquantes():
    d = b2.fake_llm("", "")
    del d["pros"]
    msg = b2.check_sortie_llm(d)
    assert msg is not None
    assert "pros" in msg


def test_check_sortie_llm_detecte_pricing_hors_enum():
    d = b2.fake_llm("", "")
    d["pricing"] = "gratuit-ish"
    msg = b2.check_sortie_llm(d)
    assert msg is not None
    assert "pricing" in msg


def test_check_sortie_llm_detecte_type_non_dict():
    msg = b2.check_sortie_llm("pas un dict")
    assert msg is not None


# ---------------------------------------------------------------------------
# enrich_one : auto-correction (echoue puis reussit au re-prompt)
# ---------------------------------------------------------------------------

def test_enrich_one_reprend_avec_succes_apres_json_invalide():
    """Premier appel renvoie une sortie invalide (cle manquante), le
    deuxieme (re-prompt) renvoie une sortie valide -> le resultat final
    doit etre OK, et les evenements journalises doivent etre
    json_invalide puis reprise_reussie."""
    appels = {"n": 0}
    evenements = []

    def fn_gen(prompt, system, modele=None, timeout=120, _appel=None):
        appels["n"] += 1
        if appels["n"] == 1:
            d = b2.fake_llm(prompt, system)
            del d["cons"]  # sortie invalide : cle manquante
            return d
        # 2e appel (reprise) : sortie valide, et le prompt doit contenir
        # le message d'erreur + un extrait de la sortie fautive
        assert "Ta reponse precedente etait invalide" in prompt
        assert "cons" in prompt
        return b2.fake_llm(prompt, system)

    def log_fn(run_id, etape, type_evenement, detail, slug=None, niveau="erreur"):
        evenements.append((etape, type_evenement, niveau, slug))

    res = b2.enrich_one(RAW, _chash(), fn_gen, b2.fake_embed, model="fake-model",
                         run_id="run-t1", log_fn=log_fn)

    assert res["ok"] is True
    assert appels["n"] == 2
    types = [e[1] for e in evenements]
    assert "json_invalide" in types
    assert "reprise_reussie" in types
    assert types.index("json_invalide") < types.index("reprise_reussie")


def test_enrich_one_echec_final_si_reprise_echoue_aussi():
    """Les deux appels (initial + reprise) renvoient une sortie invalide
    -> l'echec final est retourne (ok=False), sans 'reprise_reussie'."""
    evenements = []

    def fn_gen(prompt, system, modele=None, timeout=120, _appel=None):
        d = b2.fake_llm(prompt, system)
        del d["faq"]  # toujours invalide
        return d

    def log_fn(run_id, etape, type_evenement, detail, slug=None, niveau="erreur"):
        evenements.append((etape, type_evenement, niveau, slug))

    res = b2.enrich_one(RAW, _chash(), fn_gen, b2.fake_embed, model="fake-model",
                         run_id="run-t2", log_fn=log_fn)

    assert res["ok"] is False
    assert "apres reprise" in res["error"]
    types = [e[1] for e in evenements]
    assert types.count("json_invalide") == 2  # une fois initiale, une fois finale
    assert "reprise_reussie" not in types


def test_enrich_one_sortie_valide_du_premier_coup_ne_declenche_pas_de_reprise():
    appels = {"n": 0}

    def fn_gen(prompt, system, modele=None, timeout=120, _appel=None):
        appels["n"] += 1
        return b2.fake_llm(prompt, system)

    res = b2.enrich_one(RAW, _chash(), fn_gen, b2.fake_embed, model="fake-model")
    assert res["ok"] is True
    assert appels["n"] == 1


# ---------------------------------------------------------------------------
# run_enrichment : quarantaine apres 3 echecs (via staging monkeypatch)
# ---------------------------------------------------------------------------

def test_run_enrichment_met_en_quarantaine_apres_3_echecs(monkeypatch):
    """Un slug qui echoue definitivement (LLM en echec permanent) doit
    declencher increment_echecs puis mettre_en_quarantaine des que le
    compte atteint MAX_ECHECS_AVANT_QUARANTAINE, avec un evenement
    'quarantaine' journalise."""
    compte_echecs = {"tool-fail": 0}
    quarantaines = []
    evenements = []

    def fake_increment_echecs(slug, path=None):
        compte_echecs[slug] = compte_echecs.get(slug, 0) + 1
        return compte_echecs[slug]

    def fake_mettre_en_quarantaine(slug, path=None):
        quarantaines.append(slug)

    monkeypatch.setattr(b2.staging, "increment_echecs", fake_increment_echecs)
    monkeypatch.setattr(b2.staging, "mettre_en_quarantaine", fake_mettre_en_quarantaine)

    def fn_gen_echec_permanent(prompt, system, modele=None, timeout=120, _appel=None):
        raise b2.LLMError("echec simule permanent")

    def log_fn(run_id, etape, type_evenement, detail, slug=None, niveau="erreur"):
        evenements.append((type_evenement, slug))

    raw = {"slug": "tool-fail", "name": "Tool Fail", "raw_title": "t",
           "raw_meta_desc": "d", "raw_text": "x"}
    to_enrich = [(raw, b2.content_hash_for(raw))] * 3  # simule 3 runs successifs

    for _, (r, ch) in enumerate(to_enrich):
        nb_ok, nb_error = b2.run_enrichment(
            [(r, ch)], fn_gen_echec_permanent, b2.fake_embed, model="fake-model",
            workers=1, dry_run=False, run_id="run-q", log_fn=log_fn,
        )
        assert nb_ok == 0
        assert nb_error == 1

    assert compte_echecs["tool-fail"] == 3
    assert quarantaines == ["tool-fail"]
    types_quarantaine = [t for (t, s) in evenements if t == "quarantaine"]
    assert len(types_quarantaine) == 1


def test_run_enrichment_dry_run_n_incremente_jamais_les_echecs(monkeypatch):
    """En --dry-run, meme un echec LLM ne doit jamais toucher a
    staging.increment_echecs / mettre_en_quarantaine."""
    appelee = {"increment": False, "quarantaine": False}

    def fake_increment_echecs(slug, path=None):
        appelee["increment"] = True
        return 1

    def fake_mettre_en_quarantaine(slug, path=None):
        appelee["quarantaine"] = True

    monkeypatch.setattr(b2.staging, "increment_echecs", fake_increment_echecs)
    monkeypatch.setattr(b2.staging, "mettre_en_quarantaine", fake_mettre_en_quarantaine)

    def fn_gen_echec(prompt, system, modele=None, timeout=120, _appel=None):
        raise b2.LLMError("echec simule")

    nb_ok, nb_error = b2.run_enrichment(
        [(RAW, _chash())], fn_gen_echec, b2.fake_embed, model="fake-model",
        workers=1, dry_run=True,
    )
    assert nb_ok == 0
    assert nb_error == 1
    assert appelee["increment"] is False
    assert appelee["quarantaine"] is False


# ---------------------------------------------------------------------------
# Derivation deterministe de nom depuis domaine (avant l'appel LLM)
# ---------------------------------------------------------------------------

def test_nom_propre_depuis_domaine_retire_tld_et_capitalise():
    assert b2.nom_propre_depuis_domaine("https://acme-tool.io") == "Acme Tool"


def test_nom_propre_depuis_domaine_gere_www_et_sous_domaines():
    assert b2.nom_propre_depuis_domaine("https://www.my-cool-app.com") == "My Cool App"


def test_nom_propre_depuis_domaine_url_vide_retourne_chaine_vide():
    assert b2.nom_propre_depuis_domaine("") == ""


def test_nom_ressemble_a_un_slug_domaine_detecte_slug_brut():
    assert b2.nom_ressemble_a_un_slug_domaine("acmetool-io", "https://acmetool.io") is True
    assert b2.nom_ressemble_a_un_slug_domaine("my-tool-com", "https://example.org") is True


def test_nom_ressemble_a_un_slug_domaine_accepte_vrai_nom():
    assert b2.nom_ressemble_a_un_slug_domaine("Acme Tool", "https://acme-tool.io") is False


def test_nom_ressemble_a_un_slug_domaine_nom_vide_est_incertain():
    assert b2.nom_ressemble_a_un_slug_domaine("", "https://acme-tool.io") is True


def test_nom_corrige_si_besoin_derive_quand_name_manque():
    raw = {"slug": "x", "website_url": "https://acme-tool.io"}
    nom, incertain = b2.nom_corrige_si_besoin(raw)
    assert nom == "Acme Tool"
    assert incertain is True


def test_nom_corrige_si_besoin_derive_quand_name_est_un_slug_domaine():
    raw = {"slug": "x", "name": "acmetool-io", "website_url": "https://acmetool.io"}
    nom, incertain = b2.nom_corrige_si_besoin(raw)
    assert nom == "Acmetool"
    assert incertain is True


def test_nom_corrige_si_besoin_garde_un_vrai_nom_tel_quel():
    raw = {"slug": "x", "name": "Acme Tool", "website_url": "https://acme-tool.io"}
    nom, incertain = b2.nom_corrige_si_besoin(raw)
    assert nom == "Acme Tool"
    assert incertain is False


def test_build_prompt_signale_le_nom_incertain():
    raw = {"slug": "x", "name": "acmetool-io", "website_url": "https://acmetool.io",
           "raw_title": "t", "raw_meta_desc": "d", "raw_text": "txt"}
    prompt = b2.build_prompt(raw)
    assert "auto-derived from the domain" in prompt
    assert "Tool name: Acmetool" in prompt


def test_build_prompt_ne_signale_rien_pour_un_nom_fiable():
    raw = {"slug": "x", "name": "Acme Tool", "website_url": "https://acme-tool.io",
           "raw_title": "t", "raw_meta_desc": "d", "raw_text": "txt"}
    prompt = b2.build_prompt(raw)
    assert "auto-derived from the domain" not in prompt
