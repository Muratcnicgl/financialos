# Güvenlik, gizlilik, auth (kod: SEC)

> En güçlü mevcut savunma: LLM asla doğrudan DB yazmıyor (propose→onay→execute) ve Master Checkpoint enforcement kod seviyesinde. Bu ilkeleri gevşetme.

### [SEC-001] Kimlik doğrulama tamamen yok — `get_current_user` ilk kullanıcıyı döndürüyor
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: get_current_user JWT + AUTH_ENABLED gate (dependencies.py:73)
- **Kanıt:** `app/dependencies.py:36`; `app/main.py`'de auth middleware yok
- **Aksiyon:** OAuth2 bearer + JWT iskeleti; MVP'de tek statik token bile "auth yok"tan iyi. (OWASP API2:2023)
- **Etki:** Yüksek · **Efor:** M

### [SEC-002] Nesne seviyesi yetkilendirme (BOLA) için savunma yok
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: scope_filter tüm mutasyon router'larında (accounts.py:220)
- **Kanıt:** `accounts.py:195`, `transactions.py:343`, `debts.py:136`
- **Aksiyon:** `get_owned_or_404(model,id,user)` helper; `test_isolation.py`. (OWASP API1:2023)
- **Etki:** Yüksek · **Efor:** M

### [SEC-003] CORS `credentials=True` + `methods=["*"]`, `headers=["*"]`
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: CORS env-driven, wildcard+credentials yok (main.py:157)
- **Kanıt:** `app/main.py:152-163`
- **Aksiyon:** Origin'leri env'den; method/header'ı gerçek kümeyle sınırla; prod'da wildcard yok.
- **Etki:** Orta · **Efor:** S

### [SEC-004] Rate limiting yok — LLM maliyeti ve DoS açık
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: rate_limit yalnız auth bucket'ları; actions/execute per-IP yok (rate_limit.py:18)
- **Kanıt:** `app/main.py` sadece CORS; günlük sayaç var ama hız sınırı yok
- **Aksiyon:** slowapi; coach/chat, user POST, actions/execute'e limit. (OWASP API4:2023)
- **Etki:** Yüksek · **Efor:** S

### [SEC-005] Güvenlik başlıkları yok (HSTS, CSP, X-Frame-Options, nosniff)
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: app güvenlik başlığı yok, Caddy'ye devredilmiş (main.py:157)
- **Kanıt:** `app/main.py:152-163`
- **Aksiyon:** `@app.middleware("http")` ile başlıklar.
- **Etki:** Orta · **Efor:** S

### [SEC-006] `coach/chat` mesajında üst sınır yok — sınırsız girdi ✅ UYGULANDI (12 Tem 2026)
- **Durum:** ✅ KAPANDI (inline işaret)
- **Kanıt:** `routers/coach.py:53` (max yok) vs `user.py:36` max_length=100
- **Aksiyon:** `max_length=4000` + genel gövde boyutu sınırı.
- **Etki:** Orta · **Efor:** S
- **Durum:** `ChatRequest.message` → `max_length=4000` (4000 karakter finansal olay tarifi için fazlasıyla yeterli; aşarsa 422). Sağlayıcı token-limiti (413) + maliyet/bellek koruması — provider TPM gerçeğiyle doğrudan ilişkili (kazara büyük yapıştırma tüm zinciri patlatabilirdi). 2 test (>4000 → 422, boş → 422). test_coach_chat_endpoint.py.

### [SEC-007] LLM prompt injection — kullanıcı mesajı doğrudan prompt'a, sanitizasyon yok
- **Durum:** ⚪ DEFEKT-DEĞİL — M85 R3 doğrulama: çift savunma + MC enforcement + LLM DB yazmıyor (mimari mitigasyon)
- **Kanıt:** `routers/coach.py:263-299`; prompt'ta sadece metinsel yasaklar
- **Aksiyon:** Çift savunmayı koru/güçlendir (propose→onay→execute ADR ile kilitle; MC enforcement kod seviyesinde); yürütülen payload'u onay ekranında net göster.
- **Etki:** Yüksek · **Efor:** M · **Not:** "LLM asla DB yazmaz" en güçlü savunma — gevşetme.

