-- Row-level security: the tenant-isolation boundary. Run as a superuser
-- (or table owner) AFTER the schema and data load.
--
-- The authenticated customer id is carried in the per-transaction GUC
-- `app.customer_id`, set with `SET LOCAL app.customer_id = '<id>'` at the start
-- of every query transaction. The expression below resolves it:
--   - unset or empty  -> NULL  -> every `col = NULL` is false -> ZERO rows (fail-closed)
--   - set to an int   -> that customer's rows only
-- There is deliberately no fallback to "all rows": a missing context denies access.

-- ---------------------------------------------------------------------------
-- Privileges: strip defaults, then grant the minimum each role needs.
-- ---------------------------------------------------------------------------
REVOKE ALL ON customers, products, orders, order_items FROM PUBLIC;

GRANT USAGE ON SCHEMA public TO sample_app, sample_auth;

-- Agent query role: read-only on everything it may touch. NO write privileges,
-- so DML is impossible regardless of what SQL the model emits.
GRANT SELECT ON customers, products, orders, order_items TO sample_app;

-- Auth role: just enough to resolve email -> customer id at login time.
GRANT SELECT ON customers TO sample_auth;

-- ---------------------------------------------------------------------------
-- Enable + FORCE RLS on the tenant-scoped tables.
-- FORCE makes the policies apply even to the table owner (defense in depth);
-- the app never connects as owner, but this removes the owner-bypass footgun.
-- `products` is a shared catalog: no RLS, everyone with SELECT sees all rows.
-- ---------------------------------------------------------------------------
ALTER TABLE customers   ENABLE ROW LEVEL SECURITY;
ALTER TABLE customers   FORCE  ROW LEVEL SECURITY;
ALTER TABLE orders      ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders      FORCE  ROW LEVEL SECURITY;
ALTER TABLE order_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_items FORCE  ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- Policies. Each is scoped `TO <role>` so a role only ever gets its own rule;
-- policies are permissive/OR-ed, but role-scoping keeps them disjoint.
-- ---------------------------------------------------------------------------

-- customers: the app sees only its own row...
DROP POLICY IF EXISTS customers_app_self ON customers;
CREATE POLICY customers_app_self ON customers
    FOR SELECT TO sample_app
    USING (id = nullif(current_setting('app.customer_id', true), '')::int);

-- ...the auth role may read all customers, but ONLY to map email -> id.
DROP POLICY IF EXISTS customers_auth_lookup ON customers;
CREATE POLICY customers_auth_lookup ON customers
    FOR SELECT TO sample_auth
    USING (true);

-- orders: scoped directly by owning customer.
DROP POLICY IF EXISTS orders_app_self ON orders;
CREATE POLICY orders_app_self ON orders
    FOR SELECT TO sample_app
    USING (customer_id = nullif(current_setting('app.customer_id', true), '')::int);

-- order_items: scoped via the owning order. The orders subquery is itself
-- RLS-filtered for sample_app, so this is doubly enforced.
DROP POLICY IF EXISTS order_items_app_self ON order_items;
CREATE POLICY order_items_app_self ON order_items
    FOR SELECT TO sample_app
    USING (EXISTS (
        SELECT 1 FROM orders o
        WHERE o.id = order_items.order_id
          AND o.customer_id = nullif(current_setting('app.customer_id', true), '')::int
    ));
