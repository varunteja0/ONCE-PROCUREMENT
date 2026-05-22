# bootstrap-landing.ps1
# One-shot script to materialise the landing/ directory.
#
# Why this exists: Agent A9 generated the marketing landing site for
# `getonce.com`, but its sandboxed file-creation tool could not mkdir new
# top-level folders. Run this once to produce landing/index.html,
# landing/vercel.json, and landing/README.md.
#
# Usage (Windows PowerShell 5.1+, from repo root):
#   powershell -ExecutionPolicy Bypass -File .\bootstrap-landing.ps1
#
# After running, delete this script and commit the landing/ folder.

$ErrorActionPreference = 'Stop'
$repoRoot   = $PSScriptRoot
$landingDir = Join-Path $repoRoot 'landing'

if (-not (Test-Path $landingDir)) {
    New-Item -ItemType Directory -Path $landingDir | Out-Null
    Write-Host "Created $landingDir" -ForegroundColor Green
} else {
    Write-Host "$landingDir already exists" -ForegroundColor Yellow
}

# --- landing/index.html -----------------------------------------------------
$indexHtml = @'
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
    <meta name="theme-color" content="#4f46e5" />
    <title>Once — Submit once. Prove it forever.</title>
    <meta
      name="description"
      content="Once is the supplier-portal autopilot for US specialty insurance MGAs. Capture submission data once, submit to every carrier portal, and emit cryptographically signed audit receipts."
    />
    <link rel="canonical" href="https://getonce.com/" />
    <meta property="og:title" content="Once — Submit once. Prove it forever." />
    <meta
      property="og:description"
      content="The supplier-portal autopilot for US specialty insurance MGAs."
    />
    <meta property="og:url" content="https://getonce.com/" />
    <meta property="og:type" content="website" />
    <meta name="twitter:card" content="summary_large_image" />
    <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%234f46e5'/%3E%3Ctext x='16' y='22' font-family='system-ui,sans-serif' font-size='18' font-weight='700' text-anchor='middle' fill='white'%3E1%3C/text%3E%3C/svg%3E" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"
      rel="stylesheet"
    />
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
      tailwind.config = {
        theme: {
          extend: {
            fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'] },
            colors: {
              brand: {
                50: '#eef2ff',
                100: '#e0e7ff',
                500: '#6366f1',
                600: '#4f46e5',
                700: '#4338ca',
                900: '#312e81',
              },
            },
          },
        },
      };
    </script>
    <style>
      html { scroll-behavior: smooth; }
      body { font-family: 'Inter', system-ui, sans-serif; }
      .bg-grid {
        background-image:
          linear-gradient(to right, rgba(99,102,241,0.08) 1px, transparent 1px),
          linear-gradient(to bottom, rgba(99,102,241,0.08) 1px, transparent 1px);
        background-size: 32px 32px;
      }
    </style>
  </head>
  <body class="bg-white text-slate-900 antialiased">
    <header class="border-b border-slate-100 bg-white/80 backdrop-blur sticky top-0 z-40">
      <div class="mx-auto max-w-6xl px-6 h-16 flex items-center justify-between">
        <a href="/" class="flex items-center gap-2 font-bold text-lg">
          <span class="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white">1</span>
          Once
        </a>
        <nav class="hidden md:flex items-center gap-8 text-sm text-slate-600">
          <a href="#problem" class="hover:text-slate-900">Problem</a>
          <a href="#how" class="hover:text-slate-900">How it works</a>
          <a href="#receipts" class="hover:text-slate-900">Receipts</a>
          <a href="https://app.getonce.com" class="hover:text-slate-900">Sign in</a>
        </nav>
        <a href="#demo" class="inline-flex items-center rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700">Book a demo</a>
      </div>
    </header>

    <section class="relative overflow-hidden bg-grid">
      <div class="mx-auto max-w-6xl px-6 pt-24 pb-20 md:pt-32 md:pb-28">
        <div class="max-w-3xl">
          <p class="inline-flex items-center gap-2 rounded-full bg-brand-50 px-3 py-1 text-xs font-medium text-brand-700">
            <span class="inline-block h-1.5 w-1.5 rounded-full bg-brand-600"></span>
            For US specialty-insurance MGAs &amp; wholesalers
          </p>
          <h1 class="mt-6 text-5xl md:text-6xl font-extrabold tracking-tight text-slate-900">
            Submit once.<br />
            <span class="text-brand-600">Prove it forever.</span>
          </h1>
          <p class="mt-6 text-xl text-slate-600 leading-relaxed">
            Once is the supplier-portal autopilot for US specialty insurance
            MGAs. Capture producer submission data once, submit it to every
            carrier portal, and walk away with cryptographically signed audit
            receipts you can hand to any underwriter, auditor, or regulator.
          </p>
          <div class="mt-10 flex flex-wrap items-center gap-4">
            <a href="#demo" class="inline-flex items-center rounded-lg bg-brand-600 px-6 py-3 text-base font-semibold text-white shadow-sm hover:bg-brand-700">Book a 20-min demo</a>
            <a href="#how" class="inline-flex items-center rounded-lg border border-slate-200 px-6 py-3 text-base font-semibold text-slate-700 hover:bg-slate-50">See how it works →</a>
          </div>
          <p class="mt-6 text-sm text-slate-500">
            Ed25519-signed receipts · SOC 2 in progress · Built for AmTrust,
            Markel, Applied Epic, Vertafore, Sircon
          </p>
        </div>
      </div>
    </section>

    <section id="problem" class="border-t border-slate-100 bg-slate-50">
      <div class="mx-auto max-w-6xl px-6 py-24">
        <div class="max-w-3xl">
          <p class="text-sm font-semibold uppercase tracking-wider text-brand-600">The problem</p>
          <h2 class="mt-3 text-3xl md:text-4xl font-bold tracking-tight">
            Every carrier wants the same data — in their own broken portal.
          </h2>
          <p class="mt-4 text-lg text-slate-600">
            A mid-size MGA juggles 8–25 carrier portals. Each one demands the
            same supplier data in a slightly different shape, on a slightly
            different login, with a slightly different ToS that nobody reads.
            Your team re-keys it. Mistakes compound. Audits hurt.
          </p>
        </div>
        <div class="mt-12 grid gap-6 md:grid-cols-3">
          <div class="rounded-xl bg-white p-6 border border-slate-200">
            <div class="text-3xl font-bold text-brand-600">8–25</div>
            <p class="mt-2 text-slate-700 font-semibold">Carrier portals per MGA</p>
            <p class="mt-1 text-sm text-slate-500">
              AmTrust, Markel, Applied Epic, Vertafore AMS360, Sircon, CNA,
              Nationwide E&amp;S, Guidewire, HawkSoft, EzLynx, NowCerts…
            </p>
          </div>
          <div class="rounded-xl bg-white p-6 border border-slate-200">
            <div class="text-3xl font-bold text-brand-600">40+ hrs / wk</div>
            <p class="mt-2 text-slate-700 font-semibold">Spent re-keying data</p>
            <p class="mt-1 text-sm text-slate-500">
              Junior staff copy-paste the same producer profile dozens of times
              every week. One typo and the policy is wrong.
            </p>
          </div>
          <div class="rounded-xl bg-white p-6 border border-slate-200">
            <div class="text-3xl font-bold text-brand-600">0</div>
            <p class="mt-2 text-slate-700 font-semibold">Tamper-proof audit trail</p>
            <p class="mt-1 text-sm text-slate-500">
              Screenshots aren&#39;t evidence. When an underwriter or regulator
              asks &quot;what exactly did you submit?&quot;, nobody can answer.
            </p>
          </div>
        </div>
      </div>
    </section>

    <section id="how" class="border-t border-slate-100">
      <div class="mx-auto max-w-6xl px-6 py-24">
        <div class="max-w-3xl">
          <p class="text-sm font-semibold uppercase tracking-wider text-brand-600">How it works</p>
          <h2 class="mt-3 text-3xl md:text-4xl font-bold tracking-tight">
            Three steps. One source of truth.
          </h2>
        </div>
        <div class="mt-12 grid gap-8 md:grid-cols-3">
          <div>
            <div class="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-brand-600 text-white font-bold">1</div>
            <h3 class="mt-4 text-xl font-semibold">Capture once</h3>
            <p class="mt-2 text-slate-600">
              Producer fills a single Once profile — licenses, E&amp;O,
              appointments, NAIC IDs, banking. Stored encrypted, owned by them.
            </p>
          </div>
          <div>
            <div class="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-brand-600 text-white font-bold">2</div>
            <h3 class="mt-4 text-xl font-semibold">Submit to many</h3>
            <p class="mt-2 text-slate-600">
              Browser extension and server-side Playwright bots fill carrier
              portals at machine speed — with explicit per-portal consent, ToS
              tracked, captcha-aware, drift-monitored every 15 minutes.
            </p>
          </div>
          <div>
            <div class="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-brand-600 text-white font-bold">3</div>
            <h3 class="mt-4 text-xl font-semibold">Prove forever</h3>
            <p class="mt-2 text-slate-600">
              Every successful submission emits an Ed25519-signed receipt —
              payload hash, ToS hash, consent ID, timestamp. Verifiable by
              anyone at <code class="text-brand-700">verify.getonce.com</code>.
            </p>
          </div>
        </div>
      </div>
    </section>

    <section id="receipts" class="border-t border-slate-100 bg-slate-900 text-slate-100">
      <div class="mx-auto max-w-6xl px-6 py-24 grid gap-12 md:grid-cols-2 md:items-center">
        <div>
          <p class="text-sm font-semibold uppercase tracking-wider text-brand-100">Receipts you can verify</p>
          <h2 class="mt-3 text-3xl md:text-4xl font-bold tracking-tight">
            Evidence that holds up under audit.
          </h2>
          <p class="mt-4 text-lg text-slate-300">
            Every Once receipt is an Ed25519 signature over a canonical JSON
            payload — supplier, portal, submission time, hash of exactly what
            was submitted, and the consent that authorized it. Public keys are
            published. Verification is one HTTP call. No vendor lock-in.
          </p>
          <ul class="mt-6 space-y-2 text-slate-300">
            <li>✓ Cryptographically verifiable, not just logged</li>
            <li>✓ Per-portal consent ledger, signed by the supplier</li>
            <li>✓ Public verifier at <code class="text-white">verify.getonce.com</code></li>
            <li>✓ Receipt protocol open-sourced (Q2 2027 roadmap)</li>
          </ul>
        </div>
        <div class="rounded-2xl bg-slate-950 border border-slate-800 p-6 text-sm font-mono text-slate-200 shadow-2xl overflow-x-auto">
