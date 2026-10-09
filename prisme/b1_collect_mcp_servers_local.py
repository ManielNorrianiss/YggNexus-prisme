import json
from typing import Dict, List, Any
from datetime import datetime
import argparse

def get_sample_mcp_servers() -> List[Dict[str, Any]]:
    """
    Sample MCP servers for testing (from public awesome-mcp-servers and registry knowledge).
    In production, these would come from registry.modelcontextprotocol.io.
    """
    return [
        {
            "name": "filesystem",
            "owner": "Anthropic",
            "description": "Read, write, and list files and directories",
            "repository": {"url": "https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem"},
            "installation": {"package_type": "npm"},
            "transport": {"type": "stdio"},
            "capabilities": ["files", "reading", "writing"],
        },
        {
            "name": "memory",
            "owner": "Anthropic",
            "description": "In-memory data store for conversation state",
            "repository": {"url": "https://github.com/modelcontextprotocol/servers/tree/main/src/memory"},
            "installation": {"package_type": "npm"},
            "transport": {"type": "stdio"},
            "capabilities": ["data-storage", "state-management"],
        },
        {
            "name": "github",
            "owner": "ModelContextProtocol",
            "description": "Interact with GitHub repositories, issues, PRs",
            "repository": {"url": "https://github.com/modelcontextprotocol/servers/tree/main/src/github"},
            "installation": {"package_type": "npm"},
            "transport": {"type": "stdio"},
            "capabilities": ["github", "repositories", "issues"],
        },
        {
            "name": "slack",
            "owner": "ModelContextProtocol",
            "description": "Send and read Slack messages",
            "repository": {"url": "https://github.com/modelcontextprotocol/servers/tree/main/src/slack"},
            "installation": {"package_type": "npm"},
            "transport": {"type": "stdio"},
            "capabilities": ["messaging", "slack", "communication"],
        },
        {
            "name": "postgres",
            "owner": "ModelContextProtocol",
            "description": "Query PostgreSQL databases",
            "repository": {"url": "https://github.com/modelcontextprotocol/servers/tree/main/src/postgres"},
            "installation": {"package_type": "npm"},
            "transport": {"type": "stdio"},
            "capabilities": ["database", "sql", "postgres"],
        },
        {
            "name": "sqlite",
            "owner": "ModelContextProtocol",
            "description": "Query and manage SQLite databases",
            "repository": {"url": "https://github.com/modelcontextprotocol/servers/tree/main/src/sqlite"},
            "installation": {"package_type": "npm"},
            "transport": {"type": "stdio"},
            "capabilities": ["database", "sql", "sqlite"],
        },
        {
            "name": "brave-search",
            "owner": "Anthropic",
            "description": "Web search using Brave Search API",
            "repository": {"url": "https://github.com/modelcontextprotocol/servers/tree/main/src/brave-search"},
            "installation": {"package_type": "npm"},
            "transport": {"type": "stdio"},
            "capabilities": ["search", "web", "information-retrieval"],
        },
        {
            "name": "exa-search",
            "owner": "Exa",
            "description": "Neural web search via Exa API",
            "repository": {"url": "https://github.com/exa-labs/exa-py-mcp-server"},
            "installation": {"package_type": "pip"},
            "transport": {"type": "stdio"},
            "capabilities": ["search", "semantic-search", "research"],
        },
    ]

def canonicalize_name(name: str) -> str:
    """Convert server name to canonical format: io.github.owner/servername"""
    name_lower = name.lower().strip()
    if name_lower.startswith("io.github."):
        return name_lower
    name_lower = name_lower.replace(" ", "-").replace("_", "-")
    return f"io.github.mcp/{name_lower}"

def normalize_servers(raw_servers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize raw server data to YggNexus canonical format"""
    normalized = []
    for srv in raw_servers:
        canonical_slug = canonicalize_name(srv.get("name", "unknown"))
        normalized.append({
            "slug": canonical_slug,
            "name": srv.get("name", ""),
            "description": srv.get("description", ""),
            "author": srv.get("owner", ""),
            "repo_url": srv.get("repository", {}).get("url", ""),
            "registry_source": "sample_local",
            "package_type": srv.get("installation", {}).get("package_type", ""),
            "transport": srv.get("transport", {}).get("type", ""),
            "capabilities": srv.get("capabilities", []),
            "hosting": "unknown",
            "stars": 0,
            "weekly_downloads": 0,
            "license": "",
            "quality_score": None,
        })
    return normalized

def deduplicate_servers(servers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Deduplicate servers by repo_url and canonical name"""
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
    parser = argparse.ArgumentParser(description="Collect MCP servers from local sample data")
    parser.add_argument("--output", type=str, default="/sessions/adoring-eager-keller/mnt/Emperor/YggNexus/prisme/mcp_servers_sample.json", help="Output file path")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Dry run mode (no file write)")
    parser.add_argument("--write", action="store_true", help="Actually write output file")
    
    args = parser.parse_args()
    
    if args.write:
        args.dry_run = False
    
    print("=" * 60)
    print("MCP SERVER COLLECTOR - LOCAL SAMPLE" + (" - DRY RUN" if args.dry_run else " - WRITE MODE"))
    print("=" * 60)
    print()
    
    raw = get_sample_mcp_servers()
    print(f"Loaded {len(raw)} sample servers from local data")
    print()
    
    normalized = normalize_servers(raw)
    print(f"Normalized to {len(normalized)} servers")
    print()
    
    dedup_result = deduplicate_servers(normalized)
    
    print("Deduplication Report:")
    print(f"  Total before: {dedup_result['total_before']}")
    print(f"  Duplicates removed: {dedup_result['duplicates_removed']}")
    print(f"  Final unique: {dedup_result['total_after']}")
    print()
    
    final_output = {
        "timestamp": datetime.now().isoformat(),
        "source": "local_sample_data",
        "note": "This is sample data for testing. In production, use official registry at registry.modelcontextprotocol.io",
        "total_servers": dedup_result["total_after"],
        "servers": dedup_result["servers"],
    }
    
    output_json = json.dumps(final_output, indent=2, ensure_ascii=True)
    
    if args.dry_run:
        print(f"DRY RUN: Would write {len(output_json)} bytes to {args.output}")
        print()
        print("Sample output (first 800 chars):")
        print(output_json[:800])
        print("...")
    else:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"SUCCESS: Written {len(output_json)} bytes to {args.output}")
    
    print()
    print("=" * 60)

if __name__ == "__main__":
    main()
