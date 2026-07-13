#!/bin/sh
# Prod başlatma: önce şema (alembic), sonra uvicorn (--reload YOK → APScheduler cron
# tek-process'te düzgün çalışır; M4 cron production sorununun kök çözümü).
set -e
echo "[entrypoint] alembic upgrade head…"
python -m alembic upgrade head
echo "[entrypoint] uvicorn başlıyor (daemon, reload yok)…"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-server-header
