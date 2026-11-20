# Stratégie de liens entrants et d'autorité de domaine

*Ouvrage Sunday 253. Rédigé le 2026-11-19. Chaque fait externe porte son adresse et sa date de lecture (2026-11-19). Rien n'a été soumis, envoyé ni publié : tout geste vers un tiers est marqué **[À Josué]**.*

## 1. Point de départ (ce que le dépôt sait déjà)

- Le kit stratégique (`KIT_STRATEGIQUE_YGGNEXUS.md`, §6) note : aucune audience, **aucun lien entrant, aucune autorité de domaine** ; le BHAG de la boucle SEO passe par l'autorité. La ligne « stratégie backlinks / autorité » y est au 4e trimestre, priorité 1.
- Le plan de référencement (`PLAN_REFERENCEMENT_YGGNEXUS.md`, phase B) prévoit neuf cibles, étalées à 2-3 par semaine. Le kit de soumission est prêt depuis le 2026-07-02 (`SUBMISSION_KIT.md`), mais `registre_soumissions.md` montre **les neuf cibles encore « à faire »** (ouvrage 129).
- Le site a déjà : un sitemap avec hreflang en/fr, une clé IndexNow, un fichier de vérification Google dans `frontend/public`, des comparatifs (`/compare`), 1003 outils publiés.
- Le plan Reddit (`PLAN_COMMUNAUTE_REDDIT.md`) couvre la communauté ; il n'est pas répété ici.
- Atout propre à YggNexus : des données croisées (outils, alternatives, agents, skills, serveurs MCP) que les annuaires classiques n'ont pas. C'est la matière des liens qu'on **mérite**, plutôt que ceux qu'on demande.

## 2. Règles du jeu (ce que Google permet et interdit)

