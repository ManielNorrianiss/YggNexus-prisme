# Marche à suivre — fond hybride « image IA + plante canvas qui grandit »

**Concept retenu**
- **Fond** = image IA riche (générée dans Midjourney/Firefly/etc.), statique.
- **Par-dessus** = couche **canvas animée** : une **petite plante qui grandit** avec la
  data du site (sève/énergie qui circule, balancement, secret « surcharge » au clic).
- La croissance = la plante mûrit (pousse → arbre) à mesure que le site grandit, au lieu
  de dézoomer sur un arbre déjà géant.

L'image IA donne la richesse ; le canvas donne le vivant et la progression.

## 1. Outil de génération
Midjourney (le plus proche du style), sinon Firefly / DALL·E 3 / Ideogram / Leonardo.
> Claude ne génère pas l'image ici — je raffine les prompts et je code l'intégration.

## 2. Prompts (copier-coller, en anglais)

Palette forcée partout : `#0B0F17` fond · `#3B82F6` bleu · `#22D3EE` cyan · `#22C55E` vert.
Toujours bannir l'ambre : `--no amber, orange, gold, yellow, brown, text, watermark, people`.

### Variante A — fond atmosphérique « sol-circuit » (recommandé pour la plante devant)
Laisse le centre vide pour que la plante canvas soit la vedette.
```
Dark abstract circuit-board ground and atmosphere, pure black background, faint
horizontal PCB traces with right-angle bends and small glowing solder pads spreading
across the lower third, soft volumetric energy haze, lots of empty negative space in
the center and upper area. Strict palette: near-black (#0B0F17), electric blue
(#3B82F6), cyan (#22D3EE), green (#22C55E) glow only. Minimal, premium dark sci-fi,
subtle. --ar 16:9 --no amber, orange, gold, yellow, brown, text, watermark, people, tree
```

### Variante B — arbre complet majestueux (si tu veux l'arbre « destinée » en fond)
```
A majestic tree of life as a glowing circuit board, centered, pure black background,
thick gnarled trunk of fine luminous circuit traces branching into a dense rounded
canopy of countless tiny glowing leaves, sprawling fibrous roots below, horizontal PCB
traces radiating from the base ending in glowing solder pads, bright energy core at the
trunk base. Strict palette: near-black (#0B0F17), blue (#3B82F6), cyan (#22D3EE), green
(#22C55E) glow only. Neon bioluminescent, volumetric glow, ultra detailed, symmetrical.
--ar 16:9 --no amber, orange, gold, yellow, brown, text, watermark, people
```

### Variante C — jeune pousse circuit (si l'image elle-même = la petite plante)
```
A tiny glowing circuit-board seedling sprouting from dark soil made of fine PCB traces,
two small luminous leaves, thin glowing stem, a bright energy seed at the base, pure
black background, lots of empty space above. Strict palette: near-black (#0B0F17), blue
(#3B82F6), cyan (#22D3EE), green (#22C55E) glow only. Minimal, delicate, premium dark
sci-fi, volumetric glow. --ar 16:9 --no amber, orange, gold, yellow, brown, text, people
```

Sur Firefly/DALL·E : enlève `--ar`/`--no`, écris « 16:9 aspect ratio, no amber or orange ».

## 3. Générer / trier / exporter
1. 4 variantes → garde la meilleure silhouette + palette.
2. 2-3 variations de la préférée → upscale.
3. Vérifie : zéro ambre, fond noir pur `#0B0F17`.
4. Exporte en **WebP** < 400 Ko → `public/yn-tree-hero.webp`.

## 4. Intégration (je m'en occupe)
- Image en fond du hero (CSS), canvas « plante qui grandit » par-dessus en transparence.
- Paramètre `growthLevel` (0..1) piloté plus tard par le nombre d'outils du site →
  la plante mûrit toute seule à mesure que la data grandit.
- Secret « surcharge » au clic conservé.

---
*Palette verrouillée. Aucun ambre.*

---

## 5. Kit Leonardo.ai — plante évolutive (wallpaper, 5 étapes)

Objectif : un **fond d'écran** où la plante **grandit par paliers** à mesure que le site se
peuple, jusqu'à l'arbre final. Même monde, même cadrage, même palette à chaque étape.

