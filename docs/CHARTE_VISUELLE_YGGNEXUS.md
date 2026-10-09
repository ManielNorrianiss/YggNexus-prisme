# 🎨 Charte visuelle — YggNexus

> **Type :** Document maître d'identité de marque
> **Actif :** YggNexus.com (catalogue intelligent IA/SaaS, anglophone)
> **Version :** 1.0 — 2026-06-21
> **Source stratégique :** `KIT_STRATEGIQUE_YGGNEXUS.md`
> **Pilote :** Josué

---

## 0. Le principe directeur

YggNexus n'est pas « un site IA ». C'est un **instrument de navigation** : la carte de confiance de l'univers des outils IA. La marque se traite comme une infrastructure (logique Stripe) — invisible, précise, qui inspire une confiance totale — avec la chaleur humaine d'un outil de pensée (logique Anthropic).

Règle d'or unique : **la sophistication vient de la retenue.** Zéro effet, zéro dégradé néon, zéro illustration littérale. Un fond qui ancre, un seul accent qui signale la valeur, du blanc qui respire.

---

## 1. Plateforme de marque

| Axe | Position |
|---|---|
| **Promesse** | Transformer n'importe quel outil IA en automatisation concrète. |
| **Nature** | Une **carte** (a map), pas un OS ni un assistant. |
| **Archétype** | **Sage** (dominante) + teinte **Creator**. Le guide qui sait, et qui aide à bâtir. |
| **Personnage** | Mimir — la tête-conseil au pied d'Yggdrasil. Bibliothécaire-stratège, pas magicien. |
| **Émotion cible** | La clarté confiante. Le soulagement de « enfin, c'est cartographié, je sais quoi faire ». |
| **3 mots** | Carte · Confiance · Connexion. |
| **3 anti-mots** | Annuaire · Générique · Publicitaire. |

---

## 2. Le symbole

### Concept central

