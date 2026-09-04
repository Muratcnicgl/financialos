#!/usr/bin/env pwsh
# FinancialOS — canlı betayı ÇALIŞAN sürümden HEDEF sürüme getirir (Wave-Y / Y1, BUG #339)
#
# NEDEN VAR — ÖLÇÜLEN OLAY (4 Eylül 2026)
# ---------------------------------------
# Canlı beta 24 commit geride koşuyordu: `/api/meta` build `aed4b5fa`, yerel HEAD
# `fce47532`. 4 Eylül'de kapatılan 21 defektin HİÇBİRİ kullanıcılarda yoktu.
#
# İki kök neden ölçüldü:
#   1. `app/version.py:71` sürüm damgasını `@lru_cache(maxsize=1)` ile tutuyor — damga
#      SÜREÇ BAŞLANGICINDA donuyor. Çalışma ağacı güncellense bile süreç eski kodu
#      bellekte taşır; `/api/meta` doğruyu söyler, yalan söyleyen kod değil SÜREÇTİR.
#   2. `baslat.ps1` idempotenttir ve haklı olarak öyledir (sağlık görevi onu 10 dakikada
#      bir çağırıyor): port dinleniyorsa "dokunulmadi" der. Ama bu, **bir kod
#      güncellemesinin canlıya HİÇ ULAŞMAMASI** demektir — kimse `-Zorla` çağırmıyordu.
#
# Yani mekanizma vardı (`baslat.ps1 -Zorla` durdurur, yedekler, göç uygular, sağlık ölçer);
# eksik olan onu ÇAĞIRAN ve sonucu DOĞRULAYAN adımdı. `scripts/deploy.sh` bu işi yapar
# ama **Docker yolu için** (`docker compose -f docker-compose.prod.yml`) ve bu makinede
# Docker kullanılmıyor. BUG #326'nın aynı sınıfı: bir adımın başka bir yolda olması,
# KULLANILAN yolda olduğu anlamına gelmez (L64).
#
# KULLANIM-GATE: bu betik "başlattım" demez. Başlattıktan sonra `/api/meta`yı OKUR ve
# damganın hedef SHA'ya eşit olduğunu ölçer. Eşit değilse BAŞARISIZ sayar — çünkü
# çalıştığını sanmak, çalıştırmak değildir.
#
#   .\deploy\windows\guncelle.ps1              # gerekiyorsa günceller
#   .\deploy\windows\guncelle.ps1 -KuruKosum   # yalnız ölçer, hiçbir şey yapmaz
param(
    [switch]$KuruKosum,
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$KOK = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$LOGDIZIN = Join-Path $KOK "logs"

function Yaz($mesaj) {
    $satir = "{0} [guncelle] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $mesaj
    Write-Output $satir
    if (Test-Path $LOGDIZIN) {
        Add-Content -Path (Join-Path $LOGDIZIN "servis.log") -Value $satir -Encoding UTF8
    }
}

function CanliDamga($port) {
    # Damga BOŞ da dönebilir (git yok / bozuk repo — `version.py` sessizce env'e düşer).
    # Boşu "eşit" saymak, güncellemeyi sessizce atlamak olurdu; ayrı bir değer döndürülür.
    try {
        $r = Invoke-WebRequest "http://127.0.0.1:$port/api/meta" -UseBasicParsing -TimeoutSec 8
        $m = ($r.Content | ConvertFrom-Json).build
        if ([string]::IsNullOrWhiteSpace($m)) { return "(bos)" }
        return $m
    } catch { return "(ulasilamadi)" }
}

# --- 1) ÖLÇ: hedef ne, canlıda ne var -----------------------------------------------
Push-Location $KOK
try {
    $hedef = (& git rev-parse HEAD).Substring(0, 12)
    $kirli = (& git status --porcelain)
} finally { Pop-Location }

if ($kirli) {
    # Kirli ağaçtan deploy, hangi kodun canlıda olduğunu ÖLÇÜLEMEZ kılar; damga `+` alır
    # ama `+` neyin eklendiğini söylemez. Bu, sürüm damgasının varlık sebebini yok eder.
    Yaz "REDDEDILDI: calisma agaci kirli — once commit et (damga olculemez olurdu)"
    Yaz "  kirli dosyalar:"
    $kirli -split "`n" | Select-Object -First 8 | ForEach-Object { Yaz "  | $_" }
    exit 2
}

$canli = CanliDamga $Port
Yaz "canli=$canli  hedef=$hedef"

# --- 1b) ARAYUZ DERLEMESI (BUG #353) ------------------------------------------------
# OLCULEN OLAY (5 Eylul 2026): bu betik BACKEND'i guncelliyordu, arayuzu HIC derlemiyordu.
# `frontend/dist` 2 Eylul 18:05'ten kalmaydi ve o tarihten beri `frontend/src` 9 commit
# almisti — #318 erken kapama, #319 nakit takvimi, #320 bekleyen nakit, #330/#331 kart,
# #332 "hesabi o an belli olur" secenegi. Yani bu duzeltmelerin BACKEND yarisi canlida,
# ARAYUZ yarisi degildi. Bir duzeltmeyi ikiye bolmek, hic yapmamaktan daha yaniltici:
# urun "duzeldi" diye kaydedilir, kullanici eski ekrani gormeye devam eder (L64).
#
# `dist/` gitignore'da (bilincli — derleme ciktisi depoya girmez), dolayisiyla onu
# URETMEK dagitimin isidir. Yeniden baslatma GEREKMEZ: `app/spa.py` StaticFiles +
# FileResponse kullanir, yani diski HER ISTEKTE okur (olculdu).
$fKaynak = (git log -1 --format=%H -- frontend/src frontend/package.json frontend/vite.config.js frontend/index.html).Trim()
$distDizin = Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) "frontend/dist"
$damgaDosya = Join-Path $distDizin ".kaynak-damgasi"
$distIndex = Join-Path $distDizin "index.html"
$fMevcut = ""
if (Test-Path $damgaDosya) { $fMevcut = (Get-Content $damgaDosya -Raw).Trim() }

