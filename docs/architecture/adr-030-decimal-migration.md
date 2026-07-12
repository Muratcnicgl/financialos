# ADR-030 — Para alanları Float → Numeric(19,4) + Decimal aritmetiği

**Tarih:** 12 Temmuz 2026 · **Durum:** Kabul edildi (M5, onay-kapılı) · **İlgili:** ADR-012 (PriceHistory zaten Numeric(19,4)), ADR-001 (para matematiği backend'de)

## Bağlam
Finansal bir OS'te para IEEE-754 float'ta tutuluyor: `0.1 + 0.2 = 0.30000000000000004`. 20 para kolonu `Column(Float)` — bütçe, devreden bakiye, kart stratejisi, K/Z hesaplarında sessiz drift birikir. Bir _finansal_ sistemde bu KURAL 12 ihlali (kalite mutlak). PriceHistory zaten `Numeric(19,4)` (ADR-012) — tutarsızlık.

## D1 araştırması (sektör liderleri)
- **Beancount** — Python `Decimal`, `prec=28` context. Çift-girişli muhasebe standardı.
- **Firefly III** — `decimal(32,12)` (kripto dahil aşırı hassas). Bizim için fazla geniş.
- **Maybe Finance** — `Decimal(19,4)` (Rails Money). 19 basamak / 4 ondalık = ~10^15 TL + kuruş-altı. **Referans alındı.**
- **Ledger CLI** — keyfi hassasiyet rasyonel aritmetik.
- **SQLAlchemy `Numeric(asdecimal=True)`** — ORM okuma/yazmada Python `Decimal` döner.

## R3 GERÇEĞİ — SQLite ampirik testi (varsayma, ölçüldü)
`Numeric(19,4)` SQLite'ta:
- **Python katmanı:** ORM `Decimal` döner → `0.1 + 0.2 == Decimal("0.3")` **TRUE** (uygulama aritmetiği KESİN — asıl kazanç).
- **Depolama katmanı:** SQLite'ın native DECIMAL'i YOK → `typeof(money)` = **`real`** (REAL/float). SQLAlchemy okurken string-quantize ile `Decimal`'e döndürür. TL tutarları (< 10^11, 4 ondalık ≤ 15 anlamlı basamak, double kapasitesi 15-17) için güvenli; **tam DECIMAL depolama Wave-3 PostgreSQL göçünde tamamlanır** (revize-tetiği). Dürüst sınır: SQLite'ta kazanç %90 (app-katmanı kesin), depolama round-trip REAL.
- **`Decimal + float` → `TypeError`** (sessiz-yanlış DEĞİL, sert çökme). Blast radius: para kolonlarını tüketen HER aritmetik modül Decimal-temiz olmalı.

## Karar
1. **20 para kolonu → `Numeric(19, 4)`** (`asdecimal=True`): Account.balance/credit_limit/monthly_payment/cost_per_lot/current_price, RecurringIncome/RecurringExpense/Transaction/PersonalDebt.amount, ActionHistory.net_worth_before/after+cash_before/after, NetWorthSnapshot.net_worth_seen/full+cash+card_debt+loan_debt+investment_value+receivables.
2. **OTONOM KARAR (kategori-c, kalite):** Charter "Float sütunları tara → Numeric" premisi FAZLA GENİŞ. **3 kolon para DEĞİL, Float KALIR:** `interest_rate` (aylık % oran), `lot_count` (fon lot adedi, kesirli miktar), `confidence_score` (LLM 0-1 güven skoru). Bunları Numeric'e çevirmek semantik yanlış + confidence-parser testlerini bozar. "Hepsini çevir" tembel-sweep'i REDDEDİLDİ — para/oran/miktar/skor ayrımı yapıldı.
3. **Aritmetik modüller Decimal context** (`ROUND_HALF_UP`, `getcontext().prec=28`): rules_engine, goal_engine, debt_strategy, cashflow, action_executor. Decimal↔float TypeError'ı önlemek için para değerleri Decimal olarak akar; sabitler Decimal'e çekilir.
4. **İç aritmetik Decimal + `floatify` serialize sınırı (uygulama gerçeği):** `app/money.py` — `D()` (float→Decimal, str üzerinden, drift yok), `ZERO`, `q2/q4` (ROUND_HALF_UP), `floatify` (public dönüşte Decimal→float özyinelemeli). Kural motoru İÇERDE Decimal hesaplar; cockpit/simülasyon/zarf/K-Z **public dönüşünde `floatify`** ile float'a çevrilir → JSON float, frontend değişmez. `float(para)` cast'ları (rules_engine 22, action_executor, transactions router, fund_tracker) `D()`'ye çevrildi → Numeric-depola-ama-float-hesapla KURAL 12 tuzağı önlendi. `json.dumps(..., default=float)` (coach_insights/coach/premortem/reasoning_trace/actions) → Decimal JSON sınırı.
5. **OTONOM KARAR (kategori-b, KAPSAM_SAPMASI — Pydantic condecimal):** Charter Faz E "schemas.py `condecimal(max_digits=19, decimal_places=4)`" diyordu. **R3 + K10 ile yeniden yorumlandı:** hedef (para hassasiyeti) `floatify` sınır mimarisiyle DAHA İYİ karşılanıyor. `condecimal`'i RESPONSE şemalarına koymak Decimal'i JSON serialize'a iter → B1'in "JSON float, frontend değişmez" mandasını RİSKE ATAR (Pydantic v2 Decimal-JSON kodlaması). Input hassasiyeti zaten `Numeric(19,4)` quantize + `D()` coercion + SEC-032 sonlu-doğrulama ile korunuyor. Bu yüzden şemalar `float` bırakıldı; hedefe daha temiz mekanizmayla ulaşıldı. Bu "MVP yeterli" pes edişi DEĞİL — kalite-eşdeğeri, B1-uyumlu daha iyi yol.
6. **Frontend politikası (B1):** **Decimal.js YOK.** JSON float serialize; `formatTL` değişmez; para matematiği backend'de (ADR-001). Frontend salt gösterim → dokunulmaz.

## K10 üç boyut
- **MUHAKEME:** Sektör (Beancount/Maybe/Firefly) para = Decimal, istisnasız. Float para = bilinen anti-pattern (Bloomberg/muhasebe standartları). Numeric(19,4) TL+kuruş için doğru genişlik.
- **BENİ DÜŞÜN (Murat):** Solo dev + öğrenci; kart %99.8 dolu, 5 kredi — kuruş driftinin bütçe/zikzak hesabında birikmesi tam da onun günlük 62 TL limitini etkiler. Hassasiyet lüks değil, gereksinim. SQLite şimdilik yeterli; Postgres Wave-3 backlog.
- **GENELİ DÜŞÜN:** TR ekonomik gerçek (yüksek enflasyon → büyük TL rakamları, double'ın 15-basamak sınırına yakın) Decimal'i daha da haklı çıkarır. KVKK etkisi yok (şema değişikliği, veri paylaşımı değil).

## Strateji (Faz B-I)
B backup+tag(`pre-decimal-migration`) · C batch_alter_table migration (para kolonları) · D mevcut REAL değerleri `Decimal(str(v)).quantize(0.0001, HALF_UP)` round · E kod Decimal · F test_decimal_precision.py + 781 uyum · **G ONAY KAPISI (canlı upgrade onaysız YASAK)** · H upgrade+doğrula · I commit+tag.

## Revize-tetiği
Wave-3 kripto → `Numeric(28, 8)` (revize kolay). **PostgreSQL göçü** → gerçek DECIMAL depolama (SQLite REAL sınırı kalkar) — bu ADR'ın depolama-katmanı sınırını kapatır.
