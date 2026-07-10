# Bağımsız Per-File Denetim — Round 2 (11 Tem 2026)

Kullanıcı talebi: "tüm projedeki her bir kodu ayrı ayrı ajanlara, tembellik yapmadan,
tam bakmadım demeden her detayı kontrol et." 37 backend dosyası **7 bağımsız adversarial
ajanla** tam okundu; her ajan yalnız `file:line` + somut failure-senaryosu olan doğrulanmış
defektleri döndürdü. Ana asistan her bulguyu **kod üzerinde bağımsız doğruladı** (körlemesine
ajan sonucu kabul edilmedi); düzeltmeler önce kırmızı test → sonra fix (TDD) ile yapıldı.

## Ajan dağılımı
1. rules_engine.py · 2. action_executor + simulation_engine · 3. analiz motorları (cashflow,
premortem, debt_strategy, goal_engine, goal_rules, fund_tracker) · 4. veri katmanı (models,
schemas, database, dependencies) · 5. mutasyon router'ları (transactions, actions, goals,
incomes, expenses, debts) · 6. sorgu router'ları + altyapı (coach, reports, accounts,
checkpoints, cashflow, cockpit, fund_price, scheduler, main, reasoning_trace) · 7. coach LLM
katmanı (coach.py, coach_insights.py).

## ✅ Düzeltilen + test edilen (BUG #085 iter2, #086–#092) — süit 218 yeşil

| BUG | Dosya | Defekt | Şiddet |
|-----|-------|--------|--------|
| #086 | rules_engine.py | Beklenen gelir çift-sayımı (tetiklenmiş gelir hem nakit hem recurring_income) → reel_butce şişer | P1 (kurucu "çift sayma yasak") |
| #087 | routers/transactions.py | update amount≤0 doğrulanmıyor → gider güncellemesi bakiyeyi ARTIRIYOR; yabancı account_id sessiz kabul | HIGH |
| #088 | routers/expenses.py | update account_id sahiplik doğrulaması yok | MEDIUM |
| #089 | debt_strategy.py | Kart rollover STALE başlangıç min'i ekliyor → iyimser months_to_freedom | MEDIUM |
| #090 | goal_rules.py | full/percent (+ fixed) işaret-farkındasız → gider goal progress'i şişiriyor | MEDIUM |
| #091 | routers/accounts.py | Bağlı txn'li hesap silme IntegrityError → HTTP 500 (FK #060'ta enforce) | HIGH |
| #092 | 8 router + serializers.py | 14 datetime alanı tzinfo'suz → JS -3h kayma | MEDIUM |
| #085 iter2 | coach.py | _FAKE_PASTTENSE_RE edilgen formları analiz raporlarını bozuyor (yanlış-pozitif) | HIGH (regresyon) |

## ⏳ Bilinçli ertelenen (kayıt için — kaybolmasın) + gerekçe

**LLM-davranışı (eval harness / LLM-004 gerektirir — doğrulanamayan değişiklik uygulanmaz):**
- **coach.py:1235-1253 FallbackProvider tüm exception'ı yutuyor** (MEDIUM-HIGH): gerçek kod
  hatası "tüm sağlayıcılar düştü" gibi görünüyor. → Gözlemlenebilirlik fix'i (ERROR log) uygulandı (BUG #093).
- **coach.py YENİ CHECKPOINT stripping**: kullanıcı açıkça kural isteyip cevapta "eklenebilir"
  gibi hedge kelime geçince öneri siliniyor. → Kullanıcı-istediğinde-koru fix'i uygulandı (BUG #094).
- **is_question boşlukları** (MEDIUM plausible): değerlendir/özetle/yorumla/karşılaştır/göster/
  hesapla + gelecek-zaman ifadeleri yakalanmıyor → propose_action bu durumda hâlâ açık.
  ✅ **ÇÖZÜLDÜ (BUG #095):** is_question analiz fiillerini yakalar + should_offer_propose_tool
  gelecek/niyet ifadesinde propose_action'ı baskılar (deterministik). Uçtan uca contract harness ile kilitli.
- **STEP E retry non-realized eylemde propose_action zorluyor** (KURAL SIFIR): ✅ **ÇÖZÜLDÜ
  (BUG #095):** retry artık `offer_propose` guard'ına bağlı — gelecek/niyet ifadesinde zorlanmaz.
- **coach_insights K2 non-deterministik başlık → duplicate insight** (LOW-MEDIUM): dedup title
  LLM üretimine bağlı. **BACKLOG.**

**Mimari / model (ayrı tasarım kararı):**
- **models.py Account/Goal cascade yok** (HIGH/MEDIUM): FK enforce olunca User/Account silme
  IntegrityError. Router 409 guard'ı (BUG #091) çökmeyi kapattı; tam cascade tasarımı ayrı.
  **BACKLOG: DATA (cascade stratejisi).**
- **reasoning_trace per-step commit** (MEDIUM plausible): İncelendi — büyük ölçüde TASARIM
  GEREĞİ (observability trace, chat başarısız olsa bile debug için kalmalı; CoachMemory/
  PendingAction kendi commit'lerinde atomik). Net bug değil. **İzleme.**
- **main.py _catch_up_snapshots iş mantığı** (style, app/PROJE.md): startup modülüne taşınmalı.

**Düşük şiddet (izleme):**
- rules_engine kart durum 3-state basitleştirmesi: ✅ **MİTİGE (BUG #096):** kart son ödeme
  artık ayrı proaktif reminder olarak firing — durum-state suppression'dan bağımsız.
- rules_engine anomali penceresi 30 vs 31 gün off-by-one (kozmetik). **İzleme.**
- sim emanet guard asimetrisi → ✅ **ÇÖZÜLDÜ (BUG #101):** add_transaction + update_account_balance
  sim'de emanet'i bloklar (executor ile birebir); update_fund_price meşru revalüasyon (bloklanmaz).
- executor mutasyon+status ayrı commit (P2 plausible, düşük olasılık). **İzleme.**
- sell_investment balance vs current_price sapması → ✅ **ÇÖZÜLDÜ (BUG #102):** satışta
  current_price=actual_price güncellenir; balance == lot_count*current_price tutarlı.
- income-on-card işaret → ✅ **ÇÖZÜLDÜ (BUG #103):** karta gelen gelir borcu azaltır (executor+sim).
- debts.py çelişkili paid state (LOW edge). **İzleme.**
- goal_engine daily_rate/90 genç goal'de yavaş (modelleme). **İzleme.**
- cashflow tek-hesap projeksiyonu global gelir/gider karıştırıyor (modelleme). **İzleme.**

## Vizyon değeri (denetim sonrası, aynı turda)
Kurucu vizyona hizmet eden eklemeler: **A1 kart son ödeme reminder (#096)**, **A3 aylık özet
(#097)** + rules_engine refactor, **koç aylık trend farkındalığı (#098)**, **son işlemler
grounding-tutarlı context (#099)**, **zikzak "yarınki limit" projeksiyonu (#100)**, **koç
davranış sözleşmesi uçtan-uca harness** (deterministik eval). Süit 162→272 yeşil.

## Doğrulanan temiz alanlar (ajan raporlarından)
premortem.py, fund_tracker.py (tam temiz); rules_engine bölme-sıfır guard'ları + leap-year +
shadow_accounting formülü; reports.py #073/#074 month-rollover; scheduler rollback; goals.py
allocation guard (#072); Pydantic V1 leftover yok; dual-index anti-pattern yok; get_current_user
doğru; enum↔Literal pariteleri; _project_forward (start,end] yarı-açık tutarlılığı (#084).
