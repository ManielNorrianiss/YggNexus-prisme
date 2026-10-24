# Rapport de nuit YggNexus : 24 octobre 2026

Session du 23 octobre 23:50 au 24 octobre, 01:00 environ.

---

## En bref

- **L'accueil V2 est en ligne** sur www.yggnexus.com, palette Forêt et Lumière sur tout le site.
- **87 fiches qui ne sont pas des outils** (articles, livres, cours) sortent du catalogue au nightly de 03:00.
- **La verticale MCP reste bloquée** : elle demande Supabase et le registre MCP, que je ne peux pas joindre d'ici. Il reste 2 gestes à toi.
- Tout est commité et poussé sur GitHub, dans les deux dépôts.

---

## 1. Ce qui est fait

### Site (dépôt YggNexus)

- [x] Branche `refonte-filtres` (ton travail du 16 août) fusionnée dans `main`
- [x] Accueil V2 allégée en production : héros avec l'arbre, six besoins en branches, trois outils vedettes (Framer, Canva, n8n)
- [x] Palette Forêt et Lumière sur toutes les pages, plus de cyan ni de halo
- [x] Thème automatique par défaut (suit le téléphone ou l'ordi)
- [x] Ancien fond Yggdrasil retiré (parallaxe, lanterne, runes)
- [x] Mot-symbole « YggNexus » en Syne dans l'en-tête et le pied
- [x] Textes anglais de l'accueil adaptés
- [x] Français du site passé au tutoiement (Décris, Parcours, Découvre)
- [x] Plus aucun tiret cadratin dans les textes du site
- [x] Titres de page corrigés : la marque apparaissait deux fois (« Tous les tags, YggNexus, YggNexus »)
- [x] Pages de comparaison : une seule adresse officielle par paire (a-vs-b et b-vs-a se confondaient pour Google)
- [x] Fiche outil : la description s'affiche formatée, les astérisques ne sortent plus en clair

### Pipeline (dépôt YggNexus-prisme)

- [x] Commit de l'état avant toute modification (traductions et paramètres du nightly)
- [x] Nouvelle liste `prisme/data/hors_scope.json` : 87 fiches forcées en « archivées » à chaque nuit
- [x] `export_tools.py` lit cette liste. Pour republier une fiche : retirer sa ligne
- [x] Fichier SQL piège `sql/001_mcp_servers_and_bridges.sql` renommé en `.OBSOLETE`

### Déjà réglé avant cette nuit

- Le rapport de santé ne signale plus les « 365 outils sans catégorie » : 0 problème au rapport du 23 octobre.

---

## 2. Comment le nettoyage du catalogue fonctionne

Je ne peux pas joindre Supabase d'ici. Plutôt que d'écrire directement dans la base, la liste passe par ton pipeline, dans le bon sens : Prisme, puis Supabase, puis le site. Au nightly de 03:00, l'export marque les 87 fiches « archivées », le publish les envoie à Supabase et elles disparaissent du site.

La sauvegarde, c'est `tools.json` tel qu'il était avant, commité dans Git (`f3d2071`). Rien n'est supprimé : une fiche archivée reste dans la base.

| Type | Nombre | Exemples |
|---|---|---|
| Articles, billets, nouvelles | 59 | The Atlantic, TIME, Wired, Forbes, The Verge |
| Livres | 13 | R for Data Science, Python Crash Course, Algorithms of Oppression |
| Cours en ligne | 6 | Coursera, Udemy, Udacity, Fast.ai |
| Guides et listes | 6 | Liste ClickUp, guide des samplers Stable Diffusion |
| Sites sans outil | 3 | une boutique de vêtements, un portfolio, un organisme |

### Les cas douteux, gardés publiés

Ces fiches ne sont ni clairement des outils, ni clairement des articles. Je les ai laissées. À toi de trancher.

| Fiche | Ce que c'est |
|---|---|
| learnprompting | Plateforme de cours sur le prompting |
| promptingguide | Site de référence sur le prompting |
| buildclub | Communauté d'apprentissage |
| datacamp | Plateforme de cours |
| oreilly | Plateforme d'apprentissage |
| hbritalia | Formation HBR Italia |
| paperswithcode | Base d'articles scientifiques |
| nltk | Bibliothèque Python, fiche titrée comme le livre |
| llmtop10 | Liste de risques OWASP |
| ai-jobs, aijobster | Sites d'emploi en IA |
| co-uk | « KDP Readiness Score », description incohérente |
| intlekt | Langage d'ontologie, flou |
| haveibeentrained | Outil réel, description floue |

### Problèmes de données repérés, non corrigés

- Des slugs dérivés du domaine : `com`, `org`, `ai`, `blog`, `amazon-com`, `openai-com`, `claude-com`. Ils font de mauvaises adresses de page.
- Des noms qui sont des titres d'article sur de vrais outils : « Introducing AACP | SuperAGI », « Free Dolly | The Databricks Blog ».
- Les FAQ et descriptions générées sont au vouvoiement. C'est le chantier traduction.
- Certaines facettes sont surprenantes : Midjourney classé « Marketing ».

---

## 3. Ce qui reste à toi

### Ce matin, 5 minutes

1. Ouvre www.yggnexus.com sur ton téléphone et sur ton ordi. Regarde l'accueil en mode sombre et en mode clair (bouton rond en haut à droite).
2. Ouvre www.yggnexus.com/fr/tools/time. Si la page dit « introuvable », le nettoyage du catalogue a fonctionné cette nuit.

### Verticale MCP, 5 minutes

Le document `docs\DEBLOCAGE_MCP_ETAPE_PAR_ETAPE.md` est toujours valide. L'étape 4 est déjà faite.

1. Ouvre `D:\Emperor\YggNexus\database\migration_mcp_vertical.sql` avec le Bloc-notes, tout sélectionner, copier.
2. Va sur supabase.com, projet `biykachrofudlvdgtbvo`, menu SQL Editor, New query.
3. Vide la fenêtre, colle, clique Run. Attendu : bandeau vert « Success ».
4. Double-clique `D:\Emperor\YggNexus\prisme\lancer_mcp.cmd` et laisse finir.
5. Dis-moi le chiffre de la ligne UNIQUE.

### Décisions à prendre

| Sujet | Pourquoi c'est important | Ma recommandation |
|---|---|---|
| Le projet Vercel « yggnexus » | Il échoue à chaque déploiement depuis le 30 juin. Le site tourne sur l'autre projet, « ygg-nexus ». Chaque commit lance donc deux constructions sur ton plan gratuit déjà saturé | Le supprimer dans Vercel |
| Page Confidentialité | Le site mesure les visites (Vercel Analytics). Au Québec, la Loi 25 demande une politique de confidentialité publiée | La rédiger en priorité |
| Pages À propos et Nous joindre | Prévues dans la spec, absentes. L'en-tête et le pied en ont besoin | Je peux les rédiger |
| Les 15 cas douteux | Ils restent publiés tant que tu ne tranches pas | Sortir les plateformes de cours, garder les bibliothèques |

---

## 4. Ce que je n'ai pas pu faire

| Tâche | Blocage |
|---|---|
| Écrire dans Supabase | Ni mon environnement ni ton ordi (côté Claude) ne joignent Supabase. Contourné par le pipeline pour le catalogue |
| Collecte MCP | Le registre MCP est bloqué de la même façon |
| Voir l'aperçu Vercel avant la mise en prod | L'aperçu demande une connexion Vercel. Le build a réussi, puis j'ai vérifié directement en production |
| Tester au lecteur d'écran et au zoom 200 % | Pas d'outil pour ça ici |

---

## 5. Commits de la nuit

**YggNexus (site)**

| Commit | Contenu |
|---|---|
| `0dd8241` | Accueil V2 allégée, palette, en-tête, pied |
| `823976b` | Alignement du héros |
| `9f0d0be` | SEO et textes : canoniques, titres, tutoiement, tirets |
| `8437a46` | Retrait de fichiers de transfert commités par erreur |
| `0bf8ba9` | Description Markdown formatée sur la fiche outil |

**YggNexus-prisme (pipeline)**

| Commit | Contenu |
|---|---|
| `f3d2071` | État du pipeline avant la nuit |
| `eff28a2` | Liste hors scope, 87 fiches |
| `9ca2147` | Fichier SQL piège renommé |

---

## Journal de versions

| Version | Date | Auteur | Changement |
|---|---|---|---|
| 1.0 | 2026-10-24 | Claude, session de nuit | Création |
