# -*- coding: utf-8 -*-
"""
b5_audit_categories.py - Audit LECTURE SEULE de la "categorie" imprimee par le
gabarit de raisons de b5_liens.py (raison_gabarit / _category_label).

Cause : le gabarit imprime le champ libre tools.application_category (valeur
schema.org posee par b2_enrichissement : SoftwareApplication, WebApplication,
BusinessApplication, DeveloperApplication, MultimediaApplication,
UtilitiesApplication), PAS la categorie du site (tool_categories/categories).

Ce script :
  1. mesure la repartition du champ et ses contradictions avec la categorie du
     site (proxy local : staging.db, table tool_categories, car data/tools.json
     a les listes de categories vides depuis le 2026-06-21) ;
  2. propose, outil par outil, une valeur tiree de data/taxonomy.json ;
  3. simule les paires que B5 calculerait (embeddings locaux de staging.db) et
     compte celles dont la raison serait fausse avant / apres correction.

Aucun reseau, aucun .env, aucune ecriture en base. Seule ecriture : le fichier
JSON de proposition (--sortie). --sans-ecriture n'ecrit rien.

Usage :
    python b5_audit_categories.py
    python b5_audit_categories.py --sans-ecriture
    python b5_audit_categories.py --sortie ..\\exports\\b5\\corrections_categories_2026-11-20.json
"""
import argparse
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAUT_SORTIE = ROOT.parent / "exports" / "b5" / "corrections_categories_2026-11-20.json"

# Libelles de gabarit propres, par slug de taxonomie (ce que B5 devrait imprimer).
LIBELLE_SITE = {
    "ai-writing": "AI writing",
    "automation": "automation",
    "ai-images": "AI image",
    "ai-audio": "AI audio",
    "data-scraping": "data and scraping",
    "productivity": "productivity",
    "no-code": "no-code",
    "ai-coding": "AI coding",
    "ai-video": "AI video",
}

GENERIQUES = {"software", "web", "utilities", "business", "education",
              "research", "ai/saas"}
MEDIAS = {"ai-images", "ai-audio", "ai-video"}
# "developer" reste vrai pour ces categories du site
COMPATIBLES_DEVELOPER = {"ai-coding", "no-code", "automation", "data-scraping"}


# ---------------------------------------------------------------------------
# Copie fidele de b5_liens._category_label (version nuit-2026-11-19)
# ---------------------------------------------------------------------------

def label_gabarit(application_category):
    if not application_category:
        return "ai/saas"
    mots = re.findall(r"[A-Z][a-z]*|[a-z]+", application_category)
    if not mots:
        return "ai/saas"
    label = " ".join(mots).lower()
    label = label.replace(" application", "").strip()
    return label or "ai/saas"


# ---------------------------------------------------------------------------
# Chargement (lecture seule)
# ---------------------------------------------------------------------------

def charger_outils():
    brut = (ROOT / "data" / "tools.json").read_bytes().rstrip(b"\x00").rstrip()
    return [t for t in json.loads(brut) if t.get("status") == "published"]


def charger_taxonomie():
    return json.loads((ROOT / "data" / "taxonomy.json").read_text(encoding="utf-8"))


def charger_site_proxy():
    """{slug_outil: slug_categorie_principale} et ensemble des non classes,
    depuis staging.db (lecture seule)."""
    con = sqlite3.connect("file:" + (ROOT / "staging.db").as_posix() + "?mode=ro", uri=True)
    try:
        prim = {s: c for s, c in con.execute(
            "SELECT tool_slug, category_slug FROM tool_categories WHERE is_primary=1")}
        sec = defaultdict(list)
        for s, c in con.execute(
                "SELECT tool_slug, category_slug FROM tool_categories "
                "WHERE is_primary=0 AND category_slug<>''"):
            sec[s].append(c)
    finally:
        con.close()
    return prim, sec


def charger_embeddings(slugs):
    import json as _j
    con = sqlite3.connect("file:" + (ROOT / "staging.db").as_posix() + "?mode=ro", uri=True)
    try:
        out = {}
        for s, emb in con.execute(
                "SELECT slug, embedding_json FROM tool_embeddings "
                "WHERE model='nomic-embed-text'"):
            if s in slugs:
                out[s] = _j.loads(emb)
    finally:
        con.close()
    return out


