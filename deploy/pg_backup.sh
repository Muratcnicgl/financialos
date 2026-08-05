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

echo "[yedek] $ZAMAN — pg_dump başlıyor (host=$PGHOST db=$PGDATABASE)"
if ! pg_dump -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" --no-owner --no-privileges \
     | gzip -c > "$GECICI"; then
    rm -f "$GECICI"
    echo "[yedek] HATA: pg_dump başarısız — YEDEK ALINAMADI" >&2
    exit 1
fi

BOYUT="$(wc -c < "$GECICI" | tr -d ' ')"
if [ "$BOYUT" -lt "$MIN_BYTES" ]; then
    rm -f "$GECICI"
    echo "[yedek] HATA: dump şüpheli küçük ($BOYUT bayt < $MIN_BYTES) — REDDEDİLDİ" >&2
    exit 2
fi

# gzip bütünlüğü: bozuk arşiv geri yüklenemez, ama dosya olarak "var" görünür.
if ! gzip -t "$GECICI"; then
    rm -f "$GECICI"
    echo "[yedek] HATA: arşiv bozuk (gzip -t) — REDDEDİLDİ" >&2
    exit 3
fi

mv "$GECICI" "$HEDEF"
echo "[yedek] TAMAM: $HEDEF ($BOYUT bayt)"

# Rotasyon — dolu disk yeni yedeği de engeller.
if [ "$KEEP_DAYS" -gt 0 ]; then
    SILINEN="$(find "$BACKUP_DIR" -name 'financialos-*.sql.gz' -type f -mtime "+$KEEP_DAYS" -print -delete | wc -l | tr -d ' ')"
    echo "[yedek] rotasyon: $KEEP_DAYS günden eski $SILINEN dosya silindi"
fi

# Yarım kalmış geçici dosyalar (önceki çöken koşumlar) birikmesin.
find "$BACKUP_DIR" -name '.yedek-*.tmp' -type f -mtime +1 -delete 2>/dev/null || true