### [SEC-008] Ham finansal mesaj log'a yazılıyor (PII loglama)
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: ham finansal mesaj loglanıyor logger.warning({user_message!r}) (coach.py:2445)
- **Kanıt:** `app/coach.py:1695,1757` (`{user_message!r}`)
- **Aksiyon:** Uzunluk/hash logla; PII redaksiyon filtresi; prod'da DEBUG kapalı. (KVKK veri minimizasyonu)
- **Etki:** Orta · **Efor:** S

### [SEC-009] `ApiCallLog.error_message` ham hata metni — sır sızma
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: ApiCallLog.error_message ham str(e) (coach.py:344)
- **Kanıt:** `routers/coach.py:189,200`
- **Aksiyon:** `type(e).__name__` + temizlenmiş metin; ham payload saklama.
- **Etki:** Düşük · **Efor:** S

### [SEC-010] KVKK: hesap silme / imha endpoint'i yok
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: DELETE /api/users/me cascade (auth.py:292)
- **Kanıt:** `routers/user.py` sadece GET/POST/PUT
- **Aksiyon:** `DELETE /api/user` (cascade), audit'li, idempotent. (KVKK m.7)
- **Etki:** Orta · **Efor:** M

### [SEC-011] KVKK/GDPR: veri export endpoint'i yok
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: GET /api/users/me/export (auth.py:300)
- **Kanıt:** Grep export → yok
- **Aksiyon:** `GET /api/user/export` (tüm veri tek JSON, auth arkasında). (KVKK m.11)
- **Etki:** Düşük · **Efor:** M

### [SEC-012] At-rest şifreleme yok — SQLite düz metin
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: SQLite düz metin, disk şifreleme yok (database.py:25)
- **Kanıt:** `DATABASE_URL=sqlite:///./data/financialos.db`
- **Aksiyon:** SQLCipher veya OS-disk şifreleme (BitLocker); anahtar secret'ta.
- **Etki:** Orta · **Efor:** L

### [SEC-013] Yedekler şifresiz
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: yedekler düz .db, şifreleme yok (scripts/backup)
- **Kanıt:** `scripts/backup` düz `.db` kopyası
- **Aksiyon:** `age`/`gpg` ile şifrele; dizin izinlerini kısıtla.
- **Etki:** Orta · **Efor:** S

### [SEC-014] HTTPS/TLS zorlaması yok
- **Durum:** ⏸️ KAPSAM DIŞI — M85 R3 doğrulama: HTTPS/TLS ters-proxy = deploy
- **Kanıt:** `uvicorn --port 8000` (TLS yok)
- **Aksiyon:** Reverse proxy (Caddy/Nginx) TLS; HTTP→HTTPS; HSTS.
- **Etki:** Yüksek · **Efor:** M

### [SEC-015] `/docs`, `/openapi.json`, `/redoc` auth'suz açık
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: production'da docs/redoc/openapi None (main.py:114)
- **Kanıt:** `app/main.py:140-145`
- **Aksiyon:** Prod'da `docs_url=None` veya auth arkasına.
- **Etki:** Orta · **Efor:** S

### [SEC-016] Hata mesajlarında iç bilgi/config sızıntısı
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: coach generic mesaj (coach.py:346) ama tüm endpoint garanti değil
- **Kanıt:** `routers/coach.py:288-290`; `user.py:63-64`; `dependencies.py:40-42`
- **Aksiyon:** Jenerik mesaj; detay sadece log'da; env değişken adlarını yanıttan çıkar. (OWASP API8:2023)
- **Etki:** Düşük · **Efor:** S

### [SEC-017] Sır yönetimi — API anahtarları düz `.env`, rotasyon yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: API anahtarları düz .env, secret manager yok
- **Kanıt:** `.env` diskte; `.gitignore` doğru
- **Aksiyon:** Prod'da secret manager; rotasyon prosedürü; dosya izni 600; git geçmişini doğrula.
- **Etki:** Orta · **Efor:** M

### [SEC-018] `.env` diskte mevcut — sızma denetimi yap
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: .env diskte, gitleaks kanıtı yok
- **Kanıt:** `ls`: `.env` 698 byte
- **Aksiyon:** `git log --all -- .env`; sızmışsa anahtar rotasyonu; pre-commit `gitleaks`.
- **Etki:** Orta · **Efor:** S

### [SEC-019] Ham SQL f-string kalıbı (`text(f"...")`) — latent injection deseni
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: rules_engine.py:940 db.execute(text(f"...")) f-string (sabit liste, latent)
- **Kanıt:** `rules_engine.py:575` + `:60` (`_EXCLUDED_SQL` sabit listeden — şu an güvenli)
- **Aksiyon:** Parametreli expanding bindparam; "buraya kullanıcı girdisi koyma" yorumu.
- **Etki:** Düşük · **Efor:** S

