// YggNexus - re-embed incremental des outils publies en gte-small (384d).
// Lot par defaut TRES petit (?batch=4) pour tenir sous la limite de
// ressources d'une Edge Function (le modele se recharge a chaque appel).
// Requetes allegees : on ne charge les longues descriptions que pour le lot.
// Relancer jusqu'a remaining=0. Protection : Verify JWT de Supabase.
import { createClient } from "jsr:@supabase/supabase-js@2";

const model = new Supabase.ai.Session("gte-small");

Deno.serve(async (req) => {
  if (req.method !== "POST") {
    return new Response("method not allowed", { status: 405 });
  }
  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
  );
  const u = new URL(req.url);
  const batch = Math.min(Math.max(Number(u.searchParams.get("batch") ?? "4"), 1), 10);

  const json = (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    });

  // 1) ids legers seulement, pour calculer le reste a faire.
  const { data: done } = await supabase.from("search_embeddings").select("tool_id");
  const doneIds = new Set((done ?? []).map((d) => d.tool_id));
  const { data: ids, error: idErr } = await supabase
    .from("tools").select("id").eq("status", "published");
  if (idErr) return json({ error: idErr.message }, 500);

  const todoIds = (ids ?? []).map((r) => r.id).filter((id) => !doneIds.has(id)).slice(0, batch);
  if (todoIds.length === 0) {
    return json({ reindexed: 0, remaining: 0, total: ids?.length ?? 0, failed: [] });
  }

  // 2) details uniquement pour le petit lot.
  const { data: rows, error } = await supabase
    .from("tools").select("id, name, short_desc, description_md").in("id", todoIds);
  if (error) return json({ error: error.message }, 500);

  let ok = 0;
  const failed: string[] = [];
  for (const t of rows ?? []) {
    const text = [t.name, t.short_desc, t.description_md].filter(Boolean).join(". ").slice(0, 512);
    try {
      const embedding = await model.run(text, { mean_pool: true, normalize: true });
      const { error: upErr } = await supabase
        .from("search_embeddings")
        .upsert({ tool_id: t.id, embedding, updated_at: new Date().toISOString() }, { onConflict: "tool_id" });
      if (upErr) failed.push(`${t.id}:${upErr.message}`);
      else ok++;
    } catch (e) {
      failed.push(`${t.id}:${String(e)}`);
    }
  }
  const remaining = (ids?.length ?? 0) - doneIds.size - ok;
  return json({ reindexed: ok, remaining, total: ids?.length ?? 0, failed });
});
