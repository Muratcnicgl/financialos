#!/bin/sh
# FinancialOS production entrypoint (MA1, Wave-8).
# SERVICE_MODE:
#   web       (default) → alembic upgrade head + gunicorn (uvicorn worker'ları). Scheduler KAPALI.
#   scheduler           → yalnız APScheduler daemon (migrate YOK; web servisi migrate eder). Scheduler AÇIK.
# Böylece çok-worker'lı web'de cron çift-tetiklenmez; tek scheduler servisi 7/24 fiyat/batch koşar (MA4).
set -e

MODE="${SERVICE_MODE:-web}"

if [ "$MODE" = "scheduler" ]; then
    echo "[entrypoint] SERVICE_MODE=scheduler → yalnız APScheduler daemon (SCHEDULER_ENABLED=true)."
    export SCHEDULER_ENABLED=true
    # Web açmadan sadece lifespan'ı çalıştıracak minimal ASGI process (tek worker, scheduler lifespan'da başlar).
    exec uvicorn app.main:app --host 127.0.0.1 --port 8001 --no-server-header --workers 1
fi

# web modu: şema migrate (tek sefer) + gunicorn. Scheduler bu process'lerde KAPALI (ayrı servis koşar).
export SCHEDULER_ENABLED=false
echo "[entrypoint] alembic upgrade head…"
python -m alembic upgrade head
echo "[entrypoint] gunicorn başlıyor (uvicorn worker, WEB_CONCURRENCY=${WEB_CONCURRENCY:-2})…"
exec gunicorn app.main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers "${WEB_CONCURRENCY:-2}" \
    --bind 0.0.0.0:8000 \
    --timeout 60 \
    --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-*}" \
    --access-logfile - --error-logfile -