L'arbre et le réseau sont **le même dessin** : un nœud d'où partent des branches qui se ramifient. Yggdrasil (l'arbre-monde qui relie les royaumes) et Nexus (le point de connexion) fusionnent en une seule glyphe.

### Contraintes non négociables

- Réductible à un **signe monochrome** lisible en favicon 16 px.
- Fonctionne en positif (sombre sur clair) et négatif (clair sur sombre).
- Reconnaissable sans le mot-symbole « YggNexus » à côté.
- Construit au **trait**, pas en illustration texturée.

> ⚠️ Le logo `YN` actuel (arbre doré organique, `YN Logo.svg`) est dans le bon territoire symbolique mais trop illustratif et texturé : il ne tient ni en favicon ni en monochrome. À faire évoluer vers une glyphe.

---

## 3. Palette

Reprend et fixe ce qui existe déjà dans le frontend (`globals.css`). Le **dark mode est le mode canonique** (l'encre nuit pose l'autorité) ; le clair est le mode secondaire.

### Mode sombre (canonique)

| Rôle | Hex | Usage |
|---|---|---|
| Encre nuit (fond) | `#050510` | Fond principal. Ancre, autorité. |
| Carte / surface | `#0d0d2b` | Cartes, panneaux. |
| Texte | `#e8eef5` | Corps de texte. |
| Texte atténué | `#a8b2c1` | Secondaire, légendes. |
| **Or runique (accent valeur)** | `#c9a227` | **Accent principal de marque.** Valeur, confiance, le « précieux ». |
| Cyan (accent fonctionnel) | `#00d4ff` | **Liens et états interactifs uniquement** — jamais comme couleur de marque. |
| Survol | `#1a0a3e` | États hover. |

### Mode clair (secondaire)

| Rôle | Hex |
|---|---|
| Fond | `#eef3fa` |
| Texte | `#0f1722` |
| Accent | `#0077a3` (cyan foncé, WCAG AA) |
| Or | `#8a6d12` (or foncé lisible) |

### Hiérarchie des accents

L'**or** porte l'identité de marque (logo, signature, ce qui doit « valoir »). Le **cyan** est purement fonctionnel (liens, focus, hover). Ne jamais inverser : le cyan tape-à-l'œil ne doit pas devenir la couleur de la marque.

---

## 4. Typographie

| Police | Rôle | Notes |
|---|---|---|
| **Syne** | Display / titres / mot-symbole | Porte le « futurisme discret ». Le caractère vient d'ici, jamais de la couleur. |
| **Inter** | Corps / interface / data | Neutralité, lisibilité, confiance. |

Le contraste display/corps EST l'identité typographique. Pas de troisième police.

---

## 5. Do / Don't

### À conserver absolument

- La métaphore arbre = réseau (racine, tronc, branches, liens).
- Le fond sombre profond comme socle d'autorité.
- L'or comme accent de valeur et de confiance.
- Le couple Syne + Inter.
- Le blanc qui respire, la grille aérée.

### À éviter absolument

- Runes littérales et glyphes ésotériques (illisibles, cliché).
- Casques à cornes, drakkars, tout cliché viking « costume ».
- Dégradés néon / cyberpunk / crypto.
- Illustrations d'IA génériques : cerveaux, circuits, robots, têtes filaires.
- Constellations décoratives déconnectées du sens « arbre/réseau ».
- Toute esthétique qui crie *futurisme* ou *sci-fi* (daté, tue la confiance).

> La mythologie nordique vit dans l'**ADN et le vocabulaire** (Yggdrasil, Nexus, royaumes, racines), **jamais dans le costume visuel.**

---

## 6. Les 3 pistes de logo

Toutes partent de la même idée : **un nœud qui se ramifie**. Trois traductions, du plus organique au plus systématique.

### Piste A — « La racine-source »

Un point/nœud unique en bas, d'où trois branches montent et se subdivisent une seule fois. Lu de bas en haut : une racine qui devient arbre. Lu comme réseau : un hub qui distribue.

- **Force :** la plus proche du sens Yggdrasil, chaleureuse, mémorable.
- **Risque :** doit rester ultra-épurée pour ne pas redevenir « illustration d'arbre ».
- **Or sur encre nuit, trait unique d'épaisseur constante.**

### Piste B — « Le nexus » (recommandée)

Un nœud central plein, six liens rayonnants qui se terminent en petits nœuds, dont certains se reconnectent entre eux. C'est un graphe, pas un arbre — mais sa silhouette évoque la cime ramifiée. Plus abstrait, plus « infrastructure ».

- **Force :** intemporel, tient en 16 px, dit « connexion » avant « mythologie ». Le plus Stripe/Anthropic.
- **Risque :** un peu plus froid — l'or chaud compense.
- **Recommandée** : maximise la lisibilité système sans perdre le symbole.

### Piste C — « La ligature YN »

Le `Y` et le `N` fusionnés en un seul trait où la fourche du Y devient le point de ramification du réseau. Mono-glyphe typographique.

- **Force :** signature compacte idéale en favicon et avatar ; rattache directement au nom.
- **Risque :** plus « logo de startup » que « carte de référence » ; perd un peu la profondeur mythologique.

Dans les trois cas : **construction au trait, monochrome d'abord, or comme couleur de signature, testé en 16 px avant toute fioriture.**

---

## 7. Applications prioritaires

1. Favicon + avatar social (le test 16 px décide du logo final).
2. Hero du site (mot-symbole Syne + glyphe + tagline « Turn any AI tool into a working automation »).
3. Gabarit Open Graph (partage social — fond encre nuit, glyphe or, titre Syne).
4. Signature newsletter (Beehiiv).

---

*Charte v1.0 — à versionner dans `YggNexus/docs/`. Évolue avec le choix de logo final. La stratégie qui la fonde : `KIT_STRATEGIQUE_YGGNEXUS.md`.*
