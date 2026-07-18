# Dokümantasyon & DX (kod: DOCS)

### [DOCS-001] `wave3-vision.md` ADR-001 yasaklı ifadeyi içeriyor — temizlenmeli
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Sorun/Fırsat:** ADR-001 ile yasaklanan kişi ismi bu dokümanda ("... mimarisi", "... Murat'ın vizyonu" başlıkları ve tablo) geçiyor. Proje kuralı ihlali; commit/docstring/kod dışı olsa da tutarlılık için düzeltilmeli.
- **Kanıt:** `docs/architecture/wave3-vision.md:473,475-476,481,485` civarı (yasaklı ifade)
- **Aksiyon:** Yasaklı ifadeyi ADR-001'in tam onaylı ifadesiyle değiştir; kelimeyi metinden çıkar.
- **Etki:** Orta · **Efor:** S

### [DOCS-002] `dev-commands.md` "pytest kullanılmıyor" derken olgun pytest suite var
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Kanıt:** `docs/dev-commands.md` "Test Scriptleri" vs `tests/` (16 dosya, conftest, .pytest_cache)
- **Aksiyon:** İki-katmanlı gerçeği yaz: `tests/` pytest + kök legacy smoke; hedef tam geçiş. (TEST-002)
- **Etki:** Orta · **Efor:** S

### [DOCS-003] ADR dizini eksik/dağınık — ADR-001..024 referanslı ama dosyalar yok
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Sorun/Fırsat:** Kod/commit ADR-001, ADR-012, ADR-013 vb. atıfları var ama `docs/architecture/` altında sadece `adr-025-goal-engine.md` mevcut. Kararların kaynağı izlenemiyor.
- **Kanıt:** `docs/architecture/adr-025-goal-engine.md` tek ADR; git log "ADR-025"; kod içi ADR atıfları
- **Aksiyon:** `docs/architecture/adr/` klasörü; geçmiş kararları retroaktif kısa ADR'lere dök (en azından atıf yapılan ADR-001/012/013).
- **Etki:** Orta · **Efor:** M

### [DOCS-004] CHANGELOG yok — BUG #NNN geçmişi koda dağılmış
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Sorun/Fırsat:** BUG #001..#058 düzeltmeleri dosya docstring'lerinde dağınık; sürüm/tarih bazlı toplu geçmiş yok.
- **Kanıt:** 19 dosyada `BUG #NNN` (159 atıf); CHANGELOG yok
- **Aksiyon:** `CHANGELOG.md` (Keep a Changelog formatı); BUG geçmişini sürümlere topla. (DEVOPS-020)
- **Etki:** Düşük · **Efor:** M

### [DOCS-005] Provider listesi belgeler arası tutarsız
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Sorun/Fırsat:** README (Groq/Cerebras/Gemini/OpenRouter) vs PROJE.md/architecture.md (gemini/anthropic/groq/fallback) vs kod (6 provider). Yeni geliştirici/agent yanlış model kurar.
- **Kanıt:** `README.md:54-63` vs `docs/dev-commands.md` .env şeması vs `app/coach.py` provider'lar
- **Aksiyon:** Tek doğruluk kaynağı (kod/Settings) + belgeleri senkronla.
- **Etki:** Orta · **Efor:** S

### [DOCS-006] Docstring/type hint kapsamı düşük — karmaşık fonksiyonlar belgesiz
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Kanıt:** `app/rules_engine.py`, `app/coach.py` (uzun fonksiyonlar, kısmi docstring); tip ipuçları eksik (DATA-031)
- **Aksiyon:** Kritik hesap fonksiyonlarına (finansal formüller) docstring + tip; "neden bu formül" gerekçesi.
- **Etki:** Düşük · **Efor:** M

### [DOCS-007] CONTRIBUTING/geliştirme rehberi yok
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Kanıt:** repo (CONTRIBUTING.md yok)
- **Aksiyon:** CONTRIBUTING.md: kurulum, test, BUG #NNN konvansiyonu, ADR-001 kuralı, commit stili. (PROJE.md'ler var ama insan-odaklı rehber ayrı.)
- **Etki:** Düşük · **Efor:** S

