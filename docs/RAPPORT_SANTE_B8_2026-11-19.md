# Rapport de santé B8 (staging.db), 2026-11-19

Source : `prisme/staging.db`, ouverte en lecture seule (`mode=ro`). Aucun réseau, aucune écriture en production. Commande : `python b8_sante.py --source staging`. Le rapport complet est écrit dans `exports/health/<date>_staging.md` (dossier ignoré par git, comme les autres rapports de santé).

## Constat

| Contrôle | Problèmes |
|---|---|
| Fiches sans embedding | 0 |
| Champs SEO manquants | 0 |
| quality_score hors borne | 0 |
| Fiches non mises à jour depuis 90 jours | 415 sur 1137 |
| Fiches enrichies sans ligne brute / lignes brutes sans fiche enrichie | 0 / 0 |
| Classements vers un outil inconnu | 0 |
| Fiches sans étiquetage | 0 |
| Embeddings incohérents (JSON, dimension, orphelins) | 0 |
| Doublons : canonique absent ou boucle | 0 |
| Titres SEO en double | 13 paires |

Total : 428, dont 415 de fraîcheur (dernier enrichissement entre 2026-06-19 et 2026-07-24 pour ces fiches) et 13 titres SEO en double (ex. : artbreeder et ganbreeder, character et character-ai, codium et qodo). Ce sont probablement des doublons de fiches que la déduplication (B3) n'a pas fusionnés : à vérifier à la main.

## Ce qui cassait et ce qui a changé

- `--dry-run` plantait sur la console Windows (UnicodeEncodeError sur la coche du rapport) : la sortie est maintenant forcée en UTF-8.
- Le script ne lisait que Supabase et le site en ligne. Nouvelle option `--source staging` (défaut inchangé : `supabase`, donc la tâche de nuit `run_nightly.py` n'est pas touchée), avec six contrôles propres à staging.db.
- Le rapport du jour contre la production (`exports/health/2026-11-19.md`, produit par la tâche de nuit) donnait 0 problème sur 1004 pages : rien n'y cassait.

## Essais

`prisme/tests/test_b8_sante.py` : 11 essais (contrôles purs, lecture sur une base temporaire, refus d'écriture, rapport suffixé). Suite `prisme/tests` : 164 réussis, 1 échec qui existait avant (`test_b2_parallelisation`, lié à `llm_local.py` modifié hors de cette nuit).
