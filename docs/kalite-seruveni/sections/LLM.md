# LLM / Coach / AI orkestrasyon (kod: LLM)

> wave3-vision'ın LangGraph/DSPy önerileri tekrarlanmadı; DSPy'siz/LangGraph'sız uygulanabilir ara adımlara somutlandı. Rules Engine/LLM ayrımı korunur.

### [LLM-001] AnthropicProvider modeli güncel değil + adaptive thinking yok
- **Kanıt:** `app/coach.py:767` `DEFAULT_MODEL="claude-opus-4-7"`; `:785-791` thinking yok
- **Aksiyon:** `claude-opus-4-8`; analiz çağrılarında `thinking={"type":"adaptive"}`+`output_config={"effort":"high"}`, bildirimde `effort="low"`. `budget_tokens` EKLEME (400 hatası).
- **Etki:** Yüksek · **Efor:** S

### [LLM-002] Prompt caching yok — V3 mega-prompt her çağrıda tam fiyat
- **Kanıt:** `app/coach.py:785-791,1562-1566`
- **Aksiyon:** Donmuş V3 çekirdeğine `cache_control:{"type":"ephemeral"}`; volatil cockpit'i sonra/messages'a taşı; `cache_read_input_tokens` ile doğrula. (~%90 ucuz, ~%85 latency↓)
- **Etki:** Yüksek · **Efor:** M

### [LLM-003] Çıktı grounding kontrolü yok — LLM'in sayısı cockpit ile eşleşmiyor
- **Kanıt:** `app/coach.py:1780-1796` (postprocess sadece regex)
- **Aksiyon:** `_check_grounding(reply, cockpit)`: reply'daki TL/yüzde token'larını cockpit değerleriyle (±tolerans) kıyasla; eşleşmezse trace'e `grounding_violation`, confidence düşür.
- **Etki:** Yüksek · **Efor:** M · **Not:** TR sayı formatı (31.342,86) parse'ında dikkat.

### [LLM-004] Eval/regression harness yok
- **Kanıt:** pytest yok; `test_coach.py` tek-akış
- **Aksiyon:** `evals/coach_cases.yaml` (20-30 vaka: kahve/TLY/kart/selam/belirsiz hesap) + beklenen is_question/tool/grounding/format; promptfoo ile provider matrisi. Her prompt değişikliğinden önce.
- **Etki:** Yüksek · **Efor:** M

### [LLM-005] LLM-as-judge ile provider kalite karşılaştırması yok
- **Kanıt:** `app/coach.py:1242-1264`; `routers/coach.py:181-206`
- **Aksiyon:** DeepEval G-Eval/küçük judge ile offline puanla; trace'e provider+skor; haftalık dashboard.
- **Etki:** Orta · **Efor:** M

### [LLM-006] Token cost/latency ölçümü eksik — sadece süre
- **Kanıt:** `routers/coach.py:181-206`; `coach.py:1608-1610`
- **Aksiyon:** ApiCallLog'a input/output token + `est_cost_usd`; provider fiyat tablosu; `/usage`'a aylık maliyet.
- **Etki:** Orta · **Efor:** M

### [LLM-007] usage/provider_used/model_name sadece Groq'ta set ediliyor
- **Kanıt:** `coach.py:801,953,1064,1115` (yok) vs `1018-1020` (Groq)
- **Aksiyon:** Her provider usage çıkarsın (Anthropic `usage.input/output_tokens`, Gemini `usage_metadata`, OpenAI-uyumlu `usage`); provider_used/model_name kendi set etsin.
- **Etki:** Yüksek · **Efor:** S · **Not:** LLM-005/006'nın ön koşulu.

### [LLM-008] Tool-call şema doğrulaması yok — args sessizce {}
- **Kanıt:** `coach.py:1006-1009,1060-1063,1110-1114,911-913`; `:1659-1662`
- **Aksiyon:** PROPOSE/SAVE şemalarını Pydantic'e bağla; tool-call sonrası `model_validate`, hata→retry; Anthropic'te `strict:true`+`additionalProperties:false`.
- **Etki:** Yüksek · **Efor:** M

