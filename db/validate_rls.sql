-- RLS validation, run as the unprivileged sample_app role.
-- Every line prints PASS/FAIL. Any FAIL (or any error) means isolation is broken.
\pset footer off

-- == Context: authenticated as customer 7 ==
SET app.customer_id = '7';

SELECT CASE WHEN count(*) = 1 AND bool_and(id = 7) THEN 'PASS' ELSE 'FAIL' END
       AS customers_sees_only_self FROM customers;

SELECT CASE WHEN count(*) > 0 AND bool_and(customer_id = 7) THEN 'PASS' ELSE 'FAIL' END
       AS orders_sees_only_self FROM orders;

-- No visible order_item may reference an order that isn't ours (would be an orphan).
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       AS order_items_no_cross_tenant_leak
FROM order_items oi
WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.id = oi.order_id);

-- Explicit cross-tenant probe: ask for customer 8 directly.
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       AS direct_cross_tenant_blocked FROM customers WHERE id = 8;

-- Injection-style tautology cannot widen past RLS.
SELECT CASE WHEN count(*) = 1 AND bool_and(id = 7) THEN 'PASS' ELSE 'FAIL' END
       AS tautology_cannot_escape_rls FROM customers WHERE id = 8 OR 1 = 1;

-- Email harvest attempt returns only our own address.
SELECT CASE WHEN count(*) = 1 AND bool_and(id = 7) THEN 'PASS' ELSE 'FAIL' END
       AS email_harvest_blocked FROM customers WHERE email LIKE 'user_%';

-- Shared catalog stays fully visible.
SELECT CASE WHEN count(*) = 80 THEN 'PASS' ELSE 'FAIL' END
       AS products_catalog_visible FROM products;

-- == Switch tenants: authenticated as customer 8 ==
SET app.customer_id = '8';
SELECT CASE WHEN count(*) = 1 AND bool_and(id = 8) THEN 'PASS' ELSE 'FAIL' END
       AS switching_tenant_is_disjoint FROM customers;

-- == Fail-closed: no tenant context at all ==
RESET app.customer_id;
SELECT CASE WHEN (SELECT count(*) FROM customers) = 0
             AND (SELECT count(*) FROM orders) = 0
             AND (SELECT count(*) FROM order_items) = 0
            THEN 'PASS' ELSE 'FAIL' END AS fail_closed_when_unset;

-- Empty string (e.g. a blank header) is also fail-closed, not an error.
SET app.customer_id = '';
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       AS fail_closed_when_empty FROM customers;

-- == Role hygiene ==
SELECT CASE WHEN rolsuper = false AND rolbypassrls = false THEN 'PASS' ELSE 'FAIL' END
       AS app_role_has_no_bypass
FROM pg_roles WHERE rolname = current_user;
