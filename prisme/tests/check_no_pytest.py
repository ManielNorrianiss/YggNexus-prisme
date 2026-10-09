# -*- coding: utf-8 -*-
"""
check_no_pytest.py - harnais de secours (stdlib uniquement).

But : verifier les tests quand pytest n'est pas installable (ex : PyPI bloque
dans le sandbox). En usage normal, lance plutot `pytest` depuis prisme/.

Il injecte un stub minimal de `pytest` (decorateur fixture no-op), applique
manuellement le seul monkeypatch necessaire (staging.get_tool_categories),
fournit de vraies implementations minimales des fixtures `monkeypatch` et
`tmp_path` (assez pour les tests de ce depot), puis execute toutes les
fonctions test_* (a zero argument, ou acceptant monkeypatch/tmp_path).
"""
import shutil
import sys
import tempfile
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
import test_b2_parallelisation
import test_staging_memoire
import test_b2_auto_correction
import test_memoire_prisme
import test_b2b_juge
import test_llm_local_routage
import test_b5_liens_raisons
import test_publier_embeddings_pgvector

modules = [test_export_tools, test_b6_seo, test_b4_classification, test_b6_pages,
           test_b2_parallelisation, test_staging_memoire, test_b2_auto_correction,
           test_memoire_prisme, test_b2b_juge, test_llm_local_routage,
           test_b5_liens_raisons, test_publier_embeddings_pgvector]


# --- mini implementation de la fixture pytest `monkeypatch` ---
class _MiniMonkeypatch:
    """Sous-ensemble suffisant de pytest.monkeypatch : setattr avec
    restauration automatique apres le test."""

    def __init__(self):
        self._restaurations = []

    def setattr(self, obj, name, value):
        sentinel = object()
        ancienne = getattr(obj, name, sentinel)
        self._restaurations.append((obj, name, ancienne, sentinel))
        setattr(obj, name, value)

    def undo(self):
        for obj, name, ancienne, sentinel in reversed(self._restaurations):
            if ancienne is sentinel:
                try:
                    delattr(obj, name)
                except AttributeError:
                    pass
            else:
                setattr(obj, name, ancienne)
        self._restaurations = []


def _mini_tmp_path():
    """Cree un dossier temporaire ; le harnais le nettoie apres le test."""
    d = tempfile.mkdtemp(prefix="prisme_test_")
    return Path(d)


FIXTURES_SUPPORTEES = {"monkeypatch", "tmp_path"}

passed = failed = skipped = 0
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
        noms_requis = [p.name for p in required]

        non_supportes = [n for n in noms_requis if n not in FIXTURES_SUPPORTEES]
        if non_supportes:
            # fixture(s) non geree(s) par ce harnais minimal -> ignoree
            skipped += 1
            continue

        mp = _MiniMonkeypatch()
        tmp_dirs = []
        kwargs = {}
        for n in noms_requis:
            if n == "monkeypatch":
                kwargs[n] = mp
            elif n == "tmp_path":
                p = _mini_tmp_path()
                tmp_dirs.append(p)
                kwargs[n] = p

        try:
            fn(**kwargs)
            passed += 1
            print(f"  PASS {mod.__name__}::{name}")
        except Exception:
            failed += 1
            failures.append((mod.__name__, name, traceback.format_exc()))
            print(f"  FAIL {mod.__name__}::{name}")
        finally:
            mp.undo()
            for p in tmp_dirs:
                shutil.rmtree(str(p), ignore_errors=True)

print(f"\nResultat: {passed} passes, {failed} echecs, {skipped} ignores (fixture non geree).")
for m, n, tb in failures:
    print(f"\n--- {m}::{n} ---\n{tb}")
sys.exit(1 if failed else 0)
