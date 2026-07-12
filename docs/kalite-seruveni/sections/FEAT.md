# Finansal ürün özellikleri (kod: FEAT)

Kapsam: FinancialOS'e YENİ finansal değer katacak özellikler. Kod kalitesi değil,
yeni yetenek. Her madde mevcut mimariye oturur: Rules Engine hesaplar, LLM açıklar,
akış her zaman propose_action → onay → execute; LLM asla DB yazmaz.

Kısıt: Kişiselleştirilmiş yatırım tavsiyesi YOK. Yatırımla ilgili maddeler yalnızca
nötr görünürlük / araç / otomasyon sağlar; "al/sat" önermez.

Zaten planlanan (Wave-2 A1-A3, D1-D4, Tema B grafikleri; Wave-3 LangGraph/DSPy/
observability/FSD/KVKK/i18n) TEKRARLANMADI. Aşağıdakiler yeni yeteneklerdir.

---

### [FEAT-001] ✅ UYGULANDI Zarf bütçe (envelope budgeting)
- **Değer/Fırsat:** Kategori bazlı aylık zarf; her kategoriye tutar ayrılır, harcama zarftan düşer, zarf biterse görünür şekilde bloklanır/uyarır. Günlük 62 TL limitinin üstüne kategori disiplini ekler.
- **Kaynak/İlham:** YNAB / Actual Budget zarf yöntemi.
- **Nasıl (mimari):** Yeni EnvelopeAllocation tablosu + rules_engine'de zarf bakiyesi hesabı; Transactions kaydı zarfı düşürür. Cockpit'e zarf durumu chip'i. Zarf aşımında LLM açıklar, kullanıcı transfer'i propose_action ile onaylar.
- **Etki:** Yüksek · **Efor:** L

### [FEAT-002] ✅ UYGULANDI Atanmamış nakit göstergesi ("her liraya görev")
- **Değer/Fırsat:** Nakit kasadaki henüz bir zarfa/hedefe atanmamış tutarı tek sayı olarak gösterir; "boşta para" psikolojik olarak harcanır, atanınca korunur.
- **Kaynak/İlham:** YNAB "Ready to Assign" / "give every dollar a job".
- **Nasıl (mimari):** rules_engine generate_cockpit'e `atanmamis_nakit = nakit - (zarflar + hedef allocation)` metriği. FEAT-001 zarflarına bağlı; salt hesap.
- **Etki:** Orta · **Efor:** S

