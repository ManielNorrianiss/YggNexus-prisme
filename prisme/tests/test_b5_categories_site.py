# -*- coding: utf-8 -*-
"""
Essais de la categorie du site dans les raisons de b5_liens.py (correction du
2026-11-20) : lecture paginee de la categorie principale (tool_categories
is_primary + categories), libelles anglais et francais, absence de categorie,
application_category jamais imprime, apercu, mode --ajouts-seulement sans
suppression. Faux client Supabase en memoire, aucun reseau.
"""
import json
import sys
import types

import b5_liens as b5


class FauxRequete:
    def __init__(self, client, table):
        self.client, self.table = client, table
        self.op, self.charge, self.plage, self.filtres, self.tri = "select", None, None, [], []

    def select(self, *_a, **_k):
        return self

    def eq(self, col, val):
        self.filtres.append((col, val))
        return self

    def order(self, col, **_k):
        self.tri.append(col)
        return self

    def range(self, a, b):
        self.plage = (a, b)
        return self

    def delete(self):
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
        lignes = [r for r in self.client.donnees.get(self.table, [])
                  if all(r.get(c) == v for c, v in self.filtres)]
        for col in reversed(self.tri):
            lignes = sorted(lignes, key=lambda r, c=col: r.get(c))
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


CATEGORIES = [{"id": 10 + i, "slug": s} for i, s in enumerate(b5.CATEGORIES_SITE)]
ID_CAT = {c["slug"]: c["id"] for c in CATEGORIES}


def _tool(i, nom, cat_site="", pricing="free", libre="MultimediaApplication"):
    return {"id": i, "slug": nom.lower(), "name": nom, "pricing": pricing,
            "categorie_site": cat_site, "application_category": libre}


# ---------------------------------------------------------------------------
# Lecture de la categorie principale
# ---------------------------------------------------------------------------

def test_load_tools_rapporte_la_categorie_principale_is_primary():
    sb = FauxClient({
        "tools": [{"id": 1, "slug": "pika", "name": "Pika", "status": "published"},
                  {"id": 2, "slug": "nocat", "name": "NoCat", "status": "published"},
                  {"id": 3, "slug": "sec", "name": "SecondaireSeule", "status": "published"}],
        "categories": CATEGORIES,
        "tool_categories": [
            {"tool_id": 1, "category_id": ID_CAT["ai-video"], "is_primary": True},
            {"tool_id": 1, "category_id": ID_CAT["ai-images"], "is_primary": False},
            {"tool_id": 3, "category_id": ID_CAT["productivity"], "is_primary": False},
        ],
    })
    res = {t["slug"]: t for t in b5.load_tools(sb)}
    assert res["pika"]["categorie_site"] == "ai-video"
    assert res["nocat"]["categorie_site"] == ""
    assert res["sec"]["categorie_site"] == ""          # secondaire seule : pas de principale
    assert all("application_category" not in t for t in res.values())


def test_load_tools_lecture_seule_et_paginee():
    n = 2100
    sb = FauxClient({
        "tools": [{"id": i, "slug": f"o{i}", "name": f"O{i}", "status": "published"} for i in range(1, 5)],
        "categories": CATEGORIES,
        "tool_categories": [{"tool_id": i, "category_id": ID_CAT["ai-coding"], "is_primary": True}
                            for i in range(1, n + 1)],
    })
    res = b5.load_tools(sb)
    assert {t["categorie_site"] for t in res} == {"ai-coding"}
    pages = [p for t, p in sb.lectures if t == "tool_categories"]
    assert pages == [(0, 999), (1000, 1999), (2000, 2999)]
    assert sb.appels == []                              # aucune ecriture, aucune suppression


def test_load_categories_principales_deux_principales_garde_le_plus_petit_id():
    sb = FauxClient({
        "categories": CATEGORIES,
        "tool_categories": [
            {"tool_id": 1, "category_id": ID_CAT["ai-video"], "is_primary": True},
            {"tool_id": 1, "category_id": ID_CAT["ai-audio"], "is_primary": True},
        ],
    })
    assert b5.load_categories_principales(sb) == {1: "ai-audio" if ID_CAT["ai-audio"] < ID_CAT["ai-video"] else "ai-video"}


# ---------------------------------------------------------------------------
# Libelles
# ---------------------------------------------------------------------------

