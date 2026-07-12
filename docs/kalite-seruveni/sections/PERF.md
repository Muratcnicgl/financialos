# Performans (kod: PERF)

> DATA/BE/FE bölümlerindeki bazı maddeler performans lensinden burada. Tek-kullanıcı MVP'de çoğu düşük etkili ama ucuz; mobil/çok-veri geldiğinde kritikleşir. Önce profille, sonra optimize et.

### [PERF-001] `generate_cockpit` her chat çağrısında yeniden üretiliyor — cache yok
- **Sorun/Fırsat:** Her koç mesajı tüm hesap/işlem/PnL/checkpoint sorgusu + hesap yapıyor; 10sn içinde 3 mesaj = 3 tam tarama.
- **Kanıt:** `app/coach.py:1564-1566`, `525-527`
- **Aksiyon:** Kısa TTL (10sn) memoize, key = user_id + son değişiklik ts; pending onayında invalidate. (LLM-033)
- **Etki:** Orta · **Efor:** S

### [PERF-002] `approve_action` tek istekte `generate_cockpit`'i 2 kez çağırıyor
- **Kanıt:** `app/routers/actions.py:239,264`
- **Aksiyon:** Before için hafif skaler hesap veya pending'ten türet; iki tam tarama yerine bir. (BE-036)
- **Etki:** Orta · **Efor:** S

### [PERF-003] `ReasoningTrace` chat başına N commit — SQLite yazma kilidi
- **Kanıt:** `app/reasoning_trace.py:168-171`; chat başına 6-8 step
- **Aksiyon:** Bellekte biriktir, sonda tek commit/flush. (BE-023)
- **Etki:** Orta · **Efor:** M

### [PERF-004] Frontend her mutasyonda tam refetch (refetch-all)
- **Sorun/Fırsat:** Tek gelir toggle'ı incomes+expenses+debts+accounts hepsini yeniden çekiyor.
- **Kanıt:** `frontend/src/panels/IncomeDebt.jsx:116-165`; `Transactions.jsx:138-152`
- **Aksiyon:** Optimistic local update veya TanStack Query selective invalidation. (FE-014/015)
- **Etki:** Orta · **Efor:** M

### [PERF-005] Kod-splitting yok — 10 panel + recharts tek bundle
- **Kanıt:** `App.jsx:11-20`; `vite.config.js:21-24` (manualChunks yok)
- **Aksiyon:** `React.lazy`+`Suspense`; recharts/lucide vendor chunk. İlk paint hızlanır. (FE-009)
- **Etki:** Orta · **Efor:** M

### [PERF-006] recharts ağır ve sadece 2 panelde — ilk yüklemeye biniyor
- **Kanıt:** `Reports.jsx:7-10`, `Cashflow.jsx` (recharts); tüm kullanıcıya iniyor
- **Aksiyon:** Reports/Cashflow lazy; recharts dynamic import.
- **Etki:** Orta · **Efor:** S

### [PERF-007] Cockpit `load()` her açılışta 2 POST (trigger-due) — gereksiz yazma
- **Kanıt:** `Cockpit.jsx:42-47`
- **Aksiyon:** trigger'ı görünümden ayır; salt-okuma yükleme. (FE-011/API-008)
- **Etki:** Orta · **Efor:** M

### [PERF-008] `useBackendHealth` 5sn sonsuz polling — dakikada 12 istek
- **Kanıt:** `App.jsx:54-81`
- **Aksiyon:** visibilitychange ile kıs veya 15-30sn. (FE-012)
- **Etki:** Düşük · **Efor:** S

### [PERF-009] Coach mesajları her render'da yeniden markdown parse
- **Kanıt:** `Coach.jsx:448-454,544-548`
- **Aksiyon:** `React.memo`+`useMemo`. (FE-016)
- **Etki:** Orta · **Efor:** S