# ---------------------------------------------------------------------------
# Regle independante : domaine deduit des facettes, etiquettes et du texte
# ---------------------------------------------------------------------------

MOTS_CLES = {
    "ai-video": ["video", "avatar", "text-to-video", "clip"],
    "ai-audio": ["voice", "speech", "music", "audio", "text-to-speech",
                 "podcast", "transcri", "song", "sound"],
    "ai-images": ["image", "photo", "art ", "illustration", "logo", "picture",
                  "sketch", "3d", "design"],
    "ai-coding": ["coding assistant", "code generat", "code completion", "copilot",
                  "pair program", "code review", "refactor", "ide ", "code editor",
                  "autocomplete", "programming assistant"],
    "automation": ["workflow", "automat", "zapier", "integration", "orchestrat"],
    "no-code": ["no-code", "no code", "low-code", "drag-and-drop", "app builder",
                "website builder"],
    "data-scraping": ["scrap", "crawl", "extract data", "dataset", "web data",
                      "data collection"],
    "ai-writing": ["writing", "copywriting", "content generat", "text generat",
                   "essay", "blog", "chatbot", "assistant", "summar", "translat",
                   "prompt"],
    "productivity": ["notes", "meeting", "calendar", "task", "collaborat",
                     "productiv", "workspace", "to-do", "email"],
}

MODALITE_VERS_SLUG = {"video": "ai-video", "audio": "ai-audio",
                      "image": "ai-images", "3d": "ai-images"}


def signaux_domaine(outil):
    """Retourne {slug: [signaux]} pour les 9 categories de la taxonomie."""
    sig = defaultdict(list)
    fac = outil.get("facets") or {}
    for m in fac.get("modality", []) or []:
        if m in MODALITE_VERS_SLUG:
            sig[MODALITE_VERS_SLUG[m]].append("modalite:" + m)
    tags = " ".join((t.get("slug", "") + " " + t.get("label", "")).lower()
                    for t in outil.get("tags", []) or [])
    texte = " " + " ".join([outil.get("name", ""), outil.get("short_desc", ""), tags]).lower() + " "
    for slug, mots in MOTS_CLES.items():
        for mot in mots:
            if mot in texte:
                sig[slug].append("mot:" + mot.strip())
    return sig


def domaine_regle(outil):
    """(slug ou None, nb de types de signaux, signaux). Prend le plus fort ;
    en cas d'egalite stricte, None."""
    sig = signaux_domaine(outil)
    if not sig:
        return None, 0, {}
    classement = sorted(sig.items(), key=lambda kv: -len(set(kv[1])))
    top_slug, top_sig = classement[0]
    if len(classement) > 1 and len(set(classement[1][1])) == len(set(top_sig)):
        return None, len(set(top_sig)), {k: sorted(set(v)) for k, v in sig.items()}
    return top_slug, len(set(top_sig)), {k: sorted(set(v)) for k, v in sig.items()}


def signaux_developpeur(outil):
    fac = outil.get("facets") or {}
    if "code" in (fac.get("modality") or []):
        return True
    if "developers" in (fac.get("audience") or []):
        return True
    tags = " ".join(t.get("slug", "") for t in outil.get("tags", []) or [])
    return any(m in tags for m in ("api", "sdk", "developer", "ide", "mcp", "code",
                                   "llm", "open-source", "devops"))


def signaux_media(outil):
    fac = outil.get("facets") or {}
    return any(m in (fac.get("modality") or []) for m in ("image", "video", "audio", "3d"))


# ---------------------------------------------------------------------------
# Verdict sur la valeur imprimee
# ---------------------------------------------------------------------------