- Acheter ou vendre des liens pour le classement, les échanges de liens à grande échelle, les campagnes de billets invités ou d'articles à grande échelle, et les liens d'annuaires de faible qualité sont des **spams de liens** (https://developers.google.com/search/docs/essentials/spam-policies, lu 2026-11-19). Un lien payant est acceptable s'il porte `rel="sponsored"` ou `rel="nofollow"`.
- Google documente trois attributs : `sponsored`, `ugc`, `nofollow`, traités comme des signaux et non des garanties (https://developers.google.com/search/docs/crawling-indexing/qualify-outbound-links, lu 2026-11-19). Beaucoup de liens d'annuaires et de forums seront donc de peu de poids SEO direct : leur valeur est surtout l'indexation, le trafic et la découverte. Le poids exact de chaque plateforme n'a **pas été vérifié** cette nuit.
- Conséquence : la stratégie évite l'achat, les échanges, les billets invités en série et la soumission à des centaines d'annuaires obscurs. On vise peu de liens, de bonne provenance, étalés.

## 3. Le plan, dans l'ordre

Effort en heures de travail humain ; « Prisme » ou « Emperor » = faisable sans Josué.

### Étape 0. Mesurer le point de départ (semaine 1, 1 h) [À Josué : ouvrir la console]

1. Dans Google Search Console, relever le rapport « Liens » : sites référents, pages les plus liées, texte d'ancrage. Limites du rapport : échantillon, 1000 lignes par tableau, il n'indique pas quels liens sont nofollow (https://support.google.com/webmasters/answer/9049606, lu 2026-11-19).
2. Noter le chiffre de départ dans un fichier daté (domaines référents, pages indexées, clics, impressions, recherches de la marque).
3. Choisir un outil tiers d'autorité (la « note de domaine » est une mesure de fournisseurs privés, pas de Google) et le relever une fois par mois pour la tendance seulement. Outil choisi : **à décider par Josué** (gratuit de préférence).

### Étape 1. Les liens qui t'appartiennent déjà (semaines 1-2, 2 h) [À Josué]

Liens depuis des profils et sites que Josué contrôle : profil GitHub et dépôt public du projet, profil LinkedIn, profils de créateur sur les plateformes déjà utilisées, signature de courriel. Effort faible, risque nul, et ces pages servent de preuve d'identité pour les inscriptions suivantes.

### Étape 2. Les neuf annuaires cibles (semaines 2-6, 3 h au total) [À Josué]

Reprendre `SUBMISSION_KIT.md` et le plan B2 : Product Hunt, There's An AI For That, AlternativeTo, Toolify, Futurepedia, SaaSHub, Uneed, MicroLaunch, Show HN. Cadence : 2 à 3 par semaine, jamais un mur d'un jour. Points de vigilance tirés des lectures :

- **Show HN** : les règles excluent les « blogs, pages d'inscription, infolettres, **listes** » et les pages d'atterrissage ; le projet doit être essayable par chacun (https://news.ycombinator.com/showhn.html, lu 2026-11-19). Un catalogue peut être classé comme liste. À réserver pour un objet concret (le serveur MCP de l'étape 4 ou le jeu de données de l'étape 5), sinon passer par une soumission ordinaire.
- **AlternativeTo** : la page « à propos » dit que les fiches et recommandations viennent des utilisateurs plutôt que des éditeurs (https://alternativeto.net/about/, lu 2026-11-19). La procédure de soumission par le créateur n'a pas été trouvée : **non vérifié**, lire leurs règles avant de s'inscrire.
- Product Hunt : le guide existe (https://help.producthunt.com/en/collections/19793093-launch-guide) mais ses articles n'ont pas été lus ; le statut dofollow ou nofollow des liens **n'est pas vérifié**. Le plan existant mentionne « DR91 » sans source : à confirmer.
- Le texte du kit a été produit par un modèle local et reste générique (« bridge AI tools into workflows ») : le relire et le préciser avant de coller.
- Compléter `registre_soumissions.md` à chaque soumission (date, URL de la fiche). Il est vide aujourd'hui.

### Étape 3. Faire de YggNexus une source citée : le serveur MCP du catalogue (mois 2-3, 8 à 16 h de code) [Emperor ou Claude Code, puis À Josué pour publier]

Idée à valider : un petit serveur MCP public qui expose la recherche du catalogue (outil, alternatives, recettes). L'enregistrement dans le registre officiel exige de prouver la propriété de l'espace de noms (GitHub ou domaine) et le registre est destiné aux agrégateurs qui le reprennent (https://modelcontextprotocol.io/registry/about, lu 2026-11-19 ; en préversion). Un serveur listé là, dans l'awesome-list de référence (https://github.com/punkpeye/awesome-mcp-servers, règles de contribution non lues) et dans les places de marché MCP donne des mentions pertinentes, dans la niche même du site. Risque : le registre est en préversion (réinitialisations possibles). C'est un ouvrage de code à part, à créer si Josué retient l'idée.

### Étape 4. Les actifs qui attirent les liens (mois 2-4, 10 à 20 h, surtout Prisme)

- Un jeu de données ouvert (CSV ou JSON, licence claire) de l'état du catalogue, avec une page « méthodologie ». Les chercheurs, les infolettres et les rédacteurs citent les données.
- Deux ou trois analyses chiffrées tirées du catalogue (par exemple la répartition des prix, des outils nouveaux par mois, les catégories les plus saturées), publiées sur le site puis résumées sur Reddit selon le plan existant. Chaque chiffre doit venir de la base, avec la date.
- Une page de comparatifs et d'alternatives à forte valeur (`/compare`, déjà en place) : les pages qui répondent vraiment à une question gagnent des liens naturels ; ne pas en produire en masse sans contrôle de qualité (le kit signale lui-même le risque de pénalité sur le contenu généré en masse).

### Étape 5. Prévenir les éditeurs d'outils [À Josué, volume à décider]

Chaque fiche outil est une occasion de lien : l'éditeur peut vouloir signaler sa fiche. Option sobre : un courriel court, personnalisé, envoyé à quelques dizaines d'éditeurs dont la fiche est de bonne qualité, sans demander de lien, seulement pour qu'ils vérifient la fiche. Un badge « présent dans YggNexus » est possible, mais l'ancre doit rester neutre (nom du site) ; les règles de Google sur les liens de gadgets distribués en masse n'ont pas été relues cette nuit : **à vérifier avant de lancer**. Aucun courriel n'a été rédigé ni envoyé.

### Étape 6. Presse et infolettres du créneau (mois 4-6) [À Josué]

Liste de 20 infolettres et blogues d'outils d'IA et d'automatisation, un seul message court chacun, appuyé sur une donnée de l'étape 4. Pas de paiement. Si une publication demande de l'argent, le lien doit porter `rel="sponsored"` (voir §2).

## 4. Calendrier résumé

| Période | Livrable | Qui | Effort |
|---|---|---|---|
| Semaine 1 | Étape 0 : chiffres de départ | Josué | 1 h |
| Semaines 1-2 | Étape 1 : profils et dépôt | Josué | 2 h |
| Semaines 2-6 | Étape 2 : 9 annuaires, registre tenu | Josué | 3 h |
| Mois 2-3 | Étape 3 : serveur MCP (si retenu) | Emperor/Claude Code, puis Josué | 8-16 h |
| Mois 2-4 | Étape 4 : jeu de données et analyses | Prisme + relecture Josué | 10-20 h |
| Mois 3-6 | Étapes 5 et 6 : éditeurs et infolettres | Josué | 4-8 h |

Les efforts sont des estimations de cette nuit, non mesurées.

## 5. Mesure (mensuelle, une page)

| Indicateur | Source | Cible proposée à 90 jours (estimation, non sourcée) |
|---|---|---|
| Domaines référents | Search Console, rapport « Liens » | 15 à 30 |
| Pages indexées | Search Console | tout le sitemap utile |
| Recherches de la marque | Search Console, requêtes | première apparition |
| Trafic référent | Vercel Analytics (déjà branché) | tendance à la hausse |
| Note de domaine tierce | outil choisi à l'étape 0 | tendance seulement |
| Annuaires « en ligne » | `registre_soumissions.md` | 9 sur 9 |

Règle de décision à 90 jours : si les domaines référents n'augmentent pas malgré les annuaires, remonter l'effort sur les étapes 3 et 4 (actifs citables) plutôt que d'ajouter des annuaires.

## 6. À éviter

Achat de liens ; échanges de liens massifs ; billets invités en série ; annuaires de faible qualité ; ancres avec mots-clés répétés ; toute soumission en rafale ; faux comptes (aussi interdits par le plan Reddit).

## 7. Liste des gestes « À Josué »

1. Relever le rapport « Liens » de Search Console et choisir l'outil de note de domaine (étape 0).
2. Poser les liens de ses propres profils (étape 1).
3. Soumettre aux neuf annuaires, 2 à 3 par semaine, après relecture du kit (étape 2).
4. Décider si le serveur MCP du catalogue devient un ouvrage (étape 3) et publier dans les registres.
5. Valider le jeu de données ouvert avant publication (étape 4).
6. Décider du volume de courriels aux éditeurs et envoyer (étape 5) ; choisir les infolettres (étape 6).
