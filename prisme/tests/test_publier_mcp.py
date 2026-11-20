# -*- coding: utf-8 -*-
"""
Essais de publier_mcp.py : aucun reseau, l'expediteur HTTP est un faux.
"""
import json
import os
import re

import pytest

import publier_mcp as pm

CLE_SECRETE = "cle-secrete-ne-jamais-afficher-123"
ENV = {"SUPABASE_URL": "https://exemple.invalide", "SUPABASE_SERVICE_KEY": CLE_SECRETE}


def serveur(i, **sur):
    rec = {
        "slug": "serveur-%d" % i, "name": "ns/serveur-%d" % i,
        "description": "desc %d" % i, "author": "ns", "repo_url": None,
        "registry_source": "modelcontextprotocol.io",
        "package_type": "npm", "package_types": ["npm"],
        "transport": "stdio", "transports": ["stdio"], "capabilities": [],
        "hosting": "local", "version": "1.0.0", "website_url": None,
        "license": None, "stars": 3, "weekly_downloads": None,
        "quality_score": 12.5, "status": "active", "is_latest": True,
        "published_at": "2026-01-01T00:00:00Z", "package_identifier": "x",
        "package_ids": [], "remote_urls": [],
    }
    rec.update(sur)
    return rec


def pont(i, **sur):
    rec = {
        "source_type": "mcp_server", "source_id": "a-%d" % i,
        "target_type": "saas_tool", "target_id": "stripe",
        "relation": "wraps", "weight": 0.9, "evidence": "name:stripe",
    }
    rec.update(sur)
    return rec


class FauxSender:
    def __init__(self, reponses=None):
        self.appels = []
        self.reponses = list(reponses or [])

    def __call__(self, methode, url, entetes, corps):
        self.appels.append((methode, url, dict(entetes), corps))
        if methode == "GET":
            return 200, {"content-range": "0-0/42"}, ""
        if self.reponses:
            rep = self.reponses.pop(0)
            if isinstance(rep, Exception):
                raise rep
            return rep
        return 201, {}, ""

    def posts(self):
        return [a for a in self.appels if a[0] == "POST"]


def ecrire_staging(tmp_path, recs, cle="records", nom="staging.json"):
    p = tmp_path / nom
    p.write_text(json.dumps({cle: recs}), encoding="utf-8")
    return str(p)


def lancer(args, sender=None, pause=None):
    sender = sender or FauxSender()
    code = pm.main(args, sender=sender, env=ENV, pause=pause or (lambda s: None),
                   env_path=os.devnull)
    return code, sender


def test_essai_a_blanc_n_envoie_rien(tmp_path, capsys):
    chemin = ecrire_staging(tmp_path, [serveur(i) for i in range(5)])
    code, sender = lancer(["--in", chemin])
    sortie = capsys.readouterr().out
    assert code == 0
    assert sender.appels == []
    for mot in ("LUS 5", "VALIDES 5", "ECARTES 0", "LOTS 1"):
        assert mot in sortie


def test_decoupage_en_lots(tmp_path, capsys):
    chemin = ecrire_staging(tmp_path, [serveur(i) for i in range(23)])
    code, sender = lancer(["--in", chemin, "--pousser", "--lot", "10"])
    assert code == 0
    tailles = [len(json.loads(a[3])) for a in sender.posts()]
    assert tailles == [10, 10, 3]
    assert "LOTS 3" in capsys.readouterr().out


def test_en_tetes_et_url_ajouts_seulement(tmp_path):
    chemin = ecrire_staging(tmp_path, [serveur(1)])
    _, sender = lancer(["--in", chemin, "--pousser"])
    methode, url, h, _ = sender.posts()[0]
    assert url == "https://exemple.invalide/rest/v1/mcp_servers?on_conflict=slug"
    assert h["Prefer"] == "resolution=ignore-duplicates,return=minimal"
    assert h["apikey"] == CLE_SECRETE
    assert h["Authorization"] == "Bearer " + CLE_SECRETE
    assert h["Content-Type"] == "application/json"