def verdict_valeur(outil, site):
    """Retourne (verdict, motif).
    verdict : 'fausse' | 'generique' | 'vague' | 'plausible' | 'ok'
      fausse     : contredit la categorie du site ou, sans categorie du site,
                   les signaux de l'outil
      generique  : software, web, utilities, business... (ne dit rien)
      vague      : vraie mais moins precise que la categorie du site (ex.
                   multimedia pour de la video)
      plausible  : pas de categorie du site, valeur non contredite
      ok         : coherente avec la categorie du site
    """
    lab = label_gabarit(outil.get("application_category"))
    if lab in GENERIQUES:
        return "generique", "valeur generique : " + lab
    if lab == "multimedia":
        if site in MEDIAS:
            return "vague", "multimedia couvre ai-video/ai-images/ai-audio sans preciser"
        if site is None:
            return ("plausible", "multimedia, pas de categorie du site, modalite media") \
                if signaux_media(outil) else ("fausse", "multimedia sans signal media")
        return "fausse", "multimedia mais le site classe en " + site
    if lab == "developer":
        if site == "ai-coding":
            return "ok", "developer et ai-coding concordent"
        if site in COMPATIBLES_DEVELOPER:
            return "vague", "developer compatible avec " + site
        if site is None:
            return ("plausible", "developer, pas de categorie du site, signaux developpeur") \
                if signaux_developpeur(outil) else ("fausse", "developer sans signal developpeur")
        return "fausse", "developer mais le site classe en " + site
    return "fausse", "valeur hors liste : " + lab


# ---------------------------------------------------------------------------
# Jugement a la lecture (partie a relire par Josue)
# ---------------------------------------------------------------------------

# slug -> (slug de taxonomie ou None, note). Rempli apres lecture des
# descriptions des cas ou la regle et la categorie du site divergent, ou ou
# le site n'a pas de categorie.
JUGEMENT = {
    # --- la categorie du site (proxy) parait fausse a la lecture de la description
    "trae": ("ai-coding", "assistant de code ; le site le range en productivity"),
    "aicodingcompare": ("ai-coding", "comparateur d'outils de code ; le site dit productivity"),
    "gonewx": ("ai-coding", "rejoue des sessions de code assistees par IA"),
    "superset": ("ai-coding", "execute plusieurs agents de code en parallele"),
    "nimbalyst": ("ai-coding", "editeur visuel pour Claude Code et Codex"),
    "conductor": ("ai-coding", "agents de code en parallele"),
    "replit-com": ("ai-coding", "Replit Agent ; replit lui-meme est deja ai-coding"),
    "wisprflow": ("ai-audio", "dictee vocale ; le site dit ai-writing"),
    "clipwing": ("ai-video", "cree des clips video ; le site dit productivity"),
    "grok-x-ai": ("ai-writing", "assistant conversationnel ; le site dit ai-images"),
    "composio": ("automation", "relie des agents a des applications SaaS"),
    # --- aucune categorie de la taxonomie ne convient
    "ollama": (None, "executeur de modeles locaux : aucune des neuf categories ne convient"),
    "lochbot": (None, "verificateur d'injection de prompt : le site dit data-scraping, a tort"),
    "mitre": (None, "base de menaces IA : le site dit data-scraping, a tort"),
    # --- outil sans categorie du site : la regle se trompait ou rien ne convient
    "autodesk": (None, "outil de conception et simulation : rien ne convient"),
    "datarobot": (None, "plateforme de modeles pour entreprises : rien ne convient"),
    "nvidia": (None, "extension Omniverse : rien ne convient"),
    "pixray": (None, "droits d'auteur pour photographes : pas de la generation d'images"),
    "llamaindex": (None, "cadriciel pour agents et documents : rien ne convient"),
    "agen": (None, "repertoire d'agents : rien ne convient"),
    "aidepot": (None, "repertoire d'outils : rien ne convient"),
    "salesagent": (None, "copilote de vente en appel : rien ne convient"),
    "withgoogle-com": (None, "prototypage d'interfaces : ni image ni code au sens de la taxonomie"),
    "krater": (None, "plateforme de plusieurs modeles : rien ne convient"),
    "thebricks": (None, "tableaux de bord sur CSV : rien ne convient"),
    "unsolomind": (None, "PDF vers base de connaissances : rien ne convient"),
    "ugcfast": (None, "publicites UGC : rien ne convient"),
    "googleblog": (None, "blogue de recherche, pas un outil"),
    "noemamag": (None, "magazine d'essais, pas un outil"),
    "theconversation": (None, "publication, pas un outil"),
    "darioamodei": (None, "essais personnels, pas un outil"),
    "piszek": (None, "blogue personnel, pas un outil"),
    "mathgptpro": (None, "tuteur de mathematiques : la regle disait ai-images, a tort"),
    # --- jugements positifs, sans categorie du site
    "mistral-ai": ("ai-writing", "assistant conversationnel"),
    "sqlai": ("ai-coding", "genere des requetes SQL"),
    "heytensor": ("ai-coding", "corrige des erreurs de code PyTorch"),
    "itsconvo": ("productivity", "assistant de reunion (la taxonomie range les reunions en productivity)"),
    "summarytube": ("ai-writing", "resume de videos YouTube : c'est du resume de texte, pas de la video"),
    "digitalhumans": ("ai-video", "humains numeriques"),
}