### [FEAT-003] Birikim zarfları (sinking funds) ✅ UYGULANDI (11 Tem 2026)
- **Değer/Fırsat:** Düzensiz yıllık giderleri (MTV, sigorta, tatil, bayram) aylık küçük parçalara böler; "büyük fatura şoku" ortadan kalkar.
- **Kaynak/İlham:** Sinking funds (davranışsal bütçe), YNAB true expenses.
- **Nasıl (mimari):** goal_engine'e yeni goal_type `sinking_fund` (hedef tutar + hedef tarih → aylık gereken). goal_rules ile otomatik allocation. Progress mevcut allocation mekanizmasıyla.
- **Etki:** Yüksek · **Efor:** M
- **Durum:** `sinking_fund_plan` (goal_engine, saf) — aylık gereken = kalan / kalan_ay + gecikmiş/tamamlandı. **Tasarım kararı:** yeni goal_type YERİNE "cash_target + target_date = sinking fund" (daha az yüzey, geri-uyumlu). `GoalRead.sinking_fund` **computed_field** (serileştirmede türetilir → şema/DB DEĞİŞMEZ, Alembic'siz güvenli). Goals.jsx "💧 Aylık gereken X TL/ay · N ay" satırı. 10 test.

### [FEAT-004] Paranın yaşı (Age of Money) metriği
- **Değer/Fırsat:** Harcanan paranın kaç gün önce kazanıldığını gösterir; buffer sağlığının tek sayılık göstergesi, "maaştan maaşa" yaşamaktan çıkışı ölçer.
- **Kaynak/İlham:** YNAB Age of Money.
- **Nasıl (mimari):** rules_engine'de gelir/gider FIFO eşleştirmesiyle saf hesap; Cockpit metriği. Sadece okuma.
- **Etki:** Orta · **Efor:** M

### [FEAT-005] Kategori bütçe aşım tahmini ✅ UYGULANDI (11 Tem 2026)
- **Değer/Fırsat:** Ay ortasında mevcut harcama hızıyla hangi kategorinin ay sonunda bütçeyi aşacağını önceden söyler ("bu gidişle market zarfı 8 gün erken bitecek").
- **Kaynak/İlham:** Copilot / YNAB projected spending.
- **Nasıl (mimari):** rules_engine'de kategori günlük ortalama × kalan gün projeksiyonu (mevcut _calculate_category_patterns altyapısını genişletir). LLM açıklar; aksiyon yok.
- **Etki:** Yüksek · **Efor:** M
- **Durum:** `_category_overspend_alerts` — ay-içi hız × kalan gün projeksiyonu vs GEÇEN AY (envelope bütçe YOK, geçen ay yumuşak referans → FEAT-001 bağımlılığı aşıldı). > geçen ay ×1.15 ise uyarı; ay başı (< 5 gün) gürültü atlanır; top-2 → cockpit alerts (koç Kural 14). 6 test.

### [FEAT-006] Abonelik denetçisi ✅ UYGULANDI (11 Tem 2026, detection+endpoint)
- **Değer/Fırsat:** İşlem geçmişinden aynı tutarlı tekrarlayan ödemeleri (Netflix, Spotify, üyelik) otomatik tespit eder, toplam aylık/yıllık abonelik yükünü çıkarır. Kullanılmayanı işaretler.
- **Kaynak/İlham:** Rocket Money / Copilot subscription detection.
- **Nasıl (mimari):** rules_engine'de merchant+tutar tekrarı deseni; tespit edilenler RecurringExpense'e dönüştürülmek üzere propose_action ile önerilir, kullanıcı onaylar.
- **Etki:** Yüksek · **Efor:** M
- **Durum:** `detect_subscriptions` (rules_engine, salt okuma) + `GET /api/subscriptions`. Algoritma harici araştırmayla (Rocket Money/Monarch) doğrulandı: 180g tarama → description grubu → medyan aralık aylık/yıllık + **farklı-tutar ≤ 2** ayırt edicisi (fiyat artışına tolerans, değişken harcama elenir). `fiyat_degisti` bayrağı = FEAT-007 sinyali. RecurringExpense "— ay" soneki normalize. 9 test. Kalan (follow-up): propose→RecurringExpense dönüştürme + FE panel.

### [FEAT-007] Abonelik fiyat artışı (price creep) tespiti ✅ UYGULANDI (11 Tem 2026)
- **Değer/Fırsat:** Bir aboneliğin tutarı sessizce arttığında uyarır ("Spotify 59.99'dan 74.99'a çıktı"). Fark edilmeyen zamları görünür kılar.
- **Kaynak/İlham:** Rocket Money price-increase alerts.
- **Nasıl (mimari):** rules_engine tekrarlayan ödeme grubunda tutar deltası kontrolü; detect_alerts'e yeni uyarı tipi. Salt görünürlük.
- **Etki:** Orta · **Efor:** S
- **Durum:** `_subscription_price_alerts` — detect_subscriptions'a eklenen `eski_tutar`/`yeni_tutar` üzerinden; yeni > eski ise uyarı seviyesi cockpit alert'i (%artış + eski→yeni). Yalnızca artış (düşüş değil). generate_cockpit'e bağlı → koç Kural 14 ile proaktif. 4 test. Bağımlı: FEAT-006.

### [FEAT-008] Abonelik iptal hatırlatıcı + yıllık maliyet paneli
- **Değer/Fırsat:** Deneme süresi/yenileme yaklaşınca proaktif hatırlatma ve "bu abonelik yılda X TL" çerçevesi; iptal kararını kolaylaştırır.
- **Kaynak/İlham:** Rocket Money cancellation reminders.
- **Nasıl (mimari):** RecurringExpense üzerine `is_subscription`+yenileme günü; scheduler nightly batch koça hatırlatma insight'ı yazar (FEAT-006 ile bağlı). LLM açıklar.
- **Etki:** Orta · **Efor:** S

### [FEAT-009] "Harcanabilir güvenli tutar" (safe-to-spend) ✅ UYGULANDI (11 Tem 2026)
- **Değer/Fırsat:** Yaklaşan tüm faturalar/taksitler/hedef katkıları düşüldükten sonra bugün gerçekten güvenle harcanabilir tek sayı. Günlük limitten daha güçlü, ileriye bakan sinyal.
- **Kaynak/İlham:** Copilot "Safe to Spend" imza metriği.
- **Nasıl (mimari):** cashflow forecast + rules_engine: en düşük gelecek bakiye tamponu üzerinden hesap. Cockpit metriği; salt okuma.
- **Etki:** Yüksek · **Efor:** M
- **Durum:** `_calculate_safe_to_spend` (rules_engine) — `guvenli_harcama = max(0, lowest_forecast_balance - buffer)`; #121 forecast summary'sinden paylaşımlı (tek hesap). Cockpit kutusu + koç context'i + 8 test. Kapsam notu: kart döngüsü hariç (kart-ayarlı daily_limit ile birlikte okunur). Bağımlı: BUG #121 (ileriye dönük nakit krizi).

### [FEAT-010] Nakit runway (kaç gün dayanır) ✅ UYGULANDI (11 Tem 2026)
- **Değer/Fırsat:** "Hiç gelir gelmezse mevcut nakit kaç gün yeter" göstergesi; belirsizlik/işsizlik kaygısını somut sayıya indirger.
- **Kaynak/İlham:** Maybe Finance / startup runway kavramı.
- **Nasıl (mimari):** cashflow'da ortalama günlük net çıkış × mevcut likit bakiye; Cockpit metriği. Salt hesap.
- **Etki:** Orta · **Efor:** S
- **Durum:** `_calculate_cash_runway` — `nakit_runway_gun = nakit / (son 30g gider / 30)`; nakit çağırandan (re-query yok), gider yoksa None. Cockpit kutusu (Clock, <30g kırmızı) + koç context. 5 test. İleriye-dönük solvency üçlüsünü (#121 kriz + FEAT-009 safe-to-spend + FEAT-010 runway) tamamlar.

### [FEAT-011] Maaş-öncesi tükeniş erken uyarısı
- **Değer/Fırsat:** Mevcut harcama hızıyla bir sonraki maaştan önce bakiyenin sıfırın altına ineceği günü önceden bildirir ve kaç TL kısılması gerektiğini söyler.
- **Kaynak/İlham:** Copilot / cash-flow forecasting; davranışsal "payday cliff".
- **Nasıl (mimari):** cashflow crunch tespitini maaş döngüsüne bağlar; detect_alerts'e proaktif uyarı. LLM açıklar, gerekirse harcama kısma önerisi (aksiyon değil).
- **Etki:** Yüksek · **Efor:** S

### [FEAT-012] Borçsuzluk tarihi + kartopu zaman çizelgesi ✅ UYGULANDI
- **Değer/Fırsat:** "Bu tempoyla 14 Mart 2028'de borçsuzsun" tek tarih + aylık ilerleme çizelgesi. 5 kredi + kart yükünde en güçlü motivasyon aracı.
- **Kaynak/İlham:** Debt payoff psychology (Ramsey momentum), Undebt.it payoff date.
- **Nasıl (mimari):** debt_strategy zaten snowball/avalanche simüle ediyor; çıktıya borçsuzluk tarihi + aylık kalan-borç serisi eklenir. LLM açıklar.
- **Etki:** Yüksek · **Efor:** S

### [FEAT-013] Faiz sızıntısı sayacı ✅ UYGULANDI
- **Değer/Fırsat:** Şu ana kadar ödenen toplam faizi ve mevcut planla ödenecek kalan faizi gösterir ("kredilerin sana bu yıl 41.200 TL faize mal oldu"). Görünmez maliyeti görünür yapar.
- **Kaynak/İlham:** Davranışsal finans — faizin somutlaştırılması.
- **Nasıl (mimari):** debt_strategy/rules_engine amortisman hesabı (Account.interest_rate, taksit). Cockpit/DebtStrategy metriği; salt okuma.
- **Etki:** Yüksek · **Efor:** M

### [FEAT-014] Çoklu kredi konsolidasyon simülatörü ✅ UYGULANDI (12 Tem 2026)
- **Değer/Fırsat:** 5 ayrı krediyi tek konsolidasyon kredisiyle değiştirmeyi modeller: yeni taksit, toplam faiz, vade karşılaştırması. Türkiye'de yaygın; nötr karşılaştırma aracı, tavsiye değil.
- **Kaynak/İlham:** Türkiye çoklu kredi konsolidasyonu; debt consolidation calculators.
- **Nasıl (mimari):** simulation_engine'e "consolidation" senaryosu (RAM kopyası, gerçek DB'ye dokunmaz) + debt_strategy amortisman. Kullanıcı faiz/vade girer, sistem hesaplar.
- **Etki:** Yüksek · **Efor:** M
- **Durum:** İki katman. (1) `calculate_consolidation_baseline` (debt_strategy, saf, ASSUMPTION-FREE): ağırlıklı ort. aylık oran = Σ(bakiye×oran)/Σbakiye = konsolidasyon EŞİĞİ. Konsolidasyon yalnız teklif oran bu eşiğin altındaysa faiz-avantajlı. Kullanıcının KENDİ borçlarından türetilir (dış varsayım yok). Cockpit `konsolidasyon` + koç context (proaktif, nötr eşik — Kural: tavsiye değil). (2) `simulate_consolidation` + `_annuity_payment` (annüite formülü): teklif oran+vade → yeni taksit/toplam faiz; `GET /api/debt-strategy/consolidation?rate&term` (<2 borç→404, oran>20→422). DebtStrategy.jsx what-if formu (eşik client-side, kesin sayı endpoint). 12 test. `collect_debts` FEAT-012/015 ile paylaşımlı.

### [FEAT-015] Kart asgari-ödeme tuzağı göstergesi ✅ UYGULANDI (12 Tem 2026)
- **Değer/Fırsat:** "Sadece asgari ödersen bu kart 11 yılda kapanır ve X TL faiz ödersin" uyarısı. Kart %99.8 doluyken kritik farkındalık.
- **Kaynak/İlham:** ABD kredi kartı ekstrelerindeki zorunlu "minimum payment warning".
- **Nasıl (mimari):** debt_strategy'de asgari-ödeme-only senaryosu; detect_alerts uyarısı. LLM açıklar. Salt hesap.
- **Etki:** Yüksek · **Efor:** S
- **Durum:** `calculate_min_payment_trap` (debt_strategy, saf) — her kart için `_simulate([kart],[id], extra=0)` azalan %25 asgari (TR) trajektorisi (mevcut motor; BUG #079 azalan-min + RULE-011 asla-bitmez korumalı). Kredi HARİÇ (kart-spesifik kavram). `_min_payment_trap_alerts`: asla-bitmez (asgari<faiz, eşik %33.3) → KRİTİK "sarmal"; ≥12 ay uzun kuyruk → UYARI (yalnız en kötü kart, #126 alert-yorgunluğu). Cockpit `asgari_tuzagi` + koç context block + grounding (`_coach_extra_numbers`) + Cockpit.jsx kartı. Murat kanonik: Ziraat 22 ay / 2.318 TL faiz. 12 test. `collect_debts` FEAT-012 ile paylaşımlı (tek sorgu).

### [FEAT-016] Kart kullanım oranı (utilization) + kredi sağlığı ✅ UYGULANDI (12 Tem 2026)
- **Değer/Fırsat:** Kart borcu/limit oranını (%99.8) ve iyileşme trendini gösterir; limit yönetimi ve borç azaltma ilerlemesini tek metrikte izler.
- **Kaynak/İlham:** Credit utilization (kredi skoru davranışı), Monarch credit tracking.
- **Nasıl (mimari):** rules_engine'de Account.balance / credit_limit; Cockpit metriği + NetWorthSnapshot benzeri zaman serisi. Salt okuma.
- **Etki:** Orta · **Efor:** S
- **Uygulama:** `calculate_card_utilization` (rules_engine, saf) — toplam kart borcu/limit, band (saglikli<30<orta<70<yuksek<90<kritik), `saglikli_borc_hedefi` (%30'a inmek için borç seviyesi = somut çapa), trend (en eski NetWorthSnapshot kart borcu ÷ GÜNCEL limit — limit stabil varsayımı; ≥7 gün). Cockpit `kart_kullanim` + koç context bloğu (yalnız yuksek/kritik → gürültü yok; grounding'e oran/hedef/trend tanıtıldı) + Cockpit.jsx utilization çubuğu (band rengi + trend oku). 9 test. Not: mevcut per-kart `kullanim_orani` yalnız kart-döngüsü detayındaydı; bu agregat + trend + kredi-sağlık çerçevesi ekler.

### [FEAT-017] Borçsuzluk milestone rozetleri ✅ UYGULANDI (12 Tem 2026, ilerleme metriği)
- **Değer/Fırsat:** "İlk kredi kapandı", "toplam borç %25 azaldı", "kart 5 hane altına indi" gibi eşiklerde kutlama/rozet; kartopu momentumunu davranışsal olarak besler.
- **Kaynak/İlham:** Debt payoff psychology, gamification (Qapital, Ramsey baby steps).
- **Nasıl (mimari):** rules_engine eşik tespiti → CoachInsight (breakthrough extractor mevcut) → koç proaktif kutlar. DB yazımı yok, insight katmanı.
- **Etki:** Orta · **Efor:** S
- **Durum:** `calculate_debt_progress` (rules_engine, saf) — en eski NetWorthSnapshot'tan bugüne toplam borç (kart+kredi) azalması: "başladığından beri X TL / %Y ödedin." ≥7 gün geçmiş + başlangıç>0 guard. Cockpit `borc_ilerleme` + koç context "momentum" bloğu (yalnız gerçek ilerlemede — Ramsey davranışsal #1 faktör; grounding'e tanıtıldı). Kokpit yoğunluğu artmasın diye ayrı prominent kart YOK, koç motivasyonu üzerinden. NetWorthSnapshot günlük birikir → zamanla aktifleşir. 7 test. (Eşik-crossing rozet/insight katmanı — follow-up; bu metrik ilerleme görünürlüğünü sağlar.)

### [FEAT-018] Acil durum fonu hedefi (otomatik target)
- **Değer/Fırsat:** Ortalama aylık giderden 3-6 aylık acil fon hedefini otomatik hesaplar ve ilerlemeyi izler; finansal dayanıklılığın temel taşı.
- **Kaynak/İlham:** Emergency fund (kişisel finans standardı), Monarch/YNAB.
- **Nasıl (mimari):** goal_engine'e `emergency_fund` goal_type; target = ortalama aylık gider (reports altyapısı) × N. Allocation mevcut mekanizma.
- **Etki:** Yüksek · **Efor:** M

### [FEAT-019] Yuvarlama birikimi (round-up)
- **Değer/Fırsat:** Her harcamayı bir üst 10/100 TL'ye yuvarlayıp farkı bir hedefe otomatik yönlendirmeyi önerir; fark edilmeden biriktirme.
- **Kaynak/İlham:** Acorns / Qapital round-ups (nötr otomasyon, yatırım değil birikim).
- **Nasıl (mimari):** goal_rules'a round-up kural tipi; her Transaction sonrası fark hesaplanır, GoalAllocation propose_action ile önerilir/onaylanır. LLM DB yazmaz.
- **Etki:** Orta · **Efor:** M

### [FEAT-020] Harcama molası / no-spend streak challenge
- **Değer/Fırsat:** "Harcamasız gün" serisi sayacı ve mikro meydan okuma; impuls harcamayı oyunlaştırarak azaltır.
- **Kaynak/İlham:** No-spend challenge (davranışsal), Lunch Money etiketleme kültürü.
- **Nasıl (mimari):** rules_engine gün bazında harcama=0 serisi; Cockpit rozeti + koç teşviki. Salt okuma + insight.
- **Etki:** Orta · **Efor:** S

### [FEAT-021] Net değer değişim ayrıştırması (attribution) ✅ UYGULANDI
- **Değer/Fırsat:** Net değer değişiminin ne kadarının tasarruf/borç ödeme, ne kadarının yatırım fiyat hareketi olduğunu ayrıştırır ("bu ay +18.000; 12.000'i borç ödeme, 6.000'i fon değerlenmesi").
- **Kaynak/İlham:** Maybe Finance / Monarch net worth attribution.
- **Nasıl (mimari):** rules_engine iki NetWorthSnapshot arası delta + PriceHistory ile fiyat etkisini ayırır. reports metriği; salt okuma (yatırım tavsiyesi değil, açıklama).
- **Etki:** Orta · **Efor:** M

### [FEAT-022] Finansal sağlık skoru (composite) ✅ UYGULANDI
- **Değer/Fırsat:** Tasarruf oranı + borç/gelir + kart kullanımı + nakit tamponu birleşik 0-100 skoru; sistemin genel durumunu tek bakışta özetler ve trendini gösterir.
- **Kaynak/İlham:** Copilot/Monarch health score, CFPB Financial Well-Being.
- **Nasıl (mimari):** rules_engine'de bileşen metrikleri (çoğu FEAT-016/023/010'dan) ağırlıklı skor. Cockpit; salt hesap.
- **Etki:** Orta · **Efor:** M

