# Denetim: app/routers/coach.py

### [RCO-001] Fallback provider modunda gunluk limit koruma ve provider bazli istatistik kirilir
- **Sorun:** `provider_name` (satir 280) `engine.provider_name` degerinden turetiliyor. `CoachEngine.provider_name` (app/coach.py satir 1501-1505) `FallbackProvider` kullanildiginda ve `last_used_provider` set edildiginde `"Fallback(Gemini)"` gibi bir string doner. `.replace("Provider", "")` (satir 280) bu string uzerinde hicbir sey degistirmez (alt string "Provider" gecmiyor), sonuc `.lower()` ile `"fallback(gemini)"` olur. `_build_usage_info` (satir 169-178) ise sadece `provider == "gemini"` esitligini kontrol ediyor; `"fallback(gemini)" != "gemini"` oldugundan `daily_limit=999999`, `percentage=0.0` sabitlenir — yani gercekte Gemini'nin 1500/gun ucretsiz kotasi kullanilirken sistem hicbir zaman `%80 uyari` veya `%100 block` (satir 285-290) tetiklemez. Ayrica `_log_api_call` (satir 316-320) her cagriyi degisen `provider_name` degeriyle (cagridan cagriya "Fallback", "Fallback(Gemini)", "Fallback(Groq)" gibi farkli stringlerle) kaydeder; bu da `ApiCallLog.provider` bazli index'i (models.py satir 488, docstring: "Provider bazli ayri sayim") parcalar ve `_today_call_count` (satir 156-166) filtre esitligi hicbir zaman gercek kayitlarla eslesmez.
- **Kanit:** app/routers/coach.py satir 280, 284-290, 316-320, 169-178; app/coach.py satir 1501-1505.
- **Aksiyon:** `provider_name` hesaplamasinda Fallback sarmalayicisindan asil saglayici adini cikar (orn. regex/parse ile `"Fallback(Gemini)"` -> `"gemini"`), ya da `_build_usage_info`'ya "fallback icindeki asil provider" mantigini ekle. `.env` dokumantasyonunda `LLM_PROVIDER=fallback` desteklendigi belirtildigi icin (docs/dev-commands.md) bu mod icin kota korumasi calismali.
- **Onem:** Kritik · **Guven:** Kesin

### [RCO-002] Gunluk kullanim sayaci UTC yerine sunucu yerel saatine gore sifirlaniyor
- **Sorun:** `_today_call_count` (satir 156-166) gun baslangicini `date.today()` (sunucu yerel tarihi) ile hesaplayip `datetime.combine(date.today(), datetime.min.time())` seklinde naive bir sinir olusturuyor. Ancak `ApiCallLog.called_at` `default=datetime.utcnow` ile UTC-naive olarak yaziliyor (models.py satir 480) ve proje genelinde PROJE.md/architecture.md aciyor: "DB'deki tum DateTime alanlari timezone-naive UTC". Sunucu Turkiye saatinde (UTC+3) calisiyorsa, yerel gece yarisi UTC 21:00'e denk gelir; yerel 00:00-02:59 araliginda (yani gercek UTC gunu henuz bitmeden) `today_start` bir sonraki gune atlar ve o ana kadar UTC gununde yapilmis cagrilar sayimdan duser — gunluk sayac gercekte olmasi gerekenden 3 saat erken sifirlanir, kullanici Gemini'nin gercek 1500/gun kotasini asma riskiyle karsi karsiya kalir (block/warn hicbir zaman dogru esikte tetiklenmez).
- **Kanit:** satir 157 (`date.today()`), models.py satir 480 (`default=datetime.utcnow`).
- **Aksiyon:** `date.today()` yerine `datetime.utcnow().date()` kullanilarak gun siniri UTC'ye gore hesaplanmali — tum diger datetime islemleriyle tutarli olur.
- **Onem:** Yuksek · **Guven:** Kesin

