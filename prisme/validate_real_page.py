import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import b1_mcp

FIXTURE = os.path.join(HERE, "data", "registry_real_page_20260720.json")

def main():
    with open(FIXTURE, "r") as f:
        page = json.load(f)
    entries = page.get("servers") or []
    norm = [b1_mcp.normalize(e) for e in entries]
    kept, dropped = b1_mcp.dedup(norm)
    print("entrees brutes:", len(entries))
    print("normalisees:", len(norm))
    print("uniques apres dedup:", len(kept))
    print("doublons versions retires:", dropped)
    problems = []
    for r in kept:
        if not r.get("slug") or r.get("slug") == "unknown":
            problems.append("slug manquant: " + str(r.get("name")))
        if r.get("hosting") not in ("local", "remote", "hybrid", "unknown"):
            problems.append("hosting invalide: " + str(r.get("hosting")))
        if r.get("transport") and r.get("transport") not in b1_mcp.TRANSPORTS:
            problems.append("transport invalide: " + str(r.get("transport")))
        if r.get("package_type") and r.get("package_type") not in b1_mcp.PKG_TYPES:
            problems.append("package_type invalide: " + str(r.get("package_type")))
    by_name = {}
    for r in kept:
        by_name[r["name"]] = r
    checks = [
        ("ac.inference.sh/mcp version 1.0.1 (isLatest gagne)",
         by_name.get("ac.inference.sh/mcp", {}).get("version") == "1.0.1"),
        ("ac.tandem/docs-mcp version 0.3.2",
         by_name.get("ac.tandem/docs-mcp", {}).get("version") == "0.3.2"),
        ("ai.adeu/adeu unique malgre pypi+npm (meme repo)",
         "ai.adeu/adeu" in by_name),
        ("spotdb package_type oci",
         by_name.get("ai.aliengiraffe/spotdb", {}).get("package_type") == "oci"),
        ("spotdb hosting local",
         by_name.get("ai.aliengiraffe/spotdb", {}).get("hosting") == "local"),
        ("adadvisor hosting remote",
         by_name.get("ai.adadvisor/mcp-server", {}).get("hosting") == "remote"),
        ("agentra transport sse",
         by_name.get("ai.agentrapay/agentra", {}).get("transport") == "sse"),
        ("graffeo status deprecated conserve",
         by_name.get("ai.agenticshelf/graffeo", {}).get("status") == "deprecated"),
        ("streamable-http mappe correctement",
         by_name.get("ac.inference.sh/mcp", {}).get("transport") == "streamable-http"),
        ("repository vide tolere (agentra repo_url None)",
         by_name.get("ai.agentrapay/agentra", {}).get("repo_url") is None),
    ]
    fails = [label for label, ok in checks if not ok]
    for label, ok in checks:
        print(("PASS " if ok else "FAIL ") + label)
    if problems:
        print("PROBLEMES:", problems)
    out = os.path.join(HERE, "data", "mcp_servers_staging_realpage.json")
    payload = {"metadata": {"source": "registry.modelcontextprotocol.io",
                            "mode": "dry-run fixture reelle 2026-07-20",
                            "count": len(kept)},
               "servers": kept}
    with open(out, "w") as f:
        json.dump(payload, f, ensure_ascii=True, indent=2)
    print("staging ecrit:", out)
    if fails or problems:
        return 1
    print("VALIDATION REELLE OK")
    return 0

if __name__ == "__main__":
    sys.exit(main())