$arayuzBayat = (-not (Test-Path $distIndex)) -or ($fMevcut -ne $fKaynak)
if ($arayuzBayat) {
    if ($KuruKosum) {
        Yaz "KURU KOSUM: arayuz BAYAT (dist damgasi '$fMevcut' != kaynak '$fKaynak')"
    } else {
        Yaz "arayuz bayat — derleniyor (npm run build)"
        $fLog = Join-Path $LOGDIZIN "guncelle-build.out"
        $fe = Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) "frontend"
        $n = Start-Process -FilePath "cmd" -ArgumentList @("/c", "npm", "run", "build") `
             -WorkingDirectory $fe -PassThru -WindowStyle Hidden `
             -RedirectStandardOutput $fLog -RedirectStandardError "$fLog.err"
        Wait-Process -Id $n.Id -Timeout 600
        if ($n.ExitCode -ne 0) {
            Yaz "BASARISIZ: arayuz derlemesi cikis $($n.ExitCode) verdi — bkz. $fLog.err"
            exit 3
        }
        # KULLANIM-GATE'in arayuz ayagi: derleme "kostu" demek yetmez, CIKTI olculur.
        if (-not (Test-Path $distIndex)) {
            Yaz "BASARISIZ: derleme 0 dondu ama dist/index.html YOK"
            exit 3
        }
        Set-Content -Path $damgaDosya -Value $fKaynak -Encoding utf8
        Yaz "arayuz derlendi — damga $fKaynak"
    }
} else {
    Yaz "arayuz guncel (damga $fKaynak)"
}

if ($canli -eq $hedef) {
    Yaz "GUNCEL — backend icin yapilacak bir sey yok"
    exit 0
}

if ($KuruKosum) {
    Yaz "KURU KOSUM: guncelleme GEREKIYOR ama uygulanmadi"
    exit 10
}

