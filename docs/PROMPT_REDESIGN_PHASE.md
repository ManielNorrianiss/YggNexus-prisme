# Prompt — Phase Redesign YggNexus (a coller dans une nouvelle conversation)

> Copie tout ce bloc et colle-le dans une nouvelle conversation Cowork branchee sur `D:\Emperor\yggnexus`.

---

Tu es lead engineer sur YggNexus, un site **deja en ligne** (www.yggnexus.com) : annuaire premium d'outils / agents / automatisations IA. Repo : `D:\Emperor\yggnexus`, frontend dans `frontend/`.

## Etat technique reel (ne pas repartir de zero)

- **Next.js 14.2** (App Router), TypeScript 5.5, React 18. **NE PAS migrer vers Next 15** maintenant.
- Styling actuel : **CSS custom** dans `app/globals.css`. **Ni Tailwind ni Shadcn installes.**
- i18n next-intl EN/FR (`app/[locale]/...`, `middleware.ts`, `messages/en.json` + `fr.json`).
- Donnees : Supabase + pgvector. Composants existants a restyler, pas a jeter : `ToolCard`, `RealmGrid`, `HomeFilterBar`, `SearchBox`, `LanguageSwitcher`, `ThemeToggle`, `StarBackground`, `JsonLd`, `RelatedLinks`.
- Contexte complet : lire `docs/RECONCILIATION_ARCHI_CHATGPT_VS_REEL.md` et `docs/CHARTE_VISUELLE_YGGNEXUS.md`.

## Identite visuelle VERROUILLEE (ne pas redessiner, ne pas rediscuter)

- Palette : `#0B0F17` (fond), `#3B82F6` (bleu), `#22D3EE` (cyan), `#22C55E` (vert).
- Style : dark premium SaaS, spatial UI, minimalisme haut de gamme, "systeme vivant".
- Logo : `frontend/public/yn-logo.svg` (+ `YN Logo.png` / `.svg` a la racine du repo).
- Ecrans cibles du design : Homepage, System Overview (les 2 prioritaires MVP). Map/Graph/Atlas/Agent Detail/Automation Builder = V2, garder seulement l'esthetique.

## Mission de cette phase (incrementale, rien casser)

1. **Integrer Tailwind dans le Next.js 14 existant** sans tout reecrire : installer tailwindcss + postcss + autoprefixer, configurer `tailwind.config.js` + `globals.css`, faire cohabiter avec le CSS actuel.
2. **Poser les design tokens** de la palette verrouillee dans `tailwind.config.js` (couleurs nommees : bg, blue, cyan, green) + typographie + rayons + ombres "premium".
3. **Adopter Shadcn de facon ciblee** (seulement les primitives neuves : button, card, input, dialog). Pas de big-bang.
4. **Re-skinner en premier la Homepage**, puis creer **System Overview**, en dark premium / spatial UI. Reutiliser et restyler les composants existants.
5. **Integrer le logo** dans le header/footer.

## Contraintes

- Chaque etape doit laisser le site buildable (`npm run build` OK) et le `tsc` propre.
- Ne pas casser l'i18n EN/FR ni le SEO (JSON-LD, sitemap, robots, ISR).
- Commits petits et frequents. Repo git : reparer l'index avant de commit si besoin (`del .git\index .git\index.lock` puis `git reset`).
- Travailler page par page, valider visuellement (screenshots) avant de passer a la suivante.

## Premier livrable attendu

Un plan d'execution en etapes numerotees (quels fichiers, dans quel ordre), puis l'integration Tailwind + tokens, et le re-skin de la Homepage. Demande validation avant d'attaquer System Overview.
