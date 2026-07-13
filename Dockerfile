# FinancialOS backend — API-only (statik SPA'yı Caddy sunar).
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY scripts ./scripts
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh && mkdir -p /data
ENV DATABASE_URL=sqlite:////data/financialos.db
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1
ENTRYPOINT ["./docker-entrypoint.sh"]
