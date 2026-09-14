# Performans (kod: PERF)

> DATA/BE/FE bölümlerindeki bazı maddeler performans lensinden burada. Tek-kullanıcı MVP'de çoğu düşük etkili ama ucuz; mobil/çok-veri geldiğinde kritikleşir. Önce profille, sonra optimize et.

### [PERF-001] `generate_cockpit` her chat çağrısında yeniden üretiliyor — cache yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: generate_cockpit cache yok
- **Sorun/Fırsat:** Her koç mesajı tüm hesap/işlem/PnL/checkpoint sorgusu + hesap yapıyor; 10sn içinde 3 mesaj = 3 tam tarama.
- **Kanıt:** `app/coach.py:1564-1566`, `525-527`
- **Aksiyon:** Kısa TTL (10sn) memoize, key = user_id + son değişiklik ts; pending onayında invalidate. (LLM-033)
- **Etki:** Orta · **Efor:** S

### [PERF-002] `approve_action` tek istekte `generate_cockpit`'i 2 kez çağırıyor
- **Durum:** ✅ KAPANDI — BUG #487 (14 Eyl 2026). Ölçüldü: onay ucu tam kokpiti iki kez üretiyor (~40 sorgu, koç sinyalleri, nakit takvimi, alacak yaşlandırma…), sonuçtan yalnız `net_deger` ve `nakit_kasa` okuyordu. `rules_engine.hizli_bakiye_ozeti`: tek hesap sorgusu, aynı toplama kuralları (nakit / kart / kredi / lot×fiyat, emanet hariç) ve aynı net-değer formülü (`balance_rules.net_worth_seen`). Ölçüm (6 hesaplık bellek DB): kokpit 12,8 ms, hızlı özet 0,23 ms — **55×**; onay isteğinde iki çağrı → ~25 ms kazanç, canlı DB'de (daha çok tablo) daha fazla. Kapı `tests/test_hizli_bakiye_ozeti_kapisi.py`: beş hesap tipinde kokpitle kuruş eşitliği (kopya sürüklenirse kırılır), tek SELECT, onay ucu `generate_cockpit` çağırmaz.
- **Kanıt:** `app/rules_engine.py::hizli_bakiye_ozeti`, `app/routers/actions.py`
- **Aksiyon:** Before için hafif skaler hesap veya pending'ten türet; iki tam tarama yerine bir. (BE-036)
- **Etki:** Orta · **Efor:** S

### [PERF-003] `ReasoningTrace` chat başına N commit — SQLite yazma kilidi
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: reasoning_trace her step commit
- **Kanıt:** `app/reasoning_trace.py:168-171`; chat başına 6-8 step
- **Aksiyon:** Bellekte biriktir, sonda tek commit/flush. (BE-023)
- **Etki:** Orta · **Efor:** M

### [PERF-004] Frontend her mutasyonda tam refetch (refetch-all)
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: IncomeDebt tam refetch
- **Sorun/Fırsat:** Tek gelir toggle'ı incomes+expenses+debts+accounts hepsini yeniden çekiyor.
- **Kanıt:** `frontend/src/panels/IncomeDebt.jsx:116-165`; `Transactions.jsx:138-152`
- **Aksiyon:** Optimistic local update veya TanStack Query selective invalidation. (FE-014/015)
- **Etki:** Orta · **Efor:** M

### [PERF-005] Kod-splitting yok — 10 panel + recharts tek bundle
- **Durum:** ✅ KAPANDI — BUG #486 (14 Eyl 2026). Ölçüldü (`npm run build`): ÖNCE tek parça **1.113 kB** JS (13 panel + recharts ilk boyaya biniyordu). SONRA ilk yük ≈ index 183 + react 133 + lucide 27 kB (**−68 %**); recharts 443 kB ayrı parçada ve `modulepreload` listesinde YOK — kokpitteki tek tüketici (`AylikSeri`) tembel. Kokpit statik (ilk ekran), diğer 11 panel `lazy()` + `Suspense` ("Panel yükleniyor…", `role=status`); vite `manualChunks`: recharts/d3, react/react-dom/scheduler, lucide. PWA precache parçaları otomatik alır (workbox glob). Yan bulgu: altbilgi **"v0.1.0"** sabitti (sürüm 0.3.0'dayken) → `/api/meta`'dan sürüm + build damgası. Kapı `frontend/src/kod-bolme.test.jsx` (kaynak: 11 lazy panel, Suspense sarmalı, manualChunks, kokpit recharts tembel, altbilgi sabit değil); usage-loop e2e izole koşumda 2/2.
- **Kanıt:** `App.jsx:11-20`; `vite.config.js:21-24` (manualChunks yok)
- **Aksiyon:** `React.lazy`+`Suspense`; recharts/lucide vendor chunk. İlk paint hızlanır. (FE-009)
- **Etki:** Orta · **Efor:** M

