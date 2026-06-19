# -*- coding: utf-8 -*-
"""publier_nouveaux.py — passe en status='published' tout raw encore en
'draft' dont le slug figure dans data/sources.json. A lancer apres b1_collecte
(qui cree les nouveaux raw en draft) et AVANT export_tools, sinon l'export les
ignore. Idempotent : ne touche que les drafts."""
import json
import staging

slugs = {x["slug"] for x in json.load(open("data/sources.json", encoding="utf-8"))}
db = staging.connect()
rows = db.execute("SELECT slug, status FROM raw_tools WHERE status='draft'").fetchall()
n = 0
for slug, st in rows:
    if slug in slugs:
        staging.set_raw_status(slug, "published")
        n += 1
        print("  published:", slug)
print(f"total publies: {n} (drafts vus: {len(rows)})")
