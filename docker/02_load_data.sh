#!/usr/bin/env bash
set -euo pipefail

# Reuse the canonical seed script (db/02_seed.sql). Its \copy paths are
# relative to the repo root ('data/...'); with cwd=/ they resolve to the
# /data bind mount, so the CSVs are loaded from the same single source.
cd /
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /db/02_seed.sql

psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c "SELECT 'customers rows=' || count(*) FROM customers" \
  -c "SELECT 'products rows=' || count(*) FROM products" \
  -c "SELECT 'orders rows=' || count(*) FROM orders" \
  -c "SELECT 'order_items rows=' || count(*) FROM order_items"
