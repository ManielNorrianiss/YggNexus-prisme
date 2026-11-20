# -*- coding: utf-8 -*-
"""
Essais de la detection SaaS (hebergement ecarte, frontieres de mots) et des
filtres de bruit du Jaccard de b5_bridges_mcp.py.
"""
import b5_bridges_mcp as b5


def rec(name, description="", website_url=None, slug=None, repo_url=None):
    return {
        "slug": slug or name.replace("/", "-").replace(".", "-"),
        "name": name,
        "description": description,
        "website_url": website_url,
        "repo_url": repo_url,
        "package_type": None,
        "package_types": [],
    }


def saas(r):
    d = b5.detect_saas(r)
    return d[0] if d else None


def test_hebergement_github_n_est_pas_un_signal():
    assert saas(rec("io.github.quelquun/outil-meteo", "Previsions meteo par ville.")) is None
    assert saas(rec("io.gitlab.quelquun/outil-meteo", "Previsions meteo.")) is None
    assert saas(rec("com.github.quelquun/outil", "Un outil.")) is None


def test_depot_github_comme_site_n_est_pas_un_signal():
    r = rec("io.github.quelquun/outil-meteo", "Previsions meteo.",
            website_url="https://github.com/quelquun/outil-meteo",
            repo_url="https://github.com/quelquun/outil-meteo")
    assert saas(r) is None
    r2 = rec("io.github.quelquun/outil-meteo", "Previsions meteo.",
             website_url="https://quelquun.github.io/outil-meteo")
    assert saas(r2) is None


def test_serveur_qui_parle_de_github_enveloppe_github():
    assert saas(rec("io.github.quelquun/github-issues", "Lister les tickets.")) == "github"
    assert saas(rec("io.github.quelquun/outil", "Manage GitHub issues and pull requests.")) == "github"
    assert saas(rec("io.github.github/github-mcp-server", "Le serveur officiel.")) == "github"
    assert saas(rec("io.github.quelquun/outil", "x", website_url="https://docs.github.com/fr")) == "github"


def test_url_de_depot_dans_la_description_n_est_pas_un_signal():
    r = rec("io.github.quelquun/outil", "Previsions meteo. Source : https://github.com/quelquun/outil")
    assert saas(r) is None


def test_proprietaire_reste_un_signal():
    assert saas(rec("com.stripe/mcp", "Paiements en ligne.")) == "stripe"
    assert saas(rec("com.stripe/mcp", "Paiements.", slug="com-stripe-mcp")) == "stripe"
    assert saas(rec("ai.adramp/google-ads", "Campagnes.")) == "google-ads"


def test_alias_au_milieu_d_un_mot_n_est_pas_reconnu():
    assert saas(rec("com.acme/slackware-tools", "Outils pour slackware.")) is None
    assert saas(rec("com.acme/notionalpoint", "Point notionnel.")) is None
    assert saas(rec("com.acme/outil", "Un hexagone lineaire et sentryless.")) is None
    assert saas(rec("com.acme/outil", "Prefixe githubber et stripeless.")) is None


def test_plateforme_d_hebergement_n_est_pas_un_signal_de_domaine():
    r = rec("com.acme/outil", "Un outil.", website_url="https://mon-outil.vercel.app")
    assert saas(r) is None
    r2 = rec("com.acme/outil", "Un outil.", website_url="https://mon-stripe-outil.vercel.app")
    assert saas(r2) == "stripe"


def test_espace_de_noms_d_une_plateforme_n_est_pas_le_proprietaire():
    assert saas(rec("app.vercel.flightsweeper-webmcp/public", "Outils publics.")) is None
    assert b5.owner_tokens("app.vercel.flightsweeper-webmcp") == ["flightsweeper", "webmcp"]
    assert saas(rec("com.acme/outil", "Search open AI training jobs.")) is None
    assert saas(rec("com.acme/outil", "Un client OpenAI pour les modeles.")) == "openai"


def test_proprietaire_sans_domaine_de_premier_niveau():
    assert b5.owner_tokens("io.github.quelquun") == ["quelquun"]
    assert b5.owner_tokens("com.stripe") == ["stripe"]
    assert b5.owner_tokens("ai.adramp") == ["adramp"]
    assert b5.owner_tokens("uk.co.mon-site") == ["mon", "site"]
    assert b5.owner_tokens("br.com") == []


# --- Bruit du Jaccard -------------------------------------------------------

def test_deux_descriptions_de_gabarit_ne_sont_pas_reliees():
    gabarit = "Live uptime verification for crawling pipelines with provenance tags and receipts"
    recs = [
        rec("com.alpha/un", gabarit),
        rec("com.beta/deux", gabarit),
        rec("com.gamma/trois", gabarit),
    ]
    ponts, _ = b5.build_bridges(recs, b5.DEFAULT_THRESHOLD)
    assert [p for p in ponts if p["relation"] == "alternative_of"] == []


def test_descriptions_identiques_d_un_meme_proprietaire_restent_comparables():
    texte = "Indexation de fichiers markdown avec recherche plein texte rapide locale"
    recs = [rec("com.alpha/un", texte), rec("com.alpha/deux", texte)]
    ponts, _ = b5.build_bridges(recs, b5.DEFAULT_THRESHOLD)
    assert len([p for p in ponts if p["relation"] == "alternative_of"]) == 1


def test_marqueur_de_retrait_ecarte_la_description():
    assert b5.is_retirement_description("Retired. Use com.x/y instead of this one.")
    assert b5.is_retirement_description("Moved to de.fibalo/mcp. Connect to the new host.")
    assert b5.is_retirement_description("Deprecated: use the new server")
    assert not b5.is_retirement_description("Handles retired employees records")
    recs = [
        rec("com.alpha/un", "Retired. Use com.alpha/nouveau for invoice scanning pipeline tools"),
        rec("com.beta/deux", "Retired. Use com.beta/nouveau for invoice scanning pipeline tools"),
    ]
    ponts, _ = b5.build_bridges(recs, b5.DEFAULT_THRESHOLD)
    assert [p for p in ponts if p["relation"] == "alternative_of"] == []


def test_description_trop_courte_ecartee():
    recs = [rec("com.alpha/un", "Weather forecast service"),
            rec("com.beta/deux", "Weather forecast service tool")]
    ponts, _ = b5.build_bridges(recs, b5.DEFAULT_THRESHOLD)
    assert [p for p in ponts if p["relation"] == "alternative_of"] == []


def test_jeton_trop_frequent_ecarte_sur_une_grande_collecte():
    n = b5.DF_MIN_CORPUS + 100
    recs = []
    for i in range(n):
        recs.append(rec("ns%d/srv%d" % (i, i),
                        "x402 usdc paid agents unique%da unique%db unique%dc unique%dd" % (i, i, i, i)))
    toks, stats = b5.filtered_description_tokens(recs)
    assert stats["jetons_trop_frequents"] >= 4
    t = toks["ns0-srv0"] if "ns0-srv0" in toks else toks[recs[0]["slug"]]
    assert "x402" not in t and "usdc" not in t and "paid" not in t
    assert "unique0a" in t


def test_vrai_couple_de_descriptions_proches_reste_relie():
    recs = [
        rec("com.alpha/un", "Convertit des documents PDF en texte brut avec extraction des tableaux"),
        rec("com.beta/deux", "Convertit des documents PDF en texte brut avec extraction des images"),
    ]
    ponts, _ = b5.build_bridges(recs, b5.DEFAULT_THRESHOLD)
    assert len([p for p in ponts if p["evidence"].startswith("desc-jaccard")]) == 1
