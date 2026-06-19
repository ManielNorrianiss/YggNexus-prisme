# Prompt de reprise — YggNexus (mis a jour 2026-06-19)

> Copie-colle ce bloc dans une nouvelle conversation Cowork (space Emperor, branche sur D:\Emperor) pour continuer le projet sans recharger tout le contexte.

---

Reprends le projet YggNexus.com avec moi.

Avant de repondre, lis tes memoires YggNexus : `yggnexus-repos`, `yggnexus-pipeline-execution`, `yggnexus-etat`, et `montage-windows-tronque-fichiers`. Elles contiennent l'architecture, l'etat a jour et les pieges — pas besoin que je reexplique. (Elles sont dans D:\Emperor\memory.)

## Etat actuel (2026-06-19)
- Catalogue : 22 outils publies sur https://www.yggnexus.com (fiche enrichie, embedding 768d, categories, alternatives B5).
- Taxonomie : 7 categories (ai-writing, automation, ai-images, ai-audio, data-scraping, productivity, no-code).
- Deux repos : pipeline = D:\Emperor\YggNexus (GitHub YggNexus-prisme) ; frontend = D:\Emperor\YggNexus\frontend (GitHub YggNexus, Vercel).
- Le pipeline B1->B7 tourne sur ma machine Windows (Supabase et PyPI bloques dans le sandbox Cowork) : je lance les commandes, tu guides UNE etape a la fois avec des boutons.

## Fait la derniere fois
- ETAPE 2 : categorie ai-audio creee ; elevenlabs -> ai-audio ; n8n sorti de data-scraping.
- ETAPE 3 : tous les quality_score ramenes sur 10 (etaient sur 100). tools.json repare (corruption NUL). Verifie live.
- B8 sante code (b8_sante.py) + branche dans run_nightly. A detecte puis on a repare 5 outils hors pipeline (make/copy-ai/midjourney/claude/apify). B8 final : 0 partout.
- Ameliorations pipeline : B1 UA navigateur+headers, seed_raw.py (sites Cloudflare), filet SEO deterministe dans export_tools, B2 --force.
- B6 v1 code (b6_seo.py) : intros de categorie -> Supabase, branche dans run_nightly. 7 categories ecrites.

## Prochaines etapes (on priorise ensemble)
- **Afficher les intros de categorie** (frontend) : B6 v1 ecrit categories.description_md mais /categories/[slug] ne l'affiche pas dans le corps (juste en meta). Petite modif frontend a faire.
- **B6 phase 2** : prose pages X vs Y / alternatives (table de stockage + frontend).
- Verifier staging.db (`PRAGMA integrity_check`) : lu comme malformed depuis le sandbox.
- Ameliorer publish.py pour revalider aussi /best/<cat> et /categories/<cat> (eviter le cache perime apres reclassification).
- Coder B6 (generation SEO contenus longs) et B8 (sante) — pas encore ecrits.
- Grossir le catalogue (nouvelles sources, relancer B1->B5). Automatiser la chaine de nuit + recherche semantique.

## Facon de travailler
Francais quebecois, ton humain, resultat avant le chemin, UNE etape a la fois avec des boutons (jamais de texte libre a remplir), zero jargon technique inutile, Underdark en touches legeres. Editer le code sous D:\ via le terminal bash (Edit/Write tronque). Verifier (JSON/tsc/import) avant de donner les commandes de push. Routine de fin d'etape : mettre a jour la memoire + produire un nouveau prompt de reprise.

Confirme que tu as le contexte (via tes memoires), puis propose-moi la prochaine etape.

---
