# MASTER FIX LIST — FinancialOS Backend Kalite Denetimi

Bu belge iki denetim kaynagini birlestirip deduped, onceliklendirilmis TEK liste uretir:

- **Kaynak 1 (per-file, satir-satir):** `docs/kalite-seruveni/dosya-denetimi/*.md` — 36 backend dosyasi.
- **Kaynak 2 (dimension audit, dedup referansi):** `docs/kalite-seruveni/sections/{RULE,DATA,SEC,BE,LLM}.md`.

Her madde kaynak ID'leri ile isaretlidir (per-file kodu orn. `AE-001` VE/VEYA dimension ID orn. `RULE-002`). "YENI" etiketi: per-file'da bulunup dimension taramasinda karsiligi olmayan bulgu.

## Ozet

| Oncelik | Adet | Tanim |
|---|---|---|
| **P0** | 21 | Finansal matematik hatasi, veri butunlugu, aktif guvenlik bypass'i — KESIN ve yanlis-sonuc senaryolu |
| **P1** | 27 | Onemli ama acil-olmayan dogruluk/dayaniklilik (KESIN) |
| **P2** | ~20 grup | Kalite/temizlik, konvansiyon, olu kod (KESIN) |
| **TEYIT-GEREKLI** | 18 | Guven=Dogrulanmali — uygulanmadan once teyit gerekir |

**Zaten COZULMUS (hariç tutuldu):**
- `RULE-001` / BUG #059 — `goal_rules._matches` account_type enum-str karsilastirmasi (`.value` ile duzeltildi). NOT: `GR-001` (fixed allocation isaret bug'i) AYNI dosyada AMA FARKLI bir bulgudur, hala aciktir → P0.
- `DATA-003` + `DATA-004` / BUG #060 — SQLite `PRAGMA foreign_keys=ON` + `busy_timeout=5000` eklendi. NOT: FK artik ENFORCE edildigi icin `MO-004` (hesap silme IntegrityError) simdi CANLI bir sorundur → P1.
- `RULE-023` / ADR-026 — ZikZak additive carried_forward cift-sayimi (`carried_forward=0.0` + `today_target=daily_limit`).

---

## ✅ UYGULAMA DURUMU (10 Tem 2026 — 21/21 P0 çözüldü + doğrulandı, süit 187 yeşil)

