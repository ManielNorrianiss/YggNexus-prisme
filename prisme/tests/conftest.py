# -*- coding: utf-8 -*-
"""
conftest.py - rend le paquet prisme/ importable depuis les tests, peu importe
le repertoire d'ou pytest est lance (racine du repo ou prisme/).
"""
import sys
from pathlib import Path

PRISME = Path(__file__).resolve().parent.parent  # .../prisme
if str(PRISME) not in sys.path:
    sys.path.insert(0, str(PRISME))
