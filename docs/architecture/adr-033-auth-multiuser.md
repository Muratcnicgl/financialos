# ADR-033 — Auth + Multi-user (JWT vs Firebase, KVKK) + prod-gate güvenlik

**Tarih:** 13 Tem 2026 · **Durum:** ✅ KARAR VERİLDİ (Wave-3 M11, D1 + K10) · **İlgili:** SEC-001/002, T-17, W3-034 (izolasyon), W3-041 (rate limit)

## Bağlam
`dependencies.py:get_current_user` şu an "ilk kullanıcı" (MVP). Multi-user = auth buraya bağlanır (mimari sınır: yalnız burası). Wave-2'de güvenlik-sertleştirme (auth/rate-limit/HTTPS, T-17) bilinçli ertelendi. **Kritik kolaylık:** User modelinde tüm ilişkiler zaten `cascade="all, delete-orphan"` → KVKK silme `db.delete(user)` ile çalışır; 17 tabloda `user_id` var (segregation temeli hazır).

## D1 — Sektör Referansları

| Proje | Auth | Not |
|-------|------|-----|
| **Firefly III** | Laravel Sanctum (first-party SPA, token/cookie) | Kendi auth, external yok — self-host uyumlu |
| **Beancount fava** | Reverse-proxy basic auth (app-level user yok) | Minimal; multi-user değil |
| **Maybe Finance** | Devise (Rails, session cookie) | Kendi auth, olgun |
| **Firebase Auth** | Managed (Google) | Hızlı ama **veri Google'a** → KVKK yurtdışı-aktarım riski, vendor lock |
| **Supabase Auth** | Managed/self-host (Postgres GoTrue) | Self-host mümkün ama Postgres+ek servis zorunlu |

**Çıkarım:** Self-host + KVKK-bilinçli bir uygulama için **managed auth (Firebase/Supabase) yanlış**: veri egemenliği kaybı + external bağımlılık. Firefly/Maybe gibi **kendi auth** (JWT) doğru yol — veri kullanıcının SQLite'ında kalır.

## K10 — Üç Boyut

- **MUHAKEME:** Kendi JWT auth = veri egemen (SQLite), external servis yok, FastAPI ekosisteminde standart (OAuth2PasswordBearer). Firebase/Supabase veriyi dışarı taşır + KVKK yurtdışı-aktarım açık rızası gerektirir → gereksiz karmaşa. Şifre: **bcrypt** (olgun, 72-byte sınırı bilinen; argon2 daha güçlü ama kurulum ağır — bcrypt MVP için yeterli).
- **BENİ DÜŞÜN (Murat solo):** Kendi JWT bakımı basit (PyJWT + bcrypt, ~200 satır). Firebase SDK + console yönetimi öğrenci için ek yük. OAuth (Google/GitHub) authlib ile eklenir ama **API key gerekli** (Murat tedarik eder — API_KEY_TALEP). Apple OAuth ücretli Developer Program → PLACEHOLDER.
- **GENELİ DÜŞÜN (KVKK + topluluk):** Kişisel finansal veri → en hassas kategori. Self-host + kendi auth = veri yurt-içi/kullanıcı kontrolünde (KVKK m.4 açık rıza + m.7 silme hakkı). Silme: `DELETE /api/users/me` cascade. Export: KVKK taşınabilirlik hakkı → JSON export. Rate-limit (W3-041) auth endpoint'lerde brute-force koruması.

## Karar

1. **Auth:** **Kendi JWT** (external değil). `bcrypt` şifre hash. `PyJWT` HS256, `SECRET_KEY` env'den.
2. **Token:** kısa-ömürlü **access token** (30 dk) + uzun-ömürlü **refresh token** (30 gün). Access `Authorization: Bearer`. Logout = refresh token blacklist (`RevokedToken` tablosu).
3. **OAuth:** `authlib` ile Google + GitHub (**API_KEY_TALEP**). Apple → PLACEHOLDER (ücretli program).
4. **KVKK:** register'da açık rıza (`kvkk_consent_at` + `kvkk_consent_version`, checkbox zorunlu). `DELETE /api/users/me` (cascade, zaten var). `GET /api/users/me/export` (JSON taşınabilirlik).
5. **İzolasyon (W3-034):** `get_current_user` JWT'den user döner; endpoint'ler user.id filtreli (çoğu zaten). **Geriye-dönük uyum:** `AUTH_ENABLED` env False iken (default) get_current_user ilk-user fallback → mevcut 817 test kırılmaz; True iken JWT zorunlu. Kademeli rollout.
6. **Prod-gate:** rate-limit auth endpoint'lerde (W3-041), HTTPS/security-header Caddy'de (ADR-035/W3-042), CORS env-driven (W3-040).
7. **Depolama:** SQLite yeterli (multi-user az kullanıcı); PostgreSQL gerçek-DECIMAL + RLS → Wave-4 (ölçek gelince).
8. **SMTP (şifre sıfırlama):** Brevo/Sendgrid free tier (**API_KEY_TALEP**). Token'lı reset akışı.

## Uygulama (M11)
User modeli (email, password_hash, oauth_provider/sub, kvkk_*, is_active) + migration · `app/auth.py` (hash/JWT/reset-token) · `app/routers/auth.py` (register/login/refresh/logout/me/password-reset/oauth) · `get_current_user` JWT+fallback · KVKK export/delete · rate-limit · testler.

## Kaynak
wave-3-master-plan.md §3, SEC boyutu, T-17, goal-charter-wave3.md M11, D1 (Firefly Sanctum / Maybe Devise / Firebase vs Supabase).