# --- 2) UYGULA: tek kaynak `baslat.ps1 -Zorla` --------------------------------------
# Yedek + göç + sağlık ölçümü ORADA yazılı (BUG #326). Buraya kopyalamak, aynı kararı
# iki yerde tutmak olurdu — bir sonraki düzeltme birini güncelleyip diğerini unuturdu.
Yaz "guncelleniyor: baslat.ps1 -Zorla (yedek + goc + saglik onun icinde)"

# BUG #341 — ÇIKIŞ KODU OKUNAMAYAN DEPLOY BETİĞİ YARIM ARAÇTIR.
#
# Ölçülen: `guncelle.ps1 | tail` çağrısı betik 9 saniyede bittiği hâlde 2 dakika boyunca
# dönmedi. Sebep boru: `baslat.ps1` uvicorn'u `Start-Process` ile açıyor ve TORUN SÜREÇ
# çağıranın stdout tanıtıcısını miras alıyor — uvicorn günlerce yaşadığı için boru asla
# kapanmıyor ve çağıran taraf çıkış kodunu HİÇ göremiyor. (Ölçümle elendi: `-KuruKosum`,
# yani `Start-Process` çalışmayan yol, boruyu 0,3 saniyede kapatıyor.)
#
# Çözüm torunu boruya HİÇ SOKMAMAK: `baslat.ps1` ayrı bir PowerShell sürecinde, std
# tanıtıcıları DOSYAYA bağlanmış olarak koşar. Miras alınan tanıtıcı artık bir dosyadır;
# bizim borumuz serbest kalır. Çıkış kodu `-Wait -PassThru` ile okunur.
$bLog = Join-Path $LOGDIZIN "guncelle-baslat.out"
$bHata = Join-Path $LOGDIZIN "guncelle-baslat.err"
$b = Start-Process -FilePath "powershell" -ArgumentList @(
        "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
        # Yol BOŞLUK içeriyor (kullanıcı dizini "Ad Soyad"). `Start-Process -ArgumentList`
        # dizi elemanlarını TIRNAKLAMAZ: tırnaksız verilince `-File` argümanı bölünüyor,
        # PowerShell etkileşimli açılıyor, banner basıyor ve -196608 ile düşüyor (ölçüldü).
        "-File", ('"' + (Join-Path $PSScriptRoot "baslat.ps1") + '"'), "-Zorla", "-Port", "$Port"
    ) -PassThru -WindowStyle Hidden `
      -RedirectStandardOutput $bLog -RedirectStandardError $bHata

# `-Wait` KULLANILMAZ (ölçüldü): `-Wait`, .NET tarafında yönlendirilmiş AKIŞLARIN
# kapanmasını da bekler; uvicorn o dosya tanıtıcılarını miras aldığı için akışlar
# uvicorn ölene kadar kapanmaz ve çağrı sonsuza dek asılır. `Wait-Process` ise
# işletim sistemi SÜREÇ tanıtıcısını bekler — akışlardan etkilenmez.
try { $b | Wait-Process -Timeout 180 -ErrorAction Stop }
catch { Yaz "BASARISIZ: baslat.ps1 180 sn icinde bitmedi"; exit 1 }

if (Test-Path $bLog) { Get-Content $bLog | ForEach-Object { if ($_) { Write-Output "  | $_" } } }
if ($b.ExitCode -ne 0) {
    Yaz "BASARISIZ: baslat.ps1 cikis $($b.ExitCode) — ayrinti: $bLog / $bHata"
    exit 1
}

# --- 3) DOĞRULA: gerçekten hedef sürüm mü koşuyor ------------------------------------
# Sağlık 200 vermesi YETMEZ: eski süreç de 200 veriyordu. Ölçülecek şey DAMGA.
$sonuc = "(olculmedi)"
for ($i = 0; $i -lt 10; $i++) {
    Start-Sleep -Seconds 2
    $sonuc = CanliDamga $Port
    if ($sonuc -eq $hedef) { break }
}

if ($sonuc -ne $hedef) {
    Yaz "DOGRULAMA BASARISIZ: canli damga '$sonuc', hedef '$hedef' — surum ULASMADI"
    exit 1
}

Yaz "TAMAM: canli damga $sonuc = hedef $hedef"
exit 0
