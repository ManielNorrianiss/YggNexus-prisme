alter table mcp_servers enable row level security;

drop policy if exists p_mcp_servers_pub on mcp_servers;

create policy p_mcp_servers_pub on mcp_servers for select to anon, authenticated using (true);

alter table bridges enable row level security;

drop policy if exists p_bridges_pub on bridges;

create policy p_bridges_pub on bridges for select to anon, authenticated using (true);