def test_ponts_url_de_conflit(tmp_path):
    chemin = ecrire_staging(tmp_path, [pont(1)], cle="bridges")
    _, sender = lancer(["--quoi", "ponts", "--in", chemin, "--pousser"])
    url = sender.posts()[0][1]
    assert url.endswith("/rest/v1/bridges?on_conflict=source_type,source_id,target_type,target_id,relation")


def test_seules_les_methodes_post_et_get_sortent(tmp_path):
    chemin = ecrire_staging(tmp_path, [serveur(i) for i in range(12)])
    _, sender = lancer(["--in", chemin, "--pousser", "--lot", "5"])
    assert {a[0] for a in sender.appels} <= {"GET", "POST"}
    with pytest.raises(ValueError):
        pm.envoyer_http("DELE" + "TE", "http://localhost", {}, None)


def test_source_sans_methodes_destructrices():
    src = open(pm.__file__, encoding="utf-8").read()
    assert not re.search(r"\b(DELETE|PATCH|PUT)\b", src, re.IGNORECASE)
    assert "merge-duplicates" not in src


def test_validation_et_raisons_d_ecart(tmp_path, capsys):
    recs = [
        serveur(0),
        serveur(1, slug=""),
        serveur(2, name="   "),
        serveur(3, package_type="cargo"),
        serveur(4, transport="grpc"),
        serveur(5, hosting="cloud"),
        serveur(6, stars="12"),
        serveur(7, weekly_downloads=1.5),
        serveur(8, quality_score="haut"),
        serveur(9, capabilities="tools"),
        serveur(10, remote_urls=[1, 2]),
        serveur(11, slug="serveur-0"),
        serveur(12, name="ns/serveur-0"),
        serveur(13, package_type=None, transport=None, hosting=None, stars=None,
                weekly_downloads=None, quality_score=None),
        serveur(14, stars=True),
        serveur(15, description="a\x00b"),
    ]
    chemin = ecrire_staging(tmp_path, recs)
    lancer(["--in", chemin])
    sortie = capsys.readouterr().out
    assert "LUS 16" in sortie
    assert "VALIDES 2" in sortie
    assert "ECARTES 14" in sortie
    for raison in ("slug vide", "name vide", "package_type hors liste",
                   "transport hors liste", "hosting hors liste", "stars pas un entier",
                   "weekly_downloads pas un entier", "quality_score invalide",
                   "capabilities pas une liste de textes", "remote_urls pas une liste de textes",
                   "slug en double", "nom en double", "description pas un texte"):
        assert raison in sortie, raison


def test_validation_ponts():
    recs = [pont(0), pont(1, source_id=""), pont(2, weight=10), pont(3, weight=-0.1),
            pont(4, relation=None), pont(5, weight="x"), pont(0), pont(6, weight=9.9999)]
    valides, ecarts = pm.preparer("ponts", recs)
    assert len(valides) == 2
    assert ecarts["pont en double"] == 1
    assert sum(ecarts.values()) == 6


def test_limite_et_depuis(tmp_path):
    chemin = ecrire_staging(tmp_path, [serveur(i) for i in range(10)])
    _, sender = lancer(["--in", chemin, "--pousser", "--depuis", "3", "--limite", "4"])
    envoyees = [r["slug"] for a in sender.posts() for r in json.loads(a[3])]
    assert envoyees == ["serveur-3", "serveur-4", "serveur-5", "serveur-6"]


def test_reprise_sur_503_puis_reussite(tmp_path, capsys):
    chemin = ecrire_staging(tmp_path, [serveur(1)])
    sender = FauxSender([(503, {}, "occupe"), (429, {}, "lent"), (201, {}, "")])
    attentes = []
    code, _ = lancer(["--in", chemin, "--pousser"], sender=sender, pause=attentes.append)
    assert code == 0
    assert len(sender.posts()) == 3
    assert attentes == [1, 2]


