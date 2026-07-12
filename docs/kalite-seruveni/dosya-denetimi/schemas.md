# Denetim: app/schemas.py

### [SH-001] Dosyanin buyuk cogunlugu (satir 12-249) olu kod
- **Sorun:** `TimestampedSchema`, `AccountBase/Create/Update/Read`, `RecurringIncomeBase/Create/Update/Read`, `TransactionBase/Create/Read`, `PersonalDebtBase/Create/Update/Read`, `MasterCheckpointBase/Create/Read`, `CoachMessageRequest`, `ProposedAction`, `CoachMessageResponse`, `CoachMemoryRead`, `PendingActionRead`, `ActionDecision`, `CockpitSnapshot` siniflarinin hicbiri projede baska hicbir yerden referans edilmiyor. Repo genelinde `app.schemas` yalnizca `app/routers/goals.py` icinde import ediliyor (`from app import models, schemas`) ve sadece `schemas.Goal*` siniflari (satir 256-346) kullaniliyor. `app/routers/user.py` da schemas kelimesini iceriyor ama kendi yorumunda acikca "router-yerel, schemas.py'yi kirletmeyiz" diyerek kendi lokal Pydantic modellerini tanimliyor. `app/routers/transactions.py` da ayni sekilde kendi lokal `TransactionCreate` sinifini tanimliyor (schemas.py'deki `TransactionBase`/`TransactionCreate` ile isim cakismasi var ama farkli sinif, kullanilmiyor).
- **Kanit:** satir 12-249 (tum AccountBase/Create/Update/Read, RecurringIncomeBase/Create/Update/Read, TransactionBase/Create/Read, PersonalDebtBase/Create/Update/Read, MasterCheckpointBase/Create/Read, CoachMessageRequest/Response, ProposedAction, CoachMemoryRead, PendingActionRead, ActionDecision, CockpitSnapshot); dogrulama: `grep -r "schemas\." app/` sonucu sadece `goals.py` icinde `schemas.Goal*` cagrilari donuyor.
- **Aksiyon:** Bu bloklari ya silin ya da gercekten kullanilan router'lara baglayin. Olu kod, "hangi sema gercekten API sozlesmesi" sorusunu belirsizlestiriyor ve gelecekte birileri bu semalari guncelleyip gercek davranisin degistigini sanabilir (orn. AccountBase'e alan eklenirse hicbir efekti olmaz, yanlis guven verir).
- **Onem:** Yuksek · **Guven:** Kesin

