# P2 — Güvenlik Review (Wave-9 publish yolu)

**Tarih:** 2026-08-04/05 · **Kapsam:** kapalı-beta öncesi zorunlu güvenlik kapısı · **Durum:** ✅ KAPI GEÇTİ
**Masterprompt:** `masterprompt-publish.md` §P2

> Yöntem: iki bağımsız ajan tüm `app/`, `frontend/src/`, deploy dosyalarını taradı (34 bulgu
> raporladı). **Ajan raporu kanıt sayılmadı** (§5) — her bulgu kod okunarak doğrulandı, gerçek
> olanlar TDD ile (önce kırmızı test) kapatıldı, gerçek olmayanlar/zaten korunanlar elendi.

---

## 1. KAPATILAN AÇIKLAR (19 bug)

### Kritik — hesap ele geçirme sınıfı
| # | Açık | Somut senaryo |
|---|---|---|
| #170 | Şifre sıfırlama token'ı **HTTP yanıtında** dönüyordu (koşulda `is_production()` yoktu) | Prod'da SMTP eksik/bozuksa saldırgan herhangi bir e-posta için token alır → şifreyi değiştirir |
| #171 | `AUTH_ENABLED` production'da **doğrulanmıyordu** (varsayılan KAPALI) | Compose dışı bir deploy (systemd/manuel/PaaS) tüm API'yi kimliksiz "ilk kullanıcı"ya açardı |
| #172 | Şifre sıfırlama **oturumları düşürmüyordu** | Çalınmış 30 günlük refresh, kurban şifresini değiştirdikten sonra da çalışırdı (hesap geri alınamaz) |

### Yüksek
| # | Açık | Etki |
|---|---|---|
| #173 | `subscriptions`/`fund_price`'ta `require_write` yok | **viewer** paylaşılan workspace'e gider yazar, yatırım fiyatını/bakiyeyi değiştirir |
| #175 | Ham exception metni gövdede (4 uç + cockpit) | SQL cümlesi/kolon adları/iç yol ifşası |
| #179 | OAuth access+refresh **URL'de** | 30 günlük token: tarayıcı geçmişi, access log, Referer |
| #185 | OAuth state process-yerel + PKCE yok | Çok-worker'da girişlerin ~yarısı düşer; CSRF korumasını gevşetme baskısı |
| #186 | Refresh **rotasyonu yok** | Çalınmış token 30 gün sınırsız; sızıntı asla tespit edilemez |
| #182 | Rate limit: proxy arkasında **tek kova** + çok-worker'da bölünme | Bir saldırgan 5 hatalı login ile HERKESİN girişini kilitler (DoS) |

### Orta / düşük
`#174` kimliksiz kullanıcı yaratma · `#176` Goal tutarlarında `Infinity`/sınırsız ·
`#177` sınırsız checkpoint metni **sistem prompt'una** giriyordu · `#178` prod CORS localhost'a
düşüyordu · `#180` tam e-posta + ham koç mesajı log'da (KVKK) · `#181` 6 router'da sınırsız
serbest metin · `#183` davet ucunda rate limit yok (SMTP spam relay) · `#184` Caddy yolunda CSP
ve gövde sınırı yok + geçersiz site adresi · `#187` şifre politikası yalnız uzunluk ·
`#169` prod konteynerlerinde saat dilimi tanımsız (UTC → yanlış "bugün", cron 3 saat kayması).

## 2. BAĞIMLILIK DENETİMİ

```
KOMUT : python -m pip_audit
ÖNCE  : 23 bilinen açık / 5 paket
SONRA : No known vulnerabilities found
```
En kritiği **PyJWT 2.9.0 → 2.13.0** (11 advisory) — uygulamanın **token doğrulama** kütüphanesi.
Ayrıca authlib 1.3.2→1.7.2 (OAuth), starlette 0.38.6→1.3.1 (fastapi 0.115→0.141 ile),
cryptography, requests, urllib3, python-multipart, python-dotenv, idna, pyasn1.
`npm audit`: 0 açık. Sürümler `requirements.txt`'te sabitlendi + dolaylı bağımlılıklar için
güvenlik-tabanı bloğu eklendi (eski sürümler transitif geri gelmesin).

## 3. DOĞRULANIP "AÇIK DEĞİL" DENEN BAŞLIKLAR

- **SQL enjeksiyonu:** tek `text()` f-string'i modül sabiti interpole ediyor; tüm kullanıcı
  değerleri bound parameter. Enjekte edilemez.
- **XSS:** `dangerouslySetInnerHTML` sıfır kullanım; `react-markdown` `rehype-raw`'sız (ham HTML
  parse edilmez) + nginx CSP `script-src 'self'`.
- **Path traversal:** dosya tabanlı export/import özelliği yok; tüm export saf JSON.
- **Repo'da gerçek sır:** git'te izlenen env dosyaları boş/`REPLACE_WITH_*`; `.env` hem
  `.gitignore` hem `.dockerignore` içinde; prod'da zayıf SECRET_KEY fail-fast.
- **Başkasının verisi koça geçmiyor:** `user_id` istemciden hiç alınmıyor (`get_current_user`
  + `scope_filter`/`workspace_scope` + Postgres RLS).
- **Dosya yükleme:** yükleme ucu mevcut değil (saldırı yüzeyi açılmamış).

## 4. KABUL EDİLEN RİSKLER (gerekçeli, kapatılmadı)

- **Kayıt ucunda e-posta enumerasyonu (409 "zaten kayıtlı").** Kapalı betada davetli kullanıcı
  olduğu için etkisi sınırlı; rate limit (3/saat/IP) + nginx `limit_req` ile ölçeklenmesi
  engellendi. Açık betaya geçmeden (P8) generic-yanıt + "hesabınız zaten var" e-postası
  desenine geçilecek.
- **Depolanmış metinle dolaylı prompt injection.** Checkpoint/hesap metni sistem prompt'una
  giriyor (artık 2000 karakterle sınırlı). Kod katmanı savunmaları duruyor: tool-gating
  (`should_offer_propose_action`), insan onayı zorunlu, checkpoint enforcement kodda,
  grounding TL doğrulaması. Tam çözüm (kullanıcı metnini sistem prompt'undan ayırma) P3'te
  koç maliyet/kota çalışmasıyla birlikte ele alınacak.
- **Token'lar `localStorage`'da.** XSS vektörü bulunamadı + CSP `script-src 'self'`.
  httpOnly çerez mimarisi tüm frontend akışını değiştirir; kapalı beta sonrası değerlendirilecek.

## 5. KANIT

```
KOMUT : .\venv\Scripts\python.exe -m pytest tests/ -q
ÇIKTI : 1390 passed, 5 skipped
KOMUT : cd frontend && npm test -- --run
ÇIKTI : 65 passed
KOMUT : .\venv\Scripts\python.exe scripts/test_fresh_db_migration.py
ÇIKTI : temiz DB'de alembic upgrade head → 26 tablo, create_all ile TAM ÖZDEŞ
KOMUT : .\venv\Scripts\python.exe scripts/pg_gate_run.py
ÇIKTI : 13 passed (PostgreSQL RLS + Numeric + net-worth + NULL-ordering)
```

Yeni kalıcı güvenlik testleri: `tests/security/test_auth_hardening_p2.py`,
`test_input_and_exposure_p2.py`, `test_oauth_code_exchange_p2.py`, `test_oauth_state_pkce_p2.py`,
`test_rate_limit_hardening_p2.py`, `test_refresh_rotation_password_policy_p2.py`,
`tests/test_deploy_timezone.py` (deploy yapılandırma kapıları).