### [FEAT-023] Tasarruf oranı metriği
- **Değer/Fırsat:** Aylık (gelir − gider) / gelir oranını gösterir ve önceki aylarla kıyaslar; "ne kadar biriktiriyorum" sorusunun net cevabı.
- **Kaynak/İlham:** Savings rate (FIRE / kişisel finans temel metriği).
- **Nasıl (mimari):** reports/rules_engine mevcut gelir-gider toplamlarından; NetWorthSnapshot benzeri aylık seri. Salt okuma.
- **Etki:** Orta · **Efor:** S

### [FEAT-024] Enflasyon-düzeltilmiş (reel) net değer ✅ UYGULANDI
- **Değer/Fırsat:** Nominal net değer artsa bile TÜFE karşısında satın alma gücünün ne olduğunu gösterir; Türkiye yüksek enflasyon bağlamında kritik gerçeklik kontrolü.
- **Kaynak/İlham:** Türkiye enflasyon muhasebesi; reel getiri kavramı.
- **Nasıl (mimari):** Kullanıcı aylık TÜFE'yi manuel girer (fund_tracker manuel fiyat paterni gibi); rules_engine NetWorthSnapshot'ı baz aya deflate eder. Salt okuma, nötr.
- **Etki:** Yüksek · **Efor:** M

