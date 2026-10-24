"""
b1_mcp.py - Collecteur de serveurs MCP depuis le registre officiel.

Verticale MCP de YggNexus (le pont). Source primaire: registre officiel
registry.modelcontextprotocol.io (API publique, sans auth, pagination par
cursor). Normalise chaque serveur vers le modele canonique YggNexus
(table mcp_servers) et deduplique par repo_url + nom canonique.

Aucune ecriture Supabase ici: la collecte ecrit un fichier de staging JSON.
La propagation Supabase est une etape separee (reservee a Josue).

Usage:
  python b1_mcp.py                 # dry-run, ecrit data/mcp_servers_staging.json
  python b1_mcp.py --limit 100 --max-pages 0
  python b1_mcp.py --enrich-github # enrichissement secondaire (stars/licence)
  python b1_mcp.py --self-test     # test de normalisation sur fixture locale
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_BASES = ["https://registry.modelcontextprotocol.io"]
ENDPOINT_PATHS = ["/v0/servers", "/v0.1/servers"]
REGISTRY_SOURCE = "modelcontextprotocol.io"
USER_AGENT = "YggNexus-Prisme/1.0 (+https://www.yggnexus.com)"

PKG_TYPES = ("npm", "pypi", "oci", "docker", "nuget", "mcpb", "unknown")
TRANSPORTS = ("stdio", "http", "sse", "streamable-http", "unknown")
HOSTING = ("local", "remote", "hybrid", "unknown")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
DEFAULT_OUT = os.path.join(DATA_DIR, "mcp_servers_staging.json")


def slugify(value):
    value = (value or "").lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "unknown"


RETRY_WAITS = [5, 15, 30, 60, 120, 180]  # secondes entre essais (environ 7 min au total)


def http_get_json_once(url, token=None, timeout=60):
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_get_json(url, token=None, timeout=60, retries=True):
    """GET JSON avec reprises sur erreur reseau ou 5xx/429.
    Les 4xx (sauf 429) sont definitives : aucune reprise."""
    waits = RETRY_WAITS if retries else []
    for attempt in range(len(waits) + 1):
        try:
            return http_get_json_once(url, token=token, timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code != 429 and e.code < 500:
                raise
            err = "HTTP " + str(e.code)
        except Exception as e:
            err = type(e).__name__ + ": " + str(e)
        if attempt >= len(waits):
            raise RuntimeError("echec apres " + str(attempt + 1) + " essais (" + err + ")")
        w = waits[attempt]
        sys.stderr.write("  reseau : " + err[:120] + " | nouvel essai dans " + str(w) + " s\n")
        time.sleep(w)


def resolve_endpoint(base, limit):
    last_err = None
    for path in ENDPOINT_PATHS:
        url = base + path + "?limit=" + str(limit)
        try:
            data = http_get_json(url)
            if isinstance(data, dict) and "servers" in data:
                return base + path
        except urllib.error.HTTPError as e:
            last_err = "HTTP " + str(e.code) + " on " + path
            continue
        except Exception as e:
            last_err = type(e).__name__ + " on " + path + ": " + str(e)
            continue
    raise RuntimeError("aucun endpoint /servers exploitable (" + str(last_err) + ")")


CHECKPOINT_RAW = os.path.join(DATA_DIR, "mcp_collecte_en_cours.jsonl")
CHECKPOINT_STATE = os.path.join(DATA_DIR, "mcp_collecte_en_cours.state.json")


def _load_checkpoint():
    """Reprend une collecte interrompue : (endpoint, cursor, page, raw) ou None."""
    if not (os.path.exists(CHECKPOINT_RAW) and os.path.exists(CHECKPOINT_STATE)):
        return None
    try:
        with open(CHECKPOINT_STATE, "r", encoding="utf-8") as f:
            st = json.load(f)
        raw = []
        with open(CHECKPOINT_RAW, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    raw.append(json.loads(line))
        return st.get("endpoint"), st.get("cursor"), int(st.get("page") or 0), raw
    except Exception as e:
        sys.stderr.write("checkpoint illisible, collecte reprise du debut (" + str(e) + ")\n")
        return None


def _save_state(endpoint, cursor, page):
    tmp = CHECKPOINT_STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"endpoint": endpoint, "cursor": cursor, "page": page}, f)
    os.replace(tmp, CHECKPOINT_STATE)


def _clear_checkpoint():
    for path in (CHECKPOINT_RAW, CHECKPOINT_STATE):
        try:
            os.remove(path)
        except OSError:
            pass


def fetch_all(base, limit, max_pages):
    """Collecte toutes les pages. Chaque page est sauvee sur disque au fur et a
    mesure : si la collecte plante, le prochain lancement reprend la ou elle
    s'est arretee au lieu de tout recommencer."""
    os.makedirs(DATA_DIR, exist_ok=True)
    cp = _load_checkpoint()
    if cp and cp[1]:
        endpoint, cursor, page, raw = cp
        sys.stderr.write("REPRISE de la collecte interrompue : page " + str(page) +
                         ", " + str(len(raw)) + " entrees deja sur disque\n")
    else:
        _clear_checkpoint()
        endpoint = resolve_endpoint(base, limit)
        cursor, page, raw = None, 0, []
    with open(CHECKPOINT_RAW, "a", encoding="utf-8") as out:
        while True:
            params = {"limit": str(limit)}
            if cursor:
                params["cursor"] = cursor
            url = endpoint + "?" + urllib.parse.urlencode(params)
            data = http_get_json(url)
            servers = data.get("servers") or []
            for srv in servers:
                out.write(json.dumps(srv, ensure_ascii=False) + "\n")
            out.flush()
            raw.extend(servers)
            page += 1
            meta = data.get("metadata") or {}
            cursor = meta.get("nextCursor") or meta.get("next_cursor")
            _save_state(endpoint, cursor, page)
            sys.stderr.write("page " + str(page) + ": +" + str(len(servers)) +
                             " (cumul " + str(len(raw)) + ")\n")
            if not cursor:
                break
            if max_pages and page >= max_pages:
                break
            time.sleep(0.2)
    return endpoint, raw