# ---------------------------------------------------------------------------
# Proposition
# ---------------------------------------------------------------------------

def proposer(outil, site, secondaires, nom_par_slug):
    """Retourne un dict de proposition ou None (rien a corriger)."""
    verdict, motif = verdict_valeur(outil, site)
    if verdict in ("ok", "plausible"):
        return None, verdict, motif
    slug = outil["slug"]
    regle, nb_sig, sig = domaine_regle(outil)
    valeur, source, conf, note = None, "", "a voir", ""

    if slug in JUGEMENT:
        valeur, note = JUGEMENT[slug]
        source, conf = "jugement", ("probable" if valeur else "a voir")
        if site and valeur == site:
            conf = "sur"
    elif site:
        valeur, source = site, "categorie du site (staging.db)"
        if regle == site:
            conf = "sur"
        elif regle is None:
            conf = "probable"
        else:
            conf = "a voir"
            note = "la regle (facettes, etiquettes, texte) pencherait pour " + regle
    else:
        if regle and nb_sig >= 2:
            valeur, source, conf = regle, "regle (facettes, etiquettes, texte)", "probable"
        elif regle:
            valeur, source, conf = None, "aucune (un seul signal, trop faible)", "a voir"
            note = ("signal unique pour " + regle + " ; B5 devrait n'imprimer "
                    "aucune categorie pour cet outil")
        else:
            valeur, source, conf = None, "aucune (outil non classe, aucun signal net)", "a voir"
            note = "B5 devrait n'imprimer aucune categorie pour cet outil"

    return {
        "slug": slug,
        "nom": outil.get("name", ""),
        "valeur_actuelle": outil.get("application_category") or "",
        "libelle_imprime_actuel": label_gabarit(outil.get("application_category")),
        "verdict_actuel": verdict,
        "motif": motif,
        "categorie_site_proxy": site,
        "valeur_proposee": valeur,
        "libelle_propose": LIBELLE_SITE.get(valeur) if valeur else None,
        "nom_categorie_site": nom_par_slug.get(valeur) if valeur else None,
        "source": source,
        "confiance": conf,
        "note": note,
        "description_courte": outil.get("short_desc", ""),
    }, verdict, motif


# ---------------------------------------------------------------------------
# Simulation des paires de B5
# ---------------------------------------------------------------------------

def paires_candidates(outils, top=5, seuil=0.55):
    import numpy as np
    emb = charger_embeddings({o["slug"] for o in outils})
    ids = [o["slug"] for o in outils if o["slug"] in emb]
    mat = np.array([emb[s] for s in ids], dtype=float)
    n = np.linalg.norm(mat, axis=1, keepdims=True)
    mat = mat / np.where(n == 0, 1.0, n)
    sim = np.round(mat @ mat.T, 3)
    paires = []
    for i, s in enumerate(ids):
        cand = [(float(sim[i, j]), ids[j]) for j in range(len(ids))
                if j != i and sim[i, j] >= seuil]
        cand.sort(key=lambda x: -x[0])
        for _, a in cand[:top]:
            paires.append((s, a))
    return paires


