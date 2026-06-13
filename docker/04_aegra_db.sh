#!/usr/bin/env bash
set -euo pipefail

psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres <<'SQL'
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'aegra') THEN
        CREATE ROLE aegra LOGIN PASSWORD 'aegra_pw';
    END IF;
END
$$;

SELECT 'CREATE DATABASE aegra OWNER aegra'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'aegra')
\gexec
SQL

psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d aegra <<'SQL'
CREATE EXTENSION IF NOT EXISTS vector;
SQL
