# -*- coding: utf-8 -*-
"""
Tests purs de publier_embeddings_pgvector.py : construction du payload
d'upsert (entity_type/entity_id/model/embedding/content_hash), parse_vec,
resolution des tool_id et publication par lots via un client Supabase
factice (aucun reseau reel).
"""
import publier_embeddings_pgvector as ppv


# ---------------------------------------------------------------------------
# parse_vec
# ---------------------------------------------------------------------------

def test_parse_vec_liste_retournee_telle_quelle():
    assert ppv.parse_vec([0.1, 0.2, 0.3]) == [0.1, 0.2, 0.3]


def test_parse_vec_json_str_est_parsee():
    assert ppv.parse_vec("[0.1, 0.2]") == [0.1, 0.2]


def test_parse_vec_invalide_retourne_none():
    assert ppv.parse_vec("pas du json") is None


# ---------------------------------------------------------------------------
# construire_payload
# ---------------------------------------------------------------------------

def test_construire_payload_contient_les_bonnes_cles():
    vec = [0.0] * 768
    payload = ppv.construire_payload("acme-writer", 42, vec, "nomic-embed-text", "hash123")
    assert payload == {
        "entity_type": "tool",
        "entity_id": 42,
        "model": "nomic-embed-text",
        "embedding": vec,
        "content_hash": "hash123",
    }


def test_construire_payload_content_hash_vide_devient_chaine_vide():
    payload = ppv.construire_payload("x", 1, [0.1], "nomic-embed-text", None)
    assert payload["content_hash"] == ""


# ---------------------------------------------------------------------------
# resoudre_tool_ids : client Supabase factice
# ---------------------------------------------------------------------------

class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, table_data):
        self._table_data = table_data
        self._slugs = None

    def select(self, *_a, **_k):
        return self

    def in_(self, _col, slugs):
        self._slugs = set(slugs)
        return self

    def execute(self):
        rows = [r for r in self._table_data if r["slug"] in self._slugs]
        return _FakeResult(rows)


class _FakeTable:
    def __init__(self, data):
        self._data = data

    def select(self, *_a, **_k):
        return _FakeQuery(self._data)


class _FakeSupabase:
    """Client Supabase factice : sb.table('tools') -> lignes fixes."""

    def __init__(self, tools_rows):
        self._tools_rows = tools_rows

    def table(self, name):
        if name == "tools":
            return _FakeTable(self._tools_rows)
        raise AssertionError(f"table inattendue: {name}")


def test_resoudre_tool_ids_mappe_slug_vers_id():
    sb = _FakeSupabase([
        {"id": 1, "slug": "acme-writer"},
        {"id": 2, "slug": "scribe-ai"},
    ])
    mapping = ppv.resoudre_tool_ids(sb, ["acme-writer", "scribe-ai", "inconnu"])
    assert mapping == {"acme-writer": 1, "scribe-ai": 2}


# ---------------------------------------------------------------------------
# publier_par_lots : upsert par lots via client factice, dry_run n'ecrit rien
# ---------------------------------------------------------------------------

class _FakeUpsertTable:
    def __init__(self):
        self.lots_recus = []

    def upsert(self, rows, on_conflict=None):
        self.lots_recus.append((list(rows), on_conflict))
        return self

    def execute(self):
        return _FakeResult(None)


class _FakeSupabaseUpsert:
    def __init__(self):
        self.embeddings_table = _FakeUpsertTable()

    def table(self, name):
        assert name == "embeddings"
        return self.embeddings_table


def test_publier_par_lots_decoupe_en_lots_de_taille_batch_size():
    sb = _FakeSupabaseUpsert()
    rows = [ppv.construire_payload(f"tool-{i}", i, [0.1], "nomic-embed-text", "h") for i in range(5)]

    nb_ok, nb_error = ppv.publier_par_lots(sb, rows, dry_run=False, batch_size=2)

    assert nb_ok == 5
    assert nb_error == 0
    lots = sb.embeddings_table.lots_recus
    assert len(lots) == 3  # 2 + 2 + 1
    assert [len(l[0]) for l in lots] == [2, 2, 1]
    assert all(l[1] == "entity_type,entity_id,model" for l in lots)


def test_publier_par_lots_dry_run_ne_touche_pas_au_client():
    sb = _FakeSupabaseUpsert()
    rows = [ppv.construire_payload("tool-a", 1, [0.1], "nomic-embed-text", "h")]

    nb_ok, nb_error = ppv.publier_par_lots(sb, rows, dry_run=True, batch_size=10)

    assert nb_ok == 1
    assert nb_error == 0
    assert sb.embeddings_table.lots_recus == []


def test_publier_par_lots_erreur_upsert_est_comptee_sans_lever():
    class _SupabaseEnErreur:
        def table(self, _name):
            class _T:
                def upsert(self, rows, on_conflict=None):
                    raise RuntimeError("upsert echoue")
            return _T()

    rows = [ppv.construire_payload("tool-a", 1, [0.1], "nomic-embed-text", "h")]
    nb_ok, nb_error = ppv.publier_par_lots(_SupabaseEnErreur(), rows, dry_run=False, batch_size=10)

    assert nb_ok == 0
    assert nb_error == 1


# ---------------------------------------------------------------------------
# charger_lignes : filtre --only / --limit sur staging.iter_embeddings (via
# un staging temporaire, jamais staging.db du montage)
# ---------------------------------------------------------------------------

def test_charger_lignes_filtre_only_et_limit(monkeypatch, tmp_path):
    import staging

    db_path = str(tmp_path / "staging_test.db")
    staging.upsert_embedding({
        "slug": "tool-a", "model": "nomic-embed-text", "dim": 768,
        "embedding_json": [0.1] * 768, "content_hash": "h1", "created_at": "2026-07-01T00:00:00Z",
    }, path=db_path)
    staging.upsert_embedding({
        "slug": "tool-b", "model": "nomic-embed-text", "dim": 768,
        "embedding_json": [0.2] * 768, "content_hash": "h2", "created_at": "2026-07-01T00:00:00Z",
    }, path=db_path)

    def _iter_embeddings_stub(path=None):
        return staging.iter_embeddings.__wrapped__(path=db_path) if hasattr(staging.iter_embeddings, "__wrapped__") \
            else _iter_from_db(db_path)

    def _iter_from_db(path):
        db = staging.connect(path)
        for row in db.execute("SELECT * FROM tool_embeddings ORDER BY slug"):
            yield dict(row)

    monkeypatch.setattr(ppv.staging, "iter_embeddings", lambda path=None: _iter_from_db(db_path))

    rows_all = ppv.charger_lignes()
    slugs = sorted(r["slug"] for r in rows_all)
    assert slugs == ["tool-a", "tool-b"]

    rows_only = ppv.charger_lignes(only="tool-a")
    assert len(rows_only) == 1
    assert rows_only[0]["slug"] == "tool-a"

    rows_limit = ppv.charger_lignes(limit=1)
    assert len(rows_limit) == 1
