# Dayanıklılık & hata yönetimi (kod: RESIL)

> propose→onay→execute akışı ve Master Checkpoint enforcement korunur. Burada işlem bütünlüğü, kısmi başarı, retry/timeout, degradasyon.

### [RESIL-001] `execute_pending_action` atomik değil — kısmi yazımda tutarsız durum
- **Sorun/Fırsat:** Payload parse + DB güncelleme + status='executed' + ActionHistory birden çok adım; ortada hata olursa bakiye güncellenip status pending kalabilir (veya tersi).
- **Kanıt:** `app/action_executor.py:255-335`
- **Aksiyon:** Tüm execute'i tek transaction'a sar; hata'da `db.rollback()`. Başarı=tek commit.
- **Etki:** Yüksek · **Efor:** M

### [RESIL-002] IntegrityError için `db.rollback()` yerine savepoint kullanılmıyor
- **Sorun/Fırsat:** Kısmi hata'da tüm transaction geri alınıyor; iç içe işlemde önceki geçerli iş de kaybolur.
- **Kanıt:** MEMORY savepoint feedback'i (`db.begin_nested()`); executor/router IntegrityError yolları
- **Aksiyon:** Riskli insert'leri `db.begin_nested()` (SAVEPOINT) ile sar; hata'da sadece savepoint geri al.
- **Etki:** Orta · **Efor:** M

### [RESIL-003] Idempotency/replay koruması yok — retry çift işlem
- **Kanıt:** `app/routers/actions.py` execute; `transactions.py` create
- **Aksiyon:** Status geçişini atomik tek-yön (pending→executed, tekrar 409); Idempotency-Key. (SEC-023/API-007)
- **Etki:** Orta · **Efor:** M

