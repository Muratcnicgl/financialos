# KALICI ÇÖZÜM PLANI — kapalı betadan sonrası

**Yazıldı:** 11 Ağustos 2026, kapalı beta canlıya alındığı gün.
**Neden yazıldı:** bugünkü kurulum (kendi makine + Tailscale Funnel + Windows görevleri)
**bilinçli bir ara çözümdür**. "Sonra bakarız" bu projede en pahalı cümlelerden biri; bu
belge o cümlenin yerine **yazılı tetikler** koyar.

---

## 0. Bugünkü durum — ne var, ne yok

| | Durum |
|---|---|
| Adres | `financialos.tail378d7a.ts.net` (Tailscale Funnel, ücretsiz, kalıcı) |
| TLS | Let's Encrypt, **kendi makinemizde sonlanıyor** (relay'ler şifreli bayt taşır) |
| Uygulama | uvicorn, SQLite, `SERVE_SPA=1` (arayüzü uygulama servis ediyor) |
| Kayıt | `invite_only` — davet kodu / davetli e-posta zorunlu |
| Otomatik başlatma | ✅ `FinancialOS-Baslat` (**oturum açılışında** — bilgisayarın açılması yetmez, Windows'a giriş yapılmalı) |
| Sağlık kontrolü | ✅ `FinancialOS-Saglik` (10 dk; uygulama + tünel + **dış yol**) |
| Yedek | ✅ `FinancialOS-Yedek` (her gün 03:15, `data/backups/`) |
| **Postgres + RLS** | ❌ **YOK** — SQLite kullanılıyor |
| **7/24** | ❌ Makine kapalıyken uygulama kapalı |
| **Gece cron'ları** | ❌ Makine kapalıysa atlanır, telafi edilmez |
| **Yedeğin geri yükleme provası** | ❌ Canlı veriyle **koşulmadı** |

---

## 1. KABUL EDİLMİŞ BORÇLAR (sessiz değil, yazılı)

### 1.1 RLS (DB-katmanı ikinci savunma) devre dışı
ADR-038/M51 workspace izolasyonunu **iki katmanda** kuruyordu: uygulama katmanı
(`scope_filter`, **birincil**) + PostgreSQL Row-Level Security (**ikinci**). SQLite'ta RLS
yoktur → şu an **tek katman** var.

**Neden kabul edilebilir:** birincil savunma tam ve ağır test edilmiş (workspace izolasyon
matrisi, çapraz-kullanıcı testleri). **Neden kalıcı olamaz:** iki katman kararı bir
sebeple verilmişti; tek katman "yeterli görünüyor" diye kalıcılaşırsa H22'yi ihlal eder.

**Tetik:** VPS'e geçiş (§2) — Postgres ile birlikte RLS geri gelir.

### 1.2 Gece işleri makine kapalıyken atlanıyor
`misfire_grace_time` yalnız 1 saat. 02:45'te makine kapalıysa **o günün yatırım fiyatı
`price_history`'ye hiç yazılmaz** ve açılış telafisi geçmiş tarihi **geri getiremez**
(kod yalnız anlık fiyat çeker). Net-değer geçmişi telafi edilir.

**Tetik:** **davetlilerden birinde yatırım hesabı açılırsa** → ya fiyat çekimini açılış
telafisine ekle (geçmiş tarih desteğiyle) ya da VPS'e geç.

### 1.3 Oturum açılmadan uygulama dönmez
Görevler "oturum açılışında" tetikleniyor. "Kullanıcı oturum açmasa da çalıştır" seçeneği
Windows'ta **parola saklamayı** gerektirir — bilinçli olarak kullanılmadı (bir sırrı görev
zamanlayıcıya yazmak, kazandırdığı rahatlıktan pahalıdır).

**Sonucu:** bilgisayar açılıp **oturum açıldığında** uygulama döner; kilit ekranında dönmez.

---

## 2. VPS'E GEÇİŞ — tetikler ve plan

