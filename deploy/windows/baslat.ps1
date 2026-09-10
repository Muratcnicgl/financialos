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

# ── BUG #368 — BETİK, ÇAĞIRANIN ÇALIŞMA DİZİNİNE BAĞIMLIYDI ──────────────────
#
# Aşağıdaki üç ölçüm komutu (`& $PY -m scripts.goc_durumu`, `-m scripts.backup`,
# `-m alembic`) modülü ÇALIŞMA DİZİNİNDEN çözer. Betik depo kökü dışından
# çağrıldığında sonuç şu:
#
#   ModuleNotFoundError: No module named 'scripts'
#   [baslat] GOC BASARISIZ: goc durumu OLCULEMEDI (cikis 1) - baslatilmiyor
#
# Yani uygulama HİÇ AÇILMAZ — ve mesaj "göç ölçülemedi" der, "yanlış dizindeyim"
# demez; arıza kendini bir VERİTABANI sorunu gibi gösterir. `logs/servis.log` bu
# satırın canlıda iki kez düştüğünü zaten yazıyor (2026-09-10 15:47:15 ve 15:48:26).
#
# Zamanlanmış görev bunu tesadüfen örtüyordu: `gorevleri_kur.ps1`, aksiyona
# `-WorkingDirectory $KOK` veriyor ve `gizli_calistir.vbs`in `WScript.Shell.Run`u
# o dizini çocuğa devrediyor. Yani yol GÖREVDEN geçerken çalışıyor, ELDEN
# çağrıldığında çalışmıyordu — bir adımın bir yolda olması, kullanılan HER yolda
# olduğu anlamına gelmez (BUG #326'nın dersi, bu kez ters yönden).
#
# Betiğin kendisi yazarının bunu bildiğini gösteriyor: uvicorn `Start-Process`'e
# `-WorkingDirectory $KOK` AÇIKÇA veriliyor. Eksik olan, ölçüm komutlarının aynı
# güvenceye sahip olmamasıydı. Tek satır, tüm çağrı yollarını eşitler.
Set-Location $KOK

$PY = Join-Path $KOK "venv\Scripts\python.exe"
# BUG #303'un ikinci ayagi (10 Eyl 2026): uvicorn `python.exe` + `-WindowStyle Hidden`
# ile aciliyordu. `gizli_calistir.vbs`in kendi belgesi bunun NEDEN yetmedigini yaziyor:
# `-WindowStyle Hidden` pencereyi ancak ACILDIKTAN SONRA gizler, yani ekranda bir an
# siyah kutu cakar. Sarmalayici gorevin KENDISINI gizlemisti; icerideki uvicorn
# baslatmasi disarida kalmisti.
#
# `pythonw.exe` GUI alt sistemine baglidir ve konsolu HIC yaratmaz. Ciktilar zaten
# dosyaya yonlendiriliyor (asagida -RedirectStandardOutput/Error), yani konsolsuz
# calismak hicbir bilgiyi kaybettirmez.
#
# AYRI DEGISKEN — bilerek (ilk denemede olculdu): `$PY` ayni zamanda GOC DURUMUNU ve
# yedegi OLCEN komutlarda kullaniliyor (`& $PY -m scripts.goc_durumu`). pythonw konsola
# baglanmadigi icin o cagrilar cikis kodu/cikti URETMEDI; betik "goc durumu OLCULEMEDI"
# deyip uygulamayi hic baslatmadi. Yani tek degiskeni degistirmek, pencereyi gizlerken
# uygulamayi kapatiyordu. Olcen komutlar `$PY`, YALNIZ sunucu baslatma `$PYW` kullanir.
$PYW = Join-Path $KOK "venv\Scripts\pythonw.exe"
if (-not (Test-Path $PYW)) { $PYW = $PY }
$LOGDIZIN = Join-Path $KOK "logs"
$LOG = Join-Path $LOGDIZIN "uvicorn.out.log"
$HATA = Join-Path $LOGDIZIN "uvicorn.err.log"

function Yaz($mesaj) {
    $satir = "{0} [baslat] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $mesaj
    Write-Output $satir
    if (Test-Path $LOGDIZIN) { Add-Content -Path (Join-Path $LOGDIZIN "servis.log") -Value $satir -Encoding UTF8 }
}

function Saglikli() {
    # Portu DEĞİL, uygulamayı ölçer: port açık olup uygulama 500 veriyor olabilir.
    try {
        $r = Invoke-WebRequest "http://127.0.0.1:$Port/api/health" -UseBasicParsing -TimeoutSec 5
        return ($r.StatusCode -eq 200)
    } catch { return $false }
}

if (-not (Test-Path $PY)) { Yaz "HATA: venv python yok: $PY"; exit 1 }
if (-not (Test-Path $LOGDIZIN)) { New-Item -ItemType Directory -Path $LOGDIZIN | Out-Null }

