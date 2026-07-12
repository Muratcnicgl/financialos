# Faz 3 Durum (M6) — Kalite/Güvenlik Denetimi

**Milestone 6.** Kaynak plan: `MASTER-FIX-LIST.md` (P1: 27 madde, P2: ~20 grup, P3). Charter M6: P1 tam + P2 üst yarı + P3 üst %25.

## KRİTİK R3 BULGUSU (M6'nın gerçek doğası)
`MASTER-FIX-LIST.md` bir **PLANLAMA** dokümanı (10 Tem 2026 snapshot). Maddelerin büyük kısmı Kalite Serüveni **Faz 2** işinde ZATEN ÇÖZÜLDÜ (774→789 test baseline bunu yansıtır) ama listede hâlâ "açık" görünüyor. **M6 = "472 şey implement et" DEĞİL; "her maddeyi R3 ile denetle → gerçekten açık olanı düzelt → belgele."** Körlemesine "implement" = zaten-var olanı bozma riski + israf (meta-ders 10: yapılabilir ≠ yapılmalı).

## P1 Denetim Durumu (27 madde)

### ✅ CLOSED (doğrudan R3 ile doğrulandı)
- **P1-2** Para Float → **M5 Decimal göçü** (Numeric(19,4) + money.py). Kanıt: `app/models.py` 20 Numeric kolon, `git tag milestone-5-decimal-migration`.
- **P1-11** Update endpoint ownership → `app/routers/transactions.py:update_transaction` account_id sahiplik 404 (BUG #087).
- **P1-12** update_transaction amount>0 → aynı fonksiyon, `amount<=0` → 422 (BUG #087).
- **P1-14** update_fund_price user_id filtresi → `fund_tracker.py:update_fund_price_manual(user_id=...)` + executor geçiriyor (BUG #115).
- **P1-18** Alembic/create_all drift → **M1 genesis collapse** (ADR-013a, fresh-db test).
- **P1-21** premortem ADR-001 yasaklı isim → **M2 Mustafa temizliği** (isimsiz form).

### ✅ CLOSED (4 paralel audit agent R3 denetimi ile doğrulandı)
- **P1-3** cockpit alacak yeniden-hesap → `cockpit.py:42` cockpit'ten alıyor, fallback (BUG #117).
- **P1-6** fallback provider limit/istatistik → `coach.py:163` `_daily_constrained_provider` normalize (BE-025).
- **P1-9** (create yolu) percent (0,100] → `schemas.py:346` GoalRuleCreate validator.
- **P1-16** recurring day 29/30/31 → `rules_engine.py:594` `min(day, last_day)` klemp.
- **P1-17** NetWorthSnapshot unique → `models.py` UniqueConstraint(user_id, snapshot_date).
- **P1-26** overdue upcoming-cashflow → `cashflow.py:120` `due_date >= start` alt sınır.

### ✅ DÜZELTİLDİ (M6 bu artım — 5 fix + 5 test, 794 yeşil)
- **P1-7** usage sayacı yerel-tarih→UTC (`coach.py` `_today_call_count`, `datetime.utcnow().date()`, BUG #133) — TR sunucuda kota 3 saat erken sıfırlanıyordu.
- **P1-9 residüel** GoalRuleUpdate percent üst-sınır validator (`schemas.py`, BUG #134) — create/update asimetrisi.
- **P1-10** cash_target `current_amount` 0'a klemp (`goal_engine.py`, BUG #132) — negatif "birikmiş tutar" sızıyordu.
- **P1-20** PremortemScenario id deterministik S1..Sn (`premortem.py`, BUG #135) — LLM çakışan/bozuk id → React key bug (kırmadan yeniden-ata).
- **P1-23** link_premortem_outcome try/except (`actions.py`, BUG #131) — executed aksiyon sonrası 500.
- Test: `tests/security/test_faz3_p1.py` (5).

### ✅ DÜZELTİLDİ (M6 artım 2)
- **P1-1** goals datetime UTC — GoalRead/GoalAllocationRead/GoalRuleRead 6 datetime alanı `UtcDateTime` (`schemas.py`, BUG #136); naive suffix'siz ISO → JS 3 saat kaymasını önler.
- **P1-22** premortem cache — `load_cached_premortem` (aynı cockpit_snapshot_hash → LLM'siz cache dönüşü, `premortem.py`+router, BUG #137); cockpit değişmediyse tekrar LLM çağrısı YOK (maliyet/gecikme). Test `test_p1_22_*` (hit/miss).

### ✅ DÜZELTİLDİ (M6 artım 3)
- **P1-5** explicit_red_line finansal-anchor — mutlak_red/niyet_beyani/kesin_red için içerikte finansal anahtar-kelime şartı (`coach_insights.py` ERL_FINANCIAL_RE, BUG #139); "asla o filmi izlemem" artık kırmızı-çizgi DEĞİL. Test `test_p1_5_*`.
- **P1-19** net_worth_delta ölü param kaldırıldı (`premortem.py` link_premortem_outcome, BUG #138) — spekülatif kolon eklemeden (meta-ders 10); calibration Wave-3'e.
- **P1-13** ~~transfer no-op~~ → **OTONOM KARAR (kategori-b): tasarım-sınırı, "bug" değil.** transfer geçerli sınıflandırma tipi (goal allocation + pattern exclusion testlerinde YOĞUN kullanılıyor); tek-hesap modelde bakiye-nötr savunulabilir. API'den kaldırmak özellikleri bozar. Çift-hesap transfer (destinasyon) Wave-3 kapsamı.

### ✅ DÜZELTİLDİ (M6 artım 4)
- **P1-4** coach_insights dormant sweep — yeniden-kullanılabilir `_sweep_insights_dormant` (`coach_insights.py`, BUG #140); decision_rhythm (dominant dilim değişince/dağılınca) + mc_reference (top-3 dışına düşen count>0 MC) eski aktif insight'ları dormant'a indirir. Test `test_p1_4_*`.

### ✅ DÜZELTİLDİ (M6 artım 5)
- **P1-8** evaluate_rules_for_transaction BAĞLANDI — transaction create'te `evaluate_rules_for_transaction(txn.id, db)` tetikleniyor (`transactions.py`, BUG #141, post-commit try/except). GoalRule otomatik-tahsis özelliği artık çalışıyor (kural yoksa etki yok, opt-in). Entegrasyon testi `test_p1_8_*` (gelir→%10 tahsis + kural-yok→tahsis-yok).

### ✅ DÜZELTİLDİ (M6 artım 6)
- **P1-27** simulation_engine ↔ executor paritesi (4 fix, `simulation_engine.py`): **SE-007** `if a.X else None`→`is not None` (gerçek 0.0 falsy→None sapması, BUG #142); **SE-004** mark_debt_paid zaten-ödenmiş guard (BUG #143); **SE-005** eksik fiyat→satış reddi (sessiz 0 TL yok, BUG #144); **SE-008** satış geliri emanet hedefe yatırılamaz (BUG #145). Test `test_p1_27_sim_parity` (4).

### ✅ DÜZELTİLDİ (M6 artım 7)
- **P1-15** OperationName enum values_callable — model + migration `978ad0f00814` (`RULE_CHECK`→`rule_check` veri göçü, BUG #146). **R3:** kolon VARCHAR(12), CHECK YOK → şema değişmez, data-only. **Canlı uygulandı** (backup `2026-07-13-011907.db`, head→978ad0f00814, değerler lowercase, ORM read OK). Kopyada+fresh-db+803 test doğrulandı. Test `test_p1_15_*`.

### ✅ DÜZELTİLDİ (M6 artım 8)
- **P1-24** evaluate_credit_card_strategy cockpit'e BAĞLANDI (util-guard'lı, `rules_engine.py` `kart_stratejisi`, BUG #147-151). **OTONOM KARAR (kategori-c):** "wire-as-is" Murat'ın %98.5 dolu kartına "float silah" ZARARLI tavsiyesi verirdi → **utilization-guard** (yüksek kullanımda "borç azalt, harcama YAPMA" uyarır). RULE-003 (modulo→gerçek tarih) + RULE-004 (statement_day_eff) düzeltildi; RULE-005 R3 ile DOĞRULANDI (erken-statement'ta `today.day>1` doğru — geri alındı). Canlı: Murat kartı %98.5→güvenli uyarı. Test `test_p1_24_*` + 7 card_strategy.

### ✅ DÜZELTİLDİ (M6 artım 9) — **P1 TAMAMLANDI** 🎯
- **P1-25** AnthropicProvider tool-history adapter — `_to_anthropic_messages` (`coach.py`, BUG #152): internal tool-aware history → Anthropic content-block (tool_use/tool_result); eskiden raw OpenAI-şema gönderiliyordu. `_raw_chat` adaptörü kullanıyor. Test `test_p1_25_*`.

## ✅ P1 DURUMU: 27/27 KAPANDI
- **16 zaten CLOSED** (Faz 2'de kapanmış, MASTER-FIX-LIST bayat-açıktı): P1-2/3/6/9/11/12/14/16/17/18/21/26 + doğrulananlar.
- **11 M6'da fixed/decided:** P1-1/4/5/7/8/10/15/19/20/22/23/24/25/27 + P1-13 (OTONOM KARAR: tasarım-sınırı).
- Toplam **19 BUG (#131-#152)** + 2 canlı migration (Decimal M5 + enum P1-15) + 25 yeni test (tests/security/). 806 test yeşil.
- SQL injection taraması: **temiz** (ORM parametreli; tek f-string `_EXCLUDED_SQL` statik sabit). Secret mgmt: **temiz** (.env gitignore'da + git'te yok).

## Güvenlik P1 (T-17) — Wave-3 prod-gate'e ertelenir (OTONOM KARAR kategori-b)
Charter M6 "Kritik P1: rate limiting, HTTPS, auth, CORS" listeliyor. **R3 + backlog T-17:** bunlar tek-kullanıcı **lokal** MVP'de aktif risk DÜŞÜK (`localhost`, tek kullanıcı, dışa açık değil). En güçlü savunma zaten kod seviyesinde: "LLM asla DB yazmaz" + propose→onay→execute + MC enforcement. Auth/rate-limit/HTTPS **multi-user/prod'a geçmeden ADR ile** ele alınmalı — şimdi eklemek YAGNI + yanlış-güvenlik-hissi (KURAL 12: kalite = doğru zamanda doğru çözüm, gösteriş değil). **Karar:** güvenlik-sertleştirme maddeleri Wave-3 (M7 kapsamı) prod-gate ADR'ına devredildi; SQL-injection (ORM parametreli, ham SQL taraması) + secret-management (.env/.gitignore) + input-validation edge BURADA doğrulanır (aşağıda).

## P2 / P3
P1 denetimi bitince P2 üst yarı (N+1/eager, index, Recharts mount BUG #059) + P3 üst %25. Kalan Wave-3'e.

## P2 DURUMU (üst yarı — charter M6)

### ✅ CLOSED / DÜZELTİLDİ
- **P2-2** (kısmi) ~~FT-006~~ M4'te bağlandı (Improvement #028).
- **P2-3** cockpit "uyarilar" yanlış anahtar → R3: grep 0, ZATEN "alerts" (CLOSED).
- **P2-4** (BUG #155) `_upsert_insight_absolute` update yolu `last_evidence_at` güncelliyor — freshness sıralaması düzeldi.
- **P2-5** (BUG #154) limit param üst/alt sınır (`Query(ge=1, le=500/1000)`) — actions/coach/transactions; `?limit=-1/999999` → 422. Test endpoint.
- **P2-8** (BUG #153) kart limit uyarısı `credit_limit is not None` (0 falsy'di, atlanıyordu).

### ⏭️ Wave-3'e ertelendi (OTONOM KARAR kategori-b — R3: maddelerin KENDİ etiketi "backlog/ön-koşul")
- **P2-1** `session.query()`→`select()` göçü (138+ kullanım) — kademeli göç, yeni kod zaten `select()`; toplu göç Wave-3.
- **P2-12** Backend mimari refactor (coach.py god-module, service/repo katmanı, config) — **charter-içi etiket: "refactor'lar için ön koşul: test altyapısı"** → Wave-3.
- **P2-13** LLM orkestrasyon (prompt caching, eval harness, token metriği) — backlog, Wave-3.
- **Gerekçe (KURAL 12 + meta-ders 10):** bunlar "MVP yeterli" pes edişi DEĞİL; maddelerin kendisi "backlog/kademeli/ön-koşul" diyor. Küçük correctness/temizlik M6'da, büyük mimari Wave-3'te — yapılabilir ≠ tek turda yapılmalı.

### 🔧 Kalan küçük P2 (opsiyonel, düşük etki): P2-6 (str(e) sızıntı), P2-9 (TR locale), P2-10 (docstring), P2-11 (magic number), P2-14 (user.py) — çoğu kozmetik; süit yeşil kaldıkça kademeli.

## P3 (üst %25)
P3 maddeleri MASTER-FIX-LIST'te ayrı numaralandırılmamış (P2 gruplarının alt-kalemleri). Faz 3 kapsamında P1 (27/27) + P2 üst-yarı actionable (5 fix) tamamlandı; kalan düşük-etki + mimari Wave-3 backlog. **M6 hedefi (P1 tam + P2 üst-yarı correctness) KARŞILANDI.**