### Tetikler (biri bile gerçekleşirse geçilir)
1. **Davetlide yatırım hesabı var** → fiyat geçmişi delinir (§1.2)
2. **Makineyi akşamları açık tutamıyorsun** → davetli "açılmıyor" der ve bir daha denemez
3. **Davetli sayısı 5'i geçti** → kesinti maliyeti kişi başı değil, toplam
4. **P8 (açık beta) konuşuluyor** → bu kurulum orada **kabul edilemez**

### Hedef
**Hetzner CX22** (2 vCPU / 4 GB / 40 GB, ~€3,79/ay) + **alan adı** (Cloudflare Registrar
`.com` 10,46 $/yıl sabit).

### Geçişte ne değişir
| | Şimdi | VPS'te |
|---|---|---|
| DB | SQLite | **PostgreSQL + RLS** (ikinci savunma geri gelir) |
| Arayüz | `SERVE_SPA=1` (uygulama servis eder) | **nginx** (`deploy/nginx.conf.template`) |
| TLS | Tailscale (kendi makinede) | **Let's Encrypt + certbot** (hazır yığın **ilk kez** canlıda sınanır) |
| Süreçler | tek uvicorn | compose: db + backend + **scheduler ayrı** + nginx + certbot + backup |
| Çalışma | oturum açıkken | **7/24** |

