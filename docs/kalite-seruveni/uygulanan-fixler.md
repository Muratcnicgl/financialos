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
| M21 | Auth rate limit production değerleri: `app/rate_limit.py` per-bucket (login 5/15dk, register 3/saat, pwreset 3/saat, oauth 10/dk) + env override (RATE_LIMIT_<BUCKET>_MAX/WINDOW). M11 global limiter genişletildi (slowapi yerine, yeni dep yok). oauth_login'e de eklendi. auth.py alias korundu (test uyumu) | tests/security/test_rate_limit.py (6) + auth regresyon | ✅ |
| M22 | CORS whitelist: **R3 — W3-040/M9'da zaten env-driven** (CORS_ORIGINS, credentials=True, açık method/header, 3 test). Enhancement: `_compute_cors_origins` CORS_ORIGINS boşsa dev-default + FRONTEND_URL birleştirir (prod tek-var kolaylığı) | 6 CORS testi | ✅ |
| M23 | Log rotation: `app/logging_config.py` (console + RotatingFileHandler logs/financialos.log 10MB×5, prod JSON/dev text, fail-safe console). main.py basicConfig → setup_logging. logs/.gitignore. Env: LOG_DIR/LOG_ROTATION_MAX_MB/BACKUP | tests/test_logging_config.py (3), 891 test | ✅ |
| M24 | MCP memory auto-sync: `.githooks/post-commit` (commit'i `.mcp-sync-pending.log`'a yakalar) + `scripts/mcp_sync_report.py` (flush okuma) + `docs/kalite-seruveni/memory-auto-sync.md`. **R3: hook MCP'ye DOĞRUDAN yazamaz (shell, MCP Claude-aracı)** → capture(otomatik)→flush(Claude) deseni. "graph bayat kalır" (Wave-3 dersi) yarı-otomatik çözüldü | post-commit ledger canlı | ✅ |
| M25 | Bug Archive kanıtlama turu: disk kanıt indeksi (commit/fixler/test/docstring) 141 bug (#1-157). 44 KANITLI (çok-kaynak) + 52 test-korumalı + 51 İDDİA (erken #1-55, docstring/commit var test yok). **Yeniden-açık: 0.** Rapor bug-archive-audit-14tem.md | R3 disk-indeks | ✅ |
| M26 | Sections kapatma turu: R3 sections prose-format, P0/P1 zaten kapalı. Spot-check kritik boyutlar. **2 otonom milestone:** M34 (SEC-015 /docs prod kapalı), M35 (FE-032/PERF-020 sourcemap kapalı). Gerçek açık P0/P1: 0. Rapor faz-4-durum.md | R3 spot-check | ✅ |
| M34 / SEC-015 | /docs+/redoc+/openapi.json production'da kapalı (is_production gate), dev'de açık. Bilgi ifşası önlendi | tests/security/test_docs_gating.py (2) | ✅ |
| M35 / FE-032,PERF-020 | vite.config sourcemap:true→false — prod build kaynak sızıntısı önlendi | dist .map yok doğrulandı | ✅ |
| M27 | Test coverage: TOTAL %86→%87, 897 test. startup.py 0→**%100** (4 test, catch_up_snapshots 4 dal). Çekirdek motorlar zaten >%80. Rapor tests/README.md (router/external düşük-kapsam hedef listesi) | coverage ölçüldü | ✅ |
| M28 | Frontend anti-pattern denetimi: 40 dosya R3. **Temiz** — doğrudan fetch 0 (api.js disiplini), parseFloat yalnız backend-değer, dinamik Tailwind safelist'li, kritik async-error M9/M14'te kapalı. Küçük (index-key 23, a11y) → Wave-4. Kritik anti-pattern: 0. Rapor frontend-audit-14tem.md | R3 tarama | ✅ |
| M29 | Improvement Backlog kapatma turu: ~188 obs, disk kanıtı (22 FEAT + Wave-3 milestone). ~15+ ONERI KAPANDI (#002/004/005/006/008/019/020/021/028/030 + FEAT dalgası). Açık kalanlar feature-fikri (#007/009/010/011/014/016/017/018/029) → Wave-4, kritik yok. Rapor improvement-backlog-audit-14tem.md | R3 disk-indeks | ✅ |
| M30 | Documentation turu: docs/contributing.md (dev kurulum + ADR kuralları + PR), docs/faq.md (KVKK/gizlilik/TR bağlam), docs/user-guide/README.md (paneller + akışlar), docs/api-reference/README.md (endpoint grupları + openapi). README.md mevcut (164 satır) | dosyalar oluşturuldu | ✅ |
| M31 | TR number locale denetimi: parseTRNumber 20 (text-input W3-001), Number() yalnız number/range-input (tarayıcı "." → doğru), parseFloat yalnız backend-değer, formatTL 19 dosya. Edge-case'ler W3-001 testli. 3 raw toLocaleString display-tutarlılık (Wave-4). Kritik TR-locale bug: 0. Rapor tr-locale-audit.md | R3 tarama | ✅ |
| M32 | Wave-4 skeleton detay: BUG #157 kapandı-işaretlendi (M16), mobil (ADR-032)/aile hesabı/kripto Numeric(28,8)/PostgreSQL+RLS/OHVPS/Sentry/design-system detaylandı. **Google OAuth "External Test" 100-limit + unverified uyarısı BUG olarak eklendi** (Wave-4 publish/doğrulama). Kalan küçük Wave-4 listesi | wave-4-skeleton.md (112 satır) | ✅ |
| M33 | Wave-3-Tamamlama kapanış: 20 milestone (18 planlı M16-M32 + 2 otonom M34/M35), 897 backend + 33 vitest, TOTAL %87. Durma kriteri KARŞILANDI: kapatılabilir kritik/orta açık iş 0. PROJE.md baseline + milestone-log kapanış tablosu | git senkron | ✅ GOAL TAMAM |

## M19-v3 EVDS Regression Fix (2026-07-14)

| ID | Değişiklik | Doğrulama | Durum |
|----|-----------|-----------|-------|
| M19-v3 / EVDS regression | EVDS v2→v3 geçişi: evds_client.py base `evds3.tcmb.gov.tr/igmevdsms-dis`, series PATH'e gömülü, header `{"key":...}` auth. fetch_series/fetch_currency_rate(buy+sell)/fetch_gold_price + get_evds_price compat. prices.py buy/sell response + date param. Scheduler otomatik v3 (get_evds_price). ADR-029 revize. **CANLI: USD 46.9121/46.9966 (14 Tem) 200 ✓.** R3: altın TP.MK.F.BILESIK.TUM bileşik-endeks (gram değil, Wave-4) | 7 endpoint testi + canlı curl 200 | ✅ |

## P1 — Çok-Kullanıcı İzolasyon Denetimi (Wave-9 publish yolu, 2026-08-04)

| ID | Değişiklik | Doğrulama | Durum |
|----|-----------|-----------|-------|
| BUG #162 | **ÇAPRAZ-KULLANICI SIZINTISI (kritik).** `app/goal_rules.evaluate_rules_for_transaction` TÜM kullanıcıların/workspace'lerin aktif `GoalRule`'larını çekip tek kullanıcının işlemine uyguluyordu → A'nın işlemi B'nin hedefine `GoalAllocation` yazıyor, B kendi allocation listesinde A'nın tutarını + `transaction_id`'sini görüyordu. Canlı yol (`transactions.py:368`, her işlem oluşturmada). Fix: kurallar `Goal` join + `scope_filter(Goal, tx.user_id, tx.workspace_id)` ile işlemin sahibine kapsanır (ADR-036: aynı workspace'teki üyenin kuralı geçerli kalır) | TDD: `tests/test_goal_rules.py::test_15/16` kırmızıydı → yeşil; `test_17` pozitif kontrol (aile üyesi kuralı çalışmaya devam ediyor) | ✅ |
| P1-gate | **Statik kapı genişletildi.** `tests/test_scope_enforcement.py` yalnız scope'suz `user_id ==` yakalıyordu; **filtresiz sorgu** (BUG #162'nin şekli) kör noktaydı. AST tabanlı yeni kapı `app/` ağacının tamamını tarar; her sahipli-model sorgusu ya kapsamlı ya `# scope-exempt: <gerekçe>` işaretli olmalı. 12 ihlal triyaj edildi: 2 gerçek sertleştirme (action_executor recurring, coach history PendingAction), 10 gerekçeli exempt | 6 test yeşil; **3 meta-test** kapının BUG #162 desenini gerçekten yakaladığını ispatlar (hep-yeşil kapı riski kapandı) | ✅ |
| P1-matris | **Runtime çapraz-kullanıcı matrisi.** `tests/test_cross_user_isolation.py`: A kaynak yaratır, B aynı id ile okur/yazar/siler → 403/404 beklenir (7 kaynak ailesi, 17 test). Liste uçlarında sızıntı yok; B, A'nın hesabına işlem yazamıyor; `X-Workspace-Id` ile workspace ele geçirme 403. **Kapsam kilidi:** yeni `/{id}` endpoint'i matrise veya gerekçeli `MATRIS_DISI`'na yazılmazsa test kırılır (kapsam kendiliğinden daralamaz) | 17 test yeşil | ✅ |
| BUG #163 | **Çok-kullanıcı doğruluk defekti.** `scripts/backfill_net_worth.run_backfill` + `app/startup.catch_up_snapshots` yalnız İLK kullanıcıyı işliyordu (tek-kullanıcı kalıntısı) → 2. kullanıcıdan itibaren net-değer geçmişi hiç dolmuyor, trend/atıf raporları sessizce eksik kalıyordu. Ayrıca yazılan satırlarda `workspace_id` NULL kalıyor, workspace kapsamlı okumalar geçmişi göremiyordu. Fix: tüm kullanıcılar döngüsü (`user_id` opsiyonel filtre) + personal workspace bağlama | TDD: `tests/test_backfill_multiuser.py` 3 test kırmızıydı → yeşil | ✅ |
| BUG #164 | **Yıkıcı script footgun'ı (kritik).** `scripts/cleanup_orphan_traces.py` "gerçek kullanıcı = adı 'test' ile başlamayan" sezgisiyle kalan HERKESİ siliyordu (FK'lar PRAGMA ile kapalı). Kapalı betada adı "Test..." olan gerçek kullanıcının tüm finansal verisi + hesabı geri dönüşsüz silinirdi. Fix: isim sezgisi KALDIRILDI; `--keep-user-ids` + `--delete-user-ids` zorunlu, keep id'leri DB'de doğrulanır, kesişim reddedilir, production'da `--force-production` şartı | `tests/test_cleanup_script_guards.py` 6 test (5 kilit + 1 pozitif kontrol) yeşil | ✅ |
| BUG #165 | **Workspace kapsam tutarsızlığı.** `app/cashflow.generate_forecast` `workspace_scope` bloğu içinden çağrılmasına rağmen ham `user_id` filtreliyordu → paylaşımlı (aile) workspace görünümünde nakit krizi / güvenli-harcama rakamları kişisel veriden hesaplanıyor, workspace'in kendi kalemleri hiç sayılmıyordu. Fix: 5 sorgu `rules_engine._scope` köprüsüne geçti (kapsam yoksa legacy user_id korunur) | TDD: `tests/test_cashflow_workspace_scope.py` 3 kırmızı → yeşil; mevcut 26 cashflow testi regresyonsuz | ✅ |

## P5 / P8 — Dayanıklılık + eşzamanlılık (publish yolu, 2026-08-05)

| ID | Değişiklik | Doğrulama | Durum |
|----|-----------|-----------|-------|
| BUG #211 | **H16 — döviz kesintisinde ürün susuyordu.** `fx_live.get_live_fx` üç hata yolunda da `None` dönüyordu: 31 dk önce başarıyla çekilmiş kur elde dururken koç "çekemedim, bankana bak" diyordu. Ücretsiz sağlayıcının birkaç saatlik kesintisi rutin → o süre boyunca kur özelliği tümüyle ölü. Diğer uç (bayat değeri sessizce "şu anki kur" diye sunmak) daha kötü olurdu. Fix: son BAŞARILI değer `bayat=True` + `yas_dakika` ile döner, `_BAYAT_TAVAN_DK=12s` üstü hiç dönmez; `app/coach._maybe_market_block` bayat dalında "SON BİLİNEN KUR (BAYAT: X saat Y dakika önce)" der ve "ŞU ANKİ GÜNCEL KUR" ifadesini KULLANMAZ. Fon/hisse tarafı zaten `fund_tracker.is_stale` → Cockpit "N eski" ile işaretliydi (doğrulandı) | `tests/test_fx_bayat.py` 8 test: taze≠bayat, kesintide yaş doğru, bozuk yanıt da düşer, 12s üstü None, cache kirlenmiyor, koç dili iki yönde kilitli | ✅ |
| BUG #212 | **H17 — eşzamanlı koç kullanımı iki defekt.** (a) *Kota yarışı:* akış "sayacı OKU → LLM çağır (saniyeler) → sayacı YAZ" idi; sayaç ancak çağrı bitince arttığı için aynı anda gelen N istek aynı eski sayıyı okuyup hepsi geçiyordu — hakkı 1 kalan kullanıcı paralel istekle tavanı deliyordu (BUG #188'in maliyet tavanı fiilen iptal, açık betada fatura riski). Fix: **rezervasyon deseni** (`_kota_rezerve_et`) — satır çağrı ÖNCESİ yazılır, id sırası tavanı aşarsa satır silinip 429 döner; `_rezervasyonu_tamamla` sonucu aynı satıra işler (reddedilen istek sayacı kirletmez). (b) *Muhasebe etiketi:* `engine.provider_name`, `FallbackProvider`'ın **paylaşılan** `last_used_provider` alanını okuyordu → ilk başarılı çağrıdan sonra etiket `fallback(gemini)` oluyor, bu ad `PROVIDER_DAILY_LIMITS`'te YOK → günlük sağlayıcı kotası koruması sessizce ölüyordu; ayrıca etiket eşzamanlı BAŞKA kullanıcının çağrısına göre değişiyordu. Fix: `_muhasebe_saglayici_adi` etiketi yapılandırmadan türetir | `tests/test_coach_eszamanlilik.py` 5 test (3 gerçek paralel thread). **Eski kodla ölçüldü:** `[200, 200, 200]` + tavan 3 iken 5 satır → yeni kodda `[200, 429, 429]` + 3 satır | ✅ |
| BUG #213 | **H22 — güvenlik sınırı tek katmanda yaşıyordu.** İstek gövdesi sınırı YALNIZ `deploy/nginx.conf.template` içindeki `client_max_body_size 1m` idi. Üç boşluk: (1) uygulamaya ters vekil ATLANARAK erişilirse (docker ağı, nginx'siz kurulum, yerel çalıştırma) koruma yok, (2) nginx yapılandırması sessizce değişirse bunu yakalayan test YOKTU, (3) chunked transfer-encoding'de `Content-Length` hiç gelmez — boyut ancak akarken sayılarak bilinir. Fix: `app/request_limits.GovdeBoyutuMiddleware` (saf ASGI — BaseHTTPMiddleware gövdeyi tamponlar) `Content-Length` yolunda gövdeyi HİÇ okumadan 413 döner, başlık yoksa akan baytları sayıp sınırda keser; `MAX_REQUEST_BODY_BYTES` geçersiz/0/negatifse SESSİZCE sınırsıza kaçmaz, 1 MiB'e düşer; 413 `beklenen reddetme` olarak işlenir (hata-izleme tablosuna 500 olarak düşmez) | `tests/test_govde_limiti.py` 14 test. **Koruma kaldırılarak ölçüldü:** chunked testi + "uygulamada kurulu" testi + "413 hata izlemeye düşmez" testi (413 yerine 422) kırmızıya döndü. Ayrıca nginx şablonu drift kilidi + `scripts/live_gate.py` canlı kapısı (2 MiB → 413) | ✅ |
| BUG #214 | **H23 — betanın kullanılıp kullanılmadığı ÖLÇÜLEMİYORDU.** Operatörün elindeki tek araç `beta_triage` idi ve o yalnız **şikâyet edeni** gösterir. Beta'nın en olası başarısızlığı gürültülü çöküş değil SESSİZ TERK'tir: davet edilir, kayıt olur, ilk ekranda takılır, kimse şikâyet etmez — panelde her şey yeşil görünür, ürün ölüdür. P8'in çıkış ölçütü ("gerçek kullanıcı davranışıyla sınanmış operasyon") bu yüzden ölçülemezdi. Fix: `scripts/beta_metrics.py` — onboarding hunisi (kayıt→hesap→işlem→koç→kural), hiç iz bırakmayan sayısı, tutunma (kayıt gününden BAŞKA bir gün dönen), koç hata oranı/süre, açık geri bildirim + hata grubu. Aktiflik üç sinyalin BİRLEŞİMİ ile gün bazında sayılır (tek kişinin yoğun günü 'çok kullanıcı' gibi görünmez). Şema değişikliği gerekmedi (`last_login` sütunu eklenmedi — giriş yapıp hiçbir şey yapmamak zaten kullanım değil) | `tests/test_beta_metrics.py` 10 test. **Gizlilik kod seviyesinde kilitli:** çıktıda e-posta, isim, serbest metin ve para tutarı bulunması testle YASAK; JSON ağacının her yaprağı sayı olmak zorunda. Dış analitik servisi yok — veri makineden çıkmaz (BUG #195 ile aynı çizgi) | ✅ |

## P3.2 — Boş-durum + hata-durumu arayüz kapısı (publish yolu, 2026-08-05)

| ID | Değişiklik | Doğrulama | Durum |
|----|-----------|-----------|-------|
| BUG #217 | **KAPSAM SESSİZCE ÇÖKMÜŞ — iki kapı fiilen ÖLÜYDÜ.** Hem `test_sifirdan_kullanici_e2e` ("parametresiz her GET ucu boş-durumda çağrılır") hem `test_cross_user_isolation::test_id_alan_endpointler_matriste_kapsanir` ("her `/{id}` ucu izolasyon matrisinde olmalı") kapsamı `app.routes` üzerinden türetiyordu. **FastAPI 0.141** `include_router`'ı düzleştirmeyi bıraktı (`_IncludedRouter` sarmalayıcısı, `path`/`routes` boş) → 87 yoldan **1'i** (`/api/health`) taranıyordu; izolasyon kapısında ise liste **boş** kaldığı için kapı hiçbir şey ölçmüyordu. Her iki test de YEŞİL'di. Fix: envanter `tests/endpoint_envanteri.py` içinde **OpenAPI**'den türetiliyor (FastAPI'nin kararlı kamu sözleşmesi) + **kapsam TABANI** assert ediliyor (parametresiz GET ≥ 25, parametreli ≥ 25) → aynı çöküş bir daha sessiz olamaz | Kapı açılınca: boş-durum taraması 1 → **36 uç**; izolasyon kapısı ilk kez gerçek bulgu verdi (`/api/legal/{slug}` matris dışıydı — gerekçeli istisnaya eklendi). Backend süiti 1606 → **1608 passed** | ✅ |
| BUG #218 | **TEK BİR HATALI İSTEK → SONSUZ İSTEK DÖNGÜSÜ (canlıyı etkiler).** `ToastProvider` context değerini (`api` nesnesi) HER RENDER'da yeniden yaratıyordu. Zincir: istek patlar → `toast.error()` → `setToasts` → provider re-render → `toast` KİMLİĞİ değişir → `useCallback(..., [toast])` yenilenir → ona bağlı `useEffect` TEKRAR koşar → istek yine patlar → … Tetikleyici bol: bayat workspace seçimi (403 — BUG #162 senaryosu), backend kapalı, oturum düşmüş, uç 404. **Ölçüldü:** Aile paneli 150 ms'de **54 istek**, durmuyor (kullanıcı sekmeyi açık bıraktıkça backend'e kesintisiz yağmur; kendi rate-limit'ine takılır, mobilde pil/veri yakar). Fix: context değeri `useMemo([show, dismiss])` ile sabitlendi (ikisi de zaten kararlı `useCallback`) | `frontend/src/error-state.test.jsx` — 13 panelin tamamı hata yolunda taranır. **Eski kodla ölçüldü:** 54 istek → düzeltmeden sonra **2**. Ayrı bir kök-neden kilidi toast kimliğinin render'lar arasında sabit kaldığını sınar (yeni panel aynı tuzağa düşemez) | ✅ |
| BUG #219 | **Bütçe paneli backend hata verince ÇÖKÜYORDU.** `load()` hatayı yalnız toast'a düşürüyor, `data` `null` kalıyordu; render `data.envelopes.length` okuyunca panel çöküyordu (ErrorBoundary devreye girer → "Bu panel yüklenemedi"). Aynı dosyada `data?.durum` / `data?.atanmamis_nakit` guard'lıydı — tutarsızlık bug'ın kendisiydi. Ayrıca toast 4 sn sonra kaybolur, geriye SEBEPSİZ kırık ekran kalırdı. Fix: hata artık state'te tutulur, ekranda **kalıcı** hata kartı + "Tekrar dene" gösterilir (yükleme başarısızken kullanıcıya "zarfın yok" DENMEZ — veriyi bilmiyoruz), liste `data?.envelopes || []` üzerinden okunur | Panel sweep testi. **Mutasyon kontrolü:** fix `git checkout` ile geri alındı → `Bütçe paneli hata yolunda çökmez` KIRMIZI, geri konunca yeşil. Ayrıca tespit mekanizmasının kendisi ayrı bir sahte-panelle doğrulandı | ✅ |
| BUG #220 | **Zamana bağlı gizli flaky test.** `test_farkli_saat_dilimi_farkli_gun_verebilir` UTC+14 (Kiritimati) ile UTC-11 (Midway) arasındaki takvim farkını `in (0, 1)` sanıyordu. İki bölge **25 saat** ayrı: UTC günü 10:00-10:59 penceresindeyken fark **2 gün** olur → test günün ~1/24'ünde kırmızı. Üretim kodu (`user_today`) doğru, iddia yanlıştı; M90 "flaky yok" ölçümü bu pencereye denk gelmemişti. Fix: sınır `in (0, 1, 2)` + gerekçe yorumu | Tam süit 13:25 TSİ'de (10:25 UTC) kırmızıydı → yeşil; 1608 passed | ✅ |
| P3.2-fixture | **Frontend boş-durum testi TAHMİN mock'la değil, GERÇEK sözleşmeyle koşuyor.** `tests/test_bos_durum_frontend_fixture.py` gerçek kayıt akışıyla boş kullanıcı yaratıp 36 ucun gövdesini `frontend/src/__fixtures__/bos-kullanici.json`'a döker; vitest tarafı bunu servis eder. **Sözleşme kayması kapısı:** diskteki fixture'ın YAPISI (anahtar+tip iskeleti; oynak değerler değil) canlı cevapla karşılaştırılır — backend alan ekler/siler/tipini değiştirirse test kırılır, frontend testi sessizce bayatlayamaz. Kullanıcının kendi personal workspace'i de dökülür (yoksa Aile paneli testi boş-durumu değil HATA yolunu ölçerdi — yanıltıcı yeşil) | `empty-state.test.jsx` 27 test (13 panel × çökme + ham-JS-artığı sızıntısı) + fixture kapsam kilidi. Frontend süiti 71 → **125 passed** | ✅ |

## P1 — Doğrulama denetiminden çıkan kritik defekt (2026-08-05)

| ID | Değişiklik | Doğrulama | Durum |
|----|-----------|-----------|-------|
| BUG #221 | **KRİTİK — koç-onaylı kayıt kullanıcının KENDİ listesinden kayboluyordu.** `execute_pending_action` handler'ları `(db, user_id, payload)` imzasıyla çağırıyordu; **workspace bağlamı hiç geçmiyordu** → `Transaction` ve `MasterCheckpoint` satırları `workspace_id=NULL` yazılıyordu. Okuma tarafı workspace kapsamlı (`scope_filter`) ve production'da personal workspace ZORUNLU (`workspace_deps.active_workspace_id` prod'da fail-fast) olduğu için NULL satır kullanıcının kendi listesinden/raporundan/koç bağlamından eleniyordu. Kullanıcı açısından: koça "500 TL market harcadım" → onayla → **bakiye düşüyor ama işlem hiçbir yerde görünmüyor** (para buharlaşmış gibi; kategori bütçesi, reel bütçe, abonelik tespiti, nakit-akış tahmini hepsi eksik hesaplıyor). Ürünün amiral akışı bu. **3. kol:** `app/premortem.py` `DecisionJournal` de `workspace_id` yazmıyordu — `decision_journal` RLS listesinde (`alembic/versions/f5a6b7c8d9e0`), yani prod PostgreSQL'de satır INSERT edilir (policy USING-only, WITH CHECK yok) ama sonra GÖRÜNMEZ. Fix: handler çağrısı `workspace_scope(pending.workspace_id)` içine alındı (yazma + handler içindeki `rules_engine` okumaları aynı kapsamda) + `_yazma_workspace_id()` çözümleyicisi (aktif kapsam → kaynağın/hesabın workspace'i → kullanıcının personal workspace'i → None=legacy, davranış değişmez) | `tests/test_action_executor_workspace.py` 5 test (bakiye düştü→işlem görünür, ws taşınır, kırmızı çizgi panelde, workspace'siz eski aksiyon hesabın ws'ine düşer, legacy kurulumda davranış değişmez). **Kaynak:** doğrulama denetimi D01 (kritik) + D02; canlı DB'de ZATEN gerçekleşmişti (`transactions` tek satır ws=NULL, tüm hesaplar ws=1) | ✅ |
| #221-kapı | **Statik kapı: workspace'li modele `workspace_id` yazmadan kayıt açılamaz.** Mevcut kapı (`test_scope_enforcement`) yalnız SORGULARI denetliyordu (denetim bulgusu D31) — oysa #221'in şekli YAZMA idi. Yeni kapı `app/` ağacındaki her `Model(...)` çağrısını AST ile tarar; model listesi `models.py`'den türetilir (elle liste yok), muafiyet `# ws-exempt: <gerekçe>` ile gerekçelenir. L11 gereği kapsam tabanı assert edilir | `tests/test_workspace_insert_kapisi.py` 3 test. **Mutasyon kontrolü:** `workspace_id` satırı silininde kapı kırmızıya döndü. Kapı açılınca aynı sınıftan **3. bir yer** bulundu (premortem `DecisionJournal`) ve o da kapatıldı | ✅ |
| BUG #222 | **CANLI ŞEMA KODUN 9 MIGRATION GERİSİNDEYDİ — uygulama sessizce yarım çalışıyordu.** `data/financialos.db` `a1b2c3d4e5f6`'da kalmıştı, kod `e1f2a3b4c5d6` bekliyordu. Eksikler: `users.token_version` (#172), `rate_limit_hits` (#182), **`master_checkpoints.rule_type/rule_params` (#192)**, `demo_data_markers` (#194), `error_logs` (#195), `users.timezone/currency/locale` (#197), `beta_invites` (#199), `users.email_verified_at` (#202), `scheduler_runs` (#203). Etki: `enforce_user_rules` her aksiyon onayında `rule_type`'ı sorguluyor → **koç yolundan yapılan HER onay 500 veriyordu**; rate-limit/hata-izleme/davet/e-posta-doğrulama/cron-görünürlüğü de canlıda fiilen yoktu. Uygulama yine de açılıyor ve `/api/health` yeşil dönüyordu. Kök boşluk: ADR-013 "şema yalnız Alembic" doğru kararıydı ama "migration'ı çalıştırmayı unutma" adımını hiçbir kapı denetlemiyordu (L8: belgelenen ≠ uygulanan). Fix: `app/schema_guard.validate_schema_version` startup'ta (lifespan) sürümü doğrular — production'da **fail-fast**, dev'de gürültülü uyarı, `alembic_version` tablosu yoksa (test/`create_all` yolu) sessiz geçer (L6: geliştirmeyi kilitleme) | `tests/test_schema_guard.py` 5 test. Sözleşme **dönüş değeriyle** sınanır (`guncel`/`atlandi`/`uyumsuz`) — ilk sürüm log'a dayanıyordu ve tam süitte `basicConfig(force=True)` handler'ları değiştirince KÖR kalıyordu; kapının kendi kör noktası kapatıldı (L3). Prod dalı gerçek geride-kalmış sürümle (`a1b2c3d4e5f6`) sınanıyor | ✅ |
| Canlı iş | **Canlı DB onarıldı + şema head'e yükseltildi (Murat onayıyla, 5 Ağu).** Sıra: yedek (`2026-08-05-141912.db`) → `repair_null_workspace --uygula` (2 satır: 4 Ağu 2310 TL 'sigara' işlemi + 1 net-değer anlık görüntüsü) → yedek (`2026-08-05-142714.db`) → `alembic upgrade head` (9 migration) → doğrulama: **hiçbir satır kaybolmadı, bakiyeler değişmedi**, `rule_type` kolonu geldi. Ardından kullanıcının bildirdiği 5 Ağu 300 TL yemek harcaması uygulamanın KENDİ akışıyla (propose → execute) Enpara Nakit'e yazıldı — bu aynı zamanda #221 düzeltmesinin canlı doğrulamasıdır: iki işlem de workspace kapsamlı okumada görünüyor, bakiye 2.263,52 → 1.963,52 TL | Salt-okur doğrulama: `scope_filter(Transaction, 1, 1)` → 2 işlem görünür (öncesinde 0) | ✅ |
| #221-onarım | **Canlı veri onarım aracı** — `scripts/repair_null_workspace.py`. Kod düzeltildi ama ZATEN oluşmuş NULL satırlar duruyor. Araç varsayılan **salt-rapor**; sezgi YOK (her satır yalnız kendi `user_id`'sinin **tek** personal workspace'ine bağlanır, belirsizse dokunulmaz), dolu `workspace_id`'ye asla dokunmaz, silme yok, yazma öncesi yedek alır (BUG #164 footgun dersi) | Rapor modu koşuldu: **2 satır onarılabilir** (4 Ağu tarihli 2310 TL 'sigara' işlemi + 1 net-değer anlık görüntüsü), 0 satır atlanır. **Uygulama İNSAN-KAPISI — Murat onayı bekliyor** | ⏸️ |

| BUG #223 | **`/api/cashflow/forecast` + `/api/debt-strategy/*` workspace bağlamını hiç kurmuyordu (denetim D03).** BUG #165 motor katmanını düzeltmişti (`app/cashflow.py`, `app/debt_strategy.py` → `_scope` köprüsü), ama HTTP uçları `workspace_scope(ws_id)` bloğuna hiç girmiyordu; contextvar boş kaldığı için köprü HER ZAMAN legacy `user_id` dalına düşüyordu. Aile workspace'i seçiliyken **aynı ekranda çelişen rakamlar**: cockpit "0 TL borç / 50.000 nakit" derken debt-strategy KİŞİSEL iki borcu listeliyor, cashflow açılışı 60.000 (kişisel+aile toplanmış) diyordu. Daha ağırı: snowball/avalanche, konsolidasyon ve fırsat-maliyeti simülasyonları **yanlış borç kümesi** üzerinde koşuyordu (paylaşımlı workspace'te eş kullanıcı gerçek ortak borcu hiç görmüyor, kendi kişisel kartını görüyordu) → hatalı borç-kapatma kararı. İkinci kol: bu uçlar **üyelik doğrulaması da yapmıyordu** (üye olunmayan `X-Workspace-Id` ile 200; cockpit doğru şekilde 403). Fix: 4 uca `ws_id: Optional[int] = Depends(active_workspace_id)` + gövde `with workspace_scope(ws_id):` (cockpit ile aynı desen; üyelik doğrulaması dependency'den bedava gelir). **L11 dersi:** motorda kanıtlanmış kapsam, uçta bağlanmamışsa YOKTUR — mevcut `tests/test_cashflow_workspace_scope.py` `generate_forecast`'i doğrudan `with workspace_scope(...)` içinde çağırdığı için ucun kör olduğunu göremiyordu | `tests/test_cashflow_debt_endpoint_workspace_scope.py` **12 test** (HTTP seviyesinde: aile bağlamı, başlıksız=kişisel, gelir sızıntısı, 4 uçta üye-olmayan→403, konsolidasyon toplamı, fırsat-maliyeti hedefi, ikinci kullanıcı ortak borcu görür). Düzeltme öncesi **12'si de kırmızıydı** (denetim kanıtı birebir üretildi) | ✅ |

| BUG #224 | **Premortem + simülasyon uçları da workspace bağlamı kurmuyordu (D03b — #223'ün SINIF taramasında bulundu).** `POST /api/premortem/{id}` → `build_cockpit_snapshot` → `generate_cockpit` ve `POST /api/simulate/{id}` → `simulate_action` → `_load_world`. Aile workspace'i seçiliyken bir aksiyonun **ön-ölüm risk analizi ve 3-ufuklu etki simülasyonu KİŞİSEL manzara üzerinde** koşuyordu → kullanıcı ekrandaki aile rakamlarıyla çelişen bir analiz okuyup ona göre karar veriyordu; premortem'de bu bağlam ayrıca LLM'e gidiyordu. **Motor katmanı ayrı bir sorun:** `simulation_engine` hiç workspace-farkında değildi (3 sorgu da ham `Model.user_id == user_id`) çünkü tasarım gereği `rules_engine`'i import etmiyor (bağımsızlık ilkesi) ve köprü orada tanımlıydı → köprüye erişemiyordu. Fix: köprü (`contextvar` + `workspace_scope` + `scope_expr`) **yaprak modül `app/scope.py`'ye taşındı**; `rules_engine` geriye-uyum re-export'u yapar (mevcut ~20 import yeri değişmedi, tek contextvar), `simulation_engine` katman ihlali olmadan aynı köprüyü kullanır. İki uca `Depends(active_workspace_id)` + `with workspace_scope(ws_id):` eklendi (üyelik doğrulaması dependency'den geldi) | `tests/test_premortem_simulation_workspace_scope.py` **7 test** (sim aile bağlamı baseline+T+0, başlıksız=kişisel & aile hesabı kişisel bağlamda BULUNAMAZ, 403 × 2, premortem'e giden snapshot'ın nakdi, motor köprüsü + legacy regresyonu). Düzeltme öncesi 7'si de kırmızıydı. **Mutasyon kontrolü:** `scope_expr` ham `user_id`'ye çevrilince 3 test kırmızıya döndü | ✅ |

| BUG #225 | **Şifre sıfırlama bağlantısı, kullanıcı şifresini değiştirdikten SONRA hâlâ geçerliydi — hesap geri alınamıyordu (denetim D04, BUG #172 ailesinin açık kolu).** Posta kutusuna geçici erişen biri (paylaşılan bilgisayar, iletilmiş sıfırlama postası, ele geçirilmiş e-posta) bağlantıyı alıp BEKLETEBİLİYORDU. Kullanıcının doğru refleksi olan "hemen şifremi değiştireyim" saldırganın elindeki bağlantıyı ÖLDÜRMÜYORDU: saldırgan 30 dk içinde şifreyi tekrar değiştirip hesabı kalıcı ele geçiriyor, sahibini dışarıda bırakıyordu (denetimin PoC'sinde kurban 401, saldırgan 200). Hesabın içinde tüm bakiyeler, borçlar, işlem geçmişi, KVKK export'u ve `DELETE /api/users/me` var. Uygulama üstüne "Güvenlik için tüm oturumlar kapatıldı" diyerek yanlış güvenlik hissi veriyordu. **Çift kök neden:** (1) `password_reset_confirm` `token_version_ok(...)` çağırmıyordu; (2) `create_password_reset_token` `token_version`'ı hiç geçirmiyordu → payload `tv` daima 0, yani (1) tek başına eklense bile kapı SESSİZCE etkisiz kalırdı. İkinci senaryo aynı kökten: arka arkaya iki "şifremi unuttum" → iki bağlantı da 30 dk aynı anda canlı, birinin kullanılması diğerini öldürmüyordu. Fix: token `tv` taşır + confirm doğrular; sayacı artıran her olay bekleyen bağlantıları öldürür | `tests/auth/test_pwreset_token_gecerliligi.py` **5 test**: denetimin PoC'si (kurban içeride/saldırgan dışarıda ispatlı), iki-canlı-bağlantı senaryosu, **meşru akış bozulmadı** (L6), tek-kullanımlık regresyonu (#172), `tv` claim'i gerçekten taşınıyor (bu olmadan diğer kapılar kör kalır — L3). Düzeltme öncesi 3'ü kırmızıydı. **Sınıf taraması (L11):** `email_verify` / `oauth_exchange` / `email_change` token'ları da bakıldı — hesap-ele-geçirme sınıfında değiller | ✅ |

| BUG #226 | **OAuth callback kapalı-beta davet kapısını TAMAMEN atlıyordu (denetim D05).** `invite_required()` yalnız `POST /api/auth/register` içinde çağrılıyordu; OAuth yapılandırılmış bir canlıda alan adını bilen herkes Google/GitHub ile tek tıkla hesap açabiliyordu — **aynı e-posta `/register`'da 403 alırken**. Denetimin PoC'si zincirin sonuna kadar gitti: kullanıcı yaratılıyor, `oauth/exchange` 200, `/auth/me` 200 (tam kullanılabilir oturum). BUG #199'un tüm gerekçesi "kapalı beta bir iddia değil KONTROL olsun" idi; bu yol o kontrolü fail-open bırakıyordu. Etki: davetsiz izlenemeyen kullanıcılar KVKK'da veri-sorumlusu yükümlülüğü doğurur ve envanterde görünmez; her yeni kullanıcı paylaşılan LLM sağlayıcı kotasını tüketir (gerçek davetliler koçu kullanamaz); `BetaInvite` listesi gerçekle uyuşmaz; `/api/meta` kimliksiz olarak `davet_kodu_gerekli: true` beyan ederken ürün o kontrolü uygulamıyordu (L8). Mevcut süit bu fail-open davranışı **kilitliyordu** (`test_callback_yeni_kullanici_olusturur`) — kapı yokluğu testle onaylanmış görünüyordu. Fix: OAuth'ta kod girilecek alan olmadığı için kapı **e-posta eşleşmeli davet** ile kuruldu (davet ilk girişte tüketilir, kurallar tek kaynaktan `davet_dogrula`'dan gelir); e-postasız davet OAuth'ta fail-closed; operatör aracı + runbook uyarısı eklendi | `tests/auth/test_oauth_davet_kapisi.py` **11 test** (PoC, `/register` ile aynı davranış, meşru davetli + davet tüketimi izlenebilir, büyük/küçük harf, mevcut kullanıcı girişi bozulmadı, `open` modda davranış aynı, tükenmiş/süresi geçmiş/başka adres/e-postasız davet, meta beyanının kodda karşılığı). Düzeltme öncesi 8'i kırmızıydı; mevcut `tests/auth/test_oauth.py` (10 test) yeşil kaldı | ✅ |

| BUG #227 | **Belgelenen bir dağıtım yolu KİMLİKSİZ canlı sunucu üretiyordu (denetim D06).** `docs/deployment/README.md` iki yolu da resmî belgeliyor (ADR-035: systemd "alternatif") ve her ikisi de `cp .env.example .env` diyordu; `.env.example` ise `ENVIRONMENT=development` + `AUTH_ENABLED=` (BOŞ). Yol 1'i (Docker) compose'un `${ENVIRONMENT:-production}`/`${AUTH_ENABLED:-true}` varsayılanları kurtarıyordu — **Yol 2'de (systemd) hiçbir koruma yoktu.** Denetimin çalıştırdığı kanıt: `validate_security_config()` istisna atmıyor, `GET /api/cockpit` 200, `GET /api/users/me/export` 200 (tam KVKK export'u), `DELETE /api/users/me` 204 — hepsi Authorization header OLMADAN. BUG #171 tam bu senaryo için açılmış ve "kapatıldı" denmişti; koruma `is_production()`e bağlı olduğu için bu yolda hiç devreye girmiyordu. **Kök neden doküman değil, güvenlik varsayılanının fail-OPEN olması.** Fix (katmanlı): (1) `auth_enabled()` **fail-closed** — tanımsız/boş/anlamsız değer AÇIK sayılır, kapatmak için açıkça `AUTH_ENABLED=false`; (2) `auth_problems()` prod fail-fast'i ikinci savunma hattı olarak kalır (açıkça kapatma prod'da yasak); (3) `deploy/financialos.service` kendini `ENVIRONMENT=production` ilan eder — EnvironmentFile'dan SONRA, eskimiş `.env` ezemesin; (4) README her iki yolda `.env.prod.example` gösterir + minimum listeye `ENVIRONMENT`/`AUTH_ENABLED`/`SUPPORT_EMAIL` eklendi; (5) `.env.example` yeni varsayılanı yazar; (6) ADR-033 §5'teki "varsayılan kapalı" kararı DEĞİŞTİRİLDİ notuyla güncellendi | `tests/security/test_kimliksiz_deploy_kapisi.py` **20 test**: varsayılan/boş/anlamsız değer → açık, `0/false/no/off` → kapalı (L6: yerel kurulum kilitlenmez), prod'da açıkça kapatma fail-fast, **README'nin `cp <şablon> .env` dediği HER şablon gerçekten kimlikli sunucu üretir** (kapsam tabanı assert'li — L11), systemd unit'i production ilan eder ve sırası doğru. Düzeltme öncesi 9'u kırmızıydı. **Tam süit 1677 passed** — varsayılan çevrilmesine rağmen kırmızı yok; test altyapısı artık gerçek bir yerel kurulumla aynı hareketi yapıyor (açıkça `AUTH_ENABLED=false`) | ✅ |

| BUG #228 | **LLM kotası tek uca cıvatalanmıştı; diğer yollar tavanı sıfırlıyordu (denetim D07 + D16).** ADR-041/BUG #188'in tüm amacı "bir kullanıcı paylaşılan API anahtarını/faturayı tek başına tüketemesin" idi; dayatma yalnız `POST /api/coach/chat` içindeydi. Denetim kanıtı: kota DOLU (coach 429) iken premortem ucu **5/5 istekte 200** döndü, 5 LLM üretimi yapıldı, `ApiCallLog` **hiç artmadı**; tek bir aksiyon için 6 kez üretim (BUG #137 cache'i cockpit hash'ine bağlı, kullanıcı kotasız bir uçla bakiyeyi değiştirince hash değişiyor). D16 aynı sınıf: `POST /api/actions/{id}/approve` arka planda kotasız + kayıtsız Groq çağrısı yapıyordu. Zarar: ücretsiz kademede paylaşılan anahtar tükenir → TÜM beta kullanıcılarının koçu "cevap veremedi"ye düşer; ücretli kademede doğrudan fatura. Üstelik trafik `ApiCallLog`'a düşmediği için `beta_metrics` maliyet/hata ölçümleri onu HİÇ görmüyordu — operatör patlamayı ölçse bile nedenini bulamazdı. Fix: kota muhasebesi router'dan **sökülüp `app/llm_quota.py`'ye alındı** (rezerve/tamamla/iptal + tavan + günlük sayı); `routers/coach.py` geriye-uyum sarmalayıcısı yapar. Premortem ucu **önbellek dalından SONRA** rezerve eder (cache LLM harcamaz → kullanıcı yapılmamış çağrı için cezalanmaz), çöken çağrı sayılır. Aksiyon yansıması arka plan görevi olduğu için 429 yerine **atlar** (kullanıcıya hata gösterilemez; doğru davranış işi atlamak, sessizce kotasız çağırmak değil) ve beklenmedik hatada rezervasyon iptal edilir | `tests/test_llm_kota_kapisi.py` **9 test**: premortem sayaca yazar / kota dolu → 429 / tavan kapalıyken çalışır (L6) / önbellek kota harcamaz, yansıma kota doluyken LLM çağırmaz + koşarsa sayaca yazar, **ve statik kapı**: `provider.chat`/`build_provider` çağıran her `app/` dosyası ya `llm_quota`'dan geçer ya `# kota-exempt: <gerekçe>` taşır (kapsam tabanı + bayat-muafiyet kontrolü ile). **Mutasyon kontrolü:** rezervasyonlar kaldırılınca 4 test kırmızıya döndü. Muafiyetler gerekçeli: `coach.py`/`premortem.py` (motor — kota router'da), `coach_insights.py` (cron, kullanıcı döngüye sokamaz; **açık iş:** cron çağrılarının ayrı maliyet muhasebesi, D24 ailesi) | ✅ |

| BUG #229 | **Fiyat cron'u `Account.balance`'ı güncellemiyordu — kullanıcı aynı hesap için İKİ FARKLI TL görüyordu (denetim D08).** Cockpit 36.000, Hesaplar paneli 30.000; üstelik aynı kartta "6 lot × 6.000 TL" yazıyor. Hangisinin doğru olduğunu anlamanın yolu yok. Finansal üründe çelişen bakiye = yanlış rakama göre satış/harcama kararı + güvenin bir defada bitmesi. Fark her fiyat hareketiyle büyüyor, kullanıcı manuel fiyat girmedikçe Hesaplar paneli KALICI donmuş kalıyordu. Kök neden bir DEĞİŞMEZ İHLALİ: yatırım hesabında `balance == lot_count × current_price`; bu değişmezi diğer TÜM yazma yolları koruyor (fund_tracker manuel fiyat, accounts create/update, `action_executor` — oradaki BUG #102 yorumu değişmezi açıkça adlandırıyor, simulation_engine), tek ihlal eden gece koşan cron'du. Okuma tarafı ayrışık olduğu için sapma görünür oluyordu: cockpit `lot × fiyat` hesaplar, `/api/accounts` ham `balance` döner. Fix: cron da değişmezi korur; `lot_count` None ise bakiyeye DOKUNULMAZ (hesaplanamaz — 0'a düşürmek veri kaybı olurdu), lot=0 ise bakiye 0 olur (kapanmış pozisyon para göstermez), yatırım-dışı hesaplara dokunulmaz | `tests/test_fiyat_cron_bakiye_senkron.py` **6 test** (değişmez; **iki panelin aynı hesapta aynı TL'yi göstermesi** — kullanıcı-görünür sözleşme; lot bilinmiyor / lot=0 uç durumları; PriceHistory + zaman damgası regresyonu; yatırım-dışı hesap). Düzeltme öncesi 3'ü kırmızıydı. Ayrıca sapmayı yeşile gömen `test_stock_price_isyatirim_m_hisse.py` (yalnız cockpit'i doğruluyordu) bakiye assert'iyle güçlendirildi | ✅ |

| BUG #230 | **Production yığını belgelenen komutla AYAĞA KALKMIYORDU + otomatik yedeği YOKTU (denetim D11+D12+D13/D09).** **(D11)** `docker-compose.prod.yml`'de hiçbir serviste `env_file:` yoktu; runbook'un tek deploy komutu `--env-file .env.prod` kullanıyor ama o bayrak YALNIZ `${...}` interpolasyonunu besler, konteyner ortamına değişken YAZMAZ. Sonuç: `.env.prod`'a doğru yazılmış `SUPPORT_EMAIL` (BUG #210 gereği prod'da zorunlu) uygulamaya hiç ulaşmıyor → backend startup'ta fail-fast, `deploy.sh` healthcheck'i geçemiyor, otomatik rollback **aynı derecede bozuk** önceki sürüme dönüyordu; operatörün elinde "neden açılmıyor" cevabı yoktu. Operatör onu elle eklese bile `SMTP_*`/`OAUTH_*` sessizce yapılandırılmamış kalıyordu (davet + şifre sıfırlama ÖLÜ). **(D12)** `scheduler` servisinde `AUTH_ENABLED` yoktu → aynı lifespan, aynı fail-fast, crash-loop; 02:45 fiyat ve 03:00 gece batch'i hiç koşmuyor, kullanıcı BAYAT fiyatlarla hesaplanmış net değere göre para kararı veriyordu. Üstelik `deploy.sh` yalnız "UYARI" basıp çıkış 0 ile "TAMAM" diyordu (sessiz arıza) ve `restarting` durumu `Up\|running` grep'iyle eşleşmediği için crash-loop hiç fark edilmiyordu. **(D13/D09)** Prod yığınında otomatik yedek YOKTU; beta kullanıcılarının tüm finansal geçmişi tek volume + tek Free-Tier VM'de. Depodaki tek yedek otomasyonu SQLite-only `scripts/backup.py`'yi çağırdığı için Postgres'te her gece çıkış kodu 1 ile sessizce ölüyordu. Fix: `env_file` (backend+scheduler), scheduler `AUTH_ENABLED`, `deploy.sh` scheduler ölüyse **rollback** + crash-loop tespiti, compose'a `backup` servisi + `deploy/pg_backup.sh` (dump → **doğrula**: asgari boyut + `gzip -t`; geçmeyen dump SİLİNİR → geçici dosyadan adlandırma → `pg-backups` adlandırılmış hacmi → `KEEP_DAYS` rotasyonu), yanıltıcı systemd unit'inin başlığı düzeltildi, runbook'a listeleme/elle koşma/**dışarı kopyalama** uyarısı, `.env.prod.example`'a `BACKUP_KEEP_DAYS`/`BACKUP_INTERVAL` | `tests/test_prod_compose_sozlesmesi.py` **11 test**: kapsam tabanı (L11), `env_file` iki serviste, **`.env.prod.example`'ın tarif ettiği anahtar gerçekten konteynere ulaşıyor mu** (L8), scheduler `AUTH_ENABLED` + backend↔scheduler kritik ortam paritesi, yedek servisi var / `pg_dump` alıyor / **kalıcı hacme** yazıyor, yedek script'i rotasyon + `set -e` uyguluyor, bayat SQLite unit'i kendini açıkça etiketliyor. Düzeltme öncesi 9'u kırmızıydı | ✅ |

| BUG #231 | **Yayınlanan KVKK/veri-işleyen beyanı gerçek veri akışıyla uyuşmuyordu (denetim D10).** Beyan (rıza kapısında sunuluyor): *"Gönderilmeyenler: … ham işlem listesi"*. Gerçek: koç bağlamında `## SON İŞLEMLER` bloğu literal olarak gidiyor — tarih, tutar, kategori ve **kullanıcının serbest metin açıklaması** ("Psikiyatri kontrol"), ayrıca **hesap adları** ve alacak/borç kaydındaki **üçüncü kişilerin adları**. İşlem açıklaması pratikte ÖZEL NİTELİKLİ veri taşır (sağlık/inanç/sendika); KVKK m.6 ve m.9 ayrı ve bilgilendirilmiş açık rıza ister — yanlış kapsamla alınan rıza sakattır (idari para cezası + tazminat riski). Üstelik üçüncü kişi uygulamanın kullanıcısı bile değil. Fix: **(1)** envanter gerçeğe uyduruldu (tam gönderilen liste + özel nitelikli veri uyarısı + üçüncü kişi uyarısı + gerçekten gönderilmeyenler); **(2)** kapsam maddi değiştiği için rıza sürümü **v3**; **(3)** `/api/legal/kvkk` dosyayı `KVKK_CONSENT_VERSION`'dan türetiyor — sabit "v2" yazılıydı, yani sürüm yükselse bile kullanıcı ESKİ metni okuyacaktı (onayladığı sürüm ≠ okuduğu metin); **(4)** "sürümü yükseltip susmak" L8 tuzağı olacağı için **rıza tazeleme yolu** (`GET/POST /api/users/me/kvkk-consent`) + Koç panelinde bant; **(5)** aktarım kapsamı **aktarımın yapıldığı yerde** (mesaj kutusu altında) yazıyor — kullanıcı rıza metnini kayıtta bir kez okur, mesajı her gün burada yazar | `tests/test_kvkk_beyan_gercek_akis.py` **14 test**: işaretli kullanıcıyla GERÇEK koç bağlamı üretilir, her veri sınıfının bağlamda olduğu (kapsam tabanı, L11) ve **beyanda yazılı olduğu** doğrulanır → bağlama yeni alan eklenip beyan güncellenmezse kapı kırılır (L9: kod ile doküman arasına test); ters yön (şifre hash'i/e-posta gerçekten gitmiyor); yanlış cümlenin geri gelmemesi; rıza metni ↔ envanter tutarlılığı; sunulan metin = onaylanan sürüm; eski sürümlü kullanıcı yeniden onay ister. Düzeltme öncesi 7'si kırmızıydı. Frontend: `npm run build` + 125 vitest yeşil | ✅ |

**Ledger notu (2026-08-05):** bu dosya P1 turundan sonra geride kalmıştı; BUG #166-#210 arası
publish-yolu düzeltmeleri **`masterprompt-publish.md` §11 durum tablosunda** kayıtlı (tek doğruluk
kaynağı orası). Bu bölüm ledger'ı yeniden bağlar; §11 ile çelişki çıkarsa §11 esas alınır.
