# Backend mimari & kod kalitesi (kod: BE)

### [BE-001] `coach.py` 1865 satırlık tanrı-modülü domain paketine bölünmeli
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: coach.py 2640 satır tek modül
- **Sorun:** Tek dosyada prompt, 6 provider, retry helper, confidence parser, history, post-processor, `CoachEngine`. Değişiklik yüzeyi kocaman, test edilemez, merge çatışması mıknatısı.
- **Kanıt:** `app/coach.py:1-1865`
- **Aksiyon:** `app/coach/` paketi: `providers/`, `prompts.py`, `context.py`, `parsing.py`, `history.py`, `engine.py`. Public API `__init__.py` ile korunur.
- **Etki:** Yüksek · **Efor:** L · **Not:** Davranış değişmeden saf taşıma; her adımda test çalıştır. (zhanymkanov/fastapi-best-practices)

### [BE-002] OpenAI-uyumlu 3 provider `_raw_chat` gövdesi neredeyse birebir aynı
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: _OpenAICompatMixin var ama Groq/Cerebras/OpenRouter kopya gövde
- **Sorun:** Groq/Cerebras/OpenRouter `_raw_chat` kodu kopya; bir bug 3 yerde düzeltiliyor.
- **Kanıt:** `app/coach.py:972-1023, 1039-1067, 1090-1118`
- **Aksiyon:** `OpenAICompatibleProvider` temel sınıfı (`base_url`, `NAME`, `DEFAULT_MODEL`, `default_headers` param); üçü türesin.
- **Etki:** Yüksek · **Efor:** M

### [BE-003] `V3_GOD_MODE_PROMPT` 200 satırlık inline literal koddan ayrılmalı
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: V3 prompt inline literal, prompts/ yok
- **Sorun:** ~195 satır system prompt kod içinde; iterasyon = kod diff, sürüm karşılaştırması imkânsız.
- **Kanıt:** `app/coach.py:96-290`
- **Aksiyon:** `app/prompts/coach_v3.md`'ye al, `importlib.resources` ile UTF-8 oku; `PROMPT_VERSION`'ı trace'e yaz.
- **Etki:** Orta · **Efor:** S

### [BE-004] `CoachEngine.chat()` tek metotta ~300 satır — ReAct adımları çıkarılmalı
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: CoachEngine.chat() 366 satır tek metot
- **Sorun:** cockpit kurulumu, sınıflandırma, LLM çağrısı, tool döngüsü, 2 retry bloğu, post-process, DB, trace tek fonksiyonda.
- **Kanıt:** `app/coach.py:1549-1858`
- **Aksiyon:** `_classify_tools`, `_handle_tool_calls`, `_retry_force_action`, `_retry_question`, `_persist_turn` private metotlarına böl.
- **Etki:** Yüksek · **Efor:** M

