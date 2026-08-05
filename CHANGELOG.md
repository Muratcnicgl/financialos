# Değişiklik Günlüğü

Bu dosya **yayınlanan** sürümleri kaydeder (P9). Sürüm numarası `app/version.py`
içindeki `APP_VERSION` ile **aynı** olmalıdır — `tests/test_version_release.py` bunu kilitler.

Biçim: [Semantic Versioning](https://semver.org/lang/tr/) · Tarihler: YYYY-AA-GG

## [Yayınlanmamış]

### ⚠️ Kırıcı değişiklik (self-host)
- **`AUTH_ENABLED` varsayılanı AÇIK oldu (#227).** Eskiden değişken tanımsız/boşsa kimlik
  doğrulama KAPALI sayılıyordu; belgelenen systemd dağıtım yolu bu değişkeni hiç set
  etmediği için dokümanı izleyen operatör tüm finansal verisini (cockpit, hesaplar, KVKK
  export'u, hesap silme) kimliksiz açıyordu. Artık kimlik doğrulama açıkça kapatılmadıkça
  AÇIKTIR. **Kimliksiz yerel tek-kullanıcı kurulumu kullananlar `.env`'e `AUTH_ENABLED=false`
  eklemelidir** (production'da bu da fail-fast ile reddedilir).

### Güvenlik
- Şifre sıfırlama bağlantısı, kullanıcı şifresini değiştirdikten sonra hâlâ geçerliydi;
  saldırgan bağlantıyı bekletip hesabı kalıcı ele geçirebiliyordu — token artık oturum
  sürümüne bağlı (#225).
- OAuth kaydı kapalı-beta davet kapısını atlıyordu; alan adını bilen herkes Google/GitHub
  ile hesap açabiliyordu — e-posta eşleşmeli davet kapısı (#226).
- Belgelenen bir dağıtım yolu kimliksiz canlı sunucu üretiyordu — güvenlik varsayılanı
  fail-closed'a çevrildi, systemd unit'i kendini production ilan ediyor (#227).

### Düzeltmeler
- Nakit-akış tahmini ve borç-stratejisi uçları workspace bağlamını kurmuyordu: aile
  görünümünde kişisel borçlar üzerinden strateji hesaplanıyor, cockpit ile çelişen rakamlar
  gösteriliyordu (#223).
- Ön-ölüm (premortem) ve simülasyon uçları da aynı kör noktadaydı (#224).

## [0.2.0] — 2026-08-05 — "Kapalı betaya hazırlık" (Wave-9)

Bu sürüm, uygulamayı **tek kişinin sistemi** olmaktan çıkarıp **yabancıların finansal
verisini taşıyabilecek** bir ürüne dönüştüren kapsamlı bir sertleştirme turudur.
39 bug (#162-#200) kapatıldı.

### Güvenlik
- Şifre sıfırlama token'ı production'da HTTP yanıtında dönüyordu (hesap ele geçirme) — kapatıldı (#170).
- `AUTH_ENABLED` production'da doğrulanmıyordu; compose dışı bir deploy TÜM API'yi kimliksiz
  açıyordu — startup fail-fast eklendi (#171).
- Şifre sıfırlama mevcut oturumları düşürmüyordu; çalınmış refresh token yaşamaya devam
  ediyordu — oturum geçersizleme sayacı, tek-kullanımlık sıfırlama, logout'ta access iptali (#172).
- OAuth access+refresh token'ları yönlendirme URL'inde taşınıyordu — tek-kullanımlık değişim
  koduna geçildi (#179); OAuth state stateless + PKCE (#185); refresh rotasyonu + tekrar-kullanım
  tespiti (#186); şifre politikası (#187).
- Rate limit proxy arkasında tek kovaya düşüyor ve çok-worker'da bölünüyordu (#182);
  davet ucunda limit yoktu (#183).
- Ham exception metni kullanıcıya dönüyordu (#175); girdi sınırları (#176, #177, #181);
  prod CORS localhost'a düşüyordu (#178); PII log temizliği (#180).
- Bağımlılıklarda 23 bilinen açık → 0 (PyJWT, authlib, starlette, cryptography dahil).

### Veri izolasyonu (çok kullanıcı)
- Hedef kuralları TÜM kullanıcılardan çekiliyordu: bir kullanıcının işlemi başkasının
  hedefine yazılıyordu (#162). Kalıcı statik + runtime kapılar eklendi.
- Çok-kullanıcı net-değer backfill (#163), yıkıcı temizlik script'i footgun'ı (#164),
  workspace kapsam tutarsızlığı (#165).

### Ürünleşme
- Metinlerde/koda gömülü kişi adları ve banka markaları temizlendi (#166, #168).
- Türkçe normalizasyon Kiril karakter üretiyordu — sessiz veri bozulması (#167).
- **Kullanıcının kendi kuralı artık kod seviyesinde dayatılıyor** (#192): nakit tabanı,
  dokunulmaz hesap, tek harcama tavanı.
- İsteğe bağlı demo veri + tam silinebilirlik (#194); onboarding kartı; kullanıcı saat
  dilimi (#197).

### Operasyon & uyum
- Kullanıcı başına LLM kotası (ADR-041, #188); giriş yapmış kullanıcı şifre değiştirebiliyor (#190).
- KVKK metinleri canlıda erişilemezdi (#191) — `/api/legal/*` + rıza v2 + kullanım şartları
  + veri-işleyen envanteri.
- Yedekten geri yükleme provası (SQLite + PostgreSQL), kendi kendine yeten hata izleme (#195),
  alembic zincir bütünlüğü (#193) ve config-URL izolasyonu (#196).
- Prod konteynerinde saat dilimi tanımsızdı (#169).

### Kapalı beta
- **Kayıt artık davetli-only** (production varsayılanı, fail-closed) — #199.
- Canlı doğrulama kapısı (`scripts/live_gate.py`) + Docker'sız production provası.

### Bilinen sınırlar
- Para birimi görüntülemesi TRY varsayımlı (ADR-042 — açık betadan önce).
- TLS/Let's Encrypt ve 7/24 cron yalnız gerçek sunucuda doğrulanabilir.

## [0.1.0] — 2026 öncesi
Wave-1…Wave-8: çekirdek uygulama, koç, workspace/RLS, PostgreSQL geçişi, deploy paketi, PWA.
