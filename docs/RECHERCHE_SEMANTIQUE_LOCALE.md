# Recherche semantique locale (pont pgvector) -- etat et plan

Contexte : la recherche semantique du frontend (`searchToolsSemantic` dans
`frontend/lib/queries.ts`) embed la requete via l'API Jina (`jina-embeddings-v3`,
1024 dim, `task=retrieval.query`) puis appelle la RPC Supabase `match_tools`.
Jina est payant au-dela du plan gratuit -- ce chantier vise a permettre un
repli 100% local (nomic-embed-text via Ollama, deja utilise par le Prisme
pour B2/B5) sans dependre de Jina.

## Ce qui existe deja (avant ce chantier)

- `embeddings` (table Supabase, polymorphe) : `entity_type`, `entity_id`,
  `model`, `embedding vector(768)` (portee a 768 par
  `database/migration_embeddings_dim_768.sql`), `content_hash`. Alimentee par
  `publish_embeddings.py` a partir de `staging.iter_embeddings()`
  (`tool_embeddings` en SQLite local, produites par `llm_local.embed()` avec
  `MODELE_EMBED = nomic-embed-text`).
- `search_embeddings` (table Supabase dediee) : `tool_id`, `embedding
  vector(1024)`, alimentee par `embed_search_jina.py` via l'API Jina. C'est
  la table interrogee par la RPC `match_tools` actuelle (voir
  `database/migration_search_embeddings_jina.sql`).
- RPC `match_tools(query_embedding vector(1024), match_count int, match_threshold
  double precision)` : coeur de la recherche semantique en production
  aujourd'hui, mais couplee a Jina cote requete (embedding de la requete
  utilisateur calcule serveur Next.js via l'API Jina, `JINA_API_KEY`).

## Ce qui a ete ajoute par ce chantier

1. `database/migration_pgvector_search.sql` (idempotent) :
   - `create extension if not exists vector` (deja actif, no-op si deja fait).
   - Index HNSW cosinus sur `embeddings.embedding` (`idx_embeddings_hnsw_cosine`).
   - Nouvelle RPC `search_tools_semantic(query_embedding vector(768), match_count
     int default 10)` qui interroge directement `embeddings` filtre sur
     `entity_type='tool'` et `model='nomic-embed-text'`, jointe a `tools`
     (uniquement `status='published'`). Retourne `slug, name, short_desc,
     quality_score, similarity`.
   - Choix de design : PAS de nouvelle colonne/table. `embeddings` porte deja
     une colonne pgvector 768d alimentee a chaque run nightly (etape
     `embeddings` avant `liens`, cf. `run_nightly.py`) -- reutiliser cette
     table evite une duplication de donnees et un flux d'alimentation
     supplementaire a maintenir.
2. `publier_embeddings_pgvector.py` : script dedie qui pousse les embeddings
   nomic 768d du staging vers `embeddings` (Supabase), par lots (upsert
   `on_conflict=entity_type,entity_id,model`), avec `--dry-run`, `--limit`,
   `--only`. Fonctionnellement proche de `publish_embeddings.py` (meme
   source, meme table cible) -- garde separe pour ce chantier afin de
   pouvoir republier une portion cible (`--only`/`--limit`) et verifier
   independamment du run nightly complet pendant la transition.

Cote embedding des OUTILS (les "documents"), le pont est donc complet et
testable des maintenant : `python publier_embeddings_pgvector.py --dry-run`
puis, une fois le SQL colle dans Supabase, un appel direct a la RPC :

```sql
select * from search_tools_semantic(
    (select embedding from embeddings where entity_type='tool' and model='nomic-embed-text' limit 1),
    5
);
```

## Ce qui reste a decider (Josue)

Le maillon manquant est l'embedding de la **requete utilisateur** (le texte
tape dans la barre de recherche), cote frontend. `match_tools` actuel
resout ce probleme en appelant l'API Jina depuis le serveur Next.js
(Vercel). Pour une requete nomic-embed-text locale, il n'y a **pas
d'equivalent direct disponible depuis Vercel** : Ollama tourne sur la
machine Windows de Josue, pas accessible publiquement depuis l'infra Vercel
sans exposer un service.

Trois options, aucune n'est cochee -- c'est un choix produit/infra a
trancher, pas une decision technique implicite :

### Option A -- petit point d'acces local expose (tunnel/edge léger)
Un petit service (FastAPI/Flask minimal, ou Ollama lui-meme) tourne sur la
machine de Josue ou un VPS pas cher, expose via un tunnel (Cloudflare
Tunnel, Tailscale Funnel, ngrok payant pour la stabilite) ou un vrai
deploiement. `searchToolsSemantic` appelle ce point d'acces au lieu de
Jina pour obtenir l'embedding de la requete (768d, nomic), puis appelle
`search_tools_semantic` au lieu de `match_tools`.
- Avantage : recherche semantique complete, temps reel, gratuite (pas de
  cout API).
  Inconvenient : depend de la disponibilite de la machine/tunnel de Josue --
  si elle est eteinte, la recherche semantique tombe (le frontend a deja un
  repli texte ILIKE, donc pas de panne totale, mais degradation).

### Option B -- embeddings de requetes precalcules pour les suggestions populaires
Pas de calcul d'embedding en temps reel. On precalcule (offline, via le
Prisme) les embeddings d'un ensemble de requetes/termes populaires
(categories, tags, noms d'outils frequents) et on les stocke (nouvelle
petite table ou fichier JSON publie). Le frontend fait un rapprochement
ILIKE/`pg_trgm` sur ces termes precalcules pour choisir l'embedding le plus
proche, puis appelle la RPC avec cet embedding existant.
- Avantage : zero dependance externe, zero cout, marche meme machine
  Windows eteinte. Inconvenient : ne couvre pas les requetes libres/longue
  traine -- degrade vers la recherche texte pour tout le reste.

### Option C -- API d'embedding gratuite tierce (ex. HuggingFace Inference API)
Remplacer Jina par un fournisseur gratuit (HuggingFace Inference API,
modele compatible nomic ou proche) pour l'embedding de requete uniquement,
en gardant `search_tools_semantic`/768d cote outils. Necessite de verifier
la dimension du modele choisi correspond a 768 (ou d'ajouter un mapping/
projection si different), et les limites de taux du plan gratuit.
- Avantage : simple a brancher (meme forme que le code Jina existant,
  juste changer l'endpoint/modele). Inconvenient : depend encore d'un tiers
  externe (juste gratuit au lieu de payant) -- meme classe de risque que
  Jina (quota, disponibilite, changement de tarification).

## Recommandation (a valider, pas une decision prise)

Court terme : Option C est la plus rapide a brancher sans nouvelle
infrastructure a maintenir (juste un changement d'endpoint dans
`searchToolsSemantic`). Moyen terme, si Josue veut vraiment zero dependance
externe : Option A avec Cloudflare Tunnel (gratuit, stable) est la plus
robuste, mais ajoute une dependance de disponibilite machine. Option B est
un bon complement (suggestions/autocomplete) quel que soit le choix final
pour la recherche libre, car elle ne remplace pas la recherche a texte
libre — elle l'ameliore juste pour les cas frequents.

Aucune de ces options n'a ete implementee cote frontend : le frontend n'a
pas ete touche par ce chantier (consigne explicite). Ce document sert de
base de decision pour la prochaine etape.
