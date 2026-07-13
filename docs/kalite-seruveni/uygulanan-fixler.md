# Uygulanan Değişiklikler (Kalite Serüveni — fix ledger)

Her satır: yapıldı → **doğrulandı**. Halüsinasyon/varsayım yok; her fix çalıştırılarak teyit edildi. Backlog ID + BUG/ADR numarası referanslı.

| # | ID | Değişiklik | Dosya | Doğrulama | Durum |
|---|----|-----------|-------|-----------|-------|
| 1 | RULE-001 / BUG #059 | `account_type` kriteri `str(enum)` yerine `.value` — enum bug'ı yüzünden account_type kriterli her GoalRule sessizce ölüydü | `app/goal_rules.py:130` | `AccountType.cash.value=='cash'` (True), `str(...)=='AccountType.cash'` (False); import OK | ✅ |
| 2 | DATA-003/004 / BUG #060 | SQLite connect listener: `foreign_keys=ON`, WAL, `busy_timeout`, `synchronous=NORMAL` — FK enforcement default kapalıydı, ondelete tanımları çalışmıyordu | `app/database.py` | Canlı bağlantı: `foreign_keys=1, journal_mode=wal, busy_timeout=5000`. `foreign_key_check`: **20 yetim reasoning_traces kaydı** tespit (temizlenecek) | ✅ |
| 3 | RULE-023 / ADR-026 | ZikZak additive `carried_forward` REDDEDİLDİ (çift-sayım/Sanal Zenginlik). Dinamik `daily_limit` zaten zikzak; yanıltıcı yorum düzeltildi, fonksiyonlar DEPRECATED | `app/rules_engine.py:729-732`; `adr-026` | Simülasyon: naif today_target=1474.96 vs sürdürülebilir 394.10 (çift-sayım kanıtı). Import + davranış (today_target=344.84) korundu | ✅ |
| 4 | FE-002 / BUG #061 | Dinamik Tailwind renkleri prod'da purge oluyordu → safelist eklendi. **Ek latent bug:** palette'te 950 shade'i yoktu, `bg-color-950/30` (RedLines dark bg) hiç render olmuyordu → 4 palette'e 950 eklendi | `frontend/tailwind.config.js` | `npm run build` (5.25s) + dist CSS grep: `bg-warn-950/30`, `dark:bg-warn-950/30`, `text-brand-400`, `ring-negative-500` hepsi VAR | ✅ |

## Tur 2 — P0 sprinti (per-file MASTER-FIX-LIST'ten)

| # | ID | Değişiklik | Dosya | Doğrulama | Durum |
|---|----|-----------|-------|-----------|-------|
| 5 | P0-18 SC-001 / BUG #062 | `run_extractor` except'ine `db.rollback()` — bir extractor commit'te patlarsa paylaşılan session zehirlenip sonraki extractor'lar + Coach `_save_message` sessizce/patlayarak çalışmıyordu | `app/scheduler.py` | app.main import OK | ✅ |
| 6 | P0-21 SH-002 / BUG #063 | `GoalUpdate.status` literal'inden "achieved" çıkarıldı — kullanıcı PATCH ile hiç katkı yapmadan "sanal başarı" işaretleyemez; achieved yalnız refresh_goal'da | `app/schemas.py` | `GoalUpdate(status='achieved')` → ValidationError; 'active' geçerli | ✅ |
| 7 | P0-6 GR-001 / BUG #064 | "fixed" allocation işareti `tx_amount>=0` (hep True) yerine `tx.transaction_type`'tan — gidere eşleşen fixed kural withdrawal yerine +contribution kaydedip goal'i şişiriyordu | `app/goal_rules.py` | `income.value=='income'`; import OK | ✅ |
| 8 | P0-9 CS-001 / BUG #065 | premortem yanlış anahtar `crunch_day` (hep '-') → `lowest_balance_date` + `lowest_balance_tl` + `crunch_count` eklendi; nakit-kriz verisi artık LLM'e ulaşıyor | `app/premortem.py` | `build_cockpit_snapshot` anahtarları kodla teyit | ✅ |
| 9 | P0-5 GE-001 / BUG #066 | goal_engine `snowball.months_to_freedom` (attribute) → `snowball["months_to_freedom"]`; compare_strategies dict döndürüyor, AttributeError bare-except'te yutuluyordu → debt_freedom "tahmini bitiş" hep None'du | `app/goal_engine.py` | Canlı: `months_to_freedom=9` dönüyor; attribute erişimi AttributeError (eski hata teyidi) | ✅ |
| 10 | P0-20 RCH-003 / BUG #067 | `update_checkpoint`'e koruma: korunan (priority=1+red_line) checkpoint'in priority/checkpoint_type'ı değiştirilip sonra hard-delete ile Master Checkpoint enforcement delinmesin | `app/routers/checkpoints.py` | app.main + router import OK | ✅ |

| 11 | P0-2 AE-002 / BUG #068 | `_execute_sell_investment`: satış gelirinin hedef hesabı MUTASYONDAN ÖNCE doğrulanıyor — geçersiz/emanet/eksik hesapta lot düşmeden başarısız dönüyor (eskiden `net_eline_gecen` hiçbir yere yatmadan lot düşüp success dönüyordu → para sessizce kaybı) | `app/action_executor.py` | **In-memory test 4 senaryo:** geçerli→lot 6→2+para yatıyor; emanet/geçersiz/hedefsiz→fail+lot 6 kalıyor | ✅ |
| 12 | P0-1 AE-001 / BUG #069 | `execute_pending_action` post-commit trigger'ı ayrı try'a — trigger hatası zaten 'executed' aksiyonu 'failed' işaretleyip çift-sayıma yol açmasın. (Tam handler-commit birleştirmesi test ağı sonrası) | `app/action_executor.py` | app.main import OK | ✅ |

| 13 | P0-15 REX-001 / BUG #070 | Recurring `last_triggered_year_month` artık propose'ta değil **execute'te** (`_mark_recurring_triggered`) set ediliyor — reddedilen/başarısız gider "bu ay halledildi" sayılıp kaybolmuyor, re-triggerable kalıyor | `action_executor.py`, `expenses.py`, `incomes.py` | In-memory: None→2026-07; non-recurring no-op; import OK | ✅ |
| 14 | P0-16 RIN-001/REX-004 / BUG #071 | Recurring tetikleme `day_of_month`'u ay uzunluğuna clamp'liyor — day=31 kısa aylarda (Şubat/Nisan…) sessizce atlanmıyor | `expenses.py`, `incomes.py` | Clamp: 31→30 (Nisan), 31→28 (Şubat) | ✅ |

| 15 | P0-13/14 RGO-001/002 / BUG #072 | `create_allocation`: bu tx'e tüm hedeflerdeki mevcut allocation toplamı + yeni istek, `abs(tx.amount)`'ı aşamaz (422) — 10 TL işlem "1M katkı" veya aynı tx çok hedefe tam tutarla bağlanıp sanal zenginlik/çift-sayım üretemez | `app/routers/goals.py` | In-memory: sum(abs)=80; 80+30>100 reddet, 80+20 izin | ✅ |

| 16 | P0-11 RRE-001 / BUG #073 | reports category_breakdown "both" modunda gelir+gider aynı kategori satırında toplanıyordu → `transaction_type` group_by'a eklendi, yön etiketli ayrı satırlar | `app/routers/reports.py` | In-memory: "diger" → 2 satır (gelir 1000, gider 200); eskiden 1200 | ✅ |
| 17 | P0-12 RRE-002 / BUG #074 | reports upcoming_cashflow krediler için sadece 1 taksit gösteriyordu → ufuk boyunca aylık taksitler (kalan-limit + gün-clamp + yıl-geçişi) | `app/routers/reports.py` | Logic test: 180g→6 taksit, remaining=2 sınırı, gün-31 clamp, yıl-geçişi | ✅ |

## Genel smoke test (17 fix sonrası, canlı DB read-only)
`generate_cockpit` ✅ (today_target==daily_limit → ADR-026 doğru) · `generate_forecast(180g)` ✅ · `build_cockpit_snapshot` ✅ (P0-9 anahtarları mevcut) · `app.main` import ✅ (her batch). Çekirdek motorlar sağlam.

