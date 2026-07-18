# Denetim: app/routers/debts.py

> **M86 güncellik:** 🔴 BAYAT — RDE-001/002/003 düzeltildi (BUG#106); RDE-004+ düşük


> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [RDE-001] is_paid/paid_date senkronizasyon mantigi celiskili payload'da tutarsiz durum uretiyor
- **Sorun:** update_debt (satir 120-128) once tum alanlari ham payload'daki degerlerle setattr ile yazar, sonra iki bagimsiz "akilli senkronizasyon" kurali sirayla uygulanir: (1) "paid_date" gonderilmisse is_paid = (paid_date is not None), (2) "is_paid" gonderilmis ve False ise paid_date = None. Bu iki kural ayni payload icinde CELISKILI degerler gonderildiginde (orn. hem paid_date hem is_paid=False beraber) birbirini eziyor ve nihai state hicbir zaman istenen durum olmuyor.
- **Kanit:** satir 120-128. Somut senaryo: PUT /api/debts/{id} body = {"paid_date": "2026-05-05", "is_paid": false}. Sirasiyla: loop -> debt.paid_date=2026-05-05, debt.is_paid=False. Sonra (1). kural calisir: "paid_date" update_data'da var -> debt.is_paid = True (paid_date None degil). Sonra (2). kural calisir: update_data["is_paid"] is False -> debt.paid_date = None. NIHAI SONUC: debt.is_paid=True, debt.paid_date=None — yani borc "odendi" isaretlenmis ama hangi tarihte odendigi kayitli degil. Bu durum, is_paid=True + paid_date=None ile tek basina is_paid=True gonderilip paid_date hic gonderilmedigi durumda da (satir 121'deki loop ile dogrudan) olusabiliyor; hicbir dal paid_date'i otomatik bugune set etmiyor (action_executor.py:515-517'deki `_execute_mark_debt_paid` boyle bir varsayilan icerirken, bu router'da yok).
- **Aksiyon:** Senkronizasyon kurallarini tek bir if/elif zincirine indir (ikisi ayni update icinde celisirse acikca hangisinin ustun oldugunu belirle, veya HTTPException 400 firlat) VE is_paid=True gonderilip paid_date verilmemisse action_executor.py'deki pattern'e paralel olarak paid_date = date.today() varsayilani uygula.
- **Onem:** Yuksek · **Guven:** Kesin

### [RDE-002] Tutarsiz is_paid=True + paid_date=None kayitlar rules_engine/cashflow/reports hesaplarindan sessizce dusuyor
- **Sorun:** rules_engine.py (satir 356, 433, 467, 550), cashflow.py (satir 117), reports.py (satir 172, 184) hepsi `PersonalDebt.is_paid == False` filtresiyle "odenmemis" borc/alacaklari hesaba katiyor. RDE-001'deki bug nedeniyle debts.py uzerinden is_paid=True + paid_date=None durumuna dusen bir kayit, gercekte hicbir odeme/tahsilat yapilmamis olmasina ragmen "beklenen gelir", "borc takvimi" ve raporlardan tamamen kaybolur — kullanicinin gercek nakit pozisyonuyla sistemdeki gorunum arasinda sessiz bir tutarsizlik (sanal kayip) olusur.
- **Kanit:** satir 125-128 (debts.py) + rules_engine.py:356,433,467,550 + cashflow.py:117 + reports.py:172,184 (referans, dosya disi).
- **Aksiyon:** RDE-001 duzeltilince bu da cozulur; ayrica is_paid=True ama paid_date=None olan kayitlar icin bir DB-seviyesi CHECK constraint veya en azindan router seviyesinde validasyon (is_paid=True iken paid_date zorunlu) eklenebilir.
- **Onem:** Kritik · **Guven:** Kesin

### [RDE-003] created_at alani timezone-naive olarak frontend'e donuyor
- **Sorun:** PROJE.md / docs/architecture.md acikca sart kosuyor: frontend'e tarih donen her endpoint'te serialize oncesi `tzinfo=timezone.utc` eklenmeli, aksi halde JS Turkiye saatinde 3 saat geri gosterir. DebtOut.created_at (satir 53) dogrudan modelden (models.py:261 `Column(DateTime, default=datetime.utcnow)` — naive) from_attributes ile map ediliyor, hicbir yerde tzinfo eklenmiyor.
- **Kanit:** satir 49-56 (DebtOut), models.py:261.
- **Aksiyon:** DebtOut icin bir field_validator/model_validator ekleyip created_at'i `v.replace(tzinfo=timezone.utc)` ile aware'e cevir (coach.py'deki `_memory_to_history_item` pattern'i referans alinabilir).
- **Onem:** Orta · **Guven:** Kesin

