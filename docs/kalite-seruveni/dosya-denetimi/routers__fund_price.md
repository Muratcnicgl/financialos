# Denetim: app/routers/fund_price.py

> **M86 güncellik:** 🟢 GÜNCEL — RFP-001/002/003/004 geçerli


> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [RFP-001] Timestamp alani timezone-naive donuyor, PROJE.md kuralini ihlal ediyor
- **Sorun:** `FundPriceUpdateResponse.timestamp: str` alani, `app/fund_tracker.py`'deki `update_fund_price_manual()` fonksiyonunun urettigi `account.last_price_update.isoformat()` degerini oldugu gibi tasiyor (fund_price.py satir 112, kaynak: fund_tracker.py satir 131 `datetime.utcnow()` + satir 149 `.isoformat()`). `datetime.utcnow()` timezone-naive bir deger uretir; `.isoformat()` bu deger uzerinde cagrilinca suffix'siz string uretir (orn. `2026-07-10T14:00:00.123456`, `+00:00` yok). `app/PROJE.md` ve `docs/architecture.md` acikca bu davranisi "eksik birakirsan JS Turkiye saatinde 3 saat geri gosterir" seklinde bug olarak tanimliyor ve `tzinfo=timezone.utc` eklenmesini zorunlu kiliyor. Bu router bunu yapmiyor.
- **Kanit:** satir 112 (`timestamp=result["timestamp"]`), kaynak fund_tracker.py satir 131 ve 149
- **Aksiyon:** `update_fund_price_manual` icinde (veya router'da response olusturulurken) `account.last_price_update.replace(tzinfo=timezone.utc).isoformat()` kullanilarak aware ISO string uretilmeli. Ayni sekilde `get_freshness_summary`'deki `last_update` alani da (fund_tracker.py satir 191) ayni sorunu tasiyor ve `/freshness` endpoint'i uzerinden (satir 133) oldugu gibi frontend'e geciyor.
- **Onem:** Kritik · **Guven:** Kesin

### [RFP-002] GET /freshness response_model kullanmiyor — kirilgan cikti sozlesmesi
- **Sorun:** `get_freshness` endpoint'i (satir 117-133) donus tipini sadece `-> dict` olarak isaretliyor, Pydantic `response_model` tanimlanmamis. `get_freshness_summary()` fonksiyonunun urettigi dict'in sekli (`total_investments`, `stale_count`, `never_set_count`, `items[...]`) sadece docstring'de belgeleniyor; fund_tracker.py'de bu sozluk degisirse (alan adi degisir/silinir) FastAPI hicbir validasyon veya hata vermeden bozuk veri donebilir, frontend sessizce kirilir. Diger iki endpoint (`/update`, `/tefas-link/{fund_code}`) response_model kullaniyor, bu endpoint tutarsiz.
- **Kanit:** satir 117-121, 133
- **Aksiyon:** `FreshnessSummaryResponse` / `FreshnessItem` Pydantic modelleri tanimlanip `response_model` olarak baglanmalidir; boylece hem sema garantisi hem otomatik dokuman (Swagger) dogru cikar.
- **Onem:** Orta · **Guven:** Kesin

### [RFP-003] Kullanilmayan import: `datetime`
- **Sorun:** Satir 18'de `from datetime import datetime` import ediliyor ama dosyanin geri kalaninda `datetime` sembolu hic kullanilmiyor (tum datetime islemleri fund_tracker.py icinde yapiliyor).
- **Kanit:** satir 18
- **Aksiyon:** Kullanilmayan import silinsin. (Alternatif olarak RFP-001 fix'i bu router'da yapilirsa `datetime`/`timezone` gercekten kullanilir hale gelir.)
- **Onem:** Dusuk · **Guven:** Kesin

### [RFP-004] fund_code path parametresi sanitize edilmeden URL'e ekleniyor
- **Sorun:** `tefas_link` endpoint'i (satir 136-145) `fund_code` path parametresini dogrudan `fund_code.upper()` ile `get_tefas_url()`'e geciriyor, bu da f-string ile TEFAS URL'ine ekleniyor (`fund_tracker.py` satir 81). `fund_code` icin herhangi bir karakter/format dogrulamasi (alfanumerik, uzunluk vb.) yok. Path parametresine `&`, `#`, `%23` gibi karakterler girilirse uretilen URL'e ekstra query-string/fragment enjekte edilebilir; bu endpoint auth gerektirmedigi icin (Depends(get_current_user) yok) herhangi bir cagiran keyfi fund_code ile URL uretebilir ve donen linki paylasabilir.
- **Kanit:** satir 136-145; get_tefas_url tanimi fund_tracker.py satir 76-81
- **Aksiyon:** `fund_code` icin regex/whitelist dogrulama (`^[A-Za-z0-9]{2,10}$` gibi) eklenmesi onerilir; ayrica bu endpoint kullanici-spesifik veri donmedigi icin auth gereksinimi olup olmadigi netlestirilmeli (su an DB'ye erismiyor, dusuk risk).
- **Onem:** Dusuk · **Guven:** Dogrulanmali

### [RFP-005] Para hesaplamasi float ile yapiliyor (round-based), Decimal degil
- **Sorun:** `update_fund_price_manual` icinde (fund_tracker.py satir 126-127) `old_value = round((old_price or 0) * lot_count, 2)` ve `new_value = round(new_price * lot_count, 2)` float aritmetigi kullaniyor. Router bu degerleri dogrudan `FundPriceUpdateResponse.new_value: float` olarak disari veriyor (fund_price.py satir 110) ve `Account.balance` bu float deger ile guncelleniyor. Float ile carpim + round, ozellikle kucuk lot_count/fiyat kombinasyonlarinda ondalik yuvarlama sapmasi uretebilir (orn. `0.1 * 3 = 0.30000000000000004` gibi klasik float temsil hatalari), ve tekrarlanan guncellemelerde kumulatif sapma birikebilir.
- **Kanit:** fund_price.py satir 109-111 (float degerleri response'a tasiyor); fund_tracker.py satir 126-127
- **Aksiyon:** Para/lot hesaplarinda `Decimal` kullanilmasi, sadece disariya donerken float'a cevrilmesi onerilir. Router degisikligi gerekmez ama fund_tracker.py'deki formul duzeltilirse response otomatik dogrulanir.
- **Onem:** Orta · **Guven:** Dogrulanmali

### [RFP-006] never_set_count, emanet hesaplari icin de sayiliyor — stale_count ile tutarsiz muafiyet
- **Sorun:** `get_freshness_summary` (fund_tracker.py satir 176-183) `stale_count` hesaplanirken `if stale and not inv.is_emanet` seklinde emanet hesaplari acikca hariç tutuyor ("Emanet icin uyari cikarmiyoruz" yorumu), ama `never_set_count += 1` satirinda boyle bir muafiyet yok — emanet hesabin fiyati hic girilmemisse yine de `never_set_count`'a dahil oluyor. Bu, Cockpit'te emanet hesaplar icin gosterilmesi istenmeyen bir uyari turunun (hic girilmemis fiyat) sizmasina yol acabilir; is kuralinin kasitli mi yoksa gozden kacmis mi oldugu net degil.
- **Kanit:** fund_tracker.py satir 180-183; router bu degeri oldugu gibi /freshness uzerinden geciyor (fund_price.py satir 133)
- **Aksiyon:** Urun/is kurali netlestirilmeli: never_set_count da emanet'i hariç tutmali mi? Netlesince fund_tracker.py'de tek satirlik guard eklenebilir.
- **Onem:** Dusuk · **Guven:** Dogrulanmali
