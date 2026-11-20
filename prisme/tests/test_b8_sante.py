# -*- coding: utf-8 -*-
"""
test_b8_sante.py - essais de b8_sante.py : controles purs et lecture de
staging.db (base temporaire, aucun reseau, aucune cle).
"""
import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

import b8_sante as b8

NOW = datetime(2026, 11, 19, tzinfo=timezone.utc)


def _outil(slug, **kw):
    base = {"id": slug, "slug": slug, "seo_title": f"T {slug}",
            "seo_description": "d", "description_md": "m",
            "quality_score": 7.0, "updated_at": NOW.isoformat()}
    base.update(kw)
    return base


def _section(sections, debut):
    for titre, p in sections:
        if titre.startswith(debut):
            return p
    raise AssertionError(f"section absente : {debut}")


# ---------------------------------------------------------------- db_checks

def test_db_checks_outil_sain_aucun_probleme():
    s = b8.db_checks([_outil("a")], [], [], {"a"}, 90, NOW)
    assert sum(len(p) for _, p in s) == 0


def test_db_checks_detecte_embedding_seo_score_fraicheur():
    vieux = (NOW - timedelta(days=200)).isoformat()
    tools = [_outil("a", seo_title=""), _outil("b", quality_score=None),
             _outil("c", quality_score=11), _outil("d", updated_at=vieux),
             _outil("e", quality_score="x")]
    s = b8.db_checks(tools, [], [], {"a", "b", "c", "e"}, 90, NOW)
    assert _section(s, "Outils publies sans embedding") == ["d (id d)"]
    assert any("seo_title" in x for x in _section(s, "Outils avec champs SEO"))
    q = _section(s, "Outils avec quality_score")
    assert len(q) == 3
    assert len(_section(s, "Outils non mis a jour")) == 1


def test_parse_dt_formats():
    assert b8.parse_dt("2026-01-01T00:00:00Z").tzinfo is not None
    assert b8.parse_dt("2026-01-01").tzinfo is not None
    assert b8.parse_dt("pas une date") is None
    assert b8.parse_dt(None) is None


def test_render_report_total_et_tableau():
    total, md = b8.render_report([("A", ["x", "y"]), ("B", [])], NOW,
                                 "staging.db", False)
    assert total == 2
    assert "**Total de problemes : 2**" in md
    assert "| A | 2 |" in md and "- x" in md


def test_build_urls():
    u = b8.build_urls("https://s.test", ["a", "b"], ["c"])
    assert u == ["https://s.test/", "https://s.test/tools/a",
                 "https://s.test/tools/b"]


# ----------------------------------------------------------- staging_checks

def _brut(**kw):
    base = {"raw": [], "embeddings": [], "tagging": [], "dedup": []}
    base.update(kw)
    return base


def test_staging_checks_coherent():
    tools = [_outil("a")]
    brut = _brut(raw=[{"slug": "a", "status": "draft", "echecs": 0}],
                 tagging=["a"],
                 embeddings=[{"slug": "a", "dim": 2, "model": "m",
                              "embedding_json": "[0.1, 0.2]"}])
    s = b8.staging_checks(tools, [{"tool_id": "a", "category_id": "c",
                                   "is_primary": True}], brut)
    assert sum(len(p) for _, p in s) == 0


def test_staging_checks_incoherences():
    tools = [_outil("a", seo_title="Meme"), _outil("b", seo_title="meme")]
    brut = _brut(
        raw=[{"slug": "a"}, {"slug": "z"}],
        tagging=["a"],
        embeddings=[
            {"slug": "a", "dim": 2, "embedding_json": "[1, 2]"},
            {"slug": "b", "dim": 2, "embedding_json": "[1, 2]"},
            {"slug": "q", "dim": 2, "embedding_json": "[1, 2]"},
            {"slug": "r", "dim": 3, "embedding_json": "[1, 2]"},
            {"slug": "s", "dim": 2, "embedding_json": "pas json"},
            {"slug": "t", "dim": 2, "embedding_json": "[]"},
            {"slug": "u", "dim": 3, "embedding_json": "[1, 2, 3]"},
        ],
        dedup=[{"slug": "a", "canonical_slug": "z"},
               {"slug": "m", "canonical_slug": "n"},
               {"slug": "n", "canonical_slug": "m"},
               {"slug": "k", "canonical_slug": "absent"}])
    tc = [{"tool_id": "fantome", "category_id": "c", "is_primary": 1}]
    s = b8.staging_checks(tools, tc, brut)
    assert _section(s, "Fiches enrichies sans ligne brute") == ["b"]
    assert _section(s, "Lignes brutes sans fiche enrichie") == ["z"]
    assert _section(s, "Classements pointant") == ["fantome -> c"]
    assert _section(s, "Outils enrichis sans etiquetage") == ["b"]
    emb = " | ".join(_section(s, "Embeddings incoherents"))
    assert "q -> embedding sans fiche" in emb
    assert "s -> embedding_json illisible" in emb
    assert "t -> embedding vide" in emb
    assert "r -> dim declaree 3 != 2" in emb
    assert "u -> dimension 3" in emb
    dd = _section(s, "Doublons")
    assert any("k -> canonique absent" in x for x in dd)
    assert any("boucle" in x for x in dd)
    assert len(_section(s, "Titres SEO en double")) == 1