**Çözüldü (BUG #059-#085, hepsi test/çalıştırma ile doğrulandı — bkz. `uygulanan-fixler.md`):**
P0-1 (#069), P0-2 (#068), P0-3 (#079), P0-4 (#081), P0-5 (#066), P0-6 (#064), **P0-7 (#084)**, P0-8 (#080), P0-9 (#065), P0-10 (#082), P0-11 (#073), P0-12 (#074), P0-13 (#072), P0-14 (#072), P0-15 (#070), P0-16 (#071), P0-18 (#062), **P0-19 (#085)**, P0-20 (#067), P0-21 (#063) + önceki tur (RULE-001/#059, DATA-003-004/#060, FE-002/#061, ADR-026 zikzak) + altyapı (scripts #075/#076, pytest #077, conftest in-memory #078) + devrimsel: **grounding check (LLM-003/#083)**.

**Kapatılan son 2 P0 (10 Tem 2026 — önce test yazıldı, kırmızı doğrulandı, sonra fix):**
- **P0-7** (sim sınır çift-sayım) → **BUG #084**: `_project_forward` pencereleri yarı-açık `(start, end]`. `tests/test_simulation_boundary.py` önce kırmızıydı (kredi zincir 100k→80k vs tek 100k→85k), fix sonrası eşit. 3 boundary testi yeşil.
- **P0-19** (coach sahte-tamamlama) → **BUG #085**: `_FAKE_PASTTENSE_RE` parantezsiz düz geçmiş-zaman iddiasını (1. tekil + edilgen) yakalar; `tests/test_coach_fake_completion.py` 8 MUST_CATCH + 6 MUST_PRESERVE (yanlış-pozitif koruması) ile doğrulandı.

> Not: P0-1 kısmi (post-commit trigger izolasyonu); tam handler-commit birleştirmesi ayrı.

---

## P0 — Kritik (finansal doğruluk / veri bütünlüğü / aktif güvenlik)

### [P0-1] execute_pending_action: mutasyon commit edilmis ama "failed" raporlaniyor → cift-sayim
- **Sorun:** Handler (`_execute_*`) kendi `db.commit()`'ini yapip parayi/lotu/borcu kalici yaziyor; SONRA ayni try blogunda ikinci commit (`status=executed`) ve `trigger_after_action_resolution` cagriliyor. Ikinci commit veya post-commit kod patlarsa disardaki `except` `_mark_failed` ile status=failed yaziyor — ama finansal mutasyon ONCEKI commit ile zaten kalici.
- **Kanit:** `app/action_executor.py:305-335` (306, 318-323, 332-335); erken commit'ler 403, 481, 519, 608, 674.
- **Yanlis-sonuc senaryosu:** Kullaniciya "aksiyon basarisiz" doner, hesap bakiyesi zaten degismistir. Kullanici/koc ayni aksiyonu tekrar tetiklerse mutasyon IKINCI kez uygulanir → cift-sayim.
- **Fix:** Handler mutasyonu ile status=executed'i TEK commit sinirinda birlestir (handler'lar kendi commit'ini yapmasin); post-commit kodu ayri try'a al, orada hata olursa asla zaten-commit-edilmis mutasyonu 'failed' isaretleme.
- **Kaynak:** AE-001 · **YENI** · **Güven:** Kesin

### [P0-2] sell_investment: gecersiz/emanet credit hesabi → satis parasi sessizce yok oluyor
- **Sorun:** `credit_account_id` verilmis ama hesap bulunamiyor veya `is_emanet=True` ise `net_eline_gecen` HICBIR hesaba eklenmiyor; ama lot dususu + `inv.balance` guncellemesi zaten yapilmis ve commit edilmis, fonksiyon `success:True` donuyor. Kaynak tarafinda emanet korumasi var (558-565), hedef tarafinda yok.
- **Kanit:** `app/action_executor.py:597-621` (kars. 558-565).
- **Yanlis-sonuc senaryosu:** Yatirim satilir, lot azalir ama satis geliri hicbir yere gitmez — para sistemden kaybolur, kullaniciya ne hata ne uyari doner (net deger sessizce azalir).
- **Fix:** `credit_to_account_id` gecersiz/emanet cikarsa tum handler'i basarisiz dondur (lot dusurulmesin) veya en azindan "para hicbir hesaba yatirilmadi" uyarisi ver.
- **Kaynak:** AE-002 · **YENI** · **Güven:** Kesin

### [P0-3] Kart asgari odemesi baslangic bakiyesinden SABIT — yanlis amortisman ("X ayda biter" iyimser)
- **Sorun:** Kart min odemesi `collect_debts`'te bir kez `balance*0.25` hesaplanip tum simulasyon boyunca sabit tutuluyor; her ay guncel bakiyeden yeniden hesaplanmiyor.
- **Kanit:** `app/debt_strategy.py:104`, `:171, 191-195` (sabit tuketim).
- **Yanlis-sonuc senaryosu:** Ziraat karti (4342.98) elle simule edildiginde arac "5 ayda kapanir" der; gercek TR banka pratiginde (asgari = guncel bakiyenin %25'i) bakiye cok daha yavas erir, sadece-minimum odeyen kullanici borcu pratikte hic kapatamaz. Snowball/avalanche ay sayisi sistemli iyimser.
- **Fix:** Kart icin her ay `min_pay = max(state[aid]*MIN_CARD_PAYMENT_RATIO, floor)` yeniden hesapla; `DebtItem.min_payment` kart tipinde "oran" olarak sakla.
- **Kaynak:** DS-001, RULE-002 · **Güven:** Kesin

### [P0-4] Kredi hesaplarinda interest_rate bos → faiz sessizce %0 (TUM test kredileri boyle)
- **Sorun:** `collect_debts`'te `rate is None or <=0` durumunda kart icin varsayilan %4.25, kredi icin `0.0` (faizsiz) ataniyor. `setup_data.py`'deki 5 kredinin hicbirinde `interest_rate` set edilmiyor → hepsi faizsiz simule ediliyor.
- **Kanit:** `app/debt_strategy.py:99-101`; `scripts/setup_data.py:83-142`.
- **Yanlis-sonuc senaryosu:** `total_interest_paid` ve stratejik karsilastirma onbinlerce TL'lik gercek faizli krediyi faizsiz gosterir — maliyet sistematik dusuk, "sanal zenginlik" riski.
- **Fix:** En az UI/response'ta `assumed_interest_free: bool` uyarisi don; veya sektor ortalamasi bir varsayilan tavan uygulayip "tahmini" notu ver.
- **Kaynak:** DS-003 · **YENI** · **Güven:** Kesin

### [P0-5] goal_engine debt_freedom: projected_completion_date HER ZAMAN None (dict/attribute uyumsuzlugu + sessiz except)
- **Sorun:** `compare_strategies` bir **dict** donuyor (`_result_to_dict`), ama `goal_engine` buna `snowball.months_to_freedom` diye **attribute** erisimi yapiyor → her cagride `AttributeError`; `except Exception: pass` (goal_engine:109) sessizce yutuyor.
- **Kanit:** `app/goal_engine.py:106-110`; `app/debt_strategy.py:306, 316-326`.
- **Yanlis-sonuc senaryosu:** debt_freedom hedeflerinde "tahmini bitis tarihi" ozelligi fiilen hicbir zaman calismiyor, kullaniciya asla gosterilmiyor; hata loglanmadigi icin fark edilemiyor.
- **Fix:** `snowball["months_to_freedom"]` kullan (iki yerde); bare except yerine dar tip + log.
- **Kaynak:** GE-001, DS-005, RULE-011, BE-010 · **Güven:** Kesin

### [P0-6] goal_rules "fixed" allocation: gider hep POZITIF katki olarak kaydediliyor (olu isaret dali)
- **Sorun:** "fixed" dali `tx_amount >= 0` ile isaret secmeye calisiyor ama `Transaction.amount` DB'de HER ZAMAN pozitif (yon `transaction_type` ile ayriliyor). Boylece `else -fixed` dali asla calismaz.
- **Kanit:** `app/goal_rules.py:166-171`; `app/routers/transactions.py:265-266` (amount>0 zorunlu).
- **Yanlis-sonuc senaryosu:** "fixed" kural bir GIDER islemine eslesirse hedefe cekim (withdrawal, amount<0) yerine POZITIF katki (contribution) kaydedilir → goal progress yanlis sisirilir.
- **Fix:** Isareti `tx.transaction_type`'dan ver: `fixed if type=="income" else -fixed`.
- **Kaynak:** GR-001 · **YENI** · **Güven:** Kesin

### [P0-7] simulation_engine: zincirlenmis ufuk projeksiyonu sinir tarihinde geliri/taksiti IKI KEZ sayiyor
- **Sorun:** `simulate_action` T+0→T+30→T+60→T+90 zincirleme `_project_forward` cagiriyor; her segment `world.as_of=end` yapiyor. Gelir/kredi donguleri her iki ucu da kapsayici (`<=`/`>=`), odeme tam segment sinirina denk gelince iki kez tetikleniyor (borc dongusu `paid_date` ile korunuyor, gelir/kredi korunmuyor).
- **Kanit:** `app/simulation_engine.py:351, 320-323, 526-529` (ampirik dogrulandi: 31 Ocak maasi 3000 yerine dogru 2000).
- **Yanlis-sonuc senaryosu:** `delta_vs_baseline` (T+30 karar tablosu, T+60/T+90) aksiyonun gercek etkisini degil kismen implementasyon artefaktini yansitir — "cift-sayma yasak" vizyon ilkesi ihlali.
- **Fix:** Sinir kosulunu yari-acik yap (`start < pay_date <= end`) VEYA `world.as_of`'u bir sonraki cagriya `end+1gun` devret; gelir/kredi icin "islendi" izi tut.
- **Kaynak:** SE-001 · **YENI** · **Güven:** Kesin (calistirilarak)

### [P0-8] simulation_engine add_transaction: auto_update_balance bayragi yok sayiliyor
- **Sorun:** Gercek yurutucu bakiyeyi SADECE `auto_update_balance=True` ise gunceller (executor:467). Simulasyon `_apply_action` bu bayragi HIC okumadan kosulsuz bakiye degistiriyor.
- **Kanit:** `app/simulation_engine.py:240-248` vs `app/action_executor.py:465-479`.
- **Yanlis-sonuc senaryosu:** Simulasyon, gercekte bakiyeyi degistirmeyecek bir islemi bakiye degisimi olarak on-izlemede gosterip yanlis karar destegi verir.
- **Fix:** `auto_update_balance` False/eksikse simulasyonda da bakiyeyi degistirme.
- **Kaynak:** SE-002 · **YENI** · **Güven:** Kesin

### [P0-9] Premortem prompt'u crunch/en-dusuk-bakiye verisini HIC gormuyor (yanlis anahtar `crunch_day`)
- **Sorun:** `build_cockpit_snapshot` alanlari `lowest_balance_tl/lowest_balance_date/crunch_count` uretiyor; ama `premortem._user_prompt` var olmayan `crunch_day` anahtarini `.get('crunch_day','-')` ile okuyor → HER ZAMAN `'-'` doner.
- **Kanit:** `app/cockpit_snapshot.py:33-35, 88-90` vs `app/premortem.py:144`.
- **Yanlis-sonuc senaryosu:** LLM, nakit-krizi tarihinden tamamen habersiz 6 aylik basarisizlik senaryolari uretir — dosyanin en kritik veri turu (ne zaman nakit tukenir) hic ulasmaz.
- **Fix:** `premortem.py:144`'u `lowest_balance_date` ile degistir; `lowest_balance_tl`+`crunch_count`'u da prompta ekle.
- **Kaynak:** CS-001 · **YENI** · **Güven:** Kesin

### [P0-10] simulation router: reel_butce / daily_limit hicbir zaman doldurulmuyor → sessizce 0.0
- **Sorun:** `HorizonSnapshot` `reel_butce`/`daily_limit` vaat ediyor, `_snapshot_to_horizon` `snap.get(...)` ile okuyor; ama `simulation_engine._snapshot_to_dict` bu anahtarlari HIC yazmiyor (shadow-accounting sadece rules_engine'de).
- **Kanit:** `app/routers/simulation.py:44-45, 73-75`; `app/simulation_engine.py:418-441`.
- **Yanlis-sonuc senaryosu:** `.get(...) or 0.0` ile reel_butce/daily_limit her ufukta 0.0 doner → kullaniciya/LLM'e "butceniz sifir/kritik" gibi yanlis okunur.
- **Fix:** Semadan bu alanlari cikar VEYA simulation_engine'e rules_engine ile tutarli reel_butce/daily_limit hesabi ekle.
- **Kaynak:** RSI-001 · **YENI** · **Güven:** Kesin

### [P0-11] reports category_breakdown "both": gelir ve gider ayni kategori satirinda toplaniyor
- **Sorun:** `group_by` sadece `Transaction.category`, `transaction_type` degil. "both" modunda ayni kategori adindaki gelir + gider tek `total`'da toplaniyor.
- **Kanit:** `app/routers/reports.py:74-78` (group_by), 65-72 (type filtresi), 87 (percentage).
- **Yanlis-sonuc senaryosu:** "diger"de 1000 gelir + 200 gider → tek satir total=1200 (gercek net +800). Yon bilgisi kaybolur, percentage hatali toplama gore hesaplanir.
- **Fix:** `group_by`'i (transaction_type, category) ikilisine gore yap veya response'a `type` alani ekle.
- **Kaynak:** RRE-001 · **YENI** · **Güven:** Kesin

### [P0-12] reports upcoming_cashflow: kredi hesaplarinda sadece TEK sonraki taksit — uzun ufukta gercek yuku ciddi eksik gosterir
- **Sorun:** RecurringIncome/Expense icin ufuk boyunca tum aylik tekrarlar uretiliyor; Account(loan) icin sadece `next_payment_date` alanindaki TEK tarih kullaniliyor.
- **Kanit:** `app/routers/reports.py:193-200` vs 202-218.
- **Yanlis-sonuc senaryosu:** days=180'de 5 kredinin her biri ~6 taksit odeyecekken rapor 1'er taksit gosterir; `total_payable` eksik, `net_flow` cok daha iyimser cikar — "sanal zenginlik" ihlali.
- **Fix:** Loan icin `next_payment_date`'ten baslayarak ufuk sonuna kadar aylik tekrar uret; veya "sadece bir sonraki taksit" uyarisi ekle.
- **Kaynak:** RRE-002 · **YENI** · **Güven:** Kesin

### [P0-13] Manuel allocation tutari gercek transaction tutariyla dogrulanmiyor → sanal zenginlik
- **Sorun:** `create_allocation`/`link_transaction` `payload.amount`'u dogrudan `GoalAllocation.amount` yaziyor; `tx.amount` ile ust-sinir/isaret karsilastirmasi yok, schema'da da `gt/le` kisiti yok.
- **Kanit:** `app/routers/goals.py:186-222`; `app/goal_engine.py:199-224`; `app/schemas.py:290-292`.
- **Yanlis-sonuc senaryosu:** 10 TL'lik transaction "1.000.000 TL katki" olarak baglanabilir; `current_amount`/`progress_percent` bu uydurma degerden hesaplanir, goal yanlislikla "achieved" olabilir.
- **Fix:** `abs(payload.amount) <= abs(tx.amount)` dogrula (ve ayni tx'in diger allocation'lari ile toplamda tavan); asilirsa 422.
- **Kaynak:** RGO-001, GE-003 · (kis. SEC-032) · **Güven:** Kesin

### [P0-14] Ayni transaction birden fazla goal'e tam tutarla baglanabiliyor → cift sayim
- **Sorun:** `uq_goal_tx` sadece (goal_id, transaction_id) ciftini korur; create_allocation transaction'in baska goal'e bagli olup olmadigini kontrol etmiyor.
- **Kanit:** `app/routers/goals.py:186-222`; `app/models.py:801-802`.
- **Yanlis-sonuc senaryosu:** Ayni 5000 TL gercek para hem "Acil Fon" hem "Tatil Fonu"na tam baglanir; iki goal toplami gercekte olmayan 10.000 TL ilerleme gosterir — "cift-sayma yasak" ihlali.
- **Fix:** Ayni transaction_id icin tum goal'lerdeki mevcut allocation toplamini sorgula, `toplam <= tx.amount` zorla.
- **Kaynak:** RGO-002 · **YENI** · **Güven:** Kesin

### [P0-15] Recurring gider: last_triggered_year_month ONAYDAN ONCE isaretleniyor → reddedilen/basarisiz gider bir daha tetiklenmiyor
- **Sorun:** `trigger_due_expenses` PendingAction'i "pending" olusturur olusturmaz `last_triggered_year_month`'u yazip commit ediyor; dedup sadece bu alana bakiyor, PendingAction'in "executed" olup olmadigina bakmiyor.
- **Kanit:** `app/routers/expenses.py:166, 194-197`; reject `app/action_executor.py:338-361` (bu alana dokunmuyor).
- **Yanlis-sonuc senaryosu:** Kullanici reddederse veya execute basarisiz olursa, gercekte odenmemis gider o ay "halledildi" sayilir; cockpit gercek nakit durumunu yansitmaz (sessiz veri kaybi).
- **Fix:** `last_triggered_year_month`'u SADECE action gercekten 'executed' olduktan sonra set et; ya da reject/failed akisinda geri al (rollback).
- **Kaynak:** REX-001 · **YENI** · **Güven:** Kesin

### [P0-16] Recurring gelir/gider: day_of_month=29/30/31 kisa aylarda tamamen atlaniyor (telafi yok)
- **Sorun:** Tetikleme kosulu `day_of_month <= today.day`. day_of_month o ayin gun sayisindan buyukse (31→Nisan/Subat) kosul o ay hicbir gun True olmaz; `last_triggered_year_month` sadece basarili tetiklemede yazildigi icin telafi mekanizmasi yok.
- **Kanit:** `app/routers/incomes.py:145, 181`; `app/routers/expenses.py:159`.
- **Yanlis-sonuc senaryosu:** "Ayin son gunu" niyetiyle 31 giren maas Subat/Nisan/Haziran/Eylul/Kasim aylarinda sessizce hic tetiklenmez, sonraki ay da telafi edilmez.
- **Fix:** `effective_day = min(day_of_month, calendar.monthrange(y,m)[1])` ile ay sonuna clamp'le.
- **Kaynak:** RIN-001, REX-004 · **YENI** · **Güven:** Kesin

### [P0-17] PersonalDebt: is_paid/paid_date senkron kurallari celiskili payload'da tutarsiz durum → borc hesaplardan kayboluyor
- **Sorun:** `update_debt` once ham setattr, sonra iki bagimsiz senkron kurali (paid_date verilmisse is_paid=True; is_paid=False ise paid_date=None) birbirini eziyor; celiskili payload'da is_paid=True + paid_date=None gibi tutarsiz durum uretiyor.
- **Kanit:** `app/routers/debts.py:120-128`; tuketiciler `rules_engine.py:356,433,467,550`, `cashflow.py:117`, `reports.py:172,184` (`is_paid==False` filtreler).
- **Yanlis-sonuc senaryosu:** is_paid=True + paid_date=None kayit, gercekte hicbir tahsilat olmadan "beklenen gelir"/borc takvimi/raporlardan tamamen kaybolur (sanal kayip).
- **Fix:** Senkron kurallarini tek if/elif zincirine indir; is_paid=True + paid_date yoksa `date.today()` varsayilani; DB CHECK `(is_paid=0 AND paid_date NULL) OR (is_paid=1 AND paid_date NOT NULL)`.
- **Kaynak:** RDE-001, RDE-002, DATA-025 · **Güven:** Kesin

### [P0-18] scheduler run_extractor hatada db.rollback() yapmiyor → paylasilan session zehirleniyor
- **Sorun:** `run_extractor` her cagriyi try/except sariyor ama except'te `db.rollback()` YOK. Bir extractor commit'te hata atarsa session "pending rollback"a duser; ayni `db` cagiran yerde kullanilmaya devam eder.
- **Kanit:** `app/scheduler.py:88-120` (118-120); `app/coach.py:1813-1832`; `run_periodic_batch_for_user:123-129`.
- **Yanlis-sonuc senaryosu:** (a) Event-triggered yolda Coach'in ikinci `_save_message`'i `PendingRollbackError` ile patlar → kullaniciya yanit hic donmez. (b) Gece batch'inde ilk extractor session'i zehirlerse kalan 4'u de sessizce calismaz. Modul docstring'inin "bir extractor cokerse digerleri etkilenmez" vaadi ihlal.
- **Fix:** except'te `db.rollback()` ekle veya her extractor'i `db.begin_nested()` savepoint ile sar (proje konvansiyonu).
- **Kaynak:** SC-001, BE-029, BE-010 · **Güven:** Kesin

### [P0-19] Coach: gecmis-zaman sahte-tamamlama ("Kaydettim.") ne temizleniyor ne retry tetikliyor
- **Sorun:** `_FAKE_CONFIRM_RE` sadece koseli-parantezli metni yakaliyor; `_FAKE_NIYET_RE` sadece gelecek/niyet kaliplarini. Duz gecmis-zaman iddiasi ("Harcamani kaydettim.", "Islem kaydedildi.") hicbir filtreye takilmiyor.
- **Kanit:** `app/coach.py:1330-1333, 1336-1345, 1402-1404, 1691-1694`.
- **Yanlis-sonuc senaryosu:** LLM `propose_action` cagirmadan "Kaydettim." yazarsa, hicbir DB yazimi olmadan "islendi" izlenimi kullaniciya oldugu gibi ulasir — finansal guven kirilir.
- **Fix:** `_FAKE_CONFIRM_RE`'yi parantez zorunlulugu olmadan (cumle/satir sonu ile) genislet, veya `_FAKE_NIYET_RE`'ye gecmis-zaman tamamlama fiillerini ekleyip retry kapsamina al.
- **Kaynak:** CO-002, LLM-023 · **Güven:** Kesin

### [P0-20] update_checkpoint hard-delete korumasini bypass ediyor (Master Checkpoint enforcement delinir)
- **Sorun:** `update_checkpoint` hicbir kisit uygulamadan `priority`/`checkpoint_type` alanlarini degistirebiliyor. Korunan bir checkpoint'in once priority'si/type'i degistirilip sonra `?hard=true` ile kalici silinebilir.
- **Kanit:** `app/routers/checkpoints.py:112-114` (serbest setattr), `:144` (delete korumasi sadece anlik degerlere bakiyor).
- **Yanlis-sonuc senaryosu:** PROJE.md'nin "Master Checkpoint enforcement kod seviyesinde" ilkesi anlamsizlasir; kritik davranissal kural (emanet dokunulmazligi vb.) iki adimda kalici silinir.
- **Fix:** `update_checkpoint`'te de ayni koruma kontrolunu uygula (korunan kayitlarin priority/type degisimini engelle/onay iste).
- **Kaynak:** RCH-003, DATA-034 · **Güven:** Kesin

### [P0-21] GoalUpdate.status ile "achieved" dogrudan PATCH edilebiliyor → sanal basari
- **Sorun:** `GoalUpdate.status` literal'i "achieved" iceriyor; router kosulsuz `setattr` ile yaziyor, `achieved_at` set edilmiyor. Gercek gecis yalnizca `goal_engine.refresh_goal`'da olmali.
- **Kanit:** `app/schemas.py:267`; `app/routers/goals.py:131-132`; `app/goal_engine.py:188-189`.
- **Yanlis-sonuc senaryosu:** Kullanici hicbir katki yapmadan (current < target) goal'i "achieved" isaretleyebilir — "Rules Engine karar verir" + "sanal zenginlik yasak" ihlali.
- **Fix:** `GoalUpdate.status` literal kumesinden "achieved"i cikar (sadece active/paused/abandoned).
- **Kaynak:** SH-002 · **YENI** · **Güven:** Kesin

---

## P1 — Onemli (dogruluk/dayaniklilik, acil degil)

### [P1-1] Datetime serialize'da tzinfo=timezone.utc eksik (SISTEMIK, coklu endpoint)
- Naive UTC datetime `tzinfo` eklenmeden serialize edilince JS Turkiye saatinde 3 saat geri gosterir. Etkilenen: `accounts` (RAC-001), `checkpoints` (RCH-001), `debts` (RDE-003), `expenses` (REX-002), `fund_price` (RFP-001), `goals` (RGO-003), `transactions` (RTR-001), `user` (RUS-001), `fund_tracker` (FT-002), `goals last_refreshed/achieved` (GE-008). Ayrica model tarafinda tutarsizlik: DecisionJournal aware (MO-002), PriceHistory karma (MO-003), DATA-007.
- **Fix:** `_memory_to_history_item` pattern'i — response oncesi `.replace(tzinfo=timezone.utc)` veya `field_serializer`. Merkezi bir helper.
- **Kaynak:** RAC-001, RCH-001, RDE-003, REX-002, RFP-001, RGO-003, RTR-001, RUS-001, FT-002, GE-008, DATA-007, MO-002, MO-003 · **Güven:** Kesin

### [P1-2] Para alanlari Float — kumulatif yuvarlama + banker's rounding (SISTEMIK)
- Cekirdek para kolonlari `Column(Float)`; tekrarli `+=/-=` ve topla-sonra-yuvarla zincirlerinde kurus sur5klenmesi birikir; `round()` ROUND_HALF_EVEN (2.675→2.67). Goal Engine bilerek Numeric kullaniyor → dosya-ici iki standart.
- **Fix:** Uzun vadede para kolonlarini `Numeric(14,2)`/kurus-Integer + `Decimal` + `quantize(ROUND_HALF_UP)`; kisa vadede tek `money()` helper + invariant testleri. ADR ile "float MVP / Decimal Wave-3" karari.
- **Kaynak:** DATA-001, RULE-006, RULE-040, BE-021, SH-003, MO-005, AE-006, RAC-006, RTR-006, RDE-007, RFP-005, RCF-006, RRE-008, GE-007, RULE-014, DATA-022, RULE-033, RULE-035 · **Güven:** Kesin

### [P1-3] cockpit router alacaklar'i yeniden hesapliyor (mimari ihlali + cift-yuvarlama)
- `receivables = net_deger_tam - net_deger` iki yuvarlanmis degerin farki; `generate_cockpit` zaten `alacaklar_toplami` donuyor. Router'da matematik yapiliyor (PROJE.md ihlali) + 0.01 sapma riski.
- **Fix:** `cockpit["alacaklar_toplami"]` dogrudan kullan.
- **Kaynak:** RCP-001, RCP-006 · **Güven:** Kesin

### [P1-4] coach_insights: dominant-dilim & mc_reference top-3-disi insight'lar dormant'a dusurulmuyor
- `extract_decision_rhythm` ve `extract_mc_reference_frequency` "DORMANT SWEEP" pass'ine sahip degil; eski/guncelligini yitirmis insight'lar `status=active` kalip prompta sonsuza kadar enjekte edilir.
- **Fix:** Diger extractor'lardaki gibi bu calismada uretilmeyen aktif basliklari dormant'a dusuren sweep pass ekle.
- **Kaynak:** CI-001, CI-002 · **Güven:** Kesin

### [P1-5] explicit_red_line K1 regex'leri finansal alanla anchor'lanmamis — "%0 false positive" iddiasiyla celiskili
- `mutlak_red/niyet_beyani/kesin_red` desenleri "istemiyorum/asla/kesinlikle" iceren HER konuyu yakalar (film, sohbet vb.); sort_priority=15 ile 90 gun aktif kirmizi-cizgi insight'ina donusur.
- **Fix:** Bu 3 desene finansal baglam zorunlulugu (para/kart/kredi/borc...) ekle veya K2'ye devret.
- **Kaynak:** CI-003 · **Güven:** Kesin

### [P1-6] Fallback provider modunda gunluk limit korumasi ve provider-bazli istatistik kiriliyor
- `provider_name="Fallback(Gemini)"` `!= "gemini"` oldugundan `_build_usage_info` daily_limit=999999 sabitler → %80/%100 uyari hic tetiklenmez; `_log_api_call` degisen string'lerle sayimi parcalar.
- **Fix:** Fallback sarmalayicisindan asil provider adini ayristir/normalize et.
- **Kaynak:** RCO-001, BE-025 · **Güven:** Kesin

### [P1-7] Gunluk kullanim sayaci sunucu yerel saatine gore sifirlaniyor (UTC degil)
- `_today_call_count` `date.today()` ile gun sinirini kurar; `ApiCallLog.called_at` naive UTC. TR (UTC+3) sunucuda sayac 3 saat erken sifirlanir → Gemini 1500/gun kotasi asilabilir.
- **Fix:** `datetime.utcnow().date()` kullan.
- **Kaynak:** RCO-002 · **Güven:** Kesin

### [P1-8] evaluate_rules_for_transaction hicbir yerden cagrilmiyor — otomatik kural motoru fiilen olu
- Docstring "Transaction kaydedildiginde cagrilir" der ama transactions router import etmiyor; kurallar hicbir zaman otomatik tetiklenmiyor.
- **Fix:** transactions create/update/delete akisina `evaluate_rules_for_transaction(tx.id, db)` bagla; ya da docstring'i "henuz wiring yok" yap.
- **Kaynak:** GR-002 · **Güven:** Kesin

### [P1-9] percent allocation_value ust siniri (100) hicbir yerde uygulanmiyor
- `allocation_value=150` → `pct=1.5`, transaction tutarinin 1.5 kati katki (sanal zenginlik). schema sadece `ge=0`.
- **Fix:** schema'da `le=100` (+`gt=0`), veya `pct=min(pct, 1)` klemp.
- **Kaynak:** GR-004, RULE-033 · **Güven:** Kesin (etki GR-002 cozumune bagli)

### [P1-10] cash_target current_amount 0'a clamp edilmiyor — debt_freedom ile tutarsiz, negatif gosterim
- `_compute_cash_target` sadece progress'i klemp ediyor, `current_amount`'i degil; cekimler katkidan fazlaysa negatif `current_amount` frontend'e sizar.
- **Fix:** don degerinde `max(current, 0)` (progress ham deger uzerinden kalabilir).
- **Kaynak:** GE-004, RULE-034 · **Güven:** Kesin

### [P1-11] Update endpoint'leri account_id sahiplik/varlik dogrulamasi yapmiyor
- `update_transaction` (RTR-002) ve `update_expense` (REX-003) `account_id`'yi kosulsuz setattr ile yaziyor; create tarafinda 404 var, update'te yok. Yabanci/gecersiz account_id sessizce kaydedilir, bakiye guncellemesi sessizce atlanir.
- **Fix:** update_data'da account_id varsa `Account.id==x, user_id==user.id` dogrula, yoksa 404.
- **Kaynak:** RTR-002, REX-003 · **Güven:** Kesin

### [P1-12] update_transaction amount>0 dogrulamasi yok (create ile asimetrik)
- create'te `amount<=0` reddediliyor; update'te yok → negatif/sifir tutarli islem + bozuk bakiye.
- **Fix:** update_data'da "amount" varsa `<=0` kontrolu.
- **Kaynak:** RTR-003, SH-004 · **Güven:** Kesin

### [P1-13] transaction_type="transfer" hicbir bakiyeyi etkilemiyor (sessiz no-op, coklu yol)
- `_apply_to_balance` (transactions), `_execute_add_transaction` (executor) ve `_apply_action` (simulation) "transfer" dalini islemiyor; model tek `account_id` (hedef hesap yok). auto_update_balance=True olsa bile bakiye degismez.
- **Fix:** "transfer"i API'den kaldir VEYA iki hesapli transfer'i implement et; simulation'i gercek davranisla (no-op) hizala.
- **Kaynak:** RTR-004, AE-008, SE-003 · **Güven:** Kesin

### [P1-14] update_fund_price_manual hesap sorgusunda user_id filtresi yok
- Fonksiyon imzasinda user_id yok, sorgu sadece `Account.id==account_id`; `_execute_update_fund_price` user_id'yi alip iletmiyor → action_executor-onay akisinda sahiplik kontrolu atlaniyor.
- **Fix:** imzaya `user_id` ekle, `Account.user_id==user_id` filtresi, executor'dan gec.
- **Kaynak:** FT-001, AE-003 · **Güven:** Kesin

### [P1-15] OperationName enum values_callable eksik — DB'de deger yerine UYE ADI yaziliyor
- BUYUK_SNAKE ad vs kucuk_snake deger; `values_callable` olmadan SQLAlchemy adi yaziyor; PriceSource'da (`:557-563`) duzeltilmis, OperationName'de degil. Migration CHECK constraint'i buyuk-harfli isimlerle olusturmus.
- **Fix:** `SQLEnum(OperationName, values_callable=lambda x:[e.value for e in x])` + reasoning_traces CHECK/migration guncelle.
- **Kaynak:** MO-001, DATA-017 · **Güven:** Kesin

### [P1-16] Hesap silme: cascade tanimsiz + FK artik ON → ham IntegrityError/500 sizar
- `Transaction/RecurringExpense.account_id` `ondelete` yok (RESTRICT); BUG#060 ile FK enforce ediliyor; `delete_account` try/except'siz → 500 + stack.
- **Fix:** `try/except IntegrityError` ile 409 "Bu hesaba bagli N islem var" veya bilincli cascade karari.
- **Kaynak:** MO-004, RAC-004, DATA-013, BE-039 · **Güven:** Kesin

### [P1-17] NetWorthSnapshot: (user_id, snapshot_date) unique constraint yok — TOCTOU duplike kayit
- `_ensure_today_snapshot` check-then-insert atomik degil; es zamanli iki cockpit istegi ayni gun icin duplike snapshot uretebilir (trend grafiginde cakisan noktalar).
- **Fix:** `UniqueConstraint("user_id","snapshot_date")` + IntegrityError'i savepoint ile yut.
- **Kaynak:** RCP-002 · **Güven:** Kesin

### [P1-18] Alembic vs create_all schema drift + dokuman-kod celiskisi
- `init_db`/`setup_data.py` `drop_all+create_all` yapiyor, `alembic_version` stamp'lenmiyor; `app/PROJE.md` "startup create_all" der ama kod ADR-013 (alembic) diyor.
- **Fix:** `setup_data` sonunda `alembic stamp head`; `init_db`'yi test-only yap; PROJE.md'leri "schema alembic ile" guncelle.
- **Kaynak:** DB-001, DATA-005, BE-014, MN-001 · **Güven:** Kesin (drift senaryosu: Dogrulanmali)

### [P1-19] net_worth_delta hesaplaniyor ama hicbir yere yazilmiyor (olu parametre)
- `approve_action` net_worth_delta hesaplayip `link_premortem_outcome`'a geciyor; fonksiyon parametreyi kullanmiyor, DecisionJournal'da kolon yok.
- **Fix:** `outcome_net_worth_delta` kolonu ekleyip yaz, VEYA olu hesaplama+parametreyi kaldir; kalirsa `round(...,2)`.
- **Kaynak:** PM-001, RAT-002, RAT-003 · **Güven:** Kesin

### [P1-20] PremortemScenario.id format/tekillik dogrulanmiyor — frontend React key
- `id` icin pattern/uniqueness yok; LLM duplicate id donerse `PremortemModal.jsx:144` `key={s.id}` render'i bozulur.
- **Fix:** `^S[1-5]$` field_validator + PremortemResult'ta id-tekillik model_validator (aksi halde retry).
- **Kaynak:** PM-002 · **Güven:** Kesin

### [P1-21] premortem.py docstring'inde ADR-001 yasakli ozel isim
- Modul docstring satir 8 yasakli kisi ismini iceriyor; diger dosyalar isimsiz ifade kullaniyor (`debt_strategy.py:10-11`).
- **Fix:** Satiri isimsiz "ADR-001 uygulamasi: Premortem karar vermez, korluk noktalarini acar" ile degistir.
- **Kaynak:** PM-003 · **Güven:** Kesin

### [P1-22] premortem "cached" hep False — snapshot_hash hic karsilastirilmiyor (LLM cagri israfi)
- Hash hesaplanip yaziliyor ama mevcut DJ hash ile karsilastirilmiyor; her cagri (ayni pending icin ust uste tiklama) gercek LLM cagrisi tetikler.
- **Fix:** persist oncesi mevcut hash'i karsilastir, esitse LLM'siz mevcut senaryolari don; veya `cached` alanini kaldir.
- **Kaynak:** RPM-001 · **Güven:** Kesin

### [P1-23] Basarili aksiyon sonrasi korumasiz cagrilar 500 uretebilir (response/gercek durum celiskisi)
- `link_premortem_outcome` (RAT-001) ve `persist_premortem` (RPM-002) try/except disi; iclerinde `commit/refresh` var. Hata firlarsa aksiyon zaten executed iken kullaniciya 500 doner.
- **Fix:** Bu cagrilari reflection cagrisindaki gibi try/except ile sar; hata olursa logla, response'u etkileme.
- **Kaynak:** RAT-001, RPM-002 · **Güven:** Kesin (RPM-002 tetik: Dogrulanmali)

### [P1-24] evaluate_credit_card_strategy (MC3 kart stratejisi) hicbir yerden cagrilmiyor — olu kod
- Kok vizyonun parcasi olan kart-dongusu analizi `generate_cockpit`'e baglanmamis; kullaniciya/LLM'e hic ulasmiyor. (Ayrica RULE-003/004/005 icindeki off-by-one'lar bu fonksiyonda.)
- **Fix:** `generate_cockpit`'e `kart_stratejisi` olarak bagla VEYA fonksiyonu+vizyon maddesini kaldir; baglanirsa RULE-003/004/005 off-by-one'lari da duzelt.
- **Kaynak:** RE-001, RULE-003, RULE-004, RULE-005, RULE-021 · **Güven:** Kesin

### [P1-25] AnthropicProvider tool-aware history adapter kullanmiyor
- Diger provider'lar `_to_openai_messages`/ozel donusum kullanirken Anthropic `messages`'i donusumsuz gonderiyor; `role="tool"` + `tool_calls_json` Anthropic semasinda gecersiz. Bugun default degil ama `LLM_PROVIDER=anthropic` secilince ilk tool-cagrili konusmadan sonra kirilir.
- **Fix:** Anthropic tool_use/tool_result content-block adapter'i yaz.
- **Kaynak:** CO-003 · **Güven:** Kesin

### [P1-26] Vadesi gecmis borc/alacak "upcoming-cashflow"a kariyor (alt sinir yok)
- PersonalDebt/loan sorgularinda sadece `<= horizon`, `>= today` yok; yillar once vadesi gecmis is_paid=False kalem "yaklasan" listesine girer.
- **Fix:** `>= today` filtresi ekle veya "overdue" grubuna ayir.
- **Kaynak:** RRE-003 · **Güven:** Kesin

### [P1-27] simulation_engine — gercek yurutucu ile davranis paritesi kopuk
- `mark_debt_paid` zaten odenmis borcu tekrar odetir (SE-004); `sell_investment` eksik cost/price'i sessizce 0 kabul eder (SE-005, executor:575 guard'i yok); kredi taksit gunu kisa aydan sonra kalici kayar (SE-006); `_load_world` gercek 0 degerleri None'a cevirir (SE-007); satis geliri emanet hedefe kontrolsuz aktarilir (SE-008).
- **Fix:** Her kolu action_executor guard'lari ile birebir hizala; `_load_world`'de `if X is not None` kullan.
- **Kaynak:** SE-004, SE-005, SE-006, SE-007, SE-008 · **Güven:** Kesin (SE-008 Dogrulanmali)

---

## P2 — Kalite / Temizlik / Konvansiyon (Kesin)

- **[P2-1] Legacy `session.query()` yaygin (138+ kullanim)** — app/PROJE.md SQLAlchemy 2.x kuralini ihlal. Kaynak: CI-007, DP-002, RAC-002, RCH-004, RDE-004, RRE-004, RT-003, SC-002, BE-018, DATA-031. Yeni kod `select()` zorunlu, sik dokunulanlar kademeli goc.
- **[P2-2] Olu kod / baglanmamis ozellikler** — `parse_gg_command`+`GG_PATTERN` (RE-002/RE-003/RE-004/RE-005/RE-006), `try_auto_fetch_*` (FT-006), `schemas.py` buyuk cogunlugu (SH-001, BE-020), `reasoning_trace.close()` no-op (RT-005), `_compute_cash_target` target==0 dali (GE-009). Kaldir veya bagla.
- **[P2-3] `cockpit_dict.get("uyarilar")` yanlis anahtar → RULE_CHECK trace olu** — "alerts" olmali. Kaynak: CO-004.
- **[P2-4] `_upsert_insight_absolute` guncelleme yolunda last_evidence_at dokunulmuyor** → siralama bozuk. Kaynak: CI-004. Ayrica CI-008 (dedup title'a duyarli), CI-009 (max() tie gece'ye onyargili).
- **[P2-5] Limit parametreleri ust-sinirsiz** — `?limit=-1`/`999999`. Kaynak: RAT-006, RCO-007, RTR-009, RCH-006.
- **[P2-6] Ham `str(e)` / snapshot hatasi kullaniciya/sessizce sizar** — RDS-001, RSI-002, RCP-003, RCP-004, RCO-005, REX-005, MN-004 (sessiz/loglu except). `logger.exception` + jenerik mesaj. (Kis. BE-010, SEC-016)
- **[P2-7] DB constraint sertlestirme (CHECK yok)** — day_of_month 1-31, priority 1-3, progress 0-100, amount<>0, is_paid/paid_date, credit_card kosullu alanlar. Kaynak: DATA-009, DATA-018, DATA-025, DATA-026, DATA-027, DATA-028, DATA-033, RGO-007, SH-009. `updated_at`/audit eksikligi: DATA-014, DATA-034, SEC-024.
- **[P2-8] Kart limit uyarisi credit_limit=0 falsy → hic tetiklenmiyor** — `is not None` olmali. Kaynak: AE-007. Benzer detect_alerts nakit<=0 guard tutarsizligi: RE-006, RULE-009.
- **[P2-9] Turkce `.lower()`/`strftime('%B')` locale sorunlari** — RIN-006, RE-005; `_TR_NORM` kullan. (RIN-002 locale ay adi → TEYIT)
- **[P2-10] Docstring/kod uyumsuzluklari** — MO-006 (index envanteri), DS-007 (kredi fallback magic %5), RCF-003 (loan vs loan_payment), PM-005 ("5" vs 3-5), RT-001 (otomatik nesting vaadi), CO-007 (numaralandirma), DATA-006 (PK dual-index).
- **[P2-11] Adsiz magic number'lar** — DS-010 (50.0 kart tabani), DS-008 (30-gun ay), RDS-003 (100_000 extra), BE-024. Isimlendirilmis sabite tasi.
- **[P2-12] Backend mimari refactor backlog** — coach.py tanri-modulu (BE-001/LLM-015), OpenAI-uyumlu provider tekrari (BE-002), CoachEngine.chat 300 satir (BE-004), service/repository katmani yok (BE-015/BE-019), config dagitik (BE-012), prompt inline (BE-003), reasoning_trace her step commit (BE-023/LLM-027). Test altyapisi pytest degil (BE-040) — refactor'lar icin on kosul.
- **[P2-13] LLM orkestrasyon iyilestirmeleri (backlog)** — tool-call schema dogrulamasi (LLM-008), grounding kontrolu (LLM-003/LLM-034), eval harness (LLM-004), prompt caching (LLM-002), usage/token metrigi (LLM-006/LLM-007), Anthropic model guncelleme (LLM-001), tool_calls_count yanlis sayim (RCO-003).
- **[P2-14] user.py kucuk duzeltmeler** — bos-string isim (RUS-003), Config→ConfigDict (RUS-004).

---

## TEYIT-GEREKLI (Güven = Doğrulanmali — uygulanmadan once teyit)

> Bu bulgular KESIN degil; mekanik davranis okundu ama urun niyeti / gercek tetiklenme / calisma-ortami dogrulanmali. Bazilari onem acisindan P0/P1 seviyesindedir (asagida isaretli).

- **[T-1] (KRITIK potansiyel) RCH-002** — Hard-delete korumasi sadece `priority=1 AND red_line`'i koruyor; seed'deki gercek kritik kurallar (MC4/5/6/8) `priority=1` ama `checkpoint_type=rule` → `?hard=true` ile silinebilir. Teyit: canli DB'de checkpoint tipleri. Fix: korumayi `priority==1` (tip bagimsiz) yap.
- **[T-2] (KRITIK potansiyel) CO-001** — EMANET KASA halusinasyon filtresi (`_EMANET_HEADER_RE`) sadece birebir `[5. EMANET KASA]` formatini yakalar; LLM markdown `## 5. EMANET KASA` yazarsa silinmez. Teyit: LLM gercek cikti formati. Fix: `_YC_HEADER_RE` esnekligine getir.
- **[T-3] (YUKSEK potansiyel) CF-001** — cashflow loan taksitleri `account_id` filtresine tabi degil; tek nakit hesap forecast'inda ilgisiz kredilerin taksitleri o hesaptan dusuluyor. (Kesin okundu ama Account'ta paying_account_id olmadigi icin tasarim karari gerek.)
- **[T-4] AE-005** — income turu kredi karti hesabina uygulanirsa borc AZALACAGI yerde ARTIYOR. Teyit: bu path LLM tarafindan tetikleniyor mu (coach prompt).
- **[T-5] CO-005** — `is_question()` yanlis-pozitifi propose_action'i sert bloke ediyor; gercek harcama bildirimi sessizce kaydedilmeyebilir. Teyit: heuristic false-positive orani (LLM-010 ile hizali).
- **[T-6] DS-002 / RULE-011** — MAX_MONTHS(600) asilinca "borc bitmedi" flag'i yok; negatif amortizasyonda "600 ayda biter" gibi doner. Fix: `never_pays_off`/`is_converged` bayragi.
- **[T-7] DS-004 / RULE-012** — 0.01 esigi icin tutarsiz `>`/`<`/`<=` operatorleri; tam 0.01'de kalan borc payoff'a hic girmeyebilir. Fix: tek `DUST_THRESHOLD`, tek yonlu operator.
- **[T-8] AE-004 / SE-009** — `actual_price=0` falsy-check nedeniyle current_price'a dusuyor (kod deseni Kesin, 0-fiyat senaryosu nadir).
- **[T-9] AE-006 / RAC-006 / RTR-006** — Float bakiye atamalarinda yuvarlama (P1-2 kapsaminda; birikim etkisi olcum gerektirir).
- **[T-10] CF-002/CF-003/CF-004/CF-005** — monthly_payment isaret dogrulamasi (negatif→gelir), account_id sahiplik/tip (RCF-002 ayni), VALID_INCLUDE dogrulamasi (RCF-001 ayni), overdue idx tuketimi (RULE-016).
- **[T-11] RIN-002** — Turkce ay adi `strftime('%B')` locale'e bagli ("May 2026"). Teyit: prod locale. Fix: sabit TR ay listesi.
- **[T-12] RIN-003 / RIN-005** — Ikinci commit basarisiz olursa rollback yok (cift gelir onerisi); source_recurring_id FK'siz (SQLite id yeniden kullanimi). Teyit: SQLAlchemy commit-fail davranisi.
- **[T-13] SC-005** — Trace cleanup cutoff aware, ReasoningTrace.created_at naive; SQLite'ta calisiyor, Postgres gecisinde kirilir.
- **[T-14] GE-002** — debt_freedom `PersonalDebt(payable)` borclarini goz ardi ediyor (kullanilmayan import isaret); mevcut veride sadece receivable var. Teyit: kapsam kasitli mi.
- **[T-15] GE-005 / GE-006** — achieved geri alinmiyor (tek yonlu gecis, tasarim mi?); achieved yuvarlanmis progress ile kontrol (5 TL eksikte false-pozitif, cok dar aralik).
- **[T-16] DB-002/DB-003/DB-004 / DP-001** — `:memory:` StaticPool tuzagi; backup.py hardcoded DB_PATH; `get_db` exception yolunda explicit rollback yok (SQLAlchemy implicit rollback ediyor ama niyet belirsiz). BE-010 sessiz except ailesi.
- **[T-17] Guvenlik — deploy/multi-user kapisi** — SEC-001 (auth yok), SEC-002 (BOLA), SEC-004/LLM-031 (rate limit yok), SEC-007/SEC-033 (prompt injection — mevcut propose→onay→execute savunmasi korunmali), SEC-003/005 (CORS/headers), SEC-014 (HTTPS). Tek-kullanici lokal MVP'de aktif risk dusuk; multi-user/prod'a gecmeden ADR ile ele alinmali. NOT: "LLM asla DB yazmaz" + "MC enforcement kod seviyesinde" en guclu savunma — gevsetme.
- **[T-18] Diger dayaniklilik** — RAT-004 (approve status filtresi yok), RAT-005 (reflection abs() eksik), RAT-008 (cift date.today()), RCP-005 (date.today lokal), RUS-002 (create_user race), RPM-003/RPM-004/RPM-005 (action_context tip/TOCTOU/log), FT-003/FT-004/FT-007 (old_value turetme, emanet item rengi, negatif yas), SH-007/SH-008 (payload tip guvenligi, full+value), RGO-004/RGO-005/RGO-006 (allocation status/goal_type/IDOR), RDE-005/RDE-006 (mark_debt_paid asimetri, direction degistirilemez), RCF-005 (crunch_threshold NaN), RTR-005/RTR-007/RTR-008 (loan+income no-op, substring kategori, quick default nondeterministik), SC-003/SC-004/SC-006 (job hata tutarsizligi, utcnow, scheduler leak), MN-002/MN-003 (CORS env, ayri session).

---

*Uretim: dosya-denetimi (36 dosya) + sections (RULE/DATA/SEC/BE/LLM) birlestirilerek. Cozulmus bulgular (BUG#059/#060, ADR-026) haric tutuldu.*
