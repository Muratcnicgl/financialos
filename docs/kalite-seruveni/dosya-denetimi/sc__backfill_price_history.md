# Denetim: scripts/backfill_price_history.py

Denetim tarihi: 2026-07-10. Kapsam: dosyanin tamami (satir 1-236), satir satir okundu. `app/models.py` PriceHistory tanimi (satir 540-579) capraz kontrol edildi.

Genel not: bu script `setup_data.py`'nin aksine **drop_all cagirmiyor**. Yazma islemi `INSERT ... ON CONFLICT DO NOTHING` (satir 149-152), PriceHistory'nin kompozit PK'si (`fund_code, price_date, source` - `app/models.py:573-577`) ile eslesiyor, dolayisiyla tekrar calistirmak veri kaybina veya duplike satira yol acmaz. Asagidaki bulgular veri kaybindan cok gozlemlenebilirlik, dayaniklilik ve ic tutarlilik ile ilgili.

---

### [SBP-001] Coklu fund_code turunde her seferinde yeni Crawler() olusturuluyor, rate-limit durumu paylasilmiyor
**Sorun**: `_fetch_tefas_range` (satir 46-113), her cagrildiginda (yani her fund_code icin, satir 66) yeni bir `Crawler()` nesnesi yaratiyor. `main()` (satir 213-219) coklu fund_code'u sirayla `backfill_fund` ile isliyor; her fund kendi Crawler'ini aliyor.
**Kanit(satir)**: 66 (`crawler = Crawler()`), 213-214 (`for fc in fund_codes: r = backfill_fund(...)`).
**Aksiyon**: Docstring'de (satir 13) "rate-limit otomatik yonetilir" iddiasi pytefas paketinin *tek Crawler instance'i* icin gecerli olabilir (Dogrulanmali — pytefas kaynagi incelenmedi). Eger paketin rate-limit sayaci instance-scoped ise, coklu fund_code'lu bir calistirmada (varsayilan tum investment hesaplari, 365 gun) her fund taze bir sayacla baslar ve TEFAS'in gercek sunucu-tarafi limitine (dakikada 6 istek gibi) toplamda uyulmayabilir. Tum fund'lar icin tek Crawler paylastirilmasi veya pytefas dokumantasyonunda instance-scope davranisinin dogrulanmasi onerilir.
**Onem**: Yuksek (dogrulanirsa) — coklu-fund calistirmalarinda TEFAS tarafinda throttle/IP kisitlamasina yol acabilir, sessizce basarisiz fund'lar birikebilir.
**Guven**: Dogrulanmali (pytefas 0.3.0 ic implementasyonu bu dosyadan gorulemiyor).

### [SBP-002] Bulk upsert sonrasi rowcount'un SQLite insertmanyvalues batching ile toplamda dogru rapor edip etmedigi belirsiz
**Sorun**: `values` listesi (satir 139-147) tek bir `sqlite_upsert(...).values(values)` ifadesine veriliyor; 365 gunluk varsayilan araliktaki bir fund icin bu satir sayisi SQLite'in parametre limitini (tipik 999) asabilir, bu durumda SQLAlchemy 2.0 "insertmanyvalues" ozelligi statement'i birden fazla batch INSERT'e boler. `result.rowcount` (satir 158) bu cok-batch senaryosunda tum batch'lerin toplamini mi yoksa sadece son batch'i mi yansitiyor, kod icinde dogrulanmiyor.
**Kanit(satir)**: 139-158, ozellikle `inserted = result.rowcount if result.rowcount is not None and result.rowcount >= 0 else 0` (158) ve `skipped = len(rows) - inserted` (159).
**Aksiyon**: `--dry-run` disi gercek calistirmada 365 satirlik (veya daha uzun `--start` ile daha fazla) bir fund ile calistirip stdout'taki "Eklendi"/"Atlandi" sayilarini `SELECT COUNT(*) FROM price_history WHERE fund_code=...` ile karsilastirarak dogrulanmali. Rapor sayisi yanlissa (veri kaybi yok, sadece yanlis rapor) loglama hatasi kullaniciyi yanlis yonlendirir.
**Onem**: Orta — veri kaybi riski yok (ON CONFLICT DO NOTHING garanti), ama operator yanlis "Eklendi: N" sayisina gorebilir ve is takibi yanilir.
**Guven**: Dogrulanmali.

