-- Load sample rows. Run from the repository root after db/01_schema.sql and
-- before db/03_rls.sql:
--
--   psql -d sample_db -f db/02_seed.sql

SET ROLE sample_owner;

\copy customers (id, name, email, country, created_at) FROM 'data/customers.csv' WITH (FORMAT csv, HEADER true)
\copy products (id, name, category, price_cents) FROM 'data/products.csv' WITH (FORMAT csv, HEADER true)
\copy orders (id, customer_id, status, created_at) FROM 'data/orders.csv' WITH (FORMAT csv, HEADER true)
\copy order_items (id, order_id, product_id, quantity, unit_price_cents) FROM 'data/order_items.csv' WITH (FORMAT csv, HEADER true)

RESET ROLE;
