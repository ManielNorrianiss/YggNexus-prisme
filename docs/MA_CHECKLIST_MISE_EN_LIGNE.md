# Ma checklist - mettre YggNexus en ligne

Coche les cases au fur et a mesure. Trois blocs, dans l'ordre.

---

## Ce que Emperor a deja fait (rien a faire ici)

- [x] Ecrit le fichier des serrures `database/securite_rls.sql` (valide)
- [x] Verifie que le site compile sans erreur
- [x] Verifie qu'aucune cle secrete ne partira dans le commit
- [x] Ecrit le guide `docs/DEPLOIEMENT_VERCEL.md`

---

## BLOC A - Poser les serrures sur la base (5 min)

- [ ] **A1.** Ouvre Supabase et va dans ton projet `biykachrofudlvdgtbvo`
- [ ] **A2.** Clique sur **SQL Editor** dans le menu de gauche
- [ ] **A3.** Ouvre le fichier `database/securite_rls.sql`, copie **tout** son contenu
- [ ] **A4.** Colle dans l'editeur, clique **Run**
- [ ] **A5.** Verifie qu'il n'y a pas d'erreur rouge en bas

> Resultat : ton site et ta base sont verrouilles. Le public peut juste regarder
> les contenus publies, personne ne peut ecrire. Le Prisme, lui, continue normalement.

---

## BLOC B - Mettre le site en ligne (20-30 min)

### Creer le coffre sur GitHub
- [ ] **B1.** Sur github.com, clique **New repository**
- [ ] **B2.** Nom : `YggNexus` -- Visibilite : **Private** -- ne coche RIEN d'autre (pas de README)
- [ ] **B3.** Clique **Create repository**

### Envoyer le site dans le coffre
- [ ] **B4.** Ouvre un terminal dans le dossier `D:\Emperor\YggNexus\frontend`
- [ ] **B5.** Colle ces commandes une par une :

```
git init
git add .
git commit -m "YggNexus frontend - mise en ligne initiale"
git branch -M main
git remote add origin git@github.com:ManielNorrianiss/YggNexus.git
git push -u origin main
```

- [ ] **B6.** Recharge la page GitHub : tu dois voir les dossiers `app`, `components`, `lib`
- [ ] **B7.** Verifie qu'il n'y a **PAS** de `.env.local` ni `node_modules` sur GitHub

### Brancher Vercel
- [ ] **B8.** Sur vercel.com : **Add New -> Project**
- [ ] **B9.** Importe le repo `ManielNorrianiss/YggNexus`
- [ ] **B10.** Root Directory : laisse `./` -- Framework : Next.js (auto)
- [ ] **B11.** Dans **Environment Variables**, ajoute ces 4 lignes :

| Nom | Valeur a coller |
|---|---|
| NEXT_PUBLIC_SUPABASE_URL | la meme que dans `frontend/.env.local` |
| NEXT_PUBLIC_SUPABASE_ANON_KEY | la meme que dans `frontend/.env.local` |
| NEXT_PUBLIC_SITE_URL | https://yggnexus.com |
| REVALIDATE_SECRET | la meme que dans `prisme/.env` |

- [ ] **B12.** Clique **Deploy** et attends la fin (qq minutes)
- [ ] **B13.** Ouvre l'URL que Vercel te donne : ta page d'accueil doit s'afficher

### Brancher ton nom de domaine
- [ ] **B14.** Vercel -> projet -> **Settings -> Domains** -> ajoute `yggnexus.com`
- [ ] **B15.** Va chez ton registraire de domaine et ajoute les enregistrements DNS que Vercel affiche
- [ ] **B16.** Attends que `https://yggnexus.com` reponde (parfois jusqu'a 1h)

---

## BLOC C - Reconnecter le Prisme a la prod (2 min)

- [ ] **C1.** Ouvre `prisme/.env`
- [ ] **C2.** Mets : `SITE_URL=https://yggnexus.com`
- [ ] **C3.** Sauvegarde

> Resultat : quand le Prisme publie la nuit, il rafraichit le vrai site en ligne,
> plus le site local.

---

## Quand tout est coche

Dis-le a Emperor : on enchaine sur le chantier suivant (les batchs du Prisme,
ou les pages SEO manquantes).