def pick(d, *keys):
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in (None, ""):
            return d.get(k)
    return None


def map_choice(value, allowed, fallback="unknown"):
    if value is None:
        return None
    v = str(value).lower()
    if v in allowed:
        return v
    if v in ("streamablehttp", "streamable_http"):
        return "streamable-http"
    if v in ("http", "sse", "stdio"):
        return v
    return fallback


def author_from_name(name):
    if not name:
        return None
    head = name.split("/")[0]
    parts = head.split(".")
    if len(parts) >= 2 and parts[0] in ("io", "com", "org", "net", "dev", "app"):
        return parts[-1]
    return head or None


def normalize(entry):
    server = entry.get("server") if isinstance(entry, dict) else None
    if not isinstance(server, dict):
        server = entry if isinstance(entry, dict) else {}
    meta = entry.get("_meta") if isinstance(entry, dict) else {}
    official = {}
    if isinstance(meta, dict):
        official = meta.get("io.modelcontextprotocol.registry/official") or {}

    name = pick(server, "name")
    description = pick(server, "description")
    version = pick(server, "version")
    website_url = pick(server, "websiteUrl", "website_url")

    repo = server.get("repository") if isinstance(server.get("repository"), dict) else {}
    repo_url = pick(repo, "url")

    packages = server.get("packages") or []
    remotes = server.get("remotes") or []

    package_types = []
    package_ids = []
    package_names = []
    transports = []
    for p in packages:
        if not isinstance(p, dict):
            continue
        pt = map_choice(pick(p, "registryType", "registry_name", "registry_type"), PKG_TYPES)
        if pt and pt not in package_types:
            package_types.append(pt)
        pid = pick(p, "identifier", "name")
        if pid and str(pid) not in package_names:
            package_names.append(str(pid))
        if pt and pid:
            token = pt + ":" + str(pid)
            if token not in package_ids:
                package_ids.append(token)
        tr_obj = p.get("transport") if isinstance(p.get("transport"), dict) else {}
        tr = map_choice(pick(tr_obj, "type") or pick(p, "transport"), TRANSPORTS)
        if tr and tr not in transports:
            transports.append(tr)
    remote_urls = []
    for r in remotes:
        if not isinstance(r, dict):
            continue
        tr = map_choice(pick(r, "type"), TRANSPORTS)
        if tr and tr not in transports:
            transports.append(tr)
        ru = pick(r, "url")
        if ru and ru not in remote_urls:
            remote_urls.append(ru)

    if remotes and packages:
        hosting = "hybrid"
    elif remotes:
        hosting = "remote"
    elif packages:
        hosting = "local"
    else:
        hosting = "unknown"

    capabilities = []
    for t in transports:
        if t not in capabilities:
            capabilities.append(t)

    return {
        "slug": slugify(name),
        "name": name,
        "description": description,
        "author": author_from_name(name),
        "repo_url": repo_url,
        "registry_source": REGISTRY_SOURCE,
        "package_type": (package_types[0] if package_types else None),
        "package_types": package_types,
        "package_ids": package_ids,
        "package_identifier": (package_names[0] if package_names else None),
        "remote_urls": remote_urls,
        "transport": (transports[0] if transports else None),
        "transports": transports,
        "capabilities": capabilities,
        "hosting": hosting,
        "version": version,
        "website_url": website_url,
        "license": None,
        "stars": None,
        "weekly_downloads": None,
        "quality_score": None,
        "status": (official.get("status") if isinstance(official, dict) else None) or "active",
        "is_latest": bool(official.get("isLatest", True)) if isinstance(official, dict) else True,
        "published_at": (official.get("publishedAt") if isinstance(official, dict) else None),
    }


