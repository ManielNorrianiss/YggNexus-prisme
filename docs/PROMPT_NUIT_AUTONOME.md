# Prompt — travail de nuit autonome sur YggNexus

> Copie-colle ce bloc dans une nouvelle conversation Cowork (space Emperor, branche sur D:\Emperor) avant d'aller dormir.

---

Reprends YggNexus.com en mode TRAVAIL DE NUIT AUTONOME. Je dors — tu avances sans moi.

D'abord, lis tes memoires : `yggnexus-repos`, `yggnexus-pipeline-execution`, `yggnexus-etat`, `montage-windows-tronque-fichiers` (dans D:\Emperor\memory) et `docs/PROMPT_REPRISE_YggNexus.md`. Confirme rien, enchaine.

## Regles (importantes)
- Je suis endormi : NE POSE AUCUNE QUESTION, n'utilise pas de boutons. Prends les decisions raisonnables toi-meme et note-les dans ton rapport.
- Tu ne peux PAS atteindre mon Supabase, mon Ollama, ni pousser sur git (les cles sont sur ma machine). DONC :
  - ne lance PAS le pipeline (B1->B8), ne publie PAS, n'execute PAS de SQL Supabase ;
  - ne commit/push PAS toi-meme (ca laisse des fichiers verrous .git que tu ne peux pas effacer) ;
  - ne lis pas staging.db depuis le sandbox (il ressort "malformed" via le montage — c'est normal).
- Edite le code sous D:\ via le terminal bash (python/sed/heredoc), JAMAIS les outils Edit/Write (ca tronque les fichiers). Fais des remplacements precis avec verification (assert que l'ancre existe).
- Verifie CHAQUE changement : `py_compile` pour le Python, `tsc` (npx tsc --noEmit) pour le frontend, parse JSON pour les .json. Ne laisse rien de casse.
- Travaille uniquement sur ce qui ne demande pas ma machine : ecrire/ameliorer du code, des tests, des fichiers de migration SQL (ecrits, PAS executes), de la doc.

## Tache de cette nuit
[ECRIS ICI CE QUE TU VEUX QUE JE FASSE. Si tu laisses vide, prends l'item du haut du backlog "Prochaines etapes" dans yggnexus-etat, sinon, par defaut, fais les deux :
 1) Ameliore prisme/publish.py pour qu'il revalide aussi /best/<cat> et /categories/<cat> (en plus de / et /tools/<slug>), afin que les pages de regroupement ne restent plus en cache perime apres une publication.
 2) Cree un dossier prisme/tests/ avec des tests (pytest, pures fonctions, sans reseau) couvrant : le filet score /10 et le filet SEO de export_tools, content_hash + garde-fou anti-mince de b6_seo, et la validation de b4_classification. Lance-les et assure-toi qu'ils passent.]

## Livrable au reveil
- Tout le code modifie compile/valide (montre les sorties py_compile / tsc / tests).
- Un rapport de nuit dans `D:\Emperor\YggNexus\exports\nuit\AAAA-MM-JJ.md` qui contient :
  - ce que t'as fait et les decisions que t'as prises (et pourquoi) ;
  - un RUNBOOK pas-a-pas des commandes que MOI je dois lancer au matin pour activer/publier ton travail (git add/commit/push, pipeline, SQL Supabase, redeploy Vercel) — avec l'ordre et ce que chaque commande fait en une ligne ;
  - ce qui reste a faire / ce sur quoi t'as bloque.
- Mets a jour la memoire `yggnexus-etat` et `docs/PROMPT_REPRISE_YggNexus.md`.
- Ne casse rien : si t'es bloque ou incertain, arrete-toi proprement et ecris-le dans le rapport plutot que de forcer.

Ton : francais quebecois, Emperor. Travaille, documente, laisse-moi un terrain net au reveil. Farevel.
