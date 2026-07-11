# Rules Engine & finansal doğruluk (kod: RULE)

> EN KRİTİK BOYUT. Aşağıda RULE-001, RULE-002, RULE-003/004/005 gibi **canlı hatalar** var — gerçek para kararlarını etkiler. Rules Engine DB'ye yazmaz kuralı korunur.

### [RULE-001] `_matches` account_type kriteri hiçbir zaman eşleşmiyor (enum str bug) — CANLI HATA
- **Sorun:** `str(acc.account_type)` bir Python enum'ında `"AccountType.cash"` döner, criteria düz `"cash"` bekler → karşılaştırma HER ZAMAN False. Aynı dosyada `tx_type` için 102. satırda `.value` doğru kullanılmış ve yorumda tuzak uyarılmış; account_type dalı bu dersi uygulamamış.
- **Kanıt:** `app/goal_rules.py:130` (`if str(acc.account_type) not in allowed`)
- **Aksiyon:** `acc.account_type.value` kullan (satır 102 ile tutarlı).
- **Etki:** Yüksek · **Efor:** S
- **Not:** `account_type: "cash"` kriterli bir GoalRule hiçbir işlemi yakalamaz — kural sessizce ölü. `test_goal_rules.py` account_type criteria'sını test etmediği için kaçmış.

### [RULE-002] Kart asgari ödemesi başlangıç bakiyesine sabitleniyor (yanlış amortisman)
- **Sorun:** Kart min ödemesi `collect_debts`'te bir kez `balance * 0.25` hesaplanıp tüm simülasyon boyunca sabit tutuluyor. Gerçekte asgari ödeme her ay güncel bakiyenin %'sidir (azalır). Sabit tutmak kartı gerçekte olduğundan hızlı kapatır.
- **Kanıt:** `app/debt_strategy.py:104` + `_simulate` içinde min_pay yeniden hesaplanmıyor (`app/debt_strategy.py:171`)
- **Aksiyon:** Kart için her ay `min_pay = max(state[aid] * MIN_CARD_PAYMENT_RATIO, floor)` yeniden hesapla; `DebtItem.min_payment`'ı kart tipinde "oran" olarak sakla.
- **Etki:** Yüksek · **Efor:** M
- **Not:** Snowball/avalanche ay sayısı gerçekten olduğundan kısa çıkar.

### [RULE-003] `evaluate_credit_card_strategy` — `days_to_statement` modulo yanlış ay uzunluğuyla
- **Sorun:** `(statement_day_eff - today.day) % last_day` — `last_day` cari ay uzunluğu; kesim geçmişse bir sonraki ay uzunluğuna göre hesaplanmalı. Şubat (28) → Mart taşarken off-by.
- **Kanıt:** `app/rules_engine.py:184-185`
- **Aksiyon:** `get_next_occurrence`/`_get_next_due_date` mantığı (gerçek tarih farkı `(next_date - today).days`) kullan; modulo aritmetiğini bırak.
- **Etki:** Orta · **Efor:** M

### [RULE-004] Kart stratejisi `today.day > statement_day` — `statement_day_eff` yerine ham değer
- **Sorun:** Dal seçiminde 191. satır ham `statement_day` kullanıyor; üstte `statement_day_eff = min(statement_day, last_day)` hesaplanmış. Kesim 31, ay 30 → `eff=30` ama karşılaştırma 31'e bakar → 30. günde asla "vade_avantaji"na geçmez.
- **Kanıt:** `app/rules_engine.py:191` vs `:181`
- **Aksiyon:** `if today.day > statement_day_eff:`
- **Etki:** Orta · **Efor:** S

### [RULE-005] Kart stratejisi `today.day > 1` koşulu ayın 1'ini yanlış dala atıyor
- **Sorun:** `elif today.day <= payment_day and today.day > 1:` — ayın 1'inde ödeme günü gelmemiş olsa bile "odeme_dikkat" yerine else (kesim_dikkat) dalına düşer.
- **Kanıt:** `app/rules_engine.py:198`
- **Aksiyon:** `today.day > 1` şartını kaldır ya da gerçek tarih karşılaştırması.
- **Etki:** Düşük · **Efor:** S

