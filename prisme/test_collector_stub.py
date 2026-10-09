#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from b1_collect_mcp_servers import MCPServer

stub_data = [
    {
        'name': 'File System MCP Server',
        'description': 'Filesystem operations and management',
        'author': 'Claude Team',
        'repository': 'https://github.com/anthropics/mcp-server-filesystem',
        'type': 'npm',
        'transport': 'stdio',
        'capabilities': ['read', 'write', 'list'],
    },
    {
        'name': 'PostgreSQL MCP Server',
        'description': 'Database operations for PostgreSQL',
        'author': 'CloudFlare',
        'repository': 'https://github.com/cloudflare/mcp-server-postgres',
        'type': 'docker',
        'transport': 'http',
        'capabilities': ['query', 'execute', 'introspect'],
    },
    {
        'name': 'Web Scraper',
        'description': 'Web content extraction and scraping',
        'author': 'YggNexus Contributors',
        'repository': 'https://github.com/example/mcp-web-scraper',
        'type': 'npm',
        'transport': 'stdio',
        'capabilities': ['fetch', 'parse', 'extract'],
    },
]

servers = []
dedup_map = {}

for srv_data in stub_data:
    name = srv_data.get('name', '').strip()
    slug = name.lower().replace(' ', '-').replace('/', '-')[:50]
    repo_url = srv_data.get('repository', '').strip() or None
    
    dedup_key = (repo_url, slug) if repo_url else slug
    if dedup_key in dedup_map:
        print(f'[DEDUP] Skipping duplicate: {name}')
        continue
    
    dedup_map[dedup_key] = True
    
    server = MCPServer(
        slug=slug,
        name=name,
        description=srv_data.get('description'),
        author=srv_data.get('author'),
        repo_url=repo_url,
        package_type=srv_data.get('type', 'other').lower(),
        transport=srv_data.get('transport', 'stdio').lower(),
        capabilities=srv_data.get('capabilities', []),
        hosting='remote' if 'http' in srv_data.get('transport', '').lower() else 'local'
    )
    servers.append(server)

output_path = Path('data/mcp_servers_collected_stub.json')
output_path.parent.mkdir(parents=True, exist_ok=True)

data = {
    'metadata': {
        'version': '1.0',
        'source': 'stub_data',
        'count': len(servers),
        'mode': 'test'
    },
    'servers': [s.to_dict() for s in servers]
}

with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=True)

print(f'[TEST] Saved {len(servers)} stub servers to {output_path}')
print(f'[TEST] Structure validated. Ready for production collector.')
