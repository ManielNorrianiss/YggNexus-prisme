# -*- coding: utf-8 -*-
"""
staging.py - SQLite local pour le pipeline B1/B2.
Tables: raw_tools, enriched_tools, tool_embeddings.

CHEMIN PAR DEFAUT: variable d'env STAGING_DB_PATH, sinon prisme/staging.db.
Sur Windows, SQLite peut planter sur un lecteur reseau ou partage.
Si necessaire, definir STAGING_DB_PATH vers un chemin local (ex: C:/staging.db).
"""
import json
import os
import sqlite3
from pathlib import Path

_PRISME_DIR = Path(__file__).resolve().parent
_DEFAULT_DB = Path(os.environ.get("STAGING_DB_PATH", str(_PRISME_DIR / "staging.db")))


def connect(path=None):
    """Retourne une connexion SQLite avec row_factory dict-like."""
    db_path = str(path or _DEFAULT_DB)
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    return db


def init_db(path=None):
    """Cree les tables si elles n'existent pas encore."""
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
    db.commit()
    return db


def replace_tool_categories(tool_slug, rows, path=None):
    """Delete existing rows for tool_slug then insert new rows atomically."""
    db = init_tool_categories(path)
    db.execute("DELETE FROM tool_categories WHERE tool_slug=?", (tool_slug,))
    for r in rows:
        db.execute("""
            INSERT INTO tool_categories
                (tool_slug, category_slug, is_primary, confidence,
                 is_unclassified, classified_at, content_hash)
            VALUES (?,?,?,?,?,?,?)
        """, (
            tool_slug,
            r.get("category_slug", ""),
            r.get("is_primary", 0),
            r.get("confidence", 0.0),
            r.get("is_unclassified", 0),
            r.get("classified_at", ""),
            r.get("content_hash", ""),
        ))
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
