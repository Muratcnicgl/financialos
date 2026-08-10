# Gözlemlenebilirlik & operasyon (kod: OBS)

> Mevcut temel: `reasoning_traces` tablosu (latency/token/provider), `ApiCallLog`. Eksik: metrik/trace/structured-log altyapısı. wave3-vision "observability-first" diyor — burada somut.

### [OBS-001] Structured/JSON logging yok — `basicConfig(INFO)` düz metin
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: logging_config JsonFormatter
- **Sorun/Fırsat:** Log agregasyonu (JSON), sorgulanabilirlik, üretim analizi yapılamıyor.
- **Kanıt:** `app/main.py:57-61`
- **Aksiyon:** `structlog` JSON formatter; dev'de renkli, prod'da JSON.
- **Etki:** Orta · **Efor:** M

### [OBS-002] Request/trace korelasyon ID'si yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: request_id middleware yok
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
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: healthz/readyz ayrimi yok
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
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: ApiCallLog/CoachMemory retention yok
- **Kanıt:** `app/models.py:450-489`; scheduler'da trace cleanup var ama ApiCallLog için yok
- **Aksiyon:** N günden eski kayıt retention job (mevcut nightly cleanup'a ekle); aggregate tablo. (DATA-032)
- **Etki:** Düşük · **Efor:** M

### [OBS-015] Log seviyesi ortam-bazlı değil — prod'da DEBUG sızabilir
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: LOG_LEVEL env-driven
- **Kanıt:** `app/main.py:57` sabit basicConfig
- **Aksiyon:** `Settings.log_level` (BE-012); prod default WARNING/INFO, dev DEBUG.
- **Etki:** Düşük · **Efor:** S

### [OBS-016] LLM latency dağılımı (p50/p95/p99) izlenmiyor
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: LLM latency percentile yok
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
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: uptime monitor yok
- **Aksiyon:** Basit uptime monitor (UptimeRobot free) `/healthz`'e; deploy sürüm bilgisi (`app.version`) metrikte.
- **Etki:** Düşük · **Efor:** S

### [OBS-024] Trace'ler UI'da var ama toplu analiz/arama yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: TracePanel toplu arama yok
- **Kanıt:** `TracePanel` tek mesaj trace'i gösteriyor (`routers/coach.py:104-110`)
- **Aksiyon:** Trace'lerde toplu arama/filtre (yavaş çağrılar, grounding-ihlalli olanlar) — geliştirici görünümü.
- **Etki:** Düşük · **Efor:** M

### [OBS-025] Maliyet/kullanım bütçe uyarısı yok (LLM harcama tavanı)
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: aylik LLM maliyet butcesi yok
- **Kanıt:** Gemini günlük limit kontrolü var ama toplam maliyet tavanı yok
- **Aksiyon:** Aylık LLM maliyet bütçesi + %80/%100 eşik uyarısı (OBS-005 verisiyle).
- **Etki:** Düşük · **Efor:** S

---
**Kaynaklar:** OpenTelemetry FastAPI; prometheus-fastapi-instrumentator; structlog + asgi-correlation-id; Sentry; Langfuse/Arize (LLM observability); Google SRE "four golden signals".
