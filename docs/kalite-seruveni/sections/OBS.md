# Gözlemlenebilirlik & operasyon (kod: OBS)

> Mevcut temel: `reasoning_traces` tablosu (latency/token/provider), `ApiCallLog`. Eksik: metrik/trace/structured-log altyapısı. wave3-vision "observability-first" diyor — burada somut.

### [OBS-001] Structured/JSON logging yok — `basicConfig(INFO)` düz metin
- **Sorun/Fırsat:** Log agregasyonu (JSON), sorgulanabilirlik, üretim analizi yapılamıyor.
- **Kanıt:** `app/main.py:57-61`
- **Aksiyon:** `structlog` JSON formatter; dev'de renkli, prod'da JSON.
- **Etki:** Orta · **Efor:** M

### [OBS-002] Request/trace korelasyon ID'si yok
- **Sorun/Fırsat:** Bir chat çağrısının tüm log satırları/DB kayıtları/LLM çağrıları birbirine bağlanamıyor.
- **Kanıt:** `app/main.py` middleware yok; `reasoning_trace` `trace_id` var ama log'a bağlı değil
- **Aksiyon:** `asgi-correlation-id` veya custom middleware + `contextvars`; her log'a `request_id`/`trace_id`/`user_id`. reasoning_trace `trace_id`'siyle hizala.
- **Etki:** Orta · **Efor:** M

