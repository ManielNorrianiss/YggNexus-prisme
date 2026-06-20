# -*- coding: utf-8 -*-
"""merge_pricing_fr.py - Fusionne data/pricing_notes_fr.json (slug -> pricing_note_fr)
dans data/translations_fr.json, sous tools.<slug>.pricing_note_fr, SANS toucher au
reste. A lancer sur Windows (ecriture native, pas de troncature par le montage).
Usage : python merge_pricing_fr.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TR = ROOT / "data" / "translations_fr.json"
PN = ROOT / "data" / "pricing_notes_fr.json"


def main():
    data = json.loads(TR.read_text(encoding="utf-8"))
    notes = json.loads(PN.read_text(encoding="utf-8"))
    tools = data.setdefault("tools", {})
    n = 0
    for slug, fr in notes.items():
        if not (fr or "").strip():
            continue
        entry = tools.setdefault(slug, {})
        entry["pricing_note_fr"] = fr
        n += 1
    TR.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[merge] {n} pricing_note_fr fusionnes dans {TR}")


if __name__ == "__main__":
    main()
