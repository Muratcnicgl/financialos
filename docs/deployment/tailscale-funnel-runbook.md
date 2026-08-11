# RUNBOOK — Kendi makineden yayın: Tailscale Funnel (B4 / Seçenek A-0, **alan adı GEREKMEZ**)

**Durum:** HAZIR, koşulmadı.
**Ne zaman bu yol:** "şimdi 0 TL başla, markalaşınca alan adı al" kararı verildiğinde.
**Maliyet: 0.** Alan adı yok, sunucu yok, port yönlendirme yok.

> Bu yol, Cloudflare Tunnel'ın alan adı şartını **tamamen ortadan kaldırır** çünkü Tailscale
> kalıcı bir hostname'i kendisi verir: `makine-adi.tailnet-adi.ts.net`.

---

## 0. Neden bu yol çalışıyor (ve neyi çözüyor)

| Sorun | Tailscale Funnel'ın cevabı |
|---|---|
| Kalıcı URL (PWA kırılmasın) | `*.ts.net` hostname'i **sabittir**, yeniden başlatmada değişmez |
| Geçerli HTTPS | Sertifika **otomatik** sağlanır |
| Port yönlendirme / router erişimi | **Gerekmez** — bağlantı içeriden dışarı kurulur |
| CGNAT (Türkiye'de yaygın) | **Sorun değil** — relay üzerinden çalışır, gelen bağlantı beklemez |
| Ev IP'sinin açığa çıkması | **Çıkmaz** — internetteki kimse makineye doğrudan bağlanamaz |
| Gizlilik | **TLS SENİN MAKİNENDE sonlanır** (`termination is done by your node's Tailscale daemon itself`) → relay'ler yalnız şifreli bayt taşır. Cloudflare Tunnel'da TLS kenarda sonlanır, yani orada vekil düz metni görür. Bu yol bu açıdan **daha iyidir.** |

**Bilinen sınırlar (yazılı olsun):**
1. Funnel yalnız **443 / 8443 / 10000** portlarında yayın yapar → 443 kullanacağız, sorun yok.
2. Adres çirkindir (`...ts.net`) — kapalı beta için önemsiz, markalaşmada değişecek.
3. Tailscale ücretsiz katmanı kişisel kullanım içindir; kapalı beta hacmi bunun çok altında,
   ama **açık betada (P8) bu yol kullanılmaz** — orada alan adı + VPS şarttır.
4. Makine kapalıyken uygulama kapalıdır (Seçenek A'nın değişmeyen bedeli) ve gece cron'ları
   atlanır (bkz. Cloudflare runbook §8.2 — aynı sınır).
5. **Markalaşmaya geçildiğinde adres değişir** → davetlilerin PWA'yı yeniden kurması gerekir.
   3-5 kişide bu bir mesajlık iştir; **bilinçli kabul edilmiş bedeldir.**

---

## 1. Ön koşul — nginx TÜNEL şablonuna geçilmiş olmalı

⚠️ **Bu adım atlanırsa uygulama açılmaz.** Varsayılan `deploy/nginx.conf.template` :80'i
koşulsuz `return 301 https://…` ile yönlendirir. Tünelde TLS dışarıda sonlandığı için
nginx'e düz HTTP gelir → **sonsuz yönlendirme döngüsü**.

`deploy/nginx.tunnel.conf.template` bunun için var: yönlendirmez, TLS sonlandırmaz,
`X-Forwarded-Proto: https` sabitler, güvenlik başlıklarını **aynen** taşır
(kapı: `tests/security/test_guvenlik_basliklari.py`).

```powershell
# compose'da web servisinin sablonunu tunel surumune cevir (ayrinti: docker-compose.prod.yml)
# ve yigini kaldir:
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps
# BEKLENEN: db / backend / scheduler / web running (certbot TUNEL MODUNDA GEREKMEZ)

curl.exe -s -o NUL -w "%{http_code}`n" http://localhost/api/ready
# BEKLENEN: 200   ← 301 gorursen tunel sablonuna gecilmemis demektir
```

---

## 2. Tailscale kurulumu

```powershell
winget install --id Tailscale.Tailscale -e
tailscale version
# BEKLENEN: 1.5x.x veya ustu (funnel komutu 1.52'de degisti)

tailscale up
# Tarayici acilir → hesap ac / giris yap (Google/GitHub/Microsoft ile olur)
# BEKLENEN: "Success." ve makine tailnet'e katilir

tailscale status
# BEKLENEN: makinenin adi + 100.x.y.z adresi
```

**Makineye anlamlı bir ad ver** (hostname URL'e girer):

```powershell
tailscale set --hostname=financialos
```

---

## 3. Funnel'ı aç

```powershell
# Once tailnet politikasinda Funnel'in acik olmasi gerekir; komut gerekirse
# admin panelinde onay linki verir (tarayicida tek tik).
tailscale funnel --bg --https=443 http://127.0.0.1:80

tailscale funnel status
# BEKLENEN ornegi:
#   https://financialos.<tailnet>.ts.net (Funnel on)
#   |-- / proxy http://127.0.0.1:80
```

`--bg` **zorunlu**: arka planda kalır ve makine yeniden başladığında Funnel kendiliğinden
devam eder. `--bg` olmadan çalıştırırsan her açılışta elle başlatman gerekir.

**Not:** hedef `http://127.0.0.1:80` — Funnel yalnız `127.0.0.1`'e vekillik eder.
Compose'daki `web` (nginx) servisi 80'i host'a yayınlıyor olmalı.

---

## 4. DOĞRULAMA (bu adım atlanmaz)

```powershell
$URL = "https://financialos.<tailnet>.ts.net"

curl.exe -s -o NUL -w "%{http_code}`n" "$URL/api/ready"
# BEKLENEN: 200

curl.exe -s "$URL/api/meta" | ConvertFrom-Json | Select-Object surum,build,kayit_modu
# BEKLENEN: surum=0.2.0 · build=<gercek git sha> · kayit_modu=invite_only
# build="bilinmiyor" → BUILD_COMMIT enjekte edilmemis
# kayit_modu="open"  → DUR, kapali beta acik demektir

curl.exe -s -D - -o NUL "$URL/api/health" | Select-String -Pattern "strict-transport|x-frame|x-request-id"
# BEKLENEN: uc baslik da var

# Yonlendirme dongusu KONTROLU (en sik hata):
curl.exe -s -o NUL -w "%{num_redirects}`n" -L "$URL/"
# BEKLENEN: 0 veya 1. Yuksek sayi/hata → nginx tunel sablonuna gecilmemis (§1)
```

**Sonra gerçek telefonda:** adresi aç → giriş yap → **ana ekrana ekle** → ikondan aç.
Emülatör ölçümü tek başına yetmez (L29).

---

## 5. Kapanış kapısı (Cloudflare runbook'undaki 9 madde ile aynı)

| # | Kontrol | Beklenen |
|---|---|---|
| 1 | `/api/ready` | 200 |
| 2 | `/api/meta` → `build` | gerçek git SHA |
| 3 | `/api/meta` → `kayit_modu` | `invite_only` |
| 4 | Güvenlik başlıkları | HSTS + X-Frame + nosniff |
| 5 | `X-Request-Id` | yanıtta var |
| 6 | Yönlendirme döngüsü yok | `num_redirects` ≤ 1 |
| 7 | PWA **gerçek telefonda** | ikon + açılış |
| 8 | Canlı SMTP (H11) | e-posta gerçekten gelir |
| 9 | **Canlı yedek + geri yükleme provası** | boş ortama yüklenip açılır |
| 10 | `scripts/live_gate.py` | yeşil |

Eksik madde **"KANIT YOK"** yazılır.

---

## 6. Kapatma / geri alma

```powershell
tailscale funnel --https=443 off      # yalniz yayini kapat
tailscale down                        # tailnet baglantisini da kes
```

Uygulama yerelde çalışmaya devam eder. **Davetlilere haber ver** — sessiz kapatma
kullanıcı için "uygulama bozuldu" demektir.

---

## 7. Markalaşmaya geçiş (ileride)

Alan adı alındığında iki yol var; ikisi de bu kurulumun üstüne gelir:

- **Alan adı + Cloudflare Tunnel** → `cloudflare-tunnel-runbook.md` (aynı nginx tünel şablonu
  kullanılır, hiçbir şey yeniden yazılmaz).
- **Alan adı + VPS** → `deploy/nginx.conf.template` (VPS modu) + `scripts/deploy.sh`.

**Geçiş günü yapılacak tek ek iş:** davetlilere "adres değişti, ana ekrandaki eskisini silin,
şunu ekleyin" mesajı. Bunu **önceden** duyur; sessiz taşıma kullanıcı kaybettirir.
