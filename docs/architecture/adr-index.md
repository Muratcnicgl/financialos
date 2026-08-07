# ADR İndeksi (M89, Wave-6 — 18 Tem 2026)

FinancialOS mimari kararlarının (ADR) tam envanteri. **39 dosya, ADR-001..037** (+013a addendum, +034-revize).
Kaynak: `docs/architecture/adr-*.md`. Wave-5 M74'te 21 eksik ADR MCP'den materyalize edildi; bu index M89
tutarlılık turunda oluşturuldu ("ADR-index güncel mi" boşluğu kapandı).

## Durum lejantı
✅ Kabul edildi (yürürlükte) · 🔴 SUPERSEDED (aşıldı) · 🟡 TASLAK · 🔵 REDDEDİLDİ (karar: yapma)

## Envanter

| ADR | Başlık | Durum | Zincir / Not |
|---|---|---|---|
| 001 | Rules Engine karar verir, LLM açıklar | ✅ temel ilke | M75: LLM-çıkarım istisnası eklendi |
| 002 | Provider-agnostic LLM (fallback zinciri) | ✅ | zincir sırası → ADR-004/034 |
| 003 | İki net değer metriği (Görülen vs Tam) | ✅ | — |
| 004 | FallbackProvider sıralaması | ✅ (revize) | sıra **ADR-034 ile revize** |
| 005 | is_question() deterministik ön-sınıflandırıcı | ✅ | — |
| 006 | Wave-2 mimari üçgeni (öğrenen koç) | ✅ | ADR-016/017/020 uygular |
| 007 | Tool-aware history (CoachMemory tool kolonları) | ✅ | — |
| 008 | İki katmanlı LLM savunma (input+output) | ✅ | — |
| 009 | PWA → RN+Expo mobil yol haritası | ✅ (yol haritası) | → ADR-032 (mobil platform) |
| 010 | Apple HIG 44px hit area | ✅ | .btn-icon (A11Y-006 kapandı) |
| 011 | PRICE_PROVIDER hibrit kanal | ✅ (güncellendi) | **ADR-029 ile güncellendi** |
| 012 | PriceHistory kompozit PK + çoklu-kaynak | ✅ | — |
| 013 | Alembic şema tek doğruluk kaynağı | ✅ | addendum: **ADR-013a** |
| 013a | Migration Genesis Collapse (013 addendum) | ✅ (M1) | — |
| 014 | Fiyat geçmişi backfill 1 yıl | ✅ | — |
| 015 | Yatırım değeri tarihsel backfill | ✅ | lot-history → Wave-3 (ADR-019) |
| 016 | Coach Insights iki helper paterni | ✅ | — |
| 017 | Coach Insights iki tip dormant sweep | ✅ | — |
| 018 | ReAct Reasoning Layer (UX+retention) | ✅ | — |
| 019 | Wave-3 Multi-Asset Vizyonu | ✅ (vizyon) | uygulama → **ADR-031** |
| 020 | Davranışsal hafıza prompt enjeksiyonu | ✅ | coach.py:1149 canlı |
| 021 | Cashflow Forecast Engine | ✅ KAPALI | +REV1-3 |
| 022 | 3-Ufuklu Karar Masası (T+0/30/90) | ✅ | T+1095 → Wave-3 |
| 023 | H2G4-G7 sıra değişikliği (veri-gerçeklik) | ✅ | — |
| 024 | Goal Engine kapsam daraltma (4→2 tip) | ✅ (Murat onayladı) | ADR-025 uygular |
| 025 | Goal Engine — Allocation-Based Pattern | ✅ (Wave-2 uygulandı) | Monarch Goals 3.0 |
| 026 | ZikZak (devreden bakiye) additive-red | ✅ | — |
| 027 | Koç raporu "structured output" | 🔵 REDDEDİLDİ | karar: yapma |
| 028 | Koç fiilen tek-sağlayıcı (Gemini-only) | 🔴 **SUPERSEDED by ADR-034** | M75 notu eklendi |
| 029 | Fiyat sağlayıcı stratejisi (pytefas cron) | ✅ (M4) | +EVDS v3 revize (14 Tem) |
| 030 | Para Float → Numeric(19,4) + Decimal | ✅ (M5) | canlı DB migrated |
| 031 | Multi-asset (asset_type kolonu) | ✅ (Wave-3 M12) | ADR-019 uygular; kripto→Wave-4 |
| 032 | Mobil platform (PWA vs RN+Expo) | 🟡 **TASLAK** | KAPSAM DIŞI (Wave-6 ÜRÜN-DNA) — ayrı karar bekliyor |
| 033 | Auth + Multi-user (JWT, KVKK) | ✅ (Wave-3 M11) | canlı AUTH_ENABLED |
| 034 | Koç sağlayıcı Wave-3 (028 revize) | ✅ (Wave-3 M13) | ADR-028'i aşar |
| 034-revize | Koç sağlayıcı ücretsiz alternatifler | ✅ | — |
| 035 | Production Deployment Strategy | ✅ (Wave-3 M10) | Docker+Caddy (M80 statik-doğrulandı) |
| 036 | Workspace + İzin Sistemi (Aile) | ✅ (Wave-4 M39) | owner/editor/viewer |
| 037 | Workspace köprü-deseni + fail-fast | ✅ (Wave-4 M42) | ADR-036 uygular (M43 bridge) |
| 038 | PostgreSQL hibrit + RLS + dual-dialect Alembic | ✅ (Wave-7 M49-53) | dev SQLite / prod Postgres; RLS 2. savunma |
| 039 | Deploy implementasyonu (Docker+Compose+nginx/HTTPS) | ✅ kod, canlı-deploy Murat bekliyor (Wave-8 MA1-4) | ADR-035'i somutlaştırır; statik-doğrulandı |
| 040 | PWA + mobil-uyum (native yerine) | ✅ kod, canlı PWA-gate deploy bekliyor (Wave-8 MC1-2) | ADR-009/032'yi kesinleştirir; mobil=PWA |
| 041 | Kullanıcı-başına LLM kotası | ✅ | BUG #188; muhasebe BUG #234 ile ağa çıkan isteğe taşındı |
| 042 | Kullanıcı saat dilimi / para birimi / locale | ✅ (saat dilimi), 🟡 (para birimi ertelendi) | BUG #237 saat dilimini kapıya bağladı; para birimi gösterimi BUG #251 ile TRY'ye sınırlandı — çok-para-birimi bu ADR'nin açık kalan yarısı |
| 043 | Oturum sabitlemesi + token yaşam döngüsü | ✅ | P2.1'in yazılı gerekçesi (6 Ağu 2026); kanıt tablosu `tests/auth/test_adr043_oturum_sozlesmesi.py` ile denetleniyor |

