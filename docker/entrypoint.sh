#!/bin/sh
set -euo pipefail
cd /app

GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-120}"
GUNICORN_WORKERS="${GUNICORN_WORKERS:-4}"
GUNICORN_LOGLEVEL="${GUNICORN_LOGLEVEL:-info}"
FASTAPI_BIND="${FASTAPI_BIND:-127.0.0.1:9191}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
FRONTEND_HOSTNAME="${FRONTEND_HOSTNAME:-0.0.0.0}"
BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:9191}"

GUNICORN_ARGS="-t ${GUNICORN_TIMEOUT} --workers ${GUNICORN_WORKERS} --bind ${FASTAPI_BIND} --log-level ${GUNICORN_LOGLEVEL}"

if [ "$1" = "start" ]; then
    # Run database migrations
    python -c "from powerdnsadmin.core.config import get_config; get_config()" && \
    alembic -c migrations/alembic.ini upgrade head

    # Start FastAPI backend (internal, not exposed to users)
    gunicorn "powerdnsadmin.app:create_app()" -k uvicorn.workers.UvicornWorker $GUNICORN_ARGS &
    BACKEND_PID=$!

    # Start Next.js frontend (user-facing)
    export BACKEND_URL
    export PORT="${FRONTEND_PORT}"
    export HOSTNAME="${FRONTEND_HOSTNAME}"
    cd /app/frontend
    exec node server.js

elif [ "$1" = "gunicorn" ]; then
    # Legacy: run only the FastAPI backend
    python -c "from powerdnsadmin.core.config import get_config; get_config()" && \
    alembic -c migrations/alembic.ini upgrade head
    exec "$@" $GUNICORN_ARGS

else
    exec "$@"
fi
