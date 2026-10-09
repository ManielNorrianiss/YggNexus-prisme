# Debloquer la verticale MCP - etape par etape

> **Duree reelle : 6 minutes.** Tout est deja ecrit et verifie. Il ne reste que des gestes de tes mains, sur ta machine Windows.
> **Pourquoi ca traine :** le bac a sable ou je travaille la nuit n'a pas d'acces reseau sortant. Je vois la premiere page du registre MCP (30 serveurs) et jamais la suite. Ton Windows, lui, a l'acces complet. Le mur est chez moi, pas chez toi.
> Cree la nuit du 2026-08-21 (29e nuit). Version 1.

---

## Bloc 1 - Ce que j'ai deja fait a ta place

| Livrable | Chemin | Etat verifie le 2026-08-21 |
|---|---|---|
| Migration SQL des tables `mcp_servers` + `bridges` | `database\migration_mcp_vertical.sql` | 0 caractere non-ASCII, 0 commentaire `--`, 0 bloc `DO`, dollar-quoting `$t$`, idempotent |
| Collecteur du registre officiel | `prisme\b1_mcp.py` | `py_compile` OK, 100 % ASCII, self-test OK, rejeu sur fixture reelle OK (15 lus -> 15 uniques) |
| Constructeur du graphe pont | `prisme\b5_bridges_mcp.py` | `py_compile` OK, 100 % ASCII |
| Lanceur un-clic (collecte + ponts) | `prisme\lancer_mcp.cmd` | ASCII pur, deux scripts en dry-run, aucun push Supabase |
| Deplacement du fichier SQL piege | `prisme\nettoyer_sql_obsolete.cmd` | ASCII pur, renomme seulement, ne supprime rien |
| Sonde du registre en direct | `registry.modelcontextprotocol.io/v0/servers` | HTTP 200, schema `2025-12-11`, page 1 = 30 entrees |

Rien de tout ca n'a touche Supabase. Aucun envoi. Aucune ecriture hors `D:\Emperor\YggNexus`.

---

## Bloc 2 - Les etapes, dans l'ordre

### Etape 1 - Coller le SQL dans Supabase (3 min)

1. Ouvrir `D:\Emperor\YggNexus\database\migration_mcp_vertical.sql` **avec le Bloc-notes**.
2. `Ctrl + A`, puis `Ctrl + C`. **Le fichier au complet, jamais une selection partielle.**
3. Aller sur `https://supabase.com/dashboard`, ouvrir le projet **biykachrofudlvdgtbvo**.
4. Dans le menu de gauche, cliquer **SQL Editor**.
5. Cliquer **New query** (bouton en haut a gauche de la zone d'edition).
6. Dans la fenetre d'edition : `Ctrl + A` puis `Suppr`. **Vider completement**, meme si elle a l'air vide.
7. `Ctrl + V`, puis cliquer **Run** (ou `Ctrl + Entree`).
8. Resultat attendu : bandeau vert **Success. No rows returned**.

### Etape 2 - Verifier que les deux tables existent (30 s)

1. Menu de gauche, cliquer **Table Editor**.
2. Dans la liste des tables du schema `public`, tu dois voir **`mcp_servers`** et **`bridges`**.
3. Les deux sont vides. C'est normal : le SQL cree les contenants, pas le contenu.

### Etape 3 - Lancer la vraie collecte (2 min)

1. Ouvrir l'Explorateur de fichiers sur `D:\Emperor\YggNexus\prisme\`.
2. **Double-cliquer `lancer_mcp.cmd`.**
3. Une fenetre noire s'ouvre et defile. Laisser finir - ca peut prendre quelques minutes, il y a ~100 pages a tirer.
4. Chercher la ligne **`UNIQUE`** dans la sortie : c'est le nombre reel de serveurs MCP du registre, dedoublonne. **C'est le chiffre que j'attends depuis 29 nuits.**
5. La fenetre se termine par `TERMINE. Sorties dans prisme\data\.`

### Etape 4 - Ranger le fichier SQL piege (10 s)

1. Toujours dans `D:\Emperor\YggNexus\prisme\`, **double-cliquer `nettoyer_sql_obsolete.cmd`**.
2. Ca renomme `sql\001_mcp_servers_and_bridges.sql` en `.OBSOLETE`. **Rien n'est supprime**, le fichier reste sur le disque.
3. Pourquoi : ce fichier contient 6 commentaires `--` et 4 blocs `DO $$` avec des ENUM - exactement la construction qui a fait planter Supabase le 16 juin. S'il reste la, un jour on le collera par erreur.

### Etape 5 - Trancher le sort de la tache nocturne

Une fois les etapes 1 a 3 faites, dis-le moi et je reprends le fil : dedup reel, enrichissement, ponts, pages frontend.
Si tu ne fais rien, la tache continue de produire un document par nuit sans faire avancer le projet.

---

## Bloc 3 - Si ca bloque

| Ce que tu vois | Cause | Correctif |
|---|---|---|
| `ERROR: 42P01: relation "the" does not exist` | Le presse-papiers a abime des guillemets simples pendant le collage | Refaire l'etape 1 en entier, en vidant bien la fenetre (`Ctrl+A`, `Suppr`) avant de coller. Ne jamais coller un bloc isole. |
| `ERROR: type "vector" does not exist` | L'extension pgvector n'est pas activee | La premiere ligne du fichier (`create extension if not exists vector;`) s'en occupe. Si l'erreur persiste : **Database -> Extensions**, chercher `vector`, activer. |
| `relation "mcp_servers" already exists` | Tu as deja passe le fichier | Aucun probleme, le fichier est idempotent. Continuer a l'etape 2. |
| `python n'est pas reconnu` en lancant le .cmd | Python absent du PATH Windows | Ouvrir une invite de commande, taper `py --version`. Si ca repond, me le dire : je change `python` pour `py` dans le lanceur. |
| La fenetre noire se ferme instantanement | Erreur au demarrage, trop vite pour la lire | Ouvrir une invite de commande, taper `cd /d D:\Emperor\YggNexus\prisme` puis `lancer_mcp.cmd`, et me copier ce qui s'affiche. |
| `disk I/O error` pendant la collecte | Base de staging sur un disque qui bronche | Dans la meme invite : `set STAGING_DB_PATH=C:\staging_yggnexus.db` puis relancer. |
| La collecte tourne mais `UNIQUE 30` | Le lanceur n'a tire qu'une page | Verifier que la ligne du .cmd contient bien `--max-pages 0` (0 = toutes les pages). |
| Erreur 403 pendant l'enrichissement GitHub | Plafond de requetes GitHub sans jeton | Sans gravite, l'enrichissement est facultatif. La collecte principale est deja faite. |

---

## Bloc 4 - Ce que cette procedure ne fait PAS

- **Elle ne pousse rien dans Supabase.** Les deux scripts restent en dry-run : ils ecrivent des fichiers JSON dans `prisme\data\`, c'est tout. Le remplissage reel des tables est une etape separee, a faire ensemble.
- **Elle ne publie rien sur le site.** Aucune page `/mcp` n'est encore codee cote frontend.
- **Elle ne construit pas les vrais ponts.** `b5_bridges_mcp.py` batit le graphe a partir de ce qu'il trouve dans les fiches ; sans les serveurs en base, il tourne a vide.
- **Elle ne touche pas aux `tools` existants.** La verticale MCP vit dans ses propres tables.
- **Elle ne supprime aucun fichier.** L'etape 4 renomme, elle n'efface pas.

---

*Emperor - artefact de deblocage, nuit du 2026-08-21.*
