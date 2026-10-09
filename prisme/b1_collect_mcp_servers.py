import json
import requests
import hashlib
from typing import Optional, Dict, List, Any
from datetime import datetime
import argparse

REGISTRY_URL = "https://registry.modelcontextprotocol.io/v0/servers"
LIMIT = 100

def canonicalize_name(name: str) -> str:
    """Convert server name to canonical format: io.github.owner/servername"""
    name_lower = name.lower().strip()
    if name_lower.startswith("io.github."):
        return name_lower
    name_lower = name_lower.replace(" ", "-").replace("_", "-")
    return f"io.github.mcp/{name_lower}"

def collect_mcp_servers(limit: Optional[int] = None, dry_run: bool = True) -> Dict[str, Any]:
    """
    Fetch all MCP servers from official registry with pagination.
    Returns dict with servers list and metadata.
    """
    servers = []
    cursor = None
    page_count = 0
    total_fetched = 0
    
    print(f"Starting MCP server collection from {REGISTRY_URL}")
    print(f"Limit per page: {LIMIT}, Total limit: {limit or 'unlimited'}")
    print()
    
    while True:
        params = {"limit": LIMIT}
        if cursor:
            params["cursor"] = cursor
        
        try:
            response = requests.get(REGISTRY_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            print(f"ERROR fetching page {page_count + 1}: {e}")
            break
        
        page_servers = data.get("servers", [])
        if not page_servers:
            print(f"No more servers found at page {page_count + 1}")
            break
        
        page_count += 1
        print(f"Page {page_count}: fetched {len(page_servers)} servers")
        
        for srv in page_servers:
            canonical_slug = canonicalize_name(srv.get("name", "unknown"))
            
            normalized = {
                "slug": canonical_slug,
                "name": srv.get("name", ""),
                "description": srv.get("description", ""),
                "author": srv.get("owner", ""),
                "repo_url": srv.get("repository", {}).get("url", ""),
                "registry_source": "official_mcp_registry",
                "package_type": srv.get("installation", {}).get("package_type", ""),
                "transport": srv.get("transport", {}).get("type", ""),
                "capabilities": srv.get("capabilities", []),
                "hosting": "unknown",
                "stars": 0,
                "weekly_downloads": 0,
                "license": "",
                "quality_score": None,
            }
            
            servers.append(normalized)
            total_fetched += 1
            
            if limit and total_fetched >= limit:
                print(f"Reached limit of {limit} servers")
                break
        
        if limit and total_fetched >= limit:
            break
        
        cursor = data.get("cursor")
        if not cursor:
            print(f"No cursor found, stopping pagination")
            break
    
    print()
    print(f"Total servers collected: {total_fetched} across {page_count} pages")
    print()
    
    result = {
        "timestamp": datetime.now().isoformat(),
        "registry_url": REGISTRY_URL,
        "total_servers": total_fetched,
        "pages_fetched": page_count,
        "servers": servers,
    }
    
    return result

def deduplicate_servers(servers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Deduplicate servers by repo_url and canonical name.
    Returns dict with deduped list and collision report.
    """
    seen = {}
    deduped = []
    collisions = []
    
    for srv in servers:
        key = (srv.get("repo_url", ""), srv.get("slug", ""))
        
        if key in seen:
            collisions.append({
                "slug": srv.get("slug"),
                "repo_url": srv.get("repo_url"),
                "collision_with": seen[key]["slug"],
            })
        else:
            seen[key] = srv
            deduped.append(srv)
    
    return {
        "total_before": len(servers),
        "total_after": len(deduped),
        "duplicates_removed": len(collisions),
        "servers": deduped,
        "collisions": collisions,
    }

def main():
    parser = argparse.ArgumentParser(description="Collect MCP servers from official registry")
    parser.add_argument("--limit", type=int, default=None, help="Limit total servers to fetch")
    parser.add_argument("--output", type=str, default="/sessions/adoring-eager-keller/mnt/Emperor/YggNexus/prisme/mcp_servers_raw.json", help="Output file path")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Dry run mode (no file write)")
    parser.add_argument("--write", action="store_true", help="Actually write output file (disable dry-run)")
    
    args = parser.parse_args()
    
    if args.write:
        args.dry_run = False
    
    print("=" * 60)
    print("MCP SERVER COLLECTOR - DRY RUN MODE" if args.dry_run else "MCP SERVER COLLECTOR - WRITE MODE")
    print("=" * 60)
    print()
    
    result = collect_mcp_servers(limit=args.limit, dry_run=args.dry_run)
    
    dedup_result = deduplicate_servers(result["servers"])
    
    print("Deduplication Report:")
    print(f"  Total before dedup: {dedup_result['total_before']}")
    print(f"  Duplicates removed: {dedup_result['duplicates_removed']}")
    print(f"  Final unique servers: {dedup_result['total_after']}")
    print()
    
    if dedup_result["collisions"]:
        print(f"Collisions found: {len(dedup_result['collisions'])} (showing first 5)")
        for col in dedup_result["collisions"][:5]:
            print(f"  - {col['slug']} from {col['repo_url'][:50]}... collides with {col['collision_with']}")
        print()
    
    final_output = {
        "collection": result,
        "deduplication": dedup_result,
    }
    
    output_json = json.dumps(final_output, indent=2, ensure_ascii=True)
    
    if args.dry_run:
        print(f"DRY RUN: Would write {len(output_json)} bytes to {args.output}")
        print(f"Sample (first 500 chars):")
        print(output_json[:500])
        print("...")
    else:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"SUCCESS: Written {len(output_json)} bytes to {args.output}")
    
    print()
    print("=" * 60)

if __name__ == "__main__":
    main()