### [RULE-006] Para hesaplarında `float` + `round()` banker's rounding sürüklenmesi
- **Sorun:** Tüm tutarlar `Column(Float)`. `round()` Python'da ROUND_HALF_EVEN (banker's); 2.675 ikili kayan noktada tam temsil edilemez. Topla-sonra-yuvarla zincirlerinde kuruş sürüklenmesi birikir.
- **Kanıt:** `app/rules_engine.py:128, 718, 723`; toplama `nakit += acc.balance` (`:665`) sonra tek round.
- **Aksiyon:** Para için `Decimal` + `quantize(Decimal("0.01"), ROUND_HALF_UP)`; en azından tek `money(x)` yardımcısı.
- **Etki:** Orta · **Efor:** L
- **Not:** `round(2.675,2)` → 2.67 (beklenen 2.68). [Real Python — Rounding]

### [RULE-007] "FIFO lot" aslında yok — tek `cost_per_lot` = ağırlıklı ortalama
- **Sorun:** `simulate_partial_sale` ve model tek `cost_per_lot` tutar; farklı fiyatlı lotlar tek ortalamaya çökertilir. FIFO değil weighted-average. K/Z ve stopaj matrahı FIFO'dan farklı.
- **Kanıt:** `app/rules_engine.py:257-298`; `app/models.py:171` `cost_per_lot = Column(Float)`
- **Aksiyon:** Gerçek lot bazlı maliyet gerekiyorsa "lot ledger" tablosu; aksi halde "ağırlıklı ortalama maliyet" olarak netleştir, yanıltıcı "FIFO" iddiasını kaldır.
- **Etki:** Orta · **Efor:** L
- **Not:** 4 lot @3.616 + 2 lot @5.000 alıp 4 lot satınca stopaj farkı yüzlerce TL. [Vanguard — FIFO Cost Basis]

### [RULE-008] `simulate_partial_sale` giriş doğrulaması eksik (negatif/sıfır lot) ✅ UYGULANDI
- **Sorun:** `lots_to_sell > lot_count` kontrol var ama `lots_to_sell <= 0`, negatif fiyat, `cost_per_lot<0` yok.
- **Kanıt:** `app/rules_engine.py:272-273`
- **Aksiyon:** `if lots_to_sell <= 0 or current_price < 0: raise ValueError`
- **Etki:** Düşük · **Efor:** S

### [RULE-009] Kart kullanım/status oranında `max(nakit, 1)` tabanı çarpıtıyor ✅ UYGULANDI
- **Sorun:** `kart_borcu / max(nakit, 1)`; nakit 0–1 TL veya negatifse oran yanlış (0.5 TL nakit → payda 1; negatif nakit → negatif oran).
- **Kanıt:** `app/rules_engine.py:744` ve `:851`
- **Aksiyon:** `if nakit <= 0` özel dalı; oranı None/"sonsuz baskı" işaretle.
- **Etki:** Düşük · **Efor:** S

### [RULE-010] `debt_strategy` payoff tarihi 30 günlük ay yaklaşımı ✅ UYGULANDI
- **Sorun:** `payoff = date.today() + timedelta(days=month * 30)` — 12 ay=360 gün ≠ 365. Uzun vadede haftalar kayar; `date.today()` fonksiyonu saf olmaktan çıkarır (test edilemez).
- **Kanıt:** `app/debt_strategy.py:216`
- **Aksiyon:** Gerçek takvim ay ilerlemesi (`_advance_month`); `today` parametresini enjekte et.
- **Etki:** Orta · **Efor:** M

### [RULE-011] `months_to_freedom == MAX_MONTHS` "özgürlük" gibi dönüyor (asla bitmez maskeleniyor) ✅ UYGULANDI
- **Sorun:** Faiz > ödeme olunca borç hiç bitmez ama `months_to_freedom` 600 döner ve payoff_date hesaplanır → çağıran "50 yılda biter" sanar.
- **Kanıt:** `app/debt_strategy.py:150, 216-227`; `goal_engine.py:107` kısmen koruyor.
- **Aksiyon:** `never_pays_off: bool` bayrağı; MAX_MONTHS'ta `payoff_date=None`.
- **Etki:** Orta · **Efor:** S

### [RULE-012] `_simulate` 0.01 TL eşiğiyle borç "kapandı" — toplam korunumu bozuk
- **Sorun:** `b > 0.01` / `state[aid] <= 0.01` eşiği borçları 1 kuruşa kadar "ödenmiş" sayar ama `total_paid`'e eklemez. Invariant `total_paid ≈ Σbalance + total_interest` bozulur.
- **Kanıt:** `app/debt_strategy.py:150, 169, 177, 189`
- **Aksiyon:** Kapanışta kalan artığı son ödemeye ekle veya eşiği kaldır; korunum invariant testi.
- **Etki:** Düşük · **Efor:** M