### [OBS-003] OpenTelemetry tracing yok — "niye 4 saniye sürdü" görünmüyor
- **Sorun/Fırsat:** Endpoint→cockpit→LLM(provider attempt'leri)→executor zinciri span'lenmiyor; latency kaynağı belirsiz.
- **Kanıt:** `app/coach.py` fallback zinciri (`1139-1173`); `main.py` OTel yok
- **Aksiyon:** `opentelemetry-instrumentation-fastapi` + LLM her attempt için manuel span (provider, tokens, sonuç). Jaeger/Tempo (free).
- **Etki:** Orta · **Efor:** M

### [OBS-004] Prometheus metrics yok — latency/error histogram, RPS
- **Kanıt:** `app/main.py` (metrics endpoint yok)
- **Aksiyon:** `prometheus-fastapi-instrumentator`; endpoint latency histogram + error counter; `/metrics`. Grafana (free).
- **Etki:** Orta · **Efor:** M

### [OBS-005] LLM cost metriği toplanmıyor
- **Sorun/Fırsat:** Token/maliyet görünmez; aylık LLM harcaması bilinmiyor.
- **Kanıt:** `ApiCallLog` sadece duration; `app/coach.py:1608-1610` usage trace'te ama cost yok
- **Aksiyon:** Provider fiyat tablosu + input/output token → `est_cost_usd`; günlük/aylık dashboard. (LLM-006/007 ön koşul)
- **Etki:** Orta · **Efor:** M

### [OBS-006] LLM kalite metriği yok (format/grounding/retry)
- **Kanıt:** `reasoning_trace.py:57-67` (kalite alanı yok)
- **Aksiyon:** Trace'e `grounding_ok`, `retry_count`, `format_valid`, `tool_schema_error`; haftalık özet. (LLM-039)
- **Etki:** Orta · **Efor:** M

### [OBS-007] Provider başarısızlık/fallback görünürlüğü zayıf
- **Sorun/Fırsat:** Hangi provider ne sıklıkla düşüyor, MALFORMED oranı ne — panoya dökülmüyor.
- **Kanıt:** `app/coach.py:1157-1166` (quota→skip); `ApiCallLog.provider`
- **Aksiyon:** Provider bazında success/fail/fallback-depth counter; MALFORMED_FUNCTION_CALL oranı metriği (LLM-016).
- **Etki:** Orta · **Efor:** S

### [OBS-008] Health vs readiness ayrımı yok
- **Kanıt:** `app/main.py:200-206` tek `/api/health`
- **Aksiyon:** `/healthz` (liveness) + `/readyz` (DB ping + scheduler + provider config). (API-019)
- **Etki:** Düşük · **Efor:** S

### [OBS-009] Scheduler job görünürlüğü yok — çalıştı mı, sürdü mü, hata mı
- **Kanıt:** `app/scheduler.py:144-169` (log seviyesinde)
- **Aksiyon:** Her job için başlangıç/bitiş/süre/işlenen-kayıt metriği; son çalışma zamanı bir tabloda/gauge'da; başarısız job alarmı.
- **Etki:** Orta · **Efor:** M

### [OBS-010] `except Exception: pass` sessiz yutmalar gözlemlenebilirliği yok ediyor
- **Kanıt:** `app/coach.py:391`, `action_executor.py:246`, `routers/cockpit.py:93`, `routers/coach.py:234,363`, `goal_engine.py:109`
- **Aksiyon:** Hepsine `logger.warning(exc_info=True)` + metrik counter. (BE-010)
- **Etki:** Orta · **Efor:** S

### [OBS-011] Ham kullanıcı mesajı log'da — PII gözlemi ile gizlilik çatışması
- **Kanıt:** `app/coach.py:1695,1757`
- **Aksiyon:** Redaksiyon filtresi (uzunluk/hash logla); observability PII sızdırmadan. (SEC-008)
- **Etki:** Orta · **Efor:** S

### [OBS-012] Error tracking (Sentry vb.) yok — hatalar proaktif görünmüyor
- **Kanıt:** repo genelinde error-tracking entegrasyonu yok
- **Aksiyon:** Sentry (free 5k event/ay) backend + frontend; unhandled exception + frontend error boundary'den (FE-003) besle.
- **Etki:** Orta · **Efor:** M

### [OBS-013] Frontend gözlemlenebilirliği yok — JS hatası/console görünmüyor
- **Kanıt:** `frontend/src/main.jsx` (error reporting yok)
- **Aksiyon:** Global `window.onerror`/`unhandledrejection` → backend log endpoint veya Sentry; FE-005 sessiz rejection'ları yakalar.
- **Etki:** Düşük · **Efor:** M

### [OBS-014] `ApiCallLog`/`ReasoningTrace`/`CoachMemory` sınırsız büyür — retention/rotation yok
- **Kanıt:** `app/models.py:450-489`; scheduler'da trace cleanup var ama ApiCallLog için yok
- **Aksiyon:** N günden eski kayıt retention job (mevcut nightly cleanup'a ekle); aggregate tablo. (DATA-032)
- **Etki:** Düşük · **Efor:** M

### [OBS-015] Log seviyesi ortam-bazlı değil — prod'da DEBUG sızabilir
- **Kanıt:** `app/main.py:57` sabit basicConfig
- **Aksiyon:** `Settings.log_level` (BE-012); prod default WARNING/INFO, dev DEBUG.
- **Etki:** Düşük · **Efor:** S

### [OBS-016] LLM latency dağılımı (p50/p95/p99) izlenmiyor
- **Kanıt:** `ApiCallLog.duration_ms` var ama percentile analizi yok
- **Aksiyon:** Prometheus histogram (OBS-004) veya periyodik agregasyon; provider+çağrı-tipi kırılımı.
- **Etki:** Düşük · **Efor:** S

### [OBS-017] "Altın sinyaller" (latency/traffic/error/saturation) panosu yok
- **Aksiyon:** OBS-003/004 üstüne Grafana dashboard: RPS, error rate, p95 latency, LLM cost/gün, provider health. Tek bakışta sistem sağlığı.
- **Etki:** Düşük · **Efor:** M

### [OBS-018] DB sağlık/boyut metriği yok (SQLite dosya boyutu, WAL, lock)
- **Kanıt:** `app/database.py`; büyüyen tablolar (OBS-014)
- **Aksiyon:** DB dosya boyutu, tablo satır sayıları, "database is locked" sayacı (DATA-004 ile) gauge'la.
- **Etki:** Düşük · **Efor:** S

### [OBS-019] Kullanıcı davranış analitiği yok (mobile öncesi)
- **Kanıt:** frontend'de analytics yok; wave3-vision PostHog öneriyor
- **Aksiyon:** Privacy-first (KVKK uyumlu) PostHog/Plausible — hangi panel/özellik kullanılıyor. Mobile çıkınca anlamlı.
- **Etki:** Düşük · **Efor:** M

### [OBS-020] Audit trail zayıf — finansal mutasyon kim/ne zaman izlenmiyor
- **Kanıt:** ApiCallLog sadece LLM; DELETE/UPDATE audit yok (SEC-024)
- **Aksiyon:** Append-only audit tablosu (aktör, ts, önce/sonra); observability + KVKK hesap verebilirlik.
- **Etki:** Orta · **Efor:** M

### [OBS-021] `reasoning_trace` her step commit — gözlem maliyeti canlı yolu yavaşlatıyor
- **Kanıt:** `reasoning_trace.py:168-171`
- **Aksiyon:** Batch flush (BE-023/LLM-027); observability latency eklemesin.
- **Etki:** Düşük · **Efor:** M

### [OBS-022] Alerting yok — kritik durum (tüm provider'lar dolu, DB lock) sessiz
- **Kanıt:** `app/coach.py` chain-exhausted durumu sadece kullanıcıya mesaj
- **Aksiyon:** Eşik-tabanlı alert (error rate, chain-exhausted, disk); tek-kullanıcıda e-posta/push yeterli.
- **Etki:** Düşük · **Efor:** M

### [OBS-023] Uptime/deployment izleme yok
- **Aksiyon:** Basit uptime monitor (UptimeRobot free) `/healthz`'e; deploy sürüm bilgisi (`app.version`) metrikte.
- **Etki:** Düşük · **Efor:** S

### [OBS-024] Trace'ler UI'da var ama toplu analiz/arama yok
- **Kanıt:** `TracePanel` tek mesaj trace'i gösteriyor (`routers/coach.py:104-110`)
- **Aksiyon:** Trace'lerde toplu arama/filtre (yavaş çağrılar, grounding-ihlalli olanlar) — geliştirici görünümü.
- **Etki:** Düşük · **Efor:** M

### [OBS-025] Maliyet/kullanım bütçe uyarısı yok (LLM harcama tavanı)
- **Kanıt:** Gemini günlük limit kontrolü var ama toplam maliyet tavanı yok
- **Aksiyon:** Aylık LLM maliyet bütçesi + %80/%100 eşik uyarısı (OBS-005 verisiyle).
- **Etki:** Düşük · **Efor:** S

---
**Kaynaklar:** OpenTelemetry FastAPI; prometheus-fastapi-instrumentator; structlog + asgi-correlation-id; Sentry; Langfuse/Arize (LLM observability); Google SRE "four golden signals".