### [PERF-006] recharts ağır ve sadece 2 panelde — ilk yüklemeye biniyor
- **Durum:** ✅ KAPANDI — BUG #486 (14 Eyl 2026). Ölçüldü (`npm run build`): ÖNCE tek parça **1.113 kB** JS (13 panel + recharts ilk boyaya biniyordu). SONRA ilk yük ≈ index 183 + react 133 + lucide 27 kB (**−68 %**); recharts 443 kB ayrı parçada ve `modulepreload` listesinde YOK — kokpitteki tek tüketici (`AylikSeri`) tembel. Kokpit statik (ilk ekran), diğer 11 panel `lazy()` + `Suspense` ("Panel yükleniyor…", `role=status`); vite `manualChunks`: recharts/d3, react/react-dom/scheduler, lucide. PWA precache parçaları otomatik alır (workbox glob). Yan bulgu: altbilgi **"v0.1.0"** sabitti (sürüm 0.3.0'dayken) → `/api/meta`'dan sürüm + build damgası. Kapı `frontend/src/kod-bolme.test.jsx` (kaynak: 11 lazy panel, Suspense sarmalı, manualChunks, kokpit recharts tembel, altbilgi sabit değil); usage-loop e2e izole koşumda 2/2. (PERF-005 ile birlikte.)
- **Kanıt:** `Reports.jsx:7-10`, `Cashflow.jsx` (recharts); tüm kullanıcıya iniyor
- **Aksiyon:** Reports/Cashflow lazy; recharts dynamic import.
- **Etki:** Orta · **Efor:** S

### [PERF-007] Cockpit `load()` her açılışta 2 POST (trigger-due) — gereksiz yazma
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: Cockpit acilista triggerDue POST
- **Kanıt:** `Cockpit.jsx:42-47`
- **Aksiyon:** trigger'ı görünümden ayır; salt-okuma yükleme. (FE-011/API-008)
- **Etki:** Orta · **Efor:** M

### [PERF-008] `useBackendHealth` 5sn sonsuz polling — dakikada 12 istek
- **Durum:** ✅ KAPANDI — 5 Eyl 2026: ölçüldü ve DÜZELTİLDİ. `App.jsx`'in `useBackendHealth`'i koşulsuz `setInterval(check, 5000)` kuruyordu; arka plana atılmış bir sekme **saatte 720 istek** üretiyordu ve o isteklerin bakan bir gözü yoktu (mobil/PWA hedefi olan bir üründe doğrudan pil ve veri). Yoklama artık `visibilitychange` ile gizliyken duruyor, sekme geri geldiğinde **anında** bir ölçüm yapıyor (kullanıcı bayat bir "çevrimdışı" rozeti görmesin). **Aralık DEĞİŞTİRİLMEDİ** — görünürken hâlâ 5 sn; tepkiselliği düşürmek ayrı bir karardır. Kural genelleştirildi: `tests/test_frontend_yoklama_kapisi.py` her `setInterval` yoklamasından görünürlük koruması ister (mutasyon 2/2). vitest 214/214 yeşil.
- **Kanıt:** `App.jsx:54-81`
- **Aksiyon:** visibilitychange ile kıs veya 15-30sn. (FE-012)
- **Etki:** Düşük · **Efor:** S