### [RCO-003] tool_calls_count metrigi yanlis/eksik sayiyor
- **Sorun:** Satir 305'te `tool_calls_count = len(result.get("proposed_actions") or [])` — yani ApiCallLog'a yazilan "tool kullanim ozeti" (models.py satir 470-471 docstring) aslinda sadece `propose_action` cagrilarinin sayisini yansitiyor. LLM ayrica `save_insight` adinda ikinci bir tool cagirabiliyor (app/coach.py satir 298, 335) ve bu cagrilar `proposed_actions` listesine hic girmiyor. Dolayisiyla LLM bir turda sadece `save_insight` cagirip hicbir aksiyon onermezse, gercekte 1 tool-call olmustur ama loglanan `tool_calls_count=0` olur — metrik yanlis, ileride "maliyet analizi" (models.py docstring'de belirtilen amac) icin kullanilirsa yanlis sonuc uretir.
- **Kanit:** satir 305; app/coach.py satir 298, 335 (save_insight/propose_action tool tanimlari), models.py satir 470-471.
- **Aksiyon:** `engine.chat()` donus sozlugune gercek toplam tool-call sayisini (LLMResponse.tool_calls uzunlugu, retry turlari dahil) ekleyip router'da onu kullan; `proposed_actions` sayisini ayri bir alanla (orn. `proposed_action_count`) tut.
- **Onem:** Orta · **Guven:** Kesin

### [RCO-004] HistoryItem zorunlu datetime alanlarina None sizma ihtimali
- **Sorun:** `CoachMemory.timestamp` sutunu `Column(DateTime, default=datetime.utcnow)` seklinde tanimli (models.py satir 301) — `nullable=False` ACIKCA belirtilmemis, yani SQLAlchemy varsayilani ile bu sutun NULL kabul edebilir (default sadece ORM insert aninda deger verilmezse uygulanir; toplu/manuel insert senaryolarinda atlanabilir). `_memory_to_history_item` (satir 221-223) bunu bilerek `if ts is not None and ...` guard'i koymus, yani None ihtimalini ongormus. Ancak guard sadece tzinfo eklemeyi atliyor; `ts` (None olabilir) yine de `HistoryItem(timestamp=ts, created_at=ts, ...)` (satir 241-242) olarak donduruluyor ve `HistoryItem.timestamp` / `created_at` alanlari Optional degil (satir 136-137). `ts=None` durumunda Pydantic ValidationError firlatir ve `/api/coach/history` 500 doner — guard'in "koruma" niyeti fiilen bir crash'e donusuyor.
- **Kanit:** satir 136-137, 221-223, 241-242; models.py satir 301.
- **Aksiyon:** Ya `CoachMemory.timestamp` kolonuna `nullable=False` ekle (mevcut satirlarin hepsi zaten default ile dolu oldugu icin guvenli bir migration), ya da `_memory_to_history_item` icinde `ts is None` durumunda kaydi atla/`return None` yap, ya da `HistoryItem` alanlarini `Optional[datetime]` yap.
- **Onem:** Orta · **Guven:** Dogrulanmali (calisma zamaninda tetiklenmesi icin timestamp'in gercekten NULL yazilmasi gerekir; normal ORM akisinda default her zaman uygulaniyor)

### [RCO-005] Sessiz except/pass blollari JSON parse hatalarini loglamadan yutuyor
- **Sorun:** `_memory_to_history_item` icinde satir 234-235 (`except Exception: pass`) ve `get_history` icinde satir 363-364 (`except Exception: pass`) — `pending_action_ids_json` bozuksa (orn. kismi yazim, manuel DB duzenlemesi) sessizce yutuluyor, hicbir `logger.warning` yok. Proje genelinde `_log_api_call` gibi diger except bloklari en azindan `logger.warning` cagiriyor (satir 204-206); bu iki blok o pattern'i takip etmiyor, bozuk veri sessizce kaybolur ve debug edilemez.
- **Kanit:** satir 234-235, 362-364.
- **Aksiyon:** Her iki except bloguna da `logger.warning(...)` ekle (orn. `f"pending_action_ids_json parse hatasi (memory_id={m.id}): {e}"`), boylece bozuk kayitlar fark edilebilir.
- **Onem:** Dusuk · **Guven:** Kesin

### [RCO-006] Modul-seviyesi `_engine` singleton'i thread-safe degil
- **Sorun:** `_get_engine()` (satir 252-256) klasik "None kontrolu + ata" lazy-init pattern'i kullaniyor, kilit (lock) yok. FastAPI sync endpoint'ler threadpool'da calisir; iki istek ayni anda ilk kez `_get_engine()` cagirirsa her ikisi de `_engine is None` gorup birer `CoachEngine()` (ve icinde `build_provider()`, muhtemelen API client kurulumu) olusturabilir. Sonuc kritik bir hata degil (son atama kazanir) ama gereksiz kaynak/istemci olusturma ve olasi yaris durumu var.
- **Kanit:** satir 249-256.
- **Aksiyon:** `threading.Lock()` ile double-checked locking eklenebilir; tek-kullanicili MVP'de dusuk oncelikli.
- **Onem:** Dusuk · **Guven:** Dogrulanmali

### [RCO-007] `get_history` limit parametresi sinirsiz
- **Sorun:** `limit: int = 50` (satir 338) icin ust sinir (`le=`) veya negatif deger kontrolu yok. `?limit=-5` gibi bir deger SQLAlchemy `.limit(-5)` davranisina baglidir (SQLite'ta genelde tum satirlari doner, negatif limit yok sayilir), `?limit=999999999` ise gereksiz tam tablo taramasi yaratabilir. Tek-kullanicili MVP'de dusuk risk ama girdi dogrulama eksik.
- **Kanit:** satir 338.
- **Aksiyon:** `limit: int = Query(50, ge=1, le=500)` gibi bir sinir ekle.
- **Onem:** Dusuk · **Guven:** Kesin
