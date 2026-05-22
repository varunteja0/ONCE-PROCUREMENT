<#
.SYNOPSIS
    Once — Windows PowerShell task runner (mirror of Makefile).

.DESCRIPTION
    Provides the same task surface as the Makefile for Windows users who do
    not have GNU Make installed. Compatible with Windows PowerShell 5.1 and
    PowerShell 7+.

.EXAMPLE
    .\tasks.ps1 setup
    .\tasks.ps1 up
    .\tasks.ps1 test
    .\tasks.ps1 help
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0)] [string] $Task = "help",
    [Parameter(ValueFromRemainingArguments = $true)] [string[]] $Rest
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root      = $PSScriptRoot
$Backend   = Join-Path $Root "backend"
$Frontend  = Join-Path $Root "frontend"
$Extension = Join-Path $Root "extension"
$Verifier  = Join-Path $Root "verifier"
$Scripts   = Join-Path $Root "scripts"

$VenvPy = Join-Path $Backend ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPy)) { $VenvPy = "python" }

function _Section($t) { Write-Host "`n== $t ==" -ForegroundColor Cyan }
function _Run($cmd) { Write-Host "> $cmd" -ForegroundColor DarkGray; & cmd /c $cmd; if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $cmd" } }
function _RunIn($dir, $cmd) { Push-Location $dir; try { _Run $cmd } finally { Pop-Location } }

# ── Help ───────────────────────────────────────────────────────────────────
function Help {
    @"
Once dev tasks — usage: .\tasks.ps1 <task>

Setup & environment
  setup                Bootstrap venv, npm installs, playwright, hooks
  doctor               Diagnose local environment
  clean                Remove caches, venvs, node_modules, build outputs

Compose stack
  up                   docker compose up -d --build
  down                 docker compose down
  logs                 Tail combined logs
  ps                   Show compose status
  shell-db             psql on dev DB
  shell-backend        bash in backend container

Data lifecycle
  seed                 Seed demo tenant
  reset                Nuke local DB + re-migrate + re-seed
  demo                 up + seed + open browser

Tests
  test                 All suites
  test-backend / test-frontend / test-extension / test-verifier
  test-integration     Nginx fixtures + Playwright
  test-watch           Backend pytest watch

Lint / format / typecheck
  lint                 ruff + eslint + prettier + tsc
  fmt                  Auto-format everything
  typecheck            mypy + tsc

Migrations
  migrate              alembic upgrade head
  migrate-new "msg"    new autogenerate revision
  migrate-down         alembic downgrade -1

Build
  build-backend / build-frontend / build-extension / build-all

Security & coverage
  security             bandit + pip-audit + npm audit
  coverage             Combined coverage report

Observability
  obs-up / obs-down

See CHEATSHEET.md for a printable quick reference.
"@ | Write-Host
}

# ── Setup ──────────────────────────────────────────────────────────────────
function Setup    { _Section "Setup";  _Run "python `"$Scripts\dev_setup.py`"" }
function Doctor   { _Section "Doctor"; _Run "python `"$Scripts\dev_doctor.py`"" }
function Clean    {
    _Section "Clean"
    Get-ChildItem -Path $Root -Recurse -Directory -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -in @("__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", "htmlcov", ".vite") } |
        ForEach-Object { Remove-Item -Recurse -Force $_.FullName -ErrorAction SilentlyContinue }
    foreach ($p in @(
        (Join-Path $Backend ".venv"),
        (Join-Path $Root ".cov"),
        (Join-Path $Frontend "node_modules"), (Join-Path $Frontend "dist"),
        (Join-Path $Extension "node_modules"), (Join-Path $Extension "dist"),
        (Join-Path $Root "oncetax\node_modules"), (Join-Path $Root "oncetax\dist"), (Join-Path $Root "oncetax\.wrangler")
    )) { if (Test-Path $p) { Remove-Item -Recurse -Force $p -ErrorAction SilentlyContinue } }
    Write-Host "Done."
}

# ── Compose ────────────────────────────────────────────────────────────────
function Up            { _Run "docker compose up -d --build" }
function Down          { _Run "docker compose down" }
function Logs          { _Run "docker compose logs -f --tail=200" }
function Ps            { _Run "docker compose ps" }
function ShellDb       { _Run "docker compose exec db psql -U $(if ($env:POSTGRES_USER) {$env:POSTGRES_USER} else {'once'}) -d $(if ($env:POSTGRES_DB) {$env:POSTGRES_DB} else {'once'})" }
function ShellBackend  { _Run "docker compose exec backend bash" }

# ── Data ───────────────────────────────────────────────────────────────────
function Seed  { _Run "`"$VenvPy`" `"$Scripts\seed_demo_tenant.py`"" }
function Reset { _Run "python `"$Scripts\dev_reset.py`"" }
function Demo  {
    Up; Seed
    Start-Process "http://localhost:5173"
    Write-Host "Frontend: http://localhost:5173   API: http://localhost:8000/docs   Verifier: http://localhost:8080"
}

# ── Tests ──────────────────────────────────────────────────────────────────
function TestBackend     { _RunIn $Backend  "pytest -q" }
function TestFrontend    { _RunIn $Frontend "npm test --silent" }
function TestExtension   { _RunIn $Extension "npm test --silent" }
function TestVerifier    { _RunIn $Verifier "pytest -q" }
function Test            { TestBackend; TestFrontend; TestExtension; TestVerifier }
function TestIntegration { $env:RUN_INTEGRATION_TESTS = "1"; _RunIn $Backend "pytest -q -m integration" }
function TestWatch       { _RunIn $Backend "pytest -q --looponfail" }

# ── Lint / format / typecheck ──────────────────────────────────────────────
function Lint      { _Run "python `"$Scripts\lint_all.py`"" }
function Fmt       { _Run "python `"$Scripts\format_all.py`"" }
function Typecheck {
    _RunIn $Backend  "mypy app"
    _RunIn $Frontend "npx tsc --noEmit"
    _RunIn $Extension "npx tsc --noEmit"
}

# ── Migrations ─────────────────────────────────────────────────────────────
function Migrate     { _RunIn $Backend "alembic upgrade head" }
function MigrateNew  {
    $msg = ($Rest -join " ").Trim()
    if (-not $msg) { throw "Usage: .\tasks.ps1 migrate-new `"description`"" }
    _RunIn $Backend "alembic revision --autogenerate -m `"$msg`""
}
function MigrateDown { _RunIn $Backend "alembic downgrade -1" }

# ── Build ──────────────────────────────────────────────────────────────────
function BuildBackend   { _Run "docker build -t once/backend:dev `"$Backend`"" }
function BuildFrontend  { _RunIn $Frontend "npm run build" }
function BuildExtension { _RunIn $Extension "npm run build" }
function BuildAll       { BuildBackend; BuildFrontend; BuildExtension }

# ── Security & coverage ────────────────────────────────────────────────────
function Security {
    try { _RunIn $Backend "bandit -q -r app -x tests" } catch { Write-Warning $_ }
    try { _RunIn $Backend "pip-audit -q" }              catch { Write-Warning $_ }
    try { _RunIn $Frontend "npm audit --audit-level=high" } catch { Write-Warning $_ }
    try { _RunIn $Extension "npm audit --audit-level=high" } catch { Write-Warning $_ }
}
function Coverage { _Run "python `"$Scripts\coverage_report.py`"" }

# ── Observability ──────────────────────────────────────────────────────────
function ObsUp   { _Run "docker compose -f ops/observability/docker-compose.observability.yml up -d" }
function ObsDown { _Run "docker compose -f ops/observability/docker-compose.observability.yml down" }

# ── Realistic seed (L3.2) ──────────────────────────────────────────────────
function SeedRealistic      { _Run "`"$VenvPy`" `"$Backend\scripts\seed_realistic.py`"" }
function SeedResetRealistic { _Run "`"$VenvPy`" `"$Backend\scripts\seed_realistic_reset.py`"" }

# ── Dispatch ───────────────────────────────────────────────────────────────
switch ($Task.ToLower()) {
    "help"             { Help }
    "setup"            { Setup }
    "doctor"           { Doctor }
    "clean"            { Clean }
    "up"               { Up }
    "down"             { Down }
    "logs"             { Logs }
    "ps"               { Ps }
    "shell-db"         { ShellDb }
    "shell-backend"    { ShellBackend }
    "seed"             { Seed }
    "reset"            { Reset }
    "demo"             { Demo }
    "test"             { Test }
    "test-backend"     { TestBackend }
    "test-frontend"    { TestFrontend }
    "test-extension"   { TestExtension }
    "test-verifier"    { TestVerifier }
    "test-integration" { TestIntegration }
    "test-watch"       { TestWatch }
    "lint"             { Lint }
    "fmt"              { Fmt }
    "format"           { Fmt }
    "typecheck"        { Typecheck }
    "migrate"          { Migrate }
    "migrate-new"      { MigrateNew }
    "migrate-down"     { MigrateDown }
    "build-backend"    { BuildBackend }
    "build-frontend"   { BuildFrontend }
    "build-extension"  { BuildExtension }
    "build-all"        { BuildAll }
    "security"         { Security }
    "coverage"         { Coverage }
    "obs-up"           { ObsUp }
    "obs-down"         { ObsDown }
    "seed-realistic"        { SeedRealistic }
    "seed-reset-realistic"  { SeedResetRealistic }
    default {
        Write-Warning "Unknown task: $Task"
        Help
        exit 2
    }
}