def test_reprise_sur_erreur_reseau(tmp_path):
    chemin = ecrire_staging(tmp_path, [serveur(1)])
    sender = FauxSender([OSError("coupe"), (201, {}, "")])
    code, _ = lancer(["--in", chemin, "--pousser"], sender=sender)
    assert code == 0
    assert len(sender.posts()) == 2


def test_cinq_essais_puis_arret(tmp_path, capsys):
    chemin = ecrire_staging(tmp_path, [serveur(1)])
    sender = FauxSender([(503, {}, "x")] * 10)
    code, _ = lancer(["--in", chemin, "--pousser"], sender=sender)
    assert code == 1
    assert len(sender.posts()) == 5
    assert "HTTP 503" in capsys.readouterr().out


def test_arret_net_sur_400(tmp_path, capsys):
    chemin = ecrire_staging(tmp_path, [serveur(i) for i in range(30)])
    corps = "E" * 500
    sender = FauxSender([(201, {}, ""), (400, {}, corps)])
    code, _ = lancer(["--in", chemin, "--pousser", "--lot", "10"], sender=sender)
    sortie = capsys.readouterr().out
    assert code == 1
    assert len(sender.posts()) == 2
    assert "lot 2" in sortie and "HTTP 400" in sortie
    assert "LOTS PASSES 1" in sortie
    assert "E" * 300 in sortie and "E" * 301 not in sortie


def test_cles_identiques_et_egales_aux_colonnes(tmp_path):
    recs = [serveur(i) for i in range(7)]
    recs[3]["id"] = 99
    recs[3]["embedding"] = [0.1]
    recs[3]["created_at"] = "x"
    chemin = ecrire_staging(tmp_path, recs)
    _, sender = lancer(["--in", chemin, "--pousser", "--lot", "3"])
    lignes = [r for a in sender.posts() for r in json.loads(a[3])]
    assert len(lignes) == 7
    for r in lignes:
        assert list(r.keys()) == list(pm.COLONNES_SERVEURS)
    for interdit in ("id", "embedding", "created_at", "updated_at"):
        assert interdit not in lignes[0]
    ponts = [pont(i) for i in range(3)]
    valides, _ = pm.preparer("ponts", ponts)
    assert all(list(r.keys()) == list(pm.COLONNES_PONTS) for r in valides)


def test_colonnes_correspondent_a_la_migration():
    racine = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sql = open(os.path.join(racine, "database", "migration_mcp_vertical.sql"), encoding="utf-8").read()
    for col in pm.COLONNES_SERVEURS:
        assert re.search(r"\b" + col + r"\b", sql), col


def test_cle_de_service_jamais_affichee(tmp_path, capsys):
    chemin = ecrire_staging(tmp_path, [serveur(i) for i in range(4)])
    sender = FauxSender([(201, {}, ""), (400, {}, "echo " + CLE_SECRETE + " fin")])
    lancer(["--in", chemin, "--pousser", "--lot", "2"], sender=sender)
    lancer(["--in", chemin])
    capture = capsys.readouterr()
    assert CLE_SECRETE not in capture.out
    assert CLE_SECRETE not in capture.err


def test_comptes_avant_apres(tmp_path, capsys):
    chemin = ecrire_staging(tmp_path, [serveur(1)])
    lancer(["--in", chemin, "--pousser"])
    sortie = capsys.readouterr().out
    assert "COMPTE AVANT 42" in sortie and "COMPTE APRES 42" in sortie


def test_lecteur_env(tmp_path):
    f = tmp_path / ".env"
    f.write_text("# note\nSUPABASE_URL=https://a.b\nSUPABASE_SERVICE_KEY=\"abc\"\n", encoding="utf-8")
    url, cle = pm.charger_identifiants(env={}, env_path=str(f))
    assert url == "https://a.b" and cle == "abc"
