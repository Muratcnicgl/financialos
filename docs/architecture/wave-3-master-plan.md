# Wave-3 Master Plan (M7 — hazırlık, KARAR YOK)

**Tarih:** 13 Temmuz 2026 · **Durum:** Hazırlık (kararlar Wave-3 başında verilir) · **Kaynak:** `wave3-vision.md`, `mobile-roadmap.md`, Wave-2 ertelenen backlog (faz-3-durum.md), ADR-019 (multi-asset).

> **İLKE (charter M7):** Bu belge Wave-3'ü **materyalize eder, KARAR VERMEZ.** Mimari kararlar (mobil platform, auth stratejisi, sağlayıcı) Murat + planner tarafından Wave-3 başında, D1 araştırması sonrası verilir. Buradaki ADR'ler (031-034) **STUB** — karar bölümü boş, sorular listeli. Bu, "Rules Engine karar verir / planner mimari karar verir" ayrımına saygıdır.

## Wave-2 Bitiş Durumu (baseline)
- 807 test yeşil · Decimal para (Numeric 19,4 canlı) · fiyat otomasyonu (pytefas cron) · Kalite Serüveni Faz 3 P1 27/27.
- Canlı DB head `978ad0f00814`. Koç fiilen Gemini (ADR-028). Tek-kullanıcı lokal MVP.

---

## Ana Özellikler (6) + Açık Sorular

### 1. Multi-asset (kripto/hisse/döviz/altın/gayrimenkul) — ADR-019 → **adr-031-multi-asset**
- **Kapsam:** `Account`/`PriceHistory` modelini fon-ötesi varlıklara genişlet. Şu an yalnız TEFAS fonu (fund_code). Fiyat sağlayıcı katmanı (`app/price_providers/`) zaten dispatch-hazır (get_stock_price İş Yatırım stub var).
- **Açık sorular (karar bekliyor):** Varlık tipi modeli (tek tablo + type kolonu mu, ayrı tablolar mı)? Fiyat sağlayıcı zinciri (kripto→CoinGecko, hisse→İş Yatırım, döviz→TCMB EVDS, altın→?)? Numeric(19,4) kripto için yeterli mi yoksa Numeric(28,8) mi (ADR-030 revize-tetiği)? Emanet (MC1) çoklu-varlıkta nasıl?
- **Wave-2 kanıt:** ADR-030 "kripto → Numeric(28,8) revize kolay" notu; price_providers dispatch mimarisi.

### 2. Mobil platform (PWA vs RN+Expo) — **adr-032-mobile-platform** (araştır, KARAR VERME)
- **Kapsam:** Web'i koruyarak mobil-first. `mobile-roadmap.md`'de 3 yol analiz edildi (PWA / RN+Expo / native).
- **Açık sorular:** PWA (2-4 hafta, kod %95 korunur, App Store yok) mu, RN+Expo (native his, ayrı kod tabanı) mı? Offline-first gerekli mi? Push notification (vade hatırlatma) hangi yolda? Backend API zaten REST → ikisi de tüketebilir.
- **D1 gerekli:** PWA capability 2026 (iOS Safari PWA kısıtları), Expo Router olgunluğu.

### 3. Auth + Multi-user (JWT vs Firebase, KVKK) — **adr-033-auth-multiuser**
- **Kapsam:** `get_current_user` şu an "ilk kullanıcı" döndürüyor (MVP). Multi-user'a geçiş buraya JWT/session bağlar (dependencies.py — başka yere DEĞİL, mimari sınır korunur).
- **Açık sorular:** JWT (kendi auth) mu Firebase Auth mı? KVKK: kişisel finansal veri → veri-ikamet (TR sunucu?), şifreleme-at-rest, silme-hakkı. Row-level isolation (her sorgu user_id filtreli — çoğu zaten öyle, P1-11/14 denetimi). Rate-limit + HTTPS (Wave-2'de T-17 ertelendi) burada prod-gate ADR'ı ile.
- **Wave-2 kanıt:** SEC-001/002 (auth/BOLA), T-17 güvenlik grubu; ownership guard'ları (P1-11/12/14) zaten var.

### 4. Koç sağlayıcı Wave-3 (ADR-028 revize) — **adr-034-coach-provider-wave3**
- **Kapsam:** ADR-028 "fiilen Gemini-only" durumunu revize. Sub-agent routing (wave3-vision §1: intent classifier → uzman ajan) + OpenRouter (ADR-034 adayı, research-log'da 50/gün TPM-sınırsız).
- **Açık sorular:** LangGraph state machine mi, hafif kendi router mı? OpenRouter fallback canlı test (ADR-028 devamı)? Intent classifier maliyeti (küçük model) değer mi? Prompt caching (P2-13).
- **Wave-2 kanıt:** research-log OpenRouter D1; FallbackProvider zinciri; P1-25 Anthropic adapter (artık tool-aware).

### 5. Kart taksit (MC3 Ziraat ekstre-döngüsü genişletme)
- **Kapsam:** P1-24'te `evaluate_credit_card_strategy` cockpit'e bağlandı (util-guard'lı). Wave-3: taksitli harcama takibi, ekstre-bazlı taksit projeksiyonu, çoklu-kart.
- **Açık sorular:** Taksit modeli (Transaction'a installment alanları mı, ayrı tablo mı)? RULE-005 geç-statement kartlar için gerçek-tarih rewrite (Wave-2'de erken-statement için doğrulandı).

### 6. TR Open Banking / ÖHVPS (H2 2026)
- **Kapsam:** BDDK Açık Bankacılık (ÖHVPS) ile hesap/işlem otomatik senkronizasyon — elle giriş biter.
- **Açık sorular:** ÖHVPS API erişim (lisans/sandbox)? Hangi bankalar? Veri güvenliği + KVKK (auth ADR-033 ile bağlı). Zamanlama (H2 2026 regülasyon).

---

## Wave-2'den Devreden Teknik Backlog (Wave-3'e ertelenen, OTONOM KARAR kayıtlı)
- **P2-1** `session.query()`→`select()` göçü (138+ kullanım, kademeli).
- **P2-12** Backend mimari refactor: coach.py god-module böl, service/repository katmanı, config merkezi (ön-koşul: test altyapısı — pytest zaten var, 807 test).
- **P2-13** LLM orkestrasyon: prompt caching, eval harness, token metriği.
- **Decimal depolama tamamlama:** SQLite REAL → PostgreSQL gerçek DECIMAL (ADR-030 depolama-katmanı sınırı; auth/multi-user Postgres'e geçişle birlikte).
- **Premortem calibration:** tahmin (impact_tl) vs gerçek outcome (net_worth_delta) — P1-19'da kaldırılan param, tüketiciyle birlikte geri.
- **Güvenlik-sertleştirme:** auth/rate-limit/HTTPS/CORS (T-17) → adr-033 prod-gate.

## Sonraki Adım
Wave-3 başında: her ADR (031-034) için D1 araştırma (2-3 sektör referans, KURAL D1) → Research Log → karar. Bu belge + ADR stub'ları o kararların iskeleti. **Kararlar burada VERİLMEDİ (charter M7).**