def dedup(records):
    seen_repo = set()
    seen_name = set()
    kept = []
    dropped = 0
    records = sorted(records, key=lambda r: (0 if r.get("is_latest") else 1))
    for r in records:
        name = (r.get("name") or "").strip().lower()
        repo = (r.get("repo_url") or "").strip().lower().rstrip("/")
        if name and name in seen_name:
            dropped += 1
            continue
        if repo and repo in seen_repo:
            dropped += 1
            continue
        if name:
            seen_name.add(name)
        if repo:
            seen_repo.add(repo)
        kept.append(r)
    return kept, dropped


def parse_github_owner_repo(url):
    if not url or "github.com" not in url:
        return None
    m = re.search(r"github\.com[/:]([^/]+)/([^/#?]+)", url)
    if not m:
        return None
    owner = m.group(1)
    repo = m.group(2)
    if repo.endswith(".git"):
        repo = repo[:-4]
    return owner, repo


def enrich_github(records, token, limit=None):
    enriched = 0
    count = 0
    for r in records:
        gh = parse_github_owner_repo(r.get("repo_url"))
        if not gh:
            continue
        if limit and count >= limit:
            break
        owner, repo = gh
        api = "https://api.github.com/repos/" + owner + "/" + repo
        try:
            data = http_get_json(api, token=token, retries=False)
            r["stars"] = data.get("stargazers_count")
            lic = data.get("license") or {}
            r["license"] = lic.get("spdx_id") or lic.get("key")
            enriched += 1
        except Exception as e:
            msg = str(e)
            if "403" in msg and "rate limit" in msg.lower():
                sys.stderr.write("github: plafond de requetes atteint apres " + str(enriched)
                                 + " enrichis, arret de l'enrichissement (collecte conservee)\n")
                break
            sys.stderr.write("github skip " + owner + "/" + repo + ": " + msg + "\n")
        count += 1
        time.sleep(0.7)
    return enriched


SAMPLE_PAGE = {
    "servers": [
        {
            "server": {
                "name": "io.github.acme/filesystem",
                "description": "Filesystem operations server",
                "version": "1.0.2",
                "repository": {"url": "https://github.com/acme/filesystem", "source": "github"},
                "packages": [{"registryType": "npm", "identifier": "@acme/fs",
                              "transport": {"type": "stdio"}}],
            },
            "_meta": {"io.modelcontextprotocol.registry/official":
                      {"status": "active", "publishedAt": "2026-01-01T10:30:00Z",
                       "isLatest": True}},
        },
        {
            "server": {
                "name": "io.github.acme/filesystem",
                "description": "older duplicate",
                "version": "0.9.0",
                "repository": {"url": "https://github.com/acme/filesystem", "source": "github"},
                "packages": [{"registryType": "npm", "identifier": "@acme/fs"}],
            },
            "_meta": {"io.modelcontextprotocol.registry/official":
                      {"status": "active", "isLatest": False}},
        },
        {
            "server": {
                "name": "com.example/weather",
                "description": "Remote weather server",
                "version": "2.1.0",
                "repository": {"url": "https://github.com/example/weather.git", "source": "github"},
                "remotes": [{"type": "sse", "url": "https://example.com/sse"}],
            },
            "_meta": {"io.modelcontextprotocol.registry/official":
                      {"status": "active", "isLatest": True}},
        },
    ],
    "metadata": {"count": 3, "nextCursor": None},
}


