# Wave-3 Backlog v1 — Kusursuzlaştırma Öncelik Haritası (M8)

**Tarih:** 13 Tem 2026 · **Milestone:** M8 · **Kaynak:** Wave-3 charter'i M8 (7 kaynak a-g; charter belgesi depoda tutulmuyor) · **Baseline:** HEAD 6abc6d2, 807 test yeşil, TOTAL coverage %86.

## Yöntem

Charter M8'in 7 kaynağı (a-g) tarandı; her aday **R3 ile diskten doğrulandı** (grep/coverage/kod okuma). İki paralel denetim ajanı + firsthand tarama birleştirildi, çakışan bulgular tekilleştirildi. Her madde: `W3-NNN` ID, kaynak (a-g), kategori (kritik/orta/düşük), süre (kısa <2h / orta / uzun), bağımlılık, açıklama.

### 7 Kaynak
- **(a)** UX-bozan bug'lar → çoğunlukla frontend (`fe__*` denetim raporları) + backend correctness (T-1..T-18).
- **(b)** Kalite Serüveni P0/P1 açık → `faz-3-durum.md`: **P1 27/27 KAPANDI**; P2 üst-yarı kapandı; kalan P2/P3 + `sections/` açık kümeleri.
- **(c)** M4 cron production → ADR-035 (→ **M10**, big-package).
- **(d)** Wave-2 charter "Wave-3'e ertelendi" → P2-1/12/13, T-17 güvenlik grubu, calibration, çift-hesap transfer.
- **(e)** MCP Improvement Backlog → açık ONERI feature'ları + #030 precommit gate.
- **(f)** `dosya-denetimi/` (75 rapor) TODO/RISK/açık → frontend gövdesi (Group C/D) + backend (Group E) + `sections/` (SEC/DATA/RESIL/…).
- **(g)** Coverage haritası (807 test %86) → `startup.py` %0, `dependencies.py` %47, `routers/expenses` %52, `goals` %58, `premortem` %61, `scheduler`/`fund_tracker` %62.

