#!/bin/sh
# FinancialOS — production deploy/güncelleme (MA4, Wave-8). Canlı sunucuda çalışır.
# Akış: git pull → build → up (backend entrypoint alembic migrate eder) → healthcheck.
# Başarısızlıkta OTOMATİK ROLLBACK (önceki commit'e döner + yeniden build).
#
# İlk kurulum DEĞİL (o docs/deployment/runbook.md). Bu, çalışan bir deploy'u GÜNCELLER.
set -e

COMPOSE="docker compose -f docker-compose.prod.yml --env-file .env.prod"
PREV_COMMIT=$(git rev-parse HEAD)

rollback() {
    echo "[deploy] ❌ HATA — rollback: $PREV_COMMIT'e dönülüyor…"
    git reset --hard "$PREV_COMMIT"
    $COMPOSE up -d --build
    echo "[deploy] rollback tamam (önceki sürüm canlı)."
    exit 1
}
trap rollback INT TERM

echo "[deploy] 1) .env.prod var mı?"
[ -f .env.prod ] || { echo "HATA: .env.prod yok (cp .env.prod.example .env.prod + gerçek secret)"; exit 1; }

echo "[deploy] 2) git pull…"
git pull --ff-only origin main || { echo "HATA: git pull (temiz çalışma dizini gerekli)"; exit 1; }

echo "[deploy] 3) imajları build + up (backend entrypoint alembic upgrade head eder)…"
if ! $COMPOSE up -d --build; then rollback; fi

echo "[deploy] 4) healthcheck (backend /api/ready (DB + sema), 60s içinde 200)…"
i=0
until $COMPOSE exec -T backend curl -fsS http://localhost:8000/api/ready >/dev/null 2>&1; do
    i=$((i+1))
    [ "$i" -ge 30 ] && { echo "[deploy] healthcheck 60s'de geçmedi"; rollback; }
    sleep 2
done

echo "[deploy] 5) scheduler servisi ayakta mı (cron 7/24)?"
# BUG #230 (D12): burası eskiden yalnız "UYARI" basıp çıkış kodu 0 ile devam ediyordu.
# Scheduler ölüyken deploy "TAMAM" diyordu ve kullanıcı BAYAT fiyatlarla hesaplanmış net
# değere göre para kararı veriyordu — sessiz arıza. Ayrıca "restarting" durumu eski
# `Up|running` grep'iyle EŞLEŞMİYOR, yani crash-loop bile fark edilmiyordu.
DURUM=$($COMPOSE ps scheduler 2>/dev/null || true)
if ! echo "$DURUM" | grep -qE "Up|running"; then
    echo "[deploy] scheduler AYAKTA DEĞİL — fiyat/gece batch cron'ları koşmaz:"
    echo "$DURUM"
    rollback
fi
echo "$DURUM" | grep -qi "restarting" && { echo "[deploy] scheduler crash-loop'ta"; rollback; }

echo "[deploy] 6) otomatik yedek servisi ayakta mı (D13)?"
YEDEK=$($COMPOSE ps backup 2>/dev/null || true)
echo "$YEDEK" | grep -qE "Up|running" || echo "[deploy] UYARI: yedek servisi çalışmıyor — otomatik kopya ALINMIYOR"

echo "[deploy] ✅ TAMAM — $(git rev-parse --short HEAD) canlı. Web: https://<DOMAIN>"
trap - INT TERM
