# Denetim: app/routers/incomes.py

> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [RIN-001] day_of_month=29/30/31 olan gelirler bazi aylarda tamamen atlaniyor (Subat, 30 gunluk aylar)
- **Sorun:** `trigger_due_incomes` tetikleme kosulu `RecurringIncome.day_of_month <= today.day` (satir 145). Eger day_of_month o ayin gun sayisindan buyukse (ornegin day_of_month=31 iken Nisan/Haziran/Eylul/Kasim 30 gun cekiyor, ya da day_of_month=29/30/31 iken Subat), o ay boyunca kosul hicbir gun `True` olmuyor. `last_triggered_year_month` sadece basarili tetiklemede yazildigi icin (satir 181) bu ay icin hicbir yakalama/telafi mekanizmasi yok — gelir o ay icin sessizce hic tetiklenmiyor, sonraki ay `year_month` degistigi icin de "atlanan ay" asla telafi edilmiyor.
- **Kanit:** satir 142-146 (sorgu), satir 181 (dedup yazimi); `day_of_month` alani `ge=1, le=31` ile sinirlandirilmis (satir 35) ama ay uzunlugu kontrolu hicbir yerde yok.
- **Aksiyon:** Tetikleme kosulunu "bu ay icin uygun son gun" mantigina cevir: `effective_day = min(inc.day_of_month, takvim_ayinin_son_gunu)` ve karsilastirmayi buna gore yap; ya da ayin son gunune ozel bir bayrak/normalize kurali ekle.
- **Onem:** Kritik · **Guven:** Kesin

### [RIN-002] Turkce ay adi icin locale ayari yok — strftime('%B') sistem locale'ine bagli
- **Sorun:** `description` alani `today.strftime('%B %Y')` ile uretiliyor (satir 173). Backend'de hicbir yerde `locale.setlocale(locale.LC_TIME, 'tr_TR...')` cagrisi yok (repo genelinde arandi, bulunamadi). Python'un varsayilan "C" locale'inde `%B` Ingilizce ay adi doner (orn. "May 2026"), Turkce alan adlarini/UI'yi koruma prensibiyle celisir ve kullaniciya "Maas — May 2026" gibi karisik bir aciklama gider.
- **Kanit:** satir 173; PROJE.md "UI ve alan adlari... Turkce korunur" ilkesi.
- **Aksiyon:** Sabit bir Turkce ay adi listesiyle formatla (locale'e guvenme) veya uygulama baslangicinda `locale.setlocale` cagirip prod ortaminda tr_TR.UTF-8 kurulu oldugunu dogrula.
- **Onem:** Orta · **Guven:** Dogrulanmali (calisma ortaminin locale'i test edilmedi)

### [RIN-003] Ikinci db.commit() basarisiz olursa rollback yok — orphan/tekrar-tetiklenebilir pending action riski
- **Sorun:** `propose_action` kendi icinde commit ediyor (PendingAction status=pending olarak DB'ye yaziliyor), sonra satir 179-182'de `pending.source_recurring_id`, `source_recurring_type`, `inc.last_triggered_year_month` set edilip ikinci bir `db.commit()` cagriliyor. Bu ikinci commit basarisiz olursa (`except Exception as e` satir 191-192) sadece log yazilir, `db.rollback()` cagrilmaz. Boyle bir durumda PendingAction DB'de zaten "pending" olarak duruyor ama `source_recurring_id` alani bos kalmis olabilir; bir sonraki `trigger_due_incomes` cagrisinda dedup sorgusu (satir 155-160) bu kaydi bulamayacagi icin ayni gelir icin ikinci bir pending action daha olusturulabilir (cift gelir onerisi).
- **Kanit:** satir 163-192.
- **Aksiyon:** except blogunda `db.rollback()` ekle; ayrica source alanlarini ayni transaction'da (propose_action cagrisindan once/iceride) atomik yazacak sekilde yeniden tasarla.
- **Onem:** Orta · **Guven:** Dogrulanmali (SQLAlchemy commit-fail sonrasi session davranisi ortam/versiyon bagimli olabilir)

### [RIN-004] Birden fazla nakit hesap varsa sadece ilki kullaniliyor, sessizce
- **Sorun:** `cash_acc = db.query(Account).filter(..., AccountType.cash).first()` (satir 135-138). Kullanicinin birden fazla nakit tipi hesabi varsa hangisinin secilecegi veritabani sira garantisine (genelde id sirasi) birakiliyor; yanlis hesaba gelir eklenmesi riski var ve herhangi bir uyari/log yok.
- **Kanit:** satir 135-140.
- **Aksiyon:** Tek-kullanici MVP'de tek nakit hesap varsayimi doc'ta acikca belirtilmeli veya birden fazla nakit hesap varsa hata/uyari donulmeli.
- **Onem:** Dusuk · **Guven:** Dogrulanmali (mevcut test verisinde tek nakit hesabi olabilir)

### [RIN-005] delete_income sert silme + FK'siz source_recurring_id — SQLite id yeniden kullaniminda yanlis dedup eslesmesi ihtimali
- **Sorun:** `delete_income` (satir 197-210) RecurringIncome kaydini tamamen siliyor. `PendingAction.source_recurring_id` bir ForeignKey degil, duz Integer (app/models.py satir 333-334), yani silme islemi hicbir referans butunlugu kontrolunden gecmiyor. SQLite'ta AUTOINCREMENT anahtar sozcugu kullanilmadigi surece silinen en yuksek id yeniden kullanilabilir; eger eski (silinmis) gelir icin hala 'pending' durumda bir PendingAction varsa ve yeni olusturulan bir RecurringIncome ayni id'yi alirsa, `trigger_due_incomes` dedup sorgusu (satir 155-160) bu eski pending kaydi yanlislikla yeni gelire ait sanip yeni gelirin hic tetiklenmemesine yol acabilir.
- **Kanit:** satir 197-210; app/models.py satir 333-334 (FK yok).
- **Aksiyon:** source_recurring_id icin gercek ForeignKey + ON DELETE SET NULL tanimla, ya da delete_income icinde ilgili pending/source referanslarini temizle.
- **Onem:** Dusuk · **Guven:** Dogrulanmali (SQLite id yeniden kullanim davranisi tabloya/AUTOINCREMENT kullanimina bagli, dogrulanmadi)

### [RIN-006] Kategori slug'i Turkce buyuk/kucuk harf donusumunde bozulabilir
- **Sorun:** `category = inc.name.lower().replace(" ", "_")` (satir 172). Python'un varsayilan `str.lower()` fonksiyonu Turkce "İ" (noktali buyuk I) karakterini dogru kucultmez; "İş Bankası" gibi bir isim beklenmeyen bir kategori slug'i uretebilir (kombine karakter). Kategori serbest metin oldugu icin (bkz. transactions.py QUICK_KEYWORDS) fonksiyonel bir kirilma yaratmaz ama tutarsiz/estetik olarak bozuk kategori degerlerine yol acar.
- **Kanit:** satir 172; app/action_executor.py satir 48'de zaten `_TR_NORM` adinda bir Turkce karakter normalize tablosu var ama bu dosyada kullanilmiyor.
- **Aksiyon:** Kategori uretiminde `action_executor._TR_NORM` benzeri bir normalize fonksiyonu kullan.
- **Onem:** Dusuk · **Guven:** Kesin
