# prisme/tests

Tests unitaires purs (aucun reseau, aucun acces a staging.db / Supabase / Ollama).
Ils couvrent les filets de securite deterministes du pipeline :

- `test_export_tools.py` : filet score /10 (echelle 0-100 -> 0-10, clamp, None) et
  filet SEO deterministe (seo_title/seo_description derives quand le LLM ne les fournit pas).
- `test_b6_seo.py` : `content_hash_for` (cache de regeneration) et le garde-fou
  anti-mince `validate_category_content` (longueurs min/max, fallbacks).
- `test_b4_classification.py` : `validate_classification` (clamp confidence, filtrage
  primary/secondary, dedup, max 2, seuil) + `taxonomy_slugs` et `content_hash_for`.

## Lancer

Normal (recommande), depuis `prisme/` :

    pytest

Si pytest n'est pas installable (ex : PyPI bloque dans un sandbox), un harnais
de secours en stdlib pur execute les memes fonctions :

    python tests/check_no_pytest.py

Note : `check_no_pytest.py` n'est PAS un fichier de test (pytest ne le collecte
pas) ; c'est juste un filet pour verifier sans pytest.