<pre class="whitespace-pre"><span class="text-slate-500"># GET https://verify.getonce.com/verify/8f3c…</span>
{
  <span class="text-brand-100">&quot;verified&quot;</span>: <span class="text-emerald-400">true</span>,
  <span class="text-brand-100">&quot;payload&quot;</span>: {
    <span class="text-brand-100">&quot;receipt_id&quot;</span>:    <span class="text-amber-200">&quot;8f3c…&quot;</span>,
    <span class="text-brand-100">&quot;supplier_id&quot;</span>:   <span class="text-amber-200">&quot;a91d…&quot;</span>,
    <span class="text-brand-100">&quot;portal&quot;</span>:        <span class="text-amber-200">&quot;amtrust&quot;</span>,
    <span class="text-brand-100">&quot;submitted_at&quot;</span>:  <span class="text-amber-200">&quot;2026-08-14T17:02:11Z&quot;</span>,
    <span class="text-brand-100">&quot;payload_hash&quot;</span>:  <span class="text-amber-200">&quot;sha256:7b1a…&quot;</span>,
    <span class="text-brand-100">&quot;tos_version_hash&quot;</span>: <span class="text-amber-200">&quot;sha256:c44e…&quot;</span>,
    <span class="text-brand-100">&quot;consent_record_id&quot;</span>: <span class="text-amber-200">&quot;6e2f…&quot;</span>
  },
  <span class="text-brand-100">&quot;public_key_id&quot;</span>:  <span class="text-amber-200">&quot;prod-2026-01&quot;</span>,
  <span class="text-brand-100">&quot;sig&quot;</span>:            <span class="text-amber-200">&quot;ed25519:9a44…&quot;</span>
}</pre>
        </div>
      </div>
    </section>

    <section id="demo" class="border-t border-slate-100">
      <div class="mx-auto max-w-4xl px-6 py-24 text-center">
        <h2 class="text-3xl md:text-4xl font-bold tracking-tight">
          See Once fill a real carrier portal in 60 seconds.
        </h2>
        <p class="mt-4 text-lg text-slate-600">
          20-minute call. Live demo, no slides. We&#39;ll mock-submit through
          your two messiest portals on a sandbox account.
        </p>
        <div class="mt-10 mx-auto max-w-2xl rounded-2xl border border-slate-200 bg-slate-50 p-8">
          <div id="cal-embed" data-cal-link="once/demo" class="min-h-[120px] flex flex-col items-center justify-center text-slate-600">
            <p class="text-base">
              📅 Booking widget loads here once Cal.com link
              <code class="text-brand-700">once/demo</code> is provisioned.
            </p>
            <a href="mailto:founders@getonce.com?subject=Once%20demo%20request" class="mt-4 inline-flex items-center rounded-lg bg-brand-600 px-6 py-3 text-base font-semibold text-white shadow-sm hover:bg-brand-700">Email founders@getonce.com</a>
          </div>
        </div>
      </div>
    </section>

    <footer class="border-t border-slate-100 bg-slate-50">
      <div class="mx-auto max-w-6xl px-6 py-12 grid gap-8 md:grid-cols-4 text-sm">
        <div>
          <div class="flex items-center gap-2 font-bold text-base">
            <span class="inline-flex h-7 w-7 items-center justify-center rounded-md bg-brand-600 text-white">1</span>
            Once
          </div>
          <p class="mt-3 text-slate-500">Submit once. Prove it forever.</p>
        </div>
        <div>
          <p class="font-semibold text-slate-700">Product</p>
          <ul class="mt-3 space-y-2 text-slate-500">
            <li><a class="hover:text-slate-900" href="https://app.getonce.com">App</a></li>
            <li><a class="hover:text-slate-900" href="https://verify.getonce.com">Verifier</a></li>
            <li><a class="hover:text-slate-900" href="https://api.getonce.com/docs">API docs</a></li>
          </ul>
        </div>
        <div>
          <p class="font-semibold text-slate-700">Legal</p>
          <ul class="mt-3 space-y-2 text-slate-500">
            <li><a class="hover:text-slate-900" href="/privacy">Privacy</a></li>
            <li><a class="hover:text-slate-900" href="/terms">Terms</a></li>
            <li><a class="hover:text-slate-900" href="/security">Security</a></li>
            <li><a class="hover:text-slate-900" href="/dpa">DPA</a></li>
          </ul>
        </div>
        <div>
          <p class="font-semibold text-slate-700">Company</p>
          <ul class="mt-3 space-y-2 text-slate-500">
            <li><a class="hover:text-slate-900" href="mailto:founders@getonce.com">Contact</a></li>
            <li><a class="hover:text-slate-900" href="https://github.com/once-inc">GitHub</a></li>
          </ul>
        </div>
      </div>
      <div class="border-t border-slate-200">
        <div class="mx-auto max-w-6xl px-6 py-6 text-xs text-slate-500 flex flex-col md:flex-row md:items-center md:justify-between gap-2">
          <p>© <span id="yr"></span> Once, Inc. All rights reserved.</p>
          <p>Once, Inc. is not affiliated with any carrier or platform mentioned.</p>
        </div>
      </div>
    </footer>

    <script>
      document.getElementById('yr').textContent = new Date().getFullYear();
    </script>
  </body>
