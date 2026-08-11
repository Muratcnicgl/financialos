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
$disOk = $false
try {
    $doh = Invoke-RestMethod -Uri "https://cloudflare-dns.com/dns-query?name=$Adres&type=A" `
             -Headers @{accept = "application/dns-json"} -TimeoutSec 20
    $ipler = @($doh.Answer | Where-Object { $_.type -eq 1 -and $_.data -notlike "100.*" } |
               ForEach-Object { $_.data })
    foreach ($ip in $ipler) {
        $kod = & curl.exe -s -o NUL -w "%{http_code}" --max-time 20 `
                 --resolve "${Adres}:443:${ip}" "https://$Adres/api/ready" 2>$null
        if ($kod -eq "200") { $disOk = $true; break }
    }
} catch { }

if (-not $disOk) { $sorun += "DIS YOL erisilemiyor (public ingress)" }

# ── Sonuç ──────────────────────────────────────────────────────────────────
if ($sorun.Count -eq 0) {
    # Sessiz başarı: her 10 dakikada bir satır, log'u boğmasın diye YALNIZ saat başı yaz.
    if ((Get-Date).Minute -lt 10) { Yaz "OK" "uygulama + tunel + dis yol saglam" }
    exit 0
}
Yaz "HATA" ($sorun -join " | ")
exit 1
