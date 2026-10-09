// YggNexus - recherche semantique. Embed la requete via gte-small (384d)
// puis appelle la RPC match_tools. Lecture seule, publique (cle anon).
import { createClient } from "jsr:@supabase/supabase-js@2";

const model = new Supabase.ai.Session("gte-small");

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: cors });
  }
  const url = new URL(req.url);
  const q = (url.searchParams.get("q") ?? "").trim();
  const count = Math.min(Math.max(Number(url.searchParams.get("count") ?? "10"), 1), 50);

  const json = (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), {
      status,
      headers: { ...cors, "Content-Type": "application/json" },
    });

  if (!q) return json({ results: [] });

  try {
    const embedding = await model.run(q, { mean_pool: true, normalize: true });
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_ANON_KEY")!,
    );
    const { data, error } = await supabase.rpc("match_tools", {
      query_embedding: embedding,
      match_count: count,
    });
    if (error) return json({ error: error.message }, 500);
    return json({ results: data ?? [] });
  } catch (e) {
    return json({ error: String(e) }, 500);
  }
});