</html>
'@

# --- landing/vercel.json ----------------------------------------------------
$vercelJson = @'
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "cleanUrls": true,
  "trailingSlash": false,
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        {
          "key": "Content-Security-Policy",
          "value": "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://app.cal.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.tailwindcss.com; font-src 'self' https://fonts.gstatic.com data:; img-src 'self' data: https:; connect-src 'self' https://api.cal.com; frame-src https://app.cal.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'; upgrade-insecure-requests"
        },
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" },
        { "key": "Permissions-Policy", "value": "accelerometer=(), camera=(), geolocation=(), gyroscope=(), microphone=(), payment=(), usb=()" },
        { "key": "Strict-Transport-Security", "value": "max-age=63072000; includeSubDomains; preload" }
      ]
    }
  ]
}
'@

# --- landing/README.md ------------------------------------------------------
$readme = @'
# Once — Landing site (`getonce.com`)

Static one-pager that lives at the root of `getonce.com`. The app (React/Vite)
lives at `app.getonce.com` and the verifier at `verify.getonce.com` — this
folder is intentionally just `index.html` + `vercel.json` so the marketing
root deploys in ~2 seconds and never blocks on the app build.

## Stack
- Single HTML file.
- Tailwind via the `cdn.tailwindcss.com` script (no build step).
- Inter from Google Fonts.
- Cal.com embed placeholder (`data-cal-link="once/demo"`) — wire up once the
  Cal.com booking page exists.