def test_tableau_des_neuf_categories_complet():
    tax = json.loads((b5.ROOT / "data" / "taxonomy.json").read_text(encoding="utf-8"))
    assert set(b5.CATEGORIES_SITE) == {c["slug"] for c in tax}
    assert len(b5.CATEGORIES_SITE) == 9
    for slug in b5.CATEGORIES_SITE:
        assert b5._category_label(slug, "en") and b5._category_label(slug, "fr")


def test_category_label_vide_ou_inconnu():
    assert b5._category_label("") == ""
    assert b5._category_label(None, "fr") == ""
    assert b5._category_label("multimedia") == ""


# ---------------------------------------------------------------------------
# Raisons
# ---------------------------------------------------------------------------

def test_categorie_du_site_et_non_le_champ_libre():
    pika = _tool(1, "Pika", "ai-video", libre="MultimediaApplication")
    invideo = _tool(2, "InVideo", "ai-video", libre="SoftwareApplication")
    en = b5.raison_gabarit(pika, invideo)
    fr = b5.raison_gabarit_fr(pika, invideo)
    assert "AI video" in en and "multimedia" not in en and "software" not in en
    assert "Vidéo IA" in fr


def test_sans_categorie_du_site_aucune_parenthese_ni_libelle():
    avec = _tool(1, "Alpha", "ai-video", "free")
    sans = _tool(2, "Beta", "", "paid", libre="DeveloperApplication")
    sans2 = _tool(3, "Gamma", "", "free")
    for t, a in ((sans, sans2), (sans2, sans)):
        en, fr = b5.raison_gabarit(t, a), b5.raison_gabarit_fr(t, a)
        assert "(" not in en and "(" not in fr
        assert "«" not in fr
        for libelle in b5.CATEGORIES_SITE.values():
            assert libelle["en"] not in en and libelle["fr"] not in fr
        assert "ai/saas" not in en
        assert en.endswith(".") and fr.endswith(".")
    # un seul outil classe : le libelle de celui-ci, rien pour l'autre
    en = b5.raison_gabarit(avec, sans)
    assert en.count("AI video") == 1 and "Beta (" not in en
    fr = b5.raison_gabarit_fr(sans, avec)
    assert fr.count("Vidéo IA") == 1 and "Beta (" not in fr
    en2 = b5.raison_gabarit(sans, avec)
    assert "Beta is an AI video alternative" not in en2   # sens : l'alternative est Alpha ici
    assert "Alpha is an AI video alternative to Beta" in en2


def test_application_category_n_apparait_dans_aucune_raison():
    combos = [("ai-video", ""), ("", "ai-audio"), ("", ""), ("ai-coding", "ai-coding"),
              ("productivity", "automation")]
    libres = ["developer", "multimedia", "software", "web", "business", "utilities"]
    for ct, ca in combos:
        for libre in libres:
            t = _tool(1, "Tool", ct, "free", libre=libre.capitalize() + "Application")
            a = _tool(2, "Alt", ca, "paid", libre=libre.capitalize() + "Application")
            for r in (b5.raison_gabarit(t, a), b5.raison_gabarit_fr(t, a)):
                assert "application_category" not in r
                assert libre not in r.lower()
    import inspect
    assert "application_category" not in inspect.getsource(b5.raison_gabarit)
    assert "application_category" not in inspect.getsource(b5.raison_gabarit_fr)
    assert "application_category" not in inspect.getsource(b5.raison_llm)


def test_prompt_llm_utilise_la_categorie_du_site_et_omet_la_categorie_absente():
    vus = []

    def fn_gen(prompt, system, modele=None, timeout=60, _appel=None):
        vus.append(prompt)
        return {"reason": "Fine."}

    b5.raison_llm(fn_gen, _tool(1, "Pika", "ai-video"), _tool(2, "Beta", ""), "m")
    p = vus[0]
    assert "Pika (category: AI video, pricing: free)" in p
    assert "Beta (pricing: free)" in p
    assert "multimedia" not in p


def test_longueurs_respectees():
    t = _tool(1, "A" * 40, "data-scraping", "open_source")
    a = _tool(2, "B" * 40, "ai-writing", "unknown")
    assert len(b5.raison_gabarit(t, a)) <= b5.MAX_LEN_RAISON
    assert len(b5.raison_gabarit_fr(t, a)) <= b5.MAX_LEN_RAISON_FR


# ---------------------------------------------------------------------------
# Apercu et mode --ajouts-seulement
# ---------------------------------------------------------------------------

