# RUNBOOK — Kendi makineden yayın: Cloudflare Named Tunnel (B4 / Seçenek A)

**Durum:** HAZIR, koşulmadı. Alan adı alınır alınmaz uygulanır.
**Ön koşul:** alan adı **Cloudflare DNS'inde** olmalı (Cloudflare Registrar'dan alınırsa
kendiliğinden). Quick tunnel (`trycloudflare.com`) **kullanılmaz** — URL her yeniden
başlatmada değişir ve telefona kurulmuş PWA'yı kırar.

> **KURAL 3 / KURAL 9:** aşağıdaki adımların bir kısmı elle yapılır (hesap, satın alma,
> tarayıcıda oturum açma). Her adımda **tam komut + beklenen çıktı + hata karşılığı**
> yazılıdır. Doğrulama adımını atlama: "kurdum" ile "çalışıyor" farklı iddialardır.

---

## 0. Ön kontrol (kurulumdan ÖNCE)

```powershell
# Uygulama yerelde ayakta mı? (compose ile prod profili)
docker compose -f docker-compose.prod.yml ps
# BEKLENEN: db / backend / scheduler / web / certbot / backup → running

curl.exe -s -o NUL -w "%{http_code}`n" http://localhost/api/ready
# BEKLENEN: 200
# 503 gelirse: gövdedeki "sorunlar" alanına bak — migration koşulmamış olabilir:
#   .\venv\Scripts\python.exe -m alembic upgrade head
```

**`/api/ready` 200 dönmeden tünel kurma.** Tünel yalnız erişim sağlar; ayakta olmayan bir
uygulamayı ayağa kaldırmaz ve hatayı kendi katmanında gizler.

---

## 1. `cloudflared` kurulumu (Windows)

```powershell
winget install --id Cloudflare.cloudflared -e
cloudflared --version
# BEKLENEN: cloudflared version 2026.x.x
```

`winget` yoksa: <https://github.com/cloudflare/cloudflared/releases> → `cloudflared-windows-amd64.exe`
indir, `C:\Program Files\cloudflared\cloudflared.exe` olarak koy ve PATH'e ekle.

---

## 2. Cloudflare hesabına bağlan (ELLE — tarayıcı açılır)

```powershell
cloudflared tunnel login
```

Tarayıcı açılır → Cloudflare hesabına giriş yap → **alan adını seç** → yetki ver.
**BEKLENEN:** terminalde `You have successfully logged in.` ve
`C:\Users\<sen>\.cloudflared\cert.pem` dosyası oluşur.

**Hata: "failed to fetch zone"** → alan adı henüz Cloudflare DNS'inde değildir. Registrar
Cloudflare değilse nameserver'ları Cloudflare'a yönlendirmen ve yayılmasını (birkaç saat)
beklemen gerekir.

---

## 3. Tüneli oluştur

```powershell
cloudflared tunnel create financialos
# BEKLENEN: "Created tunnel financialos with id <UUID>"
# Kimlik dosyasi: C:\Users\<sen>\.cloudflared\<UUID>.json  ← BU DOSYA BİR SIRDIR

cloudflared tunnel list
# BEKLENEN: financialos satiri, ID ve olusturma tarihiyle
```

⚠️ `<UUID>.json` **sırdır**: repoya, sohbete, ekran görüntüsüne girmez. Sızarsa
`cloudflared tunnel delete financialos` ile tüneli sil ve yeniden oluştur.

---

## 4. DNS kaydını bağla

```powershell
cloudflared tunnel route dns financialos <ALAN-ADI>
# BEKLENEN: "Added CNAME <ALAN-ADI> which will route to this tunnel"

nslookup <ALAN-ADI>
# BEKLENEN: Cloudflare IP'leri (104.x / 172.67.x sinifi) — kendi IP'in GORUNMEZ
```

**Kendi ev IP'in görünüyorsa** tünel devrede değildir; DNS kaydı proxy'li (turuncu bulut)
olmalı.

---

## 5. Yapılandırma dosyası

`C:\Users\<sen>\.cloudflared\config.yml`:

```yaml
tunnel: financialos
credentials-file: C:\Users\<sen>\.cloudflared\<UUID>.json

ingress:
  - hostname: <ALAN-ADI>
    service: http://localhost:80          # compose'daki `web` (nginx) servisi
    originRequest:
      # Koç istegi iki LLM cagrisi surebilir (10-40 sn) — varsayilan 30 sn'lik
      # baglanti zaman asimi bu yolda ERKEN keser ve kullanici "sunucu hatasi" gorur.
      connectTimeout: 30s
      noTLSVerify: false
  - service: http_status:404              # tanimsiz hostname → 404 (zorunlu son kural)
