# FinancialOS — kapalı beta uygulamasını başlatır (BUG #290 / B4)
#
# NEDEN VAR: uygulama tünel arkasında kendi makinede koşuyor. Makine yeniden başladığında
# Tailscale SERVİS olduğu için kendiliğinden dönüyor, ama uvicorn DÖNMÜYORDU. Sonuç
# tamamen kapalı olmaktan DAHA KÖTÜ: adres çözülür, HTTPS çalışır, tünel açıktır — ama
# 127.0.0.1:8000'de kimse yoktur. Davetli hata alır, operatör "açık" sanır (ölçüldü:
# zamanlanmış görev YOK, başlangıç klasörü BOŞ).
#
# İDEMPOTENT: zaten çalışıyorsa HİÇBİR ŞEY yapmaz. Sağlık kontrolü bunu dakikada bir
# çağırdığı için ikinci bir uvicorn açmak, portu çakıştırıp ikisini de bozardı.
param(
    [switch]$Zorla,   # çalışıyor olsa bile yeniden başlat
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$KOK = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$PY = Join-Path $KOK "venv\Scripts\python.exe"
$LOGDIZIN = Join-Path $KOK "logs"
$LOG = Join-Path $LOGDIZIN "uvicorn.out.log"
$HATA = Join-Path $LOGDIZIN "uvicorn.err.log"

function Yaz($mesaj) {
    $satir = "{0} [baslat] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $mesaj
    Write-Output $satir
    if (Test-Path $LOGDIZIN) { Add-Content -Path (Join-Path $LOGDIZIN "servis.log") -Value $satir -Encoding UTF8 }
}

if (-not (Test-Path $PY)) { Yaz "HATA: venv python yok: $PY"; exit 1 }
if (-not (Test-Path $LOGDIZIN)) { New-Item -ItemType Directory -Path $LOGDIZIN | Out-Null }

$dinleyen = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($dinleyen -and -not $Zorla) {
    Yaz "zaten calisiyor (PID $($dinleyen[0].OwningProcess)) — dokunulmadi"
    exit 0
}
if ($dinleyen -and $Zorla) {
    Yaz "zorla yeniden baslatma: PID $($dinleyen[0].OwningProcess) durduruluyor"
    Stop-Process -Id $dinleyen[0].OwningProcess -Force
    Start-Sleep -Seconds 4
}

Yaz "baslatiliyor (port $Port)"
$p = Start-Process -FilePath $PY `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$Port" `
    -WorkingDirectory $KOK -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $LOG -RedirectStandardError $HATA

# Açılış fail-fast'i (SECRET_KEY, şema sürümü, kapasite) saniyeler sürebilir — hemen
# "başladı" demek yalan olur. Gerçekten cevap verdiğini ÖLÇÜYORUZ.
$basarili = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 2
    try {
        $r = Invoke-WebRequest "http://127.0.0.1:$Port/api/health" -UseBasicParsing -TimeoutSec 5
        if ($r.StatusCode -eq 200) { $basarili = $true; break }
    } catch { }
}

if ($basarili) {
    Yaz "AYAKTA (PID $($p.Id))"
    exit 0
}
Yaz "BASLATILAMADI — son hatalar: $HATA"
if (Test-Path $HATA) { Get-Content $HATA -Tail 5 | ForEach-Object { Yaz "  | $_" } }
exit 1
