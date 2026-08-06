# FinancialOS — Production Deploy Runbook (MA4, Wave-8)

Sıfırdan bir Linux sunucuda canlıya alma. Blok B'de (Murat sunucu kararı sonrası) adım adım çalıştırılır.
**Sunucu:** Oracle Cloud Free Tier (kalıcı ücretsiz VM) VEYA Hetzner ~€4/ay. Min: 1 vCPU / 1GB RAM / 20GB disk.

## Ön-koşullar (bir kez)
1. **Domain (önerilir):** bir alan adının A kaydını sunucu IP'sine yönlendir (Let's Encrypt için). IP-only da mümkün ama HTTPS zor.
2. **Portlar:** sunucu firewall'unda **80 + 443** açık (SSH 22 zaten). DB portu (5432) **AÇMA** (compose iç ağda).

## Kurulum adımları
```sh
# 1) OS + Docker (Ubuntu/Debian örneği)
sudo apt-get update && sudo apt-get install -y git
curl -fsSL https://get.docker.com | sudo sh          # Docker Engine + compose plugin
sudo usermod -aG docker $USER && newgrp docker        # docker'ı sudo'suz kullan

# 2) Repo
git clone https://github.com/Muratcnicgl/financialos.git && cd financialos

# 3) Production secret'ları (GERÇEK değerler — git'e/chat'e DÜŞMEZ)
cp .env.prod.example .env.prod
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # SECRET_KEY üret
nano .env.prod   # SECRET_KEY, POSTGRES_PASSWORD, DOMAIN, LLM key(ler) doldur — placeholder BIRAKMA (fail-fast reddeder)

# 4) TLS sertifikası (Let's Encrypt) — chicken-egg bootstrap (bir kez)
export DOMAIN=$(grep '^DOMAIN=' .env.prod | cut -d= -f2)
export EMAIL=seninmail@example.com
sh deploy/init-letsencrypt.sh          # dummy cert → nginx → gerçek cert → reload

# 5) Tüm stack'i ayağa kaldır
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

## Doğrulama (canlı-gate)
```sh
docker compose -f docker-compose.prod.yml ps          # db/backend/scheduler/web/certbot = Up
curl -fsS https://$DOMAIN/api/ready                     # {"hazir":true,"db":"ok","sema":"guncel"}
# NOT (BUG #247): /api/health CANLILIK olcer (surec ayakta mi) ve DB cokmusken de 200 doner.
# Dogrulamada /api/ready kullan: DB'ye SELECT 1 atar + sema surumunu kod ile karsilastirir,
# sorunluysa 503. HEALTHCHECK ve deploy.sh rollback kapisi da bu ucu okur.
# Tarayıcı: https://$DOMAIN → login → gerçek işlem gir → cockpit güncellendi (KULLANIM-GATE)
```
- **Scheduler (cron 7/24):** `scheduler` servisi sürekli çalışır → fiyat cron 02:45, batch 03:00 vb. **PC-kapalı sorunu ÇÖZÜLDÜ**
  (Wave-4 M4'ün prod-daemon gerekçesi, ADR-035). 24 saat sonra: `docker compose logs scheduler | grep price` → fiyat yazıldı mı.
- **RLS aktif (BUG #238 / D22):** burada eskiden "app `financialos` NON-superuser rolüyle bağlanır"
  yazıyordu — **yanlıştı**: `financialos` postgres imajının `POSTGRES_USER`'ı, yani bootstrap
  SUPERUSER'ı ve superuser `FORCE ROW LEVEL SECURITY`'ye rağmen RLS'i bypass eder; beyan edilen
  2. savunma fiilen yoktu. Artık uygulama `fos_app` (NOSUPERUSER/NOBYPASSRLS) rolüyle bağlanır,
  rolü entrypoint her deploy'da idempotent kurar, şemayı yalnız `MIGRATION_DATABASE_URL` (sahip
  rolü) değiştirir. **Kanıtla** (iddiaya güvenme):
  ```sh
  docker compose -f docker-compose.prod.yml exec -T backend python -c \
    "from app.settings import database_role_problems as p; print(p() or 'RLS rolu TAMAM')"
  ```
  Uygulama zaten superuser bağlantısıyla **açılmaz** (startup fail-fast, `validate_security_config`).

## Güncelleme (yeni sürüm)
```sh
sh scripts/deploy.sh     # git pull → build → migrate → up → healthcheck (başarısızsa OTOMATİK ROLLBACK)
```

## Yedekleme

**OTOMATİK (BUG #230 / D13):** compose yığınındaki `backup` servisi 24 saatte bir
`deploy/pg_backup.sh` koşar: `pg_dump | gzip` → **boyut + gzip bütünlüğü doğrulanır** →
adlandırılmış `pg-backups` hacmine yazılır → `BACKUP_KEEP_DAYS` (varsayılan 30) günden
eskiler silinir. Doğrulamayı geçmeyen dump SİLİNİR (yarım dosya "yedeğim var" yanılsaması
üretmesin). Ayrı bir cron/timer kurmana gerek yok.

```sh
# Yedekleri listele (en yenisi üstte)
docker compose -f docker-compose.prod.yml exec -T backup ls -lt /backups