### [SEC-020] Bağımlılık güvenlik taraması yok (pip-audit)
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: pip-audit/safety yok
- **Kanıt:** `requirements.txt`; scraper'lar (yfinance, tefas-crawler, borsapy) risk yüzeyi
- **Aksiyon:** `pip-audit`/`safety` + CI.
- **Etki:** Orta · **Efor:** S

### [SEC-021] Bağımlılıklar aralıklı pin'li — supply-chain riski
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: requirements >= pin, lock/hash yok
- **Kanıt:** `requirements.txt`: `anthropic>=0.79.0`, `google-genai>=0.3.0`, `groq>=0.11.0` vb.
- **Aksiyon:** Kesin pin + `requirements.lock` (pip-tools/uv); hash doğrulama.
- **Etki:** Düşük · **Efor:** S

### [SEC-022] `create_user` multi-user engelli ama admin/kayıt akışı tanımsız
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: password_hash/oauth/kvkk var ama rol + e-posta doğrulama yok (auth.py:96)
- **Kanıt:** `routers/user.py:53-70`; User'da parola/rol yok
- **Aksiyon:** Multi-user ADR'sinde parola hash (argon2id), e-posta doğrulama, rol; MVP'de şema alanlarını şimdi ekle.
- **Etki:** Orta · **Efor:** M

### [SEC-023] `actions/execute`'te idempotency/replay koruması yok
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: status!=pending replay bloklu ama Idempotency-Key yok (action_executor.py:364)
- **Kanıt:** `routers/actions.py`, `simulation.py:92`, `premortem.py:52`
- **Aksiyon:** Status geçişini atomik tek-yön (pending→executed, tekrar 409); Idempotency-Key.
- **Etki:** Orta · **Efor:** M

### [SEC-024] Denetim izi zayıf — kim/ne zaman/hangi IP eksik
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: ActionHistory audit var ama router DELETE/IP audit yok
- **Kanıt:** ApiCallLog sadece LLM; finansal DELETE/UPDATE audit'lenmiyor
- **Aksiyon:** Kritik mutasyonlar için append-only audit (aktör, ts, IP, önce/sonra).
- **Etki:** Orta · **Efor:** M

### [SEC-025] Rıza/gizlilik politikası ve saklama süresi yok
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: kvkk_consent + ReasoningTrace retention var, CoachMemory anonimleştirme yok (models.py:139)
- **Kanıt:** CoachMemory/CoachInsight süresiz; sadece insight'ta opsiyonel expires_at
- **Aksiyon:** Saklama süreleri + periyodik anonimleştirme job (scheduler var); aydınlatma+rıza kaydı.
- **Etki:** Düşük · **Efor:** M

### [SEC-026] Global paylaşılan `CoachEngine` singleton — multi-user'da bağlam sızması riski
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: engine stateless workspace_scope ama multi-user izolasyon testi doğrulanmadı (coach.py:332)
- **Kanıt:** `routers/coach.py:249-256`
- **Aksiyon:** Engine stateless kalsın (şu an `_build_context_message(db,user_id)` çağrı-başı — doğru); multi-user'da durum eklenmemesini test et.
- **Etki:** Orta · **Efor:** S

### [SEC-027] Sağlık ucu/root sürüm/servis bilgisi ifşa
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: health version/service/auth_enabled ifşa (main.py:208)
- **Kanıt:** `app/main.py:200-206`
- **Aksiyon:** Genel health minimal (`{"status":"ok"}`); detay auth arkasına.
- **Etki:** Düşük · **Efor:** S

### [SEC-028] Scheduler kimlik/izolasyon bağlamı olmadan tüm kullanıcılar üzerinde çalışıyor
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: scheduler retention global, per-user izolasyon doğrulanmadı (scheduler.py:195)
- **Kanıt:** `app/scheduler.py:267,279`; `main.py:120-125`
- **Aksiyon:** Job'ları user bazında izole et; bir user exception'ı batch'i durdurmasın; tenant sınırı.
- **Etki:** Düşük · **Efor:** M

