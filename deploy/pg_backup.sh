#!/bin/sh
# FinancialOS — PostgreSQL otomatik yedek (BUG #230 / denetim D13+D09).
#
# Neden: beta kullanıcılarının TÜM finansal geçmişi tek bir Docker volume'unda ve tek bir
# Free-Tier VM'de duruyordu; hiçbir otomatik kopyası yoktu. Depodaki tek yedek otomasyonu
# SQLite-only `scripts/backup.py`'yi çağırıyor ve Postgres URL'inde çıkış kodu 1 ile
# ölüyordu — operatör "timer kurdum" sanarken her gece sessizce başarısız oluyordu.
#
# Tasarım kararları:
# - `set -e` + `pg_dump | gzip` yerine ÖNCE dosyaya, SONRA doğrula: yarım/boş bir dump
#   "yedeğim var" yanılsaması üretir; en tehlikeli yedek, geri yüklenemeyeceğini
#   bilmediğin yedektir.
# - Geçici dosyaya yaz, doğrulandıktan SONRA adını koy (yarım dosya asla geçerli görünmez).
# - Rotasyon: KEEP_DAYS'ten eski dosyalar silinir — dolan disk YENİ yedeği de engeller.
# - Çıkış kodu anlamlıdır: 0 = doğrulanmış yedek, ≠0 = yedek YOK (çağıran log'a düşürür).
# - BUG #240 (D24 sınıf taraması): her koşum `scheduler_runs`'a yazar. Çıkış kodu yalnız
#   konteyner log'una düşüyordu; yedek haftalarca sessizce başarısız olsa operatör bunu
#   ancak log okuyarak görebilirdi — oysa yedek, beta verisinin TEK kopyası.
#   `/api/ops/scheduler` bu kaydı okur (app/scheduler.py `DIS_PLANLI_ISLER`).
#
# Kullanım (compose `backup` servisi 24 saatte bir çağırır; elle de koşulabilir):
#   PGPASSWORD=... PGHOST=db PGUSER=financialos PGDATABASE=financialos \
#   KEEP_DAYS=30 BACKUP_DIR=/backups sh deploy/pg_backup.sh
set -eu

PGHOST="${PGHOST:-db}"
PGUSER="${PGUSER:-financialos}"
PGDATABASE="${PGDATABASE:-financialos}"
BACKUP_DIR="${BACKUP_DIR:-/backups}"
KEEP_DAYS="${KEEP_DAYS:-30}"
# Yedeğin geçerli sayılması için asgari boyut (bayt). Boş/başarısız dump birkaç yüz bayt
# başlık üretebilir; şema-dolu bir FinancialOS dump'ı bunun çok üstündedir.
MIN_BYTES="${MIN_BYTES:-2048}"

mkdir -p "$BACKUP_DIR"
ZAMAN="$(date +%F-%H%M)"
GECICI="$BACKUP_DIR/.yedek-$ZAMAN.sql.gz.tmp"
HEDEF="$BACKUP_DIR/financialos-$ZAMAN.sql.gz"

# BUG #240: çalışma kaydı. İzleme yedeği ASLA düşürmez (hata yutulur, yalnız uyarı).
# Detay yalnız sabit metin + sayı içerir — PII yok (scheduler_runs.detail sözleşmesi).
kayit() {   # $1 = true|false, $2 = detay
    psql -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" -q -t \
         -c "INSERT INTO scheduler_runs (job_name, started_at, finished_at, ok, detail)
             VALUES ('pg_backup', (now() at time zone 'utc'), (now() at time zone 'utc'), $1, '$2');" \
         >/dev/null 2>&1 \
      || echo "[yedek] uyarı: çalışma kaydı yazılamadı (yedeğin kendisi etkilenmedi)" >&2
}

hata_cik() {   # $1 = çıkış kodu, $2 = kayda düşecek kısa sebep
    kayit false "$2"
    echo "[yedek] HATA: $2 — YEDEK ALINAMADI" >&2
    exit "$1"
}

echo "[yedek] $ZAMAN — pg_dump başlıyor (host=$PGHOST db=$PGDATABASE)"
if ! pg_dump -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" --no-owner --no-privileges \
     | gzip -c > "$GECICI"; then
    rm -f "$GECICI"
    hata_cik 1 "pg_dump basarisiz"
fi

BOYUT="$(wc -c < "$GECICI" | tr -d ' ')"
if [ "$BOYUT" -lt "$MIN_BYTES" ]; then
    rm -f "$GECICI"
    hata_cik 2 "dump supheli kucuk ($BOYUT bayt < $MIN_BYTES) - REDDEDILDI"
fi

# gzip bütünlüğü: bozuk arşiv geri yüklenemez, ama dosya olarak "var" görünür.
if ! gzip -t "$GECICI"; then
    rm -f "$GECICI"
    hata_cik 3 "arsiv bozuk (gzip -t) - REDDEDILDI"
fi

mv "$GECICI" "$HEDEF"
echo "[yedek] TAMAM: $HEDEF ($BOYUT bayt)"
kayit true "$BOYUT bayt dogrulanmis yedek"

# Rotasyon — dolu disk yeni yedeği de engeller.
if [ "$KEEP_DAYS" -gt 0 ]; then
    SILINEN="$(find "$BACKUP_DIR" -name 'financialos-*.sql.gz' -type f -mtime "+$KEEP_DAYS" -print -delete | wc -l | tr -d ' ')"
    echo "[yedek] rotasyon: $KEEP_DAYS günden eski $SILINEN dosya silindi"
fi

# Yarım kalmış geçici dosyalar (önceki çöken koşumlar) birikmesin.
find "$BACKUP_DIR" -name '.yedek-*.tmp' -type f -mtime +1 -delete 2>/dev/null || true
