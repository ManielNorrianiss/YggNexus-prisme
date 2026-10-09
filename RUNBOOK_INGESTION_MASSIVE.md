# YggNexus — Ingestion massive (objectif 2 000–5 000 outils, 100 % local)

Paramètres actés : cible **2 000–5 000** outils · sources **GitHub awesome-lists +
sitemaps d'annuaires + Product Hunt** · **gratuit/local seulement** (Ollama, pas
de Jina payant). Tout s'exécute sur Windows. On avance **par vagues** : jamais
2 000 outils d'un coup.

Conséquence actée : la recherche sémantique calcule l'embedding de requête via
Jina côté Vercel — en local-only, elle reste en **repli texte** (déjà géré). Les
fiches sont indexées normalement ; on rebranchera la sémantique plus tard si tu veux.

---

## PHASE 1 — Découverte (GitHub awesome-lists)  [PRÊT]

```bat
cd prisme
python b0_discovery.py --dry-run     REM compte par liste, rien écrit
python b0_discovery.py               REM -> data/candidates.json
python b0_to_sources.py --check-supabase --dry-run   REM combien de NOUVEAUX
python b0_to_sources.py --check-supabase             REM -> data/sources_new.json (à relire)
```

`data/sources_new.json` = les nouvelles entrées au format sources.json (slug, name,
website_url, categories vides — b4 classera). **Relis-le**, retire les évidentes
non-pertinentes, puis fusionne dans sources.json :

```bat
REM option simple : fusion directe
python b0_to_sources.py --check-supabase --append
```

Estimation Phase 1 : ~1 500–2 500 nouveaux outils selon les listes qui répondent.

---

## PHASE 2 — Annuaires (sitemaps : Futurepedia, Toolify, TAAFT)  [À CONSTRUIRE]

À bâtir après que la Phase 1 ait validé la chaîne. Méthode propre : lire le
`sitemap.xml` de chaque annuaire (liste toutes les fiches), visiter chaque fiche,
extraire le lien sortant officiel + le nom. TAAFT = anti-bot agressif (peut exiger
Claude in Chrome). Product Hunt = API GraphQL (jeton requis). **Dis-moi quand la
Phase 1 tourne** : j'inspecte la structure live d'un annuaire et j'écris le
moissonneur sur mesure (pas de scraper à l'aveugle).

---

## INGESTION PAR VAGUES (le cœur)

Ne lance jamais tout sources.json d'un coup. Procède par tranches avec `--limit`.
Pour une vague (ex. 300 outils) :

```bat
cd prisme
python b1_collecte.py --limit 300        REM fetch des sites -> staging (raw)
python b2_enrichissement.py              REM LLM Ollama : desc, pros/cons, FAQ (LENT)
python b3_dedup.py                       REM fusionne les doublons
python b4_classification.py              REM classe dans les 9 catégories (+ overrides)
python b5_liens.py                       REM alternatives (similarité)
python b6_pages.py                       REM SEO pages
python b6_seo.py                         REM SEO outils
python publier_nouveaux.py               REM PROMOTION draft->published (SINON export ignore les nouveaux !)
python b8_sante.py --no-crawl            REM audit santé (rapport, lecture seule)
python export_tools.py                   REM staging -> data/tools.json
python publish.py --dry-run
python publish.py                        REM UPSERT Supabase + revalidation
python collect_logos.py --only-missing   REM logos (DuckDuckGo->Google) des nouveaux
python sync_categories.py                REM aligne les catégories
```

Sites bloqués (403/Cloudflare) au B1 : ajoute-les à `seed_raw.py` puis
`python b2_enrichissement.py --only <slug>`.

### Embeddings (local-only)
`publish_embeddings.py` / `embed_search_jina*.py` utilisent Jina (PAYANT) — **on
ne les lance PAS**. La recherche reste en mode texte. Pour des embeddings 100 %
locaux plus tard : modèle Ollama (nomic-embed-text) -> pgvector. À câbler dans une
étape dédiée si tu veux la sémantique.

### Traduction FR des nouvelles fiches
Après chaque grosse vague :
```bat
python dump_en_content.py                REM EN -> data/i18n_source_en.json
```
-> donne-moi le fichier : je traduis (short_desc, description, pros/cons, FAQ,
pricing_note, SEO) en FR québécois -> data/translations_fr.json -> tu lances :
```bat
python merge_pricing_fr.py               REM si pricing_note traités à part
python publish_translations.py
```

---

## TEMPS MACHINE (estimation, local Ollama)

Le goulot = B2 (enrichissement LLM), ~5–15 s/outil selon le modèle.

| Palier | B1 fetch | B2 enrichissement | Réaliste (étalé) |
|-------:|---------:|------------------:|------------------|
| 300    | ~6 min   | 25–75 min         | 1 soirée         |
| 1 000  | ~20 min  | 1,5–4 h           | 1 journée        |
| 2 000  | ~40 min  | 3–8 h             | 2–3 jours par vagues |
| 5 000  | ~1,5 h   | 7–20 h            | 1–2 semaines par vagues |

Conseils : vagues de 300–500, le soir/la nuit (run_nightly.py peut enchaîner) ;
`b1` saute les inchangés (hash) donc c'est reprenable ; surveille la qualité B4
(taxonomie fermée à 9 catégories — beaucoup d'outils tomberont en "unclassified",
c'est normal, on affine les overrides).

---

## FICHIERS B0 (neufs, à committer dans le repo pipeline)

- `prisme/b0_discovery.py` — moissonneur GitHub awesome-lists -> candidates.json
- `prisme/b0_to_sources.py` — candidates -> sources_new.json (dédup + slugs)

```bat
cd ..
del .git\index & git reset
git add prisme\b0_discovery.py prisme\b0_to_sources.py
git commit -m "feat(b0): decouverte massive (GitHub awesome-lists) + merge vers sources.json"
git push
```