### [RULE-013] `_compute_debt_freedom` yeni borç eklenince ilerlemeyi gizliyor
- **Sorun:** `paid_off = max(baseline - current_debt, 0)`. Yarısını ödeyip yeni kredi çekilirse `current_debt > baseline` → paid_off 0'a kırpılır → ödediği halde %0 görür.
- **Kanıt:** `app/goal_engine.py:86-88`
- **Aksiyon:** Baseline'ı goal yaratımındaki hesap kümesine (account_id listesi) sabitle, sonraki borçları hariç tut.
- **Etki:** Orta · **Efor:** M

### [RULE-014] Float→Decimal `str()` köprüsü kirli ondalık üretebilir
- **Sorun:** `Decimal(str(total))` — total SQL'den gelen Float toplamı; `str(63462.51999999999)` artefaktı Decimal'e taşınır, quantize edilmezse baseline'a çirkin değer yazılır.
- **Kanıt:** `app/goal_engine.py:44, 84, 124, 156`
- **Aksiyon:** `Decimal(str(total)).quantize(Decimal("0.01"))`; kaynağı Numeric'e taşımayı değerlendir.
- **Etki:** Orta · **Efor:** S

### [RULE-015] `_project_cash_completion` `int()` ile gün sayısını aşağı yuvarlıyor
- **Sorun:** `days_needed = int(remaining / daily_rate)` truncation → tamamlanma hep erken; `daily_rate` 90 güne bölerek hızı düşük tahmin eder.
- **Kanıt:** `app/goal_engine.py:161-163`
- **Aksiyon:** `math.ceil`; hız için gerçek katkı-günü sayısı veya EWMA.
- **Etki:** Düşük · **Efor:** S

### [RULE-016] `_expand_loan_payments` geçmiş `next_payment_date`'te taksit sayacını boşa harcıyor
- **Sorun:** Döngü `idx < remaining` sınırlı; geçmiş occurrence'lar atlanırken `idx` yine artar → horizon içindeki gelecek taksitler eksik üretilebilir.
- **Kanıt:** `app/cashflow.py:157-170`
- **Aksiyon:** Kürsörü `max(next_payment_date, ilgili ay)`'a kaydır ya da geçmişte `idx` artırma.
- **Etki:** Orta · **Efor:** M

### [RULE-017] Ay sonu gününden taşarken gün sürüklenmesi (clamp sonrası orijinal gün kaybı)
- **Sorun:** Bir sonraki ay `min(cursor.day, last)` ile üretilir ama cursor zaten kırpılmış olabilir; 31 → Şubat 28 → Mart 28 (31 değil). Orijinal `day_of_month` korunmuyor.
- **Kanıt:** `app/cashflow.py:132-137`; `app/simulation_engine.py:326-331`
- **Aksiyon:** Orijinal `day_of_month`'ı taşı, her ay `min(day_of_month, last)` (cashflow `_month_occurrences` bunu doğru yapıyor — pattern'i taşı).
- **Etki:** Orta · **Efor:** M

### [RULE-018] Simülasyon kredi taksitini %100 anapara sayıyor (faiz yok)
- **Sorun:** `a.balance = max(0.0, a.balance - a.monthly_payment)` — taksitin faiz kısmı düşülmüyor, tamamı bakiyeden iniyor. Kalan borç gerçekte daha yavaş azalır; net değer iyimser.
- **Kanıt:** `app/simulation_engine.py:375`
- **Aksiyon:** `interest = balance*(rate/100); balance += interest - payment`.
- **Etki:** Orta · **Efor:** M

### [RULE-019] Simülasyon kartı hiç ödemiyor → net değer projeksiyonu tutarsız
- **Sorun:** Kredi taksitleri nakitten düşülür ama kart borcu/faizi sabit bırakılır — asimetrik.
- **Kanıt:** `app/simulation_engine.py:403-408`
- **Aksiyon:** Kart son ödemesini upcoming_payment olarak modelle veya net_worth deltasında kart faizini işle; asimetriyi belgele.
- **Etki:** Orta · **Efor:** M

### [RULE-020] `_calculate_category_patterns` cari pencerede üst sınır yok → gelecek işlemler sızar
- **Sorun:** `curr_30d` koşulu `transaction_date >= :curr_start` (üst sınır yok). Gelecek tarihli işlem curr penceresine girer → asimetrik pencere, çarpık anomali.
- **Kanıt:** `app/rules_engine.py:581-584`
- **Aksiyon:** `AND transaction_date <= :today`; iki pencereyi tam 30 güne kenetle.
- **Etki:** Orta · **Efor:** S

