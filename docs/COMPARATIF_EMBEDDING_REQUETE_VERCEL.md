# Embedding de la requête de recherche côté Vercel : comparatif et recommandation

*Ouvrage Sunday 141. Rédigé le 2026-11-19. Les pages externes ont été lues le 2026-11-19 (adresse indiquée à chaque fait). « Non mesuré » = pas pu être mesuré cette nuit.*

## 1. Ce que le code fait aujourd'hui

- `frontend/lib/queries.ts`, `searchToolsSemantic` : sur la page `/search` (rendue à chaque requête, `force-dynamic`), le serveur Next.js appelle `https://api.jina.ai/v1/embeddings` (modèle `jina-embeddings-v3`, `task=retrieval.query`, 1024 dimensions), puis la fonction SQL `match_tools` (EN) ou `match_tools_lang` (FR) sur les tables `search_embeddings` et `search_embeddings_fr` (vecteurs Jina 1024d des fiches).
- Aucun délai maximal, aucune mémoire tampon, aucune reprise sur l'appel Jina. Si l'appel échoue, la page attrape l'erreur et retombe sur la recherche texte (`searchTools`).
- La règle qui commande tout : **la requête doit être calculée par le même modèle que les vecteurs stockés.** Changer de modèle de requête oblige à recalculer les vecteurs des fiches (environ 1003 fiches, en EN et en FR).
- Trois espaces de vecteurs coexistent dans le dépôt : nomic-embed-text 768d (table `embeddings`, fonction `search_tools_semantic`, alimentée par le Prisme, non utilisée par le site), Jina 1024d (en production) et gte-small 384d (fonction Edge `supabase/functions/semantic-search`). Cette dernière appelle `match_tools` avec un vecteur de 384 valeurs alors que la migration Jina a fait passer `match_tools` à `vector(1024)` : elle est très probablement cassée (déduit des fichiers SQL, non vérifié en production).
- Le document `docs/RECHERCHE_SEMANTIQUE_LOCALE.md` est en partie périmé : il présente Jina comme à remplacer par nomic, mais le site tourne bien sur Jina.

## 2. Mesures faites cette nuit