# ── BUG #367 — "İDEMPOTENT" YAZIYORDU, DEĞİLDİ ───────────────────────────────
#
# Yukarıdaki satır 9 bu betiğin idempotent olduğunu SÖYLÜYOR; kod ise yalnızca
# BAK-SONRA-YAP (check-then-act) yapıyordu: port kontrolü ile `Start-Process` arasında
# göç ölçümü, yedek ve `alembic upgrade head` var — saniyeler süren bir pencere. İki
# süreç o pencereye birlikte girerse İKİSİ DE portu boş görür, İKİSİ DE uvicorn açar.
#
# Bunun teorik olmadığı ÖLÇÜLDÜ — `logs/servis.log`, üç ayrı oturum açılışı:
#   2026-09-07 09:36:20  "baslatiliyor" ×2  →  "AYAKTA" ×2  (PID 17244 ve 17280)
#   2026-09-09 15:52:03  "baslatiliyor" ×2  →  "AYAKTA" ×2  (PID 17688 ve 7632)
#   2026-09-10 23:38:46  "baslatiliyor" ×2  →  "AYAKTA" ×1  (PID 20664)
#
# İlk iki satır ÇİFT YEŞİL: tek bir portu iki sürecin birden sahiplenmesi mümkün
# değildir, yani o iki koşumdan biri portu ALAMADI ve buna rağmen "AYAKTA" yazdı.
# Sebep aşağıdaki sağlık kontrolüydü: `/api/health`'e soruyor ama cevabı KİMİN verdiğini
# sormuyordu — kaybeden süreç, kazananın açtığı uygulamayı ölçüp kendini başarılı sandı.
# Üçüncü satırda kaybeden hiç konuşamadı; izi Görev Zamanlayıcı'da kaldı
# (FinancialOS-Baslat, LastTaskResult = 1).
#
# KAYNAK İKİ GÖREVİN AYNI ANDA TETİKLENMESİ: `FinancialOS-Baslat` (AtLogOn) ve
# `FinancialOS-Saglik` (AtLogOn + 10 dk) — ikincisi düşeni onarmak için bu betiği
# çağırır. Görevlerin `-MultipleInstances IgnoreNew` ayarı bir görevi KENDİSİYLE
# yarışmaktan korur, İKİ FARKLI GÖREVDEN korumaz.
#
# ÇÖZÜM TETİKLEYİCİ SİLMEK DEĞİL: `gorevleri_kur.ps1` her iki tetikleyicinin de neden
# gerekli olduğunu gerekçesiyle yazıyor (yalnız zaman tetiği yeniden başlatmada
# güvenilir değil). Deponun tekrarlayan dersi: bir kapıya doğru cevap tavanı yükseltmek
# değil, İHTİYACI ORTADAN KALDIRMAKTIR — betiğin kendisi eşzamanlılığa dayanıklı olur.
#
# ADLANDIRILMIŞ MUTEX, işletim sisteminin bu iş için verdiği ilkel araçtır: kritik bölüm
# gerçekten tektir, üstelik süreç çökse bile çekirdek kilidi bırakır (aşağıdaki
# `AbandonedMutexException` dalı tam da o durumu devralır — terk edilmiş kilit,
# sonsuza kadar kapalı bir kapı DEĞİLDİR).
#
# `Local\` bilinçli, `Global\` değil: her iki görev de aynı kullanıcının aynı oturumunda
# koşar (ölçüldü: Principal.UserId ikisinde de aynı) ve `Global\` ad alanında nesne
# yaratmak `SeCreateGlobalPrivilege` ister — yönetici olmayan bir görevde bu, kilidi
# korumak yerine betiği düşürürdü. Ad PORTU İÇERİR: `-Port 8001` ile ikinci bir örnek
# açmak meşrudur ve onu beklememelidir.
#
# Ölçüldü (aynı anda başlatılan iki PowerShell): ikincisi birincinin bırakmasını
# 3 sn bekledi ve 25 ms sonra kilidi aldı; `Local\` için yönetici hakkı gerekmedi.
$mutexAdi = "Local\FinancialOS-Baslat-$Port"
$mutex = New-Object System.Threading.Mutex($false, $mutexAdi)
$kilitBende = $false
try {
    # BUG #371 — BEKLEME SÜRESİ, ÇAĞIRANIN BÜTÇESİNE GÖRE SEÇİLİR.
    #
    # İlk yazımda 180 sn'ydi ve gerekçesi "kritik bölümün en uzun hâli" idi. O gerekçe bu
    # betiğe TEK BAŞINA bakıyordu; oysa bir ÇAĞIRANI var ve bütçesi daha dar:
    #     deploy/windows/guncelle.ps1 →  $b | Wait-Process -Timeout 180
    # Yani 180'de vazgeçip dağıtımı BAŞARISIZ sayıyor. Kendi bütçemi de 180 koymak,
    # en kötü hâlde toplamı 220-230 sn'ye çıkarıyordu (180 kilit + ~10 göç + 40 sağlık).
    #
    # Bu ortalama koşumda GÖRÜNMEZ — kilidi tutan taraf, uygulama ayaktayken saniyeler
    # içinde "zaten calisiyor" deyip çıkar. Görünür olduğu an tam da onarım anıdır:
    # `FinancialOS-Saglik` uygulamayı AÇARKEN `guncelle.ps1` koşarsa dağıtım zaman
    # aşımına düşerdi. Yani en kötü günde ortaya çıkacak sınıftan bir hata.
    #
    # 90 sn ARİTMETİKLE seçildi:   90 + ~10 + 40 = 140 sn  <  180 sn   (40 sn pay kalır)
    # ve hâlâ her gerçek kritik bölümden kat kat uzundur: kilidi tutan taraf ya saniyeler
    # içinde çıkar ya da uygulamayı açıp 40 sn'lik sağlık bekleyişini bitirir.
    # Diğer tavanlar bağlayıcı değil (Saglik ExecutionTimeLimit 5 dk, Baslat 10 dk).
    #
    # Ders: bir zaman aşımı tek taraflı bir karar değil, İKİ TARAFLI BİR SÖZLEŞMEDİR —
    # "en uzun iş ne kadar sürer" kadar "onu kim, ne kadar bekliyor" da sabitin parçasıdır.
    $kilitBende = $mutex.WaitOne([TimeSpan]::FromSeconds(90))
} catch [System.Threading.AbandonedMutexException] {
    # Kilidi tutan süreç bırakmadan öldü. Kilit BİZE geçti (WaitOne bunu istisnayla
    # bildirir ama sahipliği verir). Uygulama yarım kalmış olabilir; aşağıdaki port ve
    # sağlık ölçümü zaten gerçeği söyleyecek.
    Yaz "onceki baslatma yarida kalmis (terk edilmis kilit) — devraliniyor"
    $kilitBende = $true
}

