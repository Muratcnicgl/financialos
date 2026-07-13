# .env Denetim Raporu — 14 Tem 2026

**KURAL:** Bu rapor hiçbir gerçek key/şifre/token içermez. Yalnız **uzunluk + ilk 4 karakter
(prefix) + son 3 karakter (suffix) + format doğrulama** gösterilir. 4+3 karakter yüksek-entropili
bir sırrı yeniden oluşturmaya yetmez (ör. 64 karakterlik SECRET_KEY'den 7 karakter).

## 1. Genel Durum
- **33 satır** · **21 değişken** (dolu 21, boş 0) · 12 yorum/boşluk satırı.
- **Duplicate: YOK.**
- **Not:** `.env` yalnız Murat'ın doldurduğu değişkenleri içeriyor; opsiyonel placeholder'lar
  (EVDS/OAuth/Together/DeepInfra/DOMAIN/CORS_ORIGINS/AUTH_ENABLED) `.env`'de YOK = unset (default'a düşer).

## 2. Değişken Detay (maskeli)

| DEĞİŞKEN | DOLU/BOŞ | uzunluk | prefix | suffix | Format |
|----------|----------|---------|--------|--------|--------|
| ANTHROPIC_API_KEY | DOLU | 108 | `sk-a` | `QAA` | ✅ sk-ant- |
| LLM_PROVIDER | DOLU | 8 | `fall` | `ack` | config (fallback) |
| LLM_MODEL | DOLU | 21 | `gemi` | `ite` | config (gemini flash-lite) |
| DATABASE_URL | DOLU | 31 | `sqli` | `.db` | config (sqlite) |
| HOST | DOLU | 9 | `127.` | `0.1` | config (uvicorn host) |
| PORT | DOLU | 4 | `8000` | `000` | config |
| LOG_LEVEL | DOLU | 4 | `INFO` | `NFO` | config |
| GEMINI_API_KEY | DOLU | 39 | `AIza` | `m6s` | ✅ Google API key (AIza, 39 char) |
| GROQ_API_KEY | DOLU | 56 | `gsk_` | `fmU` | ✅ gsk_ |
| GROQ_MODEL | DOLU | 19 | `open` | `20b` | config (openai/gpt-oss-20b) — key DEĞİL |
| GROQ_FALLBACK_ENABLED | DOLU | 4 | `true` | `rue` | config (bool) — key DEĞİL |
| CEREBRAS_API_KEY | DOLU | 52 | `csk-` | `3hm` | ✅ csk- |
| SECRET_KEY | DOLU | 64 | `3UGI` | `5L7` | ✅ ≥32 (JWT yeterli entropy) |
| SMTP_HOST | DOLU | 20 | `smtp` | `com` | ✅ smtp-relay.brevo.com |
| SMTP_PORT | DOLU | 3 | `587` | `587` | ✅ 587 (STARTTLS) |
| SMTP_USER | DOLU | 24 | `b1ea` | `com` | ✅ Brevo login (email) |
| SMTP_PASS | DOLU | 90 | `xsmt` | `ZR8` | ✅ Brevo Standard SMTP key (xsmt, 90 char) |
| SMTP_FROM | DOLU | 20 | `mura` | `com` | ✅ email (⚠️ raw gmail — Brevo sender doğrulaması gerekli) |
| SMTP_FROM_NAME | DOLU | 11 | `Fina` | `lOS` | config (FinancialOS) |
| FRONTEND_URL | DOLU | 21 | `http` | `173` | config (localhost:5173) |
| OPENROUTER_API_KEY | DOLU | 73 | `sk-o` | `af8` | ✅ sk-or-v1- |

## 3. Format Doğrulama Özeti
Tüm API key'ler beklenen prefix + uzunlukta: Gemini (AIza/39), Groq (gsk_), Cerebras (csk-),
OpenRouter (sk-or-v1-), Anthropic (sk-ant-), Brevo SMTP (xsmt/90). SECRET_KEY 64 char (güçlü).
`GROQ_MODEL`/`GROQ_FALLBACK_ENABLED` key değil config; format-checker "gsk_ bekleniyor" = **yanlış pozitif**.

## 4. Fonksiyonel Test (canlı çağrı, 14 Tem 2026)

