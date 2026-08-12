# FinancialOS — kapalı beta Windows görevleri (BUG #290 / B4)
#
# GUNCELLEMELER
# -------------
# BUG #303 fix (12 Ağu 2026): üç görev de artık `gizli_calistir.vbs` üzerinden koşar.
#   Görev Zamanlayıcı, kullanıcının OTURUMUNDA koşan bir göreve konsol penceresi açar;
#   `-WindowStyle Hidden` pencereyi ancak AÇILDIKTAN SONRA gizler, yani ekranda siyah
#   kutu çakar. Sağlık kontrolü 10 dakikada bir koştuğu için kullanıcı bunu günde ~100
#   kez görüyordu. Sıklığı azaltmak yanlış çözümdü: pencere rahatsızlığı ölçümün
#   BEDELİ değil, YAN ETKİSİYDİ — ölçümü seyrekleştirmek düşen tüneli daha uzun süre
#   düşük bırakırdı (kanıt: saglik.log 12 Ağu 08:52 "funnel kapali — yeniden kuruluyor").
#   Yan etki kaldırıldı, ölçüm sıklığı KORUNDU.
#
# Üç görev kurar:
#   1. FinancialOS-Baslat   — oturum açılışında uygulamayı başlatır
#   2. FinancialOS-Saglik   — 10 dakikada bir uygulama+tünel+dış yolu ölçer, düşeni onarır
#   3. FinancialOS-Yedek    — her gün 03:15'te veritabanı yedeği alır
#
# YÖNETİCİ YETKİSİ GEREKMEZ ve ŞİFRE SAKLANMAZ: görevler "oturum açıldığında" tetiklenir
# ve kullanıcının kendi oturumunda koşar. "Kullanıcı oturum açmasa da çalıştır" seçeneği
# Windows'ta parola saklamayı gerektirir — bu kurulumda BİLİNÇLİ OLARAK KULLANILMIYOR
# (bir sırrı görev zamanlayıcıya yazmak, kazandırdığı rahatlıktan pahalıdır).
#
# SONUCU (yazılı olsun): bilgisayar açılıp OTURUM AÇILDIĞINDA uygulama döner. Oturum
# açılmadan (kilit ekranında) dönmez.
param(
    [switch]$Kaldir,
    [switch]$Durum
)

$ErrorActionPreference = "Stop"
$KOK = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$BASLAT = Join-Path $PSScriptRoot "baslat.ps1"
$SAGLIK = Join-Path $PSScriptRoot "saglik.ps1"
$PY = Join-Path $KOK "venv\Scripts\python.exe"

$GOREVLER = @("FinancialOS-Baslat", "FinancialOS-Saglik", "FinancialOS-Yedek")

if ($Durum) {
    foreach ($g in $GOREVLER) {
        $t = Get-ScheduledTask -TaskName $g -ErrorAction SilentlyContinue
        if ($t) {
            $b = Get-ScheduledTaskInfo -TaskName $g
            "{0,-22} {1,-10} son: {2}  sonuc: {3}" -f $g, $t.State, $b.LastRunTime, $b.LastTaskResult
        } else { "{0,-22} YOK" -f $g }
    }
    exit 0
}

if ($Kaldir) {
    foreach ($g in $GOREVLER) {
        if (Get-ScheduledTask -TaskName $g -ErrorAction SilentlyContinue) {
            Unregister-ScheduledTask -TaskName $g -Confirm:$false
            "kaldirildi: $g"
        }
    }
    exit 0
}

if (-not (Test-Path $PY)) { Write-Error "venv python yok: $PY"; exit 1 }

$psExe = (Get-Command powershell.exe).Source
$ortak = @{ Force = $true }

