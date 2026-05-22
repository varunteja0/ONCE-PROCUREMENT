/**
 * OnceTax Worker entrypoint (Cloudflare Workers).
 *
 * Phase 1 (Wedge B parallel-run, 30 days): this file is the source of truth for
 * `wrangler dev` / `wrangler deploy`. It serves a `/health` endpoint directly
 * and (optionally, when the Remix server build is present at
 * `./build/server/index.js`) delegates everything else to the Remix handler.
 *
 * Keeping the health endpoint outside Remix lets the smoke test import this
 * module without spinning up Vite / Remix at all.
 */

import type { OnceTaxEnv } from "./app/lib/shopify";

export type Env = OnceTaxEnv;

interface HealthBody {
  ok: true;
  service: "oncetax";
  version: string;
  wedge: "B";
  mode: "parallel-run-30d";
  ts: string;
}

const VERSION = "0.1.0";

function healthResponse(): Response {
  const body: HealthBody = {
    ok: true,
    service: "oncetax",
    version: VERSION,
    wedge: "B",
    mode: "parallel-run-30d",
    ts: new Date().toISOString(),
  };
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

async function tryRemix(
  request: Request,
  env: Env,
  ctx: ExecutionContext,
): Promise<Response> {
  try {
    // Dynamic imports so the Worker still loads (and the smoke test still
    // runs) before `npm run build` has produced the Remix server bundle.
    const [build, { createRequestHandler }] = await Promise.all([
      // @ts-expect-error generated at build time by `remix vite:build`
      import("./build/server/index.js"),
      import("@remix-run/cloudflare"),
    ]);
    const handler = createRequestHandler(build as never, "production");
    return await handler(request, { cloudflare: { env, ctx } } as never);
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error("[oncetax] remix handler unavailable:", err);
    return new Response("Not Found", { status: 404 });
  }
}

const worker: ExportedHandler<Env> = {
  async fetch(
    request: Request,
    env: Env,
    ctx: ExecutionContext,
  ): Promise<Response> {
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/health") {
      return healthResponse();
    }
    return tryRemix(request, env, ctx);
  },
};

export default worker;
