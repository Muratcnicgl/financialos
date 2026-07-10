# Denetim: app/routers/cockpit.py

### [RCP-001] Router, rules_engine'in zaten urettigi degeri yeniden hesapliyor (mimari ihlali + cift-yuvarlama riski)
- **Sorun:** `_ensure_today_snapshot` icinde `receivables = max(0.0, cockpit.get("net_deger_tam", cockpit["net_deger"]) - cockpit["net_deger"])` satiri, alacaklar tutarini iki ayri ONCEDEN YUVARLANMIS (`round(...,2)`) alanin farkini alarak router icinde yeniden turetiyor. Oysa `generate_cockpit` bu degeri zaten `cockpit["alacaklar_toplami"]` anahtarinda dogrudan (ve yuvarlanmamis, daha hassas) olarak donduruyor (bkz. app/rules_engine.py satir 726 ve 782). PROJE.md'nin acikca soyledigi "Tum matematiksel kararlar rules_engine.py'de verilir, router'a girmez" kurali burada ihlal ediliyor: router kendi basina cikarma islemi yapiyor.
  Ayrica bu iki ayri yuvarlanmis sayinin farkini almak cift-yuvarlama riski tasir: `net_deger` ve `net_deger_tam` ayri ayri `round(x, 2)` ile yuvarlandiktan sonra farklari alindiginda, gercek `alacaklar_toplami` degerinden 0.01 TL sapabilir (ornek: net_deger = round(1000.005, 2) = 1000.0 veya 1000.01 (float temsiline bagli), net_deger_tam = round(net_deger + 234.567, 2); iki yuvarlanmis sayinin farki, dogrudan `alacaklar_toplami`'nin kendisinin yuvarlanmasindan farkli sonuc verebilir).
- **Kanit:** app/routers/cockpit.py satir 37; karsilastirma icin app/rules_engine.py satir 726-727, 782 (`"alacaklar_toplami": alacaklar_toplami` zaten cockpit dict'inde mevcut).
- **Aksiyon:** `receivables = cockpit.get("alacaklar_toplami", 0.0)` seklinde dogrudan rules_engine'in urettigi degeri kullan; router'da tekrar cikarma yapma.
- **Onem:** Yuksek · **Guven:** Kesin (mimari ihlali acik); cift-yuvarlama senaryosunun somut TL etkisi **Dogrulanmali** (spesifik veri ile test edilmeli).

### [RCP-002] Net değer snapshot'i icin check-then-insert atomik degil, DB'de unique constraint yok
- **Sorun:** `_ensure_today_snapshot`, `db.query(NetWorthSnapshot).filter_by(user_id=..., snapshot_date=today).first()` ile "bugun zaten var mi" kontrolu yapip yoksa insert ediyor. Bu iki adim (check + insert) atomik degil (TOCTOU). `NetWorthSnapshot` modelinde (app/models.py satir 492-512) `(user_id, snapshot_date)` uzerinde herhangi bir `UniqueConstraint` yok. FastAPI, `def` (sync) endpoint'leri thread pool'da calistirir; ayni gun icinde cockpit'e neredeyse es zamanli iki istek gelirse (ornegin frontend'in cift render'i, tarayici sekmeleri, ya da retry) her iki thread de "kayit yok" gorup ikisi de insert edebilir — ayni gune ait duplike `NetWorthSnapshot` satirlari olusabilir. Bu, B2 Net Deger Trend Grafiginde ayni gun icin cakisan/yanlis noktalar olarak ortaya cikar.
- **Kanit:** app/routers/cockpit.py satir 34-50; app/models.py satir 492-512 (unique constraint yok).
- **Aksiyon:** Modelde `UniqueConstraint("user_id", "snapshot_date", name="uq_networth_user_date")` ekle; router tarafinda IntegrityError'i yakalayip sessizce gecebilecek sekilde ele al (savepoint pattern — proje hafizasindaki "Savepoint pattern" notuna uygun: `db.rollback()` yerine `db.begin_nested()`).
- **Onem:** Orta · **Guven:** Kesin (constraint eksikligi dogrulandi); gercek race'in pratikte ne siklikta tetiklenecegi **Dogrulanmali**.

### [RCP-003] Sessiz `except Exception: pass` — snapshot hatasi hicbir iz birakmadan yutuluyor
- **Sorun:** Satir 91-94'te `_ensure_today_snapshot` cagrisi etrafinda `except Exception: pass` var — hicbir loglama yok. Bu, TUM hata siniflarini (programlama hatalari, KeyError, AttributeError, DB baglanti hatasi dahil) sessizce yutar. Dosyanin kendi docstring'i (satir 13-17) gecmiste tam bu turden bir hatayi ("int has no attribute query" imza hatasi) yasadigini ve bunun fark edilmesinin zor oldugunu anlatiyor — ayni desen burada tekrar ediyor: eger `_ensure_today_snapshot` ileride bir regresyonla bozulursa (ornegin cockpit dict'ten bir alan kaldirilirsa), net deger gecmisi hic uyari vermeden aylarca kaydedilmeyi durdurabilir ve kullanici bunu ancak trend grafiginde bosluk gorunce fark eder.
  Ayrica commit basarisiz olursa (ornegin gelecekte unique constraint eklenirse ve IntegrityError firlarsa) `db.rollback()` cagrilmadan gecilmesi, session'in kirli/basarisiz transaction durumunda kalmasina yol acabilir (bu istekte baska DB islemi olmadigi icin pratik etkisi sinirli, ama kirilgan bir pattern).
- **Kanit:** app/routers/cockpit.py satir 91-94.
- **Aksiyon:** En azindan `logger.exception("snapshot kaydi basarisiz")` ekle; commit hatasi durumunda `db.rollback()` cagir.
- **Onem:** Orta · **Guven:** Kesin.

### [RCP-004] fund_tracker hatasi genis `except Exception` ile yutuluyor ve ham hata metni API yanitina sizdiriliyor
- **Sorun:** Satir 77-88, `get_freshness_summary` cagrisinda olusabilecek TUM hatalari yakalayip `str(e)`'yi dogrudan `cockpit["price_freshness"]["error"]` alanina koyarak frontend'e donduruyor. Bu hem hatayi sunucu tarafinda loglamadan sessizce maskeliyor (RCP-003 ile ayni desen) hem de olasi ic detaylari (dosya yollari, DB hata mesajlari) API yanitinda disari sizdiriyor. Tek-kullanicili yerel bir uygulama oldugu icin guvenlik riski dusuk, ama hata ayiklamayi zorlastiriyor ve dosyanin kendi docstring'inin uyardigi tam senaryo (sessiz try/except'in gercek bir imza hatasini gizlemesi) ile ayni sinif problem.
- **Kanit:** app/routers/cockpit.py satir 77-88.
- **Aksiyon:** `logger.exception(...)` ile sunucu tarafinda logla; frontend'e `str(e)` yerine sabit/genel bir mesaj don, ham exception metnini disari sizdirma.
- **Onem:** Dusuk · **Guven:** Kesin.

### [RCP-005] `date.today()` sunucu yerel saatini kullaniyor, UTC degil (dosyaya ozgu degil, sistemik)
- **Sorun:** Satir 34 ve 72'de `date.today()` kullaniliyor — bu, sunucunun yerel saat dilimine (muhtemelen Turkiye, UTC+3) gore "bugun"u belirler. PROJE.md'nin datetime kurali DB alanlarinin timezone-naive UTC oldugunu ve frontend'e UTC olarak sunulmasi gerektigini soyluyor; `today` burada gun sinirini (gunluk limit, ay sonu hesaplari, snapshot_date) belirleyen kritik bir deger ve UTC gece yarisi ile yerel gece yarisi arasindaki 3 saatlik fark, gun sinirina yakin (orn. 21:00-24:00 UTC = 00:00-03:00 TR) calisan istekerde "bugun"un hangi gun sayilacagini kaydirabilir.
  Bu desen dosyaya ozgu degil — `app/routers/reports.py`, `expenses.py`, `incomes.py`, `actions.py` de ayni `date.today()` kullanimini paylasiyor, yani sistemik bir konvansiyon. Cockpit dosyasinda tek basina "bug" olarak degil, mevcut sistemik yaklasimla tutarli oldugu icin bilgi amacli isaretleniyor.
- **Kanit:** app/routers/cockpit.py satir 34, 72; karsilastirma: app/routers/reports.py:54,115,164, expenses.py:153, incomes.py:132, actions.py:239,264.
- **Aksiyon:** Sistemik bir karar gerektirir (Wave-3/ADR kapsaminda): ya sunucu saat dilimini UTC'ye sabitle ya da tum `date.today()` kullanimlarini `datetime.utcnow().date()` ile degistir. Sadece bu dosyada duzeltmek tutarsizlik yaratir.
- **Onem:** Dusuk · **Guven:** Dogrulanmali (sunucunun fiili sistem saat dilimi dogrulanmadan kesin hasar iddia edilemez).

### [RCP-006] Satir 37'deki `dict.get` fallback'i pratikte hic tetiklenmeyen olu savunma kodu
- **Sorun:** `cockpit.get("net_deger_tam", cockpit["net_deger"])` — `generate_cockpit`'in donus sozlesmesi her zaman `"net_deger_tam"` anahtarini icerir (app/rules_engine.py satir 781). Bu nedenle `.get()`'in default degeri pratikte hicbir zaman kullanilmaz; kodun "belki bu anahtar olmayabilir" varsayimi mevcut sozlesmeyle celisir ve okuyucuyu yaniltir (anahtarin opsiyonel oldugunu dusundurur).
- **Kanit:** app/routers/cockpit.py satir 37; app/rules_engine.py satir 768-781 (donus dict'i sabit sekilde `net_deger_tam` icerir).
- **Aksiyon:** RCP-001 ile birlikte cozulur — `cockpit["alacaklar_toplami"]` kullanilirsa bu satir zaten kalkar. Kalirsa, dogrudan `cockpit["net_deger_tam"]` kullan (KeyError, sozlesme bozulursa erken ve gurultulu sekilde patlasin — sessizce yanlis deger uretmesin).
- **Onem:** Dusuk · **Guven:** Kesin.