### [LLM-009] premortem.py kırılgan JSON parse — structured output kullan
- **Kanıt:** `app/premortem.py:167-189,225-262`
- **Aksiyon:** Provider'a `output_schema` param (Anthropic json_schema, Gemini response_schema, OpenAI response_format); fallback'te mevcut parse.
- **Etki:** Orta · **Efor:** M

### [LLM-010] is_question sınıflandırıcı kenar durumlarında hatalı
- **Kanıt:** `coach.py:78-89,1583-1584`
- **Aksiyon:** (1) Güçlü geçmiş-zaman marker'ları (sattım/ödedim/kaydet) varsa is_question=False zorla; (2) belirsizler için küçük LLM intent classifier (Groq 8B, tek token). Regex first-pass.
- **Etki:** Yüksek · **Efor:** M

### [LLM-011] Retry backoff'ta jitter yok — thundering herd
- **Kanıt:** `coach.py:489`
- **Aksiyon:** Full jitter `random.uniform(0, base*2^n)` + max_delay; retry sayısını logla.
- **Etki:** Düşük · **Efor:** S

### [LLM-012] Retryable/quota sınıflandırması kırılgan string-match
- **Kanıt:** `coach.py:437-471`
- **Aksiyon:** Tipli exception (Anthropic RateLimitError, status_code); 400 retry EDİLMEZ, 5xx/429 edilir; string fallback.
- **Etki:** Orta · **Efor:** M

### [LLM-013] Semantic caching yok
- **Kanıt:** `coach.py:1594-1601`
- **Aksiyon:** cockpit_hash + mesaj benzerliği; basit başlangıç: (mesaj normalize + cockpit_hash) exact-match, 60sn TTL; sonra embedding.
- **Etki:** Orta · **Efor:** M · **Not:** cockpit_hash cache key'e MUTLAKA dahil (stale finansal cevap riski).

### [LLM-014] Streaming yok — uzun raporlarda TTFB yüksek, timeout riski
- **Kanıt:** `coach.py:785-791,988-995`; Coach.jsx tam cevap bekliyor
- **Aksiyon:** `chat_stream` (SSE) en azından analiz yolunda; `get_final_message()` ile tam cevap. Bildirimde gerek yok.
- **Etki:** Orta · **Efor:** L

### [LLM-015] coach.py 1865 satır — modülerleştirme
- **Kanıt:** `app/coach.py`
- **Aksiyon:** `app/coach/` paketi (providers/prompts/tools/memory/postprocess/engine); public API `__init__.py` (premortem import kırılmasın). Eval harness (LLM-004) ÖNCE.
- **Etki:** Orta · **Efor:** L · **Not:** BE-001 ile aynı.

### [LLM-016] MALFORMED_FUNCTION_CALL sadece atlanıyor, kök-neden azaltılmıyor
- **Kanıt:** `coach.py:811-819,931-940,880-882`
- **Aksiyon:** Gemini tool şemasını sadeleştir (payload'ı ayrık tool'lar) veya net-eylemde `mode="ANY"`; MALFORMED oranını metrik yap.
- **Etki:** Orta · **Efor:** M

### [LLM-017] History trim token değil karakter tabanlı
- **Kanıt:** `coach.py:1276-1311,1294-1295`
- **Aksiyon:** Anthropic'te `count_tokens`; diğerlerinde muhafazakâr tahmin; tool_call/tool_result çiftlerini birlikte kes.
- **Etki:** Orta · **Efor:** M

