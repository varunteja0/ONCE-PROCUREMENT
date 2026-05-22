/**
 * Shopify session storage backed by Cloudflare KV (binding: SESSIONS).
 *
 * Implements the SessionStorage interface from @shopify/shopify-api so that
 * the same code path works in Workers without Node fs.
 */

import type { Session } from "@shopify/shopify-api";

export interface SessionStorageLike {
  storeSession(session: Session): Promise<boolean>;
  loadSession(id: string): Promise<Session | undefined>;
  deleteSession(id: string): Promise<boolean>;
  deleteSessions(ids: string[]): Promise<boolean>;
  findSessionsByShop(shop: string): Promise<Session[]>;
}

const SHOP_INDEX_PREFIX = "shop_index:";
const SESSION_PREFIX = "session:";

export class KvSessionStorage implements SessionStorageLike {
  constructor(
    private readonly kv: KVNamespace,
    private readonly sessionCtor: {
      fromPropertyArray: (entries: [string, unknown][]) => Session;
    },
  ) {}

  async storeSession(session: Session): Promise<boolean> {
    const serialized = JSON.stringify(session.toPropertyArray());
    await this.kv.put(SESSION_PREFIX + session.id, serialized);
    await this.kv.put(SHOP_INDEX_PREFIX + session.shop + ":" + session.id, "1");
    return true;
  }

  async loadSession(id: string): Promise<Session | undefined> {
    const raw = await this.kv.get(SESSION_PREFIX + id);
    if (!raw) return undefined;
    const entries = JSON.parse(raw) as [string, unknown][];
    return this.sessionCtor.fromPropertyArray(entries);
  }

  async deleteSession(id: string): Promise<boolean> {
    const existing = await this.loadSession(id);
    await this.kv.delete(SESSION_PREFIX + id);
    if (existing) {
      await this.kv.delete(SHOP_INDEX_PREFIX + existing.shop + ":" + id);
    }
    return true;
  }

  async deleteSessions(ids: string[]): Promise<boolean> {
    await Promise.all(ids.map((id) => this.deleteSession(id)));
    return true;
  }

  async findSessionsByShop(shop: string): Promise<Session[]> {
    const listing = await this.kv.list({ prefix: SHOP_INDEX_PREFIX + shop + ":" });
    const sessions: Session[] = [];
    for (const key of listing.keys) {
      const sessionId = key.name.slice((SHOP_INDEX_PREFIX + shop + ":").length);
      const s = await this.loadSession(sessionId);
      if (s) sessions.push(s);
    }
    return sessions;
  }
}

export function makeSessionStorage(
  kv: KVNamespace,
  sessionCtor: KvSessionStorage["sessionCtor"],
): KvSessionStorage {
  return new KvSessionStorage(kv, sessionCtor);
}
