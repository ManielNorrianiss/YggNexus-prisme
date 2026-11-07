-- Migration : type de fiche (outil, agent, skill)
-- 2026-11-06 — agents et skills deviennent des types de fiches du catalogue.
-- Idempotente : peut être rejouée sans risque.

ALTER TABLE tools
    ADD COLUMN IF NOT EXISTS kind TEXT NOT NULL DEFAULT 'tool';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'tools_kind_check'
    ) THEN
        ALTER TABLE tools
            ADD CONSTRAINT tools_kind_check CHECK (kind IN ('tool', 'agent', 'skill'));
    END IF;
END $$;

-- Plateforme hôte d'un agent ou d'une skill (claude, chatgpt, gemini, copilot, autonome...).
-- NULL pour les outils classiques.
ALTER TABLE tools
    ADD COLUMN IF NOT EXISTS platform TEXT;

CREATE INDEX IF NOT EXISTS idx_tools_kind ON tools(kind);

-- Les fiches existantes restent des outils (valeur par défaut).
