# Gözlemlenebilirlik & operasyon (kod: OBS)

> Mevcut temel: `reasoning_traces` tablosu (latency/token/provider), `ApiCallLog`. Eksik: metrik/trace/structured-log altyapısı. wave3-vision "observability-first" diyor — burada somut.

### [OBS-001] Structured/JSON logging yok — `basicConfig(INFO)` düz metin
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: logging_config JsonFormatter
- **Sorun/Fırsat:** Log agregasyonu (JSON), sorgulanabilirlik, üretim analizi yapılamıyor.
- **Kanıt:** `app/main.py:57-61`
- **Aksiyon:** `structlog` JSON formatter; dev'de renkli, prod'da JSON.
- **Etki:** Orta · **Efor:** M

### [OBS-002] Request/trace korelasyon ID'si yok
- **Durum:** ✅ KAPANDI — 5 Eyl 2026 ölçümü: `app/correlation.py` bir `istek_id` ContextVar'ı taşıyor ve her log satırı onu basıyor. Canlı örnek: `[WARNING] [dz782yg8] app.workspace_deps: ...` — yani korelasyon kimliği yalnız kodda değil, ÜRETİM ÇIKTISINDA doğrulandı.
- **Sorun/Fırsat:** Bir chat çağrısının tüm log satırları/DB kayıtları/LLM çağrıları birbirine bağlanamıyor.
- **Kanıt:** `app/main.py` middleware yok; `reasoning_trace` `trace_id` var ama log'a bağlı değil
- **Aksiyon:** `asgi-correlation-id` veya custom middleware + `contextvars`; her log'a `request_id`/`trace_id`/`user_id`. reasoning_trace `trace_id`'siyle hizala.
- **Etki:** Orta · **Efor:** M

