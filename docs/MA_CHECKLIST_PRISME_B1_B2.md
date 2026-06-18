# Ma checklist - lancer les batchs B1 + B2

Coche au fur et a mesure. A faire sur ta machine (Ollama et Supabase sont chez toi).

---

## Ce que Emperor a deja fait (rien a faire)

- [x] Ecrit B1 (collecte), B2 (enrichissement IA + embeddings)
- [x] Module qwen/ollama local + embeddings nomic-embed-text
- [x] Staging SQLite local, export vers tools.json, publication des embeddings
- [x] Etendu publish.py (pros/cons/FAQ/SEO) sans le casser
- [x] Teste la chaine de bout en bout + corrige un bug de score (plafond 99.99)

---

## BLOC 1 - Preparer (5 min, une seule fois)

- [ ] **1.** Telecharge le modele d'embedding : dans un terminal, tape
      `ollama pull nomic-embed-text`
- [ ] **2.** Verifie qu'Ollama tourne (il sert qwen + les embeddings)
- [ ] **3.** Dans Supabase -> SQL Editor, colle le contenu de
      `database/migration_embeddings_dim_768.sql` et clique Run
      (ca ajuste la table des vecteurs de 1536 a 768)
- [ ] **4.** Installe les dependances Python :
      `cd D:\Emperor\YggNexus\prisme` puis `pip install -r requirements.txt`

---

## BLOC 2 - Lancer la chaine (dans l'ordre)

- [ ] **5.** Collecte : `python b1_collecte.py`
      (va chercher titre/description des 10 sites dans data/sources.json)
- [ ] **6.** Enrichissement IA + embeddings : `python b2_enrichissement.py`
      (qwen redige les fiches, nomic calcule les vecteurs ; Ollama doit tourner)
- [ ] **7.** Export : `python export_tools.py`
      (fusionne dans data/tools.json, garde tes outils existants)
- [ ] **8.** Publication : `python publish.py`
      (pousse les fiches vers Supabase + rafraichit le site)
- [ ] **9.** Embeddings vers la base : `python publish_embeddings.py`

---

## Astuce : tester sans tout lancer

- `python b1_collecte.py --dry-run --limit 3` : voir ce qui serait collecte, sans rien ecrire
- `python b2_enrichissement.py --dry-run` : tester l'enrichissement sans Ollama (faux modele)
- `python b1_collecte.py --only n8n` : traiter un seul outil

---

## Si erreur "disk I/O error" sur staging.db

Rare, arrive sur certains lecteurs Windows. Avant de lancer :
`set STAGING_DB_PATH=C:\staging_yggnexus.db`

---

## Pour ajouter des outils au catalogue plus tard

Ouvre `prisme/data/sources.json`, ajoute une entree
(slug, name, vendor, website_url, categories, primary_category),
puis relance les etapes 5 a 9. Le systeme detecte le neuf tout seul.