def test_construire_apercu_dit_aucune_quand_pas_de_categorie():
    idx = {1: _tool(1, "Pika", "ai-video"), 2: _tool(2, "Beta", "")}
    ap = b5.construire_apercu([(1, "pika", 2, "beta", 0.8)], idx,
                              {(1, 2): "en"}, {(1, 2): "fr"})
    assert ap == [{"outil": "Pika", "outil_slug": "pika", "categorie_outil": "AI video",
                   "alternative": "Beta", "alternative_slug": "beta",
                   "categorie_alternative": "aucune", "similarity": 0.8,
                   "reason": "en", "reason_fr": "fr"}]


def _lancer_main(monkeypatch, tmp_path, donnees, *args):
    sb = FauxClient(donnees)
    faux = types.ModuleType("supabase")
    faux.create_client = lambda *_a, **_k: sb
    monkeypatch.setitem(sys.modules, "supabase", faux)
    monkeypatch.setattr(b5, "SUPABASE_URL", "http://x")
    monkeypatch.setattr(b5, "SERVICE_KEY", "k")
    monkeypatch.setattr(b5, "DOSSIER_TRACES", tmp_path)
    monkeypatch.setattr(sys, "argv", ["b5_liens.py", "--ajouts-seulement", "--sans-llm", *args])
    b5.main()
    return sb


def _donnees():
    return {
        "tools": [{"id": 1, "slug": "pika", "name": "Pika", "status": "published", "pricing": "paid", "application_category": "MultimediaApplication"},
                  {"id": 2, "slug": "invideo", "name": "InVideo", "status": "published", "pricing": "freemium", "application_category": "SoftwareApplication"},
                  {"id": 3, "slug": "nocat", "name": "NoCat", "status": "published", "pricing": "free", "application_category": "DeveloperApplication"}],
        "categories": CATEGORIES,
        "tool_categories": [
            {"tool_id": 1, "category_id": ID_CAT["ai-video"], "is_primary": True},
            {"tool_id": 2, "category_id": ID_CAT["ai-video"], "is_primary": True},
        ],
        "embeddings": [{"entity_id": i, "entity_type": "tool", "model": "nomic-embed-text", "embedding": [1.0, 0.0]} for i in (1, 2, 3)],
        "alternatives": [],
    }


def test_main_ajouts_seulement_reel_aucune_suppression_et_raisons_du_site(monkeypatch, tmp_path):
    sb = _lancer_main(monkeypatch, tmp_path, _donnees())
    assert not any(op in ("delete", "update") for _t, op in sb.appels)
    assert [t for t, _ in sb.insertions] == ["alternatives"]
    lignes = sb.insertions[0][1]
    assert len(lignes) == 6
    par_paire = {(l["tool_id"], l["alternative_id"]): l for l in lignes}
    l = par_paire[(1, 2)]
    assert l["reason"].startswith("Both are AI video tools")
    assert "Vidéo IA" in l["reason_fr"]
    for l in lignes:
        assert "multimedia" not in l["reason"] and "software" not in l["reason"]
        if 3 in (l["tool_id"], l["alternative_id"]):
            assert "(" not in l["reason"] or "AI video)" in l["reason"]
    assert list(tmp_path.glob("apercu_*.json")) == []      # --montrer absent : pas d'apercu


def test_main_dry_run_montrer_ecrit_l_apercu_et_rien_en_base(monkeypatch, tmp_path, capsys):
    sb = _lancer_main(monkeypatch, tmp_path, _donnees(), "--dry-run", "--montrer")
    assert sb.appels == [] and sb.insertions == []
    fichiers = list(tmp_path.glob("apercu_*.json"))
    assert len(fichiers) == 1 and list(tmp_path.glob("ajouts_*.json")) == []
    contenu = json.loads(fichiers[0].read_text(encoding="utf-8"))
    assert contenu["nb_paires"] == 6
    cats = {(p["outil"], p["alternative"]): (p["categorie_outil"], p["categorie_alternative"])
            for p in contenu["paires"]}
    assert cats[("Pika", "InVideo")] == ("AI video", "AI video")
    assert cats[("Pika", "NoCat")] == ("AI video", "aucune")
    sortie = capsys.readouterr().out
    assert "6 paire(s) a ajouter" in sortie and "EN :" in sortie and "FR :" in sortie
    assert "NoCat (aucune)" in sortie


def test_main_montrer_sans_dry_run_n_ecrit_pas_d_apercu(monkeypatch, tmp_path):
    _lancer_main(monkeypatch, tmp_path, _donnees(), "--montrer")
    assert list(tmp_path.glob("apercu_*.json")) == []