### [RULE-021] `evaluate_credit_card_strategy` için test YOK
- **Sorun:** Fonksiyon hiçbir testte çağrılmıyor; RULE-003/004/005 dahil kart döngüsü test edilmemiş.
- **Kanıt:** Grep: sadece `app/rules_engine.py`.
- **Aksiyon:** Kesim öncesi/sonrası, ödeme günü, ay sonu clamp (31→30/28), ayın 1'i için birim testleri.
- **Etki:** Yüksek · **Efor:** M

### [RULE-022] `detect_alerts` için test YOK
- **Sorun:** Kritik/uyarı eşikleri (kart %95/%80, negatif reel bütçe, nakit<1000, 7 gün büyük ödeme) test edilmiyor; sınır off-by (>=95 vs >95) doğrulanmamış.
- **Kanıt:** Grep: sadece `rules_engine.py`.
- **Aksiyon:** Her uyarı sınıfı + sınır (tam %95.0, kart_limit=0, nakit=1000.0) testleri.
- **Etki:** Orta · **Efor:** M

### [RULE-023] ZikZak additive carried_forward — ÇÖZÜLDÜ (ADR-026)
- **Durum:** ✅ Karar + kod düzeltmesi (6 Tem 2026). İlk teşhisim ("özellik ölü, aç") ve sonraki "P0 zikzak" iddiam **oversimplify idi** — self-control + simülasyon + araştırmayla düzeltildi.
- **Bulgu (teyitli):** `today_target = daily_limit + carried_forward` additive modeli ÇİFT-SAYIM üretir. Simülasyon: 3 nöbet günü sonrası naif today_target=1474.96 iken sürdürülebilir günlük 394.10 (Sanal Zenginlik tuzağı — kök vizyonda yasak). Dinamik `daily_limit = reel_butce/days_remaining` önceki tasarrufu ZATEN içerir → zikzak etkisi çift-saymadan mevcut. YNAB: pozitif devreder, negatif devretmez (mevcut fn negatifi de devrediyordu).
- **Yapıldı:** `carried_forward=0.0` bilinçli + `today_target=daily_limit`; yanıltıcı yorum ADR-026 atfıyla düzeltildi; additive fonksiyonlar DEPRECATED.
- **Kanıt:** `app/rules_engine.py:729-732`; `docs/architecture/adr-026-zikzak-karari.md`
- **Sonraki adım (ayrı):** "Harcama günü lump" hissi için tek-havuzlu, çift-saymayan "harcama günü tavanı" tasarla + numeric test + frontend/coach.
- **Etki:** Yüksek (vizyon-kritik doğruluk) · **Efor:** Karar S (yapıldı) / tavan-özelliği M

### [RULE-024] `calculate_investment_pnl` ve `_calculate_category_patterns` testsiz
- **Sorun:** K/Z (maliyet=0 dalı), yeni-kategori anomali, division-by-zero yolları test edilmiyor.
- **Kanıt:** Grep: sadece `rules_engine.py`.
- **Aksiyon:** `toplam_maliyet=0`, negatif K/Z, `prev_30d=0` (yeni kategori) testleri.
- **Etki:** Orta · **Efor:** M
- **Not:** Yeni kategori `anomaly_flag = curr_30d > 0` → tek 1 TL harcama "anomali" işaretler.

### [RULE-025] Avalanche/Snowball sıralamasında ikincil tie-break yok → keyfi öncelik
- **Sorun:** Avalanche `key=-interest_rate`, Snowball `key=balance`; eşit faiz/bakiyede ikincil anahtar yok → sıralama DB insertion sırasına bağlı.
- **Kanıt:** `app/debt_strategy.py:236, 244`
- **Aksiyon:** Avalanche'a ikincil `balance`, Snowball'a ikincil `-interest_rate`.
- **Etki:** Düşük · **Efor:** S

### [RULE-026] Reel bütçe ile beklenen gelir arasında tutarsızlık (alacaklar)
- **Sorun:** `expected_income` alacakları içerir (display), `reel_butce` yalnızca `recurring_income` kullanır; yan yana durunca kullanıcı elle doğrulayamaz.
- **Kanıt:** `app/rules_engine.py:707, 714`
- **Aksiyon:** `reel_butce_bileşenleri` alanı ekle veya beklenen_gelir'i (düzenli/alacak) ikiye ayır.
- **Etki:** Düşük · **Efor:** S

