# Denetim: scripts/backfill_net_worth.py

> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


Denetlenen dosya: `scripts/backfill_net_worth.py` (266 satir). Referans karsilastirma icin `app/routers/transactions.py::_apply_to_balance` (satir 84-124) okundu; bakiye yon mantigi orada tanimli.

---

### [SBN-001] income/expense geri-alma yonu tum hesap tiplerinde ayni varsayiliyor, gercekte hesap tipine gore tersine donuyor

**Sorun:** `_balance_at` (satir 105-118), gecmis tarihteki bakiyeyi hesaplarken `target_date` sonrasi islemleri "geri alir". Bunu yaparken income icin her zaman `bal -= t.amount`, expense icin her zaman `bal += t.amount` uyguluyor (satir 114-117). Ancak asil bakiye guncelleme mantigi (`app/routers/transactions.py` satir 84-124, `_apply_to_balance`) hesap tipine gore YON DEGISTIRIYOR:
- `cash`: expense -bakiye, income +bakiye (backfill'in varsaydigi gibi)
- `credit_card`: expense +bakiye (borc artar), income -bakiye (kart odendi, borc azalir) — **backfill'in varsaydiginin TERSI**
- `loan`: sadece expense -bakiye uyguluyor; income icin hicbir dal yok (loan+income bakiyeyi hic etkilemiyor)

**Kanit (satir):** `scripts/backfill_net_worth.py:113-117` vs `app/routers/transactions.py:110-124`.

**Aksiyon:** `_balance_at` icine `account.account_type` parametresi eklenip `_apply_to_balance`'daki tabloyla birebir eslesen (ters yonlu) bir undo mantigi yazilmali. Ozellikle `credit_card` (kart_borcu) ve `loan` (kredi_borcu) hesaplari icin gecmis snapshot'lar suan YANLIS uretiliyor; income/expense islemi olan her kart/kredi hesabinda gecmis `net_worth_seen`/`net_worth_full` degerleri hatali.

**Onem:** KRITIK — uretilen tum gecmis net deger grafikleri (kart borcu ve kredi borcu bilesenleri) sistematik olarak yanlis.

**Guven:** Yuksek (dogrudan iki dosyadaki mantik karsilastirmasina dayaniyor, kod okunarak dogrulandi).

---

### [SBN-002] `transfer` islem tipi `_balance_at`'te tamamen yok sayiliyor

**Sorun:** `TransactionType` enum'unda (`app/models.py:55-58`) `income`, `expense`, `transfer` var ve `transfer` aktif olarak kullaniliyor (`app/routers/transactions.py:33,48`). Ancak `_balance_at`'teki geri-alma dongusu (satir 113-117) sadece `income` ve `expense` icin `if/elif` dali iceriyor; `transfer` tipi hicbir dala girmiyor, yani `target_date` sonrasindaki transfer islemleri geri alinmadan bakiyeye dahil kaliyor.

**Kanit (satir):** `scripts/backfill_net_worth.py:113-117` (elif zinciri `transfer` icin dal icermiyor); `app/models.py:55-58` (enum tanimi); `app/routers/transactions.py:33` (transfer aktif kullanimda).

**Aksiyon:** Transfer'in bakiyeyi nasil etkiledigi (`app/routers/transactions.py` icinde transfer'e ozel bir uygulama noktasi bulunup) tespit edilip `_balance_at`'e eklenmeli. Bulunamiyorsa/Dogrulanmali: transfer'in gercekte hangi account alanlarini degistirdigi net degil, bu da SBN-002'yi hem "eksik dal" hem "belirsiz davranis" riski yapiyor.

**Onem:** YUKSEK — herhangi bir hesapta transfer islemi varsa gecmis bakiye rekonstruksiyonu sessizce yanlis olur, hata da vermez.

**Guven:** Yuksek (enum ve kullanim kaniti acik); transferin tam bakiye etkisi icin "Dogrulanmali".

---

### [SBN-003] `target_date >= today` dali gelecek tarihler icin bugunku cockpit'i tekrar tekrar yaziyor