def evaluer_paires(paires, etat_avant, etat_apres):
    """etat_* : {slug: 'faux'|'vague'|'ok'|'inconnu'}. Compte les paires dont la
    raison de gabarit contiendrait au moins un libelle de la classe."""
    def classe(s, etat):
        return etat.get(s, "ok")
    res = {}
    for nom, etat in (("avant", etat_avant), ("apres", etat_apres)):
        c = Counter()
        for a, b in paires:
            ca, cb = classe(a, etat), classe(b, etat)
            if "faux" in (ca, cb):
                c["au_moins_un_libelle_faux"] += 1
            if "vague" in (ca, cb):
                c["au_moins_un_libelle_generique_ou_vague"] += 1
            if "inconnu" in (ca, cb):
                c["au_moins_un_libelle_incertain"] += 1
        res[nom] = dict(c)
    return res


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Audit des categories imprimees par B5 (lecture seule)")
    ap.add_argument("--sortie", default=str(DEFAUT_SORTIE))
    ap.add_argument("--sans-ecriture", action="store_true")
    args = ap.parse_args()

    outils = charger_outils()
    tax = charger_taxonomie()
    nom_par_slug = {c["slug"]: c["name"] for c in tax}
    prim, sec = charger_site_proxy()

    rep = Counter(label_gabarit(o.get("application_category")) for o in outils)
    propositions, verdicts = [], {}
    contradiction_site = 0
    avec_site = 0
    for o in outils:
        site = prim.get(o["slug"]) or None
        if site:
            avec_site += 1
        prop, v, motif = proposer(o, site, sec.get(o["slug"], []), nom_par_slug)
        verdicts[o["slug"]] = v
        if v == "fausse" and site:
            contradiction_site += 1
        if prop:
            propositions.append(prop)

    cv = Counter(verdicts.values())
    conf = Counter(p["confiance"] for p in propositions)
    sans_valeur = sum(1 for p in propositions if p["valeur_proposee"] is None)

    # simulation des paires
    etat_avant = {s: ("faux" if v == "fausse" else "vague" if v in ("generique", "vague") else "ok")
                  for s, v in verdicts.items()}
    etat_apres = {}
    par_slug = {p["slug"]: p for p in propositions}
    for s, v in verdicts.items():
        p = par_slug.get(s)
        if p is None:
            etat_apres[s] = "ok"
        elif p["valeur_proposee"] is None:
            etat_apres[s] = "ok"      # B5 n'imprime rien : pas de raison fausse
        elif p["confiance"] == "a voir":
            etat_apres[s] = "inconnu"
        else:
            etat_apres[s] = "ok"
    paires = paires_candidates(outils)
    sim = evaluer_paires(paires, etat_avant, etat_apres)

    bilan = {
        "nb_outils_publies": len(outils),
        "repartition_libelle_imprime": dict(rep.most_common()),
        "avec_categorie_site_proxy": avec_site,
        "sans_categorie_site_proxy": len(outils) - avec_site,
        "verdicts": dict(cv),
        "fausses_avec_categorie_site": contradiction_site,
        "nb_propositions": len(propositions),
        "confiance": dict(conf),
        "propositions_sans_valeur": sans_valeur,
        "paires_candidates_top5_seuil055": len(paires),
        "simulation_paires": sim,
    }

    sortie = {
        "genere_par": "prisme/b5_audit_categories.py",
        "date": "2026-11-20",
        "avertissement": (
            "Proposition, aucune donnee de production modifiee. La categorie du site "
            "est un proxy (staging.db, classement du 2026-08-05) : data/tools.json a "
            "ses listes de categories vides depuis le 2026-06-21 et la table "
            "tool_categories de production n'a pas ete lue (aucun reseau). "
            "Identifiant = slug (tools.json ne porte pas l'id de base)."
        ),
        "taxonomie": nom_par_slug,
        "bilan": bilan,
        "corrections": propositions,
    }
    print(json.dumps(bilan, ensure_ascii=False, indent=2))
    if not args.sans_ecriture:
        chemin = Path(args.sortie)
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(json.dumps(sortie, ensure_ascii=False, indent=2), encoding="utf-8")
        print("[audit] ecrit :", chemin)
    return 0


if __name__ == "__main__":
    sys.exit(main())
