# Observability

Once produces **logs** and **metrics** today. Distributed traces are deferred
(Sentry performance traces are available when `SENTRY_DSN` is set; OpenTelemetry
wiring is on the roadmap).

## Logs

All services use [structlog](https://www.structlog.org/) with a JSON renderer
outside development. Every log line includes:

| Field        | Source |
|--------------|--------|
| `timestamp`  | ISO-8601 UTC |
| `level`      | log level |
| `service`    | `api` / `worker` / `beat` (set via `ONCE_SERVICE` env) |
| `request_id` | bound from the `RequestIDMiddleware` contextvar |
| `tenant_id`  | bound from `TenantScopeMiddleware` when authenticated |
| `user_id`    | bound from `TenantScopeMiddleware` when authenticated |
| `message`    | structured event name |

A canonical access log line (`event=http_access`) is emitted exactly once per
HTTP request by `app.middleware.access_log.AccessLogMiddleware`, skipping
`/v1/health/live` and `/metrics` to avoid scrape noise.

### Request ID

Every request gets an `X-Request-ID` header (UUID4 if the client did not
provide one). The same id is:

1. Set on `request.state.request_id`.
2. Stored in a contextvar so structlog auto-binds it everywhere.
3. Echoed back to the client in the response header.

To find a request end-to-end:

1. Grab `X-Request-ID` from the response.
2. Open Grafana → Explore → Loki.
3. Query: `{service="api"} | json | request_id="<id>"`.

The provisioned **Once — API** dashboard has a `request_id` textbox variable
that filters its bottom log panel for you.

## Metrics

The backend exposes Prometheus metrics at `GET /metrics`.

- **Gated** by `METRICS_ENABLED` (default `true`).
- **Token-protected** when `METRICS_TOKEN` is set — production deployments MUST
  set this. Prometheus must send `Authorization: Bearer <token>`.
- Default Process + Platform collectors are enabled (process CPU, RSS, FDs,
  Python GC stats).

### Metric inventory

| Name                             | Type      | Labels                          | Source |
|----------------------------------|-----------|---------------------------------|--------|
| `http_requests_total`            | counter   | `method`, `route`, `status`     | TimingMiddleware |
| `http_request_duration_seconds`  | histogram | `method`, `route`               | TimingMiddleware |
| `db_pool_size`                   | gauge     | —                               | sampled at `/metrics` scrape |
| `db_pool_in_use`                 | gauge     | —                               | sampled at `/metrics` scrape |
| `celery_tasks_total`             | counter   | `queue`, `task`, `state`        | Celery signals |
| `celery_task_duration_seconds`   | histogram | `queue`, `task`                 | Celery signals |
| `submissions_total`              | counter   | `portal`, `status`              | submission pipeline |
| `submissions_in_flight`          | gauge     | `portal`                        | submission pipeline |
| `submission_duration_seconds`    | histogram | `portal`                        | submission pipeline |
| `receipts_signed_total`          | counter   | `key_id`                        | receipt signer |
| `auth_logins_total`              | counter   | `result`                        | auth service |
| `csrf_failures_total`            | counter   | —                               | CSRF middleware |

**Cardinality discipline**: `route` is the FastAPI route template
(`/v1/suppliers/{supplier_id}`), never the resolved path. Labels never carry
unbounded values (`user_id`, `tenant_id`, `supplier_id`, arbitrary input).

## SLOs to track

| Service     | SLI                         | SLO                |
|-------------|-----------------------------|--------------------|
| API         | p95 request latency         | < 300 ms (30 days) |
| API         | 5xx error ratio             | < 0.5 %            |
| Submissions | p95 portal submission       | < 30 s             |
| Submissions | success rate per portal     | > 99 %             |

## Alert rules (commented out until prod)

```yaml
# ops/observability/prometheus/rules/once-api.rules.yml
groups:
  - name: once-api
    rules:
      - alert: APIHighLatencyP95
        expr: histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[5m]))) > 0.3
        for: 10m
        labels: {severity: warning}
        annotations:
          summary: "API p95 latency > 300ms"
      - alert: APIElevated5xx
        expr: sum(rate(http_requests_total{status=~"5.."}[5m])) / clamp_min(sum(rate(http_requests_total[5m])), 1e-9) > 0.005
        for: 10m
        labels: {severity: critical}
        annotations:
          summary: "API 5xx error ratio > 0.5%"
      - alert: SubmissionsP95Slow
        expr: histogram_quantile(0.95, sum by (le, portal) (rate(submission_duration_seconds_bucket[15m]))) > 30
        for: 15m
        labels: {severity: warning}
        annotations:
          summary: "Submission p95 > 30s on {{ $labels.portal }}"
```

Enable by uncommenting `rule_files` in `ops/observability/prometheus/prometheus.yml`
and dropping the file at `ops/observability/prometheus/rules/once-api.rules.yml`.

## Spinning up the local stack

```sh
docker compose \
  -f docker-compose.yml \
  -f ops/observability/docker-compose.observability.yml \
  --profile observability up -d
open http://localhost:3000   # Grafana — admin / admin
```

See `ops/observability/README.md` for details.

## Future work

- Browser-extension metrics (events, pre-fill success, time saved). The
  `once-extension` Grafana dashboard is a placeholder.
- OpenTelemetry traces exported to Tempo + linked from Loki / Grafana.
- Alertmanager + on-call rotation wiring.