### [FEAT-025] TEFAS çoklu fon karşılaştırma + enflasyon benchmark
- **Değer/Fırsat:** Birden fazla TEFAS fonunu yan yana getirir ve getirilerini enflasyon/mevduat gibi nötr referanslarla kıyaslar. Görünürlük sağlar, "al/sat" önermez.
- **Kaynak/İlham:** TEFAS fon takibi; Maybe Finance benchmark görünümü.
- **Nasıl (mimari):** fund_tracker + PriceHistory zaman serisi; reports'ta karşılaştırma çıktısı. LLM sadece açıklar, tavsiye vermez (KISIT).
- **Etki:** Orta · **Efor:** M

### [FEAT-026] Altın/döviz varlık takibi
- **Değer/Fırsat:** Gram altın, USD/EUR gibi varlıkları manuel fiyatla portföye ekleyip net değere dahil eder; Türkiye'de yaygın tasarruf araçlarının görünürlüğü.
- **Kaynak/İlham:** Türkiye döviz/altın tasarruf kültürü; Maybe multi-asset.
- **Nasıl (mimari):** Account investment tipine alt-tür + fund_tracker manuel fiyat/tazelik mekanizması yeniden kullanılır. rules_engine net değere ekler. Nötr, tavsiye yok.
- **Etki:** Orta · **Efor:** M

