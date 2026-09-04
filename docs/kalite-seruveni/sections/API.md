# API tasarımı & sözleşme (kod: API)

> BE/SEC bölümleriyle bazı noktalar örtüşür; burada API-sözleşme lensinden. Türkçe alan adları korunur.

### [API-001] API versiyonlama yok — mobile/breaking-change kırılganlığı
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: /api/v1/ yok
- **Sorun/Fırsat:** Tüm router'lar `/api/<konu>` prefix'i kullanıyor, versiyon yok. Mobile app yayınlanınca eski istemcileri kırmadan şema değiştirmek imkânsız.
- **Kanıt:** `app/main.py` router kayıtları (`prefix="/api/..."`); `docs/architecture/mobile-roadmap.md` versiyonlama ihtiyacını not ediyor
- **Aksiyon:** `/api/v1/` prefix'ine geç (FastAPI APIRouter nesting); ADR ile "v1 sözleşmesi donuk" kararı. Yeni alanlar additive, kaldırma deprecation ile.
- **Etki:** Yüksek · **Efor:** M

### [API-002] Liste endpoint'lerinde pagination yok — tüm veri tek yanıtta
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: bazı list limit aldı ama accounts/debts sınırsız, cursor yok
- **Sorun/Fırsat:** transactions/accounts/debts/coach history tüm kayıtları döner; veri büyüdükçe mobil/yavaş ağda payload şişer.
- **Kanıt:** `app/routers/transactions.py`, `debts.py`, `accounts.py` list endpoint'leri (limit/offset yok)
- **Aksiyon:** `limit`/`offset` (veya cursor) + toplam sayı; makul default (örn. 50). Coach history zaten limit'li — onu standarda taşı.
- **Etki:** Orta · **Efor:** M

### [API-003] Tutarsız hata gövdesi — RFC 9457 problem+json yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: RFC 9457 problem+json yok, hatalar karışık
- **Sorun/Fırsat:** Hatalar bazen `{"detail":...}`, bazen 200 içinde `reply`, bazen `{"success":false,"error":...}`. İstemci tek tip hata parse edemiyor.
- **Kanıt:** `app/routers/coach.py:306-313`; `app/action_executor.py:255-335`; FastAPI default `detail`
- **Aksiyon:** Merkezî exception handler + RFC 9457 `application/problem+json` (type/title/status/detail). Tüm hatalar tek şema.
- **Etki:** Yüksek · **Efor:** M · **Not:** BE-009/BE-011 ile aynı kök.

### [API-004] `/api/coach/chat` hata durumunda HTTP 200 dönüyor — sözleşme ihlali
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: chat provider hatasında 200 döner
- **Sorun/Fırsat:** İstemci başarı sanır, retry/hata UX'i kuramaz, monitoring 5xx görmez.
- **Kanıt:** `app/routers/coach.py:306-313`
- **Aksiyon:** Gerçek hatada 4xx/5xx + problem+json; başarılı ama "koç meşgul" durumunu ayrı alanla belirt.
- **Etki:** Yüksek · **Efor:** S

### [API-005] response_model tutarsız — bazı endpoint'ler ham dict döner
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: response_model tutarsız (transactions dict vs accounts model)
- **Sorun/Fırsat:** OpenAPI şeması eksik/yanlış; frontend sözleşmesi belirsiz; alan adı değişince sessiz kırılma.
- **Kanıt:** `app/routers/transactions.py:196` (dict), `cockpit.py:53` (`-> dict`) vs `accounts.py:89` (response_model)
- **Aksiyon:** Her endpoint'e `response_model`; `TransactionRead`, genişletilmiş `CockpitSnapshot`. `use_enum_values` ile enum serialize.
- **Etki:** Orta · **Efor:** M

### [API-006] Bulk/sync endpoint yok — mobile offline sync imkânsız
- **Durum:** ⏸️ KAPSAM DIŞI — M85 R3 doğrulama: bulk/sync offline-first mobil (Wave-6 mobil kapsamı)
- **Sorun/Fırsat:** Her mutasyon tek istek; offline-first mobile için "birden çok değişikliği tek istekte gönder + son sync'ten beri değişenleri al" yok.
- **Kanıt:** `app/routers/*` (tekil CRUD); mobile-roadmap.md sync ihtiyacı
- **Aksiyon:** `POST /api/v1/sync` (pending changes + last_sync_ts → uygulanan + sunucu değişiklikleri). `updated_at`/soft-delete ön koşul (DATA-014/015).
- **Etki:** Orta · **Efor:** L