### [SBP-003] Fetch sirasinda tek satirlik bozuk veri (NaN/None fiyat) tum fund'un backfill'ini iptal ediyor
**Sorun**: `_fetch_tefas_range` icindeki liste comprehension (satir 97-111), `row["price"]` degerini `float(...)` -> `Decimal(str(...))` -> `.quantize(Decimal("0.0001"))` zincirinden gecirirken herhangi bir NaN/None/bozuk deger icin try/except yok. Boyle bir satir gelirse `Decimal("nan").quantize(...)` `InvalidOperation` firlatir; bu, cagiran `backfill_fund`'daki genel `except Exception` (satir 122) tarafindan yakalanir ama **o fund icin cekilen TUM satirlar** (o gune kadar toplanmis olanlar dahil, cunku hata olusana kadar biriken `rows` listesi hic donulmeden kayboluyor) atilir — kismi/iyi satirlar bile DB'ye yazilmiyor.
**Kanit(satir)**: 97-111 (try/except yok), 120-124 (`except Exception as e: ... return {"fetched": 0, ...}` — tum fund icin sifir kayit donuyor).
**Aksiyon**: Satir bazli try/except eklenip bozuk satir atlanarak (log ile) geri kalan iyi satirlarin islenmesi onerilir; boylece bir gunun bozuk verisi butun fund'un backfill'ini iptal etmez.
**Onem**: Orta — veri kaybi degil ama veri *eksikligi* riski: bir fund'da 365 gunun 364'u saglam olsa bile tek bozuk satir yuzunden hicbiri yazilmaz.
**Guven**: Yuksek (kod akisindan dogrudan okunabiliyor).

