export interface ShopRow {
  id: string;
  shop: string;
  /** Legacy plaintext column — kept for back-compat reads only. New rows
   *  store '' here and use the ciphertext columns instead. */
  access_token: string;
  access_token_ciphertext: string | null;
  access_token_iv: string | null;
  plan: string | null;
  installed_at: number;
}

export interface OrderCacheRow {
  id: string;
  shop: string;
  order_id: string;
  state: string;
  taxable_cents: number;
  tax_cents: number;
  captured_at: number;
}

export interface FilingRow {
  id: string;
  shop: string;
  state: string;
  period_start: string;
  period_end: string;
  pdf_r2_key: string;
  generated_at: number;
}

export interface StateTotalsRow {
  state: string;
  order_count: number;
  taxable_cents: number;
  tax_cents: number;
}

function nowSec(): number {
  return Math.floor(Date.now() / 1000);
}

export async function upsertShop(
  db: D1Database,
  input: {
    shop: string;
    access_token: string;
    plan?: string | null;
  },
  workerDataKey: string
): Promise<void> {
  if (!workerDataKey) {
    throw new Error("WORKER_DATA_KEY is required to persist Shopify access tokens at rest");
  }
  // Lazy import so worker bundles that never touch upsertShop (e.g.
  // smoke.test.ts) don't pay the crypto import cost.
  const { sealString } = await import("./crypto");
  const sealed = await sealString(input.access_token, workerDataKey);
  const id = `shop_${input.shop}`;
  await db
    .prepare(
      `INSERT INTO shops (id, shop, access_token, access_token_ciphertext, access_token_iv, plan, installed_at)
       VALUES (?1, ?2, '', ?3, ?4, ?5, ?6)
       ON CONFLICT(shop) DO UPDATE SET
         access_token = '',
         access_token_ciphertext = excluded.access_token_ciphertext,
         access_token_iv = excluded.access_token_iv,
         plan = COALESCE(excluded.plan, shops.plan)`
    )
    .bind(id, input.shop, sealed.ciphertext, sealed.iv, input.plan ?? null, nowSec())
    .run();
}

/**
 * Decrypt the stored access token for ``shop``, returning ``null`` if the
 * shop is unknown. Throws if a row exists but its ciphertext columns are
 * empty (indicating a pre-migration row that needs to reinstall).
 */
export async function getShopAccessToken(db: D1Database, shop: string, workerDataKey: string): Promise<string | null> {
  const row = await getShop(db, shop);
  if (!row) return null;
  if (!row.access_token_ciphertext || !row.access_token_iv) {
    throw new Error(`shop ${shop} has no encrypted access token — the shop needs to reinstall`);
  }
  const { openString } = await import("./crypto");
  return openString(
    {
      ciphertext: row.access_token_ciphertext,
      iv: row.access_token_iv,
    },
    workerDataKey
  );
}

export async function getShop(db: D1Database, shop: string): Promise<ShopRow | null> {
  const row = await db.prepare(`SELECT * FROM shops WHERE shop = ?1 LIMIT 1`).bind(shop).first<ShopRow>();
  return row ?? null;
}

export async function upsertOrderCache(db: D1Database, row: Omit<OrderCacheRow, never>): Promise<void> {
  await db
    .prepare(
      `INSERT INTO orders_cache
         (id, shop, order_id, state, taxable_cents, tax_cents, captured_at)
       VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
       ON CONFLICT(id) DO UPDATE SET
         state = excluded.state,
         taxable_cents = excluded.taxable_cents,
         tax_cents = excluded.tax_cents,
         captured_at = excluded.captured_at`
    )
    .bind(row.id, row.shop, row.order_id, row.state, row.taxable_cents, row.tax_cents, row.captured_at)
    .run();
}

export async function getStateTotals(db: D1Database, shop: string): Promise<StateTotalsRow[]> {
  const res = await db
    .prepare(
      `SELECT state,
              COUNT(*) AS order_count,
              COALESCE(SUM(taxable_cents), 0) AS taxable_cents,
              COALESCE(SUM(tax_cents), 0) AS tax_cents
       FROM orders_cache
       WHERE shop = ?1
       GROUP BY state
       ORDER BY tax_cents DESC`
    )
    .bind(shop)
    .all<StateTotalsRow>();
  return res.results ?? [];
}

export async function insertFiling(db: D1Database, row: Omit<FilingRow, "generated_at">): Promise<void> {
  await db
    .prepare(
      `INSERT INTO filings
         (id, shop, state, period_start, period_end, pdf_r2_key, generated_at)
       VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)`
    )
    .bind(row.id, row.shop, row.state, row.period_start, row.period_end, row.pdf_r2_key, nowSec())
    .run();
}

export async function listFilings(db: D1Database, shop: string): Promise<FilingRow[]> {
  const res = await db
    .prepare(`SELECT * FROM filings WHERE shop = ?1 ORDER BY generated_at DESC`)
    .bind(shop)
    .all<FilingRow>();
  return res.results ?? [];
}
