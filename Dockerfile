# FinancialOS backend — production imajı (MA1, Wave-8).
# Multi-stage: builder (wheel derle) → runtime (slim, non-root). Statik SPA'yı nginx sunar (MA2).
#
# GÜVENLİK (Wave-8): non-root user (appuser), secret imaja GİRMEZ (.dockerignore .env hariç tutar),
# gunicorn + uvicorn worker (prod ASGI). Scheduler AYRI servis (SCHEDULER_ENABLED gate, çok-worker cron çift-tetik önlenir).

# ---- builder: bağımlılıkları wheel olarak derle ----
FROM python:3.11-slim AS builder
WORKDIR /build
ENV PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip wheel --wheel-dir=/wheels -r requirements.txt

# ---- runtime: slim + non-root ----
FROM python:3.11-slim AS runtime
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
# curl healthcheck için; libpq5 psycopg2 runtime için (postgres bağlantısı)
# BUG #169: tzdata ZORUNLU — slim imajda zoneinfo verisi yok; TZ=Europe/Istanbul
# ayarlansa bile veri olmadan konteyner UTC'de kalır ve date.today() yanlış gün verir.
RUN apt-get update && apt-get install -y --no-install-recommends curl libpq5 tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 appuser
WORKDIR /app
COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt && rm -rf /wheels
# Yalnız çalışma-zamanı gerekli dosyalar (tests/docs/.env .dockerignore ile zaten hariç)
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY scripts ./scripts
# BUG #191 (P4): hukuki metinler API uzerinden sunulur -> imajda BULUNMALI
COPY docs/legal ./docs/legal
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh && mkdir -p /data && chown -R appuser:appuser /app /data
# Prod'da DATABASE_URL env'den (postgres) verilir; volume /data SQLite fallback (dev/tek-dosya).
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1
ENTRYPOINT ["./docker-entrypoint.sh"]