# Yedek servisinin son koşumu ne dedi
docker compose -f docker-compose.prod.yml logs --tail=20 backup

# Hemen bir yedek al (beklemeden — ör. migration öncesi)
docker compose -f docker-compose.prod.yml exec -T backup sh /usr/local/bin/pg_backup.sh

# Yedeği host'a kopyala (VM ölürse volume de ölür — DIŞARI kopyala!)
docker compose -f docker-compose.prod.yml cp backup:/backups ./yedekler
```

> ⚠️ **Tek VM = tek nokta.** Otomatik yedek volume kaybına karşı korumaz. Haftada bir
> `cp` ile dışarı (kendi bilgisayarın / başka bir sağlayıcı) al.

```sh
# Elle dump (tek seferlik, ham .sql)
docker compose -f docker-compose.prod.yml exec -T db pg_dump -U financialos financialos > backup-$(date +%F).sql
```

### Yedeği DOĞRULA (almak yetmez)
```sh
test -s backup-$(date +%F).sql || echo "UYARI: dump BOŞ — yedek YOK sayılır"
grep -c "CREATE TABLE" backup-$(date +%F).sql     # tablo sayısı beklenenle uyuşmalı (28 — `alembic upgrade head` sonrası)
tail -1 backup-$(date +%F).sql                    # "PostgreSQL database dump complete" görmelisin
```

## Geri yükleme (P5 / H14 — provası yapılmış yol)
> **Kural: geri yüklenebildiği kanıtlanmamış yedek, yedek değildir.** Bu akış
> `tests/test_postgres_restore_drill.py` ile otomatik prova edilir (dump → veritabanını
> düşür → geri yükle → veri birebir aynı mı). Felaket anında ilk kez denemeyin.

```sh
# 1) Yazma trafiğini durdur (veri tutarlılığı) — web + cron
docker compose -f docker-compose.prod.yml stop backend scheduler

# 2) MEVCUT durumun emniyet kopyası (yanlış yedeği yüklersen geri dönebilesin)
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U financialos financialos > pre-restore-$(date +%F-%H%M).sql

# 3) Temiz veritabanı + geri yükleme (ON_ERROR_STOP: sessiz yarım yükleme YOK)
docker compose -f docker-compose.prod.yml exec -T db \
  psql -U financialos -d postgres -c 'DROP DATABASE financialos WITH (FORCE)'
docker compose -f docker-compose.prod.yml exec -T db \
  psql -U financialos -d postgres -c 'CREATE DATABASE financialos'
cat backup-YYYY-MM-DD.sql | docker compose -f docker-compose.prod.yml \
  exec -T db psql -U financialos -d financialos -v ON_ERROR_STOP=1

# 4) Servisleri başlat + DOĞRULA (sessiz başarı sayılmaz)
docker compose -f docker-compose.prod.yml start backend scheduler
curl -fsS https://$DOMAIN/api/ready       # 503 ise sema/DB sorunu var (BUG #247)
docker compose -f docker-compose.prod.yml exec -T db \
  psql -U financialos -d financialos -c 'SELECT COUNT(*) FROM users;'
docker compose -f docker-compose.prod.yml exec -T db \
  psql -U financialos -d financialos -c 'SELECT version_num FROM alembic_version;'
