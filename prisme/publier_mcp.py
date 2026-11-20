"""
publier_mcp.py - Remplit les tables Supabase mcp_servers et bridges (ajouts seulement).

Lit les fichiers de staging produits localement :
  --quoi serveurs  data/mcp_servers_staging.json  -> table mcp_servers (conflit sur slug)
  --quoi ponts     data/bridges_staging.json      -> table bridges
                   (conflit sur source_type,source_id,target_type,target_id,relation)

Par defaut c'est un ESSAI A BLANC : rien n'est envoye, le script affiche les
comptes LUS, VALIDES, ECARTES (par raison) et LOTS. L'envoi reel demande
--pousser explicitement.

Ajouts seulement : l'envoi est un POST avec
"Prefer: resolution=ignore-duplicates". Une ligne deja presente est laissee
telle quelle. Le script ne modifie et n'efface jamais rien.

Les identifiants viennent de prisme/.env (SUPABASE_URL, SUPABASE_SERVICE_KEY)
ou des variables d'environnement. Ils ne sont jamais affiches.

Usage:
  python publier_mcp.py                                  # essai a blanc, serveurs
  python publier_mcp.py --quoi ponts                     # essai a blanc, ponts
  python publier_mcp.py --pousser --limite 500           # premier petit lot reel
  python publier_mcp.py --pousser                        # tout envoyer
  python publier_mcp.py --pousser --depuis 500 --lot 200
"""

import argparse
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
ENV_PATH = os.path.join(HERE, ".env")

DEFAULT_LOT = 500
MAX_ESSAIS = 5
CODES_PASSAGERS = (429, 500, 502, 503, 504)
METHODES_PERMISES = ("GET", "POST")
INT_MAX = 2147483647

PACKAGE_TYPES = ("npm", "pypi", "oci", "docker", "nuget", "mcpb", "unknown")
TRANSPORTS = ("stdio", "http", "sse", "streamable-http", "unknown")
HOSTINGS = ("local", "remote", "hybrid", "unknown")

# Colonnes envoyees, dans l'ordre. id, embedding, created_at, updated_at
# ne sont jamais envoyes.
COLONNES_SERVEURS = (
    "slug", "name", "description", "author", "repo_url", "registry_source",
    "package_type", "package_types", "transport", "transports", "capabilities",
    "hosting", "version", "website_url", "license", "stars", "weekly_downloads",
    "quality_score", "status", "is_latest", "published_at",
    "package_identifier", "package_ids", "remote_urls",
)
COLONNES_PONTS = (
    "source_type", "source_id", "target_type", "target_id", "relation",
    "weight", "evidence",
)
CLE_PONTS = ("source_type", "source_id", "target_type", "target_id", "relation")

TEXTES_SERVEURS = ("description", "author", "repo_url", "registry_source", "version",
                   "website_url", "license", "package_identifier", "published_at")
TABLEAUX_SERVEURS = ("package_types", "transports", "capabilities", "package_ids", "remote_urls")

CIBLES = {
    "serveurs": {
        "table": "mcp_servers",
        "conflit": "slug",
        "colonnes": COLONNES_SERVEURS,
        "entree": os.path.join(DATA_DIR, "mcp_servers_staging.json"),
    },
    "ponts": {
        "table": "bridges",
        "conflit": ",".join(CLE_PONTS),
        "colonnes": COLONNES_PONTS,
        "entree": os.path.join(DATA_DIR, "bridges_staging.json"),
    },
}


# ---------------------------------------------------------------------------
# Identifiants
# ---------------------------------------------------------------------------

def lire_env(path):
    """Petit lecteur de lignes CLE=valeur. Retourne {} si le fichier manque."""
    valeurs = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            lignes = f.read().splitlines()
    except OSError:
        return valeurs
    for ligne in lignes:
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, valeur = ligne.split("=", 1)
        cle = cle.strip()
        if cle.startswith("export "):
            cle = cle[len("export "):].strip()
        valeur = valeur.strip()
        if len(valeur) >= 2 and valeur[0] == valeur[-1] and valeur[0] in ("'", '"'):
            valeur = valeur[1:-1]
        valeurs[cle] = valeur
    return valeurs


def charger_identifiants(env=None, env_path=ENV_PATH):
    """Variables d'environnement d'abord, sinon prisme/.env."""
    env = os.environ if env is None else env
    fichier = lire_env(env_path)
    url = env.get("SUPABASE_URL") or fichier.get("SUPABASE_URL") or ""
    cle = env.get("SUPABASE_SERVICE_KEY") or fichier.get("SUPABASE_SERVICE_KEY") or ""
    return url.strip(), cle.strip()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _est_texte(v):
    return isinstance(v, str)


