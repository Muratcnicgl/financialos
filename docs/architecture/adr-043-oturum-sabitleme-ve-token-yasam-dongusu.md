# ADR-043 — Oturum sabitlemesi (session fixation) ve token yaşam döngüsü

**Durum:** kabul edildi · **Tarih:** 6 Ağustos 2026 · **Bağlam:** P2.1 (güvenlik review,
"oturum sabitlemesi" başlığının yazılı gerekçesi eksikti — karar koda uygulanmış ama
gerekçesi hiçbir yerde yazılı değildi, yani gelecekteki bir değişiklik onu bilmeden bozabilirdi)

## Bağlam

Klasik **session fixation** saldırısı sunucu-taraflı oturumlara özgüdür: saldırgan kurbana
bilinen bir oturum kimliği (çerez) verir, kurban o kimlikle giriş yapar, sunucu AYNI kimliği
yetkili hâle getirir ve saldırgan oturuma ortak olur. Klasik savunma: "kimlik doğrulamadan
sonra oturum kimliğini YENİLE".

FinancialOS'ta **sunucu-taraflı oturum yoktur.** Kimlik, imzalı JWT ile taşınır
(`app/auth.py`): access (kısa ömür) + refresh (uzun ömür), `jti` ve `tv` (token_version)
alanlarıyla. Oturum "kimliği" giriş anında ÜRETİLİR; giriş öncesinde kurbanın taşıdığı,
saldırganın önceden bildiği bir kimlik yoktur.

## Karar

1. **Fixation kavramı bu mimaride uygulanamaz** — "girişten sonra oturumu yenile" adımının
   karşılığı zaten yapısaldır: token yalnız başarılı kimlik doğrulamada üretilir, her üretim
   yeni `jti` taşır. Bu yüzden ayrı bir "session regenerate" mekanizması EKLENMEZ.
2. **Yerine ölçtüğümüz şey, yetki-değiştiren olaylarda ESKİ tokenların ölmesidir.** Fixation'ın
   gerçek zararı (saldırganın elindeki kimliğin yetkili kalması) bu mimaride ancak "eski token
   hâlâ geçerli" hatasıyla oluşur. Bu yüzden şu olaylar `token_version`'ı artırır ve tüm eski
   tokenları geçersiz kılar: şifre değiştirme, şifre sıfırlama, şifre BELİRLEME (OAuth hesabı),
   e-posta değiştirme.
3. **Refresh rotasyonu zorunludur:** kullanılan refresh iptal edilir (`RevokedToken`), yenisi
   verilir. Çalınan bir refresh, meşru kullanıcı bir kez yenileyince ölür.
4. **Logout, access `jti`'sini de iptal eder** (yalnız istemciden silmek yetmez).
5. **Token'ın istemcide saklanma yeri (localStorage) BİLİNÇLİ kabul edilmiş risktir**
   (`guvenlik-review-publish.md` §4): XSS varsa token çalınabilir. Karşılığı: CSP + XSS
   yüzeyinin dar tutulması (React, `dangerouslySetInnerHTML` yok) + kısa access ömrü.
   httpOnly çerezine geçiş CSRF savunması gerektirir; kapalı beta ölçeğinde net kazanç yok,
   Wave-10'da yeniden değerlendirilir.

## Gerekçe

- Sunucu-taraflı oturum eklemek (Redis/DB session store) bu ölçekte yeni bir altyapı
  bağımlılığı ve yeni bir tek-nokta-arıza demektir; kazanç, JWT + `token_version` ile zaten
  elde edilen şeydir.
- `token_version` yaklaşımı çok-worker güvenlidir (durum DB'de, kullanıcı satırında) —
  process-yerel bir oturum sözlüğünün çok-worker'da kırıldığı BUG #185'te ölçülmüştü.

## Sonuçlar / kanıt (iddia değil koşum)

| Karar | Kanıt (test) |
|---|---|
| Refresh rotasyonu + eski refresh ölür | `tests/auth/test_auth.py::test_refresh_yeni_access`, `::test_logout_sonrasi_refresh_gecersiz` |
| Access token refresh yerine kullanılamaz | `tests/auth/test_auth.py::test_access_token_refresh_olarak_reddedilir` |
| Şifre sıfırlama eski oturumları düşürür | `tests/auth/test_pwreset_token_gecerliligi.py::test_sifirlama_tokeni_token_version_tasir`, `::test_sifre_degisince_bekleyen_sifirlama_baglantisi_olur` |
| Şifre BELİRLEME (OAuth hesabı) de düşürür | `tests/auth/test_oauth_sifre_belirleme.py::test_233_sifre_belirleme_diger_oturumlari_dusurur` |
| Sıfırlama token'ı tek kullanımlıktır | `tests/auth/test_pwreset_token_gecerliligi.py::test_ayni_token_iki_kez_kullanilamaz` |
| OAuth state stateless + tek kullanımlık (çok-worker) | `tests/auth/` OAuth testleri + `app/services/oauth.py::consume_state` |

Bu tabloyu `tests/auth/test_adr043_oturum_sozlesmesi.py` denetler: ADR'de adı geçen her test
gerçekten VAR olmalı — belge, kendisini ölçen koşumdan koparsa iddia hâline gelir (L17/R3).

## Reddedilen alternatifler

- **Sunucu-taraflı oturum (Redis)** — yeni altyapı + tek-nokta-arıza; kazanç `token_version`
  ile zaten var.
- **httpOnly çerez + CSRF token** — daha güçlü bir XSS duruşu sağlar ama CSRF savunması,
  SameSite ayarları ve PWA/offline akışıyla etkileşim yeni bir yüzey açar. Kapalı betada
  kullanıcı sayısı ve saldırı yüzeyi küçük; Wave-10'da (açık beta öncesi) yeniden bakılacak.