| Sağlayıcı | Sonuç | Not |
|-----------|-------|-----|
| **GROQ** | ✅ chat 200 | Çalışıyor (gpt-oss-20b) |
| **CEREBRAS** | ✅ chat 200 | Çalışıyor (gpt-oss-120b) |
| **OPENROUTER** | ✅ models.list 200 | Çalışıyor |
| **BREVO_SMTP** | ✅ STARTTLS+login | Auth başarılı (e-posta gönderilmedi, sadece login testi) |
| **GEMINI** | ⚠️ HTTP 429 | Key GEÇERLİ (auth geçti) ama günlük kota DOLU (RESOURCE_EXHAUSTED) |
| **ANTHROPIC** | ⚠️ 400 credit low | Key GEÇERLİ ama kredi bakiyesi YOK |

## 5. Birleşik Rapor Tablosu

| DEĞİŞKEN | DOLU/BOŞ | FORMAT | FONKSİYONEL | NOT |
|----------|----------|--------|-------------|-----|
| GEMINI_API_KEY | DOLU | OK | ⚠️ 429 kota | Free tier günlük kota dolu — yarın sıfırlanır |
| GROQ_API_KEY | DOLU | OK | ✅ 200 | Çalışıyor |
| CEREBRAS_API_KEY | DOLU | OK | ✅ 200 | Çalışıyor |
| OPENROUTER_API_KEY | DOLU | OK | ✅ 200 | Çalışıyor |
| ANTHROPIC_API_KEY | DOLU | OK | ⚠️ kredi yok | Ücretli — Wave-4 birincil aday, kredi gerekli |
| SECRET_KEY | DOLU | OK | — | JWT için güçlü (64 char) |
| SMTP_* (Brevo) | DOLU | OK | ✅ login | STARTTLS+auth başarılı; **teslim için Brevo'da SMTP_FROM doğrula** |
| SMTP_FROM | DOLU | ⚠️ | — | Raw gmail.com — Brevo sender/domain doğrulaması yoksa spam/bounce |
| FRONTEND_URL | DOLU | OK | — | localhost (prod'da gerçek domain) |
| EVDS_API_KEY | YOK | — | — | M12 döviz/altın için gerekli — al: evds2.tcmb.gov.tr |
| OAUTH_GOOGLE_* | YOK | — | — | M11 "Google ile giriş" — opsiyonel |
| OAUTH_GITHUB_* | YOK | — | — | M11 "GitHub ile giriş" — opsiyonel |
| TOGETHER/DEEPINFRA | YOK | — | — | M13 ek koç fallback — opsiyonel |

## 6. Duplicate Uyarısı
**YOK** — hiçbir değişken iki kez tanımlanmamış.

## 7. Sonuç: Kritik Eksikler + Opsiyoneller

### ✅ Wave-3 için KRİTİK — hepsi hazır
- **SECRET_KEY** (JWT auth) ✅ · **En az bir çalışan koç sağlayıcı** ✅ (Groq/Cerebras/OpenRouter canlı 200; Gemini kota dolu ama geçerli) · **Brevo SMTP** ✅ (login çalışıyor).
- **Tek gerçek risk:** `SMTP_FROM=muraticgil@gmail.com` raw gmail → **Brevo'da gönderen doğrulanmalı** (SPF/DKIM veya verified sender), aksi halde mail spam/bounce. Login çalışıyor ama teslim garanti değil.

### ⏳ Wave-3 opsiyonel (eksik ama engel değil)
- **EVDS_API_KEY** — M12 döviz/altın fiyat çekimi için (evds2.tcmb.gov.tr ücretsiz kayıt). Yoksa fx/gold provider None döner (graceful).
- **OAuth (Google/GitHub)** — sosyal giriş; email/şifre auth zaten çalışıyor.

### 🔮 Wave-4
- **ANTHROPIC kredi** (ücretli koç birincil aday) · **Together/DeepInfra** (ek ücretsiz fallback) · Apple OAuth (ücretli program).

### Not (koç fonksiyonel gerçeği)
Gemini kota + Anthropic kredi yok → şu an **fiilen Groq/Cerebras/OpenRouter** koçu çalıştırır
(fallback zinciri: Gemini kota→OpenRouter/Cerebras/Groq'a düşer). Zincir sağlıklı, koç çalışır durumda.