def _est_entier(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _est_nombre(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _texte_sain(v):
    return "\x00" not in v


def _liste_de_textes(v):
    return isinstance(v, list) and all(isinstance(x, str) and "\x00" not in x for x in v)


def valider_serveur(rec):
    """Retourne None si l'enregistrement est valide, sinon la raison d'ecart."""
    if not isinstance(rec, dict):
        return "pas un objet"
    for col in COLONNES_SERVEURS:
        if col not in rec:
            return "cle manquante"
    for col in ("slug", "name"):
        v = rec[col]
        if not _est_texte(v) or not v.strip():
            return col + " vide"
        if not _texte_sain(v):
            return "caractere nul"
    if rec["package_type"] is not None and rec["package_type"] not in PACKAGE_TYPES:
        return "package_type hors liste"
    if rec["transport"] is not None and rec["transport"] not in TRANSPORTS:
        return "transport hors liste"
    if rec["hosting"] is not None and rec["hosting"] not in HOSTINGS:
        return "hosting hors liste"
    for col in ("stars", "weekly_downloads"):
        v = rec[col]
        if v is not None and (not _est_entier(v) or v < 0 or v > INT_MAX):
            return col + " pas un entier"
    q = rec["quality_score"]
    if q is not None and (not _est_nombre(q) or abs(q) >= 100):
        return "quality_score invalide"
    for col in TABLEAUX_SERVEURS:
        if not _liste_de_textes(rec[col]):
            return col + " pas une liste de textes"
    for col in TEXTES_SERVEURS:
        v = rec[col]
        if v is not None and (not _est_texte(v) or not _texte_sain(v)):
            return col + " pas un texte"
    if not _est_texte(rec["status"]) or not rec["status"].strip():
        return "status vide"
    if not isinstance(rec["is_latest"], bool):
        return "is_latest pas un booleen"
    return None


def valider_pont(rec):
    if not isinstance(rec, dict):
        return "pas un objet"
    for col in COLONNES_PONTS:
        if col not in rec:
            return "cle manquante"
    for col in CLE_PONTS:
        v = rec[col]
        if not _est_texte(v) or not v.strip():
            return col + " vide"
        if not _texte_sain(v):
            return "caractere nul"
    w = rec["weight"]
    if not _est_nombre(w) or w < 0 or w > 9.9999:
        return "weight hors 0 a 9.9999"
    e = rec["evidence"]
    if e is not None and (not _est_texte(e) or not _texte_sain(e)):
        return "evidence pas un texte"
    return None


def preparer(quoi, records):
    """Valide, ecarte et compte. Retourne (lignes_valides, compte_par_raison).
    Aucun enregistrement n'est corrige : il passe tel quel ou il est ecarte."""
    cible = CIBLES[quoi]
    colonnes = cible["colonnes"]
    valider = valider_serveur if quoi == "serveurs" else valider_pont
    ecarts = Counter()
    valides = []
    slugs = set()
    noms = set()
    cles = set()
    for rec in records:
        raison = valider(rec)
        if raison is None and quoi == "serveurs":
            if rec["slug"] in slugs:
                raison = "slug en double"
            elif rec["name"] in noms:
                raison = "nom en double"
        elif raison is None:
            cle = tuple(rec[c] for c in CLE_PONTS)
            if cle in cles:
                raison = "pont en double"
        if raison is not None:
            ecarts[raison] += 1
            continue
        if quoi == "serveurs":
            slugs.add(rec["slug"])
            noms.add(rec["name"])
        else:
            cles.add(tuple(rec[c] for c in CLE_PONTS))
        valides.append({c: rec[c] for c in colonnes})
    return valides, ecarts


def decouper(lignes, taille):
    return [lignes[i:i + taille] for i in range(0, len(lignes), taille)]


# ---------------------------------------------------------------------------
# Lecture du staging
# ---------------------------------------------------------------------------

def lire_staging(path, quoi):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        cle = "records" if quoi == "serveurs" else "bridges"
        return list(data.get(cle) or [])
    return list(data)


# ---------------------------------------------------------------------------
# Reseau (injectable)
# ---------------------------------------------------------------------------

def envoyer_http(methode, url, headers, corps):
    """Expediteur par defaut. Retourne (code, entetes_en_minuscules, texte).
    Une reponse HTTP d'erreur est retournee, pas levee ; une erreur reseau
    est levee (OSError)."""
    if methode not in METHODES_PERMISES:
        raise ValueError("methode interdite: " + str(methode))
    req = urllib.request.Request(url, data=corps, headers=headers, method=methode)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            texte = r.read().decode("utf-8", "replace")
            return r.status, {k.lower(): v for k, v in r.headers.items()}, texte
    except urllib.error.HTTPError as e:
        try:
            texte = e.read().decode("utf-8", "replace")
        except Exception:
            texte = ""
        return e.code, {k.lower(): v for k, v in (e.headers or {}).items()}, texte


def _masquer(texte, secrets):
    for s in secrets:
        if s:
            texte = texte.replace(s, "***")
    return texte


def entetes_rest(cle, extra=None):
    h = {
        "apikey": cle,
        "Authorization": "Bearer " + cle,
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def compter_table(sender, base, table, cle):
    """Compte exact via l'en-tete Content-Range. None si indisponible."""
    url = base + "/rest/v1/" + table + "?select=id"
    h = entetes_rest(cle, {"Prefer": "count=exact", "Range": "0-0"})
    try:
        code, entetes, _ = sender("GET", url, h, None)
    except OSError:
        return None
    cr = entetes.get("content-range", "")
    if "/" in cr:
        total = cr.rsplit("/", 1)[1].strip()
        if total.isdigit():
            return int(total)
    return None


def envoyer_lot(sender, pause, url, cle, lot):
    """Un POST avec reprise sur erreur passagere. Retourne (ok, code, corps)."""
    corps = json.dumps(lot, ensure_ascii=False).encode("utf-8")
    h = entetes_rest(cle, {"Prefer": "resolution=ignore-duplicates,return=minimal"})
    dernier = (0, "")
    for essai in range(1, MAX_ESSAIS + 1):
        try:
            code, _, texte = sender("POST", url, h, corps)
        except OSError as e:
            code, texte = 0, "erreur reseau: " + type(e).__name__
        if 200 <= code < 300:
            return True, code, texte
        dernier = (code, texte)
        passager = code == 0 or code in CODES_PASSAGERS
        if not passager:
            break
        if essai < MAX_ESSAIS:
            pause(2 ** (essai - 1))
    return False, dernier[0], dernier[1]


# ---------------------------------------------------------------------------
# Programme principal
# ---------------------------------------------------------------------------

def main(argv=None, sender=None, env=None, pause=time.sleep, env_path=ENV_PATH):
    ap = argparse.ArgumentParser(description="Remplit mcp_servers et bridges (ajouts seulement)")
    ap.add_argument("--quoi", choices=("serveurs", "ponts"), default="serveurs")
    ap.add_argument("--in", dest="in_path", default=None, help="fichier de staging")
    ap.add_argument("--pousser", action="store_true",
                    help="envoie pour vrai (sans cela : essai a blanc)")
    ap.add_argument("--lot", type=int, default=DEFAULT_LOT, help="lignes par lot (defaut 500)")
    ap.add_argument("--limite", type=int, default=None, help="plafond de lignes envoyees")
    ap.add_argument("--depuis", type=int, default=0, help="saute les N premieres lignes valides")
    args = ap.parse_args(argv)

    if args.lot < 1 or args.depuis < 0 or (args.limite is not None and args.limite < 0):
        sys.stderr.write("ERREUR: --lot >= 1, --depuis >= 0, --limite >= 0\n")
        return 2

    cible = CIBLES[args.quoi]
    in_path = args.in_path or cible["entree"]
    try:
        records = lire_staging(in_path, args.quoi)
    except Exception as e:
        sys.stderr.write("ERREUR lecture: " + type(e).__name__ + "\n")
        return 2

    valides, ecarts = preparer(args.quoi, records)
    selection = valides[args.depuis:]
    if args.limite is not None:
        selection = selection[:args.limite]
    lots = decouper(selection, args.lot)

    print("TABLE " + cible["table"] + " (conflit sur " + cible["conflit"] + ")")
    print("LUS " + str(len(records)))
    print("VALIDES " + str(len(valides)))
    print("ECARTES " + str(sum(ecarts.values())))
    for raison, n in sorted(ecarts.items(), key=lambda p: (-p[1], p[0])):
        print("  " + raison + ": " + str(n))
    print("LOTS " + str(len(lots)) + " (" + str(len(selection)) + " lignes, lots de " + str(args.lot) + ")")

    if not args.pousser:
        print("ESSAI A BLANC: rien n'a ete envoye. Ajouter --pousser pour envoyer.")
        return 0

    base, cle = charger_identifiants(env, env_path)
    if not base or not cle:
        sys.stderr.write("ERREUR: SUPABASE_URL et SUPABASE_SERVICE_KEY introuvables "
                         "(prisme/.env ou variables d'environnement)\n")
        return 2
    base = base.rstrip("/")
    secrets = (cle,)
    sender = sender or envoyer_http
    url = base + "/rest/v1/" + cible["table"] + "?on_conflict=" + cible["conflit"]

    avant = compter_table(sender, base, cible["table"], cle)
    print("COMPTE AVANT " + (str(avant) if avant is not None else "inconnu"))

    passes = 0
    for numero, lot in enumerate(lots, start=1):
        ok, code, texte = envoyer_lot(sender, pause, url, cle, lot)
        if not ok:
            extrait = _masquer(texte or "", secrets)[:300]
            print("ARRET au lot " + str(numero) + " sur " + str(len(lots))
                  + " : HTTP " + str(code) + " : " + extrait)
            print("LOTS PASSES " + str(passes))
            return 1
        passes += 1
        print("LOT " + str(numero) + "/" + str(len(lots)) + " ok (" + str(len(lot)) + " lignes)")

    apres = compter_table(sender, base, cible["table"], cle)
    print("COMPTE APRES " + (str(apres) if apres is not None else "inconnu"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