### [OBS-003] OpenTelemetry tracing yok — "niye 4 saniye sürdü" görünmüyor
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: opentelemetry yok
- **Sorun/Fırsat:** Endpoint→cockpit→LLM(provider attempt'leri)→executor zinciri span'lenmiyor; latency kaynağı belirsiz.
- **Kanıt:** `app/coach.py` fallback zinciri (`1139-1173`); `main.py` OTel yok
- **Aksiyon:** `opentelemetry-instrumentation-fastapi` + LLM her attempt için manuel span (provider, tokens, sonuç). Jaeger/Tempo (free).
- **Etki:** Orta · **Efor:** M

### [OBS-004] Prometheus metrics yok — latency/error histogram, RPS
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: prometheus yok
- **Kanıt:** `app/main.py` (metrics endpoint yok)
- **Aksiyon:** `prometheus-fastapi-instrumentator`; endpoint latency histogram + error counter; `/metrics`. Grafana (free).
- **Etki:** Orta · **Efor:** M

### [OBS-005] LLM cost metriği toplanmıyor
- **Durum:** ✅ KAPANDI (BUG #274 / ADR-053, 10 Ağu 2026) — LLM-006 ile aynı fix.
  `est_cost_usd` yazma anındaki liste fiyatıyla dondurulur; `python -m scripts.beta_metrics`
  tahmini tutarı, amaç bazında kırılımı (koc/premortem/yansima) ve **iki ayrı bilinmeyen
  sayacını** basar (fiyatı bilinmeyen → tablo güncellenmeli; token döndürmeyen → çöken
  istek/yerel model). Toplam bilinçli olarak ALT SINIRDIR: bilinmeyen sıfır sayılmaz.
- **Kanıt:** `app/llm_cost.py`; `scripts/beta_metrics._maliyet`; kapı `tests/test_llm_maliyet_kapisi.py`
- **Etki:** Orta · **Efor:** M · **Not:** Grafana/pano ayrı iş (OBS-004 ile birlikte).

### [OBS-006] LLM kalite metriği yok (format/grounding/retry)
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: grounding_ok/format_valid alani yok
- **Kanıt:** `reasoning_trace.py:57-67` (kalite alanı yok)
- **Aksiyon:** Trace'e `grounding_ok`, `retry_count`, `format_valid`, `tool_schema_error`; haftalık özet. (LLM-039)
- **Etki:** Orta · **Efor:** M

### [OBS-007] Provider başarısızlık/fallback görünürlüğü zayıf
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: fallback_count loglu ama metrik yok
- **Sorun/Fırsat:** Hangi provider ne sıklıkla düşüyor, MALFORMED oranı ne — panoya dökülmüyor.
- **Kanıt:** `app/coach.py:1157-1166` (quota→skip); `ApiCallLog.provider`
- **Aksiyon:** Provider bazında success/fail/fallback-depth counter; MALFORMED_FUNCTION_CALL oranı metriği (LLM-016).
- **Etki:** Orta · **Efor:** S

### [OBS-008] Health vs readiness ayrımı yok
- **Durum:** ✅ KAPANDI — `API-019` ile aynı iş, iki boyutta iki kez kaydedilmiş. **BUG #247 (D39)** ayırmış: `/api/health` CANLILIK ölçer (bağımlılık yok, her zaman 200), `/api/ready` HAZIR OLMA ölçer (DB/şema; **503 dönebilir** ve bu bir hata değil ölçümün kendisidir). 5 Eyl 2026'da canlıda doğrulandı: ikisi de 200.
- **Kanıt:** `app/main.py:200-206` tek `/api/health`
- **Aksiyon:** `/healthz` (liveness) + `/readyz` (DB ping + scheduler + provider config). (API-019)
- **Etki:** Düşük · **Efor:** S

### [OBS-009] Scheduler job görünürlüğü yok — çalıştı mı, sürdü mü, hata mı
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: job sure/last_run metrik yok
- **Kanıt:** `app/scheduler.py:144-169` (log seviyesinde)
- **Aksiyon:** Her job için başlangıç/bitiş/süre/işlenen-kayıt metriği; son çalışma zamanı bir tabloda/gauge'da; başarısız job alarmı.
- **Etki:** Orta · **Efor:** M

### [OBS-010] `except Exception: pass` sessiz yutmalar gözlemlenebilirliği yok ediyor
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: BE-010 silent-except logging
- **Kanıt:** `app/coach.py:391`, `action_executor.py:246`, `routers/cockpit.py:93`, `routers/coach.py:234,363`, `goal_engine.py:109`
- **Aksiyon:** Hepsine `logger.warning(exc_info=True)` + metrik counter. (BE-010)
- **Etki:** Orta · **Efor:** S

### [OBS-011] Ham kullanıcı mesajı log'da — PII gözlemi ile gizlilik çatışması
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: ham mesaj redaksiyon yok
- **Kanıt:** `app/coach.py:1695,1757`
- **Aksiyon:** Redaksiyon filtresi (uzunluk/hash logla); observability PII sızdırmadan. (SEC-008)
- **Etki:** Orta · **Efor:** S

### [OBS-012] Error tracking (Sentry vb.) yok — hatalar proaktif görünmüyor
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: Sentry yok
- **Kanıt:** repo genelinde error-tracking entegrasyonu yok
- **Aksiyon:** Sentry (free 5k event/ay) backend + frontend; unhandled exception + frontend error boundary'den (FE-003) besle.
- **Etki:** Orta · **Efor:** M

### [OBS-013] Frontend gözlemlenebilirliği yok — JS hatası/console görünmüyor
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: ErrorBoundary var ama backend raporlama yok
- **Kanıt:** `frontend/src/main.jsx` (error reporting yok)
- **Aksiyon:** Global `window.onerror`/`unhandledrejection` → backend log endpoint veya Sentry; FE-005 sessiz rejection'ları yakalar.
- **Etki:** Düşük · **Efor:** M

### [OBS-014] `ApiCallLog`/`ReasoningTrace`/`CoachMemory` sınırsız büyür — retention/rotation yok
- **Durum:** 🟡 KISMEN — 5 Eyl 2026 ölçümü, **üç tablodan yalnız BİRİ** korunuyor: `scheduler.nightly_trace_cleanup_job` (04:00 İstanbul) `ReasoningTrace`'in 90 günden eski satırlarını siler ve **silinen satır sayısını çalışma kaydına düşer** (BUG #240 — KVKK'da verilen 90 gün sözü ancak SAYIYLA doğrulanır, log okumak kanıt değildir). AÇIK KALAN, ölçülerek daraltıldı: `ApiCallLog` ve `CoachMemory` için saklama işi YOK — ikisi de sınırsız büyümeye devam ediyor. Sıradaki iş bu iki tablodur, tamamı değil.
- **Kanıt:** `app/models.py:450-489`; scheduler'da trace cleanup var ama ApiCallLog için yok
- **Aksiyon:** N günden eski kayıt retention job (mevcut nightly cleanup'a ekle); aggregate tablo. (DATA-032)
- **Etki:** Düşük · **Efor:** M

### [OBS-015] Log seviyesi ortam-bazlı değil — prod'da DEBUG sızabilir
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: LOG_LEVEL env-driven
- **Kanıt:** `app/main.py:57` sabit basicConfig
- **Aksiyon:** `Settings.log_level` (BE-012); prod default WARNING/INFO, dev DEBUG.
- **Etki:** Düşük · **Efor:** S

### [OBS-016] LLM latency dağılımı (p50/p95/p99) izlenmiyor
- **Durum:** 🟡 KISMEN — 5 Eyl 2026 ölçümü: **veri VAR, analiz YOK.** Her LLM çağrısının süresi ölçülüp kaydediliyor (`app/routers/coach.py:450` `duration_ms` hesaplanır, `llm_quota.tamamla(...)` ile satıra yazılır). Eksik olan toplama yüzeyi: p50/p95/p99 hesaplayan bir rapor ya da uç yok. Yani bu madde "ölçmüyoruz" değil, **"ölçtüğümüze bakmıyoruz"** (L61'in bir başka yüzü). `scripts/perf_smoke.py` HTTP katmanı için aynı işi yapıyor; LLM tarafı için karşılığı yazılmalı.
- **Kanıt:** `ApiCallLog.duration_ms` var ama percentile analizi yok
- **Aksiyon:** Prometheus histogram (OBS-004) veya periyodik agregasyon; provider+çağrı-tipi kırılımı.
- **Etki:** Düşük · **Efor:** S

### [OBS-017] "Altın sinyaller" (latency/traffic/error/saturation) panosu yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: Grafana panosu yok
- **Aksiyon:** OBS-003/004 üstüne Grafana dashboard: RPS, error rate, p95 latency, LLM cost/gün, provider health. Tek bakışta sistem sağlığı.
- **Etki:** Düşük · **Efor:** M

### [OBS-018] DB sağlık/boyut metriği yok (SQLite dosya boyutu, WAL, lock)
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: DB boyut/lock metrik yok
- **Kanıt:** `app/database.py`; büyüyen tablolar (OBS-014)
- **Aksiyon:** DB dosya boyutu, tablo satır sayıları, "database is locked" sayacı (DATA-004 ile) gauge'la.
- **Etki:** Düşük · **Efor:** S

### [OBS-019] Kullanıcı davranış analitiği yok (mobile öncesi)
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: PostHog/Plausible yok
- **Kanıt:** frontend'de analytics yok; wave3-vision PostHog öneriyor
- **Aksiyon:** Privacy-first (KVKK uyumlu) PostHog/Plausible — hangi panel/özellik kullanılıyor. Mobile çıkınca anlamlı.
- **Etki:** Düşük · **Efor:** M

### [OBS-020] Audit trail zayıf — finansal mutasyon kim/ne zaman izlenmiyor
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: ActionHistory koc-aksiyon ama router DELETE audit yok
- **Kanıt:** ApiCallLog sadece LLM; DELETE/UPDATE audit yok (SEC-024)
- **Aksiyon:** Append-only audit tablosu (aktör, ts, önce/sonra); observability + KVKK hesap verebilirlik.
- **Etki:** Orta · **Efor:** M

### [OBS-021] `reasoning_trace` her step commit — gözlem maliyeti canlı yolu yavaşlatıyor
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: reasoning_trace her step commit
- **Kanıt:** `reasoning_trace.py:168-171`
- **Aksiyon:** Batch flush (BE-023/LLM-027); observability latency eklemesin.
- **Etki:** Düşük · **Efor:** M

### [OBS-022] Alerting yok — kritik durum (tüm provider'lar dolu, DB lock) sessiz
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: esik-tabanli alerting yok
- **Kanıt:** `app/coach.py` chain-exhausted durumu sadece kullanıcıya mesaj
- **Aksiyon:** Eşik-tabanlı alert (error rate, chain-exhausted, disk); tek-kullanıcıda e-posta/push yeterli.
- **Etki:** Düşük · **Efor:** M

### [OBS-023] Uptime/deployment izleme yok
- **Durum:** ✅ KAPANDI — 5 Eyl 2026 ölçümü: Wave-Y/Y2 hem uptime hem deployment izlemesini kurdu. **Uptime:** `deploy/windows/saglik.ps1` 10 dakikada bir koşar, ÖLÜ ADAM ANAHTARI ile dışarı ping atar (ping kesilirse alarm; sessizlik alarmın kendisidir), her koşumu `logs/erisilebilirlik.csv`'ye yazar ve `scripts/erisilebilirlik_raporu.py` kayıp slotları KESİNTİ sayarak oran üretir (bu gece: %29,85). **Deployment:** `deploy/windows/guncelle.ps1` dağıtımdan sonra canlı `/api/meta` damgasının hedefe EŞİT olduğunu doğrular (KULLANIM-GATE) — sağlık 200 yetmez, eski süreç de 200 verirdi. İkisi de bu gece gerçek bir olayda çalıştı (23:07-00:10 DNS kesintisi kaydedildi).
- **Aksiyon:** Basit uptime monitor (UptimeRobot free) `/healthz`'e; deploy sürüm bilgisi (`app.version`) metrikte.
- **Etki:** Düşük · **Efor:** S

### [OBS-024] Trace'ler UI'da var ama toplu analiz/arama yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: TracePanel toplu arama yok
- **Kanıt:** `TracePanel` tek mesaj trace'i gösteriyor (`routers/coach.py:104-110`)
- **Aksiyon:** Trace'lerde toplu arama/filtre (yavaş çağrılar, grounding-ihlalli olanlar) — geliştirici görünümü.
- **Etki:** Düşük · **Efor:** M

### [OBS-025] Maliyet/kullanım bütçe uyarısı yok (LLM harcama tavanı)
- **Durum:** 🟡 KISMEN — 5 Eyl 2026 ölçümü: **tavan var, UYARI yok.** `app/llm_quota.py` kullanıcı başına günlük çağrı tavanı (`kullanici_gunluk_tavan`), günlük sayım (`bugunku_cagri_sayisi`), sağlayıcı-paylaşımlı sayım (`paylasilan_cagri_sayisi`) ve çağrı başına `maliyet_usd` taşıyor; `tests/test_llm_maliyet_kapisi.py` bunu kilitliyor. Yani harcama ÖLÇÜLÜYOR ve kullanım BLOKLANIYOR. Eksik olan, bir eşiğe yaklaşıldığında HABER VEREN yol — ölü adam anahtarı kesintiyi haber veriyor, bütçeyi vermiyor.
- **Kanıt:** Gemini günlük limit kontrolü var ama toplam maliyet tavanı yok
- **Aksiyon:** Aylık LLM maliyet bütçesi + %80/%100 eşik uyarısı (OBS-005 verisiyle).
- **Etki:** Düşük · **Efor:** S

---
**Kaynaklar:** OpenTelemetry FastAPI; prometheus-fastapi-instrumentator; structlog + asgi-correlation-id; Sentry; Langfuse/Arize (LLM observability); Google SRE "four golden signals".