## Tutarlılık turu bulguları (M89)
- **Superseded zincirleri tutarlı:** ADR-028 → 034 (dosyada "SUPERSEDED by ADR-034" notu var, M75); ADR-004 sıra
  → 034 revize; ADR-011 → 029 güncelleme; ADR-019 vizyon → 031 uygulama. Hepsi ilgili dosyalarda referanslı.
- **ADR-032 (mobil) TASLAK → ADR-040 ile KESİNLEŞTİ (Wave-8):** Wave-6'da mobil KAPSAM DIŞI'ydı (taslak doğru). Wave-8
  ÜRÜN-DNA'sı mobili PWA olarak kapsam-içine aldı → ADR-040 (mobil=PWA, native kapsam-dışı) kararı verdi.
- **ADR-027 REDDEDİLDİ — DOĞRU:** "structured output yapma" kararı; kod structured-output kullanmıyor (tutarlı).
- **Kod-tutarlılık (M85 çapraz-doğrulama):** çekirdek ADR'ler kanıtlı-uygulanmış — 001 (rules_engine LLM-çağrısız),
  013 (create_all kaldırıldı), 030 (Numeric canlı), 036/037 (workspace scope Wave-5'te kilitlendi). Çelişki bulunmadı.
- **Çelişki YOK:** hiçbir yürürlükteki ADR bir diğeriyle çelişmiyor (aşılanlar açıkça işaretli).

## Not
Bu index elle kürasyon; yeni ADR eklenince buraya satır eklenmeli. 39 dosya = mimari hafızanın tam repo-envanteri
(BORÇ #3 kapandı, M74). Detaylı gerekçeler ilgili `adr-XXX-*.md` dosyalarında.

## Ek (7 Ağu 2026)
- **ADR-044 — Para biçimlendirme tek kaynak (H4 / BUG #256):** `app/money_format.py` +
  `frontend/src/lib/money.js` tek kaynak; TRY kilidi bilinçli + fail-fast; **grounding para
  birimine bağlandı** (etiket değişince doğrulama sessiz-yeşile düşüyordu) ve "etiketsiz tutar"
  artık kırmızı. Statik kapı: `tests/test_para_birimi_kapisi.py` (kapsam tabanı + muafiyet tavanı).
- **ADR-045 — Prompt enjeksiyonuna karşı YAPI savunması (H9 / BUG #257):** kullanıcı verisi koç
  bağlamının bölümlemesini değiştiremez (`app/prompt_safety.guvenli_metin`); sansür değil yapı
  nötrleme. Sınıf taraması kalıcı yolu da kapattı (insight → prompt → insight). Kapı:
  `tests/test_prompt_injection_kapisi.py` (kapsam tabanı + mutasyon).
- **ADR-046 — Kategori kullanıcıya ait bir KAYITTIR (H4 kuyruğu / BUG #264):** kod hiçbir kararı
  kategori ADINA bağlamaz; `kart_varsayilani` (harcama karta mı yazılsın) ve `sistem` (muhasebe
  işlemi mi) bayrakları `app/category_rules.py` üzerinden okunur. `Transaction.category` bilinçli
  olarak serbest metin kalır (FK, bilinmeyen kategoride kaydı reddetmeye zorlardı). Silme = hedefe
  taşı ya da gizle; sistem kategorisi silinemez. Kapı: `tests/test_kategori_kapisi.py` (backend +
  frontend aynası, kapsam tabanı + muafiyet tavanı).
- **ADR-047 — Uygulamanın İKİ görünümü vardır; ikisi de RENDER EDİLEREK ölçülür (BUG #265):**
  koyu/açık tema ve 390px telefon genişliği tek bir kapıyla ölçülür — metin kontrastı ≥ 3:1,
  yatay taşma yok, dokunma hedefi ≥ 44px (iki yazılı istisna), konsol hatası yok. Grafik renkleri
  tek kaynakta (`frontend/src/lib/grafikRenkleri.js`) ve **iki temada da** ≥ 3:1. **ADR-010'un
  "global class kalıcıdır" gerekçesini düzeltir:** kalıcılığı sağlayan sınıf değil, sınıfı
  kullanmayanı da yakalayan ölçümdür. Kapı: `frontend/e2e/tema-mobil.spec.js` (mutasyon 3/3).