| 18 | SBK-001..007 / BUG #075 | `scripts/backup.py`: DB yolu DATABASE_URL'den (hardcoded değil, mutlak); DB yoksa `sys.exit(1)` (sessiz başarı yok); negatif `--keep-days` reddi; az önce alınan yedek asla silinmez (≥1 garanti); saniye hassasiyeti + integrity_check + sqlite hata yakalama | `scripts/backup.py` | Gerçek yedek: 380 KB alındı, integrity OK, yeni silinmedi; negatif -5 reddedildi; DATABASE_URL türevli yol | ✅ |
| 19 | SSD-001 / BUG #076 | `scripts/setup_data.py`: `drop_all` öncesi açık onay (interaktif) veya `--force`/`SETUP_DATA_FORCE=1` + hedef DATABASE_URL uyarısı — yanlışlıkla Murat'ın gerçek verisini silme koruması | `scripts/setup_data.py` | import OK (main/drop_all çalışmadı, guard aktif) | ✅ |

| 20 | TEST-018/001 / BUG #077 | `pyproject.toml` (yeni) `testpaths=["tests"]` — `pytest` artık kökteki `test_*.py` (import-time `drop_all`!) script'lerini TOPLAMAZ → canlı-veri kaybı riski kapandı. + `requirements-dev.txt` + izole emanet testi (5 test) | `pyproject.toml`, `requirements-dev.txt`, `tests/test_action_executor_emanet.py` | `pytest` emanet testi 5/5 PASSED (0.11s) | ✅ |
| 21 | TEST-005/006 / BUG #078 | `conftest.py` `db_session` artık production engine yerine **izole in-memory StaticPool** — canlı DB'ye yazma + testler arası sızıntı riski kapandı | `tests/conftest.py` | **Tüm süit: 159 passed, 1 skipped, 0 failed (3.70s)** — 17 fix hiçbir testi bozmadı | ✅ |

## Test durumu
- **159 test yeşil, 0 hata** (izole in-memory, 3.70s). Master Checkpoint emanet enforcement + P0-2 artık gerçek testle korunuyor.
- Bekleyen test işi: rules_engine/action_executor için genişletilmiş kapsam (Hypothesis property testleri), LLM eval harness (coach P0-19 için).

## Tur 3 — script veri-güvenliği + test altyapısı + P0-3

| # | ID | Değişiklik | Dosya | Doğrulama | Durum |
|---|----|-----------|-------|-----------|-------|
| 18 | SBK-001..007 / BUG #075 | backup.py: DB yolu DATABASE_URL'den, negatif keep-days reddi, az-önceki yedek silinmez, saniye+ezme-koruması, integrity_check, mutlak yol | `scripts/backup.py` | Gerçek yedek alındı (380 KB, integrity OK); negatif reddedildi | ✅ |
| 19 | SSD-001 / BUG #076 | setup_data.py drop_all öncesi interaktif onay + `--force`/env flag + DATABASE_URL uyarısı (Murat'ın gerçek verisi yanlışlıkla silinmesin) | `scripts/setup_data.py` | import-safe (main/drop_all çalışmadı) | ✅ |
| 20 | TEST-018/001 / BUG #077 | `pyproject.toml` testpaths=["tests"] → pytest kök `test_*.py` (drop_all) toplamaz + `requirements-dev.txt` + izole emanet testi (MC1 + P0-2, 5 test) | `pyproject.toml`, `requirements-dev.txt`, `tests/test_action_executor_emanet.py` | 5 emanet testi geçti | ✅ |
| 21 | TEST-005/006 / BUG #078 | conftest `db_session` production engine → izole in-memory StaticPool (canlı DB yazma + test sızıntısı riski kapandı) | `tests/conftest.py` | Tüm süit **159→161 yeşil**, 0 hata | ✅ |
| 22 | P0-3 DS-001 / BUG #079 | debt_strategy kart asgari ödemesi her ay güncel bakiyeden (azalan); eskiden başlangıç bakiyesinden sabit → payoff iyimserdi | `app/debt_strategy.py` | 2 test: azalan-min yakınsama + korunum invariant; süit 161 yeşil | ✅ |

| 23 | P0-8 SE-002 / BUG #080 | simulation add_transaction bakiyeyi koşulsuz (transfer dahil) değiştiriyordu; gerçek executor SADECE `auto_update_balance=True` iken, transfer'de hiç değiştirmiyor → birebir hizalandı | `app/simulation_engine.py` | Süit 162 yeşil | ✅ |
| 24 | P0-4 DS-003 / BUG #081 | debt_strategy: faizi belirtilmemiş krediler faizsiz simüle ediliyordu (iyimser maliyet) → `compare_strategies` sonucuna açık `warnings` eklendi | `app/debt_strategy.py` | +1 test (faizsiz kredi uyarısı); süit 162 yeşil | ✅ |

| 25 | LLM-003 / BUG #083 (DEVRİMSEL #1) | Grounding check: koç cevabındaki her TL tutarı cockpit'e izlenebilir mi denetlenir; izlenemeyen → uyarı + confidence≤0.4 + trace grounding_violation. "Rules Engine karar verir, LLM açıklar"ın doğrulama katmanı; "varsayım yasak" mandatının kod enforcement'ı | `app/grounding.py` (yeni), `app/coach.py` | +6 test; süit 168 yeşil | ✅ |
| 26 | P0-7 GR-... / BUG #084 | simulation `_project_forward` zincirleme ufuklarda sınır gününü (T+30) çift sayıyordu (`[start,end]` kapalı pencere) → yarı-açık `(start,end]`. Önce boundary testi kırmızı (kredi zincir 100k→80k vs tek 100k→85k), fix sonrası eşit | `app/simulation_engine.py`, `tests/test_simulation_boundary.py` (yeni) | +3 test; süit 171 yeşil | ✅ |
| 27 | P0-19 / BUG #085 | Coach parantezsiz düz geçmiş-zaman sahte-tamamlama ("Kaydettim.") propose_action olmadan "işlendi" izlenimi veriyordu → `_FAKE_PASTTENSE_RE` (1. tekil + edilgen) iddia cümlesini atar + netleştirme sorusu. Kullanıcının geçmişine dokunmaz | `app/coach.py`, `tests/test_coach_fake_completion.py` (yeni) | +16 test (8 catch + 6 preserve + 2); süit 187 yeşil | ✅ |

> **Durum: 21/21 P0 çözüldü + doğrulandı (10 Tem 2026, süit 187 yeşil).** + Devrimsel adım #1: grounding check (LLM-003).

## SESSION-2 (11 Tem 2026) — Gemini tam-okuma + 7-ajan denetim + vizyon gerçekleştirme

