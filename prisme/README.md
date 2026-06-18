# Prisme - pont de publication (batch B7)

Prend une liste d'outils prepares, les depose dans Supabase, puis rafraichit les pages du site.

## Mise en place (une seule fois)

1. `cp .env.example .env` puis remplir les valeurs dans `.env` :
   - `SUPABASE_URL` : meme URL que le frontend (https://xxxx.supabase.co)
   - `SUPABASE_SERVICE_KEY` : cle **service_role** (Supabase > Project Settings > API > service_role secret)
   - `SITE_URL` : http://localhost:3000 en local
   - `REVALIDATE_SECRET` : la meme valeur que dans frontend/.env.local
2. `pip install -r requirements.txt`

## Utilisation

```bash
python publish.py --dry-run   # montre ce qui serait fait, sans rien ecrire
python publish.py             # publie dans Supabase + rafraichit le site
```

## Donnees

`data/tools.json` : liste d'outils a publier. Chaque outil peut avoir :
slug, name, vendor, website_url, pricing, pricing_note, short_desc,
description_md, application_category, quality_score, status,
categories (liste de slugs), primary_category.

C'est ce fichier que les batchs amont (collecte + enrichissement IA) rempliront
plus tard automatiquement. Pour l'instant on l'edite a la main pour tester le pont.