# ------------------------------------------------------- lecture staging.db

def _creer_staging(chemin):
    con = sqlite3.connect(chemin)
    con.executescript("""
    CREATE TABLE raw_tools (slug TEXT PRIMARY KEY, status TEXT, echecs INTEGER);
    CREATE TABLE enriched_tools (slug TEXT PRIMARY KEY, seo_title TEXT,
        seo_description TEXT, description_md TEXT, quality_score REAL,
        enriched_at TEXT);
    CREATE TABLE tool_embeddings (slug TEXT PRIMARY KEY, model TEXT, dim INTEGER,
        embedding_json TEXT);
    CREATE TABLE tool_categories (tool_slug TEXT, category_slug TEXT,
        is_primary INTEGER);
    CREATE TABLE tool_tagging (tool_slug TEXT PRIMARY KEY);
    CREATE TABLE dedup_map (slug TEXT PRIMARY KEY, canonical_slug TEXT);
    """)
    con.execute("INSERT INTO raw_tools VALUES ('a','draft',0)")
    con.execute("INSERT INTO enriched_tools VALUES ('a','T','d','m',5.0,"
                "'2026-11-01T00:00:00+00:00')")
    con.execute("INSERT INTO tool_embeddings VALUES ('a','m',2,?)",
                (json.dumps([0.1, 0.2]),))
    con.execute("INSERT INTO tool_categories VALUES ('a','cat',1)")
    con.execute("INSERT INTO tool_tagging VALUES ('a')")
    con.commit()
    con.close()


def test_fetch_from_staging_lit_et_ne_modifie_pas(tmp_path):
    chemin = tmp_path / "staging.db"
    _creer_staging(str(chemin))
    avant = chemin.read_bytes()
    tools, cats, tc, emb, brut = b8.fetch_from_staging(chemin)
    assert tools[0]["id"] == "a" and tools[0]["updated_at"].startswith("2026-11")
    assert cats == [{"id": "cat", "slug": "cat"}]
    assert tc == [{"tool_id": "a", "category_id": "cat", "is_primary": True}]
    assert emb == {"a"} and brut["tagging"] == ["a"]
    assert chemin.read_bytes() == avant
    s = b8.db_checks(tools, cats, tc, emb, 90, NOW) + \
        b8.staging_checks(tools, tc, brut)
    assert sum(len(p) for _, p in s) == 0


def test_fetch_from_staging_refuse_l_ecriture(tmp_path):
    chemin = tmp_path / "staging.db"
    _creer_staging(str(chemin))
    # la connexion interne est en mode=ro : on le verifie sur une connexion
    # ouverte de la meme facon.
    con = sqlite3.connect(f"file:{chemin.as_posix()}?mode=ro", uri=True)
    with pytest.raises(sqlite3.OperationalError):
        con.execute("DELETE FROM raw_tools")
    con.close()


def test_fetch_from_staging_fichier_absent(tmp_path):
    with pytest.raises(FileNotFoundError):
        b8.fetch_from_staging(tmp_path / "nexiste_pas.db")


def test_main_staging_ecrit_rapport_suffixe(tmp_path, monkeypatch):
    chemin = tmp_path / "staging.db"
    _creer_staging(str(chemin))
    monkeypatch.setattr(b8, "STAGING_DB", chemin)
    monkeypatch.setattr(b8, "EXPORTS_DIR", tmp_path / "health")
    monkeypatch.setattr("sys.argv", ["b8_sante.py", "--source", "staging"])
    b8.main()
    fichiers = list((tmp_path / "health").glob("*_staging.md"))
    assert len(fichiers) == 1
    assert "Total de problemes : 0" in fichiers[0].read_text(encoding="utf-8")
