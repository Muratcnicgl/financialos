# FinancialOS — kapalı beta sağlık kontrolü (BUG #290 / B4)
#
# NEDEN VAR: tünel yolu SESSİZCE düşüyor. Bir kez yaşandı — kullanıcı "güvenli bağlantı
# kurulamadı" dedi, operatör (ben) makineden baktığında her şey yeşil görünüyordu çünkü
# makine tailnet'in İÇİNDE ve isteği funnel'ı atlıyordu. Yani "bende çalışıyor" bu
# kurulumda kanıt DEĞİL — dışarıdaki yolun ayrıca ölçülmesi gerekiyor.
#
# ÜÇ AYRI ŞEY ÖLÇÜLÜR ve karıştırılmaz:
#   1. UYGULAMA  — 127.0.0.1:8000 cevap veriyor mu   → düşmüşse YENİDEN BAŞLATILIR
#   2. TÜNEL     — Funnel yapılandırması duruyor mu  → düşmüşse YENİDEN KURULUR
#   3. DIŞ YOL   — public ingress IP'sinden erişim   → yalnız RAPORLANIR
#
# 3. madde neden otomatik onarılmıyor: dış yol Tailscale'in altyapısına bağlı ve geçici
# ağ dalgalanmasında da düşer. Her düşüşte servisi yeniden başlatmak, çalışan bir
# sistemi gereksizce sarsar (L6: kapı ürünü kırmaz). Israrla düşerse operatör görür.
#
# GUNCELLEMELER
# -------------
# BUG #303 fix (12 Ağu 2026): 3. adım yanlış negatif üretiyordu — `/api/ready` ölçüyordu
#   (DB sorusu, yol sorusu değil), DoH çözümlemesi başarısızken "tünel kapalı" diyordu ve
#   tek denemeyle karar veriyordu. Sonuç: saglik.log'da gerçek olmayan HATA satırları →
#   gerçekten düştüğü anı ayırt edilemez hâle getiriyordu. Bu görev artık pencere de
#   açmıyor (bkz. `gizli_calistir.vbs`).
param(
    [int]$Port = 8000,
    [string]$Adres = "financialos.tail378d7a.ts.net"
)

$KOK = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$LOGDIZIN = Join-Path $KOK "logs"
$LOG = Join-Path $LOGDIZIN "saglik.log"
if (-not (Test-Path $LOGDIZIN)) { New-Item -ItemType Directory -Path $LOGDIZIN | Out-Null }

function Yaz($seviye, $mesaj) {
    $satir = "{0} [{1}] {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $seviye, $mesaj
    Add-Content -Path $LOG -Value $satir -Encoding UTF8
    Write-Output $satir
}

# Log dosyası sınırsız büyümesin (beta boyunca 6 ayda ~26k satır olurdu).
if ((Test-Path $LOG) -and ((Get-Item $LOG).Length -gt 2MB)) {
    Get-Content $LOG -Tail 500 | Set-Content "$LOG.tmp" -Encoding UTF8
    Move-Item "$LOG.tmp" $LOG -Force
}

$sorun = @()

# ── 1. UYGULAMA ────────────────────────────────────────────────────────────
$uygulamaOk = $false
try {
    $r = Invoke-WebRequest "http://127.0.0.1:$Port/api/ready" -UseBasicParsing -TimeoutSec 15
    if ($r.StatusCode -eq 200) { $uygulamaOk = $true }
} catch { }

if (-not $uygulamaOk) {
    Yaz "UYARI" "uygulama cevap vermiyor — yeniden baslatiliyor"
    & (Join-Path $PSScriptRoot "baslat.ps1") -Port $Port | Out-Null
    Start-Sleep -Seconds 3
    try {
        $r2 = Invoke-WebRequest "http://127.0.0.1:$Port/api/ready" -UseBasicParsing -TimeoutSec 15
        if ($r2.StatusCode -eq 200) { Yaz "ONARILDI" "uygulama yeniden ayakta"; $uygulamaOk = $true }
    } catch { $sorun += "uygulama baslatilamadi" }
}