### [DOCS-008] API dokümantasyonu (OpenAPI) zayıf — endpoint özet/örnek eksik
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Kanıt:** `app/routers/*` (summary/tags/örnek tutarsız); `/docs` üretilen sözleşme
- **Aksiyon:** Endpoint meta zenginleştir (API-014); üretilen OpenAPI'yi tek API referansı yap.
- **Etki:** Düşük · **Efor:** M

### [DOCS-009] Mimari diyagram güncelliği — README diyagramı "6 panel/35 endpoint" diyor, gerçek 10+ panel/17 router
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Kanıt:** `README.md:37,93-110` ("6 panel", "35 endpoint", "11 router") vs gerçek (17 router, 10+ panel, goal/premortem/simulation)
- **Aksiyon:** README mimari bölümünü güncelle; panel/endpoint/router sayılarını otomatik türetmeyi düşün.
- **Etki:** Düşük · **Efor:** S

### [DOCS-010] Kök vizyon ("Sovereign OS"→FinancialOS evrimi) belgelenmemiş
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Sorun/Fırsat:** Projenin nereden geldiği (yerel Qwen 2.5, Streamlit, /api/coach) hiçbir belgede yok; karar bağlamı kayıp.
- **Kanıt:** Gemini kök sohbetleri (repo dışı); `docs/` başlangıç vizyonu içermiyor
- **Aksiyon:** `docs/architecture/origin-vision.md` — atanın özeti ve bugüne evrim (kullanıcı aktarımından).
- **Etki:** Düşük · **Efor:** S

### [DOCS-011] setup/onboarding netliği — ilk çalıştırma adımları dağınık
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Kanıt:** README + dev-commands.md + PROJE.md'lerde tekrar/farklılık
- **Aksiyon:** Tek "Getting Started" (5 dk kurulum); DEVOPS-014 task runner'a bağla.
- **Etki:** Düşük · **Efor:** S

### [DOCS-012] `data/` runtime dizini ve DB şeması belgelenmemiş
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Kanıt:** `.gitignore` data/ hariç; şema `models.py`'de ama ER diyagramı/tablo açıklaması yok
- **Aksiyon:** `docs/architecture/data-model.md` (tablolar, ilişkiler, para/timezone konvansiyonu — DATA bölümü kararlarını yansıt).
- **Etki:** Düşük · **Efor:** M

### [DOCS-013] Bu backlog'un kendisi karar kaydına bağlanmalı (izlenebilirlik)
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Sorun/Fırsat:** 500+ madde üretildi; uygulananların ADR/commit'e bağlanması gerekir yoksa tekrar keşfedilir.
- **Kanıt:** `docs/kalite-seruveni/` (bu çalışma)
- **Aksiyon:** Uygulanan her maddeyi commit mesajında `[BE-001]` gibi ID ile referansla; backlog'da durum güncelle.
- **Etki:** Orta · **Efor:** S

### [DOCS-014] Türkçe/İngilizce README senkron değil olabilir
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Kanıt:** `README.md` + `README.tr.md` (ikisi ayrı bakım)
- **Aksiyon:** İki README'yi senkron tut veya birini kaynak yapıp diğerini türet; sürüklenmeyi CI'da kontrol et.
- **Etki:** Düşük · **Efor:** S

### [DOCS-015] Finansal formül/konvansiyon sözlüğü yok (reel bütçe, zikzak, emanet, görülen vs tam net değer)
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Sorun/Fırsat:** Alan-özel terimler kod ve UI'da var ama tanımlı tek yer yok; UX-034 mikro-kopya tutarsızlığının da kaynağı.
- **Kanıt:** `rules_engine.py` (reel_butce, shadow accounting); UI etiketleri
- **Aksiyon:** `docs/glossary.md` — her terimin tanımı + formülü + hangi modülde. UX kopyası buna dayansın.
- **Etki:** Orta · **Efor:** S

---
**Kaynaklar:** ADR (Michael Nygard); Keep a Changelog; Diátaxis (doküman türleri); OpenAPI; README best practices.