### [API-007] Idempotency-Key desteği yok — retry çift işlem üretebilir
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: Idempotency-Key yok
- **Sorun/Fırsat:** Ağ retry'ında `actions/execute` veya transaction create iki kez çalışabilir.
- **Kanıt:** `app/routers/actions.py`, `transactions.py` POST'lar
- **Aksiyon:** `Idempotency-Key` header + kısa süreli sonuç cache; pending status geçişini atomik tek-yön (SEC-023).
- **Etki:** Orta · **Efor:** M

### [API-008] HTTP metod semantiği: durum değiştiren GET riski
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: trigger-due POST oldu ama GET cockpit snapshot yazıyor
- **Sorun/Fırsat:** Cockpit yükleme sırasında POST trigger-due tetikleniyor (yan etki); ayrıca bazı "işlem" akışları REST semantiğine oturmuyor.
- **Kanıt:** `frontend/src/panels/Cockpit.jsx:42-47` (load içinde POST); `app/routers/incomes.py`/`expenses.py` triggerDue
- **Aksiyon:** Okuma (GET) yan etkisiz olsun; trigger'ı ayrı açık POST akışına al (FE-011 ile).
- **Etki:** Orta · **Efor:** M

### [API-009] PATCH yok — kısmi güncelleme PUT ile tam-nesne zorunlu
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: goals PATCH var ama accounts/debts PATCH yok
- **Sorun/Fırsat:** Tek alan (örn. hesap adı) değiştirmek için tüm nesne gönderiliyor; eşzamanlı yazımda alan ezme riski.
- **Kanıt:** `app/routers/accounts.py`, `debts.py` PUT endpoint'leri
- **Aksiyon:** `PATCH` + `exclude_unset` (Pydantic) ile kısmi güncelleme.
- **Etki:** Düşük · **Efor:** M

### [API-010] HTTP cache header'ları / ETag yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: ETag/Cache-Control yok
- **Sorun/Fırsat:** Cockpit/list yanıtları her istekte tam gönderiliyor; `ETag`/`Last-Modified` ile 304 tasarrufu yok.
- **Kanıt:** `app/routers/cockpit.py`, `main.py` (cache middleware yok)
- **Aksiyon:** Değişmeyen kaynaklara `ETag`+`If-None-Match`→304; cockpit için kısa `Cache-Control`.
- **Etki:** Düşük · **Efor:** M

### [API-011] Payload `Dict[str, Any]` — zayıf sözleşme, OpenAPI'de opak
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: payload Dict[str,Any], discriminated-union yok
- **Sorun/Fırsat:** propose/execute payload'ları `Dict[str,Any]`; OpenAPI'de yapısı görünmez, istemci sözleşmesi yok.
- **Kanıt:** `app/routers/coach.py:61`; `app/coach.py:358-360`
- **Aksiyon:** action_type'a göre discriminated-union Pydantic modeli; OpenAPI'de her aksiyon şeması görünür. (SEC-031 ile)
- **Etki:** Orta · **Efor:** M

### [API-012] Tutarsız endpoint isimlendirme/çoğul-tekil
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: fiil vs kaynak isimlendirme karışık
- **Sorun/Fırsat:** Kaynak isimlendirme, alt-kaynak yolları ve fiil-tabanlı endpoint'ler karışık (REST kaynak vs RPC-stili).
- **Kanıt:** `app/routers/` (örn. actions/execute, incomes/trigger-due fiil-tabanlı) vs kaynak-tabanlı accounts
- **Aksiyon:** Konvansiyon belirle (kaynak çoğul, alt-kaynak nested); fiil-gerektiren işlemleri `POST /resource/{id}/actions` deseniyle tutarlılaştır.
- **Etki:** Düşük · **Efor:** M

### [API-013] Doğrulama hatası yanıtı frontend'e uygun değil (alan-bazlı değil)
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: RequestValidationError handler yok
- **Sorun/Fırsat:** Pydantic 422 detay dizisi frontend'e ham geliyor; form alan-bazlı hata gösterimi zor.
- **Kanıt:** FastAPI default `RequestValidationError`; frontend `api.js` `ApiError` genel yakalıyor
- **Aksiyon:** `RequestValidationError` handler'ı alan→mesaj haritasına normalize et (problem+json `errors`).
- **Etki:** Düşük · **Efor:** S

### [API-014] OpenAPI dokümantasyon kalitesi düşük (özet/örnek/etiket eksik)
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: tags var ama summary/response örnekleri yok
- **Sorun/Fırsat:** Endpoint'lerde `summary`/`description`/`tags`/örnek eksik; `/docs` üretilen sözleşme zayıf (ayrıca prod'da açık — SEC-015).
- **Kanıt:** `app/routers/*` decorator'ları (tags/summary tutarsız)
- **Aksiyon:** Her endpoint'e tags+summary+response örnekleri; `openapi_tags` meta. İstemci/mobil ekip için sözleşme netliği.
- **Etki:** Düşük · **Efor:** M

