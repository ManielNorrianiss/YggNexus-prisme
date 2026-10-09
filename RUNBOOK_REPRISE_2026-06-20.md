# YggNexus — Runbook de reprise (2026-06-20)

Tout le code des chantiers A, B, C est ecrit et verifie dans le sandbox
(py_compile OK, `tsc --noEmit` exit 0). **Rien n'a encore touche Supabase ni le
live** : le sandbox Cowork n'atteint ni Supabase, ni Clearbit, ni Google. Tu
executes les etapes ci-dessous sur ta machine Windows, dans l'ordre. Je te donne
les commandes git, **tu pousses**.

---

## 0. Git : reparer l'index AVANT chaque commit (les 2 repos)

L'index des deux repos est corrompu (`unknown index entry format`, faux `D` sur
`lib/`, `messages/`...). Dans **chaque** repo, avant de commit :

```bat
del .git\index
git reset
git status
```

Ensuite seulement `git add ... && git commit && git push`.

---

## CHANTIER A — Logos (Clearbit -> favicon Google)

Fichier neuf : `prisme/collect_logos.py`. Run par defaut = **rafraichit tous**
les logos (ta consigne). Options : `--only <slug>`, `--only-missing`, `--force`,
`--dry-run`.

```bat
cd prisme
python collect_logos.py --dry-run      REM tableau outil -> source -> URL, rien ecrit
REM apres verif du tableau :
python collect_logos.py                REM ecrit logo_url + revalide EN+FR + accueil
```

Commit pipeline :
```bat
cd ..
del .git\index & git reset
git add prisme\collect_logos.py
git commit -m "feat(prisme): collect_logos.py - logos Clearbit->favicon Google + revalidation EN/FR"
git push
```

---

## CHANTIER B — Reclassement b4 (PRIMARY_OVERRIDE)

`prisme/b4_classification.py` : ajoute `wellsaid->ai-audio`, `canva->ai-images`,
`freepik->ai-images` (tana etait deja `productivity`).

**D'abord verifier les slugs reels** (SQL Editor web Supabase) :
```sql
select slug from tools
where slug ilike '%wellsaid%' or slug ilike '%canva%'
   or slug ilike '%freepik%' or slug ilike '%tana%';
```
Si un slug differe (ex. `wellsaid-labs`), corrige la cle dans le dict
`PRIMARY_OVERRIDE` de `b4_classification.py` (bloc « Chantier B »).

Puis :
```bat
cd prisme
python b4_classification.py --resteer
python export_tools.py
python sync_categories.py --dry-run
python sync_categories.py
```

Verif live (apres cache-bust `?x=1`) :
- WellSaid dans `/best/ai-audio`
- Canva + Freepik dans `/best/ai-images`
- Tana dans `/best/productivity`
- aucun des 4 dans AI Writing

Commit pipeline :
```bat
cd ..
del .git\index & git reset
git add prisme\b4_classification.py prisme\data
git commit -m "fix(b4): PRIMARY_OVERRIDE wellsaid/canva/freepik + tana (reclassement)"
git push
```

---

## CHANTIER C1 — Noms de categories en FR (frontend, FAIT)

Code complet et `tsc` vert. Aucune donnee live requise. Mapping slug->FR dans
`frontend/lib/localize.ts` (`CATEGORY_NAME_FR` + `localizeCategoryName`),
applique partout (home, RealmGrid, /best, /categories, badges fiche).

Commit frontend (Vercel deploie au push) :
```bat
cd frontend
del .git\index & git reset
git add lib/localize.ts lib/types.ts lib/queries.ts components/ToolCard.tsx components/RealmGrid.tsx app/[locale]/page.tsx "app/[locale]/best/[category]/page.tsx" "app/[locale]/categories/page.tsx" "app/[locale]/tools/[slug]/page.tsx" "app/[locale]/tools/[slug]/alternatives/page.tsx" app/globals.css
git commit -m "feat(i18n): noms de categories FR (C1) + pricing_note FR (C2) + reason FR affichee (C3)"
git push
```

---

## CHANTIER C2 — pricing_note FR  &  CHANTIER C3 — reason FR (+ affichee)

Frontend FAIT (meme commit que C1) : `localizeTool` sert `pricing_note_fr` en
/fr ; les cartes d'alternatives affichent la raison (prop `reason` sur
`ToolCard`, EN+FR) ; `getToolAlternatives` lit `reason_fr`.

Reste cote donnees (Windows) :

### 1) Migration (SQL Editor web Supabase)
Colle `database/migration_translations_fr_v2.sql` :
```sql
ALTER TABLE tools ADD COLUMN IF NOT EXISTS pricing_note_fr TEXT;
ALTER TABLE alternatives ADD COLUMN IF NOT EXISTS reason_fr TEXT;
```

### 2) Dump EN etendu
`dump_en_content.py` exporte maintenant AUSSI `pricing_note` (outils) et la
section `alternatives` (paires de slugs + reason).
```bat
cd prisme
python dump_en_content.py
```
-> regenere `data/i18n_source_en.json` avec `tools[].pricing_note` et
`alternatives[]`.

### 3) Traduire (etape a me confier)
Ouvre une conversation Emperor branchee a D:\Emperor : je lis
`data/i18n_source_en.json`, je traduis en FR court les `pricing_note` et les
`reason`, et je remplis `data/translations_fr.json` :
- `tools.<slug>.pricing_note_fr`
- `alternatives` : liste `{tool_slug, alternative_slug, reason_fr}`
(Le reste de translations_fr.json est inchange — repli EN si un champ manque.)

### 4) Publier + revalider
`publish_translations.py` gere maintenant `pricing_note_fr` (outils) et
`reason_fr` (alternatives, resolus par slugs) et revalide les pages /fr.
```bat
python publish_translations.py --dry-run
python publish_translations.py
```
Pas de re-embed.

Verif live : `/fr/tools/<slug>` (note de prix en FR), `/fr/tools/<slug>/alternatives`
(raison affichee en FR), `/fr/compare/<paire>` (ligne « note de prix »).

---

## Resume des fichiers touches

**Pipeline (repo YggNexus-prisme)**
- `prisme/collect_logos.py` (neuf)
- `prisme/b4_classification.py` (PRIMARY_OVERRIDE)
- `prisme/dump_en_content.py` (+pricing_note +alternatives)
- `prisme/publish_translations.py` (+pricing_note_fr +reason_fr)
- `database/migration_translations_fr_v2.sql` (neuf)

**Frontend (repo YggNexus)**
- `lib/localize.ts`, `lib/types.ts`, `lib/queries.ts`
- `components/ToolCard.tsx`, `components/RealmGrid.tsx`
- `app/[locale]/page.tsx`, `app/[locale]/best/[category]/page.tsx`,
  `app/[locale]/categories/page.tsx`, `app/[locale]/tools/[slug]/page.tsx`,
  `app/[locale]/tools/[slug]/alternatives/page.tsx`, `app/globals.css`

## A signaler
- `prisme/data/tools.json` est **tronque sur le disque** (34 Ko, JSON invalide,
  fin coupee en plein FAQ) — corruption d'une ecriture anterieure. `publish.py`
  le lit : a regenerer (re-export) avant la prochaine publication B7.
