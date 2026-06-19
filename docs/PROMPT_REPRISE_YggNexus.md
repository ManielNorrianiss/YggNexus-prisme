# Prompt de reprise — YggNexus (mis a jour 2026-06-18)

> Copie-colle ce bloc dans une nouvelle conversation Cowork (space Emperor, branche sur D:\Emperor) pour continuer le projet sans recharger tout le contexte.

---

Reprends le projet YggNexus.com avec moi.

Avant de repondre, lis tes memoires YggNexus : `yggnexus-repos`, `yggnexus-pipeline-execution`, `yggnexus-etat`, et `montage-windows-tronque-fichiers`. Elles contiennent l'architecture, l'etat a jour et les pieges — pas besoin que je reexplique. (Elles sont dans D:\Emperor\memory.)

## Etat actuel (2026-06-18)
- Catalogue : 22 outils publies sur https://www.yggnexus.com (fiche enrichie, embedding 768d, categories, alternatives B5).
- Taxonomie : 7 categories (ai-writing, automation, ai-images, ai-audio, data-scraping, productivity, no-code).
- Deux repos : pipeline = D:\Emperor\YggNexus (GitHub YggNexus-prisme) ; frontend = D:\Emperor\YggNexus\frontend (GitHub YggNexus, Vercel).
- Le pipeline B1->B7 tourne sur ma machine Windows (Supabase et PyPI bloques dans le sandbox Cowork) : je lance les commandes, tu guides UNE etape a la fois avec des boutons.

## Fait la derniere fois
- ETAPE 2 reclassification : creation de la categorie ai-audio ; elevenlabs deplace vers ai-audio (vieilles etiquettes effacees) ; n8n sorti de data-scraping. Verifie live (penser au cache : ?v=xxx ou Ctrl+Shift+R).

## Prochaines etapes (on priorise ensemble)
- **Bug score sur 100** : 20 des 22 outils ont un quality_score hors borne (ex perplexity 95, grammarly 95, elevenlabs 92, n8n 85) -> s'affiche "85/10" au lieu de "8.5/10". B2 note sur 100 au lieu de sur 10. A normaliser.
- Ameliorer publish.py pour revalider aussi /best/<cat> et /categories/<cat> (eviter le cache perime apres reclassification).
- Coder B6 (generation SEO contenus longs) et B8 (sante) — pas encore ecrits.
- Grossir le catalogue (nouvelles sources, relancer B1->B5). Automatiser la chaine de nuit + recherche semantique.

## Facon de travailler
Francais quebecois, ton humain, resultat avant le chemin, UNE etape a la fois avec des boutons (jamais de texte libre a remplir), zero jargon technique inutile, Underdark en touches legeres. Editer le code sous D:\ via le terminal bash (Edit/Write tronque). Verifier (JSON/tsc/import) avant de donner les commandes de push. Routine de fin d'etape : mettre a jour la memoire + produire un nouveau prompt de reprise.

Confirme que tu as le contexte (via tes memoires), puis propose-moi la prochaine etape.

---