### [PERF-009] Coach mesajları her render'da yeniden markdown parse
- **Durum:** ✅ KAPANDI — BUG #488 (14 Eyl 2026). Ölçüldü (kapı, 5 koç mesajı): girdi kutusuna 5 tuş basışı → 15 fazladan markdown çizimi (18/3); `Message` memo değildi, `handleActionResolved` her çizimde yeni kimlik alıyordu (memo tek başına işe yaramazdı). Yapılan: `Message = memo(...)`, `handleActionResolved` `useCallback([toast])`, `preprocessMarkdown` `useMemo([text])`. Sonra: 5 tuş → 0 fazladan çizim. Sanallaştırma ⚪ (FE-034): geçmiş 50 mesajla sınırlı; memo sonrası ölçülebilir maliyet yok, react-window erken optimizasyon olurdu. Kapı `frontend/src/koc-mesaj-memo.test.jsx` (react-markdown çizim sayacı).
- **Kanıt:** `Coach.jsx:448-454,544-548`
- **Aksiyon:** `React.memo`+`useMemo`. (FE-016)
- **Etki:** Orta · **Efor:** S

### [PERF-010] FK/filtre kolonlarında index eksik — join/lookup tam tarama
- **Durum:** ✅ KAPANDI — **BUG #418 (12 Eyl 2026):** ölçüm: 16 FK sütunu tekil indekssiz; yedisi her istekte filtre/join kolonu (beş `user_id`: categories/envelopes/goals/recurring_incomes/recurring_expenses; `recurring_expenses.account_id`; `audit_log.workspace_id`) → göç `f7a8b9c0d1e2` + model `index=True`. Kalan 9 düşük trafikli tarihsel bağlantı BİLEREK bırakıldı (kapı ratchet'ler ≤ 9). Dürüst not: bugünkü ölçekte (tek kullanıcı, yüzlerce satır) hız farkı ölçülemez — hijyen ve çok-kullanıcılı büyüme önlemi; `EXPLAIN` bu yüzden koşulmadı. Göç zinciri geçici DB'de upgrade→downgrade→upgrade doğrulandı. Kapı `tests/test_fk_indeks_kapisi.py` (her user_id FK indeksli; göç adları = model adları; ratchet).
- **Kanıt:** `app/models.py:211,367,817` (indekssiz FK)
- **Aksiyon:** Sık join edilen FK'lara index; `EXPLAIN QUERY PLAN` ile doğrula. (DATA-012)
- **Etki:** Düşük · **Efor:** S

### [PERF-011] PK'larda redundant `index=True` — yazma maliyeti
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: PK redundant index=True ~18 tablo
- **Kanıt:** `app/models.py` 18 tablo
- **Aksiyon:** Kaldır. (DATA-006)
- **Etki:** Düşük · **Efor:** S

### [PERF-012] N+1 sorgu riski — ORM lazy relationship'ler döngüde
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: selectinload yok N+1 riski
- **Sorun/Fırsat:** Hesap→işlem, goal→allocation gibi ilişkiler döngüde erişiliyorsa her iterasyon ayrı sorgu.
- **Kanıt:** `app/rules_engine.py` (accounts/transactions iterasyonu); `goal_engine.py` allocation toplama
- **Aksiyon:** `selectinload`/`joinedload` ile eager load; EXPLAIN ile N+1 tespit.
- **Etki:** Orta · **Efor:** M

### [PERF-013] SQLite WAL/pragma yok — eşzamanlı okuma/yazma yavaş + lock
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: WAL+busy_timeout PRAGMA
- **Kanıt:** `app/database.py:25-29`
- **Aksiyon:** `journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout`, `cache_size`. (DATA-004)
- **Etki:** Orta · **Efor:** S