**Sorun:** `snapshot_for` (satir 138-154), `target_date >= today` oldugunda her zaman `generate_cockpit(user.id, today, db)` cagirip sonucu `target_date` etiketiyle kaydediyor (satir 142-154). `main()`'de `--end` argumani hicbir ust sinir dogrulamasi olmadan kullaniciya birakilmis (satir 251-257); eger `--end` bugunden ileri bir tarih olarak verilirse, `run_backfill` her gelecek gun icin AYNI bugunku degerleri farkli `snapshot_date` altinda yazar — yaniltici, sanki o gunler icin gercek/ongoru veri varmis gibi gorunur.

**Kanit (satir):** `scripts/backfill_net_worth.py:142-154`, `scripts/backfill_net_worth.py:251-257`, `scripts/backfill_net_worth.py:228-238` (dongu, ust sinir kontrolu yok).

**Aksiyon:** `end_date`, `today`'i asiyorsa CLI'da erken uyari/hata verilmeli ya da dongu `min(end_date, today)` ile sinirlanmali.

**Onem:** ORTA — yanlis kullanimda (yanlislikla ileri tarih girilirse) sessizce hatali/yanlis-anlasilabilir veri uretir.

**Guven:** Orta-Yuksek (kod akisi acik; sadece CLI hatali kullanimda tetiklenir).

---

### [SBN-004] Kullanici bulunamadiginda script basarili (exit 0) gibi cikiyor

**Sorun:** `run_backfill` icinde kullanici yoksa `"HATA: Kullanici yok..."` yazdirilip `return 0` donuyor (satir 216-220). `main()`'deki cikis kodu kontrolu ise SADECE `start_date > end_date` durumunda `sys.exit(1)` cagiriyor (satir 259-261). Kullanici-yok durumunda `n == 0` olsa da `start_date > end_date` kosulu saglanmadigindan islem sessizce basariliymis gibi (exit 0) sonlaniyor.

**Kanit (satir):** `scripts/backfill_net_worth.py:216-220`, `scripts/backfill_net_worth.py:259-261`.

**Aksiyon:** `main()`'de `n == 0` durumunun nedenini ayirt eden bir donus (orn. `run_backfill` bir status/hata kodu da dondursun) veya en azindan her `n == 0` durumunda `sys.exit(1)` yapilmali. Otomasyon/cron'da (`docs/dev-commands.md` gunluk backup benzeri kullanimlar) bu sessiz basari yanlis guven verir.