### [LLM-018] format_insights_for_prompt cl100k_base tokenizer kullanıyor (yanlış)
- **Kanıt:** `coach_insights.py:2160-2169`
- **Aksiyon:** char/3.5 heuristiği (mevcut ImportError fallback'i default yap) veya aktif provider count_tokens; cl100k bağımlılığını kaldır.
- **Etki:** Düşük · **Efor:** S

### [LLM-019] Confidence prompt-tabanlı ve kırılgan — structured output'a taşı
- **Kanıt:** `coach.py:268-289,693-733`
- **Aksiyon:** Confidence'ı structured alan veya `_check_grounding`'den deterministik türet; prompt'tan CONFIDENCE bloğunu çıkar.
- **Etki:** Orta · **Efor:** M

### [LLM-020] Hallucination postprocess salt regex — kırılgan
- **Kanıt:** `coach.py:1318-1406`
- **Aksiyon:** Kısa vade: regex'i eval harness fixture'larına bağla; orta vade: rapor iskeletini structured output (bölüm listesi) — boş bölüm hiç üretilmez.
- **Etki:** Orta · **Efor:** M

### [LLM-021] Retry "[RETRY:...]" system'e enjekte ediyor — cache kırar
- **Kanıt:** `coach.py:1697,1759,1691-1778`
- **Aksiyon:** Retry talimatını system'e değil messages sonuna ekle (cache prefix korunur); iki retry bloğunu tek `_retry_once(mode)`'da birleştir.
- **Etki:** Orta · **Efor:** M

### [LLM-022] Few-shot örnekleri prompt gövdesine gömülü — bakımsız
- **Kanıt:** `coach.py:114-154`; wave3-vision:94-98
- **Aksiyon:** Örnekleri `prompts/fewshot.py`'ye al; provider yeteneğine göre koşullu enjekte; eval ile katkı ölç. (DSPy'ye hazırlık)
- **Etki:** Orta · **Efor:** M

### [LLM-023] Guardrail: yasaklar SADECE prompt+regex ile tutuluyor
- **Kanıt:** `coach.py:127-146,1401-1404`; kod-seviyesi HESAP_BELIRSIZ (`:1677`) doğru katman
- **Aksiyon:** "Sahte tamamlama" tespitini deterministik output guard yap (tool çağrılmadı ama "kaydedildi"); prompt yasak listelerini kısalt.
- **Etki:** Orta · **Efor:** M

### [LLM-024] Gemini best-effort tool-history placeholder echo riski
- **Kanıt:** `coach.py:838-862,37-42`
- **Aksiyon:** Gemini native `function_response` part'ı kullan (gerçek tool-aware geçmiş) veya tool-history senaryolarında zincirin arkasına al.
- **Etki:** Düşük · **Efor:** M

### [LLM-025] Provider client'ları lazy import — ilk çağrı latency + gizli hata
- **Kanıt:** `coach.py:771,827,968`; `routers/coach.py:247-256`
- **Aksiyon:** `build_provider`'da import hatalarını erken yakala; thread-safety doğrula; startup warmup (LLM-002 cache pre-warm ile birleştir).
- **Etki:** Düşük · **Efor:** S

### [LLM-026] Uzun history: sadece son 3 tur — stratejik bağlam kaybı
- **Kanıt:** `coach.py:1493,1507-1526`
- **Aksiyon:** Anthropic compaction/context editing veya turn 3→5 + oturum-içi özet; insight-memory yaklaşımını koru.
- **Etki:** Orta · **Efor:** M

### [LLM-027] Trace her step'te commit — N+1 DB yazımı
- **Kanıt:** `reasoning_trace.py:168-171`; `coach.py:1568-1611`
- **Aksiyon:** Step'leri biriktir, sonda tek commit; finally'de garantile.
- **Etki:** Düşük · **Efor:** M · **Not:** BE-023 ile aynı.

### [LLM-028] provider_used FallbackProvider dışında set edilmiyor
- **Kanıt:** `coach.py:1146-1147,801/953/1064/1115,1606`
- **Aksiyon:** LLM-007 ile her provider kendi provider_used/model_name set etsin.
- **Etki:** Düşük · **Efor:** S

### [LLM-029] Temperature farklı ve sabit-kodlu — eval'siz
- **Kanıt:** `coach.py:868` (Gemini 0.4), `993,1047,1098` (0.2)
- **Aksiyon:** Çağrı tipine göre parametrize (tool 0.0-0.1, analiz 0.3-0.4); eval ile ölç. Anthropic'e temp gönderme (400).
- **Etki:** Düşük · **Efor:** S

### [LLM-030] max_tokens=4096 sabit — uzun rapor kesilme riski
- **Kanıt:** `coach.py:787,869,994` vd.
- **Aksiyon:** Analiz 8000+, bildirim 1024; `stop_reason==max_tokens` yakala/logla; >16K streaming.
- **Etki:** Orta · **Efor:** S

