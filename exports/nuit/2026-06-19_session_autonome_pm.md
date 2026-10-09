# RUNBOOK YggNexus - session autonome 2026-06-19 (apres-midi/soir)

Travail fait par Emperor pendant ton absence (~1h+). Tout est en CODE, rien n'a
ete pousse ni applique sur Supabase/Vercel (le pipeline a besoin de ta machine).
Voici exactement quoi faire a ton retour, dans l'ordre. Une etape a la fois.

------------------------------------------------------------------------
## 0. URGENT - reparer l'index git du repo PRISME (sinon tu ne peux pas committer)

Le montage Windows a corrompu `D:\Emperor\YggNexus\.git\index`
(`git status` plante avec `unknown index entry format 0x49420000`).
Le repo FRONTEND est sain, seul prisme est touche.

Fix (l'arbre de travail et tes fichiers ne sont PAS touches) :

    cd D:\Emperor\YggNexus
    del .git\index
    git reset

`git reset` (mixed) reconstruit l'index depuis HEAD. Ensuite `git status`
remarche. Verifie : `git status` doit lister tes fichiers modifies sans erreur.

------------------------------------------------------------------------
## 1. Menage parasites (montage)

    cd D:\Emperor\YggNexus\frontend
    del curl
    del "app\compare\[pair]\.fuse_hidden0000001f00000001"

(`curl` = fichier vide cree par erreur ; `.fuse_hidden...` = parasite du montage.)

------------------------------------------------------------------------
## 2. Recherche - seuil de similarite (defaut 0.3)  [Supabase]

Coller dans Supabase -> SQL Editor -> Run :

    database/migration_match_tools_threshold.sql

Idempotent. Recree `match_tools` avec un 3e parametre `match_threshold` (defaut
0.3) qui coupe la queue de resultats peu pertinents. Le frontend n'envoie PAS le
seuil : il utilise le defaut DB. Pour ajuster plus tard SANS redeploy, recolle ce
fichier avec une autre valeur (ex: 0.4) -> effet immediat.

Test apres : sur /search, une requete absurde ("xyzzy plumbing") doit renvoyer 0
resultat semantique au lieu d'une queue au hasard.

------------------------------------------------------------------------
## 3. Prose compare B6 - fix GTM  [ta machine, Ollama]

`b6_pages.py` : PROMPT_VERSION passe a "b6pages-v2" (le cache content_hash
s'invalide tout seul -> regen au prochain run, --force pas necessaire) et le
prompt systeme dit maintenant GTM = go-to-market (pas Google Tag Manager) +
interdit d'inventer des acronymes.

    cd D:\Emperor\YggNexus\prisme
    python b6_pages.py            # regen toutes les pages compare/alternatives

(Ollama doit tourner. Verifie ensuite /compare/<une-paire> : plus de "Google Tag
Manager" parasite.)

------------------------------------------------------------------------
## 4. Nouvelles sources catalogue (+10)  [ta machine]

Ajoutees a `prisme/data/sources.json` (total 51) ET en fiches manuelles dans
`prisme/seed_raw.py` (total 16 fiches) au cas ou un site bloque B1 :

  quillbot, rytr (ai-writing) ; krea-ai, clipdrop (ai-images) ;
  play-ht, resemble-ai (ai-audio) ; activepieces, phantombuster (automation/
  data-scraping) ; softr (no-code) ; taskade (productivity).

Chaine recommandee (comme le 2026-06-19 matin) :

    cd D:\Emperor\YggNexus\prisme
    python b1_collecte.py                 # crawl des 10 nouvelles (UA navigateur)
    python etat_sources.py                # voir qui est en draft / bloque
    python seed_raw.py                    # filet : injecte les fiches des bloquees
    python publier_nouveaux.py            # draft -> published pour les slugs sources.json
    python run_nightly.py --from enrichissement   # b2/b4/export/publish/embeddings/b5/b6

Rappel piege : b1 insere en status=draft -> verifie l'etat REEL avec
etat_sources.py avant de conclure qu'un outil manque.

------------------------------------------------------------------------
## 5. Re-embed recherche apres ajout d'outils  [ta machine, cle Jina]

    cd D:\Emperor\YggNexus\prisme
    python embed_search_jina.py           # (re)genere les embeddings des nouveaux

------------------------------------------------------------------------
## 6. Frontend - autocomplete (deja code, juste a pousser)  [Vercel]

Nouveaux/edites cote frontend :
  - components/SearchBox.tsx        (client, debounce 180ms, nav clavier, a11y)
  - app/api/search/suggest/route.ts (suggestions plein-texte, cache CDN 60s)
  - lib/queries.ts                  (+ suggestTools)
  - app/layout.tsx, app/search/page.tsx (utilisent SearchBox)
  - app/globals.css                 (styles .searchbox)

tsc --noEmit = exit 0 (verifie). La barre du header propose maintenant des
suggestions live ; fleches haut/bas pour naviguer, Enter sur un item -> fiche
outil, Enter sinon -> /search. "Voir tous les resultats" en bas de la liste.

------------------------------------------------------------------------
## 7. Regenerer tools.json (corrompu par le montage)  [ta machine]

`prisme/data/tools.json` a 877 octets NUL + il est tronque (gremlin du montage).
C'est un artefact : `export_tools.py` le regenere proprement. Ne pas reparer a la
main. La chaine du point 4 (run_nightly) appelle deja export_tools.

------------------------------------------------------------------------
## 8. COMMITS (apres avoir fait le point 0 !) - je te donne les commandes

### Repo PRISME (D:\Emperor\YggNexus)
    cd D:\Emperor\YggNexus
    git add database/migration_match_tools_threshold.sql prisme/b6_pages.py prisme/data/sources.json prisme/seed_raw.py
    git commit -m "Recherche: seuil match_tools (0.3) + fix GTM B6 + 10 sources catalogue"
    git push

(tools.json regenere : `git add prisme/data/tools.json` apres export si tu veux le versionner.)

### Repo FRONTEND (D:\Emperor\YggNexus\frontend)
    cd D:\Emperor\YggNexus\frontend
    git add components/SearchBox.tsx app/api/search/suggest/route.ts lib/queries.ts app/layout.tsx app/search/page.tsx app/globals.css
    git commit -m "Recherche: autocomplete (SearchBox + /api/search/suggest)"
    git push

Vercel redeploie tout seul au push frontend.

------------------------------------------------------------------------
## Verifs finales faites cote code (sandbox)
- tsc --noEmit frontend : exit 0
- py_compile b6_pages.py / seed_raw.py : OK
- suite tests prisme : 55/55 verts
- 0 octet NUL sur les 10 fichiers touches ; sources.json = JSON valide
- SQL : ASCII pur, dollar-quoting equilibre, idempotent

## A surveiller / backlog
- lang du site : <html lang="en"> dans layout.tsx alors que le contenu est en
  francais -> a corriger un jour (SEO). Pas touche (hors scope, a valider).
- Runway toujours classe en ai-audio (plutot video) : reclassable via
  `python b4_classification.py --force --only runway` puis DELETE manuel de la
  vieille categorie dans Supabase si besoin.
