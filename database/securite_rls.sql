alter table categories enable row level security;
alter table tools enable row level security;
alter table tags enable row level security;
alter table automations enable row level security;
alter table automation_steps enable row level security;
alter table tool_categories enable row level security;
alter table tool_tags enable row level security;
alter table automation_tools enable row level security;
alter table alternatives enable row level security;
alter table changelog enable row level security;
alter table embeddings enable row level security;

drop policy if exists public_read_tools on tools;
create policy public_read_tools on tools for select to anon, authenticated using (status = 'published');

drop policy if exists public_read_categories on categories;
create policy public_read_categories on categories for select to anon, authenticated using (status = 'published');

drop policy if exists public_read_automations on automations;
create policy public_read_automations on automations for select to anon, authenticated using (status = 'published');

drop policy if exists public_read_tags on tags;
create policy public_read_tags on tags for select to anon, authenticated using (true);

drop policy if exists public_read_tool_categories on tool_categories;
create policy public_read_tool_categories on tool_categories for select to anon, authenticated using (true);

drop policy if exists public_read_tool_tags on tool_tags;
create policy public_read_tool_tags on tool_tags for select to anon, authenticated using (true);

drop policy if exists public_read_automation_tools on automation_tools;
create policy public_read_automation_tools on automation_tools for select to anon, authenticated using (true);

drop policy if exists public_read_automation_steps on automation_steps;
create policy public_read_automation_steps on automation_steps for select to anon, authenticated using (true);

drop policy if exists public_read_alternatives on alternatives;
create policy public_read_alternatives on alternatives for select to anon, authenticated using (true);