# ── 2. TÜNEL ───────────────────────────────────────────────────────────────
$ts = Join-Path $env:ProgramFiles "Tailscale\tailscale.exe"
if (Test-Path $ts) {
    $funnel = & $ts funnel status 2>&1 | Out-String
    if ($funnel -notmatch "Funnel on") {
        Yaz "UYARI" "funnel kapali — yeniden kuruluyor"
        & $ts funnel --bg --https=443 "http://127.0.0.1:$Port" 2>&1 | Out-Null
        Start-Sleep -Seconds 3
        $funnel2 = & $ts funnel status 2>&1 | Out-String
        if ($funnel2 -match "Funnel on") { Yaz "ONARILDI" "funnel yeniden acildi" }
        else { $sorun += "funnel acilamadi" }
    }
} else { $sorun += "tailscale bulunamadi" }

# ── 3. DIŞ YOL (yalnız raporlanır) ─────────────────────────────────────────
# ÖNEMLİ: `--resolve` ile PUBLIC ingress IP'si zorlanır. Düz istek bu makinede
# tailnet IP'sine (100.x) gider ve funnel'ı ATLAR — yani hiçbir şey ölçmez.
# NEDEN DoH (DNS-over-HTTPS): Tailscale istemcisi bu makinede DNS'i ELE GECIRIYOR —
# `Resolve-DnsName -Server 1.1.1.1` bile tailnet IP'sini (100.x) donduruyor. Yani normal
# DNS ile "disaridan hangi IP gorunuyor" sorusu bu makineden SORULAMAZ. DoH bir HTTPS
# istegidir; araya girilemez ve gercek public IP'leri verir. (Ilk yazimda normal DNS
# kullanilmisti ve kontrol her seferinde YANLIS NEGATIF veriyordu.)
# BUG #303: bu adım üç noktada YANLIŞ NEGATİF üretiyordu ve log'u güvenilmez kılıyordu.
#   (a) Ölçülen uç `/api/ready` idi — o uç VERİTABANINA dokunur. Buradaki soru "dış yol
#       AÇIK MI"; uygulamanın hazır olup olmadığı 1. adımda ZATEN yerel olarak ölçülüyor.
#       Yavaş bir DB sorgusu, sağlam bir tüneli "erişilemiyor" diye raporluyordu (iki ayrı
#       soruyu tek bayrakla cevaplamak — bu defterde tanıdık sınıf).
#   (b) DoH isteği başarısız olursa `catch` sessizce yutuyor ve sonuç "DIS YOL
#       erisilemiyor" oluyordu. Oysa çözümlenemeyen DNS ile kapalı tünel AYNI ŞEY DEĞİL;
#       operatör yanlış yere bakar.
#   (c) Tek deneme. Relay üzerinden gelen anlık dalgalanma (ölçüldü: 0.5-3.1 sn arası
#       oynuyor) doğrudan HATA satırına dönüşüyordu. Israrlı arıza ile hıçkırık ayrılmalı.
# BUG #303 (ikinci bulgu — CANLI ARIZA, 12 Ağu 14:22): tek çözümleyiciye (Cloudflare)
# bakmak, gerçekte YAŞANAN bir kesintiyi yanlış adla raporluyordu. Ölçüm: aynı anda
# Cloudflare `Status:3` (NXDOMAIN) derken Google 3 A kaydını sorunsuz döndürdü. Yani
# `ts.net` adı BAZI çözümleyicilerde geçici olarak kayboluyor — Chrome/Brave'in "Güvenli
# DNS" özelliği çoğu kurulumda Cloudflare'e gider, dolayısıyla bu pencerede DAVETLİ
# KULLANICI SİTEYİ AÇAMAZ. Operatör makinesinde hiçbir şey görünmez, çünkü Tailscale
# istemcisi adı tailnet içinden çözer.
#
# Bu yüzden burada iki soru AYRI sorulur ve ayrı raporlanır:
#   - "adres çözülüyor mu"  → kullanıcının siteye ULAŞABİLMESİ bu cevaba bağlı
#   - "ingress cevap veriyor mu" → tünelin kendisi
# Çözümleyiciler ÇELİŞİYORSA bu bir kesintidir: kullanıcıların bir kısmı giremiyordur.
$disOk = $false
$disNot = "DIS YOL erisilemiyor (public ingress)"
$ipler = @()
$cozenler = @()
$cozmeyenler = @()