### [RDE-004] session.query() legacy pattern kullaniliyor (app/PROJE.md ihlali)
- **Sorun:** app/PROJE.md acikca "SQLAlchemy 2.x: select()/session.execute() tercih edilir; session.query() eski pattern" diyor. Dosyadaki tum sorgular (list_debts, update_debt, delete_debt) `db.query(...)` kullaniyor.
- **Kanit:** satir 76, 114, 142.
- **Aksiyon:** `select(PersonalDebt).where(...)` + `db.execute(...).scalars()` pattern'ine gecir. (Not: bu pattern repo genelinde yayginlasmis — action_executor.py, rules_engine.py de ayni sekilde — dolayisiyla izole bir debts.py degisikligi tutarsizlik yaratabilir; proje capinda ele alinmasi daha dogru olabilir.)
- **Onem:** Dusuk · **Guven:** Kesin

### [RDE-005] update_debt "zaten odendi" korumasi yok, action_executor ile asimetrik
- **Sorun:** action_executor.py `_execute_mark_debt_paid` icinde debt.is_paid ise islemi reddediyor ("Bu borc zaten odenmiş olarak isaretli", satir 511-512). debts.py'deki update_debt ise boyle bir koruma icermiyor; zaten odenmis bir borcun paid_date'i sessizce degistirilebiliyor veya is_paid tekrar True/False arasinda gidip gelebiliyor. Bu, iki farkli "borc odeme" yolunun (LLM onayli propose/execute akisi vs. dogrudan frontend PUT) farkli davranis sergilemesi anlamina geliyor.
- **Kanit:** satir 102-132 (koruma yok) vs action_executor.py:511-512 (koruma var).
- **Aksiyon:** Bilinçli bir tasarim tercihiyse (frontend'in serbestce duzeltme yapmasina izin vermek) docstring'e not dusulmeli; degilse ayni "zaten odendi" korumasi eklenmeli.
- **Onem:** Dusuk · **Guven:** Dogrulanmali

### [RDE-006] DebtUpdate uzerinden direction (borc/alacak yonu) degistirilemiyor
- **Sorun:** DebtBase.direction alani DebtUpdate'e dahil edilmemis (satir 40-46). Kullanici "alacak" yerine yanlislikla "borc" girdiginde duzeltme yapmak icin kaydi silip yeniden olusturmak zorunda kaliyor; bu da id/created_at kaybina yol aciyor.
- **Kanit:** satir 40-46 (DebtBase.direction satir 30 ile karsilastir).
- **Aksiyon:** Kasitli bir tasarim ise (yon degisikligi riskli/nadirdir) sorun yok; degilse DebtUpdate'e Optional[DebtDirection] eklenebilir.
- **Onem:** Dusuk · **Guven:** Dogrulanmali

### [RDE-007] Para tutarlari Float olarak tutuluyor, yuvarlama/hassasiyet kontrolu yok
- **Sorun:** amount alani `float` (satir 31, 42) ve DB'de `Column(Float, ...)` (models.py:256). Ondalikli TL tutarlarinda ikili float temsili klasik yuvarlama hatalarina acik (orn. 0.1 + 0.2 gibi durumlar biriken islemlerde kayma yaratabilir). Dosyada round()/Decimal kullanimi yok.
- **Kanit:** satir 31, 42.
- **Aksiyon:** Bu proje genelinde tercih edilen bir tasarim (Float) gibi gorunuyor; izole degisiklik onerilmez ama proje capinda Decimal/kurus-bazli integer'a gecis degerlendirilebilir. Su an icin dusuk oncelikli not.
- **Onem:** Dusuk · **Guven:** Dogrulanmali

### [RDE-008] schemas.py'de kullanilmayan paralel PersonalDebt* semalari (dead code, iliskili dosya)
- **Sorun:** app/schemas.py icinde PersonalDebtBase/Create/Update/Read tanimli ama hicbir router bunlari import etmiyor (debts.py kendi lokal DebtBase/Create/Update/Out semalarini kullaniyor). Iki paralel sema seti kafa karistirici olabilir ve gelecekte yanlislikla eski/yanlis semaya import yapilma riski yaratir.
- **Kanit:** app/schemas.py:125-147 (dosya disi, debts.py'yi dogrudan etkilemiyor ama iliskili).
- **Aksiyon:** schemas.py'deki kullanilmayan PersonalDebt* siniflarini kaldir veya debts.py'nin bunlari kullanmasini sagla.
- **Onem:** Dusuk · **Guven:** Dogrulanmali
