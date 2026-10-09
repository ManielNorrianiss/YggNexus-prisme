# Plan — communauté Reddit YggNexus

*Créé le 2026-07-09. Décisions de Josué : positionnement thématique neutre · objectif trafic vers yggnexus.com · langue anglaise · exécution déléguée à un agent sonnet.*

---

## 1. Vision

Bâtir une communauté Reddit sur la **découverte d'outils IA** — pas une vitrine de marque. YggNexus s'y installe comme la ressource de référence, de la même façon qu'un guide de voyage devient l'autorité d'un forum de voyageurs : on aide d'abord, la marque suit.

Règle d'or Reddit (90/10) : 90 % de participation qui aide, maximum 10 % qui pointe vers le site. Toujours divulguer l'affiliation (« I run yggnexus.com »). Jamais de faux comptes, jamais la même publication recopiée dans plusieurs communautés.

## 2. Deux volets

### Volet A — notre subreddit (l'actif long terme)
Créer un subreddit thématique. Candidats de nom (vérifier la disponibilité au moment de créer) :
1. **r/AIToolFinder** — colle à l'intention de recherche (« find the right AI tool », le slogan du site)
2. r/FindAITools
3. r/AIToolDiscovery

Repli si tout est pris : r/YggNexus (marque), mais seulement en dernier recours.

### Volet B — présence dans les communautés existantes (le carburant)
Le subreddit ne grandit pas seul. Le trafic initial vient de la participation dans les communautés établies : grandes communautés grand public (r/ChatGPT, r/artificial), communautés de praticiens (r/LocalLLaMA, r/AIEngineer), communautés de bâtisseurs (r/microsaas, r/nocode, r/SideProject). L'agent d'exécution devra lire les règles de chacune avant toute publication — la plupart restreignent la promotion directe.

## 3. Phases

### Phase 0 — fondation (semaine 1) — actions de Josué + agent
- [ ] Josué : choisir/valider le compte Reddit (un compte avec historique vaut mieux qu'un compte neuf ; si neuf, 2-3 semaines de participation avant toute création)
- [ ] Créer le subreddit (nom validé, description, règles, bannière/icône à partir des logos YN dans `D:\Emperor\YggNexus\`)
- [ ] Rédiger les règles de la communauté (anti-pourriel, divulgation obligatoire pour les créateurs d'outils, un fil hebdo dédié à l'auto-promotion pour canaliser)
- [ ] Publication épinglée de bienvenue + 5-10 publications de fond pour que la communauté n'ait pas l'air vide

### Phase 1 — amorçage (semaines 2-6)
- [ ] Cadence : 3-4 publications/semaine dans notre subreddit. Formats qui marchent : comparatifs (X vs Y — le site a déjà /compare), « les 5 meilleurs outils pour [tâche précise] », « quel outil pour... » (questions ouvertes), trouvailles de la semaine (le pipeline ajoute des outils chaque nuit — matière première gratuite)
- [ ] Participation quotidienne dans les communautés du volet B : répondre aux questions « which tool should I use for X » — la recherche sémantique d'YggNexus donne la réponse en 10 secondes, c'est notre avantage déloyal
- [ ] Mention du site seulement quand elle répond vraiment à la question, avec divulgation
- [ ] Fil hebdo récurrent dans notre subreddit : « Tool of the Week » ou « What are you building with? »

### Phase 2 — croissance (mois 2-3)
- [ ] Boucle site ↔ Reddit : bandeau ou pied de page sur yggnexus.com qui invite à la communauté ; les meilleures discussions Reddit inspirent des pages du site
- [ ] Recruter 1-2 modérateurs parmi les membres actifs
- [ ] Publications riches : petites analyses tirées des données du catalogue (1000+ outils, scores, étiquettes — personne d'autre n'a ça)
- [ ] AMA ou fil « I indexed 1000+ AI tools, ask me anything »

### Phase 3 — conversion (mois 3+)
- [ ] Mesurer : trafic référent Reddit dans Vercel Analytics (déjà branché), croissance des membres, taux de publications qui ne viennent pas de nous
- [ ] Ajuster la cadence selon ce qui prend
- [ ] Seulement rendu ici : liens plus assumés vers le site (fiches, comparatifs) dans notre propre subreddit

## 4. Garde-fous

- Jamais d'automatisation de publication directe sur Reddit sans validation de Josué — chaque publication est approuvée avant d'être soumise
- Ton : utile, humble, sans jargon marketing. On répond comme un passionné qui connaît son catalogue, pas comme un vendeur
- Un seul compte, affiliation divulguée. La réputation du compte est un actif au même titre que le domaine
- Si une communauté interdit toute mention de site, on participe quand même — le profil du compte pointe vers yggnexus.com

## 5. Indicateurs (revue mensuelle)

| Indicateur | Cible 3 mois |
|:---|:---|
| Membres du subreddit | 300-500 |
| Publications/semaine non issues de nous | 3+ |
| Visites référées par Reddit (Vercel) | tendance croissante |
| Karma du compte | 1000+ |

## 6. Prompt de reprise pour l'agent d'exécution

> Lis `D:\Emperor\YggNexus\docs\PLAN_COMMUNAUTE_REDDIT.md`. On exécute la phase 0 : vérifie la disponibilité des noms de subreddit candidats, rédige la description, les règles de la communauté et les 10 premières publications de fond (en anglais, ton utile et humble, aucun ton vendeur). Tout est soumis à Josué pour approbation avant publication — rien ne part sur Reddit sans son OK. Contexte produit : yggnexus.com, répertoire de 1000+ outils IA, recherche sémantique, comparatifs, EN/FR.