if (-not $kilitBende) {
    # 90 sn boyunca kilit alınamadı. Bu, "başlat" işinin YAPILMADIĞI anlamına GELMEZ —
    # tam tersine, başka bir örnek onu hâlâ yapıyor. Doğru cevap ikinci bir uvicorn
    # açmak değil, SONUCU ÖLÇMEK (L45: bilinmeyen sıfır değildir, ama ölçülebilir).
    if (Saglikli) {
        Yaz "baska bir ornek baslatti — uygulama AYAKTA, dokunulmadi"
        $mutex.Dispose()
        exit 0
    }
    Yaz "BASLATILAMADI: baska bir baslatma 90 sn'dir surüyor ve uygulama hala cevap vermiyor"
    $mutex.Dispose()
    exit 1
}

try {
    # ── KRİTİK BÖLÜM ────────────────────────────────────────────────────────
    # Port kontrolü BURADA, kilidin İÇİNDE. Kilit dışında yapılsaydı BUG #367'nin
    # kendisi geri gelirdi: bekleyen süreç, beklerken bayatlamış bir ölçüme dayanır.
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
    $p = Start-Process -FilePath $PYW `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$Port", "--no-server-header" `
        -WorkingDirectory $KOK -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $LOG -RedirectStandardError $HATA

    # Açılış fail-fast'i (SECRET_KEY, şema sürümü, kapasite) saniyeler sürebilir — hemen
    # "başladı" demek yalan olur. Gerçekten cevap verdiğini ÖLÇÜYORUZ.
    $basarili = $false
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Seconds 2
        if (Saglikli) { $basarili = $true; break }
    }

    # BUG #367'nin ikinci yüzü — SAĞLIK CEVABI, BİZİM BAŞLATTIĞIMIZIN KANITI DEĞİLDİR.
    # `/api/health` 200 dönmesi "port 8000'de sağlıklı bir uygulama var" demektir; "onu
    # BEN açtım" demek değil. 7 ve 9 Eylül'deki çift yeşilin tam mekanizması buydu.
    # Kilit artık o yarışı önlüyor, ama başka bir süreç (elle açılmış bir uvicorn, eski
    # bir örnek) portu tutuyor olabilir — o zaman da doğru cümle "AYAKTA (PID …)" değil.
    # Kendi sürecimizin ÖLDÜĞÜNÜ görmek, tek başına ölçülebilir ve yanılmaz bir kanıttır.
    if ($basarili -and $p.HasExited) {
        Yaz "uygulama AYAKTA ama BU KOSUM ACMADI (baslattigimiz surec cikti, kod $($p.ExitCode)) — portu baska bir surec tutuyor"
        exit 0
    }
    if ($basarili) {
        Yaz "AYAKTA (PID $($p.Id))"
        exit 0
    }
    Yaz "BASLATILAMADI — son hatalar: $HATA"
    if (Test-Path $HATA) { Get-Content $HATA -Tail 5 | ForEach-Object { Yaz "  | $_" } }
    exit 1
} finally {
    # `exit`, `try` içinde de `finally`yi koşturur (ölçüldü: çıkış kodu da korunur).
    # Süreç çökse bile çekirdek kilidi bırakır; bu blok yalnız temiz yolu netleştirir.
    if ($kilitBende) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