## Local preview
Any static server works:

```bash
cd landing
python -m http.server 8000
# open http://localhost:8000
```

## Deploy (Vercel)

This is a **separate Vercel project** from `frontend/` so the marketing
homepage and the app deploy independently.

### One-time setup

```bash
cd landing
vercel link               # create a new project, e.g. "once-landing"
vercel domains add getonce.com
vercel domains add www.getonce.com
vercel alias getonce.com
```

Then in the Vercel dashboard for the `once-landing` project:

- **Root directory**: `landing`
- **Framework preset**: Other
- **Build command**: (leave blank)
- **Output directory**: `.` (root)
- **Install command**: (leave blank)
- **Production branch**: `main`

### CI/CD

The repo-level GitHub workflow `deploy-frontend.yml` only handles the **app**
project. The landing project deploys via Vercel's native Git integration
(push to `main` with changes in `landing/**` → auto-deploy).

If you'd rather drive it from GitHub Actions, mirror `deploy-frontend.yml`
with `working-directory: landing` and a separate `VERCEL_PROJECT_ID_LANDING`
secret.

## DNS

In Cloudflare, point the apex and `www` at Vercel:

| Name           | Type  | Value                  | Proxy   |
| -------------- | ----- | ---------------------- | ------- |
| `getonce.com`  | CNAME | `cname.vercel-dns.com` | DNS-only |
| `www`          | CNAME | `cname.vercel-dns.com` | DNS-only |

Cloudflare supports CNAME flattening at the apex; otherwise use Vercel's A
records (76.76.21.21).
'@

# Write files (UTF-8, no BOM)
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText((Join-Path $landingDir 'index.html'),  $indexHtml,  $utf8NoBom)
[System.IO.File]::WriteAllText((Join-Path $landingDir 'vercel.json'), $vercelJson, $utf8NoBom)
[System.IO.File]::WriteAllText((Join-Path $landingDir 'README.md'),   $readme,     $utf8NoBom)

Write-Host "Wrote landing/index.html, landing/vercel.json, landing/README.md" -ForegroundColor Green
Write-Host "You can now `git add landing/` and delete scripts/bootstrap-landing.ps1." -ForegroundColor Cyan
