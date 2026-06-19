# Prompt de reprise — YggNexus (mis a jour 2026-06-18)

> Copie-colle ce bloc dans une nouvelle conversation Cowork (space Emperor, branche sur D:\Emperor) pour continuer le projet sans recharger tout le contexte.

---

Reprends le projet YggNexus.com avec moi.

Avant de repondre, lis tes memoires YggNexus : `yggnexus-repos`, `yggnexus-pipeline-execution`, `yggnexus-etat`. Elles contiennent l'architecture et l'etat a jour — pas besoin que je reexplique.

## Etat actuel (2026-06-18)
- Catalogue : 22 outils publies sur https://www.yggnexus.com, tous avec fiche enrichie, embedding 768d, categories et alternatives (B5).
- Taxonomie : 6 categories (ai-writing, automation, ai-images, data-scraping, productivity, no-code).
- Frontend complet deploye sur Vercel : pages tools, categories, best, compare (X vs Y), tools/[slug]/alternatives, automations. Sitemap SEO complet (130+ URL).
- Deux repos : frontend = github.com/ManielNorrianiss/YggNexus (Vercel), pipeline = github.com/ManielNorrianiss/YggNexus-prisme.
- Le pipeline B1->B5 tourne sur ma machine Windows (Supabase et PyPI sont bloques dans le bac a sable Cowork) : je lance les commandes, tu guides UNE etape a la fois.

## Pistes pour la suite (on priorise ensemble)
- Grossir encore le catalogue (ajouter des sources, relancer B1->B5).
- Coder B6 (generation SEO de contenus longs) et B8 (sante) — pas encore ecrits.
- Qualite donnees : elevenlabs mal classe (envisager une categorie ai-audio) ; n8n apparait dans /best/data-scraping ; quality_score / ratings vides dans best & compare.
- Automatiser la chaine de nuit (run_nightly.py) + recherche semantique.

## Facon de travailler
Francais quebecois, ton humain, resultat avant le chemin, UNE etape a la fois avec des boutons (jamais de texte libre a remplir), etapes techniques en bullets puis une analogie du quotidien. Delegue les taches lourdes a des sous-agents. Routine de fin d'etape : mettre a jour la memoire + produire un nouveau prompt de reprise.

Confirme que tu as le contexte (via tes memoires), puis propose-moi la prochaine etape.

---
