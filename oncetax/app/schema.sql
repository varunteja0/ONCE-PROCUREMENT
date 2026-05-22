-- OnceTax D1 schema (v0)
-- Apply with: wrangler d1 execute oncetax --file=app/schema.sql

CREATE TABLE IF NOT EXISTS shops (
  id            TEXT PRIMARY KEY,
  shop          TEXT NOT NULL UNIQUE,
  access_token  TEXT NOT NULL,
  plan          TEXT,
  installed_at  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_shops_shop ON shops(shop);

CREATE TABLE IF NOT EXISTS orders_cache (
  id             TEXT PRIMARY KEY,
  shop           TEXT NOT NULL,
  order_id       TEXT NOT NULL,
  state          TEXT NOT NULL,
  taxable_cents  INTEGER NOT NULL DEFAULT 0,
  tax_cents      INTEGER NOT NULL DEFAULT 0,
  captured_at    INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_orders_cache_shop_state
  ON orders_cache(shop, state);
CREATE INDEX IF NOT EXISTS idx_orders_cache_shop_captured
  ON orders_cache(shop, captured_at);

CREATE TABLE IF NOT EXISTS filings (
  id            TEXT PRIMARY KEY,
  shop          TEXT NOT NULL,
  state         TEXT NOT NULL,
  period_start  TEXT NOT NULL,
  period_end    TEXT NOT NULL,
  pdf_r2_key    TEXT NOT NULL,
  generated_at  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_filings_shop ON filings(shop);
CREATE INDEX IF NOT EXISTS idx_filings_shop_state ON filings(shop, state);
