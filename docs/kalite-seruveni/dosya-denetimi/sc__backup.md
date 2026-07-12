# Denetim: scripts/backup.py

Kapsam: sadece `scripts/backup.py` (repo koku `C:\Users\18155\PycharmProjects\financialos`). Dosya 70 satir, tek fonksiyon (`backup`) + argparse CLI girisi.

---

### [SBK-001] DATABASE_URL yerine hardcoded goreli yol kullaniliyor — yanlis/var olmayan DB sessizce kontrol edilebilir

- **Sorun:** `DB_PATH = Path("data/financialos.db")` (satir 21) sabit deger. `docs/dev-commands.md` ve `app/database.py:25`e gore DB konumu `.env`'deki `DATABASE_URL` ile ozellestirilebilir (`os.getenv("DATABASE_URL", "sqlite:///./data/financialos.db")`). Kullanici `DATABASE_URL`'i degistirirse (ornegin farkli bir dosya adi/klasor), `backup.py` bunu okumaz; ya "HATA: DB bulunamadi" yazip sessizce cikar (satir 26-28, exit code yok — cagiran script/scheduler bunu basari sanabilir) ya da yanlislikla ayni isimli baska bir dosyayi yedekler. Bu, kullanicinin "otomatik gunluk yedek aliniyor" sandigi ama gercekte hicbir sey yedeklenmedigi bir senaryo yaratir.
- **Kanit:** `scripts/backup.py:21` (DB_PATH sabiti) vs `app/database.py:25` (DATABASE_URL kaynagi, cross-file — bu dosyanin dogrulama kapsami disinda, referans amacli). `docs/dev-commands.md` .env semasinda DATABASE_URL "opsiyonel" olarak belgeleniyor.
- **Aksiyon:** `backup.py`'nin `app.database.DATABASE_URL`'i (veya en azindan `os.getenv("DATABASE_URL")`) parse edip DB yolunu oradan turetmesi; DB bulunamadiginda `sys.exit(1)` ile hata kodu donmesi (scheduler/otomasyon sessiz basarisizligi fark edebilsin).
- **Onem:** Kritik (veri kaybi riski — yanlis/eksik yedekleme sessizce "basarili" gorunebilir).
- **Guven:** Yuksek (kod karsilastirmasi acik; DATABASE_URL kullanim deseni dogrulandi).

---

### [SBK-002] Negatif `--keep-days` degeri az once alinan yedegi de dahil TUM yedekleri siler

- **Sorun:** `argparse.add_argument("--keep-days", type=int, default=30, ...)` (satir 64-67) negatif deger icin herhangi bir validasyon yapmiyor. `--keep-days -5` verilirse `cutoff = time.time() - (-5)*86400 = time.time() + 5*86400` (satir 48) — yani gelecekte bir zaman damgasi. Butun mevcut `*.db` dosyalari (satir 50, `os.path.getmtime(f) < cutoff` her zaman True) — bu az once satir 39'da olusturulan yeni yedek (`dest`) dahil — `os.remove(f)` ile kalici olarak silinir (satir 53-54). Kullanicinin CLI'da yanlislikla eksi isaret yazmasi (veya bir scripti/env degiskenini kotu parse etmesi) tum yedek gecmisini tek komutla yok eder.
- **Kanit:** `scripts/backup.py:48-54` (cutoff hesaplama + silme dongusu), `scripts/backup.py:64-67` (argparse, min/pozitif kisit yok).
- **Aksiyon:** `keep_days < 0` durumunda `ValueError`/erken `return` ile calismayi durdur (ornegin `argparse` icin `type=lambda v: int(v) if int(v) >= 0 else parser.error(...)` veya fonksiyon basinda guard).
- **Onem:** Kritik (tek yanlis parametreyle tum yedek gecmisi geri donulemez silinir — DOGRULANMALI: production'da bu script'in nasil cagirildigi, ama argparse seviyesinde koruma olmadigi kod okumasiyla kesin).
- **Guven:** Yuksek (mantik yurutmesi kod uzerinden dogrulandi).

