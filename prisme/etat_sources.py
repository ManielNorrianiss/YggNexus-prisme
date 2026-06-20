# -*- coding: utf-8 -*-
"""etat_sources.py — diagnostic : statut de chaque slug de sources.json dans
raw_tools (staging). Lecture seule."""
import json
from collections import Counter
import staging

NOUVEAUX = ["heygen","pika","luma-dream-machine","freepik","sudowrite",
            "otter-ai","fireflies-ai","framer","gumloop","firecrawl"]

db = staging.connect()
rows = {r[0]: r[1] for r in db.execute("SELECT slug, status FROM raw_tools").fetchall()}
print("total raw_tools:", len(rows))
print("par status:", dict(Counter(rows.values())))
print("--- 15 nouveaux ---")
for s in NOUVEAUX:
    print(f"  {s}: {rows.get(s, 'ABSENT')}")
absents = [s for s in NOUVEAUX if s not in rows]
non_pub = [s for s in NOUVEAUX if rows.get(s) not in (None, "published")]
print("--- bilan ---")
print("absents:", absents or "aucun")
print("presents mais pas published:", non_pub or "aucun")
