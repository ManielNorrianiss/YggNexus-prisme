# -*- coding: utf-8 -*-
"""
check_no_pytest.py - harnais de secours (stdlib uniquement).

But : verifier les tests quand pytest n'est pas installable (ex : PyPI bloque
dans le sandbox). En usage normal, lance plutot `pytest` depuis prisme/.

Il injecte un stub minimal de `pytest` (decorateur fixture no-op), applique
manuellement le seul monkeypatch necessaire (staging.get_tool_categories),
puis execute toutes les fonctions test_* a zero argument.
"""
import sys
import types
import inspect
import traceback
from pathlib import Path

PRISME = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PRISME))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# --- stub pytest (juste assez pour importer les modules de test) ---
stub = types.ModuleType("pytest")
def _fixture(*a, **k):
    if a and callable(a[0]):
        return a[0]
    def deco(f):
        return f
    return deco
stub.fixture = _fixture
sys.modules["pytest"] = stub

# --- monkeypatch global equivalent a la fixture autouse _no_db ---
import export_tools
export_tools.staging.get_tool_categories = lambda slug: []

import test_export_tools
import test_b6_seo
import test_b4_classification
import test_b6_pages

modules = [test_export_tools, test_b6_seo, test_b4_classification, test_b6_pages]

passed = failed = 0
failures = []
for mod in modules:
    for name in sorted(dir(mod)):
        if not name.startswith("test_"):
            continue
        fn = getattr(mod, name)
        if not inspect.isfunction(fn):
            continue
        sig = inspect.signature(fn)
        required = [p for p in sig.parameters.values()
                    if p.default is inspect.Parameter.empty
                    and p.kind in (p.POSITIONAL_OR_KEYWORD, p.POSITIONAL_ONLY)]
        if required:
            # fonction a fixtures (ex: monkeypatch) -> ignoree par ce harnais
            continue
        try:
            fn()
            passed += 1
            print(f"  PASS {mod.__name__}::{name}")
        except Exception:
            failed += 1
            failures.append((mod.__name__, name, traceback.format_exc()))
            print(f"  FAIL {mod.__name__}::{name}")

print(f"\nResultat: {passed} passes, {failed} echecs.")
for m, n, tb in failures:
    print(f"\n--- {m}::{n} ---\n{tb}")
sys.exit(1 if failed else 0)