### [RULE-027] `apply_shadow_accounting` negatif/aşırı büyük değerlerde koruma yok
- **Sorun:** Saf aritmetik; `loan_payments_this_month` negatif verilirse reel bütçe şişer.
- **Kanıt:** `app/rules_engine.py:114-128`
- **Aksiyon:** Girdi işaret doğrulaması (`card_debt>=0`, `loan_payments>=0`) veya invariant assertion.
- **Etki:** Düşük · **Efor:** S

### [RULE-028] `calculate_daily_limit` negatif bütçeyi güne bölüyor (anlamsız negatif limit)
- **Sorun:** `reel_butce` negatifse negatif günlük limit döner; "bugünkü hedef" negatif gösterilir.
- **Kanıt:** `app/rules_engine.py:131-135`
- **Aksiyon:** `if reel_butce < 0: return 0.0` + ayrı "açık" metriği.
- **Etki:** Düşük · **Efor:** S

### [RULE-029] `date.today()` (lokal) ile naive-UTC DB alanları karışımı — gün kayması
- **Sorun:** cashflow/debt_strategy/goal `date.today()` (UTC+3) kullanır; `goal_engine._project_cash_completion` cutoff'u `datetime.utcnow()` ile kurup sonucu `date.today()` ile üretir → gece yarısı ±3 saat off-by-one.
- **Kanıt:** `app/goal_engine.py:147, 168`; `app/cashflow.py:257`; `app/debt_strategy.py:216`
- **Aksiyon:** Tek "bugün" kaynağı (enjekte edilen `today: date`); utcnow karşılaştırmalarını lokal tarih tabanına hizala.
- **Etki:** Orta · **Efor:** M

### [RULE-030] Forecast `closing_balance` yalnızca nakit — "kriz" tespiti borç/kartı yok sayıyor
- **Sorun:** `opening_balance` yalnız cash; crunch sadece nakit üzerinden. Kart %99.8 doluyken nakit pozitifse "kriz yok" der.
- **Kanıt:** `app/cashflow.py:261-267, 333`
- **Aksiyon:** Kapsamı UI'da netleştir; "kullanılabilir likidite = nakit + kalan kart limiti" metriği.
- **Etki:** Orta · **Efor:** M

### [RULE-031] `_simulate` — toplam korunum invariant testi yok (property-based fırsatı)
- **Sorun:** `total_paid`, `total_interest`, başlangıç bakiyeleri arasında invariant assert edilmiyor; RULE-012/RULE-002 böyle yakalanırdı.
- **Kanıt:** `tests/test_debt_strategy.py` yalnız sıralama/ay sayısı kontrol ediyor.
- **Aksiyon:** Hypothesis ile rastgele borç kümeleri; `total_paid ≈ Σbalance + total_interest` (±0.01×adet) invariant'ı.
- **Etki:** Orta · **Efor:** M

### [RULE-032] `_project_debt_freedom` extra_monthly=0 ile projeksiyon → aşırı kötümser
- **Sorun:** Goal projeksiyonu her zaman `extra_monthly=0.0`; kullanıcı fazladan ödese bile tahmin sadece minimumlarla.
- **Kanıt:** `app/goal_engine.py:105`
- **Aksiyon:** Son N ayın gerçek azalış hızından ya da allocation hızından extra türet.
- **Etki:** Düşük · **Efor:** M

