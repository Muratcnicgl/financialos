# Denetim: app/database.py

### [DB-001] init_db()/create_all, alembic (ADR-013) ile senkron degil - schema drift riski
- **Sorun:** `init_db()` (satir 75-82) `Base.metadata.create_all(bind=engine)` cagirir. Ancak repo `alembic` ile schema yonetimine gecmis (bkz. `alembic/env.py` - `Base, engine` dogrudan `app.database`'den import ediliyor, `app/main.py:112-113` "ADR-013: Schema yonetimi alembic ile" diyor). `scripts/setup_data.py:36-37` ise `Base.metadata.drop_all(bind=engine)` + `create_all(bind=engine)` calistiriyor - bu `alembic_version` tablosunu da siler. Sonrasinda DB, modellerin GUNCEL haline sahip olur ama alembic bunu bilmez (alembic_version kaydi yok). Bir sonraki `alembic upgrade head` calistirildiginda alembic ya "DB zaten guncel ama versiyon kaydi yok" belirsizligine duser ya da migration tekrar CREATE TABLE denerse "table already exists" hatasi verir.
- **Kanit:** satir 75-82 (`init_db`); capraz referans `scripts/setup_data.py:36-37`, `alembic/env.py:7`, `app/main.py:112-113`.
- **Aksiyon:** `setup_data.py` calistirildiktan sonra `alembic stamp head` ile version tablosunu senkronlamayi dokumante et, ya da `init_db()`/`drop_all+create_all` pattern'ini tamamen kaldirip test verisi kurulumunu da alembic migration + seed script'ine devret.
- **Onem:** Yuksek · **Guven:** Dogrulanmali

### [DB-002] DATABASE_URL=sqlite:///:memory: tuzagi - StaticPool/poolclass yok
- **Sorun:** `engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} ...)` (satir 34-38) icin `poolclass` belirtilmemis. Eger `.env`'de `DATABASE_URL=sqlite:///:memory:` set edilirse (dev-commands.md DATABASE_URL'i "opsiyonel" olarak listeliyor, kisitlama yok), SQLAlchemy'nin varsayilan pool'u (QueuePool/varsayilan) her checkout'ta potansiyel olarak farkli bir baglanti verir; `:memory:` DB baglanti-basina ayri ve izoledir. Sonuc: bir request'te yazilan veri baska bir request'te "no such table" hatasi olarak gorunur - repo'daki test dosyalari (`tests/test_premortem_endpoint.py:31-34` yorumu) bu sorunu bizzat belgeliyor ve kendi `StaticPool`'lu engine'lerini kuruyorlar, ama `app/database.py` boyle bir koruma icermiyor.
- **Kanit:** satir 25, 34-38 (poolclass verilmemis); karsilastirma: `tests/test_premortem_endpoint.py:31-34`.
- **Aksiyon:** `DATABASE_URL` `:memory:` iceriyorsa `poolclass=StaticPool` zorla, ya da en azindan bir yorum/guard ile bu URL'in production/dev.env'de kullanilmamasi gerektigini belirt.
- **Onem:** Orta · **Guven:** Kesin (SQLAlchemy'nin bilinen davranisi)

### [DB-003] scripts/backup.py, DATABASE_URL'i degil hardcoded yolu kullaniyor
- **Sorun:** `app/database.py:25`'teki `DATABASE_URL` env degiskeni ile ozellestirilebilir DB konumu tanimlaniyor, ama `scripts/backup.py`'deki `DB_PATH = Path("data/financialos.db")` bu degeri okumuyor, sabit yol kullaniyor. Kullanici `.env`'de `DATABASE_URL` degistirirse (dev-commands.md bunu destekliyor), yedekleme sessizce yanlis/var olmayan dosyayi kontrol eder ("HATA: DB bulunamadi" ya da eski/yanlis DB'yi yedekler).
- **Kanit:** `app/database.py:25` (DATABASE_URL kaynagi) vs `scripts/backup.py` DB_PATH sabiti (capraz dosya, ayni konfig kaynagina baglanmiyor).
- **Aksiyon:** `scripts/backup.py`'nin `app.database.DATABASE_URL`'i parse edip kullanmasi saglanmali, boylece tek dogruluk kaynagi korunur.
- **Onem:** Orta · **Guven:** Dogrulanmali

### [DB-004] get_db() exception yolunda explicit rollback yok
- **Sorun:** `get_db()` (satir 63-72) `try: yield db / finally: db.close()` yapisinda; `except` bloğu ve `db.rollback()` cagrisi yok. Bir router'da exception olustugunda (orn. yariminda commit edilmemis bir islem varken hata firlarsa) session `close()` ile kapatiliyor. SQLAlchemy `Session.close()` bekleyen transaction'i implicit rollback eder, bu yuzden fonksiyonel olarak calisir; ancak finansal-yazma agir bir sistemde niyeti acikca belirtmek (`except: db.rollback(); raise` sonra `finally: db.close()`) hem okunurlugu artirir hem de SQLAlchemy davranisina implicit guvenmekten kacinir.
- **Kanit:** satir 63-72.
- **Aksiyon:** `except Exception: db.rollback(); raise` eklenerek niyet aciklastirilmali (davranissal degisiklik degil, defansif netlik).
- **Onem:** Dusuk · **Guven:** Dogrulanmali

### [DB-005] busy_timeout=5000 hardcoded magic number
- **Sorun:** `cur.execute("PRAGMA busy_timeout=5000")` (satir 51) sabit 5000ms, env ile override edilemiyor. Docstring (satir 10-11) bunu DATA-004/PERF-013 icin gerekceli aciklasa da, deger sabit kod icine gomulu; scheduler+concurrent-request yogunlugu artarsa (Wave-2 A2 recurring islemler gibi) bu deger ayarlanamaz durumda.
- **Kanit:** satir 51.
- **Aksiyon:** Kritik degil, ama `os.getenv("SQLITE_BUSY_TIMEOUT_MS", "5000")` gibi bir override noktasi eklenebilir; su an icin sadece not.
- **Onem:** Dusuk · **Guven:** Kesin