### [API-015] `include_cockpit` gibi geniş yanıt — over-fetching
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: include_cockpit default True, opt-in değil
- **Sorun/Fırsat:** Coach yanıtı tam cockpit snapshot'ı taşıyor; istemci zaten `/api/cockpit` çağırıyor → çift veri, gereksiz payload.
- **Kanıt:** `app/routers/coach.py:73-78`
- **Aksiyon:** Varsayılanı kapat; istemci opt-in ile istesin (`?include=cockpit`). (SEC-030 ile)
- **Etki:** Düşük · **Efor:** S

### [API-016] Tarih alanları serileştirmede `Z`/`+00:00` suffix garantisi endpoint-bazlı
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: serializers.py UtcDateTime merkezîleşti
- **Sorun/Fırsat:** Bazı endpoint'ler suffix'siz ISO döner → frontend 3 saat kayması (tekrarlayan bug sınıfı).
- **Kanıt:** `app/PROJE.md` datetime kuralı; `_memory_to_history_item` referans; diğer endpoint'lerde uygulama tutarsız
- **Aksiyon:** Ortak serialize helper (tüm datetime alanlarına `tzinfo=utc`); response_model'de `field_serializer`. (TEST-031 ile doğrula)
- **Etki:** Orta · **Efor:** S

### [API-017] Rate-limit/quota bilgisi standart header ile dönmüyor
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: X-RateLimit-*/Retry-After header yok
- **Sorun/Fırsat:** Coach usage bilgisi gövdede özel alanla; standart `X-RateLimit-*`/`Retry-After` yok, istemci genel davranış kuramaz.
- **Kanıt:** `app/routers/coach.py:153-178` (usage gövdede)
- **Aksiyon:** Rate-limit (SEC-004) eklenince `X-RateLimit-Remaining`/`Retry-After` header'ları.
- **Etki:** Düşük · **Efor:** S

### [API-018] Silme yanıtı tutarsız — 200 vs 204 vs gövde
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: DELETE hepsi 204, engelde 409 tutarlı
- **Sorun/Fırsat:** DELETE endpoint'leri farklı dönüşler; ayrıca bağlı kayıt varken 500 (BE-039).
- **Kanıt:** `app/routers/accounts.py:194-221`, `transactions.py`, `debts.py`
- **Aksiyon:** Başarılı silme 204 (veya soft-delete için 200+durum); engel varsa 409 problem+json.
- **Etki:** Düşük · **Efor:** S

### [API-019] Health/readiness ayrımı yok — orkestrasyon/uptime için yetersiz
- **Durum:** ✅ KAPANDI — 5 Eyl 2026 ölçümü: ayrım **BUG #247 (D39)** ile yapılmış ve kodda gerekçesiyle yazılı. `app/routers/meta.py:95`: *"`/api/health` CANLILIK ölçer: süreç ayakta mı (bağımlılık yok, her zaman 200)"*; `:117` `@hazir_router.get("/api/ready")` HAZIR OLMA'yı ayrı yolda ölçer (DB/şema; **503 dönebilir** ve bu bir hata değil, ölçümün kendisidir). `main.py:359` ikisini de kimliksiz olarak bağlar. Canlıda doğrulandı: `/api/health` 200 · `/api/ready` 200. Ayrıca `components/SistemDurumu.jsx` bu ayrımı kullanıcıya bakan bir yüzeye çevirmiş durumda.
- **Sorun/Fırsat:** Tek `/api/health`; DB/scheduler/LLM hazır mı ayrı readiness yok. Deploy/mobil için liveness vs readiness gerekir.
- **Kanıt:** `app/main.py:200-206`
- **Aksiyon:** `/healthz` (liveness, minimal) + `/readyz` (DB ping, scheduler, provider config). (OBS ile)
- **Etki:** Düşük · **Efor:** S

### [API-020] Şema tek kaynak değil — router-içi ve schemas.py çift tanım OpenAPI'yi kirletiyor
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: schemas inline mükerrer (BE-020 kökü)
- **Sorun/Fırsat:** Aynı kaynağın iki şeması; OpenAPI'de mükerrer/tutarsız modeller, istemci kod üretimi bozulur.
- **Kanıt:** `app/schemas.py:19-249` vs router-içi tanımlar (BE-020)
- **Aksiyon:** Tek kaynak `schemas.py`; router'lar import etsin; ölü modelleri sil.
- **Etki:** Orta · **Efor:** M

---
**Kaynaklar:** RFC 9457 (Problem Details); REST/HTTP status semantics; FastAPI response_model/OpenAPI; API versioning & pagination best practices 2025.