```

```powershell
cloudflared tunnel ingress validate
# BEKLENEN: "Validating rules... OK"
```

---

## 6. Çalıştır ve DOĞRULA

```powershell
# Once on planda: log gorunsun
cloudflared tunnel run financialos
```

Ayrı bir terminalde:

```powershell
curl.exe -s -o NUL -w "%{http_code}`n" https://<ALAN-ADI>/api/ready
# BEKLENEN: 200

curl.exe -s https://<ALAN-ADI>/api/meta | ConvertFrom-Json | Select-Object surum,build,kayit_modu
# BEKLENEN: surum=0.2.0, build=<gercek git sha>, kayit_modu=invite_only
# build="bilinmiyor" ise: BUILD_COMMIT enjekte edilmemis → .env.prod'a ekle, compose'u yeniden kur.
# kayit_modu "open" ise: DUR. Kapali beta acik demektir (REGISTRATION_MODE / ENVIRONMENT kontrol et).

curl.exe -s -D - -o NUL https://<ALAN-ADI>/api/health | Select-String -Pattern "strict-transport|x-frame|x-request-id"
# BEKLENEN: uc baslik da var (HSTS + X-Frame-Options + X-Request-Id)
```

**Sonra servis olarak kur** (makine açıldığında kendiliğinden başlasın):

```powershell
# Yonetici PowerShell:
cloudflared service install
Get-Service cloudflared
# BEKLENEN: Status=Running, StartType=Automatic
```

---

## 7. Yayın sonrası zorunlu kontroller (B4 kapısı)

| # | Kontrol | Komut / yol | Beklenen |
|---|---|---|---|
| 1 | Hazır olma | `curl https://<ALAN-ADI>/api/ready` | 200 |
| 2 | Sürüm damgası | `/api/meta` → `build` | gerçek git SHA |
| 3 | Kayıt kapalı | `/api/meta` → `kayit_modu` | `invite_only` |
| 4 | Güvenlik başlıkları | yanıt başlıkları | HSTS + X-Frame + nosniff |
| 5 | Korelasyon kimliği | yanıt başlığı | `X-Request-Id` var |
| 6 | PWA **gerçek telefonda** | ana ekrana ekle → aç → çevrimdışı | ikon + açılış çalışır |
| 7 | Canlı SMTP (H11) | şifre sıfırlama iste | e-posta **gerçekten gelir** |
| 8 | **Canlı yedek + geri yükleme provası** | yedeği al → boş ortama yükle → aç | uygulama açılır, veri bütün |
| 9 | Canlı kapı | `.\venv\Scripts\python.exe scripts/live_gate.py` | yeşil |

**Eksik kalan madde "KANIT YOK" yazılır, gizlenmez.**

---

## 8. Bilinen sınırlar (yazılı, sürpriz olmasın)

1. **Makine kapalıysa uygulama kapalıdır.** Davetli karşılama metninde bu yazılı.
2. **Gece işleri atlanır.** `misfire_grace_time` yalnız 1 saat; 02:45'te makine kapalıysa
   o günün yatırım fiyatı `price_history`'ye **hiç yazılmaz** ve açılış telafisi geçmiş
   tarihi **geri getiremez** (kod yalnız anlık fiyat çekiyor). Net-değer geçmişi telafi
   edilir. → Davetlilerde yatırım hesabı varsa **VPS'e geçiş tetiği** budur.
3. **Hazır nginx/Let's Encrypt yığını bu yolda devrede değildir** — TLS Cloudflare
   kenarında biter. B'ye (VPS) geçildiğinde o yığın **ilk kez** canlıda sınanacaktır;
   geçiş günü bunu ayrı bir doğrulama adımı say.
4. **Cloudflare ücretsiz katmanı** bant genişliği/kullanım koşullarına tabidir; kapalı
   betanın hacmi bunun çok altında ama açık betada (P8) yeniden değerlendirilir.

---

## 9. Geri alma (rollback)

```powershell
cloudflared service uninstall     # servisi kaldir
cloudflared tunnel delete financialos
# DNS kaydi Cloudflare panelinden silinir (CNAME <ALAN-ADI>)
```

Uygulama yerelde çalışmaya devam eder; yalnız dışarıdan erişim kapanır. Davetlilere
haber ver — sessiz kapatma, kullanıcı için "uygulama bozuldu" demektir.