### [BE-005] `propose_action` tool döngüsü ana akış ile retry bloğunda kopyalanmış
- **Durum:** ✅ KAPANDI (9 Ağu 2026, BUG #273) — kopya SADECE teorik borç değildi: kopyalanırken
  `TARIH_BELIRSIZ` dalı düşmüştü ve retry yolunda sinyal ele alınmıyordu (ölçüldü).
- **Kanıt:** `CoachEngine._propose_tek_cagri` tek kaynak; ana akış ve retry aynı metodu çağırır.
- **Doğrulama:** `tests/test_aksiyon_sinyali_kapisi.py::test_koc_yardimcisi_tek_kaynaktir`
  (gövde `chat()` içine geri kopyalanamaz).
- **Etki:** Orta · **Efor:** S

### [BE-006] İş kuralı sinyalleri istisna string'iyle taşınıyor (`"HESAP_BELIRSIZ"`)
- **Durum:** ✅ KAPANDI (9 Ağu 2026, BUG #273 / ADR-052)
- **Sorun:** `raise ValueError("HESAP_BELIRSIZ")` + `if "HESAP_BELIRSIZ" in str(e)`.
  "Refactor'da sessizce bozulur" öngörüsü **zaten gerçekleşmişti**: 4 sinyal × 2 tüketici
  matrisinin 1 hücresi yanlıştı (retry `TARIH_BELIRSIZ`i hiç ele almıyordu). İki yan bulgu:
  iç sinyal adı kullanıcıya görünen trace "Gözlem" satırına yazılıyordu; sinyal-teşhis
  füzyonu yüzünden iki log satırı kullanıcının tutarlarını içeriyordu (BUG #180 ihlali).
- **Kanıt/fix:** `app/action_errors.py` (`AksiyonReddi` + 5 alt sınıf; kullanıcı mesajı,
  iz gerekçesi ve retry kararı sınıfın üzerinde, teşhis `str(e)`ye girmez).
- **Doğrulama:** `tests/test_aksiyon_sinyali_kapisi.py` (30; AST kapıları + davranış matrisi;
  mutasyon 6/6). Ölçüm 1/8 → 0/8, iz sızıntısı 4 → 0, tutar içeren log 2 → 0.
- **Etki:** Orta · **Efor:** S

### [BE-007] Async scheduler job'ları event loop içinde bloklayan sync DB çağrısı yapıyor
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: async job içinde sync SessionLocal event loop'ta
- **Sorun:** `nightly_batch_job`/`k2_batch_job` async ama sync `SessionLocal()`+`db.query().all()`+K2 LLM çalıştırıyor; AsyncIOScheduler bunları FastAPI event loop'unda koşturunca tüm loop bloklanır.
- **Kanıt:** `app/scheduler.py:144-169`, `app/main.py:110-127`
- **Aksiyon:** `run_in_executor` ile threadpool veya `BackgroundScheduler`.
- **Etki:** Yüksek · **Efor:** M

### [BE-008] `time.sleep` ile senkron retry — event loop bağlamında risk
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: time.sleep(wait) senkron retry (coach.py:675)
- **Kanıt:** `app/coach.py:493`
- **Aksiyon:** BE-007 ile provider çağrılarını executor'a taşı; alternatif `tenacity`.
- **Etki:** Orta · **Efor:** S

### [BE-009] Merkezî exception handler yok — `chat` endpoint hataları 200 ile gizliyor
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: ham hata kapatıldı ama chat provider hatasında 200 döner
- **Sorun:** `/api/coach/chat` tüm `Exception`'ı yakalayıp `reply="...{e}"` ile HTTP 200 dönüyor; istemci başarı sanır, ham exception sızar, monitoring 5xx görmez.
- **Kanıt:** `app/routers/coach.py:306-313`
- **Aksiyon:** `add_exception_handler(DomainError,...)` + genel Exception handler; 500 + `problem+json`. (FastAPI Handling Errors + RFC 9457)
- **Etki:** Yüksek · **Efor:** M

### [BE-010] `except Exception: pass` sessiz yutma 6 yerde ✅ UYGULANDI (12 Tem 2026)
- **Durum:** ✅ KAPANDI (inline işaret)
- **Kanıt:** `app/coach.py:391`, `app/action_executor.py:246`, `app/routers/cockpit.py:93`, `app/routers/coach.py:234,363`, `app/goal_engine.py:109`
- **Aksiyon:** `logger.warning(..., exc_info=True)`; dar exception tipi. Özellikle `_to_openai_messages` (391) bozuk tool_calls_json'u sessizce düşürüyor.
- **Etki:** Orta · **Efor:** S
- **Durum:** 6 sessiz `except: pass` → uygun seviyeli loglama (davranış DEĞİŞMEDİ, hâlâ yutar ama TANILANABİLİR): goal_engine `_project_debt_freedom` (warning — tam bu except #066'da AttributeError'ı gizliyordu, log olsa erken yakalanırdı), action_executor mesaj-biçimlendirme (warning), cockpit snapshot best-effort (warning — trend sessizce boş kalmasın), routers/coach history pending-kart (warning) + ids parse (debug), coach history tool_calls parse (debug). goal_engine + cockpit'e logger eklendi. Süit 649 yeşil.

### [BE-011] Executor `{success, error}` dict sözleşmesi ile router kontrolü tutarsız
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: router 404/422 çeviriyor ama executor dict döner, MC 422
- **Sorun:** İstisna yerine dict dönüyor; emanet ihlali (iş kuralı) ile "aksiyon bulunamadı" (404) aynı kanaldan, HTTP statü ayrımı kayboluyor.
- **Kanıt:** `app/action_executor.py:255-335`; tüketim `app/routers/actions.py:257-261`
- **Aksiyon:** `MasterCheckpointViolation`/`NotFoundError` tipli istisna; merkezî handler 403/404/422'ye çevirsin. Enforcement kod seviyesinde kalır.
- **Etki:** Orta · **Efor:** M

### [BE-012] Config: `os.getenv` 14 çağrıda dağınık, tip/validasyon yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: os.getenv dağınık, BaseSettings yok
- **Kanıt:** `app/database.py:16`, `app/coach.py:1184-1222`, `app/rules_engine.py:46`, `app/routers/actions.py:46,115`
- **Aksiyon:** `app/config.py` `pydantic_settings.BaseSettings` + `@lru_cache get_settings()`, dependency olarak enjekte.
- **Etki:** Yüksek · **Efor:** M

### [BE-013] `get_db` iki dosyada tanımlı — drift riski
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: get_db iki dosyada (database.py:63, dependencies.py:20)
- **Kanıt:** `app/database.py:38-47`, `app/dependencies.py:17-23`
- **Aksiyon:** Tek tanım `dependencies.py`'de; database'deki silinsin/re-export.
- **Etki:** Orta · **Efor:** S

### [BE-014] `create_all` / Alembic tutarsızlığı ve ölü `init_db`
- **Durum:** ✅ KAPANDI (M87) — app/PROJE.md 'startup create_all' çelişkisi düzeltildi (alembic/ADR-013 notu)
- **Sorun:** Alembic'e geçilmiş ama `database.py:50 init_db()` hâlâ `create_all`; `app/PROJE.md` "startup create_all" diyor. create_all migrate etmez → şema drift; doküman-kod çelişki.
- **Kanıt:** `app/database.py:50-57`, `app/main.py:109-118`, `app/PROJE.md`, `alembic/versions/*`
- **Aksiyon:** `init_db`'yi setup/test-only yap; PROJE.md'leri "schema Alembic ile" güncelle.
- **Etki:** Yüksek · **Efor:** S

### [BE-015] Router→service→repository katmanı yok; iş mantığı router içinde
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: service katmanı eksik, iş mantığı router'da
- **Kanıt:** `app/routers/transactions.py:84-189`, `actions.py:65-157`, `reports.py:141-236`
- **Aksiyon:** `app/services/` (`transaction_service`, `reflection_service`, `cashflow_service`); router sadece doğrulama+servis+serialize.
- **Etki:** Yüksek · **Efor:** L

### [BE-016] `_apply_to_balance` bakiye mantığı executor ile ayrık ve tekrar
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: bakiye mantığı transactions+action_executor ayrık tekrar
- **Sorun:** İşlem→bakiye etkisi `transactions.py` ve executor'da ayrı; kart/nakit/kredi işaret mantığı iki yerde.
- **Kanıt:** `app/routers/transactions.py:84-125` ve `app/action_executor.py:465-479`
- **Aksiyon:** Tek `apply_transaction_to_balance(...)` `services/transaction_service.py`'de.
- **Etki:** Yüksek · **Efor:** M

### [BE-017] Goals router'ında sahiplik sorgusu her endpoint'te tekrar (18 `.query`)
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: goals get_owned_goal dependency yok, tekrar
- **Kanıt:** `app/routers/goals.py:108-374` (10+ blok)
- **Aksiyon:** `get_owned_goal` dependency; `goal: Goal = Depends(get_owned_goal)`.
- **Etki:** Orta · **Efor:** M

### [BE-018] Legacy `session.query()` yaygın (138 kullanım) — 2.0 `select()`
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: .query() 138+ kullanım, select() göçü yok
- **Kanıt:** 138 occurrence; `app/PROJE.md` "select() tercih" ama uygulanmamış.
- **Aksiyon:** Yeni kod `select()` zorunlu; sık dokunulanları kademeli göç.
- **Etki:** Orta · **Efor:** L

### [BE-019] Repository pattern yok — `user_id` filtre mantığı elle her yerde
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: UserScopedRepository yok
- **Sorun:** Her sorguda `.filter(X.user_id==...)` elle; birini unutmak multi-user'da veri sızıntısı.
- **Kanıt:** accounts/transactions/debts/goals tüm CRUD
- **Aksiyon:** `UserScopedRepository`; en azından Account/Transaction ile başla.
- **Etki:** Orta · **Efor:** L

### [BE-020] Pydantic şemaları hem `schemas.py` hem router-içi çift, bazıları ölü
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: router-içi inline şema schemas.py dublicate
- **Kanıt:** `app/schemas.py:19-249` vs `routers/accounts.py:30-82`, `user.py:26-40`, `coach.py:52-146`; `AccountRead`/`CockpitSnapshot` import edilmiyor.
- **Aksiyon:** Tek kaynak; router-içi kullanılanları schemas.py'ye taşı, ölüleri sil.
- **Etki:** Orta · **Efor:** M

### [BE-021] `float` para — `Decimal` tutarsızlığı
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: ADR-030 Numeric/Decimal göçü + floatify sınır
- **Kanıt:** `app/schemas.py:24,26,28` (float) vs `259,277,292` (Decimal); action_executor her yerde `float()`.
- **Aksiyon:** Depolamada `Numeric(14,2)`+`Decimal` standardize veya ADR ile "float MVP, Decimal Wave-3". (DATA-001/RULE-040 ile aynı kök)
- **Etki:** Orta · **Efor:** L

### [BE-022] Structured/JSON logging ve korelasyon yok
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: JSON logging var ama request-id/trace correlation yok
- **Kanıt:** `app/main.py:57-61` tek `basicConfig`
- **Aksiyon:** `structlog` JSON + request-id middleware + `contextvars` (`trace_id`/`user_id`).
- **Etki:** Orta · **Efor:** M

### [BE-023] `ReasoningTrace` her adımda commit — chat başına N commit
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: TraceRecorder.step() her adım commit (reasoning_trace.py:169)
- **Kanıt:** `app/reasoning_trace.py:168-171`
- **Aksiyon:** Step'leri biriktir, `chat()` sonunda tek flush+commit.
- **Etki:** Orta · **Efor:** M

### [BE-024] Sihirli sabitler dağınık (reflection eşiği, kategori, limitler)
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: sihirli sabitler dağınık, constants.py yok
- **Kanıt:** `app/routers/actions.py:49-50`, `action_executor.py:47`, `coach.py:1276-1277`, `routers/coach.py:153`
- **Aksiyon:** `Settings`'e (davranışsal) + `app/constants.py`'ye (iş kuralı) topla.
- **Etki:** Düşük · **Efor:** S

### [BE-025] Usage/limit mantığı Gemini'ye sabit kodlu — fallback'te yanlış %0 ✅ UYGULANDI (12 Tem 2026)
- **Durum:** ✅ KAPANDI (inline işaret)
- **Kanıt:** `app/routers/coach.py:153,169-178`
- **Aksiyon:** Provider→limit haritası config'ten; fallback'te gerçek alt-provider'ı ayrıştır+normalize.
- **Etki:** Orta · **Efor:** S
- **Durum:** İki sorun çözüldü. (1) FONKSİYONEL: fallback modda usage hep %0 dönüyordu → pre-call günlük-limit BLOCK koruması ÖLÜYDÜ (Gemini kotası dolsa bile çağrı engellenmiyordu). (2) DOĞRULUK: nominal "fallback" loglanıyordu → Gemini sayacı hep 0. Fix: `PROVIDER_DAILY_LIMITS` haritası + `_daily_constrained_provider` (fallback/gemini→gemini, circuit breaker gpt-oss'u eleyince fiili birincil Gemini); engine.chat çıktısına `provider_used` eklendi → router İSTEĞE FİİLEN CEVAP VEREN alt-sağlayıcıyı loglar. TPM-limitli sağlayıcı (Groq/Cerebras) günlük % yerine sayı gösterir (yanıltıcı 999999 değil). 5 test (test_usage_tracking.py). Provider gerçeğiyle (memory: reference_groq_tpm_limiti) tutarlı.

### [BE-026] `_engine` global singleton — thread-safe değil, config donuk
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: _engine global singleton, app.state'e taşınmadı
- **Kanıt:** `app/routers/coach.py:249-256`
- **Aksiyon:** `lifespan`'da kur, `app.state.coach_engine`; `Depends(get_coach_engine)`.
- **Etki:** Orta · **Efor:** S

### [BE-027] `is_question` regex sezgiseli kırılgan ve dile gömülü
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: is_question regex coach.py'de gömülü
- **Kanıt:** `app/coach.py:78-89`, kullanım `1583-1584`
- **Aksiyon:** Test corpus + `intent.py`'ye izole. (LLM-010 ile hizalı)
- **Etki:** Orta · **Efor:** M

### [BE-028] Post-processor regex zinciri test-kapsamasız kırılganlık
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: _postprocess_report regex coach.py içinde
- **Kanıt:** `app/coach.py:1318-1406`
- **Aksiyon:** `postprocess.py`'ye izole + her BUG için birim testi.
- **Etki:** Orta · **Efor:** M

### [BE-029] AsyncIOScheduler çok-kullanıcı batch'i tek session'da sıralı — hata yalıtımı zayıf
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: rollback eklendi ama batch tek paylaşılan session
- **Kanıt:** `app/scheduler.py:148-152`, `run_periodic_batch_for_user:123-129`
- **Aksiyon:** User başına ayrı session scope + hata'da rollback.
- **Etki:** Orta · **Efor:** S

### [BE-030] `_next_occurrences` cashflow projeksiyonu router'da, rules_engine ile örtüşüyor
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: upcoming_cashflow router'da, rules_engine örtüşme
- **Kanıt:** `app/routers/reports.py:141-236` vs rules_engine `upcoming_*`
- **Aksiyon:** Tek yerde (`services/cashflow_service.py` veya rules_engine — okuma-only).
- **Etki:** Orta · **Efor:** M

### [BE-031] `datetime.utcnow()` deprecated + naive/aware karışıklığı
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: datetime.utcnow() deprecated ~40 kullanım
- **Kanıt:** `app/action_executor.py:319,354,368,402`, `scheduler.py:146,155` vs `main.py:205`
- **Aksiyon:** Tek `now_utc()` helper; serialize helper'ı merkezîleştir.
- **Etki:** Orta · **Efor:** M

### [BE-032] CORS origin listesi kod içinde sabit
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: CORS _compute_cors_origins env-driven (main.py:140)
- **Kanıt:** `app/main.py:152-163`
- **Aksiyon:** `Settings.cors_origins`'ten oku (BE-012).
- **Etki:** Düşük · **Efor:** S

### [BE-033] `main.py` runtime içinde `scripts.*` import ediyor — katman ihlali
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: scripts startup.py'ye taşındı ama runtime scripts'e bağımlı
- **Sorun:** `from scripts.backfill_net_worth import run_backfill`; app runtime'ı scripts'e bağımlı, dağıtımda bulunmayabilir.
- **Kanıt:** `app/main.py:68-106`
- **Aksiyon:** `run_backfill`'i `app/services/net_worth_service.py`'ye taşı.
- **Etki:** Orta · **Efor:** M

### [BE-034] Endpoint'ler ham `db.query` döndürüyor — response_model tutarsız
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: transactions ham dict, accounts response_model tutarsız
- **Kanıt:** `transactions.py:196` (dict), `cockpit.py:53` (dict) vs `accounts.py:89`
- **Aksiyon:** `TransactionRead` (`ConfigDict(use_enum_values=True)` — manuel serializer ölü kod olur), cockpit için model.
- **Etki:** Orta · **Efor:** M

### [BE-035] Reject aksiyonu `ActionHistory` yazmıyor — asimetrik denetim izi
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: reject ActionHistory yazmıyor, approve yazıyor asimetri
- **Kanıt:** `app/routers/actions.py:226-319` (approve zengin) vs `322-336` (reject yalın)
- **Aksiyon:** Reddedilenler için hafif history/log; action_rejection_pattern extractor'ıyla hizala.
- **Etki:** Düşük · **Efor:** S

### [BE-036] `approve_action` tek istekte cockpit'i 2 kez hesaplıyor
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: approve generate_cockpit 2 kez çağırıyor (actions.py:245,271)
- **Kanıt:** `app/routers/actions.py:239,264`
- **Aksiyon:** Hafif skaler hesap veya before'u pending'ten türet. Önce profille.
- **Etki:** Düşük · **Efor:** S

### [BE-037] `_run_reflection` kendi `SessionLocal()`/provider'ını elle kuruyor (DI baypası)
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: _run_reflection elle SessionLocal+provider, service yok
- **Kanıt:** `app/routers/actions.py:65-157`
- **Aksiyon:** `services/reflection_service.py`; provider `Settings`+factory'den.
- **Etki:** Orta · **Efor:** M

### [BE-038] Şema doğrulama boşlukları — negatif tutar/gelecek tarih serbest
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: amount≤0 bloklandı ama gelecek-tarih validator yok
- **Kanıt:** `app/schemas.py:107,24` vs `:259` (`gt=0`); router kontrolü `transactions.py:265`
- **Aksiyon:** Tutar alanlarına `Field(gt=0)`, tarih validator; transfer işaret mantığı `_apply_to_balance`'ta eksik.
- **Etki:** Orta · **Efor:** S

### [BE-039] `delete_account`/`delete_transaction` cascade tanımsız — SQL hatası sızıyor
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: delete_account bağlı sayıp 409, ham FK 500 kapandı
- **Sorun:** Docstring itiraf ediyor: bağlı transaction varken hesap silinince ham FK hatası (500 yerine 409 olmalı).
- **Kanıt:** `app/routers/accounts.py:194-221`
- **Aksiyon:** Silmeden count→409, veya soft-delete (finansal iz).
- **Etki:** Orta · **Efor:** M

### [BE-040] Test altyapısı pytest değil; refactor'lar için güvenlik ağı zayıf
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: pytest altyapısı canlı (in-memory + FakeProvider)
- **Sorun:** Kök `test_*.py` `__main__` gibi akan scriptler; yukarıdaki refactor'lar regresyonsuz yapılamaz.
- **Kanıt:** `docs/dev-commands.md`, kök `test_coach.py` vb.
- **Aksiyon:** pytest + in-memory SQLite fixture + provider mock; MC enforcement mutlaka birim testli. (TEST bölümüyle örtüşür — ön koşul)
- **Etki:** Yüksek · **Efor:** L

---
**Kaynaklar:** zhanymkanov/fastapi-best-practices; FastAPI Handling Errors/Dependencies; pydantic-settings; SQLAlchemy 2.0 asyncio + migration; Alembic; RFC 9457; structlog.
