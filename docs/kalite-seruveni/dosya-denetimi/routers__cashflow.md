# Denetim: app/routers/cashflow.py

### [RCF-001] include parametresi validasyonsuz - gecersiz chip'ler sessizce yutuluyor
- **Sorun:** Satir 107'de `include_set = {s.strip() for s in include.split(",") if s.strip()}` uretiliyor ama bu set hicbir yerde `app.cashflow.VALID_INCLUDE = {"incomes","expenses","receivables","payables"}` ile karsilastirilmiyor. Kullanici yazim hatasi yapip `include=incomes,exspenses` gonderirse "exspenses" sessizce yok sayilir, hicbir 400/422 donmez; kullanici "tum giderler dahil" sanirken aslinda gider kalemleri tahmine hic girmez.
- **Kanit:** satir 90-93 (Query tanimi, hicbir validator yok), satir 107 (split + set, dogrulama yok); karsilastirma icin app/cashflow.py satir 228 (`VALID_INCLUDE`) tanimli ama router'da hic kullanilmiyor.
- **Aksiyon:** `include_set - VALID_INCLUDE` bos degilse `HTTPException(422, ...)` firlat; ya da en azindan bilinmeyen chip'leri response'ta/log'da acikca belirt. "Varsayim=hata" prensibine gore sessiz yutma kabul edilmemeli.
- **Onem:** Orta · **Guven:** Kesin

