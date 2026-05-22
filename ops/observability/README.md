# Once — Observability stack

Optional Prometheus + Loki + Promtail + Grafana stack for local development.

## Bring it up

```sh
docker compose \
  -f docker-compose.yml \
  -f ops/observability/docker-compose.observability.yml \
  --profile observability \
  up -d
```

Vanilla `docker compose up` is **unaffected** — services in this overlay only
activate when the `observability` profile is selected.

## URLs

| Service    | URL                          | Default credentials |
|------------|------------------------------|---------------------|
| Grafana    | http://localhost:3000        | admin / admin (change before sharing) |
| Prometheus | http://localhost:9090        | — |
| Loki       | http://localhost:3100/ready  | — |

> Change the Grafana password **immediately** in any shared environment. Set
> `GRAFANA_ADMIN_PASSWORD` in your `.env` to override the default.

## Provisioned dashboards

- **Once — API** (`once-api`): request rate, latency p50/p95/p99, 5xx rate,
  top endpoints by latency, log panel filtered by `request_id`.
- **Once — Submissions** (`once-submissions`): submission rate by portal,
  success rate, queue depth, time-to-completion histogram, blocked count.
- **Once — Extension** (`once-extension`): placeholder. The browser extension
  does not yet emit metrics — see future work in `docs/OBSERVABILITY.md`.

## Securing `/metrics`

In production, set `METRICS_TOKEN` in the backend env and uncomment the
`authorization` block in `prometheus/prometheus.yml`. Without a token the
endpoint is open (intended for local development only).
