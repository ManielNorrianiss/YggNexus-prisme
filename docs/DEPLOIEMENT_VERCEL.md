# Mise en ligne YggNexus sur Vercel

Strategie retenue : repo GitHub dedie au site (le cerveau Emperor reste prive et separe).
On ne pousse que le dossier `frontend/`. Le Prisme et la base restent locaux.

## 1. Creer le repo GitHub

- Sur GitHub : New repository -> nom `YggNexus`, visibilite **Private**
- Ne pas ajouter de README ni de .gitignore (le frontend en a deja un)

## 2. Pousser le frontend (depuis ton terminal local)

Dans `D:\Emperor\YggNexus\frontend` :

```
git init
git add .
git commit -m "YggNexus frontend - mise en ligne initiale"
git branch -M main
git remote add origin git@github.com:ManielNorrianiss/YggNexus.git
git push -u origin main
```

Verifie apres le push : sur GitHub, il **ne doit PAS** y avoir `.env.local` ni `node_modules`
(deja exclus par `frontend/.gitignore`).

## 3. Importer dans Vercel

- vercel.com -> Add New -> Project -> Import `ManielNorrianiss/YggNexus`
- Framework : Next.js (auto-detecte)
- Root Directory : `./` (le repo EST le frontend)
- Build : laisser les valeurs par defaut

## 4. Variables d'environnement (onglet Environment Variables, scope Production)

| Variable | Valeur |
|---|---|
| NEXT_PUBLIC_SUPABASE_URL | meme valeur que `frontend/.env.local` |
| NEXT_PUBLIC_SUPABASE_ANON_KEY | meme valeur que `frontend/.env.local` |
| NEXT_PUBLIC_SITE_URL | https://yggnexus.com (sans slash final) |
| REVALIDATE_SECRET | meme valeur que `prisme/.env` |

Puis : Deploy.

## 5. Domaine

- Vercel -> projet -> Settings -> Domains -> ajouter `yggnexus.com`
- Suivre les instructions DNS de Vercel chez ton registraire (A / CNAME)

## 6. Apres mise en ligne : reconnecter le Prisme a la prod

Dans `prisme/.env`, mettre :

```
SITE_URL=https://yggnexus.com
```

Ainsi `publish.py` appellera l'endpoint `/api/revalidate` de la prod (et non plus localhost)
quand il rafraichit les pages apres publication.

## 7. Verification finale

- Ouvrir https://yggnexus.com : page d'accueil + fiches `/tools/[slug]` doivent s'afficher
- `https://yggnexus.com/sitemap.xml` et `/robots.txt` repondent
- Lancer un `publish.py` -> verifier que la page rafraichie change en prod

## Rappel securite

Avant ou apres la mise en ligne, appliquer `database/securite_rls.sql` dans Supabase
(SQL Editor). Le RLS ne casse pas le Prisme (cle service_role) ni le site (lecture anon
des contenus publies).