```
Alembic sürümü imajın beklediğinden **eskiyse** `docker compose exec backend python -m alembic
upgrade head` çalıştırın (yedek eski şemadan gelmiş olabilir).

**Dev/SQLite kurulumda:** `python -m scripts.restore --list` → `--verify <dosya>` →
`--from <dosya> --confirm` (onaysız hiçbir şey yazılmaz, bozuk yedek reddedilir, geri
yüklemeden önce mevcut DB'nin kopyası alınır).

## Canlı doğrulama (P6 — deploy sonrası ZORUNLU)
```sh
# Tek komut: saglik, HTTPS/HSTS/CSP, kimlik zorunlulugu, /docs kapali, KVKK metinleri,
# PWA, brute-force limiti + (kimlik verilirse) giris/cockpit/koc kotasi.
python scripts/live_gate.py https://$DOMAIN
python scripts/live_gate.py https://$DOMAIN --email <e-posta> --password '<parola>'
```
Cikis kodu 0 degilse **kapali beta ACILMAZ**. Parola yalnizca parametredir; script
hicbir yere yazmaz (test ile kilitli: tests/test_live_gate_script.py).
**24 saat sonra tekrar kos** — cron/fiyat tazeligi kapisi ancak bir gece gectikten
sonra anlamlidir (P6.3).

## Kapasite sınırları (P5)
Havuz **process başınadır**; toplam bağlantı şu formülle hesaplanır:

    WEB_CONCURRENCY × (DB_POOL_SIZE + DB_MAX_OVERFLOW) + scheduler(1 process)

Varsayılan: `2 × (5 + 10) + 15 = 45` < Postgres `max_connections` (100) → güvenli.
`WEB_CONCURRENCY`'yi yükseltirsen havuzu da küçült; aksi halde yük altında
**"too many connections"** alırsın (ve bunu ancak canlıda görürsün).
Küçük VM'de (Oracle Free 1GB) önerilen: `WEB_CONCURRENCY=2`, `DB_POOL_SIZE=3`, `DB_MAX_OVERFLOW=5`.

Kontrol:
```sh
docker compose -f docker-compose.prod.yml exec -T db   psql -U financialos -d financialos -c "SHOW max_connections;"
docker compose -f docker-compose.prod.yml exec -T db   psql -U financialos -d financialos -c "SELECT count(*) FROM pg_stat_activity;"
```

## Süit ↔ canlı veri izolasyonu (yılda bir / şüphelenince)

Canlı DB'nin `error_logs` tablosunda test kalıntıları bulundu (tarihsel: BUG #078 + #235).
"Artık dokunmuyor" bir İDDİA'dır; ölç:

```sh
.env\Scripts\python.exe -m scripts.suite_db_izolasyon_kontrolu
```

Canlı DB'nin KOPYASINI alır, süiti o kopyaya karşı koşturur, öncesi/sonrası tüm tabloların
satır sayılarını karşılaştırır. Tek satır bile değişirse çıkış kodu 1 ve hangi tablo olduğu
yazılır. (6 Ağu 2026 ölçümü: **TEMİZ** — 2040 test, 0 satır.)

## Beta işletimi (P7)

> **BUG #249 (D40): bu komutlar konteyner İÇİNDE koşar.** Host kabuğunda `DATABASE_URL`
> tanımlı değildir; `python -m scripts.beta_invite` orada çalıştırılırsa davet kodu **yanlış
> veritabanına** (yerel SQLite dosyası) yazılır ve davetli canlıda 403 alır — komut ise
> "davet üretildi" der. `exec -T backend` öneki, komutu prod veritabanını gören süreçte koşturur.

```sh
# Davet kodu uret (kapali beta) — --email VER (asagidaki nota bak)
docker compose -f docker-compose.prod.yml exec -T backend python -m scripts.beta_invite --email <davetli> --note "<kim>"
docker compose -f docker-compose.prod.yml exec -T backend python -m scripts.beta_invite --list

# GERI BILDIRIM + SISTEM HATASI TRIYAJI — gunluk bak
docker compose -f docker-compose.prod.yml exec -T backend python -m scripts.beta_triage      # acik geri bildirimler + son 7 gun hatalar
docker compose -f docker-compose.prod.yml exec -T backend python -m scripts.beta_triage --kapat <ID> --not "duzeltildi: BUG #NNN"

# Cron sagligi (gece islerinin gercekten kostugu) — TEK BAKILACAK ALAN: sorunlu_isler
curl -fsS -H "Authorization: Bearer <token>" https://$DOMAIN/api/ops/scheduler \
  | python -c "import json,sys; d=json.load(sys.stdin); print('SORUNLU:', d['sorunlu_isler'] or 'yok')"
