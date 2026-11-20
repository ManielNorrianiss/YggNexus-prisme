# -*- coding: utf-8 -*-
"""
Essais de mise a l'echelle de b5_bridges_mcp.py : la version par index inverse
doit donner le meme resultat qu'un calcul naif par paires quand le plafond
est large, respecter le plafond, etre deterministe et tenir 20 000 serveurs.
"""
import itertools
import random
import time

import b5_bridges_mcp as b5

SAAS_NOMS = ["stripe", "notion", "slack", "github"]


def fabriquer(n, graine, sujets=40, mots_par_sujet=9, part_saas=0.3):
    rng = random.Random(graine)
    vocab = [["m%d_%d" % (s, k) for k in range(mots_par_sujet)] for s in range(sujets)]
    communs = ["data", "files", "search", "manage", "tool", "simple"]
    recs = []
    for i in range(n):
        s = rng.randrange(sujets)
        mots = rng.sample(vocab[s], rng.randint(4, 7))
        if rng.random() < 0.5:
            mots.append(rng.choice(communs))
        if rng.random() < 0.3:
            mots.append("zz%d" % rng.randrange(500))
        rng.shuffle(mots)
        nom = "ns%d/srv%d" % (i % 17, i)
        if rng.random() < part_saas:
            nom = rng.choice(SAAS_NOMS) + "-" + nom
        recs.append({
            "slug": "srv-%05d" % i, "name": nom, "description": " ".join(mots),
            "website_url": None,
            "package_type": rng.choice([None, "npm", "pypi"]),
            "package_types": [],
        })
    return recs


def naif(records, wraps, seuil):
    """Calcul de reference par produit cartesien (l'ancien algorithme)."""
    out = {}
    toks = {r["slug"]: b5.description_tokens(r["description"]) for r in records}
    for ra, rb in itertools.combinations(records, 2):
        a, b = sorted((ra["slug"], rb["slug"]))
        wa, wb = wraps.get(a), wraps.get(b)
        if wa and wb and wa[0] == wb[0]:
            out[(a, b)] = ("same-saas", 1.0)
            continue
        sc = b5.jaccard(toks[a], toks[b])
        if sc >= seuil:
            out[(a, b)] = ("desc-jaccard", sc)
    return out


def resultat(records, seuil, plafond):
    wraps, _ = b5.build_wraps(records)
    ponts = b5.build_alternative_of(records, wraps, seuil, plafond)
    out = {}
    for p in ponts:
        genre = p["evidence"].split(":")[0]
        out[(p["source_id"], p["target_id"])] = (genre, p["weight"])
    return out, wraps, ponts


def test_meme_resultat_que_le_calcul_naif_avec_plafond_large():
    recs = fabriquer(200, 1)
    nouveau, wraps, _ = resultat(recs, b5.DEFAULT_THRESHOLD, 10 ** 6)
    ref = naif(recs, wraps, b5.DEFAULT_THRESHOLD)
    assert any(g == "same-saas" for g, _ in ref.values())
    assert any(g == "desc-jaccard" for g, _ in ref.values())
    assert set(nouveau) == set(ref)
    for cle, (genre, poids) in ref.items():
        assert nouveau[cle][0] == genre
        assert abs(nouveau[cle][1] - poids) < 1e-4


def test_plafond_respecte_et_meilleurs_partenaires_gardes():
    recs = fabriquer(200, 2)
    plafond = 3
    nouveau, wraps, ponts = resultat(recs, b5.DEFAULT_THRESHOLD, plafond)
    ref = naif(recs, wraps, b5.DEFAULT_THRESHOLD)
    assert set(nouveau) <= set(ref)
    assert len(nouveau) < len(ref)
    assert len(ponts) <= 2 * plafond * len(recs)

    toks = {r["slug"]: b5.description_tokens(r["description"]) for r in recs}
    for r in recs:
        s = r["slug"]
        for genre in ("same-saas", "desc-jaccard"):
            partenaires = []
            for (a, b), (g, _) in ref.items():
                if g != genre or s not in (a, b):
                    continue
                autre = b if a == s else a
                partenaires.append((-b5.jaccard(toks[s], toks[autre]), autre, (a, b)))
            partenaires.sort()
            for _, _, cle in partenaires[:plafond]:
                assert cle in nouveau, (s, genre, cle)


def test_deterministe_quel_que_soit_l_ordre_d_entree():
    recs = fabriquer(300, 3)
    melange = list(recs)
    random.Random(99).shuffle(melange)
    a, _ = b5.build_bridges(recs, b5.DEFAULT_THRESHOLD, 4)
    b, _ = b5.build_bridges(melange, b5.DEFAULT_THRESHOLD, 4)
    cle = lambda p: (p["relation"], p["source_id"], p["target_id"])
    assert sorted(a, key=cle) == sorted(b, key=cle)
    c, _ = b5.build_bridges(recs, b5.DEFAULT_THRESHOLD, 4)
    assert a == c


def test_vingt_mille_enregistrements_en_moins_de_60_secondes():
    recs = fabriquer(20000, 4, sujets=800, part_saas=0.15)
    debut = time.time()
    ponts, wraps = b5.build_bridges(recs, b5.DEFAULT_THRESHOLD, 5)
    duree = time.time() - debut
    assert duree < 60, duree
    relations = {p["relation"] for p in ponts}
    assert {"wraps", "alternative_of"} <= relations
    alt = [p for p in ponts if p["relation"] == "alternative_of"]
    assert len(alt) <= 2 * 5 * len(recs)
