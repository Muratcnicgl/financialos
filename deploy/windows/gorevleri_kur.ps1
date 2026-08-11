# FinancialOS — kapalı beta Windows görevleri (BUG #290 / B4)
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

# ── 1. Oturum açılışında başlat ────────────────────────────────────────────
# Gecikme: Tailscale servisinin ayağa kalkması ve ağın hazır olması için. Uygulama
# tünelden ÖNCE açılırsa sorun olmaz (tünel yerel porta bağlanır) ama ağ hazır değilken
# açılış fail-fast'i gereksiz yere gürültü üretebilir.
Register-ScheduledTask -TaskName "FinancialOS-Baslat" @ortak `
    -Description "Kapali beta: oturum acilisinda FinancialOS'u baslatir (BUG #290)" `
    -Trigger (New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME) `
    -Action (New-ScheduledTaskAction -Execute $psExe `
        -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$BASLAT`"" `
        -WorkingDirectory $KOK) `
    -Settings (New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 10)) | Out-Null
"kuruldu: FinancialOS-Baslat (oturum acilisinda)"

# ── 2. Sağlık kontrolü — 10 dakikada bir ───────────────────────────────────
$saglikTetik = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) `
    -RepetitionInterval (New-TimeSpan -Minutes 10)
Register-ScheduledTask -TaskName "FinancialOS-Saglik" @ortak `
    -Description "Kapali beta: uygulama+tunel+dis yol saglik kontrolu, duseni onarir (BUG #290)" `
    -Trigger $saglikTetik `
    -Action (New-ScheduledTaskAction -Execute $psExe `
        -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$SAGLIK`"" `
        -WorkingDirectory $KOK) `
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
    -Action (New-ScheduledTaskAction -Execute $PY -Argument "-m scripts.backup" -WorkingDirectory $KOK) `
    -Settings (New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 15)) | Out-Null
"kuruldu: FinancialOS-Yedek (her gun 03:15)"

""
"Durum icin:  .\deploy\windows\gorevleri_kur.ps1 -Durum"
"Kaldirmak:   .\deploy\windows\gorevleri_kur.ps1 -Kaldir"