### [SBP-004] DB yazma islemi ayri `engine.connect()` ile yapiliyor, canli uygulama ile SQLite kilit celismesi durumunda retry/backoff yok
**Sorun**: `db = SessionLocal()` (satir 190) sadece Account okumasi icin kullaniliyor; asil yazma her fund icin ayri bir `engine.connect()` (satir 153) ile yapiliyor. PROJE.md/wave-2-roadmap.md'ye gore sistem "her gun canli kullaniliyor" (uvicorn calisir durumda olabilir). SQLite varsayilan journal modunda ayni anda yazma kilidi celismesi olursa (`database is locked`), kod bunu genel `except Exception` (122) ile yakalayip o fund'u "HATA" olarak isaretleyip bir sonrakine geciyor — retry/backoff mekanizmasi yok.
**Kanit(satir)**: 153-155 (`with engine.connect() as conn: ... conn.commit()`), 122-124 (genel except, retry yok).
**Aksiyon**: WAL modu aktifse risk dusuk (Dogrulanmali — `app/database.py`'de PRAGMA ayari kontrol edilmeli); degilse en azindan basit bir retry (ornegin 3 deneme, kisa bekleme) eklenmesi onerilir. Idempotent oldugu icin yeniden calistirilabilir olmasi riski hafifletiyor.
**Onem**: Orta — veri kaybi yok (script tekrar calistirilabilir, idempotent), ama otomatik/zamanlanmis bir cron olarak kurulursa (docs/dev-commands.md'deki `schtasks` pattern'i gibi) sessiz basarisizliklar fark edilmeyebilir.
**Guven**: Dogrulanmali (SQLite journal modu bu dosyada gorulmuyor).

### [SBP-005] Float roundtrip ile fiyat donusumu (cift hassasiyet kaybi riski)
**Sorun**: `price_decimal = Decimal(str(float(row["price"]))).quantize(Decimal("0.0001"))` (satir 101). `row["price"]` pandas DataFrame'den geliyor ve muhtemelen zaten `float64`; `float(...)` sarmalayici gereksiz ama zararsiz. Asil risk: TEFAS API'sinden gelen deger once pytefas ic tarafinda float'a donusturulmus olabilir (Dogrulanmali), bu durumda ondalik hassasiyet kaybi backfill script'inden once olusur ve bu kod sadece onu tasir.
**Kanit(satir)**: 99-101 (kod ici yorum bunu "BUG #007 + fund_tracker.py patterni" olarak zaten belgeliyor, yani bilinen/kabul edilen bir taviz).
**Aksiyon**: Degisiklik onerilmiyor (mevcut sistemde `fund_tracker.py` ile tutarlilik icin bilerek boyle birakilmis); sadece bir sonraki fiyat-hassasiyeti incelemesinde tekrar gozden gecirilmesi icin not dusuluyor.
**Onem**: Dusuk — bilinen/dokumante edilmis taviz, yeni risk degil.
**Guven**: Bilgi amacli (kod yorumundan dogrulanan mevcut durum).

### [SBP-006] `--start`/`--end` argumanlari icin format hatasi kullaniciya ham traceback olarak donuyor
**Sorun**: `date.fromisoformat(args.end)` / `date.fromisoformat(args.start)` (satir 178-179) `try/except` ile sarilmamis. Kullanici `--start 09-05-2025` gibi yanlis formatta bir tarih girerse `ValueError` yakalanmadan cikar, script Python traceback'i ile sonlanir (exit code 1 olur ama anlasilir bir "HATA:" mesaji basilmaz — satir 182-183'teki ozenli hata mesaji pattern'i burada uygulanmiyor).
**Kanit(satir)**: 178-179 (try/except yok), karsilastir: 181-183 (start>end icin duzgun hata mesaji var).
**Aksiyon**: `date.fromisoformat` cagrilarini try/except ile sarip tutarli "HATA: gecersiz tarih formati" mesaji + `sys.exit(1)` eklenmesi onerilir.
**Onem**: Dusuk — sadece CLI kullanilabilirligi, veri riski yok.
**Guven**: Yuksek (kod akisindan dogrudan gorulebiliyor).

### [SBP-007] `--fund` argumaniyla verilen kod, Account tablosundaki gercek fund_code'lara karsi dogrulanmiyor
**Sorun**: `--fund` verildiginde (satir 192-193) dogrudan `fund_codes = [args.fund.upper()]` olusturuluyor; Account tablosunda boyle bir fund_code'un var olup olmadigi kontrol edilmiyor. Yanlis yazilmis/var olmayan bir kod icin script sessizce "YAT bos/hatali, EMK deneniyor..." (91) ardindan "Veri donmedi" (127) uyarisi basip 0 satirla biter — kullanici hesaba baglanip baglanmadigini anlayamaz.
**Kanit(satir)**: 192-193, 126-128.
**Aksiyon**: Bilgilendirici olarak, `--fund` girildiginde Account tablosunda eslesen bir kayit olup olmadigini kontrol edip bulunamazsa uyari basilmasi onerilir (zorunlu degil, docstring'de "tek fund" ozelligi zaten TEFAS'a dogrudan sorgu niyetiyle tasarlanmis olabilir).
**Onem**: Dusuk — beklenen davranis olabilir (dogrulanmali), sadece UX iyilestirmesi.
**Guven**: Orta (tasarim niyeti belirsiz, "Dogrulanmali").

---

## Ozet

| ID | Baslik | Onem | Guven |
|---|---|---|---|
| SBP-001 | Coklu fund icin paylasilmayan Crawler/rate-limit durumu | Yuksek (dogrulanirsa) | Dogrulanmali |
| SBP-002 | Bulk upsert rowcount raporlamasi batching ile belirsiz | Orta | Dogrulanmali |
| SBP-003 | Tek bozuk satir tum fund backfill'ini iptal ediyor | Orta | Yuksek |
| SBP-004 | Ayri engine.connect() ile SQLite kilit celismesi, retry yok | Orta | Dogrulanmali |
| SBP-005 | Float roundtrip hassasiyet kaybi (bilinen taviz) | Dusuk | Bilgi amacli |
| SBP-006 | Tarih parse hatasi icin try/except eksik | Dusuk | Yuksek |
| SBP-007 | --fund kodu Account tablosuna karsi dogrulanmiyor | Dusuk | Orta |

Veri kaybi (drop_all benzeri) riski bu dosyada **tespit edilmedi** — yazma islemi idempotent (kompozit PK + ON CONFLICT DO NOTHING). En kritik acik nokta SBP-001 (coklu fund'da rate-limit paylasimi) ve SBP-003'tur (bozuk tek satirin tum fund'u iptal etmesi, veri eksikligi riski).