foreach ($cozumleyici in @(
    @{ ad = "cloudflare"; url = "https://cloudflare-dns.com/dns-query?name=$Adres&type=A" },
    @{ ad = "google";     url = "https://dns.google/resolve?name=$Adres&type=A" }
)) {
    # curl.exe kullanılır, Invoke-RestMethod DEĞİL: ikincisi bu makinede aynı sorguya
    # boş gövde döndürüyordu (kanıt BUG #303 turu). Ölçüm aracının kendisi sessizce
    # başarısız olursa ölçüm de yalan söyler.
    $ham = & curl.exe -s --max-time 15 -H "accept: application/dns-json" $cozumleyici.url 2>$null
    $bulunan = @()
    try {
        $j = $ham | ConvertFrom-Json
        if ($j.Status -eq 0) {
            $bulunan = @($j.Answer | Where-Object { $_.type -eq 1 -and $_.data -notlike "100.*" } |
                         ForEach-Object { $_.data })
        }
    } catch { }
    if ($bulunan.Count -gt 0) {
        $cozenler += $cozumleyici.ad
        $ipler += $bulunan
    } else {
        $cozmeyenler += $cozumleyici.ad
    }
}
$ipler = @($ipler | Select-Object -Unique)

if ($cozenler.Count -gt 0 -and $cozmeyenler.Count -gt 0) {
    # Kısmi DNS kesintisi — tünel sağlam olsa bile kullanıcıların bir kısmı giremez.
    $sorun += ("DNS KISMI KESINTI — cozmeyen: {0} (cozen: {1}); bu cozumleyiciyi kullanan davetli SITEYI ACAMAZ" `
               -f ($cozmeyenler -join ","), ($cozenler -join ","))
}

if ($ipler.Count -eq 0) {
    # Hiçbir çözümleyici cevap vermedi: ya adres tamamen düştü ya da bu makinenin
    # internet erişimi yok. İkisi de "tünel kapalı" DEĞİLDİR — ayrı yazılır.
    $disNot = "DIS ADRES HIC COZULMUYOR (hicbir cozumleyici A kaydi vermedi) — davetliler SITEYI ACAMAZ"
} else {
    $sonKod = ""
    foreach ($deneme in 1, 2) {
        foreach ($ip in $ipler) {
            $sonKod = & curl.exe -s -o NUL -w "%{http_code}" --max-time 20 `
                        --resolve "${Adres}:443:${ip}" "https://$Adres/api/health" 2>$null
            if ($sonKod -eq "200") { $disOk = $true; break }
        }
        if ($disOk) { break }
        if ($deneme -eq 1) { Start-Sleep -Seconds 5 }   # hıçkırık mı, arıza mı
    }
    if (-not $disOk) { $disNot = "DIS YOL erisilemiyor (public ingress, son kod: $sonKod)" }
}

if (-not $disOk) { $sorun += $disNot }