### [RULE-033] Percent/fixed allocation banker's rounding ile hedef sapması
- **Sorun:** `(tx_amount * pct).quantize(Decimal("0.01"))` varsayılan ROUND_HALF_EVEN; çok sayıda yüzdesel allocation birikince hedefe tam oturmaz.
- **Kanıt:** `app/goal_rules.py:156`; `app/goal_engine.py:88, 135`
- **Aksiyon:** Para/oran quantize'larında açık `rounding=ROUND_HALF_UP`; tüm modüllerde tek konvansiyon.
- **Etki:** Düşük · **Efor:** S
- **Not:** %33.333×1000=333.33 (banker's), tekrarlı katkıda 999.99 → "achieved" tetiklenmez.

### [RULE-034] `_compute_cash_target` progress'i kırpıyor ama `current_amount` kırpmıyor — tutarsız gösterim
- **Sorun:** progress 0-100 kırpılı, current_amount ham; aşırı fonlanmış hedefte progress %100 ama current > target.
- **Kanıt:** `app/goal_engine.py:120-137`
- **Aksiyon:** `over_funded` bayrağı veya current'ı hedefte sınırlayıp fazlayı ayrı alanda göster.
- **Etki:** Düşük · **Efor:** S

### [RULE-035] Cockpit float toplamları — yatırım değerinde çift yuvarlama uyumsuzluğu
- **Sorun:** `display_balance = round(lot*price,2)` (653) ama net_deger için `yatirim_deger += lot*price` (yuvarlanmamış, 680). Gösterilen bakiye ile net değere giren değer farklı yuvarlama.
- **Kanıt:** `app/rules_engine.py:653 vs 680, 718`
- **Aksiyon:** Tek kaynak: `value = round(lot*price,2)`, hem display hem toplam kullansın.
- **Etki:** Düşük · **Efor:** S
- **Not:** BUG #007 benzer 4 kuruş sorununu zaten belgelemiş.

### [RULE-036] `_calculate_expected_income_until_eom` gün-of-month karşılaştırması tam tarih değil
- **Sorun:** `if target_day >= today.day` — sadece gün numarası; clamp edilmiş target_day bugüne eşit/büyükse dahil edilir, "bu ay geldi mi" tam tarih gerektirir.
- **Kanıt:** `app/rules_engine.py:324-325`
- **Aksiyon:** `_get_next_due_date` deseniyle tam `date` karşılaştırması.
- **Etki:** Düşük · **Efor:** S

### [RULE-037] `total_payable`/`total_receivable` sıfır tutarlı olayları yutar; net_flow işaret varsayımı
- **Sorun:** `sum(... if ev.amount > 0)` ve `< 0` — tutarı tam 0 olan olay hiçbir toplama girmez.
- **Kanıt:** `app/cashflow.py:343-344`
- **Aksiyon:** 0-tutarlı olayları veri girişinde engelle ya da toplamlarda ayrı ele al.
- **Etki:** Düşük · **Efor:** S

### [RULE-038] `compare_strategies` özet notu — `months_difference` işareti karışabilir + magic number
- **Sorun:** `saved`/`months_diff` yuvarlanmış toplamlardan; `abs(saved) < 50` magic; not metninde `abs(months_diff)` işaret bilgisini kaybeder (avalanche yavaşsa yanlış "daha hızlı biter").
- **Kanıt:** `app/debt_strategy.py:278-292`
- **Aksiyon:** İşareti metne doğru yansıt; 50 TL eşiğini adlandırılmış sabite çıkar.
- **Etki:** Düşük · **Efor:** S

### [RULE-039] `simulate_partial_sale` kalan lot 4 hane, değer 2 hane — karışık hassasiyet
- **Sorun:** `kalan_lot = round(...,4)`, diğerleri 2 hane; hassasiyet konvansiyonu belgesiz ve modüller arası tutarsız.
- **Kanıt:** `app/rules_engine.py:284-285`
- **Aksiyon:** Lot hassasiyetini tek yerde tanımla; TEFAS pay adedi konvansiyonuyla hizala.
- **Etki:** Düşük · **Efor:** S

### [RULE-040] Modüller arası para tipi tutarsızlığı: Account=Float, Goal=Numeric — köprüde hassasiyet kaybı
- **Sorun:** Account Float, Goal/GoalAllocation/GoalRule Numeric/Decimal; goal motoru Float'ı `Decimal(str())` ile alır (RULE-014); debt_strategy Decimal hiç kullanmaz. Tek para tipi disiplini yok.
- **Kanıt:** `app/models.py:154,193,256` (Float) vs `:764,774,813` (Numeric); köprü `goal_engine.py:44`
- **Aksiyon:** Uzun vadede tüm para alanlarını `Numeric(14,2)`'ye taşı; kısa vadede tek `Money` yardımcı tipi/round konvansiyonu + invariant testleri.
- **Etki:** Yüksek · **Efor:** L
- **Not:** Float drift (RULE-006) + banker's (RULE-033) + köprü kirliliği (RULE-014) birleşince net_deger/progress/baseline arasında izlenemez kuruş farkları; `==` yerine epsilon gerekir (debt_strategy 0.01 epsilon zaten kullanıyor — tip disiplini yokluğunun kanıtı).

---
**Kaynaklar:** Real Python — Rounding; Fidelity/Ramsey — Avalanche/Snowball; Vanguard/Fidelity — FIFO cost basis; Wikipedia/LibreTexts — Amortization schedule.