### [RESIL-004] FallbackProvider tükenince graceful degradation zayıf ✅ UYGULANDI (12 Tem 2026)
- **Sorun/Fırsat:** Tüm provider'lar düşünce kullanıcıya ham exception string; "koç şu an yok, verilerin güvende, sonra dene" gibi degrade edilmiş deneyim yok.
- **Kanıt:** `app/coach.py:1612-1621`; `routers/coach.py:306-313`
- **Aksiyon:** Chain-exhausted'da net degrade mesajı + son cockpit'i yine göster (Rules Engine LLM'siz çalışır — bu güç); "deterministik özet" fallback.
- **Etki:** Orta · **Efor:** M · **Not:** Rules Engine LLM'den bağımsız — LLM çökse bile sistem kullanılabilir kalmalı.
- **Durum:** CoachEngine.chat STEP-C except'i (tüm sağlayıcı düştü) düzeltildi: ham hata (str(e)) artık KULLANICIYA SIZMAZ — loglanır (exc_info). Mesaj kurucu gücü vurguluyor: "yorumlayan AI yok ama kokpit/limit/bütçe/borç/alacak verileri motor tarafından hesaplanıyor, güncel ve doğru." cockpit_snapshot yine döner (deterministik veri korunur) + grounding şeması tutarlı. test_coach_behavior_contract.py: DeadProvider ile ham-hata-sızmaz + cockpit korunur + veri-yönlendirme testi. Router-seviyesi BE-009 handler'ı zaten ayrı katman (engine.chat tamamen patlarsa).

### [RESIL-005] Scheduler batch bir kullanıcı hatasında diğerlerini kirletebilir (tek session)
- **Kanıt:** `app/scheduler.py:148-152`
- **Aksiyon:** User başına ayrı session scope + try/except + rollback; bir user'ın hatası batch'i durdurmasın. (BE-029)
- **Etki:** Orta · **Efor:** S

### [RESIL-006] DB session sızıntısı riski — background task/scheduler'da elle SessionLocal
- **Kanıt:** `app/routers/actions.py:65-157` (`_run_reflection` elle SessionLocal); scheduler
- **Aksiyon:** Context-manager helper (`with session_scope() as db:`) — commit/rollback/close garantili.
- **Etki:** Orta · **Efor:** S

### [RESIL-007] LLM çağrılarında timeout yok — asılı istek tüm chain'i bekletir
- **Kanıt:** `app/coach.py` provider çağrıları (explicit timeout yok)
- **Aksiyon:** Her provider çağrısına timeout (örn. 30sn); aşınca bir sonraki provider'a geç.
- **Etki:** Orta · **Efor:** S

### [RESIL-008] Circuit breaker yok — sürekli düşen provider her seferde deneniyor ✅ KISMEN UYGULANDI (12 Tem 2026)
- **Kanıt:** `app/coach.py:1139-1173` (fallback her istekte baştan)
- **Aksiyon:** Provider bazında circuit breaker (N ardışık hata → M dakika atla); latency/maliyet tasarrufu.
- **Etki:** Düşük · **Efor:** M
- **Durum:** KALICI-hata breaker'ı uygulandı: `_is_request_too_large` (413 / "request too large" / context limit — 429 geçici kotadan AYRI) veren sağlayıcı `FallbackProvider._oversized_providers`'a alınıp process boyunca atlanır (sabit-boyut prompt her çağrıda aynı 413'ü verir → beyhude round-trip + log gürültüsü biter). Groq free tier TPM 8000 < Türkçe prompt tipik tetik (memory: `reference_groq_tpm_limiti`). Tüm sağlayıcı oversized ise güvenli tarafta tam listeye döner. 4 test (test_fallback_provider.py). **Kalan (N-ardışık geçici hata → M-dk zaman-bazlı skip):** geçici kota için henüz yok; bu MVP'de düşük etki (fallback zaten geçici hatada sıradakine geçiyor).

### [RESIL-009] Retry backoff'ta jitter yok + maks sınır belirsiz
- **Kanıt:** `app/coach.py:489`
- **Aksiyon:** Full jitter + max_delay + max_attempts. (LLM-011)
- **Etki:** Düşük · **Efor:** S

### [RESIL-010] Kısmi cockpit hesabı başarısızlığında davranış tanımsız
- **Sorun/Fırsat:** Bir alt-hesap (örn. fiyat çekme) patlarsa tüm cockpit mi düşüyor, yoksa sessizce eksik mi geliyor?
- **Kanıt:** `app/routers/cockpit.py:93` (`except: pass`); `rules_engine.generate_cockpit`
- **Aksiyon:** Alt-hesap hatalarını izole et; eksik bölümü "hesaplanamadı" olarak işaretle, geri kalanı sun. Sessiz yutma yerine kısmi-degrade.
- **Etki:** Orta · **Efor:** M

### [RESIL-011] Backup var ama restore süreci test edilmemiş
- **Kanıt:** `scripts/backup.py`; `docs/dev-commands.md` backup bölümü (restore adımı yok)
- **Aksiyon:** `scripts/restore.py` + belgelenmiş restore prosedürü; periyodik "restore tatbikatı" (yedekten ayağa kalkıyor mu).
- **Etki:** Orta · **Efor:** M

### [RESIL-012] Backup yerel-only — disk arızasında tek nokta
- **Kanıt:** `data/backups/` (yerel); wave3-vision disaster recovery notu
- **Aksiyon:** Şifreli off-site kopya (Backblaze B2/S3); en azından farklı disk. (SEC-013 ile)
- **Etki:** Orta · **Efor:** M

### [RESIL-013] Schema migration sırasında veri kaybı koruması yok
- **Kanıt:** Alembic var ama migration öncesi otomatik backup yok; `setup_data` drop_all
- **Aksiyon:** Migration/setup öncesi otomatik backup (DATA-021); downgrade test (TEST-023).
- **Etki:** Orta · **Efor:** S

### [RESIL-014] `except Exception: pass` sessiz yutmalar hatayı gizliyor
- **Kanıt:** `app/coach.py:391`, `action_executor.py:246` vb. (BE-010)
- **Aksiyon:** En azından logla; kritik yollarda yut-ma, degrade et.
- **Etki:** Orta · **Efor:** S

### [RESIL-015] Fiyat çekme dış servis hatası — cockpit'i bozabilir
- **Kanıt:** `fund_tracker` (tefas/yfinance/borsapy dış ağ)
- **Aksiyon:** Dış çağrıyı timeout+try/except ile sar; başarısızsa son cache fiyatı + "eski" bayrağı (zaten var), cockpit düşmesin.
- **Etki:** Orta · **Efor:** S

### [RESIL-016] Chat endpoint tüm hataları yutup 200 dönüyor — hata görünmez, retry yok
- **Kanıt:** `app/routers/coach.py:306-313`
- **Aksiyon:** Gerçek hata 5xx (BE-009/API-004); istemci retry/degrade UX kurabilsin.
- **Etki:** Yüksek · **Efor:** S

### [RESIL-017] Eşzamanlı yazım (scheduler + coach aynı kayda) — sessiz ezme
- **Kanıt:** Çoğu tabloda `version_id_col`/`updated_at` yok (DATA-014)
- **Aksiyon:** Kritik tablolara optimistic locking (`version_id_col`) → `StaleDataError` yakala.
- **Etki:** Orta · **Efor:** M

### [RESIL-018] Startup dayanıklılığı — `create_all`/backfill/scheduler hatası app'i düşürebilir
- **Kanıt:** `app/main.py:68-127` (startup'ta backfill + scheduler + create_all)
- **Aksiyon:** Startup adımlarını try/except ile izole et; kritik-olmayan (backfill) hata app'i düşürmesin, logla.
- **Etki:** Orta · **Efor:** S

### [RESIL-019] `propose_action` ValueError string-sözleşmesi kırılırsa akış bozulur
- **Kanıt:** `app/action_executor.py:173,177`; `coach.py:1677-1680`
- **Aksiyon:** Tipli exception (BE-006); kırılgan string-match yerine sağlam hata iletimi.
- **Etki:** Orta · **Efor:** S

### [RESIL-020] Rate-limit/quota'da kullanıcıya net "yarın dene" degrade yok
- **Kanıt:** `routers/coach.py:284-290`
- **Aksiyon:** Quota bittiğinde net mesaj + Rules Engine tabanlı deterministik özet (LLM'siz değer). (RESIL-004 ile)
- **Etki:** Düşük · **Efor:** S

---
**Kaynaklar:** SQLAlchemy transaction/savepoint (begin_nested); idempotency patterns; circuit breaker (Fowler); graceful degradation; disaster recovery (backup/restore drill).