# ── ÖLÜ ADAM ANAHTARI (Wave-Y / Y2, BUG #342) ──────────────────────────────
#
# NEDEN YOKLAMA DEĞİL: yoklayan bir izleyici SESSİZCE ÖLEBİLİR ve öldüğünde sessizlik
# "her şey yolunda" gibi görünür. Y2'nin kapatmak için var olduğu körlük tam budur —
# 24,5 saatlik kesinti de tam böyle görünmüştü (BUG #326/#328).
#
# Ölü adam anahtarı YÖNÜ TERSİNE ÇEVİRİR: makine dışarı ping atar, ping kesilirse alarm
# çalar. Ping'in kesilme sebepleri — servis öldü · makine kapandı · ağ gitti · bu görev
# bozuldu — HEPSİ kesintidir ve hepsi aynı alarmı üretir. **Sessizlik, her şeyin yolunda
# olduğunun değil, alarmın kendisidir.** "Bekçiyi kim bekliyor?" sorusu böylece ortadan
# kalkar: bekçinin ölümü de kesinti sayılır.
#
# PING YALNIZ SAĞLIK TAMKEN ATILIR. Koşulsuz ping, "süreç ayakta" ile "servis çalışıyor"u
# karıştırırdı — Y1'in kök nedeni tam olarak buydu (eski süreç de 200 veriyordu).
# Buradaki `$sorun.Count -eq 0`, uygulama + tünel + DIŞ yolun üçünü birden kapsar.
#
# Adres YAPILANDIRMADAN okunur ve depoya GİRMEZ (`izleme-url.txt` .gitignore'da): o URL
# bir kimlik taşır, commit edilirse herkes sahte "sağlıklıyım" sinyali gönderebilir ve
# alarm kalıcı olarak susturulabilirdi.
function PingAt($durum) {
    $dosya = Join-Path $PSScriptRoot "izleme-url.txt"
    $url = $env:FOS_IZLEME_PING_URL
    if (-not $url -and (Test-Path $dosya)) { $url = (Get-Content $dosya -Raw).Trim() }
    if (-not $url) {
        # Yapılandırılmamış olmak SESSİZ kalmamalı — ama 10 dakikada bir yazmak da log'u
        # boğar; saat başı bir satır, "izleme yok" durumunun kendisini görünür tutar.
        if ((Get-Date).Minute -lt 10) { Yaz "UYARI" "olu adam anahtari YAPILANDIRILMAMIS (izleme-url.txt yok)" }
        return
    }
    try {
        Invoke-WebRequest $url -UseBasicParsing -TimeoutSec 10 -Method Get | Out-Null
    } catch {
        # İzleme servisi düşse bile SAĞLIK GÖREVİ düşmez: bekçi, beklediği şeyi bozmamalı.
        Yaz "UYARI" "izleme ping'i gonderilemedi (izleme servisi tarafi): $($_.Exception.Message)"
    }
}

# Erişilebilirlik kaydı: HER koşumda tek satır. Yüzde hesabı üçüncü tarafa değil buna
# dayanır — ve KAYIP SATIRLAR da veridir: görev 10 dakikada bir koştuğu için, olması
# gereken slot sayısıyla gerçekleşen satır sayısı arasındaki fark **kesintinin kendisidir**
# (makine kapalıyken satır yazılmaz). Böylece "veri yok" sessizce %100'e dönüşemez (L45).
function KayitYaz($ok) {
    $csv = Join-Path $LOGDIZIN "erisilebilirlik.csv"
    if (-not (Test-Path $csv)) {
        Add-Content -Path $csv -Value "zaman_utc,saglikli" -Encoding UTF8
    }
    $satir = "{0},{1}" -f (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"), $ok
    Add-Content -Path $csv -Value $satir -Encoding UTF8
}

# ── Sonuç ──────────────────────────────────────────────────────────────────
if ($sorun.Count -eq 0) {
    KayitYaz 1
    PingAt "saglam"
    # Sessiz başarı: her 10 dakikada bir satır, log'u boğmasın diye YALNIZ saat başı yaz.
    if ((Get-Date).Minute -lt 10) { Yaz "OK" "uygulama + tunel + dis yol saglam" }
    exit 0
}
# Sorun varken ping ATILMAZ — susmak, alarmın kendisidir.
KayitYaz 0
Yaz "HATA" ($sorun -join " | ")
exit 1
