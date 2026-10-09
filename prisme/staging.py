# -*- coding: utf-8 -*-
"""
staging.py - SQLite local pour le pipeline B1/B2.
Tables: raw_tools, enriched_tools, tool_embeddings.

CHEMIN PAR DEFAUT: variable d'env STAGING_DB_PATH, sinon prisme/staging.db.
Sur Windows, SQLite peut planter sur un lecteur reseau ou partage.
Si necessaire, definir STAGING_DB_PATH vers un chemin local (ex: C:/staging.db).

Concurrence : chaque fonction ouvre sa propre connexion sqlite3 de courte
duree (pas de connexion partagee entre fils). WAL + synchronous=NORMAL sont
actives a chaque connexion pour permettre des lectures concurrentes pendant
qu'un fil ecrit, sans perte de durabilite critique pour ce pipeline local.
"""
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_PRISME_DIR = Path(__file__).resolve().parent
_DEFAULT_DB = Path(os.environ.get("STAGING_DB_PATH", str(_PRISME_DIR / "staging.db")))


def connect(path=None):
    """
    Retourne une connexion SQLite avec row_factory dict-like.
    Active WAL (journal_mode) + synchronous=NORMAL pour de meilleures
    performances en ecriture/lecture concurrente (plusieurs fils).
    check_same_thread=False car chaque connexion est de courte duree et
    n'est jamais partagee entre fils simultanement dans ce pipeline.
    """
    db_path = str(path or _DEFAULT_DB)
    db = sqlite3.connect(db_path, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    return db


def init_db(path=None):
    """Cree les tables et index si elles n'existent pas encore."""
    db = connect(path)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS raw_tools (
            slug             TEXT PRIMARY KEY,
            name             TEXT,
            vendor           TEXT,
            website_url      TEXT,
            source_url       TEXT,
            source_hash      TEXT,
            raw_title        TEXT,
            raw_meta_desc    TEXT,
            raw_text         TEXT,
            categories_json  TEXT,
            primary_category TEXT,
            status           TEXT DEFAULT 'draft',
            collected_at     TEXT
        );

        CREATE TABLE IF NOT EXISTS enriched_tools (
            slug                TEXT PRIMARY KEY,
            short_desc          TEXT,
            description_md      TEXT,
            pros_json           TEXT,
            cons_json           TEXT,
            faq_json            TEXT,
            seo_title           TEXT,
            seo_description     TEXT,
            application_category TEXT,
            pricing             TEXT,
            pricing_note        TEXT,
            quality_score       REAL,
            content_hash        TEXT,
            enriched_at         TEXT
        );

        CREATE TABLE IF NOT EXISTS tool_embeddings (
            slug           TEXT PRIMARY KEY,
            model          TEXT,
            dim            INTEGER,
            embedding_json TEXT,
            content_hash   TEXT,
            created_at     TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_raw_tools_status
            ON raw_tools(status);
        CREATE INDEX IF NOT EXISTS idx_raw_tools_source_hash
            ON raw_tools(source_hash);
        CREATE INDEX IF NOT EXISTS idx_enriched_tools_content_hash
            ON enriched_tools(content_hash);
        CREATE INDEX IF NOT EXISTS idx_tool_embeddings_content_hash
            ON tool_embeddings(content_hash);
    """)
    db.commit()
    return db


def upsert_raw(d, path=None):
    """Insere ou met a jour une ligne dans raw_tools."""
    db = init_db(path)
    cats = d.get("categories_json")
    if isinstance(cats, list):
        cats = json.dumps(cats)
    db.execute("""
        INSERT INTO raw_tools
            (slug, name, vendor, website_url, source_url, source_hash,
             raw_title, raw_meta_desc, raw_text, categories_json,
             primary_category, status, collected_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(slug) DO UPDATE SET
            name=excluded.name, vendor=excluded.vendor,
            website_url=excluded.website_url, source_url=excluded.source_url,
            source_hash=excluded.source_hash, raw_title=excluded.raw_title,
            raw_meta_desc=excluded.raw_meta_desc, raw_text=excluded.raw_text,
            categories_json=excluded.categories_json,
            primary_category=excluded.primary_category,
            status=excluded.status, collected_at=excluded.collected_at
    """, (
        d.get("slug"), d.get("name"), d.get("vendor"), d.get("website_url"),
        d.get("source_url"), d.get("source_hash"), d.get("raw_title"),
        d.get("raw_meta_desc"), d.get("raw_text"), cats,
        d.get("primary_category"), d.get("status", "draft"), d.get("collected_at"),
    ))
    db.commit()


def upsert_raw_many(rows, path=None):
    """
    Insere ou met a jour plusieurs lignes dans raw_tools en une seule
    transaction (executemany). rows : liste de dicts au meme format que
    upsert_raw. Plus rapide que d'appeler upsert_raw en boucle pour de gros
    volumes (regroupe les commits).
    """
    if not rows:
        return
    db = init_db(path)
    params = []
    for d in rows:
        cats = d.get("categories_json")
        if isinstance(cats, list):
            cats = json.dumps(cats)
        params.append((
            d.get("slug"), d.get("name"), d.get("vendor"), d.get("website_url"),
            d.get("source_url"), d.get("source_hash"), d.get("raw_title"),
            d.get("raw_meta_desc"), d.get("raw_text"), cats,
            d.get("primary_category"), d.get("status", "draft"), d.get("collected_at"),
        ))
    db.executemany("""
        INSERT INTO raw_tools
            (slug, name, vendor, website_url, source_url, source_hash,
             raw_title, raw_meta_desc, raw_text, categories_json,
             primary_category, status, collected_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(slug) DO UPDATE SET
            name=excluded.name, vendor=excluded.vendor,
            website_url=excluded.website_url, source_url=excluded.source_url,
            source_hash=excluded.source_hash, raw_title=excluded.raw_title,
            raw_meta_desc=excluded.raw_meta_desc, raw_text=excluded.raw_text,
            categories_json=excluded.categories_json,
            primary_category=excluded.primary_category,
            status=excluded.status, collected_at=excluded.collected_at
    """, params)
    db.commit()


def get_raw(slug, path=None):
    db = init_db(path)
    row = db.execute("SELECT * FROM raw_tools WHERE slug=?", (slug,)).fetchone()
    return dict(row) if row else None


def iter_raw(path=None):
    db = init_db(path)
    for row in db.execute("SELECT * FROM raw_tools ORDER BY slug"):
        yield dict(row)


def upsert_enriched(d, path=None):
    """Insere ou met a jour une ligne dans enriched_tools."""
    db = init_db(path)
    pros = d.get("pros_json")
    cons = d.get("cons_json")
    faq  = d.get("faq_json")
    if isinstance(pros, list): pros = json.dumps(pros)
    if isinstance(cons, list): cons = json.dumps(cons)
    if isinstance(faq,  list): faq  = json.dumps(faq)
    db.execute("""
        INSERT INTO enriched_tools
            (slug, short_desc, description_md, pros_json, cons_json, faq_json,
             seo_title, seo_description, application_category,
             pricing, pricing_note, quality_score, content_hash, enriched_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(slug) DO UPDATE SET
            short_desc=excluded.short_desc, description_md=excluded.description_md,
            pros_json=excluded.pros_json, cons_json=excluded.cons_json,
            faq_json=excluded.faq_json, seo_title=excluded.seo_title,
            seo_description=excluded.seo_description,
            application_category=excluded.application_category,
            pricing=excluded.pricing, pricing_note=excluded.pricing_note,
            quality_score=excluded.quality_score, content_hash=excluded.content_hash,
            enriched_at=excluded.enriched_at
    """, (
        d.get("slug"), d.get("short_desc"), d.get("description_md"),
        pros, cons, faq, d.get("seo_title"), d.get("seo_description"),
        d.get("application_category"), d.get("pricing"), d.get("pricing_note"),
        d.get("quality_score"), d.get("content_hash"), d.get("enriched_at"),
    ))
    db.commit()


def get_enriched(slug, path=None):
    db = init_db(path)
    row = db.execute("SELECT * FROM enriched_tools WHERE slug=?", (slug,)).fetchone()
    return dict(row) if row else None


def iter_enriched(path=None):
    db = init_db(path)
    for row in db.execute("SELECT * FROM enriched_tools ORDER BY slug"):
        yield dict(row)


def upsert_embedding(d, path=None):
    """Insere ou met a jour une ligne dans tool_embeddings."""
    db = init_db(path)
    vec = d.get("embedding_json")
    if isinstance(vec, list): vec = json.dumps(vec)
    db.execute("""
        INSERT INTO tool_embeddings
            (slug, model, dim, embedding_json, content_hash, created_at)
        VALUES (?,?,?,?,?,?)
        ON CONFLICT(slug) DO UPDATE SET
            model=excluded.model, dim=excluded.dim,
            embedding_json=excluded.embedding_json,
            content_hash=excluded.content_hash, created_at=excluded.created_at
    """, (
        d.get("slug"), d.get("model"), d.get("dim"),
        vec, d.get("content_hash"), d.get("created_at"),
    ))
    db.commit()


def iter_embeddings(path=None):
    db = init_db(path)
    for row in db.execute("SELECT * FROM tool_embeddings ORDER BY slug"):
        yield dict(row)


# ---------------------------------------------------------------------------
# dedup_map helpers (added for B3)
# ---------------------------------------------------------------------------

def init_dedup(path=None):
    """Cree la table dedup_map si elle n'existe pas (idempotente)."""
    db = connect(path)
    db.execute("""
        CREATE TABLE IF NOT EXISTS dedup_map (
            slug          TEXT PRIMARY KEY,
            canonical_slug TEXT,
            reason        TEXT,
            score         REAL,
            prev_status   TEXT,
            detected_at   TEXT
        )
    """)
    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_dedup_map_canonical_slug
            ON dedup_map(canonical_slug)
    """)
    db.commit()
    return db


def upsert_dedup(d, path=None):
    """Insere ou met a jour une ligne dans dedup_map."""
    db = init_dedup(path)
    db.execute("""
        INSERT INTO dedup_map
            (slug, canonical_slug, reason, score, prev_status, detected_at)
        VALUES (?,?,?,?,?,?)
        ON CONFLICT(slug) DO UPDATE SET
            canonical_slug=excluded.canonical_slug,
            reason=excluded.reason,
            score=excluded.score,
            prev_status=excluded.prev_status,
            detected_at=excluded.detected_at
    """, (
        d.get("slug"), d.get("canonical_slug"), d.get("reason"),
        d.get("score"), d.get("prev_status"), d.get("detected_at"),
    ))
    db.commit()


def iter_dedup(path=None):
    """Itere sur toutes les lignes de dedup_map."""
    db = init_dedup(path)
    for row in db.execute("SELECT * FROM dedup_map ORDER BY canonical_slug, slug"):
        yield dict(row)


def clear_dedup(path=None):
    """Vide entierement la table dedup_map."""
    db = init_dedup(path)
    db.execute("DELETE FROM dedup_map")
    db.commit()


def set_raw_status(slug, status, path=None):
    """Met a jour raw_tools.status pour un slug donne."""
    db = connect(path)
    db.execute("UPDATE raw_tools SET status=? WHERE slug=?", (status, slug))
    db.commit()


# ---------------------------------------------------------------------------
# tool_categories helpers (added for B4)
# ---------------------------------------------------------------------------

def init_tool_categories(path=None):
    """Create tool_categories table if it does not exist (idempotent)."""
    db = connect(path)
    db.execute("""
        CREATE TABLE IF NOT EXISTS tool_categories (
            tool_slug       TEXT,
            category_slug   TEXT,
            is_primary      INTEGER,
            confidence      REAL,
            is_unclassified INTEGER DEFAULT 0,
            classified_at   TEXT,
            content_hash    TEXT,
            PRIMARY KEY (tool_slug, category_slug)
        )
    """)
    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_tool_categories_category_slug
            ON tool_categories(category_slug)
    """)
    db.commit()
    return db


def replace_tool_categories(tool_slug, rows, path=None):
    """Delete existing rows for tool_slug then insert new rows atomically."""
    db = init_tool_categories(path)
    db.execute("DELETE FROM tool_categories WHERE tool_slug=?", (tool_slug,))
    params = [
        (
            tool_slug,
            r.get("category_slug", ""),
            r.get("is_primary", 0),
            r.get("confidence", 0.0),
            r.get("is_unclassified", 0),
            r.get("classified_at", ""),
            r.get("content_hash", ""),
        )
        for r in rows
    ]
    if params:
        db.executemany("""
            INSERT INTO tool_categories
                (tool_slug, category_slug, is_primary, confidence,
                 is_unclassified, classified_at, content_hash)
            VALUES (?,?,?,?,?,?,?)
        """, params)
    db.commit()


def get_tool_categories(tool_slug, path=None):
    """Return list of dicts for all rows of a given tool_slug."""
    db = init_tool_categories(path)
    rows = db.execute(
        "SELECT * FROM tool_categories WHERE tool_slug=?", (tool_slug,)
    ).fetchall()
    return [dict(r) for r in rows]


def iter_tool_categories(path=None):
    """Iterate over all rows in tool_categories ordered by tool_slug."""
    db = init_tool_categories(path)
    for row in db.execute("SELECT * FROM tool_categories ORDER BY tool_slug"):
        yield dict(row)


# ---------------------------------------------------------------------------
# tool_tagging helpers (added for b4_tagging)
# ---------------------------------------------------------------------------

def init_tool_tagging(path=None):
    """Create tool_tagging table if it does not exist (idempotent)."""
    db = connect(path)
    db.execute("""
        CREATE TABLE IF NOT EXISTS tool_tagging (
            tool_slug    TEXT PRIMARY KEY,
            facets_json  TEXT,
            tags_json    TEXT,
            tagged_at    TEXT,
            content_hash TEXT
        )
    """)
    db.commit()
    return db


def replace_tool_tagging(tool_slug, facets, tags, content_hash, path=None):
    """Delete existing row for tool_slug then insert new row atomically.

    facets     : dict {axis: [slug, ...]}
    tags       : list of {"slug": ..., "label": ...}
    content_hash: str
    """
    db = init_tool_tagging(path)
    db.execute("DELETE FROM tool_tagging WHERE tool_slug=?", (tool_slug,))
    db.execute("""
        INSERT INTO tool_tagging (tool_slug, facets_json, tags_json, tagged_at, content_hash)
        VALUES (?, ?, ?, datetime('now'), ?)
    """, (
        tool_slug,
        json.dumps(facets,  ensure_ascii=False),
        json.dumps(tags,    ensure_ascii=False),
        content_hash,
    ))
    db.commit()


def get_tool_tagging(tool_slug, path=None):
    """Return {"facets": dict, "tags": list} for a given tool_slug.

    Returns defaults (empty dict / empty list) if the slug has no tagging row.
    """
    db = init_tool_tagging(path)
    row = db.execute(
        "SELECT facets_json, tags_json FROM tool_tagging WHERE tool_slug=?",
        (tool_slug,)
    ).fetchone()
    if not row:
        return {"facets": {}, "tags": []}
    facets = json.loads(row["facets_json"] or "{}")
    tags   = json.loads(row["tags_json"]   or "[]")
    return {"facets": facets, "tags": tags}


# ---------------------------------------------------------------------------
# run_log + memoire d'erreurs (ajoute pour l'auto-ajustement du Prisme)
# ---------------------------------------------------------------------------

def init_run_log(path=None):
    """Cree la table run_log si elle n'existe pas encore (idempotente)."""
    db = connect(path)
    db.execute("""
        CREATE TABLE IF NOT EXISTS run_log (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id         TEXT,
            etape          TEXT,
            slug           TEXT,
            niveau         TEXT,
            type_evenement TEXT,
            detail         TEXT,
            created_at     TEXT
        )
    """)
    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_run_log_run_id
            ON run_log(run_id)
    """)
    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_run_log_etape
            ON run_log(etape)
    """)
    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_run_log_type_evenement
            ON run_log(type_evenement)
    """)
    db.commit()
    return db


def migrate_raw_tools_echecs(path=None):
    """
    Migration idempotente : ajoute la colonne 'echecs' (INTEGER DEFAULT 0)
    a raw_tools si elle n'existe pas deja. Le statut 'quarantaine' est une
    simple valeur texte de plus pour la colonne status existante (aucune
    migration de schema requise pour ca).
    Garde try/except : ALTER TABLE ADD COLUMN echoue si la colonne existe
    deja (SQLite ne supporte pas IF NOT EXISTS sur ADD COLUMN).
    Appelle d'abord init_db() pour garantir que raw_tools existe deja.
    """
    db = init_db(path)
    try:
        db.execute("ALTER TABLE raw_tools ADD COLUMN echecs INTEGER DEFAULT 0")
        db.commit()
    except sqlite3.OperationalError:
        # colonne deja presente : rien a faire
        pass
    return db


def init_memoire(path=None):
    """Initialise les tables/colonnes necessaires a la memoire d'erreurs."""
    init_db(path)
    init_run_log(path)
    migrate_raw_tools_echecs(path)


def log_evenement(run_id, etape, type_evenement, detail, slug=None, niveau="erreur", path=None):
    """
    Ajoute une ligne dans run_log.

    Parametres:
        run_id         : str - identifiant du run (ex: horodatage)
        etape          : str - b1/b2/b3/b4/b5/publish/...
        type_evenement : str - ex. json_invalide, timeout, page_morte,
                                quarantaine, reprise_reussie
        detail         : str - texte libre (message d'erreur, contexte...)
        slug           : str|None - outil concerne, si applicable
        niveau         : str - "info" ou "erreur" (defaut "erreur")
    """
    init_memoire(path)
    db = connect(path)
    db.execute("""
        INSERT INTO run_log (run_id, etape, slug, niveau, type_evenement, detail, created_at)
        VALUES (?,?,?,?,?,?,?)
    """, (
        run_id, etape, slug, niveau, type_evenement, detail,
        datetime.now(timezone.utc).isoformat(),
    ))
    db.commit()


def increment_echecs(slug, path=None):
    """
    Incremente raw_tools.echecs pour le slug donne et retourne le nouveau
    compte. Si le slug n'existe pas dans raw_tools, ne fait rien et
    retourne 0.
    """
    migrate_raw_tools_echecs(path)
    db = connect(path)
    row = db.execute("SELECT echecs FROM raw_tools WHERE slug=?", (slug,)).fetchone()
    if row is None:
        return 0
    nouveau = (row["echecs"] or 0) + 1
    db.execute("UPDATE raw_tools SET echecs=? WHERE slug=?", (nouveau, slug))
    db.commit()
    return nouveau


def mettre_en_quarantaine(slug, path=None):
    """Met raw_tools.status a 'quarantaine' pour le slug donne."""
    migrate_raw_tools_echecs(path)
    db = connect(path)
    db.execute("UPDATE raw_tools SET status=? WHERE slug=?", ("quarantaine", slug))
    db.commit()


def stats_run(run_id, path=None):
    """
    Calcule des statistiques agregees pour un run_id donne a partir de
    run_log. Retourne un dict:
        {
          "run_id": str,
          "total": int,
          "par_etape": {etape: {"total": int, "erreurs": int}},
          "par_type": {type_evenement: int},
          "slugs_quarantaine": [slug, ...],
        }
    """
    init_run_log(path)
    db = connect(path)
    rows = db.execute(
        "SELECT etape, slug, niveau, type_evenement FROM run_log WHERE run_id=?",
        (run_id,)
    ).fetchall()

    par_etape = {}
    par_type = {}
    slugs_quarantaine = []

    for r in rows:
        etape = r["etape"] or ""
        par_etape.setdefault(etape, {"total": 0, "erreurs": 0})
        par_etape[etape]["total"] += 1
        if r["niveau"] == "erreur":
            par_etape[etape]["erreurs"] += 1

        t = r["type_evenement"] or ""
        par_type[t] = par_type.get(t, 0) + 1

        if t == "quarantaine" and r["slug"]:
            slugs_quarantaine.append(r["slug"])

    return {
        "run_id": run_id,
        "total": len(rows),
        "par_etape": par_etape,
        "par_type": par_type,
        "slugs_quarantaine": sorted(set(slugs_quarantaine)),
    }


# ---------------------------------------------------------------------------
# Juge de qualite (ajoute pour b2b_juge.py) : colonnes juge_score/juge_verdict
# sur enriched_tools + compteur de reprises sur raw_tools (garde-fou anti-boucle,
# stocke sur raw_tools car enriched_tools peut etre supprime lors d'une reprise).
# ---------------------------------------------------------------------------

def migrate_enriched_tools_juge(path=None):
    """
    Migration idempotente : ajoute juge_score (REAL) et juge_verdict (TEXT)
    a enriched_tools si absentes. Garde try/except par colonne (SQLite ne
    supporte pas IF NOT EXISTS sur ADD COLUMN).
    """
    db = init_db(path)
    for col, coltype in (("juge_score", "REAL"), ("juge_verdict", "TEXT")):
        try:
            db.execute(f"ALTER TABLE enriched_tools ADD COLUMN {col} {coltype}")
            db.commit()
        except sqlite3.OperationalError:
            pass  # colonne deja presente
    return db


def migrate_raw_tools_juge_reprises(path=None):
    """
    Migration idempotente : ajoute raw_tools.juge_reprises (INTEGER DEFAULT 0).
    Compte les reprises demandees par le juge (b2b) pour un slug -- sert de
    garde-fou anti-boucle (maximum une reprise par fiche), independant de
    raw_tools.echecs qui compte les echecs LLM de b2.
    """
    db = init_db(path)
    try:
        db.execute("ALTER TABLE raw_tools ADD COLUMN juge_reprises INTEGER DEFAULT 0")
        db.commit()
    except sqlite3.OperationalError:
        pass
    return db


def init_juge(path=None):
    """Initialise toutes les migrations necessaires au juge (b2b)."""
    init_db(path)
    migrate_enriched_tools_juge(path)
    migrate_raw_tools_juge_reprises(path)


def set_juge_verdict(slug, score, verdict, path=None):
    """
    Met a jour juge_score/juge_verdict sur enriched_tools pour slug.
    Ne fait rien si le slug n'a pas de ligne enriched_tools (ex: deja
    supprimee par une reprise precedente).
    """
    init_juge(path)
    db = connect(path)
    db.execute(
        "UPDATE enriched_tools SET juge_score=?, juge_verdict=? WHERE slug=?",
        (score, verdict, slug),
    )
    db.commit()


def get_juge_reprises(slug, path=None):
    """Retourne raw_tools.juge_reprises pour slug (0 si absent/inexistant)."""
    init_juge(path)
    db = connect(path)
    row = db.execute("SELECT juge_reprises FROM raw_tools WHERE slug=?", (slug,)).fetchone()
    if row is None or row["juge_reprises"] is None:
        return 0
    return row["juge_reprises"]


def increment_juge_reprises(slug, path=None):
    """
    Incremente raw_tools.juge_reprises pour slug et retourne le nouveau
    compte. Si le slug n'existe pas dans raw_tools, ne fait rien et
    retourne 0 (meme convention que increment_echecs).
    """
    init_juge(path)
    db = connect(path)
    row = db.execute("SELECT juge_reprises FROM raw_tools WHERE slug=?", (slug,)).fetchone()
    if row is None:
        return 0
    nouveau = (row["juge_reprises"] or 0) + 1
    db.execute("UPDATE raw_tools SET juge_reprises=? WHERE slug=?", (nouveau, slug))
    db.commit()
    return nouveau


def delete_enriched(slug, path=None):
    """
    Supprime la ligne enriched_tools (et son embedding associe) pour slug.
    Utilise par b2b_juge.py pour remettre une fiche en file de
    re-enrichissement : b2_enrichissement.py selectionne ses raw via
    `existing = staging.get_enriched(slug)` -- si existing devient None,
    b2 traite ce slug au prochain passage (meme sans --force), peu importe
    le content_hash.
    """
    db = init_db(path)
    db.execute("DELETE FROM enriched_tools WHERE slug=?", (slug,))
    db.execute("DELETE FROM tool_embeddings WHERE slug=?", (slug,))
    db.commit()


def update_enriched_name(slug, nom_corrige, path=None):
    """
    Corrige le nom affiche d'un outil. enriched_tools ne porte pas de champ
    'name' (le nom vit dans raw_tools) -- on met donc a jour raw_tools.name,
    qui est la source utilisee par export_tools.py / b2 pour construire les
    prompts et les pages publiees.
    """
    db = init_db(path)
    db.execute("UPDATE raw_tools SET name=? WHERE slug=?", (nom_corrige, slug))
    db.commit()


def iter_enriched_a_juger(path=None):
    """
    Itere les lignes enriched_tools qui n'ont jamais ete jugees
    (juge_verdict IS NULL) ou dont le contenu a change depuis le dernier
    jugement (pas de moyen direct de tracer 'juge_content_hash' sans
    colonne supplementaire -- b2b_juge.py compare content_hash courant vs
    le content_hash au moment de l'ecriture enriched, qui est deja mis a
    jour par b2 a chaque nouvel enrichissement ; donc juge_verdict NULL
    couvre le cas 'jamais juge' et le cas 'juste re-enrichi apres reprise'
    puisque delete_enriched() efface juge_verdict avec la ligne entiere).
    """
    init_juge(path)
    db = init_db(path)
    for row in db.execute(
        "SELECT * FROM enriched_tools WHERE juge_verdict IS NULL ORDER BY slug"
    ):
        yield dict(row)
