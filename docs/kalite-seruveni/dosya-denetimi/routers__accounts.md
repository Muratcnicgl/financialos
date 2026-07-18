# Denetim: app/routers/accounts.py

> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [RAC-001] Datetime alanlari tzinfo=utc olmadan frontend'e donuyor
- **Sorun:** AccountOut icindeki last_price_update, created_at, updated_at alanlari ORM'den direkt Pydantic'e geciyor. app/PROJE.md kurali acik: "Frontend'e tarih donen her endpoint'te serialize oncesi tzinfo=timezone.utc ekle" -- aksi halde Pydantic suffix'siz ISO string yayar, JS bunu local time sanip Turkiye saatinde 3 saat geri gosterir. Bu dosyada hicbir yerde tzinfo eklenmiyor (create_account, get_account, update_account, list_accounts hepsi ayni AccountOut'u donuyor).
- **Kanit:** satir 77-79 (AccountOut alan tanimlari), satir 121/187 (last_price_update = datetime.utcnow() -- naive atama), satir 101/126/142/191 (response donusleri)
- **Aksiyon:** AccountOut icin bir field_serializer veya response donmeden once acc.created_at.replace(tzinfo=timezone.utc) tarzi donusum ekle (coach.py'deki _memory_to_history_item pattern'i referans alinabilir).
- **Onem:** Yuksek · **Guven:** Kesin

### [RAC-002] session.query() kullanimi -- PROJE.md SQLAlchemy 2.x kuraliyla celisiyor
- **Sorun:** app/PROJE.md acikca "SQLAlchemy 2.x: select()/session.execute() tercih edilir; session.query() eski pattern" diyor. Dosyadaki tum sorgular eski query() API'sini kullaniyor.
- **Kanit:** satir 98, 136-139, 163-166, 207-210
- **Aksiyon:** db.execute(select(Account).where(...)).scalars().first()/.all() seklinde SQLAlchemy 2.x idiomuna gecir.
- **Onem:** Orta · **Guven:** Kesin

### [RAC-003] create_account'ta otomatik bakiye hesaplamasi kullanicinin acikca girdigi balance'i sessizce eziyor
- **Sorun:** update_account'ta "kullanici acikca balance gonderirse otomatik hesap DEVRE DISI kalir" korumasi var (satir 171, 179 user_specified_balance kontrolu). create_account'ta ayni koruma YOK: kullanici hem balance hem lot_count/current_price gonderirse (ornegin manuel dogrulanmis bir bakiye girmek isterse), lot_count*current_price hesaplamasi kullanicinin gonderdigi balance degerini sessizce eziyor. Iki endpoint arasinda tutarsiz davranis + sessiz veri kaybi.
- **Kanit:** satir 111-117 (data.get("balance") kontrolu yok, kosulsuz overwrite)
- **Aksiyon:** create_account'a da update_account'taki gibi "kullanici balance'i acikca gonderdiyse otomatik hesabi atla" kontrolu ekle (orn. "balance" alani payload'da model_fields_set icinde mi diye bak).
- **Onem:** Orta · **Guven:** Kesin

### [RAC-004] delete_account: transaction'i olan hesap silinirse ham SQL/IntegrityError kullaniciya sizabilir
- **Sorun:** Docstring bunu zaten itiraf ediyor ("Su an cascade=None oldugundan transaction varken silmeye calisirsa SQL hatasi doner"), ama kod hala bu durumu yakalamiyor. db.delete(acc); db.commit() cagrisinda FK constraint ihlali IntegrityError firlatir, bu da FastAPI'de yakalanmadigi icin 500 + stack trace olarak kullaniciya/loglara sizar (potansiyel bilgi sizintisi + kotu UX).
- **Kanit:** satir 203-205 (bilinen-ama-cozulmemis TODO), satir 220-221 (try/except yok)
- **Aksiyon:** db.delete/commit'i try/except IntegrityError ile sar, db.rollback() sonrasi HTTPException(409, "Bu hesaba bagli islemler var, once onlari silin") don.
- **Onem:** Yuksek · **Guven:** Kesin

### [RAC-005] update_account: current_price aciktan None'a set edilirse last_price_update yine de "simdi" olarak guncelleniyor
- **Sorun:** price_changed = "current_price" in update_data yalnizca alanin payload'da bulunup bulunmadigina bakiyor, degerin None olup olmadigina bakmiyor. Kullanici current_price: null gonderip fiyati temizlerse (ornek: fon takibi durduruluyor), last_price_update yine de datetime.utcnow() ile "az once fiyat guncellendi" gibi isaretleniyor -- aslinda fiyat silindi, guncellenmedi.
- **Kanit:** satir 172 (price_changed hesaplamasi), satir 186-187 (kosulsuz utcnow() atamasi)
- **Aksiyon:** price_changed = update_data.get("current_price") is not None seklinde daraltilmali, ya da None atamasinda last_price_update de None'a cekilmeli.
- **Onem:** Dusuk · **Guven:** Dogrulanmali

### [RAC-006] Para alanlari icin Float kolon + float carpim -- kumulatif yuvarlama riski
- **Sorun:** models.py'de balance/credit_limit/lot_count/current_price hepsi Column(Float). create_account (satir 117) ve update_account (satir 183) icinde balance = float(lot_count) * float(current_price) ikili kayan nokta carpimi ile hesaplaniyor. Kucuk lot sayilari ve coklu ondalikli fiyatlarla (TEFAS fonlarinda yaygin) IEEE-754 yuvarlama hatasi birikebilir; bu deger sonra rules_engine.py'nin cockpit hesaplarina girdi olarak kullanilir.
- **Kanit:** satir 117, 183; models.py satir 154/170-172 (Float kolon tanimlari)
- **Aksiyon:** Round(..., 2) ile son degeri normalize et veya Decimal'e gecisi Wave-3 icin degerlendir. Minimum: balance = round(float(lot_count) * float(current_price), 2).
- **Onem:** Orta · **Guven:** Dogrulanmali

### [RAC-007] Para/oran alanlarinda negatif deger validasyonu yok
- **Sorun:** credit_limit, interest_rate, monthly_payment, lot_count, cost_per_lot, current_price alanlarinin hicbirinde ge=0 kisiti yok (statement_day/payment_day/remaining_installments'ta var). Negatif credit_limit veya negatif current_price gonderilirse sessizce kabul edilir, balance = lot_count * current_price negatif cikabilir ve rules_engine'e hatali deger sizar.
- **Kanit:** satir 36, 40-41, 46-48 (Field kisitlari eksik)
- **Aksiyon:** Field(None, ge=0) ekle (interest_rate icin ust sinir da dusunulebilir).
- **Onem:** Dusuk · **Guven:** Dogrulanmali
