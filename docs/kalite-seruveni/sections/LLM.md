# LLM / Coach / AI orkestrasyon (kod: LLM)

> wave3-vision'ın LangGraph/DSPy önerileri tekrarlanmadı; DSPy'siz/LangGraph'sız uygulanabilir ara adımlara somutlandı. Rules Engine/LLM ayrımı korunur.

### [LLM-001] AnthropicProvider modeli güncel değil + adaptive thinking yok ✅ KISMEN (12 Tem 2026: model güncel)
- **Durum:** ✅ KAPANDI (inline işaret)
- **Kanıt:** `app/coach.py:767` `DEFAULT_MODEL="claude-opus-4-7"`; `:785-791` thinking yok
- **Aksiyon:** `claude-opus-4-8`; analiz çağrılarında `thinking={"type":"adaptive"}`+`output_config={"effort":"high"}`, bildirimde `effort="low"`. `budget_tokens` EKLEME (400 hatası).
- **Etki:** Yüksek · **Efor:** S
- **Durum:** DEFAULT_MODEL claude-opus-4-7→claude-opus-4-8 (en yeni/yetkin; eskisi 404 riski). Adaptive thinking (analiz→effort high, bildirim→low) follow-up: analiz/bildirim ayrımı + API param gerektirir.

### [LLM-002] Prompt caching yok — V3 mega-prompt her çağrıda tam fiyat
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: cache_control yok, V3 her cagrida tam
- **Kanıt:** `app/coach.py:785-791,1562-1566`
- **Aksiyon:** Donmuş V3 çekirdeğine `cache_control:{"type":"ephemeral"}`; volatil cockpit'i sonra/messages'a taşı; `cache_read_input_tokens` ile doğrula. (~%90 ucuz, ~%85 latency↓)
- **Etki:** Yüksek · **Efor:** M

### [LLM-003] Çıktı grounding kontrolü yok — LLM'in sayısı cockpit ile eşleşmiyor
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: check_grounding chat cikisinda
- **Kanıt:** `app/coach.py:1780-1796` (postprocess sadece regex)
- **Aksiyon:** `_check_grounding(reply, cockpit)`: reply'daki TL/yüzde token'larını cockpit değerleriyle (±tolerans) kıyasla; eşleşmezse trace'e `grounding_violation`, confidence düşür.
- **Etki:** Yüksek · **Efor:** M · **Not:** TR sayı formatı (31.342,86) parse'ında dikkat.

### [LLM-004] Eval/regression harness yok
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: eval harness canli (coach_eval)
- **Kanıt:** pytest yok; `test_coach.py` tek-akış
- **Aksiyon:** `evals/coach_cases.yaml` (20-30 vaka: kahve/TLY/kart/selam/belirsiz hesap) + beklenen is_question/tool/grounding/format; promptfoo ile provider matrisi. Her prompt değişikliğinden önce.
- **Etki:** Yüksek · **Efor:** M

### [LLM-005] LLM-as-judge ile provider kalite karşılaştırması yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: LLM-as-judge yok
- **Kanıt:** `app/coach.py:1242-1264`; `routers/coach.py:181-206`
- **Aksiyon:** DeepEval G-Eval/küçük judge ile offline puanla; trace'e provider+skor; haftalık dashboard.
- **Etki:** Orta · **Efor:** M

