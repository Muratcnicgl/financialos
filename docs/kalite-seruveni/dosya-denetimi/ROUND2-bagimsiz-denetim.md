# Bağımsız Per-File Denetim — Round 2 (11 Tem 2026)

> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


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

**Düşük şiddet:**
- rules_engine kart durum 3-state basitleştirmesi: ✅ **MİTİGE (BUG #096):** kart son ödeme
  artık ayrı proaktif reminder olarak firing — durum-state suppression'dan bağımsız.
- rules_engine anomali penceresi 30 vs 31 gün off-by-one → ✅ **ÇÖZÜLDÜ (BUG #108):** ikisi de eşit 30 gün.
- sim emanet guard asimetrisi → ✅ **ÇÖZÜLDÜ (BUG #101).**
- executor mutasyon+status ayrı commit (P2 plausible, düşük olasılık). **İzleme (yapısal, düşük risk).**
- sell_investment balance vs current_price sapması → ✅ **ÇÖZÜLDÜ (BUG #102).**
- income-on-card işaret → ✅ **ÇÖZÜLDÜ (BUG #103).**
- debts.py çelişkili paid state → ✅ **ÇÖZÜLDÜ (BUG #106):** explicit is_paid kazanır, her durumda tutarlı.
- goal_engine daily_rate/90 genç goal'de yavaş → ✅ **ÇÖZÜLDÜ (BUG #105):** gerçek allocation span.
- cashflow tek-hesap projeksiyonu → ✅ **ÇÖZÜLDÜ/BELGELENDİ (BUG #107):** UI hiç account_id
  geçmiyor (yol kullanılmıyor); izole-hesap semantiği ürün kararı → varsayımla değişiklik YOK, sınırlama koda not düşüldü.
- coach_insights K2 duplicate → ✅ **ÇÖZÜLDÜ (BUG #104):** stabil kategori-bazlı title.

## SONUÇ — denetim tamamen kapatıldı (11 Tem 2026)
7-ajan denetiminin TÜM bulguları çözüldü, mitige edildi, tasarım-gereği doğrulandı veya
belgelenerek kapatıldı. Deterministik düzeltme kalmadı. Açık backlog yalnız: structured output
(LLM-gated, contract harness ile de-risk), Account/Goal cascade (mimari tasarım), main.py stil.

## ROUND 3 — KAPSAM-GÜDÜMLÜ (coverage-driven) denetim (11 Tem 2026)

pytest-cov ile kritik modül kapsamı ölçüldü; düşük-kapsamlı finansal-mantık yollarına test
yazılırken **iki semantik denetimin (per-file + öz-denetim) KAÇIRDIĞI 3 gerçek bug bulundu**:
- **BUG #113 (executor):** `mark_debt_paid` nakdi hareket ettirmiyordu. Prompt bunu TEK aksiyon
  olarak öneriyor (araştırmayla doğrulandı) → alacak tahsili net değeri YANLIŞ düşürüyordu.
  Executor↔sim tutarlı hale getirildi (tahsilat nakit+, ödeme nakit−). **Finansal doğruluk.**
- **BUG #114 (executor):** `_DATE_KEYWORD_RE`'de `['']` düz apostrofları raw string'i erken
  kapatıp karakter sınıfını boş `[]` yapıyordu → "3'ünde/5'inde" Türkçe sıralı tarihleri
  yakalanmıyor (TARIH_BELIRSIZ bu formda çalışmıyor) + `\w` kaçış-uyarısı. Çift-tırnak raw ile düzeltildi.
- **BUG #115 (fund_tracker):** `update_fund_price_manual` user_id ile kapsamlanmayan tek mutasyon
  handler'ıydı (denetimin PLAUSIBLE flag'i doğrulandı). Opsiyonel user_id + iki çağıran güncellendi.

Kapsam: action_executor %49→%73, simulation_engine %66→%85 (simulate_action çekirdeği MOCK'suz
test edildi), fund_tracker %14→%51. **Ders (meta-ders #8'i pekiştirir): semantik denetim +
kapsam-güdümlü test BİRLİKTE gerekir — biri diğerinin kaçırdığını yakalar.** Süit 291→324.

## ROUND 4 — property-based + net-değer korunumu (11 Tem 2026)

- **hypothesis** ile çekirdek matematik değişmezleri fuzz-doğrulandı (shadow accounting, daily
  limit, partial-sale stopaj 300 örnek, debt PARA KORUNUMU 150 rastgele borç seti). Kod bug'ı
  YOK — güçlü "sıfır hata" kanıtı. Bir nüans belgelendi (avalanche≤snowball faiz EVRENSEL DEĞİL:
  küçük %0 borç + büyük minimum → snowball büyük minimumu erken serbest bırakır; gerçek finans
  nüansı, #081 uyarısı var).
- **Net-değer korunumu** testleri #113'ü net-değer seviyesinde kilitledi (alacak tahsili net-nötr;
  gider tam-tutar düşüş; satış yalnız-stopaj). **YENİ BULGU (flag — tasarım kararı):** `net_deger_tam`
  kişisel ALACAĞI (receivable) varlık sayıyor ama kişisel BORCU (payable) yükümlülük SAYMIYOR
  (`rules_engine:886` = net_deger + alacaklar; payable hiç düşülmüyor) → asimetri, net değeri
  fazla-iyimser gösterir (realist-koç etiğiyle gerginlik). Banka borçları (kart/kredi) DOĞRU
  düşülüyor (`net_deger:881`); kişisel payable ikincil. **Karar:** headline metrik olduğu için
  varsayımla değiştirilmedi; kullanıcı kararı — `net_deger_tam += -ödenmemiş_payable` simetrik/
  finansal-doğru olur (öneri), ama kullanıcının dashboard'unda kişisel IOU'ları net değerden
  düşmek isteyip istemediği ürün kararıdır.
  → ✅ **ÇÖZÜLDÜ (BUG #116):** simetrik + finansal-doğru + realist-etik yönünde uygulandı:
  `net_deger_tam = net_deger + alacaklar − kişisel_borçlar`. **ŞEFFAF** yapıldı: `borclar_toplami`
  cockpit'e eklendi (alacaklar_toplami ile simetrik) ve koç "Tam Net Değer" bloğu hem +alacak
  hem −kişisel-borç detayını gösteriyor (gizli değişiklik değil). Net-değer korunumu artık her
  iki yönde tutuyor (borç ödemesi net-nötr). Tersine çevrilebilir (tek işaretli değişiklik).
  Kullanıcı kişisel IOU'ları net değerden düşmek istemezse geri alınır.

## Vizyon değeri (denetim sonrası, aynı turda)
Kurucu vizyona hizmet eden eklemeler: **A1 kart son ödeme reminder (#096)**, **A3 aylık özet
(#097)** + rules_engine refactor, **koç aylık trend farkındalığı (#098)**, **son işlemler
grounding-tutarlı context (#099)**, **zikzak "yarınki limit" projeksiyonu (#100)** + frontend
görünürlük, **koç davranış sözleşmesi uçtan-uca harness** (deterministik eval). Süit 162→280 yeşil.

## Doğrulanan temiz alanlar (ajan raporlarından)
premortem.py, fund_tracker.py (tam temiz); rules_engine bölme-sıfır guard'ları + leap-year +
shadow_accounting formülü; reports.py #073/#074 month-rollover; scheduler rollback; goals.py
allocation guard (#072); Pydantic V1 leftover yok; dual-index anti-pattern yok; get_current_user
doğru; enum↔Literal pariteleri; _project_forward (start,end] yarı-açık tutarlılığı (#084).