### Réglages Leonardo (à régler une fois)
- **Modèle** : un modèle artistique stylisé (ex. *Leonardo Phoenix* ou *Flux*).
- **Aspect ratio** : **16:9** (fond d'écran). Pour mobile, refais en **9:16**.
- **Alchemy / Prompt Magic** : ON (qualité).
- **Guidance scale** : ~7.
- **Negative prompt** (champ séparé, le même pour TOUTES les étapes) :
```
amber, orange, gold, yellow, brown, warm tones, sepia, text, letters, watermark, logo,
signature, people, person, blurry, low quality, jpeg artifacts, photo, realistic photograph,
oversaturated, cluttered
```
- **Astuce continuité** : génère l'étape 1, choisis ta préférée, **note son Seed**, et
  réutilise **le même Seed** pour les étapes 2→5. Pour verrouiller encore plus le style,
  active **Image Guidance (Image to Image)** avec l'image de l'étape précédente à **force
  faible (0.2–0.3)**. Ainsi l'arbre semble *la même plante qui a grandi*.

### Tronc commun du prompt (à garder identique)
> Dark premium sci-fi wallpaper, glowing circuit-board bio-plant rooted at the bottom center,
> growing out of dark soil made of fine glowing PCB traces and tiny solder pads, pure
> near-black background (#0B0F17), only electric blue (#3B82F6), cyan (#22D3EE) and green
> (#22C55E) luminous glow, volumetric bloom, centered, lots of empty negative space in the
> upper area, clean and minimal.

### Étape 1 — la pousse (lancement V1)
```
Dark premium sci-fi wallpaper, a tiny glowing circuit-board seedling rooted at the bottom
center, two small luminous leaves on a thin glowing stem, a single bright energy seed at the
base, growing out of dark soil of fine glowing PCB traces and tiny solder pads, pure near-black
background #0B0F17, only electric blue #3B82F6, cyan #22D3EE and green #22C55E glow, volumetric
bloom, centered, lots of empty negative space above, clean minimal, 16:9
```

### Étape 2 — petite plante
```
Dark premium sci-fi wallpaper, a small young circuit-board plant rooted at the bottom center,
slender glowing stem with a handful of small luminous leaves, faint branching beginning, dark
soil of fine glowing PCB traces and solder pads, pure near-black background #0B0F17, only
electric blue #3B82F6, cyan #22D3EE and green #22C55E glow, volumetric bloom, centered, large
empty negative space above, clean minimal, 16:9
```

### Étape 3 — jeune arbuste
```
Dark premium sci-fi wallpaper, a young circuit-board sapling rooted at the bottom center, a
forming glowing trunk with a few branches and a small cluster of luminous leaves, dark soil of
fine glowing PCB traces and solder pads, pure near-black background #0B0F17, only electric blue
#3B82F6, cyan #22D3EE and green #22C55E glow, volumetric bloom, centered, empty negative space
above, clean minimal, 16:9
```

### Étape 4 — jeune arbre
```
Dark premium sci-fi wallpaper, a young circuit-board tree centered, a defined glowing trunk of
fine circuit traces splitting into branches with a growing rounded canopy of glowing leaves,
first visible roots, dark soil of PCB traces with horizontal traces and solder pads spreading
from the base, pure near-black background #0B0F17, only electric blue #3B82F6, cyan #22D3EE and
green #22C55E glow, volumetric bloom, centered, some negative space above, ultra detailed, 16:9
```

### Étape 5 — arbre final (Yggdrasil)
```
Dark premium sci-fi wallpaper, a majestic circuit-board tree of life centered, thick gnarled
trunk built from fine luminous circuit traces branching into a dense rounded canopy of countless
tiny glowing leaves, sprawling fibrous roots below, horizontal PCB traces radiating from the base
ending in glowing solder pads, bright energy core at the trunk base, pure near-black background
#0B0F17, only electric blue #3B82F6, cyan #22D3EE and green #22C55E glow, neon bioluminescent,
volumetric glow, ultra detailed, symmetrical, 16:9
```

### Export
Garde une image par étape, vérifie **zéro ambre** + fond noir pur, exporte en **WebP** :
`public/yn-plant-1.webp` … `yn-plant-5.webp`. Je les branche ensuite au palier de data
(la bonne image s'affiche selon le nombre d'outils du site).