### [LLM-006] Token cost/latency ölçümü eksik — sadece süre
- **Durum:** ✅ KAPANDI (BUG #274 / ADR-053, 10 Ağu 2026). **Ölçüm eski durumu düzeltti:**
  "token trace'te" iddiası iyimserdi — trace gerçek token'ların yalnız **%24'ünü** yakalıyordu
  (yalnız koç sohbetinin ANA çağrısı; plan geçişi, retry, premortem, yansıma hiç) ve 90 günde
  siliniyordu. Deftere düşen token: **0/13**. Ayrıca çalışan model 7/13 satırda yanlıştı
  (zincirde birincilin modeli + amaç etiketi `model` sütununda). Artık her satır isteğin
  kimliğini taşır: sağlayıcı + çalışan model + token + `est_cost_usd` + `amac`. Fiyat tablosu
  (sağlayıcı, model) ile anahtarlanır; bilinmeyen fiyat `None` döner ve raporda ayrı sayılır.
- **Kanıt:** `app/llm_cost.py` + `app/llm_quota.py`; kapı `tests/test_llm_maliyet_kapisi.py`
  (17 test, mutasyon 6/6); operatör yüzeyi `scripts/beta_metrics.py`
- **Etki:** Orta · **Efor:** M

### [LLM-007] usage/provider_used/model_name sadece Groq'ta set ediliyor ✅ UYGULANDI (12 Tem 2026)
- **Durum:** ✅ KAPANDI (inline işaret)
- **Kanıt:** `coach.py:801,953,1064,1115` (yok) vs `1018-1020` (Groq)
- **Aksiyon:** Her provider usage çıkarsın (Anthropic `usage.input/output_tokens`, Gemini `usage_metadata`, OpenAI-uyumlu `usage`); provider_used/model_name kendi set etsin.
- **Etki:** Yüksek · **Efor:** S · **Not:** LLM-005/006'nın ön koşulu.

### [LLM-008] Tool-call şema doğrulaması yok — args sessizce {}
- **Durum:** 🟡 KISMEN (BUG #266 / ADR-048, 7 Ağu 2026) — **`propose_action` yolu KAPANDI:**
  payload artık Pydantic ile onay ÖNCESİNDE doğrulanır (`app/action_schema.py`, `extra=forbid`),
  eksik tool argümanı adlandırılmış hataya döner ve mevcut retry yoluna düşer; ek olarak
  özet↔payload tutarlılığı denetlenir ve red kullanıcıya görünür mesajla söylenir. Prompt
  şablonları şemadan üretilir. Kapı: `tests/test_aksiyon_payload_kapisi.py` (mutasyon 3/3).
  **`save_insight` yolu da KAPANDI (BUG #268 / ADR-050, 8 Ağu 2026):** argümanlar ham
  indeksleniyordu — eksik `content` sessizce yutuluyor, metin-olmayan `content` ise
  session'ı zehirleyip **tüm koç isteğini çökertiyordu**; `expires_at` serbest metinse ve
  `dedup_key` boşsa gerçek kayboluyordu. En sessiz yarısı: tool açıklaması "critical: asla
  unutulmamalı" derken enjeksiyon `sort_priority` + `limit(5)` ile sıralıyor ve bu yol o
  alanı hiç yazmıyordu → kullanıcının "asla kredi çekmem" beyanı hafızaya HİÇ girmiyordu.
  Tek kaynak `app/insight_schema.py` (tool şeması ÜRETİLİR), yazma savepoint içinde, red
  kullanıcıya söylenir. Kapı `tests/test_icgoru_kapisi.py` (34, mutasyon 5/5).
  **Açık kalan:** sağlayıcı tarafında `strict:true` + `additionalProperties:false`
  (Anthropic/OpenAI) uygulanmadı — sağlayıcıya bağlı, ayrı iş.
- **Kanıt:** `coach.py:1006-1009,1060-1063,1110-1114,911-913`; `:1659-1662`
- **Aksiyon:** PROPOSE/SAVE şemalarını Pydantic'e bağla; tool-call sonrası `model_validate`, hata→retry; Anthropic'te `strict:true`+`additionalProperties:false`.
- **Etki:** Yüksek · **Efor:** M

### [LLM-009] premortem.py kırılgan JSON parse — structured output kullan
- **Durum:** ✅ KAPANDI (BUG #270, 8 Ağu 2026). **Ölçüm (9 gerçekçi sarmalama biçimi):
  5'i düşüyordu** — hepsi JSON'un ETRAFINDAKI düz metin ("Elbette, işte analiz:",
  "Umarım yardımcı olur.", kalın başlık); JSON'un kendisi kusursuzdu, kusur ZARFTAYDI.
  `_parse_and_validate` fence'i yalnız **metnin tamamı** fence ise soyuyordu. Her düşüş
  iki deneme hakkından birini yakıyor; zayıf model alışkanlığını tekrarlarsa kullanıcı
  premortem'i HİÇ göremiyordu. **Sınıf taraması:** aynı sorunun kod tabanında ZATEN daha
  dayanıklı bir cevabı vardı (`coach_insights._erl_k2_parse_llm_json`) — iki cevap tek
  kaynağa indi (`app/llm_json.py`), ve yedeğin sessiz zayıflığı da kapandı (tarama artık
  **dizge-duyarlı**: metin içindeki `{` dengeyi bozmaz). Sözleşme: **zarfa toleranslı,
  içeriğe katı**. Sonuç 5/9 → **0/9**. Kapı `tests/test_llm_json_kapisi.py` (32,
  mutasyon 5/5). **Structured output (provider `response_schema`) UYGULANMADI:** sekiz
  sağlayıcının API'sine dağılır ve jenerik OpenAI-uyumlu sağlayıcılarda yok — zarf
  toleransı sağlayıcıdan bağımsız çalışır; şema doğrulaması zaten Pydantic'te.
- **Kanıt:** `app/premortem.py:167-189,225-262`
- **Aksiyon:** Provider'a `output_schema` param (Anthropic json_schema, Gemini response_schema, OpenAI response_format); fallback'te mevcut parse.
- **Etki:** Orta · **Efor:** M

### [LLM-010] is_question sınıflandırıcı kenar durumlarında hatalı
- **Durum:** ✅ KAPANDI (BUG #267 / ADR-049, 8 Ağu 2026) — kök neden "kenar durum" değil
  **kavram karışmasıydı:** tek bayrak iki bağımsız soruyu cevaplıyordu ("soruyor mu?" /
  "gerçekleşmiş olay bildiriyor mu?"), oysa KURAL SIFIR yalnız ikincisine bakar. Yeni sözleşme
  `propose_sunulsun = gerceklesmis OR (NOT soru AND NOT gelecek)` — tek kaynak
  `app/intent_rules.py`. İkinci eksen yazımdı: desenler yalnız diakritikli hâli tanıyordu
  (tek kaynak `app/tr_text.py`).
- **Ölçüm:** korpus 9/25 → 0/25 (düzgün yazım), 12/25 → 0/25 (diakritiksiz); uçtan uca
  (FakeProvider, gerçek koç akışı) 3/4 → 0/4; kırık token 20 → 0.
- **Kanıt:** `app/intent_rules.py`, `app/tr_text.py`, `tests/test_niyet_kapisi.py` (156 test)
- **Aksiyon (özgün):** (1) ~~geçmiş-zaman marker'ı varsa is_question=False zorla~~ → **REDDEDİLDİ:**
  konflasyonu düzeltmez, ters çevirir (bu kez soru bayrağı yalan söyler, trace okunamaz).
  Bayraklar ayrı kaldı, kararı sözleşme veriyor. (2) ~~küçük LLM intent classifier~~ →
  **REDDEDİLDİ:** bu bir güvenlik kapısı; deterministik olmayan katman KURAL SIFIR'ın önüne
  geçmemeli (gerekçe ADR-049 madde 4).
- **Etki:** Yüksek · **Efor:** M
- **Yan bulgu (sınıf taraması, aynı BUG):** `action_executor._DATE_KEYWORD_RE` ay adlarını
  diakritiksiz görmüyordu → TARIH_BELIRSIZ koruması çalışmıyor, işlem **sessizce bugüne**
  yazılıyordu. `coach_insights.QT_OPEN_PATTERN` `kaç`ı saymıyordu → koçun MI/OARS oranı düşük
  görünüyor, "direktif tarz" uyarısı haksız tetiklenebiliyordu.

### [LLM-011] Retry backoff'ta jitter yok — thundering herd
- **Durum:** ✅ KAPANDI (BUG #269 / ADR-051, 8 Ağu 2026) — tam-jitter
  (`app/provider_errors.bekleme_suresi`: `[0, min(tavan, taban·2^(n-1))]`, tavan 30 sn).
  Rastgelelik enjekte edilebilir → kapı beklemeyi deterministik ölçer.
- **Kanıt:** `coach.py:489`
- **Aksiyon:** Full jitter `random.uniform(0, base*2^n)` + max_delay; retry sayısını logla.
- **Etki:** Düşük · **Efor:** S

### [LLM-012] Retryable/quota sınıflandırması kırılgan string-match
- **Durum:** ✅ KAPANDI (BUG #269 / ADR-051, 8 Ağu 2026). **Ölçüm: 10 gerçekçi sağlayıcı hata
  metninin 3'ü yanlış sınıflandırılıyordu** — hepsi alt-dizi tuzağı: `token count (8504)
  exceeds` içindeki **8504**'ün "504"ü yüzünden GEÇİCİ sayılıyordu (kalıcı hata her istekte
  3 kez retry, devre kesici HİÇ açılmıyor, her denemede kullanıcının kotası yazılıyor);
  `request_id=req_8429fa1c` ve `took 4290 ms` ise "429" içerdiği için KOTA sayılıyordu.
  Tek kaynak `app/provider_errors.py`: **önce yapı** (durum kodu alanı ya da metnin
  BAŞI/açık etiket), sonra **sayısız** metin desenleri, öncelik **KALICI > KOTA > GEÇİCİ**.
  Sonuç 3/10 → **0/10**. Kapı `tests/test_saglayici_hata_kapisi.py` (39, mutasyon 5/5).
  **Tipli sağlayıcı istisnaları bilinçli olarak REDDEDİLDİ** (ADR-051): sekiz sağlayıcının
  SDK'sını motor katmanına sızdırır ve jenerik OpenAI-uyumlu sağlayıcılarda zaten çalışmaz —
  durum kodu bu SDK'ların ortak paydasıdır.
- **Kanıt:** `coach.py:437-471`
- **Aksiyon:** Tipli exception (Anthropic RateLimitError, status_code); 400 retry EDİLMEZ, 5xx/429 edilir; string fallback.
- **Etki:** Orta · **Efor:** M

### [LLM-013] Semantic caching yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: yanit cache yok
- **Kanıt:** `coach.py:1594-1601`
- **Aksiyon:** cockpit_hash + mesaj benzerliği; basit başlangıç: (mesaj normalize + cockpit_hash) exact-match, 60sn TTL; sonra embedding.
- **Etki:** Orta · **Efor:** M · **Not:** cockpit_hash cache key'e MUTLAKA dahil (stale finansal cevap riski).

### [LLM-014] Streaming yok — uzun raporlarda TTFB yüksek, timeout riski
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: streaming/SSE yok
- **Kanıt:** `coach.py:785-791,988-995`; Coach.jsx tam cevap bekliyor
- **Aksiyon:** `chat_stream` (SSE) en azından analiz yolunda; `get_final_message()` ile tam cevap. Bildirimde gerek yok.
- **Etki:** Orta · **Efor:** L

### [LLM-015] coach.py 1865 satır — modülerleştirme
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: coach.py 2641 satir
- **Kanıt:** `app/coach.py`
- **Aksiyon:** `app/coach/` paketi (providers/prompts/tools/memory/postprocess/engine); public API `__init__.py` (premortem import kırılmasın). Eval harness (LLM-004) ÖNCE.
- **Etki:** Orta · **Efor:** L · **Not:** BE-001 ile aynı.

### [LLM-016] MALFORMED_FUNCTION_CALL sadece atlanıyor, kök-neden azaltılmıyor
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: MALFORMED atlaniyor metrik yok
- **Kanıt:** `coach.py:811-819,931-940,880-882`
- **Aksiyon:** Gemini tool şemasını sadeleştir (payload'ı ayrık tool'lar) veya net-eylemde `mode="ANY"`; MALFORMED oranını metrik yap.
- **Etki:** Orta · **Efor:** M

### [LLM-017] History trim token değil karakter tabanlı
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: history trim karakter tabanli
- **Kanıt:** `coach.py:1276-1311,1294-1295`
- **Aksiyon:** Anthropic'te `count_tokens`; diğerlerinde muhafazakâr tahmin; tool_call/tool_result çiftlerini birlikte kes.
- **Etki:** Orta · **Efor:** M

### [LLM-018] format_insights_for_prompt cl100k_base tokenizer kullanıyor (yanlış)
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: format_insights cl100k primer
- **Kanıt:** `coach_insights.py:2160-2169`
- **Aksiyon:** char/3.5 heuristiği (mevcut ImportError fallback'i default yap) veya aktif provider count_tokens; cl100k bağımlılığını kaldır.
- **Etki:** Düşük · **Efor:** S

### [LLM-019] Confidence prompt-tabanlı ve kırılgan — structured output'a taşı
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: confidence prompt regex
- **Kanıt:** `coach.py:268-289,693-733`
- **Aksiyon:** Confidence'ı structured alan veya `_check_grounding`'den deterministik türet; prompt'tan CONFIDENCE bloğunu çıkar.
- **Etki:** Orta · **Efor:** M

### [LLM-020] Hallucination postprocess salt regex — kırılgan
- **Durum:** ✅ KAPANDI (BUG #271, 8 Ağu 2026). **Ölçüm üç eksende de delik gösterdi:**
  ① sahte tamamlama fiilleri **6/12 kaçıyordu** (liste #041 → #085 → #094 boyunca büyümüştü
  ve hâlâ "işleme aldım / kayda geçirdim / not olarak girdim / sisteme yazdım / hallettim /
  düştüm"i kaçırıyordu); ② **çok satırlı yanıtta koruma HİÇ çalışmıyordu** —
  `is_structured_report` dalı taramayı komple atlıyor, `"## Durum

Harcamanı kaydettim."`
  aksiyon yokken hiçbir uyarı olmadan kullanıcıya gidiyordu; ③ EMANET KASA silicisi bölümün
  **numaralanmış** olmasını şart koşuyordu → `## EMANET KASA` / `**EMANET KASA**` /
  `### Emanet Kasa` uydurma tutarla birlikte geçiyordu (**3/6**). Yanlış-pozitif 0/5 — filtre
  hassastı ama **kapsamı varsayımdı**. **Fix:** güvence artık **ifadeye değil DURUMA** bağlı —
  kullanıcı SAF BİLDİRİM yaptıysa (`intent_rules`: gerçekleşmiş VE soru değil) ve hiçbir
  aksiyon doğmadıysa cevaba dürüst not eklenir; fiilden ve yanıtın biçiminden bağımsız.
  Fiil listesi ikinci savunma olarak kaldı, katlanmış yazılıyor (L32) ve ölçülen korpusla
  birlikte kapıya yazıldı. Çok satırlı yanıtta artık iddia içeren SATIR atılır (rapor
  iskeleti korunur — BUG #085 iter2'nin haklı kaygısı). EMANET eşleşmesi numaraya değil
  YAPIYA bağlı. Sonuç: yanıltan 6/12 → **0/12**, çok satırlı 6/6 korumasız → **0/6**,
  EMANET 3/6 → **0/6**, yanlış-pozitif **0/5**. Kapı `tests/test_sahte_tamamlama_kapisi.py`
  (50, mutasyon 5/5 — biri kapının KENDİ kör noktasını kapattı: durum-notu satır taramasını
  gölgeliyordu, karışık-mesaj vakasıyla izole edildi).
- **Kanıt:** `coach.py:1318-1406`
- **Aksiyon:** Kısa vade: regex'i eval harness fixture'larına bağla; orta vade: rapor iskeletini structured output (bölüm listesi) — boş bölüm hiç üretilmez.
- **Etki:** Orta · **Efor:** M

### [LLM-021] Retry "[RETRY:...]" system'e enjekte ediyor — cache kırar
- **Durum:** ✅ KAPANDI (BUG #272, 8 Ağu 2026). **Ölçüm (sağlayıcının gördüğü `system_prompt`
  kaydedilerek):** `propose` retry'ında denemeler arası system **DEĞİŞİYOR** (`[RETRY: ...]`
  ekleniyor, messages sabit); soru retry'ı ise aynı işi doğru şekilde messages'a nudge olarak
  yapıyordu — **aynı dosyada, bir çağrı arayla iki farklı teknik** (BUG #270 sınıfı).
  **Sınıf taraması iki yer daha buldu:** iç plan TALİMATI kendi çağrısının system'ine, ÜRETİLEN
  plan metni ise ANA çağrının system'ine ekleniyordu (21.117 karakterin son 648'i her turda
  farklı — yani sözleşme, modelin o turda ürettiği metni taşıyordu). **Fix:** değişmez tek
  cümleye indi — *bir `chat()` turundaki HER sağlayıcı çağrısı AYNI system prompt'u görür*;
  yönlendirme `messages` sonuna eklenir ve üç yönlendirme tek yerde tanımlı. Kapı
  `tests/test_sistem_sozlesmesi_kapisi.py` (10, mutasyon 4/4 — bir mutasyonun kırmızısı
  sözdizimi kazasıydı, SAHTE kırmızı olarak elendi ve geçerli biçimde yeniden yazıldı).
  **Gerekçe abartılmadı:** ölçülen şey kazanç değil **yapısal ön koşul + sözleşme
  tutarlılığı**; cache kazancı LLM-002'ye aittir ve orada ölçülemediği için ertelendi.
  **Yan bulgu (meşru çıktı):** `system_prompt += _mkt_block` (FEAT-032 canlı döviz) ilk
  çağrıdan ÖNCE kurulan bağlamdır — kilit "ilk çağrıdan SONRA mutasyon yok" olarak daraltıldı;
  bağlamın system'de olup olmaması LLM-002 kapsamı.
- **Kanıt:** `coach.py:1697,1759,1691-1778`
- **Aksiyon:** Retry talimatını system'e değil messages sonuna ekle (cache prefix korunur); iki retry bloğunu tek `_retry_once(mode)`'da birleştir.
- **Etki:** Orta · **Efor:** M

### [LLM-022] Few-shot örnekleri prompt gövdesine gömülü — bakımsız
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: few-shot prompt govdesinde
- **Kanıt:** `coach.py:114-154`; wave3-vision:94-98
- **Aksiyon:** Örnekleri `prompts/fewshot.py`'ye al; provider yeteneğine göre koşullu enjekte; eval ile katkı ölç. (DSPy'ye hazırlık)
- **Etki:** Orta · **Efor:** M

### [LLM-023] Guardrail: yasaklar SADECE prompt+regex ile tutuluyor
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: output guard var ama yasak liste uzun
- **Kanıt:** `coach.py:127-146,1401-1404`; kod-seviyesi HESAP_BELIRSIZ (`:1677`) doğru katman
- **Aksiyon:** "Sahte tamamlama" tespitini deterministik output guard yap (tool çağrılmadı ama "kaydedildi"); prompt yasak listelerini kısalt.
- **Etki:** Orta · **Efor:** M

### [LLM-024] Gemini best-effort tool-history placeholder echo riski
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: Gemini placeholder echo
- **Kanıt:** `coach.py:838-862,37-42`
- **Aksiyon:** Gemini native `function_response` part'ı kullan (gerçek tool-aware geçmiş) veya tool-history senaryolarında zincirin arkasına al.
- **Etki:** Düşük · **Efor:** M

### [LLM-025] Provider client'ları lazy import — ilk çağrı latency + gizli hata
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: provider lazy import warmup yok
- **Kanıt:** `coach.py:771,827,968`; `routers/coach.py:247-256`
- **Aksiyon:** `build_provider`'da import hatalarını erken yakala; thread-safety doğrula; startup warmup (LLM-002 cache pre-warm ile birleştir).
- **Etki:** Düşük · **Efor:** S

### [LLM-026] Uzun history: sadece son 3 tur — stratejik bağlam kaybı
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: max_history_turns=3 compaction yok
- **Kanıt:** `coach.py:1493,1507-1526`
- **Aksiyon:** Anthropic compaction/context editing veya turn 3→5 + oturum-içi özet; insight-memory yaklaşımını koru.
- **Etki:** Orta · **Efor:** M

### [LLM-027] Trace her step'te commit — N+1 DB yazımı
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: TraceRecorder her step commit
- **Kanıt:** `reasoning_trace.py:168-171`; `coach.py:1568-1611`
- **Aksiyon:** Step'leri biriktir, sonda tek commit; finally'de garantile.
- **Etki:** Düşük · **Efor:** M · **Not:** BE-023 ile aynı.

### [LLM-028] provider_used FallbackProvider dışında set edilmiyor
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: provider_used/model_name set
- **Kanıt:** `coach.py:1146-1147,801/953/1064/1115,1606`
- **Aksiyon:** LLM-007 ile her provider kendi provider_used/model_name set etsin.
- **Etki:** Düşük · **Efor:** S

### [LLM-029] Temperature farklı ve sabit-kodlu — eval'siz
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: temperature sabit-kodlu
- **Kanıt:** `coach.py:868` (Gemini 0.4), `993,1047,1098` (0.2)
- **Aksiyon:** Çağrı tipine göre parametrize (tool 0.0-0.1, analiz 0.3-0.4); eval ile ölç. Anthropic'e temp gönderme (400).
- **Etki:** Düşük · **Efor:** S

### [LLM-030] max_tokens=4096 sabit — uzun rapor kesilme riski
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: max_tokens 4096 sabit
- **Kanıt:** `coach.py:787,869,994` vd.
- **Aksiyon:** Analiz 8000+, bildirim 1024; `stop_reason==max_tokens` yakala/logla; >16K streaming.
- **Etki:** Orta · **Efor:** S

### [LLM-031] Rate limiting yok — bug avında tüm provider'lar dolar
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: token-bucket throttle yok
- **Kanıt:** `routers/coach.py:284-290`; wave3-vision:163
- **Aksiyon:** In-memory token-bucket (10/dk); gerçek 429'da `retry-after` oku.
- **Etki:** Düşük · **Efor:** S · **Not:** SEC-004 ile örtüşür.

### [LLM-032] Fallback'te 429 retry-after header'ı okunmuyor
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: 429 retry-after okunmuyor
- **Kanıt:** `coach.py:463-471,1157-1166`
- **Aksiyon:** retry-after oku; kısaysa (<5sn) primary'de bekle, uzunsa fallback; konfigüre edilebilir.
- **Etki:** Düşük · **Efor:** M

### [LLM-033] Cockpit her chat'te yeniden üretiliyor — cache yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: cockpit her chat memoize yok
- **Kanıt:** `coach.py:1564-1566,525-527`; wave3-vision:163
- **Aksiyon:** Kısa TTL (10sn) memoize, key=user_id+son değişiklik ts; pending onayında invalidate.
- **Etki:** Düşük · **Efor:** S · **Not:** BE-036/LLM-013 ile ilişkili.

### [LLM-034] Grounding için ham cockpit dict kullanılmıyor
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: check_grounding ham cockpit
- **Kanıt:** `coach.py:602-640,1856`
- **Aksiyon:** `_check_grounding` (LLM-003) için mevcut `cockpit` dict'ini kaynak-doğruluk olarak kullan (mimari değişmez).
- **Etki:** Orta · **Efor:** S

### [LLM-035] save_insight soru modunda hep aktif — istenmeyen yazım
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: save_insight soru modunda aktif
- **Kanıt:** `coach.py:1584,1630-1649`
- **Aksiyon:** dedup_key boşsa yazma; selamlaşmada save_insight'ı kapat; içeriği şema ile doğrula.
- **Etki:** Düşük · **Efor:** S

### [LLM-036] Propose sonrası execute sonucu LLM'e dönmüyor (tek tur)
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: execute sonucu history'ye donmuyor
- **Kanıt:** `coach.py:1652-1685`; execute ayrı endpoint
- **Aksiyon:** propose→onay→execute'i koru; execute sonrası tool_result'ı history'ye yazıp opsiyonel "koç yorumu" (BUG #036 altyapısı var). LLM yine DB yazmaz.
- **Etki:** Orta · **Efor:** M

### [LLM-037] Anthropic tool mapping strict/örnek kullanmıyor
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: Anthropic tool strict yok
- **Kanıt:** `coach.py:776-783,358-360`
- **Aksiyon:** `strict:true`+`additionalProperties:false`+`required`; payload'ı action_type'a göre anyOf; description'a örnek.
- **Etki:** Orta · **Efor:** M

### [LLM-038] Chat hatası düz string reply — yapısal sınıflandırma yok
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: ham exception loglu ama tip siniflandirma yok
- **Kanıt:** `coach.py:1612-1621`; `routers/coach.py:306-313`
- **Aksiyon:** Hata tipine göre kullanıcı mesajı (quota/network/400); ham exception gösterme, logla (request_id).
- **Etki:** Düşük · **Efor:** S

### [LLM-039] reasoning_traces var ama LLM-kalite metrikleri toplanmıyor
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: trace var ama grounding_ok/ozet yok
- **Kanıt:** `reasoning_trace.py:57-67`; `routers/coach.py:104-110`
- **Aksiyon:** Trace'e `grounding_ok`, `retry_count`, `format_valid`, `tool_schema_error`; haftalık özet endpoint'i. (SQLite üstünde küçük agregasyon)
- **Etki:** Orta · **Efor:** M

### [LLM-040] Fallback sonuç kalitesi kontrol edilmiyor — boş/bozuk metin geçebilir
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: FallbackProvider kalite gecidi yok
- **Kanıt:** `coach.py:1139-1173,1413-1440`
- **Aksiyon:** Fallback sonrası minimal kalite geçidi (çok kısa+tool yok+soru değil veya grounding-ihlali → sonraki provider); max_attempts ile sınırla.
- **Etki:** Orta · **Efor:** M

---
**Kaynaklar:** claude-api skill (Opus 4.8, adaptive thinking, prompt caching, strict tool use, count_tokens); promptfoo/DeepEval; prompt/semantic caching (Introl, Maxim, arxiv 2601.06007); LLM guardrails/hallucination (Leanware, FutureAGI).
