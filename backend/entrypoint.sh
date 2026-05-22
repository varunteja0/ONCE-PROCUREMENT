#!/usr/bin/env bash
# Once backend container entrypoint. Single dispatch point for every process
# group on Fly (web / worker / beat) and for docker-compose locally.
#
# Usage:
#   entrypoint.sh             -> api  (default)
#   entrypoint.sh api         -> uvicorn FastAPI app
#   entrypoint.sh worker      -> celery worker (queues: default, submissions, coi)
#   entrypoint.sh beat        -> celery beat scheduler
#   entrypoint.sh migrate     -> alembic upgrade head (one-shot, for compose)
#   entrypoint.sh shell       -> drop into bash for debugging
#   entrypoint.sh <unknown>   -> exits non-zero
#
# Schema migrations on Fly run via [deploy].release_command = "alembic upgrade head".

set -euo pipefail

CMD="${1:-api}"
shift || true

case "${CMD}" in
    api)
        echo "[entrypoint] starting uvicorn (port=${PORT:-8000}, workers=${WEB_CONCURRENCY:-2})"
        exec uvicorn app.main:app \
            --host 0.0.0.0 \
            --port "${PORT:-8000}" \
            --workers "${WEB_CONCURRENCY:-2}" \
            --proxy-headers \
            --forwarded-allow-ips='*'
        ;;
    worker)
        echo "[entrypoint] starting Celery worker (concurrency=${WORKER_CONCURRENCY:-4})"
        exec celery -A app.workers.celery_app worker \
            -l info \
            -Q default,submissions,coi \
            --concurrency="${WORKER_CONCURRENCY:-4}"
        ;;
    beat)
        echo "[entrypoint] starting Celery beat"
        exec celery -A app.workers.celery_app beat \
            -l info \
            --schedule /tmp/celerybeat-schedule
        ;;
    migrate)
        echo "[entrypoint] running alembic upgrade head"
        exec alembic upgrade head
        ;;
    shell)
        exec /bin/bash
        ;;
    *)
        echo "[entrypoint] ERROR: unknown command '${CMD}'" >&2
        echo "[entrypoint] valid commands: api | worker | beat | migrate | shell" >&2
        exit 1
        ;;
esac
