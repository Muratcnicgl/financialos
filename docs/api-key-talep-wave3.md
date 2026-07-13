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
