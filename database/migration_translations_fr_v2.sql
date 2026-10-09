-- Migration FR v2 (Chantier C2/C3, 2026-06-20)
-- A coller dans le SQL Editor WEB de Supabase. Idempotent, ASCII.
-- C2 : note de prix traduite. C3 : raison d'alternative traduite.
ALTER TABLE tools ADD COLUMN IF NOT EXISTS pricing_note_fr TEXT;
ALTER TABLE alternatives ADD COLUMN IF NOT EXISTS reason_fr TEXT;
