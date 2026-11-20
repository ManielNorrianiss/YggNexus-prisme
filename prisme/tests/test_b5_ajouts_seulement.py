# -*- coding: utf-8 -*-
"""
Essais de b5_liens.py : pagination des outils, coupe propre des raisons,
mode --ajouts-seulement (aucun delete, paires presentes ignorees, trace).
Faux client Supabase en memoire, aucun reseau.
"""
import json

import b5_liens as b5


class FauxRequete:
    def __init__(self, client, table):
        self.client, self.table = client, table
        self.op, self.charge, self.plage = "select", None, None
        self.tri = []

    def select(self, *_a, **_k):
        self.op = "select"
        return self

    def eq(self, *_a, **_k):
        return self

    def order(self, col, **_k):
        self.tri.append(col)
        return self

    def range(self, a, b):
        self.plage = (a, b)
        return self

    def delete(self):
        self.op = "delete"
        self.client.appels.append((self.table, "delete"))
        return self

    def update(self, *_a, **_k):
        self.client.appels.append((self.table, "update"))
        return self

    def insert(self, lignes):
        self.op, self.charge = "insert", lignes
        return self

    def execute(self):
        if self.op == "insert":
            self.client.insertions.append((self.table, list(self.charge)))
            self.client.appels.append((self.table, "insert"))
            return type("R", (), {"data": self.charge})()
        lignes = self.client.donnees.get(self.table, [])
        if self.plage:
            lignes = lignes[self.plage[0]:self.plage[1] + 1]
        self.client.lectures.append((self.table, self.plage))
        return type("R", (), {"data": lignes})()


class FauxClient:
    def __init__(self, donnees):
        self.donnees = donnees
        self.appels, self.insertions, self.lectures = [], [], []

    def table(self, nom):
        return FauxRequete(self, nom)


def test_load_tools_pagine_jusqu_au_bout():
    outils = [{"id": i, "slug": f"o{i}", "name": f"O{i}"} for i in range(1, 1004)]
    sb = FauxClient({"tools": outils})
    res = b5.load_tools(sb)
    assert len(res) == 1003
    assert [p for t, p in sb.lectures if t == "tools"] == [(0, 999), (1000, 1999)]


def test_load_tools_exactement_une_page_pleine_lit_la_suivante():
    outils = [{"id": i} for i in range(1000)]
    sb = FauxClient({"tools": outils})
    assert len(b5.load_tools(sb)) == 1000
    assert len([1 for t, _p in sb.lectures if t == "tools"]) == 2


def test_couper_raison_courte_inchangee():
    assert b5.couper_raison("Short one.") == "Short one."


def test_couper_raison_ne_coupe_jamais_un_mot():
    brut = ("Google Stitch is a design tool, differing from Punch Needle "
            "Generator's focus on punch needle patterns and craft projects for makers "
            "who want to sell their finished work online")
    r = b5.couper_raison(brut)
    assert len(r) <= 140
    assert r.endswith(".")
    mots = set(brut.replace(",", " ").replace("'", " ").split())
    for mot in r.rstrip(".").replace(",", " ").replace("'", " ").split():
        assert mot in mots, f"mot coupe: {mot!r}"


def test_couper_raison_garde_la_derniere_phrase_complete():
    brut = ("A is a writing tool for teams. It also offers templates and a "
            "long list of integrations that goes on and on forever and ever")
    r = b5.couper_raison(brut, 100)
    assert r == "A is a writing tool for teams."


def test_couper_raison_exemple_reel_sans_espace_final():
    brut = "x" * 50 + " " + "y" * 200
    r = b5.couper_raison(brut)
    assert len(r) <= 140 and r.endswith(".")


def test_raison_llm_longue_est_coupee_proprement():
    def fn_gen(prompt, system, modele=None, timeout=60, _appel=None):
        return {"reason": "word " * 60}

    r = b5.raison_llm(fn_gen, {"name": "A"}, {"name": "B"}, "m")
    assert len(r) <= b5.MAX_LEN_RAISON
    assert r.endswith("word.")


def _outils_et_sim():
    return [
        {"id": 1, "slug": "a", "name": "A", "pricing": "free", "categorie_site": "productivity"},
        {"id": 2, "slug": "b", "name": "B", "pricing": "free", "categorie_site": "productivity"},
    ]


def test_ajouts_seulement_aucun_delete_trace_ecrite(tmp_path):
    sb = FauxClient({})
    lignes = [
        {"tool_id": 1, "alternative_id": 2, "similarity": 0.9, "reason": "r1"},
        {"tool_id": 2, "alternative_id": 1, "similarity": 0.9, "reason": "r2"},
    ]
    nb, chemin = b5.ajouter_paires_absentes(sb, lignes, dry_run=False,
                                            dossier_traces=tmp_path, horodatage="t")
    assert nb == 2
    assert all(op == "insert" for _t, op in sb.appels)
    assert chemin == tmp_path / "ajouts_t.json"
    trace = json.loads(chemin.read_text(encoding="utf-8"))
    assert trace["paires"] == [{"tool_id": 1, "alternative_id": 2},
                               {"tool_id": 2, "alternative_id": 1}]


def test_ajouts_seulement_dry_run_n_ecrit_rien(tmp_path):
    sb = FauxClient({})
    nb, chemin = b5.ajouter_paires_absentes(
        sb, [{"tool_id": 1, "alternative_id": 2, "similarity": 1, "reason": ""}],
        dry_run=True, dossier_traces=tmp_path)
    assert nb == 0 and chemin is None
    assert sb.appels == [] and list(tmp_path.iterdir()) == []


def test_load_paires_existantes_lit_seulement(tmp_path):
    sb = FauxClient({"alternatives": [{"tool_id": 1, "alternative_id": 2},
                                      {"tool_id": 3, "alternative_id": 4}]})
    assert b5.load_paires_existantes(sb) == {(1, 2), (3, 4)}
    assert sb.appels == []


def test_main_ajouts_seulement_ignore_les_paires_presentes(monkeypatch, tmp_path):
    import sys
    import types

    donnees = {
        "tools": _outils_et_sim(),
        "embeddings": [{"entity_id": 1, "embedding": [1.0, 0.0]},
                       {"entity_id": 2, "embedding": [1.0, 0.0]}],
        "alternatives": [{"tool_id": 1, "alternative_id": 2}],  # deja la
    }
    sb = FauxClient(donnees)
    faux_module = types.ModuleType("supabase")
    faux_module.create_client = lambda *_a, **_k: sb
    monkeypatch.setitem(sys.modules, "supabase", faux_module)
    monkeypatch.setattr(b5, "SUPABASE_URL", "http://x")
    monkeypatch.setattr(b5, "SERVICE_KEY", "k")
    monkeypatch.setattr(b5, "DOSSIER_TRACES", tmp_path)
    monkeypatch.setattr(sys, "argv", ["b5_liens.py", "--ajouts-seulement", "--sans-llm"])

    b5.main()

    assert not any(op in ("delete", "update") for _t, op in sb.appels)
    assert len(sb.insertions) == 1
    lignes = sb.insertions[0][1]
    # (1,2) existait : seule (2,1) est inseree
    assert [(l["tool_id"], l["alternative_id"]) for l in lignes] == [(2, 1)]
    fichiers = list(tmp_path.glob("ajouts_*.json"))
    assert len(fichiers) == 1
    assert json.loads(fichiers[0].read_text(encoding="utf-8"))["paires"] == [
        {"tool_id": 2, "alternative_id": 1}]