### [PERF-014] Connection pool ayarı yok (default) — çok worker/istekte yetersiz
- **Durum:** ✅ KAPANDI — 5 Eyl 2026 ölçümü: havuz ayarı **M49 (Wave-7)** ile gelmiş ve kodda maddenin numarasıyla anılıyor. `app/database.py` dialect-aware: PostgreSQL için `pool_pre_ping` (kopan bağlantı ölü-havuzu önler) + `pool_size`/`max_overflow`, ve yorumda kapasite formülü yazılı (`WEB_CONCURRENCY × (pool_size + max_overflow) + scheduler`). SQLite davranışı bilinçli olarak değiştirilmemiş (mevcut testler korunsun diye). Yani "ayar yok" iddiası, ayarın GEREKTİĞİ dialect için yanlış.
- **Kanıt:** `app/database.py` create_engine (pool param yok)
- **Aksiyon:** `pool_pre_ping=True`, uygun `pool_size`/`max_overflow` (async'e geçerken BE-007 ile).
- **Etki:** Düşük · **Efor:** S

### [PERF-015] Cockpit/coach yanıt payload'ı büyük — full snapshot taşınıyor
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: payload trim+gzip yok
- **Kanıt:** `routers/coach.py:73-78` (cockpit_snapshot)
- **Aksiyon:** Over-fetching'i kes (API-015/SEC-030); gzip response middleware.
- **Etki:** Düşük · **Efor:** S

### [PERF-016] gzip/br compression yok
- **Durum:** ✅ KAPANDI — BUG #485 (14 Eyl 2026). Ölçüldü: hiçbir yanıt gzip taşımıyordu; openapi.json 230 KB düz gidiyordu; tünel yolu (Tailscale Funnel / Cloudflare Tunnel) uygulama katmanında sıkıştırmaz. `GZipMiddleware(minimum_size=1024)`: openapi.json gzip ile 1/3'ün altına iniyor (kapı ölçer), `/api/health` gibi eşik altı yanıtlar dokunulmaz (CPU'ya değmez). Akış yanıtı yok (StreamingResponse/SSE kullanılmıyor — ölçüldü), tamponlama gecikmesi de yok. br ⚪: starlette'te yerleşik değil, ek bağımlılık ister; gzip'in üstüne kazanç kokpit ölçeğinde ölçülemez.
- **Kanıt:** `app/main.py` (GZipMiddleware), `tests/test_sikistirma_ve_tefas_kapisi.py`
- **Aksiyon:** `GZipMiddleware(minimum_size=1000)`; JSON payload'ları küçülür.
- **Etki:** Düşük · **Efor:** S

### [PERF-017] `reports.py` projeksiyonu ağır döngü + rules_engine ile çift hesap
- **Durum:** ✅ KAPANDI — BUG #442 (13 Eyl 2026): `upcoming-cashflow` kredi taksiti + düzenli gelir/gider genişletmesini `app/cashflow.py` genişleticilerinden alır (`_next_occurrences` kopyası silindi). Ölçülen ayrışmalar: kalan taksit `None` (rapor sınırsız, tahmin 0 → kredi tahminden KAYBOLUYORDU; L45 gereği None = ufukta her ay taksit, 0 = ödenmiş — tahminde düzeltildi) ve geçmiş vadeli kredi (rapor geçmiş tarihleri "yaklaşan" listeliyordu; artık RULE-016 kuralı). Belgeli fark: rapor gecikmiş alacağı gösterir, tahmin göstermez. Kapı: `tests/test_yaklasan_akis_tek_kaynak_kapisi.py` (iki uç birebir; eski kodda kırmızı).
- **Kanıt:** `app/routers/reports.py:141-236`
- **Aksiyon:** Tek yerde hesapla (BE-030); gerekiyorsa memoize.
- **Etki:** Düşük · **Efor:** M

### [PERF-018] Sync SQLAlchemy + AsyncIOScheduler event loop'u blokluyor
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: async job sync DB
- **Kanıt:** `app/scheduler.py:144-169` (async job içinde sync DB)
- **Aksiyon:** run_in_executor/threadpool; loop bloklanmasın (istek latency'sini korur). (BE-007)
- **Etki:** Orta · **Efor:** M

### [PERF-019] Fiyat çekme (TEFAS/yfinance) senkron + dış ağ — endpoint'i bloklar
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: fetch_prices arka plan (ADR-029)
- **Kanıt:** `requirements.txt` (tefas-crawler, yfinance, borsapy); `fund_tracker`
- **Aksiyon:** Fiyat güncellemeyi background task/scheduler'a al; endpoint cache'ten okusun (Account.current_price zaten cache).
- **Etki:** Düşük · **Efor:** M

### [PERF-020] Prod build sourcemap açık — build boyutu/süre
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: vite sourcemap:false
- **Kanıt:** `vite.config.js:22-24`
- **Aksiyon:** `sourcemap:false`/`'hidden'` (FE-032); ayrıca `build.target` ve minify kontrolü.
- **Etki:** Düşük · **Efor:** S

---
**Kaynaklar:** SQLAlchemy N+1/eager loading; SQLite WAL & pragma tuning; Vite code-splitting/manualChunks; React memo; FastAPI GZipMiddleware.
