-- Roles for the RLS tenant-isolation model. Run as a superuser.
--
-- Three roles, least privilege:
--   sample_owner : owns the schema/tables, runs DDL + data loads. NOLOGIN.
--   sample_app   : the agent's query role. SELECT-only, RLS-enforced, NO bypass.
--                  This is THE tenant-isolation boundary. Every model-generated
--                  query runs as this role.
--   sample_auth  : the auth handler's role. SELECT on customers ONLY, used purely
--                  to resolve an authenticated email -> customer id before any
--                  tenant context exists. Never used by agent tools.
--
-- Passwords here are local-dev only and also live in .env (gitignored).

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sample_owner') THEN
        CREATE ROLE sample_owner NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sample_app') THEN
        CREATE ROLE sample_app LOGIN PASSWORD 'sample_app_pw';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sample_auth') THEN
        CREATE ROLE sample_auth LOGIN PASSWORD 'sample_auth_pw';
    END IF;
END
$$;

-- Defense in depth: neither login role may ever bypass RLS or hold superuser.
ALTER ROLE sample_app  NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
ALTER ROLE sample_auth NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;

-- Let the owner hand objects to the login roles within this database.
GRANT sample_owner TO CURRENT_USER;
