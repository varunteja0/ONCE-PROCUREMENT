import { describe, expect, it } from "vitest";

import worker, { type Env } from "./worker";

function makeEnv(): Env {
  return {
    DB: {} as unknown as D1Database,
    PDF_BUCKET: {} as unknown as R2Bucket,
    SESSIONS: {} as unknown as KVNamespace,
    SHOPIFY_API_KEY: "test-key",
    SHOPIFY_API_SECRET: "test-secret",
    APP_URL: "http://localhost:8788",
    SCOPES: "read_orders,read_customers",
    RESEND_API_KEY: "test-resend",
  };
}

const fakeCtx = {
  waitUntil: (_p: Promise<unknown>) => undefined,
  passThroughOnException: () => undefined,
} as unknown as ExecutionContext;

// Workers' fetch signature requires IncomingRequest (with cf properties
// that only the runtime can mint). For unit tests we use a plain Request,
// so alias the handler to a Request-accepting signature.
type FetchHandler = (req: Request, env: Env, ctx: ExecutionContext) => Promise<Response>;
const handle = worker.fetch as unknown as FetchHandler;

describe("oncetax worker /health", () => {
  it("returns 200 with service identity", async () => {
    const req = new Request("https://oncetax.test/health", { method: "GET" });
    const res = await handle(req, makeEnv(), fakeCtx);
    expect(res.status).toBe(200);
    const body = (await res.json()) as {
      ok: boolean;
      service: string;
      wedge: string;
      mode: string;
    };
    expect(body.ok).toBe(true);
    expect(body.service).toBe("oncetax");
    expect(body.wedge).toBe("B");
    expect(body.mode).toBe("parallel-run-30d");
  });

  it("falls through to 404 for unknown routes (no Remix build present)", async () => {
    const req = new Request("https://oncetax.test/does-not-exist");
    const res = await handle(req, makeEnv(), fakeCtx);
    expect(res.status).toBe(404);
  });

  it("does not treat non-GET /health as health", async () => {
    const req = new Request("https://oncetax.test/health", { method: "POST" });
    const res = await handle(req, makeEnv(), fakeCtx);
    expect(res.status).toBe(404);
  });
});