**Onem:** ORTA — otomatik calistirmalarda (ornegin ileride bir cron/backfill job'i) basarisizlik fark edilmeden gecebilir.

**Guven:** Yuksek (kod akisindan dogrudan okunuyor).

---

### [SBN-005] Odenmis ama `paid_date` bos olan alacaklar sessizce yanlis siniflanabilir

**Sorun:** `_receivables_at` (satir 121-135), `(is_paid == False) | (paid_date > target_date)` filtresini kullaniyor (satir 130-131). Eger DB'de `is_paid=True` ama `paid_date=NULL` olan tutarsiz bir kayit varsa, iki kosul da SQL'de False/NULL dondugunden bu kayit HER `target_date` icin receivables disinda kalir — kaydin gercekte target_date'te odenmemis olmasi ihtimaline bakilmaksizin.

**Kanit (satir):** `scripts/backfill_net_worth.py:129-133`.

**Aksiyon:** `is_paid=True` ile `paid_date IS NULL` kombinasyonunun DB seviyesinde imkansiz oldugu dogrulanmali (constraint/CHECK var mi?) — yoksa savunmaci bir NULL kontrolu (`paid_date.is_(None)` durumunda `is_paid`'e guvenip target_date'ten bagimsiz disarida birakma/icerme karari acikca yazilmali).

**Onem:** DUSUK-ORTA — sadece tutarsiz veri varsa tetiklenir; bugun icin "Dogrulanmali" (mevcut invariant bilinmiyor).

**Guven:** Orta (kosul mantigi net ama veri invariant'i dogrulanamadi).

---

### [SBN-006] Var olan snapshot'lar sessizce ustune yaziliyor (upsert), yanlis aralikla yeniden calistirma riski

**Sorun:** `upsert()` (satir 186-197), mevcut bir `NetWorthSnapshot` bulursa tum alanlari `snap` ile ezip commit ediyor (satir 192-197) — geri donusu/yedegi yok. Modul docstring'i bunu "Var olan snapshot'lar uzerine yazilir (upsert)" olarak belgeliyor (satir 15), yani kasitli; ancak SBN-001/SBN-002'deki hesaplama hatalari ile birlesince, script yanlislikla (orn. hatali `--start`/`--end` ile) tekrar calistirilirsa DOGRU olan eski snapshot'lar YANLIS hesaplanan yeni degerlerle sessizce ezilebilir; geri alma mekanizmasi yok.

**Kanit (satir):** `scripts/backfill_net_worth.py:15`, `scripts/backfill_net_worth.py:192-197`.

**Aksiyon:** Buyuk capli backfill'lerden once `python -m scripts.backup` calistirilmasi (repo pratiginde zaten var, `docs/dev-commands.md`) proje sozlesmesi/README seviyesinde hatirlatilmali; script kendi ici bir "kac satir degisecek" onizlemesi sunmuyor.

**Onem:** DUSUK (kasitli tasarim) ama SBN-001/002 ile birlikte etkisi buyuyor — veri kaybi degil ama veri BOZULMASI riski.

**Guven:** Yuksek (docstring + kod davranisi acik).

---

### [SBN-007] `START_DATE` sabiti MVP test senaryosuna hardcoded, genel kullanim icin dogrulanmadi

**Sorun:** `START_DATE = date(2026, 5, 1)` (satir 39), `scripts/setup_data.py`'deki kanonik test verisiyle (Murat'in 1 Mayis 2026 senaryosu, `docs/architecture.md`) hizalanmis bir sabit. Gercek kullanicinin ilk hesap acilis tarihi bundan farkliysa (veya birden fazla kullanici/hesap farkli tarihlerde acildiysa), `--start` verilmedigi surece backfill bu sabitten baslar; hesaplarin gercek `created_at`'inden onceki tarihler icin `_account_inception_at` (satir 69-75) zaten 0 donuyor, dolayisiyla asiri erken bir `START_DATE` pratikte zararsiz olabilir — ama bu sadece yatirim hesaplari icin kontrol ediliyor (satir 87-89); `cash`/`credit_card`/`loan` icin inception kontrolu YOK, yani hesap acilmadan onceki tarihler icin de `_balance_at` calisip (muhtemelen 0/yanlis) bir bakiye uretebilir.

**Kanit (satir):** `scripts/backfill_net_worth.py:39`, `scripts/backfill_net_worth.py:69-89` (inception kontrolu sadece `_investment_value_at` icinde), `scripts/backfill_net_worth.py:156-168` (cash/credit_card/loan icin inception kontrolu yok).

**Aksiyon:** `_balance_at`'e de hesap acilis tarihinden once icin 0/skip mantigi eklenmesi dogrulanmali; aksi halde bir hesap acilmadan once icin de (yanlislikla, cunku o tarihte islem yoktur) mevcut bakiyenin ham hali (`account.balance`, hicbir islem geri alinmadan) o hesap icin snapshot'a yazilabilir.

**Onem:** DUSUK-ORTA — tek kullanicili MVP'de START_DATE = ilk hesap acilis tarihiyle ortustugunden bugun icin risk dusuk, ama fonksiyon genel amacli degil.

**Guven:** Orta ("Dogrulanmali": tum hesaplarin `created_at`'i gercekten `START_DATE`'ten once mi kontrol edilmedi doniyor mu, kod okumasindan net degil).

---

## Ozet

En kritik iki bulgu (SBN-001, SBN-002) dogrudan **kart_borcu** ve **kredi_borcu** gibi bu projenin cekirdek Turkce alanlarinin gecmis snapshot'larini etkiliyor — PROJE.md'de "Rules Engine karar verir" ilkesi geregi bu hesaplarin dogru olmasi kritik. Script `drop_all` cagirmiyor (bu `scripts/setup_data.py`'ye ozgu, ayri script), ancak SBN-006'daki sessiz upsert + SBN-001/002'deki hesap hatalari birlikte dogru gecmis verinin yanlis veriyle ezilmesine yol acabilir.
