# Audit des catégories imprimées par B5, 2026-11-20

Audit en lecture seule, sans réseau. Rien n'a été écrit en production. Script rejouable : `prisme\b5_audit_categories.py`. Proposition outil par outil : `exports\b5\corrections_categories_2026-11-20.json`.

## La cause en trois phrases

Le gabarit de `b5_liens.py` imprime `tools.application_category`, un champ libre à six valeurs de type schema.org (`DeveloperApplication`, `WebApplication`, `SoftwareApplication`, `BusinessApplication`, `MultimediaApplication`, `UtilitiesApplication`), posé par le modèle local à l'enrichissement (`b2_enrichissement.py`). Ce champ n'a jamais été la catégorie du site : le site range un outil par `tool_categories` et `categories` (neuf catégories dans `taxonomy.json`, posées par `b4_classification.py`). Le champ libre ne sert qu'au JSON-LD des fiches (`frontend/lib/schema.ts`), et B5 l'a pris pour une catégorie de rangement.

## Les chiffres (1 003 outils publiés)

| Mesure | Outils | Part |
|---|---|---|
| Libellé imprimé « developer » | 412 | 41 % |
| « web » / « software » / « business » | 214 / 130 / 126 | 47 % |
| « multimedia » | 104 | 10 % |
| « utilities », « research », « education » | 15 / 1 / 1 | 2 % |
| Libellé générique (web, software, business, utilities...) : ne dit rien | 487 | 49 % |
| Libellé faux (contredit la catégorie du site, ou les signaux de l'outil) | 148 | 15 % |
| Libellé vrai mais vague (multimedia pour de la vidéo, developer pour du no-code) | 145 | 14 % |
| Libellé plausible ou concordant (rien à corriger) | 223 | 22 % |
| **Corrections proposées** | **780** | **78 %** |
| Outils sans catégorie du site | 320 | 32 % |

La catégorie du site est ici un **proxy** : `tools.json` a ses listes de catégories vides depuis le retrait du 2026-06-21, et la table `tool_categories` de production n'a pas pu être lue sans réseau. J'ai pris le classement local de `staging.db` (2026-08-05). Sur les 683 outils classés, 131 ont un libellé imprimé qui contredit leur catégorie (ElevenLabs et Runway sont « developer », Pika est « multimedia », InVideo est « software »).

Parmi les 320 outils non classés, beaucoup ne sont pas des outils : pages « à vendre », « bientôt disponible », blogues, revues, une publicité de casino. Voir « À décider ».

## Les deux voies

| | Par le code | Par les données |
|---|---|---|
| Geste | B5 imprime la catégorie principale du site, ou rien quand elle manque | on réécrit `application_category` pour les 780 outils |
| Données de production touchées | aucune | 780 lignes de `tools` sur 1 003 |
| Effet sur le site | aucun : pages, adresses, référencement identiques | le JSON-LD de ~780 fiches change ; le champ n'est pas dans les adresses |
| Tient dans le temps | oui | **non** : `publish.py` réécrit la colonne chaque nuit depuis `tools.json`, que `b2` régénère ; il faudrait corriger `staging.db` et le prompt de `b2` aussi |
| Risque | faible, testable à blanc | un nom de catégorie du site n'est pas une valeur schema.org valide : on dégrade les données structurées |
| Ce qu'il faut | dans `b5_liens.py`, `load_tools` lit `tool_categories` (jointure `categories`) et `_category_label` en tire un libellé ; `tools.json` **ne porte pas** ce qu'il faut (catégories vides) | rien dans le code, mais un lot d'écriture, une sauvegarde, une trace de défaisance |

**Recommandation : par le code.** Aucune donnée touchée, aucun effet sur le référencement, et la correction survit aux passages de la nuit. Il faut seulement que B5 lise la catégorie principale en production (une requête de plus, lecture seule) et que le gabarit ait un libellé par catégorie (le tableau `LIBELLE_SITE` du script en propose neuf). Les 189 cas « à voir » restent à trancher, mais avec cette voie l'erreur n'est plus recopiée dans chaque phrase.

Limite : les raisons déjà en ligne (5 450 lignes, plus `reason_fr`) gardent leur texte. Elles ne changent que si Josué autorise leur remplacement, ce qui sort de « ajouts seulement ».

## Confiance de la proposition

| Niveau | Corrections | Signification |
|---|---|---|
| sûr | 331 | la catégorie du site et la règle indépendante (facettes, étiquettes, texte) concordent |
| probable | 260 | la catégorie du site sans signal contraire, ou deux signaux concordants pour un outil non classé |
| à voir | 189 | divergence entre le site et la règle, signal unique, ou aucune catégorie ne convient (dont 84 sans valeur proposée : B5 n'imprimerait rien) |

**Partie à relire : le jugement.** 39 corrections viennent de ma lecture des descriptions (`source: jugement` dans le JSON), et non d'une règle. Exemples : Trae, Conductor, Superset passent en AI coding ; Wispr Flow en AI audio ; Ollama, MITRE et cinq blogues ou revues restent sans catégorie. Les 189 « à voir » sont aussi à regarder, surtout ceux où le site classe un outil contre l'avis de la règle (une centaine).

## L'effet sur B5

Le calcul exact des 86 paires est impossible sans réseau : il faut les 5 450 paires de `alternatives` pour savoir lesquelles sont absentes. Faute de mieux, j'ai recalculé localement les paires (embeddings de `staging.db`, top 5, seuil 0,55) : 5 015 paires candidates (le passage de nuit en attendait 5 536 ; l'écart vient sans doute des outils archivés ou d'embeddings plus récents en production, non vérifié).

| Sur les 5 015 paires | Aujourd'hui | Après correction (voie par le code) |
|---|---|---|
| Au moins un libellé faux dans la raison | 1 291 (26 %) | 0 par construction |
| Au moins un libellé générique ou vague | 3 923 (78 %) | 0 |
| Au moins un libellé incertain (« à voir ») | | 928 (19 %), borne haute |

Par extrapolation, sur les 86 paires : environ 22 raisons fausses aujourd'hui (fourchette honnête 0 à 86), environ 67 vides de sens ; après correction, au plus 16 incertaines. Pour le vrai chiffre, il manque la liste des paires déjà présentes en production.

## Vingt exemples, avant et après

« Avant » : ce que le gabarit imprime. « Après » : avec la catégorie du site.

| Outil (alternative) | Avant | Après | Confiance |
|---|---|---|---|
| Pika (Freepik) | multimedia / multimedia | AI video / AI image | sûr |
| InVideo (Animaker) | software / multimedia | AI video / (inchangé) | sûr |
| Runway (RunwayML) | developer / developer | AI video / (inchangé) | à voir |
| ElevenLabs (ElevenLabs.io) | developer / developer | AI audio / AI audio | sûr |
| HeyGen (HeyGen.com) | multimedia / multimedia | AI video / (inchangé) | sûr |
| Suno (Suno AI) | multimedia / multimedia | AI audio / AI audio | sûr |
| Synthesia (Promo) | business / business | AI video / AI video | sûr |
| CapCut (Wisecut) | multimedia / multimedia | AI video / (inchangé) | sûr |
| Kling (Kling AI) | multimedia / multimedia | AI video / AI image | probable |
| Ideogram (Getimg) | developer / multimedia | AI image / AI image | probable |
| Claude (Claude.com) | developer / developer | AI writing / (inchangé) | sûr |
| Notion (Mem) | web / business | productivity / productivity | sûr |
| Airtable (n8n) | business / developer | productivity / automation | probable |
| Zapier (Workato) | business / business | automation / automation | sûr |
| Jasper (EkLine) | business / developer | AI writing / AI writing | à voir |
| DeepL (DeepAI) | developer / web | AI writing / AI image | à voir |
| Browse AI (WebScrapeAI) | developer / software | data and scraping / data and scraping | à voir |
| Trae (Notion) | developer / web | AI coding / productivity | probable (jugement) |
| Wispr Flow (AIDictation) | software / software | AI audio / AI audio | probable (jugement) |
| Ollama (GPT4All) | developer / developer | aucune / aucune | à voir (jugement) |

## À décider par Josué

1. **La voie** : par le code (recommandée) ou par les données.
2. **La source de la catégorie du site** : autoriser une lecture de `tool_categories` en production par B5. Le classement local date du 2026-08-05 et peut avoir dérivé.
3. **Les cas sans catégorie** : imprimer rien (proposé) ou un libellé neutre. 84 outils sont concernés.
4. **Les raisons déjà en ligne** : les laisser (le passage reste « ajouts seulement ») ou les remplacer plus tard, avec sauvegarde.
5. **Les non-outils publiés** : à vérifier, d'après leur seule description : ai-finder, animalai, artistic, imagined (domaines à vendre), daruy (avis de panne), roomreinvented (gabarit vide), gpt-apps (publicité de casino), summara (loterie), paperbrain (cabinet juridique). Hors mandat : je n'y ai pas touché.