def self_test():
    norm = [normalize(e) for e in SAMPLE_PAGE["servers"]]
    kept, dropped = dedup(norm)
    assert len(norm) == 3, "expected 3 normalized"
    assert dropped == 1, "expected 1 duplicate dropped, got " + str(dropped)
    assert len(kept) == 2, "expected 2 unique"
    fs = [r for r in kept if r["name"] == "io.github.acme/filesystem"][0]
    assert fs["slug"] == "io-github-acme-filesystem", fs["slug"]
    assert fs["author"] == "acme", fs["author"]
    assert fs["package_type"] == "npm", fs["package_type"]
    assert fs["transport"] == "stdio", fs["transport"]
    assert fs["hosting"] == "local", fs["hosting"]
    assert fs["version"] == "1.0.2", "latest must win dedup"
    we = [r for r in kept if r["name"] == "com.example/weather"][0]
    assert we["hosting"] == "remote", we["hosting"]
    assert we["transport"] == "sse", we["transport"]
    assert we["author"] == "example", we["author"]
    print("SELF-TEST OK: 3 normalized, 1 dedup drop, 2 unique, mappings valid")
    return 0


def load_fixture(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        raw = data.get("servers") or data.get("records") or []
    else:
        raw = data
    return "file://" + os.path.abspath(path), list(raw)


def main():
    ap = argparse.ArgumentParser(description="Collecteur MCP (registre officiel) - YggNexus")
    ap.add_argument("--base", default=DEFAULT_BASES[0])
    ap.add_argument("--limit", type=int, default=100, help="taille de page (max 100)")
    ap.add_argument("--max-pages", type=int, default=0, help="0 = toutes les pages")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--enrich-github", action="store_true")
    ap.add_argument("--github-limit", type=int, default=0, help="0 = pas de plafond")
    ap.add_argument("--dry-run", action="store_true", default=True,
                    help="aucune ecriture Supabase (toujours actif ici)")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--from-file", default=None,
                    help="fixture JSON locale au lieu du reseau (dry-run reproductible)")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    limit = max(1, min(args.limit, 100))
    if args.from_file:
        try:
            endpoint, raw = load_fixture(args.from_file)
        except Exception as e:
            sys.stderr.write("ERREUR fixture: " + type(e).__name__ + ": " + str(e) + "\n")
            return 2
    else:
        try:
            endpoint, raw = fetch_all(args.base, limit, args.max_pages)
        except Exception as e:
            sys.stderr.write("ERREUR collecte: " + type(e).__name__ + ": " + str(e) + "\n")
            return 2

    fetched = len(raw)
    records = [normalize(e) for e in raw]
    kept, dropped = dedup(records)

    enriched = 0
    if args.enrich_github:
        token = os.environ.get("GITHUB_TOKEN")
        glimit = args.github_limit or None
        enriched = enrich_github(kept, token, glimit)

    os.makedirs(DATA_DIR, exist_ok=True)
    payload = {
        "source": REGISTRY_SOURCE,
        "endpoint": endpoint,
        "fetched": fetched,
        "unique": len(kept),
        "duplicates_dropped": dropped,
        "github_enriched": enriched,
        "records": kept,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    if not args.from_file:
        _clear_checkpoint()

    print("FETCHED " + str(fetched) + " servers from " + endpoint)
    print("UNIQUE " + str(len(kept)) + " after dedup (dropped " + str(dropped) + ")")
    if args.enrich_github:
        print("GITHUB enriched " + str(enriched))
    print("WROTE " + args.out)
    print("DRY-RUN: aucune ecriture Supabase. Propagation reservee a Josue.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