### [SH-002] GoalUpdate.status alaninda "achieved" kullaniciya direkt PATCH ile acik — Rules Engine prensibini deliyor
- **Sorun:** `GoalUpdate.status: Optional[Literal["active", "achieved", "paused", "abandoned"]]` (satir 267) API tuketicisinin `PATCH /api/goals/{id}` ile status'u dogrudan `"achieved"` yapmasina izin veriyor. `app/routers/goals.py:131-132` bu degeri `setattr(goal, field, value)` ile hicbir ek kontrol olmadan DB'ye yaziyor; `achieved_at` alani ayarlanmiyor (sadece `app/goal_engine.py:188-189` gercek hesaplamada hem `status="achieved"` hem `achieved_at=datetime.utcnow()` birlikte set ediyor). Sonuc: kullanici hedefe hicbir katki yapmadan (current_amount < target_amount) goal'i "achieved" isaretleyebilir, `achieved_at` NULL kalir ama `status="achieved"` gorunur — PROJE.md'nin "Rules Engine karar verir" ilkesine ve kok vizyonun "sanal zenginlik yasak" kuraline aykiri sanal/asilsiz bir basari durumu.
- **Kanit:** schemas.py satir 267 (GoalUpdate.status literal'i "achieved" iceriyor); capraz referans app/routers/goals.py satir 131-132 (kosulsuz setattr); app/goal_engine.py satir 188-189 (gercek "achieved" gecisi achieved_at ile birlikte olmali).
- **Aksiyon:** `GoalUpdate.status` literal kumesinden "achieved"i cikarin (kullaniciya sadece "active"/"paused"/"abandoned" birakin) — "achieved" durumuna gecis yalnizca `goal_engine.py` icindeki hesaplama tarafindan, `refresh_goal` akisinda yapilmali.
- **Onem:** Kritik · **Guven:** Kesin

### [SH-003] Para alanlari icin float kullanimi (Decimal degil) — birikimli yuvarlama riski
- **Sorun:** `AccountBase.balance`, `credit_limit`, `interest_rate`, `monthly_payment`, `lot_count`, `cost_per_lot`, `current_price` (satir 24, 28, 33-34, 40-42), `TransactionBase.amount` (satir 107), `PersonalDebtBase.amount` (satir 128), `CockpitSnapshot` icindeki tum parasal alanlar (satir 230-249) `float` tipinde. Buna karsilik, sonradan eklenen H2G5 Goal Engine (satir 259, 265, 277-278, 281-282, 292, 301, 312, 331, 344) bilincli olarak `Decimal` kullaniyor — dosyanin kendi icinde iki farkli para temsili standardi var. `float` ile yapilan tekrarli toplama/cikarma (orn. cok sayida transaction uzerinden balance guncellemesi) klasik ikili kayan nokta yuvarlama hatalarina acik (orn. 0.1 + 0.2 == 0.30000000000000004 gibi), TL bazinda kucuk ama gozlemlenebilir sapmalar birikebilir.
- **Kanit:** satir 24, 28, 33-42 (AccountBase), satir 107 (TransactionBase.amount), satir 128 (PersonalDebtBase.amount), satir 230-249 (CockpitSnapshot) vs. satir 259+ (Goal Engine Decimal kullanimi). DB tarafi da tutarli olarak Float (`app/models.py` satir 154, 158, 163-172, 193, 210, 229, 256) oldugu icin bu schemas.py'ye ozgu degil, ama para-matematigi denetimi kapsaminda bayrak.
- **Aksiyon:** Yeni gelistirmede tum yeni parasal alanlar icin Decimal standardize edin (Goal Engine gibi); mevcut Account/Transaction/PersonalDebt icin Decimal'e gecis buyuk bir migration gerektirir, bu yuzden kisa vadede en azindan rules_engine.py'de toplamalarin round() ile kontrollu yapildigini dogrulayin (bu dosyanin kapsami disinda, ayri denetim onerilir).
- **Onem:** Orta · **Guven:** Dogrulanmali (float birikimli hata pratikte SQLite Float REAL 8-byte double precision ile TL tutarlarinda genelde gozle gorulmeyecek kadar kucuk kalir, ama ilke ihlali kesin)

### [SH-004] TransactionBase.amount ve PersonalDebtBase.amount icin pozitiflik/sifir kisitlamasi yok
- **Sorun:** `TransactionBase.amount: float` (satir 107) hicbir `gt=0` veya `ne=0` kisitlamasi tasimiyor; ayni sekilde `PersonalDebtBase.amount: float` (satir 128) de kisitlamasiz. Sema seviyesinde negatif veya sifir tutarli islem/alacak gecebilir. (Not: bu sema kullanilmiyor — SH-001 — ama eger ileride tekrar bir router'a baglanirsa bu kontrolsuzluk devreye girer; ayrica gercek kullanimda olan `app/routers/transactions.py` kendi lokal semasinda da `amount: Optional[float]` icin sinir tanimlamiyor, sadece router body'sinde runtime `if amount <= 0` kontrolu var — sema seviyesinde degil.)
- **Kanit:** satir 107, 128; capraz referans app/routers/transactions.py satir 265-266 (runtime kontrol, schema constraint degil).
- **Aksiyon:** Eger bu semalar canlandirilacaksa `amount: float = Field(gt=0)` gibi bir kisit eklenmeli; boylece validation router kod tekrari yerine sema seviyesinde garanti edilir.
- **Onem:** Dusuk · **Guven:** Kesin (olu kod oldugu icin etkisi sinirli)

### [SH-005] TransactionBase.transaction_date icin date.today() sunucu yerel saatine bagli
- **Sorun:** `transaction_date: date = Field(default_factory=date.today)` (satir 110) sunucunun yerel saat dilimini kullanir. PROJE.md/architecture.md UTC-naive standardini DateTime alanlari icin tanimliyor; `date.today()` ise isletim sistemi yerel saatine gore "bugun"u hesaplar. Gece yarisina yakin (orn. TR saatiyle 00:00-03:00 UTC farki) sunucu farkli bir zaman diliminde calisirsa transaction_date bir gun kayabilir. (Bu sema kullanilmadigi icin risk teorik, ama kalip olarak yanlis.)
- **Kanit:** satir 110.
- **Aksiyon:** UTC bazli `datetime.utcnow().date()` kullanilmasi daha tutarli olur; eger bu sema hic kullanilmiyorsa (SH-001) silinmesi zaten sorunu ortadan kaldirir.
- **Onem:** Dusuk · **Guven:** Dogrulanmali

### [SH-006] AccountBase.statement_day / payment_day icin ge=1,le=31 kisitlamasi ay uzunlugunu gozetmiyor
- **Sorun:** `statement_day`/`payment_day` (satir 29-30) 1-31 araliginda herhangi bir gunu kabul ediyor. Subat gibi 28/29 gunluk aylarda 31 gecersiz bir "kesim gunu" olur; rules_engine bu degeri ay sonuna nasil map ettigini (orn. min(day, ay_sonu)) garanti etmiyorsa yanlis hesap tarihine yol acabilir. Bu sema kullanilmiyor (SH-001) ama desen olarak not edilir; gercek kullanimdaki router-yerel semalarin ayni kisiti tasiyip tasimadigi ayri dogrulanmali.
- **Kanit:** satir 29-30.
- **Aksiyon:** rules_engine.py'de statement_day=31 senaryosunun Subat/Nisan/Haziran/Eylul/Kasim gibi 28-30 gunluk aylarda nasil ele alindigini dogrulayin; gerekirse Field aciklamasina "ayin son gunu asilirsa ay sonuna sarilir" notu eklenmeli.
- **Onem:** Dusuk · **Guven:** Dogrulanmali

### [SH-007] ProposedAction.payload ve PendingActionRead.payload tip guvenligi zayif
- **Sorun:** `ProposedAction.payload: dict` (satir 184) herhangi bir sema dogrulamasi olmadan serbest bir dict kabul ediyor; `PendingActionRead.payload: str` (satir 209) ise JSON-string olarak saklaniyor, yani iki farkli katmanda iki farkli temsil var (create tarafinda dict, read tarafinda ham string). "LLM asla DB yazmaz, propose_action -> onay -> execute_pending_action" akisinda payload'un action_type'a gore dogru alanlari icerdigini garanti eden hicbir Pydantic-seviyesi kontrol yok; bu kontrol tamamen action_executor.py'nin runtime parse/kontrolune birakilmis. (Mimariye uygun oldugu belirtiliyor ama sema tarafinda hicbir tip guvenligi olmamasi, kotu bicimlendirilmis payload'in ancak calisma zamaninda patlamasina yol aciyor.)
- **Kanit:** satir 184, 209.
- **Aksiyon:** Mumkunse action_type'a gore Union/discriminated model kullanilarak payload sema seviyesinde dogrulanabilir; asgari olarak bu semanin kullanilmadigi (SH-001) goz onune alinarak, gercek kullanimda olan action modul(ler)inin benzer bir zaaf tasiyip tasimadigi kontrol edilmeli.
- **Onem:** Orta · **Guven:** Dogrulanmali