### [LLM-031] Rate limiting yok — bug avında tüm provider'lar dolar
- **Kanıt:** `routers/coach.py:284-290`; wave3-vision:163
- **Aksiyon:** In-memory token-bucket (10/dk); gerçek 429'da `retry-after` oku.
- **Etki:** Düşük · **Efor:** S · **Not:** SEC-004 ile örtüşür.

### [LLM-032] Fallback'te 429 retry-after header'ı okunmuyor
- **Kanıt:** `coach.py:463-471,1157-1166`
- **Aksiyon:** retry-after oku; kısaysa (<5sn) primary'de bekle, uzunsa fallback; konfigüre edilebilir.
- **Etki:** Düşük · **Efor:** M

### [LLM-033] Cockpit her chat'te yeniden üretiliyor — cache yok
- **Kanıt:** `coach.py:1564-1566,525-527`; wave3-vision:163
- **Aksiyon:** Kısa TTL (10sn) memoize, key=user_id+son değişiklik ts; pending onayında invalidate.
- **Etki:** Düşük · **Efor:** S · **Not:** BE-036/LLM-013 ile ilişkili.

### [LLM-034] Grounding için ham cockpit dict kullanılmıyor
- **Kanıt:** `coach.py:602-640,1856`
- **Aksiyon:** `_check_grounding` (LLM-003) için mevcut `cockpit` dict'ini kaynak-doğruluk olarak kullan (mimari değişmez).
- **Etki:** Orta · **Efor:** S

### [LLM-035] save_insight soru modunda hep aktif — istenmeyen yazım
- **Kanıt:** `coach.py:1584,1630-1649`
- **Aksiyon:** dedup_key boşsa yazma; selamlaşmada save_insight'ı kapat; içeriği şema ile doğrula.
- **Etki:** Düşük · **Efor:** S

### [LLM-036] Propose sonrası execute sonucu LLM'e dönmüyor (tek tur)
- **Kanıt:** `coach.py:1652-1685`; execute ayrı endpoint
- **Aksiyon:** propose→onay→execute'i koru; execute sonrası tool_result'ı history'ye yazıp opsiyonel "koç yorumu" (BUG #036 altyapısı var). LLM yine DB yazmaz.
- **Etki:** Orta · **Efor:** M

### [LLM-037] Anthropic tool mapping strict/örnek kullanmıyor
- **Kanıt:** `coach.py:776-783,358-360`
- **Aksiyon:** `strict:true`+`additionalProperties:false`+`required`; payload'ı action_type'a göre anyOf; description'a örnek.
- **Etki:** Orta · **Efor:** M

### [LLM-038] Chat hatası düz string reply — yapısal sınıflandırma yok
- **Kanıt:** `coach.py:1612-1621`; `routers/coach.py:306-313`
- **Aksiyon:** Hata tipine göre kullanıcı mesajı (quota/network/400); ham exception gösterme, logla (request_id).
- **Etki:** Düşük · **Efor:** S

### [LLM-039] reasoning_traces var ama LLM-kalite metrikleri toplanmıyor
- **Kanıt:** `reasoning_trace.py:57-67`; `routers/coach.py:104-110`
- **Aksiyon:** Trace'e `grounding_ok`, `retry_count`, `format_valid`, `tool_schema_error`; haftalık özet endpoint'i. (SQLite üstünde küçük agregasyon)
- **Etki:** Orta · **Efor:** M

### [LLM-040] Fallback sonuç kalitesi kontrol edilmiyor — boş/bozuk metin geçebilir
- **Kanıt:** `coach.py:1139-1173,1413-1440`
- **Aksiyon:** Fallback sonrası minimal kalite geçidi (çok kısa+tool yok+soru değil veya grounding-ihlali → sonraki provider); max_attempts ile sınırla.
- **Etki:** Orta · **Efor:** M

---
**Kaynaklar:** claude-api skill (Opus 4.8, adaptive thinking, prompt caching, strict tool use, count_tokens); promptfoo/DeepEval; prompt/semantic caching (Introl, Maxim, arxiv 2601.06007); LLM guardrails/hallucination (Leanware, FutureAGI).