### [FEAT-027] Alacak yaşlandırma (aging) raporu ✅ UYGULANDI (12 Tem 2026)
- **Değer/Fırsat:** 13 dağınık alacağı vade yaşına göre gruplar (0-30 / 31-60 / 60+ gün gecikmiş) ve toplam riski gösterir; hangi alacağın peşine düşüleceğini netleştirir.
- **Kaynak/İlham:** Muhasebe accounts-receivable aging; alacak takibi.
- **Nasıl (mimari):** rules_engine PersonalDebt (receivable, is_paid=False) üzerinde due_date yaşlandırması; reports çıktısı. Salt okuma.
- **Etki:** Yüksek · **Efor:** S
- **Durum:** `calculate_receivables_aging` (rules_engine, saf) — kovalar (öncelik: en çok geciken önce) 60+ / 31-60 / 1-30 gün gecikmiş · vadesi gelmemiş · tarihsiz (kör nokta). Boş kova atlanır; `en_riskli` = en çok geciken 3 kalem. Cockpit `alacak_yaslanma` + koç context block (grounding'e tanıtıldı, koç Kural 12 "zamanında tahsil et") + Cockpit.jsx kartı. `_collect_overdue_debts` per-kalem alert'ini GRUPLU stratejik özetle tamamlar. 7 test.

### [FEAT-028] Alacak hatırlatma mesaj taslağı
- **Değer/Fırsat:** Vadesi gelen bir alacak için gönderilmeye hazır nazik hatırlatma mesajı taslar ("Efe, geçen ay konuştuğumuz 2.500 TL..."). Tahsilatın sosyal sürtünmesini azaltır.
- **Kaynak/İlham:** Davranışsal — sosyal borç tahsilatı; müşteri iletişim şablonları.
- **Nasıl (mimari):** coach LLM alacak bağlamıyla metin üretir — SADECE açıklama/metin, DB'ye yazmaz, mesaj göndermez. Kullanıcı kopyalar. Mimariyi bozmaz.
- **Etki:** Orta · **Efor:** S

### [FEAT-029] Yıllık yükümlülük takvimi (MTV, vergi, sigorta)
- **Değer/Fırsat:** Türkiye'ye özgü yıllık/dönemsel zorunlu ödemeleri (MTV iki taksit, trafik sigortası, aidat) tanımlayıp sinking fund ile aylık ayırır ve vadesinde hatırlatır.
- **Kaynak/İlham:** Türkiye vergi/yükümlülük takvimi; sinking funds.
- **Nasıl (mimari):** FEAT-003 sinking fund + cashflow forecast'a yıllık olay tipi; scheduler hatırlatma. propose_action ile ödeme kaydı onaylanır.
- **Etki:** Orta · **Efor:** M

### [FEAT-030] Satın alma fırsat maliyeti simülatörü ✅ UYGULANDI (12 Tem 2026)
- **Değer/Fırsat:** "Bu 8.000 TL'yi harcarsam vs karta yatırırsam" karşılaştırması: borçsuzluk tarihine ve faize etkisini gösterir. İmpuls harcamayı somut maliyetle yavaşlatır.
- **Kaynak/İlham:** Opportunity cost (davranışsal finans); what-if.
- **Nasıl (mimari):** simulation_engine'de harcama-vs-borç-ödeme senaryosu (RAM kopyası) + debt_strategy. LLM açıklar; aksiyon opsiyonel.
- **Etki:** Orta · **Efor:** M
- **Durum:** `simulate_purchase_opportunity_cost` (debt_strategy, saf): baseline avalanche vs amount'ı EN YÜKSEK FAİZLİ borca ŞİMDİ ödeyince yeniden avalanche → fark (kaç ay geç + kaç TL fazla faiz). Assumption-free (mevcut avalanche motoru; dataclasses.replace ile RAM kopyası). `GET /api/debt-strategy/opportunity-cost?amount` (borç yoksa 404, amount≤0 → 422). DebtStrategy.jsx "Harcama Fırsat Maliyeti" formu. Murat kanonik: 8000 TL harcamak = ~1517 TL fazla faiz. 8 test. İnvariant: borca ödeme toplam faizi ARTIRMAZ (faiz_tasarrufu ≥ 0). collect_debts paylaşımlı.

### [FEAT-031] Harcama tetikleyici / duygu etiketi günlüğü
- **Değer/Fırsat:** İşleme opsiyonel bağlam/duygu etiketi (stres, sıkıntı, kutlama) eklenir; koç zamanla "stresliyken market harcaman 2x" gibi desenleri ortaya çıkarır.
- **Kaynak/İlham:** Lunch Money etiketleme; davranışsal harcama tetikleyicileri (emotional spending).
- **Nasıl (mimari):** Transaction'a etiket alanı; coach_insights yeni extractor (deterministik desen). Koç açıklar, DB yazmaz.
- **Etki:** Orta · **Efor:** M

### [FEAT-032] 24-saat impuls bekleme kuralı / istek listesi ✅ UYGULANDI (12 Tem 2026)
- **Değer/Fırsat:** Büyük/plansız alımı hemen yapmak yerine "istek listesine" ekler; 24 saat sonra koç hatırlatır ve hâlâ isteyip istemediğini sorar. İmpuls harcamayı kırar.
- **Kaynak/İlham:** 24-hour rule / spending pause (davranışsal finans).
- **Nasıl (mimari):** Küçük Wishlist tablosu + scheduler 24 saat sonra koça hatırlatma insight'ı. Alım gerçekleşirse propose_action → onay → execute.
- **Etki:** Orta · **Efor:** M

### [FEAT-033] Ay-karşılaştırma otomatik anlatı (MoM)
- **Değer/Fırsat:** "Bu ay geçen aya göre" gelir/gider/net değişim ve kategori kaymalarını otomatik anlatı olarak üretir; salt grafiğin ötesinde yorum.
- **Kaynak/İlham:** Copilot aylık "recap"; Monarch monthly review.
- **Nasıl (mimari):** rules_engine iki ay karşılaştırması hesaplar (sayılar), coach açıklar. Aylık rapor (A3) planlı olsa da bu, ay-üstü karşılaştırma yorumu olarak ayrı katman.
- **Etki:** Orta · **Efor:** S

### [FEAT-034] Otomatik kategori etiketleme ✅ UYGULANDI
- **Değer/Fırsat:** İşlem açıklamasındaki anahtar kelimelerden kategoriyi otomatik önerir ("Migros" → market); manuel etiketleme sürtünmesini azaltır ve tutarlılık sağlar.
- **Kaynak/İlham:** Lunch Money / Copilot auto-categorization rules.
- **Nasıl (mimari):** rules_engine deterministik keyword→kategori eşleme (kullanıcı kuralları öğrenilebilir); Transaction eklenirken öneri. Kullanıcı onaylar. LLM zorunlu değil.
- **Etki:** Orta · **Efor:** M
- **Uygulama:** `suggest_category()` (`app/routers/transactions.py`) — MERCHANT_KEYWORDS (marka: Migros/Opet/Netflix…) + mevcut QUICK_KEYWORDS; **kelime-sınırı token eşleşmesi** (substring değil → "sokak" yanlış pozitifi yok). `create_transaction` yalnız gider + kategori BOŞ ise açıklamadan türetir; kullanıcının açık seçimini asla ezmez. UI formunda kategori opsiyonel + ipucu metni. Test: `tests/test_auto_categorization.py` (9 test: marka/genel/none/case/kelime-sınırı + 3 endpoint entegrasyon).

### [FEAT-035] Fatura tutar anomali uyarısı
- **Değer/Fırsat:** Bir tekrarlayan faturanın (elektrik, doğalgaz) her zamankinden belirgin yüksek gelmesini işaretler ("elektrik geçen 3 ay ortalamasının %60 üstünde").
- **Kaynak/İlham:** Rocket Money bill anomaly; mevcut ANOMALY_THRESHOLD altyapısı.
- **Nasıl (mimari):** rules_engine mevcut rolling pattern/ANOMALY_THRESHOLD'ı tekrarlayan gider gruplarına uygular; detect_alerts. Salt görünürlük.
- **Etki:** Orta · **Efor:** S

### [FEAT-036] Hedefe otomatik allocation önerisi
- **Değer/Fırsat:** Ay sonunda harcanmayan artık nakit tespit edilince "bu 3.400 TL'yi acil fona/borca aktaralım mı?" diye önerir; birikimi otomatikleştirir.
- **Kaynak/İlham:** YNAB "roll with the punches" / otomatik sweep; Monarch goals.
- **Nasıl (mimari):** rules_engine artık nakit hesaplar → coach propose_action (GoalAllocation/transfer) → kullanıcı onayı → execute. Mimariyi tam izler.
- **Etki:** Yüksek · **Efor:** M

### [FEAT-037] Haftalık proaktif finansal digest
- **Değer/Fırsat:** Haftada bir kısa özet: bu hafta harcama, yaklaşan 3 olay, hedef ilerlemesi, tek eylem önerisi. Aylık rapordan farklı, sık ve kısa temas.
- **Kaynak/İlham:** Copilot weekly recap; Monarch digest.
- **Nasıl (mimari):** scheduler haftalık cron → rules_engine özet dict → coach açıklar (CoachInsight/mesaj). A3 aylık rapordan ayrı kadans.
- **Etki:** Orta · **Efor:** S

### [FEAT-038] Aylık ödeme optimizasyonu (nötr optimizer)
- **Değer/Fırsat:** Bu ay eldeki sınırlı ekstra parayla hangi kart/kredinin önce ödenmesinin toplam faizi en aza indireceğini hesaplar (avalanche uygulaması, tek ay). Nötr matematik, tavsiye değil hesap.
- **Kaynak/İlham:** Debt avalanche optimization; Undebt.it.
- **Nasıl (mimari):** debt_strategy tek-ay optimizasyonu + cashflow'daki uygun nakit; propose_action ile ödeme önerilir, onaylanır.
- **Etki:** Orta · **Efor:** M

### [FEAT-039] Fon fiyat tazelik proaktif hatırlatma
- **Değer/Fırsat:** Fon fiyatı 24 saatten eski kaldığında koç proaktif hatırlatır ("TLY fiyatı 2 gündür güncellenmedi, K/Z tahminin sapmış olabilir"). Manuel fiyat modelinin zayıf noktasını kapatır.
- **Kaynak/İlham:** fund_tracker mevcut tazelik kuralı + proaktif nudge.
- **Nasıl (mimari):** scheduler nightly fund_tracker tazelik kontrolü → bayat fon için CoachInsight/hatırlatma. Otomatik çekme başarısızsa manuel iste. Salt hatırlatma.
- **Etki:** Düşük · **Efor:** S

### [FEAT-040] Hedef fonlama önceliklendirme (kıt nakit dağıtımı)
- **Değer/Fırsat:** Birden fazla aktif hedef (acil fon, borç, tatil) varken ve nakit hepsine yetmezken, önceliğe göre bölüştürme önerir; hedef çakışmasını çözer.
- **Kaynak/İlham:** Goal prioritization / waterfall funding (YNAB, Qapital priorities).
- **Nasıl (mimari):** goal_engine'e priority alanı + rules_engine dağıtım hesabı → coach propose_action ile bölüştürme önerir → onay → execute. Deterministik hesap, LLM açıklar.
- **Etki:** Orta · **Efor:** M

### [FEAT-041] Deterministik "İLK ADIM" (next best action) ✅ UYGULANDI (12 Tem 2026)
- **Değer/Fırsat:** Tüm sinyalleri (alerts, alacak yaşlandırma, boşta nakit, kart borcu, kriz) TEK bir "şimdi yapılacak en yüksek etkili hamle"ye indirir. Sinyal-yığını yorgunluğunu çözer, "one clear action" verir.
- **Kaynak/İlham:** Copilot/Monarch "what to do next"; kurucu ilke "Rules Engine karar verir, LLM açıklar".
- **Nasıl (mimari):** `recommend_next_action(cockpit)` saf öncelik cascade'i: temerrüt (gecikmiş borç) > nakit krizi (→ en riskli alacağı tahsil / gideri ertele) > gecikmiş tahsilat > fırsat (boşta nakdi karta öde, faiz sızıntısını durdur) > stabil (limite sadık kal). Cockpit `sonraki_eylem` alanı + koç context "🎯 ÖNERİLEN İLK ADIM" bloğu (Kural 17: koç AÇIKLAR, türetmez) + Cockpit.jsx prominent kart. **Kritik:** öncelik LLM yargısına DEĞİL koda bağlı → sağlayıcı kalitesinden BAĞIMSIZ güvenilir #1 eylem (zayıf-provider gerçeğiyle uyumlu). 8 test.
- **Etki:** Yüksek · **Efor:** M