### R3 Düzeltmeleri (premise vs disk gerçeği)
- **Bug no çakışması:** Goal mesajındaki "#059 Recharts / #060 duplicate Maaş / #062 conftest" tanımları **yanlış** — gerçek #059=RULE-001 enum (kapalı), #060=SQLite PRAGMA FK (kapalı), #062=scheduler rollback (kapalı). #131-155 tamamı kapalı. Bu numaralar backlog'a AÇIK olarak alınmadı.
- **P2-1 AÇIK doğrulandı:** ilk grep (`session.query(`) yanılttı; kod `db.query(` kullanıyor → `.query(` ~183 kullanım. SQLAlchemy 2.x göçü gerçekten yapılmamış → W3-048.
- **DATA-003/004 (FK pragma) KAPALI:** `database.py:49-53` `PRAGMA foreign_keys=ON`+WAL+busy_timeout uygulanmış (BUG #060 fix). Agent-1'in "FK OFF" iddiası bayat section raporundan; disk çürüttü. **Sonuç:** FK enforce AÇIK olduğundan cascade eksikliği (W3-036) artık gerçekten kritik.
- **`create_all` ADR-013 ihlali YOK:** `main.py` startup'ta çağırmıyor; yalnız `init_db()` (setup/test) içinde. Drift riski düşük not (W3-053).

---

## BÖLÜM 1 — Büyük İş Paketleri (kendi milestone'ları, top-30-40 sayımına dahil DEĞİL)

Bunlar tek madde değil, tam milestone. Charter'da ayrı ele alınıyor; backlog'da izlenir ama M9/M14 "top 30-40" dışında.

| ID | Paket | Milestone | Kaynak | Not |
|----|-------|-----------|--------|-----|
| BIG-1 | M4 cron production (daemon, 02:45 saha doğrulama) + deployment (systemd/Docker, reverse proxy, backup, /health) | **M10** | c,f | ADR-035 karar M10'da |
| BIG-2 | Auth + Multi-user + KVKK (User modeli, JWT, OAuth, user_id migration tüm tablolar, data segregation, silme/export) | **M11** | b,d,f | ADR-033; W3-035/036 ön-koşul |
| BIG-3 | Multi-asset (BIST/altın/döviz/kripto, PriceProvider genişletme, Numeric(28,8) kararı, backfill) | **M12** | e,f | ADR-031 |
| BIG-4 | Koç sağlayıcı çeşitliliği (5+ ücretsiz provider fallback + quality-per-cost) | **M13** | d,e | ADR-034; W3-050/051 örtüşür |

---

## BÖLÜM 2 — Granüler Backlog (M9 + M14 kapsamı)

### Grup C — Frontend correctness/UX (kaynak a,f)

| ID | Kat. | Süre | Bağımlılık | Açıklama (dosya) |
|----|------|------|-----------|------------------|
| W3-001 | **kritik** | kısa | — | TR binlik format sessiz veri bozulması: `parseFloat(replace(',','.'))` "1.234,56"→ ~1000× yanlış tutar, uyarısız kaydeder (fe__IncomeDebt/Transactions) |
| W3-002 | **kritik** | kısa | — | `markPaid` tarihi `toISOString().slice(0,10)` UTC → gece 00:00-02:59'da borç bir önceki güne kaydolur (fe__api) |
| W3-003 | **kritik** | kısa | — | Dinamik Tailwind `text-${color}-600` prod build'de purge → görünmez renk (fe__Accounts, FE-002 paterni) |
| W3-004 | **kritik** | orta | — | DebtStrategy slider klavye ile değişince `handleExtraCommit` (onMouseUp/Touch) tetiklenmez → strateji güncellenmez (fe__DebtStrategy; a11y+UX) |
| W3-005 | **kritik** | kısa | — | DebtStrategy fetch hatası catch'te `data=null` → yanlış "Aktif borç yok" (fe__DebtStrategy) |
| W3-006 | **kritik** | kısa | — | PendingActions klavye y/n `editingById` kontrol etmiyor → disabled buton bypass, yanlış onay/red (fe__PendingActions) |
| W3-007 | orta | kısa | — | IncomeDebt toggle/markPaid handler'larında try/catch yok → sessiz başarısızlık, UI-DB tutarsızlığı |
| W3-008 | orta | kısa | — | RedLines `handleToggleActive` hata yakalamıyor → unhandled rejection |
| W3-009 | orta | kısa | — | PendingActions `JSON.parse(payload)` try/catch'siz → bozuk payload tüm listeyi çökertir |
| W3-010 | orta | kısa | — | Premortem/Horizons Reddet butonu `approving` sırasında aktif → aynı actionId approve+reject yarışı |
| W3-011 | orta | kısa | — | PremortemModal Escape useEffect `isOpen` bakmıyor → kapalıyken global Escape yakalar |
| W3-012 | orta | orta | — | Null/undefined prop guard yok (`trace.steps`, `sankey.nodes`, `events`) → beyaz ekran çökme (4 bileşen) |
| W3-013 | orta | kısa | — | CommandPalette klavye dinleyici sadece input'a bağlı → odak dışı Escape/ok çalışmaz |
| W3-014 | orta | kısa | — | Goals GoalDetailModal `Promise.all` reddinde eski hedef allocation/rule ekranda kalır |
| W3-015 | düşük | orta | — | AbortController yok → hızlı yenile/tab değiştir stale veri (5 panel) |
| W3-016 | düşük | kısa | — | React index-key anti-pattern (stale DOM riski, 3 bileşen) |
| W3-017 | düşük | kısa | W3-002 | `formatDate` Z-suffix normalizasyon uygulamıyor → gün kayması (api.js) |

### Grup D — Frontend erişilebilirlik (kaynak f)

| ID | Kat. | Süre | Bağımlılık | Açıklama |
|----|------|------|-----------|----------|
| W3-018 | orta | orta | — | Tüm modallarda `role="dialog"`/`aria-modal`/focus-trap/Escape/başlangıç-odak eksik (A11Y-001 sistematik, 6 modal) |
| W3-019 | orta | kısa | — | Dokunma hedefleri 44px altı (A11Y-006) |
| W3-020 | orta | kısa | — | Form label/input association + aria-invalid (A11Y-008/009) |
| W3-021 | düşük | kısa | — | Live region yok — toast/loading duyurulmuyor (A11Y-010/020) |
| W3-022 | düşük | orta | — | i18n altyapısı yok, hardcoded TR + `Intl` kullanılmıyor (A11Y-014/015) |

### Grup E — Backend correctness (kaynak a,f)

| ID | Kat. | Süre | Bağımlılık | Açıklama |
|----|------|------|-----------|----------|
| W3-023 | **kritik** | kısa | — | Faizsiz kredi: `interest_rate` boşsa faiz sessizce %0 → iyimser months_to_freedom; `assumed_interest_free` flag yok (debt_strategy; tüm test kredilerinde geçerli) |
| W3-024 | orta | kısa | — | `compare_strategies` dict döner, `goal_engine.py` nokta-erişim + `except: pass` → AttributeError sessiz yutuluyor |
| W3-025 | orta | kısa | — | Borç payoff epsilon 0.01 tutarsız `>`/`<`/`<=` → tam 0.01 kalan borç payoff'a girmeyebilir (DS-004/RULE-012) |
| W3-026 | orta | kısa | — | Borç payoff `MAX_MONTHS(600)` aşımında "bitmedi" flag yok → negatif amortizasyon "600 ayda biter" (DS-002/RULE-011) |
| W3-027 | orta | orta | — | cashflow loan taksiti hangi nakit hesaptan ödendiği modellenmemiş → tek-hesap forecast'ta ilgisiz krediler düşülüyor (CF-001) |
| W3-028 | orta | kısa | — | action_executor: "income" kredi kartı hesabına uygulanınca borç ARTIYOR (azalması gerek), borç-azaltma dalı yok (AE-005) |
| W3-029 | orta | kısa | — | action_executor `actual_price = payload.get() or current_price` → açık `0` fiyat yok sayılır (0-or-X bug) |
| W3-030 | **kritik** | kısa | — | EMANET KASA halüsinasyon filtresi sadece `[5. EMANET KASA]` birebir yakalıyor; markdown `## 5.` sızar (CO-001) |
| W3-031 | orta | kısa | — | reasoning_trace `finally` bloğunda koşulsuz commit, rollback/savepoint yok → gelecekte bozuk txn riski |
| W3-032 | orta | kısa | — | routers/accounts bağlı txn'li hesap silme → IntegrityError 500 + stack trace sızıntısı (docstring itiraf ediyor) |
| W3-033 | orta | kısa | — | goals `create_allocation` goal.status/goal_type kontrolsüz + IDOR olası (RGO-004/005/006) |

### Grup F — Veri/şema (kaynak f)

| ID | Kat. | Süre | Bağımlılık | Açıklama |
|----|------|------|-----------|----------|
| W3-034 | **kritik** | orta | BIG-2 | `Goal.user_id` nullable + GoalAllocation/Rule'da user_id YOK → multi-tenant izolasyon deliği (DATA-010/011). M11 auth ön-koşulu |
| W3-035 | orta | orta | — | Account/Transaction/Goal cascade tanımsız (DATA-013). **FK enforce AÇIK** (BUG #060) → parent silme IntegrityError; cascade/ondelete gerekli |
| W3-036 | orta | orta | — | DB CHECK constraint yok (day 1-31, priority 1-3, progress 0-100, amount<>0) (DATA-009/P2-7) |
| W3-037 | orta | orta | — | NetWorthSnapshot hâlâ Float (DATA-001/022) → Decimal göçü kalanı (Numeric(19,4)) |
| W3-038 | düşük | kısa | — | ApiCallLog retention yok (DATA-032) |

### Grup G — Güvenlik sertleştirme (kaynak b,d — T-17 prod-gate, M10/M11 besler)

| ID | Kat. | Süre | Bağımlılık | Açıklama |
|----|------|------|-----------|----------|
| W3-039 | **kritik** | kısa | — | Checkpoint hard-delete koruması sadece `priority=1 AND red_line`; MC4/5/6/8 (`type=rule`) `?hard=true` ile silinebilir (RCH-002/T-1) |
| W3-040 | **kritik** | kısa | — | CORS `allow_methods/headers=["*"]`+`credentials=True`, origin hardcoded (env değil) (SEC-003/MN-002) |
| W3-041 | **kritik** | orta | — | HTTP rate limiting hiçbir endpoint'te yok (slowapi) → brute-force/DoS; auth endpoint'e ekstra (SEC-004) |
| W3-042 | orta | orta | BIG-1 | Security header yok (HSTS/CSP/X-Frame) + HTTPS zorlaması yok + `/docs` açık (SEC-005/014/015) — reverse proxy katmanı M10 |
| W3-043 | orta | kısa | — | Ham `str(e)` / snapshot hatası kullanıcıya sızıyor — 7 router (P2-6, bilgi ifşası) |
| W3-044 | orta | orta | — | Prompt injection (kullanıcı mesajı + stored insight) SEC-007/033; dış LLM'e tam bağlam KVKK-yurtdışı (SEC-034) |
| W3-045 | orta | orta | — | At-rest şifreleme + yedek şifresiz (SEC-012/013) + sır rotasyonu yok (SEC-017) |
| W3-046 | orta | kısa | — | execute idempotency yok (SEC-023/RESIL) → çift-execute riski |

### Grup H — Kod borcu / mimari (kaynak b,d)

| ID | Kat. | Süre | Bağımlılık | Açıklama |
|----|------|------|-----------|----------|
| W3-047 | orta | uzun | — | **P2-1** `.query()` → `select()` göçü ~183 kullanım (rules_engine 31, coach_insights 20, goals 19…) kademeli (A1) |
| W3-048 | orta | uzun | — | **P2-12** `coach.py` 2555 satır god-module böl + service/repository katmanı + config merkezi (A2) |
| W3-049 | orta | orta | BIG-4 | **P2-13** LLM orkestrasyon: prompt caching, eval harness, token metriği (A3) — M13 örtüşür |
| W3-050 | orta | orta | BIG-4 | Structured output (LLM-009/020): kırılgan regex postprocess'i emekli et — M13 örtüşür |
| W3-051 | orta | orta | — | execute atomik değil + savepoint yok (RESIL-001/002) + LLM timeout yok (RESIL-007) + chat hata 200 yutma (RESIL-016/API-004) |
| W3-052 | orta | orta | — | Structured logging yok (OBS-001) + scheduler görünürlük (OBS-009) + error tracking/Sentry (OBS-012) |
| W3-053 | düşük | orta | — | `init_db()/create_all` alembic ile drift + baseline migration STAMP (boş upgrade) (E10/DB-001) |
| W3-054 | düşük | kısa | — | `app/PROJE.md:5` bayat "startup create_all" ifadesi düzelt (kod ADR-013 uyumlu) |
| W3-055 | düşük | orta | — | Ölü kod: `parse_gg_command`+`GG_PATTERN`, `reasoning_trace.close()` no-op, schemas kalıntı (P2-2) |
| W3-056 | düşük | kısa | — | Magic number adlandırma (50.0 kart tabanı, 30-gün ay, 100_000) (P2-11) |
| W3-057 | düşük | kısa | — | TR locale: `strftime('%B')` İngilizce ay + `.lower()` sorunları → sabit ay listesi/`_TR_NORM` (P2-9) |

### Grup I — Test/coverage/süreç (kaynak e,g)

| ID | Kat. | Süre | Bağımlılık | Açıklama |
|----|------|------|-----------|----------|
| W3-058 | orta | kısa | — | **ONERI #030** precommit test gate (BUG #061 bundan çıktı — gizli regresyon) → süreç disiplini, yüksek değer/düşük efor |
| W3-059 | orta | orta | — | `startup.py` %0 coverage → import edilmiyor; production startup, incele + test yaz veya ölüyse kaldır (g) |
| W3-060 | orta | orta | — | Frontend test altyapısı yok (Vitest/RTL, TEST-009) + LLM eval harness (TEST-024/025) |
| W3-061 | düşük | orta | — | `dependencies.py` %47 + `routers/expenses` %52 + `goals` %58 coverage artışı (g) |
| W3-062 | düşük | orta | — | PERF: cockpit cache yok (PERF-001) + kod-splitting/recharts bundle (PERF-005) + eksik index/N+1 (PERF-010/012) |
| W3-063 | düşük | kısa | — | 20 yetim `reasoning_traces` (user_id=2) temizlik — veri, onay bekliyor (B9) |

### Grup J — Feature backlog (kaynak e — çoğu Wave-4)

| ID | Kat. | Süre | Bağımlılık | Açıklama |
|----|------|------|-----------|----------|
| W3-064 | orta | orta | — | ONERI #006 inflation_adjuster: TLY reel getiri (TR %50 enflasyon sonrası) — yüksek TR-değeri |
| W3-065 | orta | orta | — | ONERI #008 cash_flow_forecast 90 gün projeksiyon — mevcut cashflow'u derinleştir |
| W3-066 | düşük | orta | — | ONERI #005 debt_payoff_optimizer (avalanche/snowball) — debt_strategy zaten var, genişlet |
| W3-067 | düşük | uzun | — | ONERI #004/#007/#009/#010/#011/#014 çeşitli feature → Wave-4 |
| W3-068 | düşük | uzun | — | ONERI #029 AST scanner (dual-index tespiti) → Wave-4 |

---

## BÖLÜM 3 — Öncelik Sıralaması (kritik yol algoritması)

Charter M8 algoritması: kritik+kısa → kritik+orta → orta+kısa → kritik+uzun (M13/M14) → düşük+uzun (Wave-4).

### Katman 1 — Kritik + Kısa (M9 çekirdek, ilk 15'in gövdesi)
W3-001, W3-002, W3-003, W3-005, W3-006 (frontend veri/UX kritik) · W3-023, W3-030 (backend correctness kritik) · W3-039, W3-040 (güvenlik kritik-kısa)

### Katman 2 — Kritik + Orta (M9 kuyruğu / M14 başı)
W3-004 (slider) · W3-041 (rate limit) · W3-034 (multi-tenant izolasyon — M11 ön-koşul)

### Katman 3 — Orta + Kısa (M14 gövde)
W3-007, W3-008, W3-009, W3-010, W3-011, W3-013, W3-014 · W3-024, W3-025, W3-026, W3-028, W3-029, W3-031, W3-032, W3-033 · W3-019, W3-020 · W3-043, W3-046 · W3-054, W3-056, W3-057 · W3-058

### Katman 4 — Orta + Orta (M14 kuyruk / seçmeli)
W3-012, W3-018 · W3-027, W3-035, W3-036, W3-037 · W3-042, W3-044, W3-045 · W3-049, W3-050, W3-051, W3-052 · W3-059, W3-060 · W3-064, W3-065

### Katman 5 — Kritik/Orta + Uzun (dağıtık, M14 veya big-package)
W3-047 (query göçü, kademeli — M14'te başlat, Wave-4'e taşar) · W3-048 (coach.py böl — M14 veya Wave-4)

### Katman 6 — Düşük (Wave-4)
W3-015, W3-016, W3-017, W3-021, W3-022 · W3-038, W3-053, W3-055, W3-061, W3-062, W3-063 · W3-066, W3-067, W3-068

---

## BÖLÜM 4 — TOP 30-40 SEÇİMİ (bu goal M9 + M14 kapsamı)

Katman 1-4'ten seçilen **35 madde**. Kalan (Katman 5 uzun + Katman 6 düşük) → Wave-4.

### M9 — Kritik Kısa Süre (TOP 15)
1. W3-001 TR binlik format veri bozulması *(kritik/kısa)*
2. W3-002 markPaid UTC gün kayması *(kritik/kısa)*
3. W3-003 Tailwind dinamik sınıf purge görünmez renk *(kritik/kısa)*
4. W3-005 DebtStrategy fetch hata → yanlış "borç yok" *(kritik/kısa)*
5. W3-006 PendingActions klavye onay bypass *(kritik/kısa)*
6. W3-023 Faizsiz kredi iyimser strateji + flag *(kritik/kısa)*
7. W3-030 EMANET KASA halüsinasyon filtre sızıntısı *(kritik/kısa)*
8. W3-039 Checkpoint hard-delete koruma açığı (MC4/5/6/8) *(kritik/kısa)*
9. W3-040 CORS credentials+wildcard + hardcoded origin *(kritik/kısa)*
10. W3-004 DebtStrategy slider klavye commit *(kritik/orta)*
11. W3-041 Rate limiting (brute-force/DoS) *(kritik/orta)*
12. W3-028 income→kredi kartı borç artışı *(orta/kısa, doğruluk)*
13. W3-026 Borç payoff MAX_MONTHS "bitmedi" flag *(orta/kısa)*
14. W3-029 action_executor 0-fiyat yok sayma *(orta/kısa)*
15. W3-058 precommit test gate (süreç, BUG #061 kökü) *(orta/kısa, yüksek kaldıraç)*

### M14 — Kalan (16-35, ~20 madde)
16. W3-007 IncomeDebt try/catch · 17. W3-008 RedLines hata yakalama · 18. W3-009 PendingActions JSON.parse guard · 19. W3-010 approve+reject yarışı · 20. W3-011 PremortemModal Escape guard · 21. W3-013 CommandPalette klavye odak · 22. W3-014 GoalDetailModal stale data · 23. W3-024 compare_strategies sessiz AttributeError · 24. W3-025 payoff epsilon tutarsızlığı · 25. W3-031 reasoning_trace commit/rollback · 26. W3-032 hesap silme IntegrityError sızıntı · 27. W3-033 create_allocation IDOR/status · 28. W3-043 str(e) hata sızıntısı · 29. W3-046 execute idempotency · 30. W3-019 dokunma hedefi 44px · 31. W3-020 form label/aria-invalid · 32. W3-018 modal a11y sistematik · 33. W3-012 null prop guard beyaz ekran · 34. W3-035 cascade/ondelete (FK ON) · 35. W3-057 TR locale ay isimleri

**Not (bağımlılık):** W3-034 (multi-tenant izolasyon) ve W3-042 (security headers/HTTPS) M11/M10 big-package'lerine gömülü uygulanır — M14 listesinde tekrar sayılmaz. W3-047/048 (uzun kod-borcu) M14'te başlatılır, tamamı Wave-4'e taşabilir (KURAL 12: kademeli, kalite düşürmeden).

---

## BÖLÜM 5 — Wave-4'e Ertelenen
Katman 6 düşük-öncelik (W3-015/016/017/021/022/038/053/055/061/062/063/066/067/068) + W3-047/048 kuyruğu + BIG paketlerin ileri fazları (mobil, aile hesabı, Open Banking ÖHVPS, vector+graph memory Mem0g). Gerekçe: KURAL 12 "yapılabilir ≠ tek dalgada yapılmalı" (meta-ders 10) — kritik doğruluk/güvenlik/UX önce.