# Pencere açmadan çalıştırma sarmalayıcısı (BUG #303). `//B` = toplu mod (hata kutusu
# çıkarmaz), `//Nologo` = banner yok. Asıl komut bunun ARDINDAN argüman olarak gelir.
$VBS = Join-Path $PSScriptRoot "gizli_calistir.vbs"
if (-not (Test-Path $VBS)) { Write-Error "gizli calistirici yok: $VBS"; exit 1 }
$wscript = (Get-Command wscript.exe).Source

function GizliAksiyon {
    param([string]$Program, [string[]]$Argumanlar)
    # Her argüman VBS'e AYRI ve tırnaklı gider; boşluklu yollar bozulmaz.
    $parcalar = @("//B", "//Nologo", "`"$VBS`"", "`"$Program`"")
    foreach ($a in $Argumanlar) { $parcalar += "`"$a`"" }
    New-ScheduledTaskAction -Execute $wscript -Argument ($parcalar -join " ") -WorkingDirectory $KOK
}

# ── 1. Oturum açılışında başlat ────────────────────────────────────────────
# Gecikme: Tailscale servisinin ayağa kalkması ve ağın hazır olması için. Uygulama
# tünelden ÖNCE açılırsa sorun olmaz (tünel yerel porta bağlanır) ama ağ hazır değilken
# açılış fail-fast'i gereksiz yere gürültü üretebilir.
Register-ScheduledTask -TaskName "FinancialOS-Baslat" @ortak `
    -Description "Kapali beta: oturum acilisinda FinancialOS'u baslatir (BUG #290)" `
    -Trigger (New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME) `
    -Action (GizliAksiyon -Program $psExe `
        -Argumanlar @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $BASLAT)) `
    -Settings (New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 10)) | Out-Null
"kuruldu: FinancialOS-Baslat (oturum acilisinda)"

# ── 2. Sağlık kontrolü — 10 dakikada bir ───────────────────────────────────
# İKİ TETİKLEYİCİ — BUG #290 ikinci tur:
#   (a) OTURUM AÇILIŞINDA: yalnız zaman tetiği kullanılırsa, tetiğin başlangıcı GEÇMİŞTE
#       kaldığı için makine yeniden başladığında tekrar kurulumu güvenilir DEĞİLDİR.
#       Sonucu sinsi olurdu: başlatma görevi çalışır, sağlık kontrolü sessizce ölür ve
#       "izleme var" sanılırken hiçbir şey izlenmez.
#   (b) 10 DAKİKALIK TEKRAR: oturum boyunca sürekli ölçüm.
$saglikTetikler = @(
    (New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME),
    (New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) `
        -RepetitionInterval (New-TimeSpan -Minutes 10))
)
Register-ScheduledTask -TaskName "FinancialOS-Saglik" @ortak `
    -Description "Kapali beta: uygulama+tunel+dis yol saglik kontrolu, duseni onarir (BUG #290)" `
    -Trigger $saglikTetikler `
    -Action (GizliAksiyon -Program $psExe `
        -Argumanlar @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $SAGLIK)) `
    -Settings (New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
        -MultipleInstances IgnoreNew) | Out-Null
"kuruldu: FinancialOS-Saglik (10 dakikada bir)"

# ── 3. Günlük yedek ────────────────────────────────────────────────────────
# 03:15 seçildi: fiyat cron'u 02:45, gece batch 03:00 — yedek onlardan SONRA alınır ki
# günün işlenmiş hâlini içersin.
Register-ScheduledTask -TaskName "FinancialOS-Yedek" @ortak `
    -Description "Kapali beta: gunluk veritabani yedegi (data/backups)" `
    -Trigger (New-ScheduledTaskTrigger -Daily -At "03:15") `
    -Action (GizliAksiyon -Program $PY -Argumanlar @("-m", "scripts.backup")) `
    -Settings (New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 15)) | Out-Null
"kuruldu: FinancialOS-Yedek (her gun 03:15)"

""
"Durum icin:  .\deploy\windows\gorevleri_kur.ps1 -Durum"
"Kaldirmak:   .\deploy\windows\gorevleri_kur.ps1 -Kaldir"