### [RCF-002] account_id sahiplik/tip dogrulamasi yok - baska kullaniciya ait veya nakit-disi hesap sessizce 0 acilis bakiyesi uretir
- **Sorun:** `account_id` Query parametresi (satir 88-89) dogrudan `generate_forecast`'a gecirilir. app/cashflow.py icinde `cash_q` filtresi hem `Account.user_id == user_id` hem `AccountType.cash` sarti tasir (cashflow.py satir 261-267); eger kullanici gecerli ama kendine ait olmayan ya da kredi/kredi karti tipinde bir account_id gonderirse cash_q bos doner, `opening_balance = 0` olur — fakat `exp_q` (cashflow.py satir 280-285) ayni account_id ile RecurringExpense'leri filtreler ve sonuc olarak "acilis bakiyesi 0 ama harcamalar var" gibi anlamsiz, sessizce yanlis bir forecast uretilebilir. Router seviyesinde account_id'nin gercekten `current_user`'a ait bir `cash` hesabi oldugunu dogrulayan hicbir kontrol yok.
- **Kanit:** satir 88-89 (parametre tanimi, aciklama "Belirli hesap ID" der ama tip/sahiplik kontrolu yok), satir 109-116 (dogrudan generate_forecast'a passthrough).
- **Aksiyon:** Router'da account_id verildiginde `Account.user_id == current_user.id AND account_type == cash` sorgusuyla var olup olmadigini dogrula; yoksa 404 don.
- **Onem:** Orta · **Guven:** Dogrulanmali

### [RCF-003] source_type sozlesmesi docstring ile gercek deger arasinda tutarsiz ("loan" vs "loan_payment")
- **Sorun:** `ForecastEventOut.source_type` alaninin yorum satirinda (satir 27) izin verilen degerler `income | recurring_expense | receivable | payable | loan` olarak belgelenmis. Ama app/cashflow.py `_expand_loan_payments` fonksiyonu gercekte `"loan_payment"` string'i uretiyor (app/cashflow.py satir 165). Frontend bu alana gore switch/case yapiyorsa "loan" degerini hic gormeyecek, "loan_payment" beklenmeyen deger olarak dusebilir.
- **Kanit:** satir 27 (docstring/yorum) vs app/cashflow.py satir 165 (`"loan_payment"` literal).
- **Aksiyon:** Docstring'i gercek degerle esitle (`loan_payment`) ya da tam tersi cashflow.py'de "loan" olarak degistir; ikisi ayni sozlesmeyi konusmali.
- **Onem:** Dusuk · **Guven:** Kesin

### [RCF-004] amount == 0 olan olaylar router'da "receivable" olarak etiketlenirken sankey grafiginde hic gorunmuyor
- **Sorun:** Satir 123'te `type="receivable" if ev.amount >= 0 else "payable"` kullaniliyor (`>=`), yani tutari tam 0 olan bir olay "receivable" olarak siniflandirilir ve `days[].events` listesinde gorunur. Ama app/cashflow.py `_build_sankey` fonksiyonu (app/cashflow.py satir 186-190) sadece `ev.amount > 0` veya `ev.amount < 0` olan olaylari sankey node/link'lerine ekliyor — `amount == 0` olan bir olay sankey'de hic yer almiyor. Aynı sekilde `total_receivable`/`total_payable` toplamlari da `> 0` / `< 0` siki karsilastirmasi kullaniyor (app/cashflow.py satir 343-344), yani 0 tutarli olay summary toplamlarina da girmiyor. Sonuc: gunluk event listesinde "receivable" gorunen bir kayit, sankey diyagraminda ve toplam istatistiklerde yok sayiliyor — ayni veri seti icinde iki farkli siniflandirma kurali cakisiyor.
- **Kanit:** satir 123 (router, `>=` kullanimi) vs app/cashflow.py satir 186-190 ve 343-344 (siki `>`/`<`).
- **Aksiyon:** Sifir tutarli olaylar icin tek bir tutarli kural belirle (orn. tumunde `> 0` kullan, ya da 0 tutarli olaylari en bastan filtrele/uretme). Pratikte 0 TL'lik bir recurring income/expense veya PersonalDebt olusmasi beklenmez ama veri girisinde 0 tutar engellenmiyorsa bu tutarsizlik gercek bir bug'a donusur.
- **Onem:** Dusuk · **Guven:** Dogrulanmali (0 tutarli kayit olusturmanin DB seviyesinde engellenip engellenmedigi ayrica kontrol edilmeli)

### [RCF-005] crunch_threshold icin sinir/ozel deger (NaN/Infinity) validasyonu yok
- **Sorun:** Satir 94-97'de `crunch_threshold: float = Query(default=0.0, ...)` tanimlanirken `ge`/`le` gibi hicbir sinir konmamis. Python/Pydantic float parse'i "inf", "-inf", "nan" gibi string sorgu parametrelerini kabul edebilir (JSON-uyumlu olmayan ozel float degerleri). `crunch_threshold=nan` gonderilirse app/cashflow.py satir 333'teki `balance < crunch_threshold` karsilastirmasi NaN ile her zaman False doner, yani crunch tespiti tamamen sessizce devre disi kalir ama endpoint hata vermez, kullanici "crunch yok" sanip yanlis guven duyar.
- **Kanit:** satir 94-97 (Query tanimi, sinir yok) + app/cashflow.py satir 333 (`balance < crunch_threshold`).
- **Aksiyon:** `crunch_threshold` icin makul bir aralik (`ge=-1_000_000, le=1_000_000` gibi) ekle ve NaN/Infinity durumlarini FastAPI/Pydantic seviyesinde reddet.
- **Onem:** Dusuk · **Guven:** Dogrulanmali (Pydantic v2'nin bu ozel string degerleri hangi surumde/ayarda kabul ettigi tam dogrulanmadi)

### [RCF-006] Cift-yuvarlama / float-para birikimi riski (cashflow.py kaynakli, router ciktisina yansiyor)
- **Sorun:** app/cashflow.py'de her gun icin `day.inflows`/`day.outflows` 2 ondalige yuvarlanip (satir 330-331) sonraki gunun `balance` degeri bu yuvarlanmis degerler uzerinden **yeniden** toplanip tasiniyor (satir 328: `balance = balance + day.inflows + day.outflows`, sonra tekrar satir 329'da `round(balance,2)`), 180 gunluk bir horizon'da IEEE-754 float toplama hatalari birikebilir (klasik "0.1+0.2" problemi TL bazinda). Router bu degerleri oldugu gibi `ForecastDayOut`/`ForecastSummary` alanlarina tasiyor, ek bir dogrulama/duzeltme yapmiyor.
- **Kanit:** app/cashflow.py satir 328-331 (round + tekrar toplama dongusu); router satir 131-139 (degerler dogrudan Pydantic modeline aktariliyor).
- **Aksiyon:** Para hesaplarinda kurus/cent bazli `int` veya `Decimal` kullanimi degerlendirilmeli; en azindan 180 gunluk uzun horizon'larda birikmis hatanin (TL bazinda anlamli buyuklukte olup olmadigi) test edilmesi onerilir.
- **Onem:** Dusuk · **Guven:** Dogrulanmali (pratikte 2 ondalik yuvarlama nedeniyle hata payi cok kucuk kalabilir, ama prensip olarak float-para riski mevcut)