---

### [SBK-003] Minimum-yedek-koruma guvenligi yok — `--keep-days 0` (veya kucuk deger) tum gecmisi silebilir

- **Sorun:** `keep_days=0` gecerli/pozitif bir deger oldugu icin SBK-002'deki guard bunu yakalamaz, ama satir 48-54'teki silme mantigi "en az N yedek sakla" gibi bir alt sinir icermiyor. `cutoff = time.time()` ile, birkaç saniye/dakika once alinmis (ayni gun icindeki) tum onceki yedekler silinir; sadece bu calismada olusturulan `dest` (satir 33, mtime ~simdi) siniri dar farkla asabilir. Yani "gunluk backup" alışkanligiyla `--keep-days 0` denenirse gunun tum onceki yedekleri (varsa) kaybolur, geriye tek kopya kalir — tek nokta hata riski.
- **Kanit:** `scripts/backup.py:48-54` (alt sinir/min-kept-count kontrolu yok).
- **Aksiyon:** Silme oncesi kalan (silinmeyecek) dosya sayisini hesapla; en az 1 (tercihen N) yedek her zaman korunacak sekilde `old_files` listesini kirp.
- **Onem:** Orta (kasitli/edge-case kullanimda veri kaybi; default=30 ile gunluk kullanimda tetiklenmez).
- **Guven:** Orta (davranis kod okumasiyla dogru cikarsandi; gercek kullanicinin `--keep-days 0` cagirma ihtimali DOGRULANMALI).

---

### [SBK-004] Ayni dakika icinde ikinci calistirma onceki yedegi sessizce ezer

- **Sorun:** Dosya adi `%Y-%m-%d-%H%M` formatinda dakika hassasiyetinde uretiliyor (satir 32-33). Script ayni dakika icinde iki kez calistirilirsa (manuel test, cift tetiklenen scheduler, vb.) `dest` ayni isimle `sqlite3.connect(dest)` acilir (satir 37) ve `.backup()` (satir 39) icerigi ustune yazar — dosya varligi kontrolu yok, kullaniciya uyari verilmez. Ilk yedek geri donulemez kaybolur.
- **Kanit:** `scripts/backup.py:32-39` (stamp/dest uretimi + connect + backup, `dest.exists()` kontrolu yok).
- **Aksiyon:** Saniye ekle (`%Y-%m-%d-%H%M%S`) veya `dest.exists()` ise dosya adina sayac/suffix ekleyerek eski yedegi koru.
- **Onem:** Orta (dusuk olasilik ama sessiz ve fark edilmesi zor veri kaybi).
- **Guven:** Yuksek (kod dogrudan bu davranisi gosteriyor).

---

### [SBK-005] Yedek butunlugu dogrulanmiyor — bozuk/yarim kopya sessizce "basarili" sayilabilir