```
**BUG #240 (D24):** uc artik **planli her isi** listeler (koşmamiş olsa bile) — bes cron
(`fetch_investment_prices`, `nightly_batch`, `k2_batch`, `nightly_trace_cleanup`,
`weekly_smoke_test`) + compose yedegi (`pg_backup`). Alanlar: `hic_calismadi` (planli ama
bir kez bile kosmamis = olu), `gecikti` (son kosum beklenen periyodun 1.5 katindan eski),
`son_sonuc=false` (kostu, patladi). `sorunlu_isler` bu ucunun birlesimidir — **bos degilse
mudahale et.** `nightly_trace_cleanup` detayinda silinen satir sayisi yazar: KVKK'da soz
verilen 90-gun saklama boylece sayiyla dogrulanir (log okumak kanit degildir).
Kullanici e-postalari triyaj ciktisinda MASKELIDIR (gizlilik); kimlik gerekiyorsa user_id ile bak.

⚠️ **Daveti HER ZAMAN `--email` ile ac (BUG #226 / D05).** Kapali betada iki kayit yolu var:
kod ile `/register` ve Google/GitHub ile OAuth. OAuth akisinda kod girilecek alan YOKTUR —
kapi davetin e-postasiyla eslesir. E-postasiz (yalniz-kod) davet OAuth girisini ACMAZ; davetli
"kapali betada, davetli listesinde degilsin" hatasi alir. Davetliye once sagliyici hesabinin
adresini sor, daveti o adrese ac. Mevcut kullanicilarin girisi davetten etkilenmez (davet
KAYIT kapisidir, giris kapisi degil).

### Kullanim metrikleri — haftada bir bak (BUG #214)

Triyaj yalniz **sikayet edeni** gosterir. Beta'nin en olasi basarisizligi gurultulu cokus
degil **sessiz terk**tir: davet edilir, kayit olur, ilk ekranda takilir, kimse sikayet etmez,
panelde her sey yesil gorunur. Onu bu arac gorunur kilar:

```sh
docker compose -f docker-compose.prod.yml exec -T backend python -m scripts.beta_metrics   # son 30 gun
docker compose -f docker-compose.prod.yml exec -T backend python -m scripts.beta_metrics --gun 7
docker compose -f docker-compose.prod.yml exec -T backend python -m scripts.beta_metrics --json   # cron/izleme icin
```

Ciktida **yalniz sayi/oran** vardir — e-posta, isim, serbest metin ve para tutari bu araçtan
CIKMAZ (testle kilitli). Dis analitik servisi YOKTUR; sorgular kendi DB'mize gider.

**Neye bakilir:**
- `hic iz birakmayan` yuksekse (>%40) sorun onboarding'dedir, ozellikte degil.
- `hesap ekleyen` << `kayitli` ise ilk kurulum adimi kiriliyor demektir.
- `yalniz ilk gun` >> `baska bir gun donen` ise urun merak uyandiriyor ama tutmuyor.
- `koc hata orani` %10'u asiyorsa saglayici/kota tarafina bak (`beta_triage` hata gruplari).

## Sorun giderme
- **nginx başlamıyor:** TLS cert yok → `deploy/init-letsencrypt.sh` koşuldu mu? Logs: `docker compose logs web`.
- **backend başlamıyor:** `.env.prod` SECRET_KEY placeholder/boş mu? Fail-fast reddeder → gerçek değer koy. Logs: `docker compose logs backend`.
- **fiyat güncellenmiyor:** `docker compose ps scheduler` Up mı? `docker compose logs scheduler`.
- **DB bağlanamıyor:** `db` healthy mi? `docker compose ps db`. POSTGRES_PASSWORD .env.prod ile compose DATABASE_URL eşleşiyor mu.

## Geri alma (P9 — provası yapılmış yol)
> **Kod'u geri almak yetmez: ŞEMA da geri alınmalı.** Kötü sürüm canlıya çıktığında şema
> zaten ilerlemiştir; eski kod yeni şemayla açılmaya çalışır. Bu akış
> `tests/test_rollback_drill.py` ile prova edilir (head → veri → 1/3 sürüm geri → veri
> bozulmadı mı → tekrar head).

```sh
# 0) ONCE YEDEK (geri almanin kendisi de riskli bir islemdir)
docker compose -f docker-compose.prod.yml exec -T db   pg_dump -U financialos financialos > pre-rollback-$(date +%F-%H%M).sql

# 1) Yazma trafigini durdur
docker compose -f docker-compose.prod.yml stop backend scheduler

# 2) SEMAYI geri al — kac surum geri gidilecegi, hatali surumun kac migration
#    getirdigine baglidir (git log ile bak: alembic/versions/ altinda kac yeni dosya var).
docker compose -f docker-compose.prod.yml run --rm backend   python -m alembic downgrade -1        # veya -2 / -3 …

# 3) KODU geri al + ayaga kaldir
git reset --hard <önceki-tag>   # ör. milestone-<N>
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build

# 4) DOGRULA (sessiz basari sayilmaz)
curl -fsS https://$DOMAIN/api/health      # "version" alani eski surume donmus olmali
curl -fsS https://$DOMAIN/api/ready       # geri alma sonrasi sema da uyumlu mu (503 = migration/DB sorunu)
python scripts/live_gate.py https://$DOMAIN
docker compose -f docker-compose.prod.yml exec -T db   psql -U financialos -d financialos -c 'SELECT COUNT(*) FROM users;'
```

**Downgrade'i olmayan migration'la karşılaşırsan** geri alma yolu kapalıdır: o durumda
yedekten geri yükleme (yukarıdaki bölüm) tek seçenektir. Bu yüzden yeni her migration
gerçek bir `downgrade()` taşımalıdır (kapı: `tests/test_rollback_drill.py`).