### [SEC-029] Reverse proxy/gövde boyutu/bağlantı sınırı yok
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Kanıt:** `uvicorn` doğrudan
- **Aksiyon:** Nginx/Caddy `client_max_body_size`, timeout, `--limit-concurrency`. (OWASP API4)
- **Etki:** Orta · **Efor:** S

### [SEC-030] Coach yanıtı tam finansal snapshot'ı geniş döndürüyor
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: coach cockpit_snapshot döndürüyor, alan daraltma yok (coach.py:371)
- **Kanıt:** `routers/coach.py:73-78`
- **Aksiyon:** Snapshot varsayılanı kapat (frontend zaten `/api/cockpit` çağırıyor); alanları daralt. (OWASP API3)
- **Etki:** Düşük · **Efor:** S

### [SEC-031] `Dict[str, Any]` payload'lar — şema doğrulaması zayıf
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: propose payload Dict[str,Any], extra=forbid yok (coach.py:81)
- **Kanıt:** `routers/coach.py:61`; `coach.py:358-360`
- **Aksiyon:** action_type'a göre discriminated union Pydantic; `extra="forbid"`.
- **Etki:** Orta · **Efor:** M

### [SEC-032] Sayısal/finansal alanlarda aralık doğrulaması eksik ✅ UYGULANDI (12 Tem 2026)
- **Durum:** ✅ KAPANDI (inline işaret)
- **Kanıt:** accounts/transactions şemalarında max_length var ama tutar `ge=`/`le=` yok
- **Aksiyon:** `Field(ge=0)`/üst sınır, Decimal; `_parse_quick_text` girdisini sıkı doğrula.
- **Etki:** Orta · **Efor:** M
- **Uygulama:** `app/schema_types.py` — paylaşılan sonlu-float tipleri (FinansTutar/FinansOptTutar
  = gt=0, FinansBakiye = negatif olabilir, FinansOptOran = ≥0; hepsi `allow_inf_nan=False` +
  üst sınır 1e12). accounts/transactions/debts/incomes/expenses şemalarına uygulandı → inf/NaN
  ve taşma (1e308) GİRİŞTE reddedilir (rules_engine'e round(inf) sızıntısı kesilir). İşlem tutarı
  FinansOptBakiye (sonlu ama sign-agnostik) → handler'daki dostça ≤0 mesajı korunur. 21 test
  (şema seviyesi inf/NaN + HTTP taşma/işaret/meşru-büyük). Not: tarayıcı JSON'u Infinity/NaN
  taşıyamaz (JSON.stringify→"null"); asıl gerçek-dünya koruması taşma/yazım-hatası (1e308) değeridir.
  Decimal geçişi ayrı iş (mevcut float+round yeterli, migration gerektirmez).

### [SEC-033] Insight/hafıza içeriği ikinci-tur (stored) prompt injection taşıyıcısı
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: insight prompt'a VERİ-değil-TALİMAT sınırıyla sarılmıyor (coach.py)
- **Kanıt:** `app/coach.py:681-684`, `1644`
- **Aksiyon:** Insight'ı prompt'a koyarken "VERİ, TALİMAT DEĞİL" sınırıyla çevrele; uzunluk+temizlik. (OWASP LLM01)
- **Etki:** Orta · **Efor:** S

### [SEC-034] Dış LLM'e tam finansal bağlam gidiyor — KVKK yurt dışı aktarım
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: Ollama offline var ama default dış LLM'e tam cockpit
- **Kanıt:** `app/coach.py:1083-1086`; tüm sağlayıcılara cockpit
- **Aksiyon:** KVKK m.9 değerlendir; gönderilen bağlamı minimize et; karşı taraf isimlerini (alacaklar — hassas) anonimleştir/maskele.
- **Etki:** Orta · **Efor:** M

### [SEC-035] Statik güvenlik testi/gizli tarama/güvenli-geliştirme kapısı yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: pre-commit pytest/vitest; bandit/gitleaks/pip-audit yok
- **Kanıt:** pytest yok; CI yok
- **Aksiyon:** `bandit`(SAST)+`gitleaks`(secret)+`pip-audit`(deps) pre-commit/CI; `test_isolation.py`.
- **Etki:** Orta · **Efor:** M

---
**Kaynaklar:** OWASP API Security Top 10 2023; FastAPI güvenlik rehberi (escape.tech); security headers (CSP/HSTS); slowapi rate limiting; KVKK/GDPR karşılaştırma; KVKK imha yönetmeliği.