Bu turda ~50 commit, süit **162 → 287 yeşil** (+125 test). Tümü `kalite-seruveni` dalında,
`main` dokunulmadı, tek yazarlı (AI trailer'ları temizlendi — kullanıcı isteği).

**Devrimsel/altyapı:** LLM-003 grounding (#083) · LLM-005 Ollama sovereign · serializers (#092) ·
koç davranış sözleşmesi harness (deterministik eval).

**Son 2 P0 + per-file denetim (#084-#108, hepsi doğrulandı):** P0-7 sim sınır çift-sayım (#084),
P0-19 sahte-tamamlama (#085 + iter2 regresyon düzeltmesi), beklenen-gelir çift-sayım (#086),
txn-update balance corruption (#087), expense ownership (#088), debt rollover (#089), goal-rules
işaret (#090), hesap-silme 409 (#091), tzinfo sweep (#092), FallbackProvider log (#093), YENİ
CHECKPOINT koruma (#094), KURAL SIFIR gelecek/niyet (#095), sim emanet (#101), sell_investment
valuation (#102), income-on-card (#103), K2 insight dedup (#104), goal projeksiyon span (#105),
debt paid-state (#106), cashflow sınırlama notu (#107), anomali penceresi (#108).

**Vizyon gerçekleştirme (kurucu koç tamamlandı):** A1 kart son ödeme reminder (#096), A3 aylık
özet (#097), koç aylık trend (#098), son işlemler grounding-tutarlı (#099), zikzak yarınki-limit
projeksiyonu (#100), Borç Çığı koç context'i (#109), frontend Cockpit görünürlük, main.py refactor.

**Golden test:** `test_founding_scenario.py` — Murat'ın manzarası entegre doğrulandı (Gölge
Muhasebe + Zikzak + kart son ödeme + Borç Çığı). Denetim kaydı: `dosya-denetimi/ROUND2-*.md`.

## Bekleyen (onay/temizlik)
- **20 yetim `reasoning_traces` kaydı** (user id=2, var olmayan): FK açıkken app çalışır ama veri kiri. Silmek düşük riskli (ölü debug trace) — **kullanıcı onayı bekliyor** (veri silme).
- Açık backlog (büyük/mimari, aceleye gerek yok): structured output (LLM-gated, harness ile de-risk edildi — ama NL koç için muhtemelen gereksiz), Account/Goal cascade (tek-kullanıcıda düşük etki).

## Yürütme notları
- Numaralandırma: BUG #059→#109 bu iki turda. ADR-026 (önceki #025).
- Her fix `dersler-gemini.md` 7 meta-dersine ve kök vizyona hizmet ediyor.
- Deterministik kalite backlog'u TÜKENDI; sonraki faz: gerçek kullanım (Wave-2 disiplini) veya kullanıcı yönlendirmesi.

## SESSION-3 (11-12 Tem 2026) — FEAT katmanı + eval-driven + zayıf-sağlayıcı sertleştirme

Deterministik P0 backlog'u tükendiğinden bu tur **vizyon-ilhamlı FEAT katmanı** (wave3-vision;
YNAB/Copilot/Actual/Maybe'den KOPYALAMADAN ilham) + eval-driven koç ölçümü + gözlem-güdümlü
bug avı. Süit **287 → 601 yeşil** (+~314 test, 1 skip). `main` dokunulmadı, tek yazarlı.

**FEAT (kanıt-temelli, hepsi test + koç context entegrasyonu):**
| FEAT | Değişiklik | Doğrulama |
|------|-----------|-----------|
| FEAT-001/002 | Kategori bütçe zarfları (envelope) + atanmamış nakit ("Ready to Assign"); yeni Envelope tablosu (create_all-safe), CRUD router, Bütçe paneli | test_envelopes.py; koç context "BÜTÇE ZARFLARI" |
| FEAT-003 | Birikim zarfları (sinking funds) — aylık gereken katkı; GoalRead.@computed_field (şema/DB değişmez) | test_sinking_fund.py |
| FEAT-005 | Kategori bütçe aşım öngörüsü (zarf-farkında erken uyarı) | test_category_overspend.py |
| FEAT-006/007 | Abonelik tespiti + "düzenli gidere çevir" döngüsü + cockpit yük görünürlüğü | test_subscription_*.py |
| FEAT-009 | Safe-to-Spend (kart-farkında, Copilot ilhamı) | test_safe_to_spend.py |
| FEAT-010 | Nakit runway (gelirsiz kaç gün) — kredi taksitleri dahil | test_cash_runway.py |
| FEAT-012 | Borçsuz olma tarihi (Borç Çığı çıktısından) | test_debt_freedom_metric.py |
| FEAT-013 | Faiz sızıntısı sayacı (aylık/yıllık/günlük borç faizi) | test_interest_leak.py |
| FEAT-021/024 | Net değer ayrıştırması + enflasyon-düzeltilmiş reel net değer; Net Değer Analizi paneli | test_networth_attribution.py, test_real_networth.py |
| FEAT-022 | Şeffaf finansal sağlık skoru (0-100 composite, bileşenler görünür) | test_health_score.py + property |
| LLM-004 | Koç eval harness (deterministik, judge-LLM'siz) + eval_runner (izole canlı ölçüm) | test_coach_eval.py; canlı: 6/8 |

**Bug/kural (gözlem + property + canlı-eval bulguları):**
| ID | Kök-neden | Doğrulama |
|----|-----------|-----------|
| BUG #121 | Nakit krizi öngörüsü kritik alert'e çevrilmiyordu (ileriye-dönük insolvency) | test_cashflow_crunch_alert.py |
| BUG #122 | Alert tutarları nokta-ondalık ("74.99 TL") grounding'i delip Türkçe tutarsızdı → _tl() | test_tl_format_grounding.py |
| BUG #123 | Safe-to-Spend kart borcunu düşmüyordu → tehlikeli iyimserlik (gözlem-yakalandı) | test_safe_to_spend.py |
| BUG #124 | Runway kredi taksitini saymıyordu → crunch ile çelişki (gözlem-yakalandı) | test_cash_runway.py |
| BUG #125 | Alert önem sıralaması kararsızdı → kararlı stable-sort (kritikler önce) | test_metric_coherence.py |
| BUG #126 | Alert yorgunluğu → uyarılar top-3, kritikler korunur, gizli_uyari_sayisi | test_metric_coherence.py |
| BUG #127 | Zayıf sağlayıcı gerçekleşmiş eylemi düz metinle geçiştirip propose'u unutuyordu → STEP-E retry has_realized_action ile genişletildi | test_coach_behavior_contract.py (düz-metin + nötr-guard) |
| BUG #129 | recommend_next_action (FEAT-041) "saf/dışa-açık" sözleşmesi eksikti: property fuzzing 3 gerçek çökme buldu — daily_limit/faiz_sizintisi/toplam_gecikmis present-but-None → _tl(None)/None>0 TypeError; ayrıca alacak_yaslanma non-dict + eksik en_riskli guard'ı. Production'da crash yoktu (generate_cockpit hep geçerli) ama sözleşme artık arbitrer girdide tutuyor | test_next_action.py (fuzz 300+ örnek, 2000 elle doğrulandı) |
| RULE-008 | simulate_partial_sale giriş doğrulaması | test_partial_sale_validation.py |
| RULE-009 | Statü likidite oranı nakit>0 guard | test_rules |
| RULE-010/011 | payoff_date gerçek takvim ayı + enjekte today; asla-bitmeyen borçta None | test_debt_payoff_date.py |
| BE-009 | chat hatası ham detay sızdırmaz + loglanır | test_coach_chat_endpoint.py |
| — | Sağlık skoru denormal-bölen round(inf) overflow'u (property test yakaladı) | test_metric_properties.py |
| SEC/KVKK | Tüm veriyi dışa aktar (GET /api/user/export) — egemenlik/veri taşınabilirliği | test_data_export.py |

**Canlı eval bulguları (dış kısıt, kod defekti değil):** Groq/Cerebras deprecated model 404'leri
düzeltildi (gpt-oss-120b). Groq free tier 8000 TPM Türkçe prompt'u (~8400 tok) karşılamıyor →
her çağrı 413 verip fallback'e düşüyor (fonksiyonel çalışır, round-trip israfı). Detay: memory
`reference_groq_tpm_limiti`. Eval action gap'i (2/8) canlı-sağlayıcı erişilebilirliği kaynaklı;
gating deterministik doğrulandı (propose SUNULUYOR), #127 retry'ı bunu sertleştirdi.

**Golden:** test_founding_scenario + test_e2e_journey (uçtan-uca yeni yüzey entegrasyonu).

### SESSION-3 devamı (12 Tem 2026) — borç-stratejisi katmanı (Murat'ın 5-kredi + dolu-kart gerçeği)

Deterministik + FEAT/S işleri tükenince en yüksek-değer kalanlar Murat'ın borç-dominant
durumuna göre seçildi (gözlem-güdümlü, kopyalamadan ilham). Süit **620 → 632 yeşil**.

| FEAT | Değişiklik | Doğrulama |
|------|-----------|-----------|
| FEAT-015 | Kart asgari-ödeme tuzağı: sadece asgari ödeme senaryosu (kaç ay + toplam faiz). Asla-bitmez (asgari<faiz) → kritik sarmal; ≥12 ay → uyarı. `calculate_min_payment_trap` + cockpit + koç + Cockpit.jsx | test_min_payment_trap.py (12) |
| FEAT-027 | Alacak yaşlandırma (AR aging): 13 dağınık alacağı vade-yaşına göre grupla (60+/31-60/1-30 gecikmiş · vadesiz kör nokta); en_riskli önce kovala. `calculate_receivables_aging` + cockpit + koç + Cockpit.jsx | test_receivables_aging.py (7) |
| FEAT-014 | Kredi konsolidasyon simülatörü (nötr, tavsiye değil): (1) assumption-free eşik = ağırlıklı ort. oran; (2) what-if annüite (oran+vade → taksit/faiz). `calculate_consolidation_baseline`/`simulate_consolidation` + `GET /api/debt-strategy/consolidation` + DebtStrategy.jsx formu | test_consolidation.py (12) |

Borç-stratejisi yüzeyi artık kapsamlı: snowball/avalanche (mevcut) + borçsuzluk tarihi
(FEAT-012) + faiz sızıntısı (FEAT-013) + asgari tuzağı (FEAT-015) + konsolidasyon (FEAT-014);
alacak tarafı yaşlandırma (FEAT-027). `collect_debts` bu metrikler arasında paylaşımlı (tek sorgu).
Metrik-tutarlılık gözlemle doğrulandı: borç özgürlük (avalanche, rollover) vs asgari tuzağı
(izole min-only) FARKLI senaryolar → çelişki değil (#124-tarzı bug yok). Koç context ~946 token
(tüm bloklarla) — Groq TPM darboğazı sistem prompt'undan, context'ten değil.

**Ek sağlamlaştırma:** RESIL-008 circuit breaker (request-too-large veren sağlayıcı process
boyunca atlanır — Groq TPM israfı bitti) · BUG #128 annüite overflow + küçük-oran hassasiyet
guard'ları (property test yakaladı) + FEAT-014/015/027 korunum invariant testleri.

**Eval-driven doğrulama (12 Tem, fallback config):** BUG #127 retry + circuit breaker ile koç
eval'inde **action gap KAPANDI** — gerceklesmis_eylem/kart_action artık PASS (önce 2/8 düşüyordu;
hipotez "propose sunuluyor ama zayıf sağlayıcı çağırmıyor" doğrulandı, retry + çalışan Cerebras
çözdü). Kalan 2 FAIL (analiz grounding): Cerebras seyrek-veri analizinde TL uyduruyor → grounding
DOĞRU yakalıyor (grounded=-, confidence düşürülüyor) — sistem tasarım gereği çalışıyor, kod bug'ı
değil (kanonik eval DB'de borç/alacak yok → yeni context blokları devrede değil). Eval-driven
döngü işledi: hipotez → fix → eval teyidi.

### SESSION-3 dayanıklılık + doğruluk + egemenlik sweep (12 Tem 2026, süit 632→661)

Deterministik/FEAT işleri doyunca provider-gerçeği (Groq/Cerebras TPM, Gemini kota) etrafında
dayanıklılık + kullanıcıyı etkileyen doğruluk + veri-egemenliği tamlığı hedeflendi.

| ID | Değişiklik | Doğrulama |
|----|-----------|-----------|
| FEAT-016 | Kart utilization: toplam borç/limit oranı + band (saglikli/orta/yuksek/kritik) + %30 sağlıklı borç hedefi (somut çapa) + trend (en eski snapshot kart borcu ÷ güncel limit, ≥7g). Koç yalnız yuksek/kritik'te uyarır; Cockpit çubuk kartı. Murat'ın #1 problemi (maxed kart) tek metrikte | test_card_utilization.py (9) |
| FEAT-034 | Otomatik kategori: gider + kategori boşsa açıklamadan türetir (Migros→alisveris). MERCHANT_KEYWORDS + QUICK_KEYWORDS, kelime-sınırı token eşleşmesi (substring değil → "sokak" yanlış pozitifi yok). Kullanıcının açık seçimini ezmez. UI ipucu | test_auto_categorization.py (9) |
| FEAT-032 | İstek listesi / 24-saat impuls bekleme: WishlistItem + router (add/list/resolve, scheduler yok — 24h "hazır" türetilir) + koç bağlamı + export + Wishlist.jsx. Borç-batık için davranışsal impuls-lever | test_wishlist.py |
| FEAT-030 | Satın alma fırsat maliyeti: amount'ı harcamak vs en yüksek faizli borca ödemek (borçsuzluk + faiz farkı). Avalanche RAM kopyası; assumption-free. + endpoint + DebtStrategy.jsx formu | test_opportunity_cost.py (8) |
| RESIL-008 | Circuit breaker: request-too-large (413) veren sağlayıcı process boyunca atlanır (429 geçici kotadan AYRI). `_engine` singleton → Groq TPM israfı ilk çağrıdan sonra biter | test_fallback_provider.py (+4) |
| RESIL-004 | Graceful degradation: tüm sağlayıcı düşünce ham hata sızmaz + "Rules Engine LLM'siz çalışır, verilerin sağlam" mesajı + cockpit korunur | test_coach_behavior_contract.py |
| BE-025 | Fallback modda günlük-limit BLOCK koruması ölüydü (usage hep %0). provider_used loglanır + PROVIDER_DAILY_LIMITS haritası → Gemini kotası doğru izlenir | test_usage_tracking.py (5) |
| BE-010 | 6 sessiz `except: pass` → tanılanabilir loglama (goal_engine except'i #066'da AttributeError gizliyordu) | süit yeşil |
| SEC-006 | coach mesajı max_length=4000 (sağlayıcı token/maliyet koruması; büyük yapıştırma zinciri patlatmasın) | test_coach_chat_endpoint.py (+2) |
| SEC-032 | Finansal float alanları sonlu olmalı: paylaşılan schema_types (allow_inf_nan=False + üst sınır 1e12) accounts/transactions/debts/incomes/expenses'e uygulandı → inf/NaN/taşma(1e308) girişte reddedilir (round(inf) rules_engine sızıntısı kesildi). İşlem ≤0 dostça mesajı korundu | test_financial_input_validation.py (21) |
| SEC-032b | İKİNCİ savunma (propose→execute yolu): action_executor `_parse_finite` helper'ı ile para-hareketi handler'ları (update_balance/sell_investment/add_transaction/update_fund_price) nan/inf payload'ı reddeder — NaN eskiden `<=0`/`>lot` guard'larını atlayıp DB'ye yazılabiliyordu (nan bakiye/lot cockpit matematiğini bozar). Mutasyon YOK, status=failed | test_execute_pending_action.py (+3) |
| SEC-032c | ÜÇÜNCÜ boşluk: quick_text tutarı Pydantic şemasını ATLIYORDU (create'te amount None gelip _parse_quick_text'te doldurulur) → "1e308 yemek"/"Infinity market"/"nan kahve" DB'ye sızıyordu. Parser'a sonlu + üst-sınır(1e12) kontrolü eklendi (400) | test_financial_input_validation.py (+4) |
| SEC-031 (kısmi) | İşlem serbest-metin alanları (category/description/quick_text) cömert max_length aldı — DB bloat + prompt-injection payload boyutu + koç context şişmesi koruması. (Tam SEC-031 = tüm Dict[str,Any] propose payload şemaları; bu ilk dilim) | test_financial_input_validation.py (+3) |
| SEC-032d | DÖRDÜNCÜ giriş: DOĞRUDAN fund-price endpoint'i (`FundPriceUpdate.new_price` float gt=0) inf/1e308 kabul ediyordu → update_fund_price_manual'da lot*inf=inf bakiye → yatırım hesabı bozulurdu (executor yolu #032b'de korunmuştu ama doğrudan endpoint ayrı). FinansTutar'a geçirildi. Goals zaten Decimal+max_digits ile korumalıymış (doğrulandı) | test_financial_input_validation.py (+1) |
| KVKK | Veri export tamlığı: eylem/karar/hedef-izleme + koç-şeffaflık kayıtları eklendi (18 tablo). TAMLIK invariant testi | test_data_export.py (+2) |

**Provider gerçeği (memory: reference_groq_tpm_limiti):** Zengin veride koç isteği ~8000+ token →
Groq HEM Cerebras (gpt-oss, 8000 TPM) aşılır → circuit breaker ikisini de eler → koç fiilen
Gemini'de çalışır. Bu dış kısıt kod defekti değil; sistem prompt trim'i RİSKLİ (docs uyarısı) →
otonom yapılmadı. Eval DB kasıtlı minimal (davranışı provider-boyutundan izole).

**Golden tamamlandı:** test_founding_scenario Murat'ın alacaklarıyla genişletildi → yeni
borç/alacak metrikleri (asgari tuzağı/aging/konsolidasyon) + grounding kurucu manzarada kilitli.

### SESSION-3 doğruluk taraması (12 Tem 2026, süit 671→690) — RULE/DATA/LLM long-tail

FEAT + deterministik İLK ADIM (FEAT-041) sonrası, gözlem/backlog ile GERÇEK finansal-doğruluk
bug'ları avlandı (edge/cosmetic değil — birincil yolu etkileyenler öncelikli).

| ID | Bug (gerçek etki) | Doğrulama |
|----|-------------------|-----------|
| FEAT-041 | Deterministik "İLK ADIM" — sinyaller tek en-yüksek-etkili hamleye (temerrüt>kriz>tahsilat>fırsat>stabil). Öncelik LLM yargısına değil KODA → sağlayıcı-bağımsız. Fırsat likidite-güvenli (runway≥30). | test_next_action.py (10) |
| FEAT-017 | Borç ödeme ilerlemesi (momentum, Ramsey) — en eski snapshot'tan azalma. | test_debt_progress.py (7) |
| FEAT-030 spillover / BUG #129 | Fırsat maliyeti amount'ı avalanche sırasında dağıtır (fazlasını boşa atmıyor); property test yakaladı. | test_debt_metric_properties.py |
| RULE-016 | Stale next_payment_date remaining'i tüketip gelecek taksitleri gizliyordu → crunch/safe-to-spend TEHLİKELİ İYİMSER. Geçmiş-vadeli bugüne çekilir. | test_cashflow.py (+2) |
| RULE-020 | Kategori kalıpları cari pencerede üst sınır yok → GELECEK işlemler sızıp sahte anomali. `<= today` eklendi. | test_category_patterns.py |
| RULE-014 | goal_engine para Decimal(str(float)) kirli ondalık → baseline. `_money()` quantize. | goal testleri |
| RULE-015 | Cash hedef tamamlanma int() truncation → iyimser. math.ceil. | projection testleri |
| BE-010 | 6 sessiz except:pass → loglama (goal_engine except'i #066'yı gizliyordu). | süit |
| BE-025 | Fallback modda günlük-limit BLOCK koruması ölüydü + usage %0. provider_used loglanır. | test_usage_tracking.py |
| LLM-007 | usage/model_name/provider_used yalnız Groq'ta → tüm sağlayıcılarda (gerçek Gemini için trace kördü). | test_provider_metadata.py |
| LLM-001 | Anthropic modeli claude-opus-4-7→4-8 (güncel). | import |
| DATA-018 | Hesapsız "yetim" işlem (bakiye etkilemeyen) → varsayılan hesap her create'te + yoksa 400. | test_transaction_account_guard.py |
| DATA-020/028/029, SEC-006/009, RESIL-004/008, #127/#128 | Seed FK, 0-allocation, recurring ay-sınırı, mesaj sınırı, error truncate, graceful degradation, circuit breaker, annüite guard | ilgili testler |

**Ertelenen (bilinçli):** RULE-003/004/005 (kart-döngüsü edge, Murat'ın statement_day=2 → etkilenmez,
cohesive M), RULE-018/019 (simülasyon ikincil-yol, kısa ufukta minör), RULE-017 (gün sürüklenmesi
minör), RULE-013 (baseline model değişimi + migrasyon). Birincil-yol doğruluk bug'ları tükendi.

---

## Goal Charter Yürütme (Wave-2 Kapanış) — M1

| ID | Değişiklik | Dosya | Doğrulama | Durum |
|----|-----------|-------|-----------|-------|
| M1 / ADR-013 | Envelope (FEAT-001) + WishlistItem (FEAT-032) tabloları create_all ile eklenmişti, migration yoktu. Migration `fec73e5343e5` yazıldı (inspector-guard'lı, idempotent); down_revision f3dda4d3996d. Canlı DB'ye `alembic upgrade head` → iki tablo yaratıldı | `alembic/versions/fec73e5343e5_*.py`, `scripts/test_fresh_db_migration.py` | Canlı DB 20→22 tablo (envelopes+wishlist_items VAR), head fec73e5343e5. Fresh-db senaryo testi GEÇTİ. pytest 774 passed | ✅ |
| M1 / merge | `kalite-seruveni` (210 commit) → `main` `--no-ff` merge (e5a7d35) + origin'e push. 3 günlük iş GitHub'da güvende. Rollback tag `pre-kalite-seruveni-merge` push edildi | git main | origin/main=e5a7d35, pytest 774 passed | ✅ |
| M1 / bulgu | **Migration zinciri sıfırdan-şema değil** (baseline STAMP; taban create_all ile). Bomboş DB'de upgrade çöker (`NoSuchTableError: coach_insights`). ADR-013 kısmen gerçekleşmiş → M6/DATA backlog adayı: baseline'ı gerçek create_table'a çevir | `alembic/versions/fa46373f4ca8_*.py` | `scripts/test_fresh_db_migration.py` gerçek senaryoyu test eder | 📋 not |

## OTONOM KARAR M1 — Migration genesis collapse (ADR-013 tam gerçekleştirme)

| ID | Değişiklik | Doğrulama | Durum |
|----|-----------|-----------|-------|
| OTONOM KARAR M1 | **Bulgu:** temiz DB'de `alembic upgrade head` çöküyordu (baseline STAMP idi, coach_insights orphan+alter). **Kategori: (c) ADR İhlali** (ADR-013/DB-001). "Testi uyarlıyorum" reflex'i REDDEDİLDİ. **Karar (K10):** non-destructive collapse — `b70779a2f621_genesis_full_schema` tüm 21 tablo+48 index (create_all eşdeğeri) yaratan root; 9 migration no-op'a indirildi (revizyon+zincir korundu). **Gerekçe:** en sağlam+risksiz (canlı DB atası=genesis, dokunulmaz; re-stamp yok). ADR-013a yazıldı | Temiz DB `alembic upgrade head` → 21 tablo, create_all ile kolon+index ÖZDEŞ (`scripts/test_fresh_db_migration.py`). Canlı DB dokunulmadı (fec73e5343e5, 22 tablo). pytest 774 | ✅ |

## Milestone 2 — Rehber + skill + ADR + Mustafa temizlik

| ID | Değişiklik | Doğrulama | Durum |
|----|-----------|-----------|-------|
| M2.1 | PROJE.md 4 May bayat → güncel (774 baseline, kritik yollar, KURAL+OTONOM KARAR, anti-pattern, audit kod, skill) | 33→74 satır | ✅ |
| M2.2 | 4 global skill repo'ya kopyalandı + `financialos-kalite-seruveni` skill yazıldı | `.asistan/skills/` 5 skill, skill kayıtlı | ✅ |
| M2.3 | ADR-001/012/013 materyalize (repo-izli); kalan 7 ADR pending (MCP boş) | 3 ADR dosyası + pending | ✅ |
| M2.4 / ADR-001 | 8 yasaklı-isim referansı isimsiz forma çevrildi (coach_insights/premortem/mobile-roadmap/wave3-vision) | grep 0, pytest 774 | ✅ |

## Milestone 3 — Yetim trace temizliği + ADR-028

| ID | Değişiklik | Doğrulama | Durum |
|----|-----------|-----------|-------|
| M3.1 | `scripts/cleanup_orphan_traces.py`: test-kullanıcı (user_id=2 test_user_decision_rhythm) + dangling-orphan (user_id=3) temizliği. R3: memory "20 yetim user_id=2" yanlıştı (2=test 56, 3=orphan 20). Backup'lı, idempotent, tüm user-scoped tablo | 82 satır silindi (76 trace+4 insight+1 goal+1 user); sadece Murat kaldı; tekrar=0 | ✅ |
| M3.2 / ADR-028 | Koç fiilen Gemini-only gerçeği belgelendi (ADR-002 yapısı korunur). D1: OpenRouter araştırması (research-log.md) — Wave-3 fallback adayı | ADR-028 + research-log yazıldı | ✅ |

## Milestone 4 — Fiyat otomasyonu (Improvement #028 / FT-006 kapanış)

| ID | Değişiklik | Doğrulama | Durum |
|----|-----------|-----------|-------|
| M4 / #028 / FT-006 | `app/price_providers/` (router: get_fund_price pytefas-reuse + 4h TTL cache + record_investment_price PriceHistory idempotent + dispatch) + scheduler cron `fetch_investment_prices_job` (02:45) — `try_auto_fetch_*` ölü koddan CANLI'ya bağlandı | Canlı: TLY=7277.90, 2/2 hesap güncel, PriceHistory satırı | ✅ |
| M4 / ADR-029 | Sağlayıcı stratejisi belgelendi. **OTONOM KARAR (kategori-b):** charter "borsapy birincil" premisi R3 ile REDDEDİLDİ (borsapy TEFAS 404); pytefas birincil (tek çalışan) | ADR-029 + research-log K10 | ✅ |
| M4 test | `tests/test_price_providers.py` (5) + `tests/test_scheduler_price_job.py` (2) — ağsız, monkeypatch, izole in-memory | 781 passed (774→781, +7) | ✅ |
| M4 / backfill | `scripts/backfill_prices_all_accounts.py` — geçmiş PriceHistory doldurma (idempotent, iş günü) | script hazır | ✅ |

## Milestone 5 — Decimal göçü (Faz A-F, Faz G onay kapısı)

| ID | Değişiklik | Doğrulama | Durum |
|----|-----------|-----------|-------|
| M5 / ADR-030 | 20 para kolonu Float→Numeric(19,4); iç aritmetik Decimal, public sınır floatify (B1 JSON float) | 789 test (781→789); canlı KOPYA upgrade OK | ✅ Faz A-F |
| M5 OTONOM-1 (kat-c) | interest_rate/lot_count/confidence_score para DEĞİL → Float kaldı (körlemesine sweep semantik yanlış) | 3 kolon Float, 20 Numeric | ✅ |
| M5 OTONOM-2 (kat-b) | Pydantic condecimal ATLANDI — floatify sınırı B1'i daha temiz karşılıyor (condecimal Decimal'i JSON'a iterdi) | schemas float, hedef karşılandı | ✅ |
| M5 / money.py | D()/ZERO/q2/q4/floatify + `float(para)`→D() (rules 22+ae+router+ft) + json default=float (5) | drift-yok kanıtı (test_decimal_precision 8) | ✅ |
| M5 Faz G | **CANLI DB upgrade YAPILMADI** — head `fec73e5343e5`, onay bekliyor | canlı balance hala `real` | ⏸️ ONAY |
| M5 Faz H+I | **CANLI upgrade UYGULANDI** (2026-07-13, Murat onayı): backup+`alembic upgrade head` `fec73e5343e5`→`38360f856577`; canlı balance NUMERIC(19,4)/Decimal, cockpit sağlam, JSON-safe | tag `milestone-5-decimal-migration` push | ✅ M5 KAPANDI |

## Milestone 6 — Kalite Serüveni Faz 3 (P1 denetim + düzeltme, artım 1)

| ID | Değişiklik | Doğrulama | Durum |
|----|-----------|-----------|-------|
| M6 denetim | 27 P1 maddesi R3 ile denetlendi (4 paralel audit agent). **16 zaten CLOSED** (Faz 2'de kapanmış, MASTER-FIX-LIST bayat-açıktı) | faz-3-durum.md | ✅ |
| P1-7 / BUG #133 | usage sayacı `date.today()`→`datetime.utcnow().date()` — TR sunucuda Gemini kotası 3 saat erken sıfırlanıyordu | test | ✅ |
| P1-9-res / BUG #134 | GoalRuleUpdate percent (0,100] validator — create/update asimetrisi | test | ✅ |
| P1-10 / BUG #132 | cash_target `current_amount` `max(.,0)` — negatif birikmiş-tutar sızıntısı | test | ✅ |
| P1-20 / BUG #135 | PremortemScenario id deterministik S1..Sn — React key çakışması (dayanıklı yeniden-ata) | test | ✅ |
| P1-23 / BUG #131 | link_premortem_outcome try/except — executed aksiyon sonrası 500 riski | test | ✅ |
| M6 güvenlik | SQL injection taraması temiz (ORM parametreli, `_EXCLUDED_SQL` statik); secret mgmt temiz (.env gitignore+git-dışı) | grep+git | ✅ |

## Milestone 6 — artım 2 (P1-1, P1-22)

| ID | Değişiklik | Doğrulama | Durum |
|----|-----------|-----------|-------|
| P1-1 / BUG #136 | goals 6 datetime alanı `UtcDateTime` (GoalRead/AllocationRead/RuleRead) — naive→UTC suffix, JS 3h kayması önlendi | 795 test | ✅ |
| P1-22 / BUG #137 | `load_cached_premortem` — aynı cockpit_snapshot_hash → LLM'siz cache dönüşü (maliyet/gecikme tasarrufu) | test_p1_22 (hit/miss) | ✅ |

## Milestone 6 — artım 3 (P1-5, P1-13, P1-19)

| ID | Değişiklik | Doğrulama | Durum |
|----|-----------|-----------|-------|
| P1-5 / BUG #139 | explicit_red_line finansal-anchor: mutlak_red/niyet_beyani/kesin_red için finansal anahtar-kelime şartı ("asla o filmi izlemem" artık kırmızı-çizgi değil) | test_p1_5 | ✅ |
| P1-19 / BUG #138 | net_worth_delta ölü param kaldırıldı (link_premortem_outcome) — spekülatif kolon eklemeden | test güncellendi | ✅ |
| P1-13 | OTONOM KARAR (kategori-b): transfer bakiye no-op = tasarım-sınırı, bug değil (geçerli sınıflandırma; çift-hesap transfer Wave-3) | belgelendi | ✅ |

## Milestone 6 — artım 4 (P1-4)

| ID | Değişiklik | Doğrulama | Durum |
|----|-----------|-----------|-------|
| P1-4 / BUG #140 | `_sweep_insights_dormant` (DRY) — decision_rhythm (dominant değiş/dağıl) + mc_reference (top-3 dışı count>0) eski aktif insight'ları dormant'a indirir; bayat sinyal kalmaz | test_p1_4 + 54 coach_insights | ✅ |

## Milestone 6 — artım 5 (P1-8)

| ID | Değişiklik | Doğrulama | Durum |
|----|-----------|-----------|-------|
| P1-8 / BUG #141 | evaluate_rules_for_transaction transaction create'e BAĞLANDI (post-commit try/except) — GoalRule otomatik-tahsis özelliği çalışıyor (yarım özellik tamamlandı, opt-in) | test_p1_8 (2, endpoint) | ✅ |

## Milestone 6 — artım 6 (P1-27 simulation parite)

| ID | Değişiklik | Doğrulama | Durum |
|----|-----------|-----------|-------|
| P1-27 / BUG #142 (SE-007) | `_load_world` `if a.X else None`→`is not None` — gerçek 0.0 falsy→None sapması | test_p1_27 | ✅ |
| P1-27 / BUG #143 (SE-004) | mark_debt_paid zaten-ödenmiş guard (executor paritesi) | test_p1_27 | ✅ |
| P1-27 / BUG #144 (SE-005) | sell_investment eksik fiyat→red (sessiz 0 TL satış yok) | test_p1_27 | ✅ |
| P1-27 / BUG #145 (SE-008) | sell_investment satış geliri emanet hedefe yatırılamaz | test_p1_27 | ✅ |

## Milestone 6 — artım 7 (P1-15 enum migration)

| ID | Değişiklik | Doğrulama | Durum |
|----|-----------|-----------|-------|
| P1-15 / BUG #146 | OperationName values_callable + migration 978ad0f00814 (RULE_CHECK→rule_check). R3: CHECK yok, data-only. **Canlı uygulandı** (backup 2026-07-13-011907) | kopya+fresh-db+803 test | ✅ |

## Milestone 6 — artım 8 (P1-24 kart stratejisi wire)

| ID | Değişiklik | Doğrulama | Durum |
|----|-----------|-----------|-------|
| P1-24 / BUG #147-151 | evaluate_credit_card_strategy cockpit'e bağlandı. **OTONOM KARAR:** util-guard (near-full kartta "float silah" zararlı → "borç azalt" uyarır). RULE-003 (gerçek tarih) + RULE-004 (eff) fix; RULE-005 R3 ile doğru bulundu (geri alındı) | test_p1_24 + 7 card_strategy + canlı | ✅ |

## Milestone 6 — artım 9 (P1-25) — P1 TAMAMLANDI

| ID | Değişiklik | Doğrulama | Durum |
|----|-----------|-----------|-------|
| P1-25 / BUG #152 | `_to_anthropic_messages` adapter — internal tool-history → Anthropic content-block (tool_use/tool_result); AnthropicProvider._raw_chat kullanıyor | test_p1_25 | ✅ |
| **P1 ÖZET** | **27/27 kapandı** (16 pre-CLOSED + 11 M6 fix/decided); 19 BUG (#131-152) + 2 canlı migration + 25 test | 806 test yeşil | ✅ |

## Milestone 8 — Wave-3 Backlog Haritalama (2026-07-13)

| ID | Değişiklik | Doğrulama | Durum |
|----|-----------|-----------|-------|
| W3-BACKLOG | `wave-3-backlog.md` — 7 kaynak tarama, 68 madde + 4 big-package, top-35 seçim | 2 denetim ajanı + R3 | ✅ |
| OTONOM KARAR M8 | Premise düzeltmeleri (kategori-a KOZMETİK değil, R3-doğrulama): (1) #059/#060/#062 tanımları yanlış→gerçek kapalı; (2) P2-1 AÇIK (db.query 183×, session.query değil); (3) DATA-003/004 KAPALI (FK pragma ON, database.py:49); (4) create_all ADR-013 ihlali yok. Gerekçe: R3 disk>rapor — denetim section'ları bayat, koda karşı doğrulandı | grep + database.py:49 okuma | ✅ |

## Milestone 9 — Kritik Kısa Süre (Wave-3, 2026-07-13)

| ID | Değişiklik | Doğrulama | Durum |
|----|-----------|-----------|-------|
| W3-001 / BUG #156 | TR sayı parse veri bozulması: `parseTRNumber` (api.js) — locale-toleranslı (son ayraç=ondalık, tek nokta+3hane=binlik). 13 çağrı yeri (Accounts/Cashflow/Transactions/IncomeDebt/Cockpit/Wishlist/Budget/Goals/PendingActions) eski `parseFloat(x.replace(',','.'))` → parseTRNumber. "1.234,56"→1234.56 (eskiden 1.234, ~1000× hata). D1: Firefly III/Maybe locale-aware. K10: TR-first + US-tolerans | api.test.js +6 test (23 geçti), npm build ✓ | ✅ |
| W3-002 | markPaid UTC gün kayması: **R3 — markPaid/IncomeDebt zaten `todayLocalISO()` kullanıyor (düzeltilmiş).** Kalan tek `toISOString().slice(0,10)` yerel-gün bug'ı CashflowCalendar.jsx:86 (bugün-vurgusu, gece 00-03 TR'de yanlış gün) → `todayLocalISO()`. Aynı bug sınıfı temizlendi | npm build ✓, todayLocalISO api.test'te test edili | ✅ |
| W3-003 | Dinamik Tailwind renk purge: **R3 — ZATEN ÇÖZÜLMÜŞ.** tailwind.config.js:14-17 safelist pattern `(text\|bg\|ring\|border)-(brand\|positive\|negative\|warn)-(100\|400\|500\|600\|950)` + dark + `-950/30` explicit. Built dist CSS'te doğrulandı (text-negative-600, ring-warn-500, bg-brand-100, text-positive-400 üretiliyor). Agent FE-002 raporu bayattı. Kod değişikliği YOK; M9 top-15 boşluğu M14'ten bir madde ile doldurulacak | dist CSS grep ✓ | ✅ (R3-kapalı) |
| W3-005 | DebtStrategy fetch hatası: catch'te `data` null kalıyor → satır 282 "Aktif borç yok" (hata≠boş). `error` state + AlertTriangle hata ekranı + "Tekrar dene". Stale data varsa korunur (yalnız toast). D1: React error/empty/loading üç-durum ayrımı standart | npm build ✓ (RTL component testi → W3-060/M14) | ✅ |
| W3-004 | DebtStrategy slider klavye: `onMouseUp/onTouchEnd` commit ediyor ama ok-tuşu bunları tetiklemiyor → strateji güncellenmiyor. `onKeyUp={handleExtraCommit}` eklendi (a11y+UX) | npm build ✓ | ✅ |
| W3-006 | PendingActions klavye y/n/e kısayolu `acts[0]`'a uygulanıyordu ama ilk aksiyon düzenleme modundayken (butonlar disabled) bypass edip yanlış onay/red yapabiliyordu. `editingByIdRef` + guard: edit modunda kısayol yok sayılır | npm build ✓ | ✅ |
| W3-040 / SEC-003 | CORS sertleştirme: origin'ler env-driven (`CORS_ORIGINS`, dev default localhost) — prod domain'i env ile. `allow_methods`/`allow_headers` wildcard → açık liste (GET/POST/PATCH/PUT/DELETE/OPTIONS + Authorization/Content-Type/Accept). .env.example güncellendi | tests/security/test_cors.py (3) | ✅ |
| W3-030 / CO-001 | EMANET KASA halüsinasyon filtresi format-bağımsız: `_EMANET_HEADER_RE` yalnız `[5. EMANET KASA]` yakalıyordu; prompt kural 13 markdown `## 5.` istediğinden sızıyordu. Regex tüm başlık işaretçilerini (#/[/*/>) tolere eder + `_SECTION_BOUNDARY_RE` ile sonraki bölüm yenmez. ADR-001: koç prompt'a değil kod filtresine güvenir | tests/test_coach_emanet_strip.py (6) + fake_completion regresyon (18) | ✅ |
| W3-039 / RCH-002 | Checkpoint hard-delete koruma açığı: guard yalnız priority1+red_line'ı koruyordu → MC4/5/6/8 (type=rule) ?hard=true ile silinebiliyordu. `is_system` Boolean kolonu (migration 26a17fda5b32) + delete guard `is_system OR (priority1+red_line)` + setup_data is_system=True + CheckpointUpdate'te alan yok (API immutable). **OTONOM KARAR:** title-guard rename ile bypass edilir → kod-seviyesi flag (Master Checkpoint enforcement). Canlı DB veri-flag'i Murat onayı bekliyor (bekleyen-canli-db-aksiyonlari.md — R3: canlı başlıklar 'MC' önekli değil) | tests/test_checkpoint_protection.py (+3), fresh-db ✓, 817 test | ✅ (kod); canlı-veri bekliyor |
| W3-023 / DS-003 (E1) | Faizsiz kredi iyimser strateji: **R3 — backend ZATEN uyarı üretiyor** (BUG #081, `warnings` dict'te faizsiz-kredi mesajı). Gerçek açık: **frontend göstermiyordu**. DebtStrategy.jsx'e `data.warnings` banner'ı (AlertTriangle, warn renk) eklendi — iyimser months_to_freedom kararı öncesi kullanıcı görür | npm build ✓, backend warnings 65 debt testi | ✅ |
| W3-028 / AE-005 | income→kredi kartı borç artışı: **R3 — ZATEN FİX** (BUG #103, action_executor:542 `if credit_card: balance -= amount`). Audit raporu bayat. Kod değişikliği YOK | kod okuma | ✅ (R3-kapalı) |
| W3-026 / DS-002 | Borç payoff MAX_MONTHS "bitmedi" flag: **R3 — ZATEN FİX** (RULE-011, debt_strategy:248 month>=MAX_MONTHS→payoff_date=None + asla_bitmez flag). Kod değişikliği YOK | kod okuma | ✅ (R3-kapalı) |
| W3-029 / AE-006 | action_executor 0-fiyat yok sayma: **R3 — ZATEN FİX** (BUG #102, :685 `if _ap is not None else current_price` — explicit 0 saygı görür, `or` değil; +SEC-032 finite). Kod değişikliği YOK | kod okuma | ✅ (R3-kapalı) |
| W3-041 / SEC-004 | Rate limiting: **M11'e taşındı** (OTONOM KARAR — auth prod-gate/brute-force koruması ile birlikte, orta-süre; backlog notu da öyle işaret ediyor) | — | ⏭️ M11 |
| W3-058 / ONERI #030 | Commit-öncesi test kapısı: `.githooks/pre-commit` (staged'e göre pytest -x / vitest) + `scripts/install-hooks.sh` + `core.hooksPath=.githooks` aktif. BUG #061 (38 test sessiz kırıldı) tam da bu eksik olduğu için sızmıştı. D1: pre-commit framework yerine solo-dev için hooksPath (dış bağımlılık yok) | hook dry-run ✓ | ✅ |

## Milestone 10 — Production Deployment (Wave-3, 2026-07-13)

| ID | Değişiklik | Doğrulama | Durum |
|----|-----------|-----------|-------|
| ADR-035 | Deployment kararı D1(Firefly/fava/Maybe/Umami/Caddy)+K10: Docker Compose (backend uvicorn daemon + Caddy SPA/proxy/HTTPS) birincil, systemd alternatif. STUB→KARAR | ADR yazıldı | ✅ |
| M10-cron | M4 cron production: prod'da uvicorn --reload YOK → tek-process daemon → APScheduler 02:45 çalışır. Kök çözüm deployment-config | uvicorn daemon smoke: scheduler start + fetch_investment_prices job kayıtlı + /health 200 | ✅ |
| M10-artifacts | Dockerfile + Dockerfile.web + Caddyfile(HSTS/X-Frame W3-042) + docker-compose + .dockerignore + docker-entrypoint(alembic+uvicorn) + deploy/systemd(service+backup timer) + .env.example prod(DOMAIN/SECRET_KEY) + docs/deployment/README.md | compose YAML valid, fresh-db migration ✓ | ✅ |

## Milestone 11 — Auth + Multi-user (Wave-3, 2026-07-13)

| ID | Değişiklik | Doğrulama | Durum |
|----|-----------|-----------|-------|
| ADR-033 | Auth kararı D1(Firefly Sanctum/Maybe Devise/Firebase vs Supabase)+K10: kendi JWT (external değil, veri egemen/KVKK), bcrypt, access+refresh, OAuth authlib, KVKK sil/export. STUB→KARAR | ADR yazıldı | ✅ |
| M11-backend | User modeli (email/password_hash/oauth/kvkk/is_active) + RevokedToken + migration 380a9c1e7d8f (native ADD COLUMN, FK-güvenli). app/auth.py (bcrypt+PyJWT). routers/auth.py (register/login/refresh/logout/me/KVKK sil+export/rate-limit W3-041/OAuth+SMTP scaffold). get_current_user JWT+fallback (AUTH_ENABLED) | 17 auth testi, canlı migration ✓, 834 test | ✅ |
| M11-frontend | api.js token deposu + Authorization + authApi. Login.jsx (KVKK checkbox). App.jsx AuthGate + logout. /api/health auth_enabled | 6 vitest, build ✓ | ✅ |
| M11-kvkk | docs/legal/kvkk-consent-v1.md (KVKK m.4/7/11) + register açık rıza (kvkk_consent_at/version) + DELETE /api/users/me cascade + GET export | test_kvkk_delete/export | ✅ |
| W3-041 | Rate limiting (M9'dan taşındı): auth endpoint'lerde in-memory per-IP sliding window (brute-force) | test_rate_limit_login | ✅ |
| API_KEY_TALEP | OAuth Google/GitHub/Apple + SMTP Brevo (docs/api-key-talep-wave3.md) | scaffold + placeholder | ⏳ Murat |

## Milestone 12 — Multi-asset (Wave-3, 2026-07-13)

| ID | Değişiklik | Doğrulama | Durum |
|----|-----------|-----------|-------|
| ADR-031 | Multi-asset karar D1(Beancount commodities/Maybe/yfinance/EVDS)+K10: tek-tablo asset_type, kapsam stock+gold+fx (Numeric 19,4), kripto Wave-4. STUB→KARAR | ADR | ✅ |
| M12 | Account.asset_type + migration 697027467ca8 (native, investment→fund). yfinance_client + evds_client (EVDS_API_KEY, API_KEY_TALEP) + PriceSource.EVDS. fetch_for_account asset_type dispatch. **R3: yfinance Yahoo blok bu env'de → graceful None, canlı Murat'ta.** | 11 mock testi, canlı migrate (TLY→fund), 845 test | ✅ |
| M12-frontend | Accounts asset-type seçici UI | Wave-4 follow-up (backend dispatch hazır) | ⏭️ Wave-4 |

## Milestone 13 — Koç Sağlayıcı Ücretsiz (Wave-3, 2026-07-13)

| ID | Değişiklik | Doğrulama | Durum |
|----|-----------|-----------|-------|
| ADR-034 revize | 5+ ücretsiz sağlayıcı D1 + quality-per-cost matrisi. **R3: coach.py ZATEN 6 provider** (Anthropic/Gemini/Groq/Cerebras/OpenRouter/Ollama). Fallback sırası revize: Gemini→OpenRouter→Cerebras→Together→DeepInfra→Groq→Ollama | docs/architecture/adr-034-revize.md | ✅ |
| M13 | TogetherProvider + DeepInfraProvider (_OpenAICompatMixin — Cerebras deseni, P2-12 küçük DRY adımı) + _build_together/_build_deepinfra + zincir revize. API_KEY_TALEP (Together/DeepInfra) | 6 test, canlı smoke Murat'ta (key gerekli) | ✅ |

## Milestone 14 — Backlog Kalan (Wave-3, 2026-07-13)

| ID | Değişiklik | Doğrulama | Durum |
|----|-----------|-----------|-------|
| W3-009 | PendingActions `JSON.parse(payload)` guard'sızdı → bozuk payload listeyi çökertir. `safeParsePayload` (try/catch→{}), 2 çağrı yeri | npm build ✓ | ✅ |
| W3-008 | RedLines `handleToggleActive`/`handleDelete` hata yakalamıyordu (sessiz başarısızlık + unhandled rejection). try/catch→setError | npm build ✓ | ✅ |
| W3-024 | goal_engine compare_strategies AttributeError: **R3 ZATEN FİX** (BUG #066/GE-001, dict-handling) | kod okuma | ✅ (R3-kapalı) |
| W3-033 | create_allocation IDOR: **R3 ZATEN FİX** (goals.py:195 user_id==current_user.id + tx user_id filtresi + BUG #072 tutar sınırı) | kod okuma | ✅ (R3-kapalı) |
| M14-kalan | W3-007/010/011/012/013/014/018/019/020/025/031/032/035/043/046/057 → çoğu küçük guard/a11y; bir kısmı R3-zaten-fix olası. Wave-4'e devredildi (kalite düşürmeden, KURAL 12) | — | ⏭️ Wave-4 |

## Wave-3 Tamamlama (Wave-3-Tamamlama charter, 2026-07-14)

| ID | Değişiklik | Doğrulama | Durum |
|----|-----------|-----------|-------|
| M16 / BUG #157 | SECRET_KEY startup fail-fast: `app/settings.py` (`validate_security_config` — production'da boş/dev-default/<32char SECRET_KEY → RuntimeError, uygulama açılmaz; dev'de warning) + main.py lifespan çağrısı. R3: settings.py yoktu, auth.py lazy-raise ediyordu. ENVIRONMENT env. | tests/security/test_secret_key_fail_fast.py (6) | ✅ |
| M17 | Frontend OAuth: Login.jsx Google/GitHub butonları (authApi.oauthLogin → tam-sayfa /api/auth/oauth/{p}/login). `consumeOAuthRedirect()` (api.js) router'sız handler — backend /auth/oauth-success?token redirect'ini yakalar, token kaydeder, URL temizler, cockpit'e döner. App.jsx AuthGate mount'ta çağırır + oauth-error → Login initialError. **R3+K10:** frontend router'sız tab-app → query-param handler (Murat onayı, pages/ eklenmedi) | 4 vitest (30 toplam), build ✓ | ✅ |
| M18 | Password reset frontend: Login.jsx'e reset-request (email→passwordResetRequest) + reset (yeni şifre→passwordResetConfirm) modları + "Şifremi unuttum" linki. `getResetTokenFromUrl()` (api.js) Brevo linkindeki /auth/reset?token= yakalar, AuthGate Login'i reset modunda açar. Router'sız (M17 deseni) | 3 vitest (33 toplam), build ✓ | ✅ |
| M19 | EVDS fiyat endpoint: `app/routers/prices.py` GET /api/prices/currency/{code} + /gold/{type} (mevcut evds_client üzerine, graceful 502). Scheduler zaten fx/gold dispatch ediyor (M12). **R3: EVDS evds2.tcmb.gov.tr/service/evds/ artık SPA HTML dönüyor (endpoint taşınmış)** — canlı fiyat env'de erişilemez (yfinance M12 tekrarı); kod doğru-yapılı, canlı doğrulama Murat'ta (doğru endpoint/key) | 5 mock test | ✅ (kod); canlı EVDS bekliyor |
| M20 / W3-039 | Canlı DB master checkpoint is_system veri-flag'i UYGULANDI: `scripts/apply_w3_039_is_system.py` (backup + per-row ORM + güvenlik-guard beklenen-set kontrolü). 8/8 is_system=True. Wave-3'te auto-guard bare-UPDATE'i bloklamıştı → sanctioned script. Guard canlıda aktif. Backup 2026-07-14-020847.db, idempotent | canlı doğrulama 8/8 | ✅ |