### [SH-008] GoalRuleCreate validator'i allocation_type="full" durumunda allocation_value'yu sessizce yok sayiyor
- **Sorun:** `value_required_for_percent_or_fixed` validator'i (satir 315-323) yalnizca `allocation_type in ("percent", "fixed")` icin `allocation_value`'yu zorunlu kiliyor. `allocation_type="full"` iken kullanici yanlislikla `allocation_value=50` gonderirse hicbir hata/uyari olmadan sessizce kabul edilir ve GoalRule kaydinda anlamsiz bir deger saklanir (full tipte allocation_value kullanilmamali). Bu "yanlis konfigurasyonu sessizce kabul etme" davranisi ileride "neden %50 degil tum tutar aktarildi" gibi hata ayiklamasi zor bir kafa karisikligina yol acabilir.
- **Kanit:** satir 315-323 (validator sadece percent/fixed dallarini kontrol ediyor, full dali icin allocation_value varliginda uyari/hata yok).
- **Aksiyon:** `allocation_type == "full"` iken `allocation_value is not None` ise ValueError firlatilmasi veya en azindan sessizce None'a zorlanmasi (`return None if atype == "full" else v`) onerilir.
- **Onem:** Orta · **Guven:** Kesin

### [SH-009] GoalAllocationCreate.amount icin sifir/negatif kisitlamasi yok
- **Sorun:** `GoalAllocationCreate.amount: Decimal` (satir 292) docstring'de "pozitif=katki, negatif=cekim" diyor ama hicbir Field kisiti (`ne=0` gibi) yok. `amount=0` gonderilirse anlamsiz, hicbir etkisi olmayan bir GoalAllocation kaydi DB'ye yazilabilir (goal_allocations tablosunda cift sayma / gurultu birikimi riski, GoalRead.progress_percent hesaplamasinda sifir-katki satirlari varsa istatistiksel gurultu).
- **Kanit:** satir 290-292.
- **Aksiyon:** `amount: Decimal = Field(..., ne=0)` gibi bir kisit eklenerek sifir-tutarli "katki" kayitlarinin onune gecilebilir.
- **Onem:** Dusuk · **Guven:** Kesin
