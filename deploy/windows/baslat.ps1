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

# BUG #326 — GÖÇÜ UYGULAYAN ADIM BU YOLDA YOKTU.
#
# Ölçülen olay (4 Eylül 2026): kapalı beta SABAHTAN BERİ KAPALIYDI. `app/schema_guard.py`
# doğru davrandı ve uygulamayı açmayı reddetti (DB e7f8a9b0c1d2, kod f8a9b0c1d2e3 —
# BUG #318'in göçü canlı DB'ye hiç uygulanmamıştı). Sağlık görevi 10 dakikada bir yeniden
# denedi ve her seferinde aynı hatayla düştü; arıza yalnız servis.log'a yazıldı.
#
# Adım YANLIŞ YOLLARDAYDI: `deploy/financialos.service` (systemd) ve `scripts/deploy.sh`
# (Docker) göçü uyguluyordu — ama ikisi de KULLANILMIYOR. Betanın gerçekte koştuğu yol
# burasıydı ve burada adım yoktu. (L64'ün sınıfı: bir adımın başka bir yolda olması,
# kullanılan yolda olduğu anlamına gelmez.)
#
# SIRA BİLİNÇLİ: önce ÖLÇ, gerekiyorsa YEDEKLE, sonra UYGULA. Her başlatmada yedek almak
# (sağlık görevi bunu 10 dakikada bir çağırıyor) diski gereksiz doldururdu; yedek yalnız
# gerçekten göç uygulanacakken alınır. SQLite'ta `batch_alter_table` tabloyu YENİDEN
# KURAR — yedeksiz göç, canlı beta verisini tek bir migration'a emanet etmektir.
& $PY -m scripts.goc_durumu
$gocDurumu = $LASTEXITCODE
if ($gocDurumu -eq 10) {
    Yaz "goc bekliyor — once yedek, sonra alembic upgrade head"
    & $PY -m scripts.backup
    if ($LASTEXITCODE -ne 0) { Yaz "GOC BASARISIZ: yedek alinamadi, goc KOSULMADI"; exit 1 }
    & $PY -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { Yaz "GOC BASARISIZ: alembic upgrade head dustu"; exit 1 }
    Yaz "goc uygulandi"
} elseif ($gocDurumu -ne 0) {
    # Bilinmeyen, "guncel" DEĞİLDİR (L45). Yarım göçle açılan uygulama, eksik kolonu
    # okuyan her uçta 500 verir — kapalı olmaktan DAHA KÖTÜ (bu dosyanın kendi gerekçesi).
    Yaz "GOC BASARISIZ: goc durumu OLCULEMEDI (cikis $gocDurumu) — baslatilmiyor"
    exit 1
}

Yaz "baslatiliyor (port $Port)"
# SEC-027 yan ayagi (5 Eyl 2026): `--no-server-header`.
# Olculdu: canli yanit disariya `Server: uvicorn` yayinliyordu ve `scripts/live_gate.py`
# bunu zaten UYARI olarak basiyordu ("sunucu surumu gizli" kontrolu) — yani kapi soyluyordu,
# kimse okumamisti. Sunucu yiginini ilan etmek saldirgana eslesme kolayligi verir,
# kullaniciya hicbir sey. Bu bayrak uvicorn'un protokol katmaninda basligi HIC eklememesini
# saglar; ASGI ara katmani bunu YAPAMAZ (baslik uvicorn tarafindan sonradan eklenir).
$p = Start-Process -FilePath $PY `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$Port", "--no-server-header" `
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
