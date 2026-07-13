# Wave-3 API Key Talep Listesi (Murat tedarik edecek)

Goal boyunca eklenen, harici API key / kimlik gerektiren araçlar. Kod placeholder'lı,
.env.example güncel. Murat key'leri tedarik edince `.env`'e girer, ilgili özellik aktifleşir.

## M11 — Auth (ADR-033)

| Kaynak | Amaç | Zorunlu/Ops. | Kayıt URL | .env değişkeni | Ücretsiz tier |
|--------|------|--------------|-----------|----------------|---------------|
| Brevo (Sendinblue) | Şifre sıfırlama e-postası (SMTP) | Opsiyonel (reset için) | https://www.brevo.com | SMTP_HOST/USER/PASS/FROM | 300 e-posta/gün |
| Google OAuth | "Google ile giriş" | Opsiyonel | https://console.cloud.google.com | OAUTH_GOOGLE_CLIENT_ID/SECRET | ücretsiz |
| GitHub OAuth | "GitHub ile giriş" | Opsiyonel | https://github.com/settings/developers | OAUTH_GITHUB_CLIENT_ID/SECRET | ücretsiz |
| Apple OAuth | "Apple ile giriş" | Opsiyonel (PLACEHOLDER) | https://developer.apple.com ($99/yıl) | — | ücretli program → ertelendi |
| SECRET_KEY | JWT imzalama | **Zorunlu (prod)** | — (kendi üret) | SECRET_KEY | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |

## M12 — Multi-asset (ADR-031)

| Kaynak | Amaç | Zorunlu/Ops. | Kayıt URL | .env değişkeni | Ücretsiz tier |
|--------|------|--------------|-----------|----------------|---------------|
| TCMB EVDS | Döviz + altın kuru | Ops. (fx/gold için) | https://evds2.tcmb.gov.tr | EVDS_API_KEY | ücretsiz kayıt |
| CoinGecko | Kripto (Wave-4) | Ops. | https://www.coingecko.com/api | — | free tier key'siz |

**Not:** yfinance (hisse) key gerektirmez ama R3: bu ortamda Yahoo erişilemez — canlı
doğrulama Murat'ın sunucusunda gerekli. BIST için İş Yatırım fallback + '.IS' suffix.

## M13 — Koç ücretsiz sağlayıcılar (ADR-034 revize)

| Kaynak | Amaç | Zorunlu/Ops. | Kayıt URL | .env değişkeni | Ücretsiz tier |
|--------|------|--------------|-----------|----------------|---------------|
| Together AI | Koç fallback (Llama/Qwen) | Opsiyonel | https://api.together.xyz | TOGETHER_API_KEY | free modeller |
| DeepInfra | Koç fallback | Opsiyonel | https://deepinfra.com | DEEPINFRA_API_KEY | free tier |
| OpenRouter | Koç ikincil (mevcut) | Opsiyonel | https://openrouter.ai/keys | OPENROUTER_API_KEY | ~50/gün |
| Cerebras/Groq | Koç fallback (mevcut) | Opsiyonel | console.cerebras.ai / console.groq.com | CEREBRAS/GROQ_API_KEY | ücretsiz |

**Not:** En az bir sağlayıcı (Gemini önerilir) yeterli; diğerleri fallback. Ollama yerel key'siz.