### [PERF-010] FK/filtre kolonlarında index eksik — join/lookup tam tarama
- **Kanıt:** `app/models.py:211,367,817` (indekssiz FK)
- **Aksiyon:** Sık join edilen FK'lara index; `EXPLAIN QUERY PLAN` ile doğrula. (DATA-012)
- **Etki:** Düşük · **Efor:** S

### [PERF-011] PK'larda redundant `index=True` — yazma maliyeti
- **Kanıt:** `app/models.py` 18 tablo
- **Aksiyon:** Kaldır. (DATA-006)
- **Etki:** Düşük · **Efor:** S

### [PERF-012] N+1 sorgu riski — ORM lazy relationship'ler döngüde
- **Sorun/Fırsat:** Hesap→işlem, goal→allocation gibi ilişkiler döngüde erişiliyorsa her iterasyon ayrı sorgu.
- **Kanıt:** `app/rules_engine.py` (accounts/transactions iterasyonu); `goal_engine.py` allocation toplama
- **Aksiyon:** `selectinload`/`joinedload` ile eager load; EXPLAIN ile N+1 tespit.
- **Etki:** Orta · **Efor:** M

### [PERF-013] SQLite WAL/pragma yok — eşzamanlı okuma/yazma yavaş + lock
- **Kanıt:** `app/database.py:25-29`
- **Aksiyon:** `journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout`, `cache_size`. (DATA-004)
- **Etki:** Orta · **Efor:** S

### [PERF-014] Connection pool ayarı yok (default) — çok worker/istekte yetersiz
- **Kanıt:** `app/database.py` create_engine (pool param yok)
- **Aksiyon:** `pool_pre_ping=True`, uygun `pool_size`/`max_overflow` (async'e geçerken BE-007 ile).
- **Etki:** Düşük · **Efor:** S

### [PERF-015] Cockpit/coach yanıt payload'ı büyük — full snapshot taşınıyor
- **Kanıt:** `routers/coach.py:73-78` (cockpit_snapshot)
- **Aksiyon:** Over-fetching'i kes (API-015/SEC-030); gzip response middleware.
- **Etki:** Düşük · **Efor:** S

### [PERF-016] gzip/br compression yok
- **Kanıt:** `app/main.py` (GZipMiddleware yok)
- **Aksiyon:** `GZipMiddleware(minimum_size=1000)`; JSON payload'ları küçülür.
- **Etki:** Düşük · **Efor:** S

### [PERF-017] `reports.py` projeksiyonu ağır döngü + rules_engine ile çift hesap
- **Kanıt:** `app/routers/reports.py:141-236`
- **Aksiyon:** Tek yerde hesapla (BE-030); gerekiyorsa memoize.
- **Etki:** Düşük · **Efor:** M

### [PERF-018] Sync SQLAlchemy + AsyncIOScheduler event loop'u blokluyor
- **Kanıt:** `app/scheduler.py:144-169` (async job içinde sync DB)
- **Aksiyon:** run_in_executor/threadpool; loop bloklanmasın (istek latency'sini korur). (BE-007)
- **Etki:** Orta · **Efor:** M

### [PERF-019] Fiyat çekme (TEFAS/yfinance) senkron + dış ağ — endpoint'i bloklar
- **Kanıt:** `requirements.txt` (tefas-crawler, yfinance, borsapy); `fund_tracker`
- **Aksiyon:** Fiyat güncellemeyi background task/scheduler'a al; endpoint cache'ten okusun (Account.current_price zaten cache).
- **Etki:** Düşük · **Efor:** M

### [PERF-020] Prod build sourcemap açık — build boyutu/süre
- **Kanıt:** `vite.config.js:22-24`
- **Aksiyon:** `sourcemap:false`/`'hidden'` (FE-032); ayrıca `build.target` ve minify kontrolü.
- **Etki:** Düşük · **Efor:** S

---
**Kaynaklar:** SQLAlchemy N+1/eager loading; SQLite WAL & pragma tuning; Vite code-splitting/manualChunks; React memo; FastAPI GZipMiddleware.