Cinq requêtes réelles vers l'API Jina depuis le poste de Josué (Windows, hors Vercel), clé du projet, requêtes de 17 à 22 jetons : latence médiane **692 ms**, minimum 613 ms, maximum 2012 ms, toutes en 200, vecteurs de 1024 valeurs. La latence depuis une fonction Vercel n'est **pas mesurée** (région par défaut `iad1`, source : https://vercel.com/docs/functions/limitations, lu le 2026-11-19).

## 3. Les options

| # | Option | Coût | Latence attendue | Complexité | Risque |
|---|---|---|---|---|---|
| A | **Jina v3 tel quel** (statu quo) | Clé gratuite : limite de 100 requêtes/min et 100 000 jetons/min ; clé payante 500 requêtes/min (https://jina.ai/embeddings/, lu 2026-11-19). Prix par jeton : non vérifié (page de tarifs non lue). | 0,6 à 2 s mesuré hors Vercel | Aucune | Dépendance à un tiers sans délai maximal ; la page Jina lue ne place plus v3 parmi les modèles recommandés (v5 et v4 listés), sans avis de retrait vu : risque d'obsolescence à surveiller |
| B | **A durci** : délai de 2,5 s (`AbortSignal.timeout`), mémoire tampon des requêtes normalisées (par langue), reprise sur la recherche texte déjà en place | 0 | Identique, mais les requêtes répétées tombent à presque 0 | Faible (une trentaine de lignes, un fichier du site) | Très faible ; le gain de la mémoire tampon dépend du taux de requêtes répétées (non mesuré) |
| C | **Fonction Edge Supabase, gte-small** (`Supabase.ai.Session`) | Inclus dans Supabase (tarif de la fonction : non lu) | Non mesuré | Moyenne : nouvelle colonne 384d, recalcul de toutes les fiches, fonction SQL nouvelle | Le modèle est **anglais seulement** et tronque à 512 jetons (https://supabase.com/docs/guides/functions/ai-models, lu 2026-11-19) : mauvais pour la version française du site |
| D | **OpenAI text-embedding-3-small** | 0,02 $ par million de jetons (https://developers.openai.com/api/docs/pricing, lu 2026-11-19). À ~20 jetons par requête : 1 million de requêtes ≈ 20 M de jetons ≈ 0,40 $ ; recalcul des fiches ≈ quelques cents (calcul fait ici, jetons par fiche non mesurés) | Non mesuré | Moyenne : recalcul des fiches, nouvelle fonction SQL | Service payant (faible), nouveau fournisseur à gérer ; vecteurs 1536d natifs, réductibles via le paramètre `dimensions` (non lu cette nuit) |
| E | **Cloudflare Workers AI, bge-m3** (multilingue) | 0,012 $ par million de jetons ; 10 000 « neurons » gratuits par jour, bge-m3 = 1075 neurons par million de jetons, soit environ 9 millions de jetons gratuits par jour (https://developers.cloudflare.com/workers-ai/platform/pricing/ et https://developers.cloudflare.com/workers-ai/models/bge-m3/, lus 2026-11-19) | Non mesuré | Moyenne à élevée : compte Cloudflare à créer (geste de Josué), jeton d'API, recalcul des fiches | Dépendance à un 2e tiers ; dimension de sortie non confirmée sur la page lue |
| F | **Calcul dans la fonction Vercel** (transformers.js, petit modèle ONNX) | 0 en service, mais du temps de processeur Vercel | Non mesuré (démarrage à froid du modèle) | Élevée | Limite de 250 Mo décompressés par fonction (5 Go en bêta « large functions ») ; modèles et temps de démarrage non évalués : **non sourcé, non recommandé sans essai** |
| G | **Ollama sur le poste de Josué + tunnel** | 0 | Dépend du tunnel et du poste | Moyenne | Poste éteint = recherche sémantique morte ; inacceptable pour la production |
| H | **Vecteurs précalculés pour les requêtes fréquentes** (ancienne option B du document existant) | 0 | Très faible | Moyenne | Ne couvre pas la longue traîne ; utile seulement en complément |

Source des limites Vercel : https://vercel.com/docs/functions/limitations (lu 2026-11-19) : durée maximale 300 s (Hobby), 250 Mo décompressés, le temps d'attente d'E/S (appel d'un modèle, requête SQL) ne compte pas comme temps de processeur actif.

## 4. Recommandation

1. **Maintenant : option B** (durcir Jina). Une demi-heure de travail dans `frontend/lib/queries.ts` : délai maximal, mémoire tampon, journal des échecs. Aucun coût, aucun recalcul, aucun changement de base. Le seuil de 100 requêtes/min de la clé gratuite est loin du trafic actuel (non mesuré) ; le repli texte absorbe déjà un refus 429.
2. **Seulement si un déclencheur se présente** (avis de retrait de Jina v3, limite de la clé gratuite atteinte, tarif devenu hostile) : migrer vers **E (bge-m3, Cloudflare)** si la gratuité prime et que Josué accepte d'ouvrir un compte, sinon **D (OpenAI)** si la simplicité prime. Dans les deux cas : nouvelle table de vecteurs en parallèle, recalcul par le Prisme, bascule de la fonction SQL, puis retrait de l'ancienne table.
3. **Écarter** C (anglais seulement), F (non éprouvé), G (disponibilité). Retirer ou réparer la fonction Edge `semantic-search`, qui est probablement cassée, et corriger `docs/RECHERCHE_SEMANTIQUE_LOCALE.md` pour dire que Jina est le moteur réel.

## 5. Ce qui n'a pas été mesuré

Latence depuis Vercel ; taux de requêtes répétées ; trafic de recherche réel ; prix de Jina au jeton ; dimension exacte et qualité en français de bge-m3 ; temps de démarrage de transformers.js ; état réel de la fonction Edge en production.