- **Sorun:** `src_conn.backup(dest_conn)` (satir 39) sonrasi hicbir dogrulama (`PRAGMA integrity_check`, dosya boyutu > 0 gibi) yapilmiyor; `size_kb` sadece bilgi amacli yazdiriliyor (satir 44-45), basarisizlik/kucukluk durumunda hata uretmiyor. Disk dolu, izin hatasi (backup cagrisi kismi kopyalayip exception firlatirsa `finally` (satir 40-42) baglantilari kapatir ama olusmus olan yarim/bozuk `dest` dosyasi `backups/` klasorunde kalir — sonraki `--keep-days` temizligine kadar orada durur ve gercek bir yedek gibi gorunur.
- **Kanit:** `scripts/backup.py:36-45` (try/finally sadece connection kapatir, dogrulama/temizlik yok).
- **Aksiyon:** Backup sonrasi `dest_conn.execute("PRAGMA integrity_check")` calistir; basarisizsa/exception olursa yarim `dest` dosyasini sil ve hata ile cik (`sys.exit(1)`).
- **Onem:** Orta (nadir tetiklenir ama tetiklendiginde kullanici bozuk bir yedege guvenebilir).
- **Guven:** Orta (sqlite3 `backup()` API'sinin hata modlari DOGRULANMALI — normal disk-dolu senaryosunda exception firlattigi genel bilgi, bu ortamda test edilmedi).

---

### [SBK-006] `sqlite3` hatalari icin exception handling yok — sadece "dosya yok" durumu kullanici-dostu mesajla ele aliniyor

- **Sorun:** Satir 26-28 sadece `DB_PATH.exists()` durumunu Turkce "HATA:" mesajiyla karsiliyor. Ancak `sqlite3.connect(DB_PATH)` (satir 36) veya `.backup()` (satir 39) sirasinda olusabilecek `sqlite3.OperationalError` (ornegin DB baska bir islem tarafindan kilitli, dosya bozuk, hedef diskte yer yok) yakalanmiyor — ham Python traceback kullaniciya/scheduler log'una dusuyor, script'in geri kalan Turkce mesaj tutarliligiyla uyusmuyor ve otomasyon (Gorev Zamanlayici) bunu okunakli bir sekilde raporlayamaz.
- **Kanit:** `scripts/backup.py:36-42` (try/finally var ama except yok — hata Turkce mesaja donusmuyor, sadece connection'lar kapatilip yeniden firlatiliyor).
- **Aksiyon:** `except sqlite3.Error as e:` ekleyip Turkce hata mesaji + `sys.exit(1)` ile cik.
- **Onem:** Dusuk (fonksiyonellik kirilmiyor, sadece hata raporlama tutarsizligi/okunabilirlik).
- **Guven:** Yuksek (kod uzerinden dogrudan gozlemlendi).

---

### [SBK-007] Calisma dizini (cwd) varsayimi dogrulanmiyor — repo kokunden baska yerden calistirilirsa DB_PATH/BACKUP_DIR farkli konuma isaret eder

- **Sorun:** `DB_PATH` ve `BACKUP_DIR` (satir 21-22) goreli (`Path("data/...")`) — script'in `python -m scripts.backup` ile repo kokunden calistirildigi varsayiliyor (dev-commands.md ve scheduled task komutunda `cd repo; ...` ile bu saglaniyor). Script icinde bu varsayimi dogrulayan/hata veren bir kontrol yok; farkli bir cwd'den calistirilirsa DB bulunamaz mesaji verir (SBK-001'deki sessiz-basarisizlik riskiyle birlesir) ya da — daha kotusu — o dizinde `data/financialos.db` adinda baska/eski bir dosya varsa YANLIS dosyayi yedekler ve kullaniciya hicbir uyari gitmez.
- **Kanit:** `scripts/backup.py:21-22` (goreli Path tanimlari, cwd dogrulamasi yok).
- **Aksiyon:** `DB_PATH`/`BACKUP_DIR`'i script dosyasinin konumuna gore (`Path(__file__).resolve().parent.parent / "data" / ...`) mutlak yola sabitle, boylece cagrilan dizinden bagimsiz calissin.
- **Onem:** Dusuk-Orta (dogru cagrildiginda sorun yok; yanlis cagrildiginda SBK-001 ile birlesip sessiz yanlis-DB yedeklemesine yol acabilir).
- **Guven:** Orta (gercek kullanimda script'in her zaman repo kokunden cagrildigi DOGRULANMALI; dokumantasyon bunu varsayiyor ama koda gomulu degil).

---

## Ozet

7 bulgu (2 kritik, 2 orta-kritik sinirinda, 3 dusuk-orta). En yuksek risk: yedekleme, gercek DB konfigurasyonundan (`DATABASE_URL`) bagimsiz calisiyor (SBK-001) ve `--keep-days` negatif/sifir degerlerine karsi korumasiz (SBK-002/003) — ikisi de "yedek aliniyor sanip aslinda alinmiyor/hepsi siliniyor" sinifinda sessiz veri kaybi riski tasir.
