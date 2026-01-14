-- Upgrade script for existing databases
-- Converts VARCHAR status/decision columns to proper PostgreSQL enum types
-- Run this if you have an existing database from before the enum fix
--
-- Usage:
--   docker exec -i controlplane-postgres psql -U controlplane -d controlplane < scripts/upgrade_enum_types.sql

-- Check if enum types already exist (idempotent)
DO $$
BEGIN
    -- Create templatestatus enum if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'templatestatus') THEN
        CREATE TYPE templatestatus AS ENUM ('ACTIVE', 'DEPRECATED', 'REVIEW');

        -- Convert templates.status column
        ALTER TABLE templates ALTER COLUMN status DROP DEFAULT;
        ALTER TABLE templates ALTER COLUMN status TYPE templatestatus USING UPPER(status)::templatestatus;
        ALTER TABLE templates ALTER COLUMN status SET DEFAULT 'ACTIVE'::templatestatus;

        RAISE NOTICE 'Created templatestatus enum and converted templates.status column';
    ELSE
        RAISE NOTICE 'templatestatus enum already exists, skipping';
    END IF;

    -- Create decision enum if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'decision') THEN
        CREATE TYPE decision AS ENUM ('MATCH', 'REVIEW', 'NEW', 'REJECT');

        -- Convert evaluations.decision column
        ALTER TABLE evaluations ALTER COLUMN decision TYPE decision USING UPPER(decision)::decision;

        RAISE NOTICE 'Created decision enum and converted evaluations.decision column';
    ELSE
        RAISE NOTICE 'decision enum already exists, skipping';
    END IF;
END
$$;

-- Verify the changes
SELECT
    column_name,
    data_type,
    udt_name
FROM information_schema.columns
WHERE table_name IN ('templates', 'evaluations')
  AND column_name IN ('status', 'decision')
ORDER BY table_name, column_name;
