# Briefing matin - YggNexus (nuit du 17 juin 2026)

Salut Josue. Voici ce qui s'est passe pendant ton sommeil et ce qui t'attend. Tout le travail de nuit est **local seulement** : rien n'a ete commite ni deploye, comme convenu.

---

## 1. Ce qu'on a regle ensemble hier soir

- **Push Supabase valide en prod** : `claude` (id=43) + `apify` (id=44), status `published`. Le pipeline publie pour de vrai de bout en bout.
- **Revalidation ISR : 200.** Le bug `401` venait de l'apex `yggnexus.com` qui redirige en 308 vers `www`, et `requests` jette le header `Authorization` au changement d'hote. Corrige : `SITE_URL` du Prisme pointe maintenant directement sur `https://www.yggnexus.com`.
- **Domaine canonique unifie sur `www`** : `NEXT_PUBLIC_SITE_URL` (Vercel) + fallback `lib/seo.ts` (local).

---

## 2. Ce que j'ai code cette nuit

### B5 - liens semantiques (alternatives)
- `prisme/b5_liens.py` : calcule les alternatives de chaque outil par similarite cosinus entre embeddings, ecrit dans la table `alternatives`. Recalcul propre et rejouable (supprime les liens d'un outil puis reinsere le top-N).
- Integre a `run_nightly.py` : nouvelle etape "liens" (non critique), apres les embeddings -> 8 etapes au total.
- Options : `--dry-run`, `--top 5`, `--threshold 0.55`, `--only SLUG`, `--limit N`, `--model nomic-embed-text`.
- Verifie : `py_compile` OK, 100% ASCII. **Pas encore lance en reel** (besoin de Supabase + des embeddings en base).

### 7 pages frontend SEO (templates, gerent le cas "table vide")
- `/categories` + `/categories/[slug]`
- `/automations` + `/automations/[slug]`
- `/best/[category]`  ("Best X")
- `/tools/[slug]/alternatives`  ("Alternatives to X")
- `/compare/[pair]`  ("X vs Y", format `slug-a-vs-slug-b`)
- Ajouts : 9 fonctions dans `lib/queries.ts`, types `Automation`/`AutomationStep`, `itemListLd` (JSON-LD), `sitemap.ts` enrichi (categories + automations).
- Verifie : `npx tsc --noEmit` = **0 erreur**.

---

## 3. A faire a ton reveil (dans l'ordre)

**Etape 1 - Lancer B5 en vrai (~5 min, sur ta machine, dossier `prisme`)**
```
python b5_liens.py --dry-run      (repetition : montre les liens sans ecrire)
python b5_liens.py                (pour de vrai)
```
Puis verifie qu'une section "alternatives" apparait en bas d'une fiche outil.
Note : avec seulement 2 outils en base, attends-toi a 0 ou 1 lien selon le seuil. Baisse `--threshold` (ex : `--threshold 0.3`) juste pour tester l'ecriture si besoin.

**Etape 2 - Relire + deployer le code de la nuit**
- Relis le diff : `b5_liens.py`, `run_nightly.py`, les 7 pages, `lib/queries.ts`, `lib/types.ts`, `lib/schema.ts`, `app/sitemap.ts`, et `lib/seo.ts` (change localement hier soir, jamais pousse).
- Commit + push sur GitHub (repo frontend) -> Vercel deploie automatiquement.

**Etape 3 - Plus tard**
- Quand le catalogue grossira (via le batch nocturne), les pages categories / best / compare se rempliront toutes seules.

---

## 4. Notes & pieges confirmes cette nuit

- **"Integrations" tool<->tool** : pas de table dediee dans le schema actuel. Evolution future possible via `automation_tools`. Non implemente.
- **`web_fetch` met en cache** : pour reverifier une page apres deploiement, ajoute `?cb=xxx` a l'URL, sinon tu relis l'ancienne version.
- **Tables `categories` / `automations` encore vides** : les nouvelles pages affichent un etat vide propre, aucun crash.
- **Reset tranches 5h** : on n'en a pas parle hier. Dis-moi ton heure de prochain reset ce matin si tu veux que j'ajuste les scheduled tasks.

-- Emperor
