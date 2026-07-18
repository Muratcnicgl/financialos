# Denetim: app/cashflow.py

> **M86 güncellik:** 🟢 GÜNCEL — CF-001 belgelenmiş sınır; CF-002/003 açık


> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [CF-001] Kredi taksitleri account_id filtresine tabi degil, RecurringExpense ile tutarsiz
- **Sorun:** `generate_forecast` icinde "expenses" chip'i altinda iki farkli kaynak genisletiliyor: `RecurringExpense` (satir 280-287) VE loan hesaplarinin taksitleri (satir 288-293). RecurringExpense sorgusu `account_id` verildiginde `exp_q.filter(RecurringExpense.account_id == account_id)` ile dogru sekilde tek hesaba daraltiliyor (satir 284-285). Ama loan dongusu boyle bir filtre uygulamiyor: `db.query(Account).filter(Account.user_id == user_id, Account.account_type == AccountType.loan)` — account_id parametresi tamamen goz ardi ediliyor. Sonuc: kullanici tek bir nakit hesap icin forecast istediginde (`account_id=X`), o hesaptan hicbir ilgisi olmayan BASKA kredi hesaplarinin taksitleri de o hesabin acilis bakiyesinden dusuluyor.
- **Kanit:** satir 279-293 (ozellikle 284-285 vs 289-293 karsilastirmasi)
- **Aksiyon:** Loan hesabinin hangi nakit hesaptan odendigini belirten bir alan yok (Account modelinde `paying_account_id` benzeri bir FK bulunmuyor — models.py 145-184 kontrol edildi). Ya (a) account_id filtresi verildiginde loan taksitlerini forecast'a hic katma (yalnizca account_id=None/tum-hesaplar gorunumunde katsin), ya da (b) Account modeline "hangi nakit hesaptan odeniyor" alani ekleyip iki dongude de ayni filtreyi uygula.
- **Onem:** Yuksek · **Guven:** Kesin

### [CF-002] monthly_payment isareti dogrulanmiyor — negatif deger taksiti "gelir"e cevirir
- **Sorun:** `_expand_loan_payments` (satir 140-170) yalnizca `not account.monthly_payment` (None/0) kontrolu yapiyor (satir 150), pozitif oldugunu dogrulamiyor. `app/routers/accounts.py` satir 41 ve 65'te `monthly_payment: Optional[float] = None` alaninda `ge=0`/`gt=0` kisiti YOK (oysa ayni satirlarda `remaining_installments` icin `Field(None, ge=0)` var — satir 42, 66). Eger monthly_payment negatif bir deger olarak kaydedilirse, satir 163'teki `-(account.monthly_payment)` ifadesi POZITIF bir tutar uretir ve bu taksit "loan_payment" kaynagiyla nakit GIRISI (income) gibi gorunur — cashflow tablosunda ve sankey'de kredi odemesi yanlislikla gelir kalemine donusur.
- **Kanit:** app/cashflow.py satir 150 ve 163; app/routers/accounts.py satir 41-42, 65-66 (karsilastirma icin)
- **Aksiyon:** `_expand_loan_payments` icinde `account.monthly_payment <= 0` durumunu da erken don (savunmaci kontrol); asil kok neden `app/routers/accounts.py`'deki schema'ya `gt=0` eklemek (bu dosyanin kapsami disinda ama burada dogrudan matematiksel sonucu bozuyor).
- **Onem:** Orta · **Guven:** Dogrulanmali (mevcut test verisinde muhtemelen tetiklenmiyor, sadece kotu/gelecekteki veri girisiyle ortaya cikar)

### [CF-003] Nakit-olmayan veya sahipsiz account_id sessizce 0 acilis bakiyesi uretiyor
- **Sorun:** `account_id` parametresi router seviyesinde (`app/routers/cashflow.py` satir 88-89) hicbir dogrulama gecmiyor — sadece `Optional[int]`. `generate_forecast` icinde `cash_q` sorgusu `Account.account_type == AccountType.cash` VE `Account.id == account_id` birlikte filtreleniyor (satir 261-266). Eger verilen account_id bir kredi karti/kredi/yatirim hesabina aitse veya baska bir kullaniciya aitse, sorgu sessizce bos doner ve `opening_balance = 0` olur (satir 267) — hata firlatilmaz. Kullaniciya "0 TL'niz var, her gun crunch" gibi yaniltici bir forecast donebilir, oysa aslinda gecersiz bir hesap secimi soz konusu.
- **Kanit:** satir 261-267; app/routers/cashflow.py satir 88-89 (dogrulama yok)
- **Aksiyon:** `account_id` verildiginde ilgili hesabin var olup olmadigini ve `account_type == cash` oldugunu kontrol edip yoksa 404 don (router katmaninda, ya da generate_forecast icinde acikca sinyal).
- **Onem:** Orta · **Guven:** Dogrulanmali (frontend gecerli ID'ler gonderdigi surece pratikte tetiklenmez, savunma amacli bulgu)

### [CF-004] VALID_INCLUDE sadece varsayilan deger icin kullaniliyor, gecersiz chip'leri dogrulamak icin degil
- **Sorun:** `VALID_INCLUDE = {"incomes", "expenses", "receivables", "payables"}` (satir 228) yalnizca `include is None` oldugunda varsayilan set olarak kullaniliyor (satir 254-255). Router'da (`app/routers/cashflow.py` satir 107) kullanicidan gelen csv string dogrudan set'e cevrilip hicbir zaman `VALID_INCLUDE` ile kesisim/dogrulama yapilmiyor. Yazim hatali bir chip (orn. "income" yerine "incomes" degil de "gelir") sessizce hicbir sey eslesmedigi icin o kategoriyi tumden disarida birakir, kullaniciya veya cagirana herhangi bir uyari/hata donmez.
- **Kanit:** satir 228, 254-255; app/routers/cashflow.py satir 90-107
- **Aksiyon:** `include - VALID_INCLUDE` bos degilse 400 don (ya router'da ya da generate_forecast basinda), boylece sessiz veri kaybi yerine acik hata alinsin.
- **Onem:** Dusuk · **Guven:** Dogrulanmali

### [CF-005] Overdue next_payment_date, remaining_installments butcesini sessizce tuketiyor
- **Sorun:** `_expand_loan_payments` icinde `idx` sayaci, olay `start`'tan (bugun) once oldugu icin listeye eklenmese bile her dongude artiyor (satir 159-169: `if current >= start:` sadece ekleme kosulu, `idx += 1` bundan bagimsiz her zaman calisiyor). Eger `Account.next_payment_date` gecmiste kaldiysa (odeme yapildi ama alan guncellenmedi, veri bayatligi), o gecmis occurrence "remaining_installments" butcesinden dusulur ve kullaniciya gosterilmeden tuketilir — forecast, kalan taksitlerden birini gostermeden bitirebilir.
- **Kanit:** satir 156-169
- **Aksiyon:** Bu, cogunlukla next_payment_date'in guncel tutulmasina bagli bir veri-tazeligi sorunu (bu dosyanin dogrudan kapsaminda degil), ama fonksiyon savunmaci olarak `current < today` durumunda ileri atlarken idx'i tuketmemeyi tercih edebilir. Yalnizca not amacli.
- **Onem:** Dusuk · **Guven:** Dogrulanmali