**Hazır olan:** `docker-compose.prod.yml`, `scripts/deploy.sh` (rollback'li),
`deploy/nginx.conf.template`, `.env.prod` fail-fast, `deploy/pg_backup.sh`.

**Geçiş günü ayrıca yapılacaklar:**
- SQLite → PostgreSQL **veri göçü** (script yok — yazılacak, provası şart)
- `FRONTEND_URL` / `OAUTH_REDIRECT_BASE` yeni alan adına
- Google + GitHub konsollarına **yeni callback URL'leri**
- **Davetlilere önceden haber:** adres değişiyorsa PWA yeniden kurulacak. Sessiz taşıma
  kullanıcı kaybettirir.
- Windows görevleri **kaldırılır** (`gorevleri_kur.ps1 -Kaldir`)

---

## 3. ALAN ADI — ne zaman ve neden

Bugün alan adı **alınmadı**; `*.ts.net` kalıcı ve ücretsiz olduğu için kapalı beta buna
ihtiyaç duymuyor.

**Tetik:** ürün adı netleştiğinde (markalaşma kararı) ya da VPS'e geçişte.

**Bilinen bedel:** adres değişince davetlilerin PWA'yı **yeniden kurması** gerekir. 3-5
kişide bu bir mesajlık iştir ve **bilinçli kabul edilmiştir** — asıl bahis, ürün adını
kullanım verisi olmadan seçmemekti.

**Ölçülmüş fiyatlar (11 Ağu):** Cloudflare Registrar `.com` 10,46 $/yıl · `.app` 14,20 $/yıl
(ikisi de sabit, yenilemede zam yok). GoDaddy'nin "0,01 TL" kampanyası **3 yıllık taahhüt**
ister ve 3 yılda ~1.600 TL tutar — Cloudflare ~1.143 TL. Ayrıntı:
`docs/kalite-seruveni/b0-barindirma-arastirmasi.md`.

---

## 4. HENÜZ KOŞULMAMIŞ KAPILAR (B4'ün kalanı)

| # | Kapı | Durum |
|---|---|---|
| 1 | Canlı SMTP (H11) — şifre sıfırlama e-postası **gerçekten geliyor mu** | ❌ denenmedi |
| 2 | **Yedekten geri yükleme provası** — canlı yedeği boş ortama yükle, aç, veriyi doğrula | ❌ koşulmadı |
| 3 | GitHub OAuth callback | ❌ eklenmedi (kullanan olursa) |
| 4 | `scripts/live_gate.py` canlı adrese karşı | ❌ koşulmadı |
| 5 | Coverage ölçümü (`pytest --cov`) | ❌ 6 Ağu'dan beri ölçülmedi |

**2. madde yayın-engeli sayılır:** "yedek alınıyor" bir iddiadır; kapı **geri yükleme
provasıdır**. Davetli verisi girmeye başladıktan sonra bu daha da kritikleşir.

---

## 4b. AÇILIŞ ZİNCİRİ — ne otomatik, ne değil (11 Ağu, ölçüldü)

Bilgisayarı kapatıp açtığında sırayla şunlar olur:

| Sıra | Bileşen | Otomatik mi | Nasıl |
|---|---|---|---|
| 1 | **Tailscale** | ✅ | Windows servisi, `StartType: Automatic` |
| 2 | **Funnel** | ✅ | `--bg` ile kuruldu; yapılandırma `tailscaled` durumunda saklanır |
| 3 | **Uygulama (uvicorn)** | ✅ | `FinancialOS-Baslat`, **oturum açılışında** |
| 4 | **İzleme** | ✅ | `FinancialOS-Saglik`, **oturum açılışında + 10 dk tekrar** |
| 5 | **Yedek** | ✅ | `FinancialOS-Yedek`, her gün 03:15 |

**TEK ŞART: Windows'a GİRİŞ YAPILMALI.** Görevler "oturum açılışında" tetiklenir; makine
açılıp kilit ekranında beklerse uygulama **başlamaz**. Sebep §1.3'te: "kullanıcı oturum
açmasa da çalıştır" seçeneği Windows'ta **parola saklamayı** gerektirir ve bu bilinçli
olarak reddedildi.

**Pratikte:** bilgisayarı aç, Windows'a gir, **başka hiçbir şeye dokunma**. ~30 saniye
içinde uygulama ayağa kalkar ve dışarıdan erişilebilir olur.

**Sağlık görevindeki düzeltme (aynı gün, ikinci tur):** ilk kurulumda tek tetikleyici
zaman tetiğiydi ve başlangıcı **geçmişte** kaldığı için yeniden başlatmada tekrar kurulumu
güvenilir değildi. Sonucu sinsi olurdu: başlatma görevi çalışır, **izleme sessizce ölür**
ve "izleme var" sanılırken hiçbir şey izlenmez. Oturum-açılışı tetikleyicisi eklendi.

---

## 5. İZLEME — bugün kurulan

`FinancialOS-Saglik` 10 dakikada bir **üç ayrı şeyi** ölçer ve karıştırmaz:
1. **Uygulama** (`127.0.0.1:8000`) → düşmüşse **yeniden başlatır**
2. **Tünel** (funnel yapılandırması) → düşmüşse **yeniden kurar**
3. **Dış yol** (public ingress IP'sinden) → yalnız **raporlar**

**3. madde neden otomatik onarılmıyor:** dış yol Tailscale altyapısına bağlı ve geçici ağ
dalgalanmasında da düşer; her düşüşte servisi sarsmak çalışan sistemi bozar (L6).

**Kritik ayrıntı:** dış yol kontrolü **DoH** (DNS-over-HTTPS) kullanır. Tailscale istemcisi
bu makinede DNS'i ele geçiriyor — normal `Resolve-DnsName` tailnet IP'sini (100.x)
döndürüyor ve kontrol **yanlış negatif** veriyordu. Daha genel ders: **bu makineden
yapılan düz istek funnel'ı ATLAR**, yani *"bende çalışıyor"* bu kurulumda kanıt değildir
(bir kez tam olarak bu yüzden yanıldım).

Log: `logs/saglik.log` · `logs/servis.log` · `logs/uvicorn.out.log`

---

## 6. GERİ ALMA

```powershell
# Gorevleri kaldir
.\deploy\windows\gorevleri_kur.ps1 -Kaldir

# Tuneli kapat
& "$env:ProgramFiles\Tailscale\tailscale.exe" funnel --https=443 off

# Uygulama yerelde calismaya devam eder; yalniz disaridan erisim kapanir.
# DAVETLILERE HABER VER — sessiz kapatma "uygulama bozuldu" demektir.
```

Rollback etiketi: `pre-kapali-beta`
