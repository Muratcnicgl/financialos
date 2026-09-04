# WAVE-Y LEDGER — yayın hattı (uygulamayı rayına oturtma)

**Hat tanımı:** `masterprompt-wave-y.md` · **Çıpa:** `7486e9c` (4 Eylül 2026)
**Başlangıç ölçümü:** 4 Eylül 2026, 13:37

> Bu defter Wave-Y'nin tek doğruluk kaynağıdır. Her hedef kapanışı kanıtıyla buraya
> yazılır; kanıtı olmayan satır **KANIT YOK** kalır ve hedef açık sayılır.

---

## §0.1 BAŞLANGIÇ ÖLÇÜMÜ (Y8'de aynı komutlar tekrar koşulacak)

| Ölçüm | Değer | Komut |
|---|---|---|
| Yerel HEAD | `fce4753` (çıpadan +5) | `git log -1` |
| **Canlı build damgası** | **`aed4b5fad0e6`** | `curl /api/meta` |
| **Drift** | canlı ≠ yerel — üstelik canlıdaki SHA, geçmiş yeniden yazıldığı için artık **var olmayan** bir commit | — |
| Canlı sağlık | health 200 · ready 200 | `curl` |
| Canlı göç sürümü | `c3d4e5f8a1b2` | sqlite |
| Kullanıcı | 6 | sqlite |
| MCP defteri | **281 satır** (4 Eyl raporunda 255'ti) | `wc -l` |
| Süit | 3.504 passed · 18 skipped | `pytest -q` |
| Coverage | %94,02 (CI'da ≥93 kilitli) | `pytest --cov` |

---

## ✅ Y1 — CANLI SÜRÜM DRİFT'İ SIFIRLANDI (4 Eylül 2026, 13:48 · doğrulama 13:59)

> **Bir alt madde Murat'ta:** kimlikli duman testi (giriş + işlem okuma). Aşağıda
> KANIT YOK olarak işaretli; tek komutla kapanır. Y1 bu madde olmadan **tam** sayılmaz.

### Kök neden — ÖLÇÜLDÜ, ve iki tane

**Bu bir ihmal değil, mekanizma eksikliğiydi.** Betanın 24 commit geride kalması
"deploy etmeyi unutmak"tan gelmiyordu; deploy edecek bir adım YOKTU.

1. **`app/version.py:71` — damga süreç başında donuyor.** Sürüm damgası
   `@lru_cache(maxsize=1)` ile tutuluyor; `git rev-parse HEAD` süreç ömrü boyunca bir kez
   okunuyor. Çalışma ağacı güncellense bile süreç eski kodu bellekte taşır. Canlı süreç
   bugün 09:21:35'te başlamış, o an HEAD `aed4b5f`'ti. **`/api/meta` yalan söylemiyordu —
   yalan söyleyen kod değil SÜREÇTİ.**
2. **`deploy/windows/baslat.ps1:34` — çalışan süreci görünce çıkıyor.** Port dinleniyorsa
   *"zaten calisiyor — dokunulmadi"* der. İdempotent olması **doğrudur** (sağlık görevi onu
   10 dakikada bir çağırıyor; ikinci uvicorn portu çakıştırırdı). Ama kimse `-Zorla`
   çağırmadığı için **bir kod güncellemesi canlıya hiç ulaşmıyordu.**

### ⚠️ Y1'İN "DONE" KRİTERİ DEĞİŞTİ — ve neden değiştiği burada yazılı

Masterprompt Y1'de *"deploy **`scripts/deploy.sh` ile** yapıldı (elle değil)"* diyordu.
**Bu kriter bu ortamda karşılanamaz ve karşılanmaya çalışılması zarar verirdi.** Ölçüldü:

```
scripts/deploy.sh:9   COMPOSE="docker compose -f docker-compose.prod.yml --env-file .env.prod"
```

`deploy.sh` **Docker yolu için** yazılmış. Canlı beta bu makinede Docker'sız koşuyor
(uvicorn + Tailscale Funnel, `deploy/windows/baslat.ps1`). Yani raporun
*"deploy.sh koştu mu? KANIT YOK"* satırının dürüst cevabı **"koşamaz"**dır.

Bu, **BUG #326'nın aynı sınıfıdır** (L64): bir adımın başka bir yolda olması, KULLANILAN
yolda olduğu anlamına gelmez. #326'da eksik olan göç adımıydı ve beta 24,5 saat kapalı
kaldı; burada eksik olan güncelleme adımıdır ve beta 24 commit geride kaldı.

**Yeni kriter:** deploy `deploy/windows/guncelle.ps1` ile yapılır.
*(Kriter sessizce değiştirilmedi; değişiklik gerekçesiyle buraya yazıldı — yoksa altı ay
sonra "deploy.sh koştu mu?" sorusu yine cevapsız kalırdı.)*

### Yapılan — `deploy/windows/guncelle.ps1` (BUG #339)

* **Ölçer:** canlı `/api/meta` damgası ↔ yerel HEAD. Eşitse hiçbir şey yapmaz.
* **Kirli ağacı REDDEDER:** kirli kopyadan deploy, hangi kodun canlıda olduğunu
  ölçülemez kılar (damga `+` alır ama `+` neyin eklendiğini söylemez).
* **Tek kaynağı çağırır:** `baslat.ps1 -Zorla`. Yedek + göç + sağlık mantığı
  **kopyalanmadı** — aynı kararı iki yerde tutmak, bir sonraki düzeltmede birini
  güncelleyip diğerini unutmak demektir.
* **KULLANIM-GATE:** sağlık 200 **yetmez** — eski süreç de 200 veriyordu. Betik yeniden
  başlattıktan sonra `/api/meta`yı okur ve damganın hedefe eşitliğini ÖLÇER; eşit
  değilse BAŞARISIZ sayar. Kök neden `@lru_cache` olduğu için kapanma kanıtı **yalnızca
  damganın tazelenmesidir.**

### Kanıt (4 Eylül 2026, 13:47–13:48)

| Adım | Çıktı |
|---|---|
| Deploy öncesi yedek | `data/backups/2026-09-04-134757.db` · **788 KB** · `integrity_check = ok` · 32 tablo · 6 kullanıcı |
| Güncelleme | `[guncelle] canli=aed4b5fad0e6  hedef=97bc72094af2` |
| Yeniden başlatma | `[baslat] zorla yeniden baslatma: PID 5496 durduruluyor` → `AYAKTA (PID 26212)` |
| **Doğrulama** | `[guncelle] TAMAM: canli damga 97bc72094af2 = hedef 97bc72094af2` |
| **Kesinti** | 13:48:06 → 13:48:12 ≈ **6 saniye** |
| Duman (dışarıdan) | funnel `health=200` · `ready=200` · `/api/meta` build `97bc72094af2` · sürüm `0.2.0` |
| `scripts/live_gate.py` | **TÜM ZORUNLU KAPILAR GEÇTİ (23 kontrol)**, çıkış 0 |
| **Canlı göç sürümü** | `c3d4e5f8a1b2` — kodun head'i ile AYNI (masterprompt Y1 şartı) |
| `alembic check` | **FAILED** — ve bu BEKLENEN: SQLite'ta belgelenmiş ADR-036 sapması (bkz. `tests/test_fk_sapmasi_kapisi.py`, 5 test geçiyor). Bu satır bir arıza değil, kayda geçmiş bir lehçe farkıdır. |

**KANIT YOK kalan tek alt madde:** kimlikli duman testi (giriş yapıp bir işlem okuma).
`live_gate.py` bunu `--email/--password` ile koşar; asistan kullanıcı parolası
kullanmaz/işlemez. `/api/ready` (DB + şema) ve 23 kimliksiz kontrol geçti; kimlikli
ayak Murat tek komutla koşabilir:
`python scripts/live_gate.py https://<adres> --email <e-posta> --password <parola>`

### Yan bulgu + kapı (aynı turda)

`guncelle.ps1` ilk yazımda **hiç ayrışmadı**. Hata satırı hatanın yeri değildi: PowerShell
5.1 **BOM'suz** dosyayı ANSI (cp1254) sayıyor, Türkçe karakterler dizge sınırını kaydırıyor,
ayrıştırıcı alakasız bir satırda patlıyor. Depodaki diğer üç betikte BOM **vardı** — yani
konvansiyon vardı ama **yazılı değildi**; yazılı olmayan konvansiyon bir sonraki dosyada
tutmaz. `tests/test_ps1_bom_kapisi.py` (2 test, **mutasyon 2/2**: BOM kaldırılınca ikisi de
kırmızı — nedensellik; BOM dururken hata sokulunca yalnız ayrıştırma testi kırmızı — kapsam).

*Kapsam notu: §10 "madem buradayız" yasağı gereği bu kapı ayrı bir iş sayılabilirdi. Y1'in
KURDUĞU yolu sessizce kırabilecek bir tuzak olduğu için içeride tutuldu; benzer bir tuzak
çıkarsa backlog'a yazılacak.*

### BUG #341 — ÇIKIŞ KODU OKUNAMAYAN DEPLOY BETİĞİ YARIM ARAÇTIR

Bu, Y1'in **kendi teslimatının defektiydi** (kapsam kayması değil): Y2/Y3'te tekrar deploy
edilecek ve çıkış kodu okunamayan bir betik her seferinde aynı belirsizliği üretirdi.
Üç turda kapandı ve **üçü de aynı sınıf**: bir çocuk süreç, ebeveynin tanıtıcısını miras
alıyor ve o tanıtıcı üzerinde bekleyen herkesi asıyor.

| Tur | Belirti | Ölçüm | Kök neden | Düzeltme |
|---|---|---|---|---|
| 1 | `guncelle.ps1 \| tail` 2 dk döndü, betik 9 sn'de bitmişti | `-KuruKosum` (Start-Process çalışmayan yol) boruyu **0,3 sn**'de kapatıyor → sızıntı kesinlikle torun süreçte | uvicorn çağıranın **stdout borusunu** miras alıyor, günlerce yaşadığı için boru hiç kapanmıyor | `baslat.ps1` ayrı PowerShell'de, std tanıtıcıları **dosyaya** bağlı koşar |
| 2 | `baslat.ps1 cikis -196608`, log'da PowerShell banner'ı | canlı **dokunulmadan kaldı** (health 200, damga değişmedi) — betik önce ölçüp sonra uyguladığı için yarım iş bırakmadı | `Start-Process -ArgumentList` dizi elemanlarını **tırnaklamaz**; kullanıcı dizini boşluk içerdiği için `-File` yolu bölündü ve PowerShell etkileşimli açıldı | argüman açıkça tırnaklandı |
| 3 | deploy 13:56:13'te **başarıyla** bitti ama çağrı yine asıldı ve **doğrulama satırı hiç yazılmadı** | servis log'unda `AYAKTA` var, `TAMAM` yok | `Start-Process -Wait`, .NET tarafında yönlendirilmiş **akışların** kapanmasını da bekler; uvicorn o dosya tanıtıcılarını miras aldığı için akışlar uvicorn ölene kadar kapanmaz | `-Wait` yerine `Wait-Process` — işletim sistemi **süreç** tanıtıcısını bekler, akışlardan etkilenmez (180 sn tavan) |

**Sonuç (13:59:17):** betik artık sonuna kadar akıyor ve doğrulama satırını yazıyor:
`[guncelle] TAMAM: canli damga 681a2eabef13 = hedef 681a2eabef13`.

**Kalan ve BİLİNÇLİ olarak kabul edilen sınır:** çağıran taraf çıktıyı **boruya** verirse
(`| tail`) boru yine açık kalır — uvicorn'un miras aldığı tanıtıcıyı betik içinden
koparmanın Windows'ta temiz bir yolu yok. **Doğru çağrı biçimi dosyaya yönlendirmedir:**

```
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\windows\guncelle.ps1 > logs\guncelle.out 2>&1
echo $?      # cikis kodu OKUNABILIR
```

Bu, betiğin kusuru değil Windows süreç tanıtıcısı semantiğidir; kayda geçti ki bir sonraki
koşumda "asıldı" diye yanlış teşhis konmasın.

---

## ✅ Y2 — KESİNTİ KÖRLÜĞÜ BİTTİ (4 Eylül 2026, canlı kanıtla)

### KANIT — zincirin İKİ halkası da ayrı ayrı ölçüldü

> **Neden iki ayrı kanıt gerekti:** "tek arıza sinyali var, bir kez kanıtlamak hepsini
> kanıtlar" diye yazmıştım — **yanlıştı.** Sinyal aynı (ping'in yokluğu) ama onu üreten
> **kod yolları farklı**: bekçi ölünce betik hiç koşmaz; servis bozulunca betik koşar ve
> `if ($sorun.Count -eq 0)` **karar dalını** atlar. İkincisi bir daldır ve ayrıca ölçülmelidir —
> o koşul ters yazılsa, site çökmüşken betik "sağlamım" pingi atmaya devam eder ve
> **alarm hiç çalmaz.** Y2'nin var olma sebebi tam olarak bu körlük.

**HALKA 1 — ping kesilirse alarm çalar (bekçi öldü senaryosu).**
Bekçi 14:50:46'da devre dışı bırakıldı; servis **ayakta bırakıldı** (kullanıcıya sıfır
kesinti). Son ping 14:50:04. Period 10 dk + grace 20 dk. **Alarm ~15:20'de telefona ulaştı**
— ve bu, daha önceki `/fail` testinden **farklı bir mekanizmadır**: orada sisteme "bozuldum"
denmişti, burada **hiçbir şey söylenmedi** ve Healthchecks kararı sessizliğin kendisinden
verdi.

**HALKA 2 — sağlıksızken ping ATILMAZ (servis bozuk, bekçi onaramıyor).**
`saglik.ps1` uygulamayı kendisi onardığı için "servisi durdur, betiği koş" dizisi bu dalı
ölçmez (betik onarır ve sağlıklı ping atar). Bu yüzden **gerçek bir onarılamaz arıza**
kuruldu — 24,5 saatlik olayın (BUG #326) tam sınıfı: uvicorn durduruldu ve port, **503
dönen sahte bir dinleyiciyle** tutuldu, böylece `baslat.ps1` yeni süreci başlatamadı.

Ölçüm tahminle değil **yakalayarak** yapıldı: ping adresi geçici olarak yerel bir
yakalayıcıya yönlendirildi (Healthchecks'in "Last Ping" damgasını okumak API anahtarı
ister ve dışarıdan gözlemdir; bu ölçüm yerel ve deterministiktir).

| Faz | Durum | `saglik.ps1` | Yakalanan ping | Kayıt |
|---|---|---|---|---|
| **A** | sağlıklı | çıkış 0 | **1** ✅ | — |
| **B** | 503 + onarım başarısız | çıkış 1, `HATA: uygulama baslatilamadi` | **1** (artmadı) ✅ | `12:24:25Z,0,1` |

B fazında ping **hiç atılmadı** ve kayıt hem sağlıksızlığı hem onarım denemesini taşıdı.

**GERİ AÇMA DOĞRULANDI** (bir testin izlemeyi kapalı bırakması, hiç kurmamaktan kötü olurdu):
görev `State = Ready` · kayda yeni satır (`12:22:57Z,1,0`, sonra `12:25:06Z,1,0`) ·
telefona **UP** bildirimi. Servis: yerel `health=200`, funnel `health=200`.

---

### (Tasarımın gerekçesi)

### Tasarım İKİ KEZ değişti — ikisi de ölçümle

**İlk tasarım (yoklama):** GitHub Actions saat başı `/api/health` yoklar, düşerse issue açar.
Kotayı hesaplayıp saatlik seçmiştim (5 dk → 8.640 koşum/ay, bütçenin 4 katı; 60 dk → 720, %36).

**Ama iki itiraz ölçüldü ve biri tasarımı devirdi:**

| İtiraz | Ölçüm | Sonuç |
|---|---|---|
| "5 dakikalık cron kotayı 7 günde bitirir" | Tasarım zaten **saatlikti**, gerekçesi dosyanın içinde | ❌ Geçersiz — dosya okunmadan aritmetik yapılmış |
| "60 gün etkinliksizlikte zamanlanmış iş devre dışı kalır" | GitHub belgesi: bu kural **public** depolar için. Depo private. **Ve kural, önerilen çözümde (workflow'u public vitrine taşımak) geçerli OLURDU** | ❌ Geçersiz — ve öneri riski yaratırdı |
| "Kota bitince Actions bloklanır" | GitHub belgesi doğruladı: ödeme yöntemi yoksa kullanım **bloklanır** | ✅ **Geçerli** — izleme, yedi kalite kapısını da susturabilirdi (asimetrik bedel) |
| "Bekçiyi kim bekliyor?" | — | ✅ **Geçerli ve tasarımı devirdi** |

**Devirici argüman:** *yoklayan bir izleyici sessizce ölebilir, ve öldüğünde sessizlik
"her şey yolunda" gibi görünür* — Y2'nin kapatmak için var olduğu körlüğün ta kendisi.

### Yeni tasarım: ÖLÜ ADAM ANAHTARI (BUG #342)

Yön tersine çevrildi. Makine **dışarı ping atar**; ping kesilirse alarm çalar. Kesilme
sebeplerinin hepsi kesintidir: servis öldü · makine kapandı · ağ gitti · **görev bozuldu**.
**Sessizlik, her şeyin yolunda olduğunun değil, alarmın kendisidir.** İstenen iki mutasyon
(servisi durdur → alarm; izlemeyi durdur → yokluğu fark edilsin) **tek mekanizmayla**
karşılanır; "bekçiyi kim bekliyor" sorusu ortadan kalkar.

* Ping `saglik.ps1`'in **yalnız `$sorun.Count -eq 0`** dalında atılır (uygulama + tünel +
  dış yol, üçü birden). Koşulsuz ping alarmı **kalıcı olarak** susturur — en tehlikeli
  arıza biçimi, çünkü sistem "izleniyorum" der ve izlenmez.
* Ping hatası sağlık görevini **düşürmez** (bekçi, beklediği şeyi bozmamalı).
* Ping adresi **depoya girmez** (`.gitignore`) — o URL kimlik taşır; commit edilirse
  herkes sahte "sağlıklıyım" gönderip alarmı susturabilir.
* `canli-izleme.yml`'den **cron kaldırıldı** (kota riski sıfır); `workflow_dispatch`
  ikinci göz olarak kaldı.

**Kapı:** `tests/test_olu_adam_anahtari_kapisi.py` — 3 test, **mutasyon 4/4**. Ölçüm metin
araması değil, PowerShell'in **kendi sözdizimi ağacı** (çağrının hangi `if` bloğunda
olduğu ancak AST'den bilinir).

### ⚠️ KARAR (a): MAKİNE KAPALI = KESİNTİ

Beta Murat'ın kendi bilgisayarında koşuyor; makine kapanınca ping duracak ve alarm çalacak.
İki seçenek vardı ve **kod yazılmadan önce seçildi**:

**(a) SEÇİLDİ — makine kapalı kesintidir.** Kullanıcı açısından zaten öyle: site erişilemiyor.
Susturma bayrağı eklemek, ölçmek için kurulan şeyi ölçülemez kılardı. **Yan etkisi
tasarımın en değerli parçası:** B0 kâğıt üzerindeki bir maddeden **her gece hissedilen bir
maliyete** dönüşür — 24 gündür bekleyen karar kendini dayatır. Y2 böylece Y0'ın kanıt
toplayıcısı olur.

**YAZILI TAAHHÜT:** alarm gürültülü gelirse çözüm **susturmak değil B0'dır.** Bu satır,
iki hafta sonra sessizce bir mute bayrağı eklenmesini engellemek için buraya yazıldı.

### Erişilebilirlik yüzdesi — açık uç kapatıldı (BUG #343)

Cron kaldırılınca raporun veri kaynağı boşta kaldı. Rapor artık **üçüncü tarafa hiç bağlı
değil**: `saglik.ps1` her koşumda `logs/erisilebilirlik.csv`'ye tek satır yazar.

**Raporun kalbi:** payda **beklenen slot**tur (10 dk'da bir → 7 gün = 1.008). Makine
kapalıyken satır yazılmaz; yalnız yazılmış satırlara bakan bir rapor o geceyi **%100
sağlıklı** gösterirdi — ölçmediğini mükemmel sanmak (L45). **Kayıp slot kesinti sayılır.**

**Ve yazarken tam bu sınıftan bir defekt üretildi:** rapor, diskte DURAN gerçek kaydı
*"OLCUM YOK"* diye okudu. Sebep BOM'du — PowerShell'in `Add-Content -Encoding UTF8`'i
dosya başına BOM koyuyor, düz `utf-8` okuyan `DictReader`'ın ilk sütun adı `﻿zaman_utc`
oluyor ve **her satır sessizce eleniyordu**. (`test_ps1_bom_kapisi` ile aynı bayt, ters
yönde: orada yokluğu, burada varlığı kırıyor.) `tests/test_erisilebilirlik_raporu_kapisi.py`
— 6 test, **mutasyon 3/3**.

### KABUL EDİLEN SINIR (yazılı, incelenmemiş varsayım değil)

**Ping servisi kendisi ölürse kimse haber vermez.** Bilinçli kabul: bir SaaS'ın ölme
olasılığı ev bilgisayarının kapanma olasılığından kat kat düşüktür, ve yerel kayda dayanan
erişilebilirlik raporu o servisten **bağımsız ikinci bir gözdür**.

### ⛔ KALAN TEK ADIM — MURAT'TA (hesap açma asistanda yasak)

Ücretsiz bir ölü-adam-anahtarı servisinde (Healthchecks.io / Better Stack / UptimeRobot
heartbeat) bir kontrol oluştur:
* **Periyot 10 dk, grace 20 dk** (sağlık görevi 10 dakikada bir koşuyor; 20 dk = iki
  kaçırılan slot, tek bir gecikmede alarm çalmaz).
* Bildirim kanalı **telefona push** — e-posta bu iş için zayıf: 24,5 saatlik kesinti zaten
  fark edilmemişti.
* Verdiği ping URL'sini şu dosyaya yapıştır (depoya girmez):
  `deploy/windows/izleme-url.txt`

Sonra iki mutasyon koşulacak: **(1)** servis durdurulacak → alarm telefona ulaşmalı;
**(2)** sağlık görevi durdurulacak → yokluğu da alarm üretmeli. İkisinin kanıtı buraya yazılacak.
## ✅ Y0 — B0 BARINDIRMA KARARI KAPANDI (4 Eylül 2026) — **24 gün sonra**

**KARAR: A — kendi makine + Cloudflare Tunnel + SATIN ALINMIŞ alan adı.**
Tam gerekçe: `docs/architecture/adr-057-barindirma.md` (ADR sayısı 56 → **57**).

**Yöntem değişikliği kayda geçti.** `masterprompt-kapali-beta.md` §5 *"asistan seçmez"*
diyordu; ölçülen sonuç: kural yürürlükteyken B0 **24 gün açık kaldı** — her turda
seçenekler yeniden sunuldu, karar hiç verilmedi. **Sunmak, karar vermek değildir.**
Charter'daki o cümle üstü çizilerek düzeltildi, sebebiyle birlikte.

### Kararı belirleyen DÖRT yeni ölçüm (11 Ağustos notundan sonra)

| Ölçüm | Sonuç | Karara etkisi |
|---|---|---|
| Kaçırılan iş telafisi | `kacirilan_isleri_telafi_et()` **5/5** planlı işi kapsıyor (BUG #302) | B0 notunun A'ya yazdığı **2. bedel maddesi kapandı** — not *"B4'te ölçülecek"* diyordu, bugün ölçüldü |
| DNS arızası (BUG #303) | Cloudflare 6/6 · Google 6/6 · ad üzerinden 200 | Alan adının **aciliyet** gerekçesi düştü; **kalıcılık** gerekçesi durdu |
| Beta kullanımı | 23 gündür dışarıdan sıfır | 7/24'ün bugünkü değeri düşük → aylık gider erken |
| **Y2 kararı (a)** | Makine kapalı = kesinti **ve artık alarm çalıyor** | A'nın 1. bedeli **sessiz olmaktan çıktı** → görünür olduğu için kabul edilebilir |

### Ölçüt uygulaması (beraberlik kuralı: en ucuz + geri dönülebilir)

* **eu.org (0 TL)** en ucuz görünüyor ama **alınabilir değil** — elle onay günler–haftalar.
  **24 gündür bekleyen bir maddeyi yeni bir kuyruğa bağlamak karar vermek değildir.**
* Alınabilirlerin en ucuzu **A**: alan adı ~**10,44 $/yıl**, B'nin (**€3,79/ay**) beşte biri.
* **A→B görünmezdir** (aynı alan adı, DNS yön değiştirir; PWA kısayolu bozulmaz) — yani A,
  B'yi dışlamıyor, B'ye giden yolu ucuzlatıyor.
* **C (Oracle)** elendi: kuyruk **ölçülmedi**; ölçülmemiş bir beklentiye karar bağlamak,
  ertelemenin başka adıdır (L45).

### B'ye geçiş tetikleyicileri — ŞİMDİDEN yazılı ("sonra bakarız" değil)

Biri gerçekleşirse B'ye geçilir, karar yeniden tartışılmaz:
1. P8 (açık beta) açılıyorsa · 2. Erişilebilirlik 7 günde **%90'ın altına** inip sebebi
makinenin kapalı olmasıysa · 3. Kurucu dışında **düzenli kullanan 2 kullanıcı** varsa.

### ⛔ KALAN TEK İNSAN ADIMI (seçenek listesi değil, tek talimat)

> **Cloudflare Registrar'dan (`domains.cloudflare.com`) bir alan adı al.** ~10,44 $/yıl,
> maliyetine, yenilemede zam yok, WHOIS gizliliği ücretsiz. Adı sen seç. Aldıktan sonra
> **alan adını söylemen yeterli** — gerisi (cloudflared, tünel, TLS, deploy, kapı 9-12)
> asistanda.

Bu, bu fazın **tek zorunlu masrafıdır**.
## Y3 — YAYIN + KAPI 9-12 ▸ BEKLİYOR
## Y4 — GERÇEK KULLANICI SİNYALİ ▸ BEKLİYOR
## ✅ Y5 — DEFTER SENKRONU KAPANDI (4 Eylül 2026)

### Backlog: 164/251/81 → **165/250/81** — ve asıl bulgu bu SAYI DEĞİL

Masterprompt *"çıpadan bu yana kapanan 60 BUG backlog'a işlenir"* diyordu. Ölçüldü:

| Ölçüm | Değer |
|---|---|
| Çıpadan bu yana `uygulanan-fixler.md`'ye eklenen satır | **413** |
| O satırlarda geçen **backlog kodu** | **5** (`FEAT-017`, `FEAT-033`, `FEAT-034`, `LLM-002`, `UX-001`) |
| Çıpa sonrası BUG'ların backlog `sections/`te geçme sayısı (#322/#326/#330/#338/#339/#342) | **0** |

**Yani backlog dağılımının hiç kımıldamaması bir defter ihmali değildi:** backlog Temmuz
2026'da yapılmış bir **denetim listesidir**; çıpadan bu yanaki 60 defektin neredeyse tamamı
**ölçümden ve gerçek kullanımdan** doğdu (banka verisi girildiği gün 21 tanesi) ya da kapı
inşasının yan ürünüydü. İki akış farklı kaynaklardan besleniyor ve 413 satırda yalnız
**5 kez** kesişiyor. **Toplu ✅ atılmadı; tek tek bakıldı.**

**Durumu değişen tek madde — kanıtla:**

* **`UX-001` (ilk açılış onboarding'i yok) 🔲 → ✅.** FEAT-034 turunda (11 Ağu) fiilen
  yapılmış ama backlog'a işlenmemiş. Doğrulandı: `OgreticiSihirbaz.jsx` · `Ipucu.jsx` ·
  `YardimKosesi.jsx` · içerik tek kaynak `lib/ogretici.js` (13 panel) · adım durumu
  **backend'de** (`GET /api/onboarding/rehber`) · `ogretici.test.jsx` · `App.jsx:30` bağlı.
  *Not:* maddenin aksiyonu "localStorage flag" diyordu; ürün bunu backend'de tek kaynağa
  çevirdi — çünkü flag'e dayalı ilk sürüm ilk hesap eklenince kayboluyordu (BUG #262).
  **Backlog'un önerdiği çözüm ile uygulanan çözüm farklı; kapanışı belirleyen SONUÇ.**

**Değişmeyenler ve NEDEN (gerekçesiz bırakılmadı):**
* `LLM-002` (prompt caching) 🔲 kalır — **bilinçli ertelendi**, gerekçesi ölçülü: canlı
  sağlayıcıda kazanç ölçülemiyor ve tool kümesi istek başına değiştiği için prefix cache
  her seferinde geçersiz olurdu.
* `FEAT-033` 🟡 kalır — MoM trend var, kategori kaymaları yok; durum doğru.

### MCP defteri: **KAPATILDI** (boşaltılmadı — kapatıldı)

| Ölçüm | Değer |
|---|---|
| 7 Ağu 2026 | flush 19 gündür hiç koşulmamış, **186 satır** |
| 4 Eyl 2026 | **300 satır**, flush hâlâ hiç koşulmamış |
| MCP'nin statüsü | 7 Ağu'da resmen **tarihsel arşiv** ilan edilmiş |

Yani `post-commit` yakalaması, **hiç koşulmayacak bir flush için** çalışıyordu. Böyle bir
defter zararsız değildir: her bakan *"300 satır bekleyen iş var"* sanır.
**Sahte yükümlülük, borçtan daha kötüdür — çünkü ödenmez ve unutulmaz.**

Yapılan: `post-commit` yakalaması durduruldu (gerekçe dosyanın içinde), obsolete
`scripts/mcp_sync_report.py` **silindi** (BUG #311: ölü kod zararsız değildir), ona atıf
yapan `canli-smoke-testleri.md` ve `PROJE.md` düzeltildi — yoksa belge denetimi kırmızı
verirdi (ölü yönlendirme). Belge denetimi + ölü kod kapısı **geçiyor**.
## ✅ Y6 — ADR BORCU KAPANDI (4 Eylül 2026)

**Beş yeni ADR yazıldı (057-061).** Masterprompt'un istediği beş kararın beşi de yazıldı:

> **⚠️ SAYI DÜZELTMESİ (aynı gece):** bu satır önce *"ADR 56 → 61"* diyordu ve **yanlıştı**.
> `glob("adr-*.md")` **`adr-index.md`'yi de sayıyor**, ayrıca `013a` ve `034 Revize`
> aynı kararın ekleri. Ölçülen doğru değerler: **58 benzersiz karar · 60 belge**.
> Vitrin üreticisi de bu yanlış sayıyı yayınlıyordu; sayım düzeltildi ve iki değer
> **ayrı** raporlanıyor (tek sayı vermek, hangisinin kastedildiğini okuyucuya bırakırdı).


| ADR | Karar | Neden ADR'ye girmesi gerekiyordu |
|---|---|---|
| **057** | Barındırma: A (kendi makine + Cloudflare Tunnel + satın alınmış alan adı) | 24 gündür açık olan tek insan-kapısı |
| **058** | Yedi kalite kapısı ve tavanların anlamı | *Tavan bir HEDEF değil, bir BORÇ DONDURUCUDUR.* Aile bazında tutulur (tek toplam takasa izin verirdi), araç sürümü sabittir, ve **reddedince doğru cevap tavanı yükseltmek değildir** — ölçülen sicil: sekiz reddediş, sekizinde de haklı |
| **059** | SQLite'ta `alembic check` **kalıcı kırmızıdır** | Belgelenmiş bir sapma, o sapmayı ölçen tek aracı okunamaz kılmıştı; ölçüm `test_fk_sapmasi_kapisi.py`'ye taşındı. **İki yanlış teşhis de kayda geçti** — mutasyon yalnız testi değil TEŞHİSİ de sınar |
| **060** | Depo private kalır + üretilmiş vitrin; kapı imajı değil **depoyu** tarar | Kapı yanlış yüzeyi koruyordu (862 dosyanın 186'sı). Vitrin **allowlist** ile üretilir: denylist yalnız düşünüleni yakalar, sızıntı düşünülmeyenden gelir |
| **061** | Milestone/tag disiplini bırakıldı | Sistem **18 Temmuz'da fiilen ölmüştü** (103 commit tag'siz, bir numara iki işe verilmiş) ve karar yalnız `PROJE.md`'de yazılıydı. *Bir kararın nerede yazılı olduğu, ne kadar yaşayacağını belirler* |

**Y6'nın ölçtüğü boşluk:** çıpadan bu yana 60 BUG kapandı, 7 kapı kuruldu, yeni bir hat
açıldı, depo private yapıldı, geçmiş ikinci kez yeniden yazıldı — ve **sıfır yeni ADR**
yazılmıştı. Kararlar commit mesajlarında kalıyordu.

## 🟡 Y7 — ÜRETİCİ + KAPI HAZIR, tek insan adımı bekliyor

> **Karar ADR-060'ta yazılı.** Aşağıdaki bölüm kararın gerekçesi; uygulama bu bloğun sonunda.

### Üretici: `scripts/vitrin_uret.py` (4 Eylül)

* **Elle yazılmaz, ÜRETİLİR.** Elle yazılmış vitrin BUG #310'a yakalanır: *"3.486 test"*
  cümlesi, testler 2.000'e düşse de orada durur. Üretici gerçek depoyu **ölçer**.
* **ALLOWLIST, denylist değil.** Üretici **hiçbir dosyanın metnini kopyalamaz**; her alan
  kendi ölçüm fonksiyonundan gelir ve `IZINLI_ALANLAR`da **gerekçesiyle** listelidir.
  Çıktıya giden tek yol o sözlüktür — izinsiz bir anahtar üretilirse **üretim durur**.
  ADR **gövdeleri hiç okunmaz**, yalnız başlık satırları alınır.
* Gerekçe: denylist yalnız *düşünülen* sızıntıyı yakalar. Sızıntı düşünülmeyenden gelir —
  commit mesajları, mutlak yollar, ADR gövdelerindeki rakamlar, fixture izleri, şahsi
  destek adresi (`live_gate` bunu zaten yakalamıştı).

### Kapı: `tests/test_vitrin_kapisi.py` — **ikinci** savunma

Üretilen **baytları** ölçer, üreticinin niyetini değil. **Mutasyon 4/4:** gerçek tutar ·
**mutlak yol** (kullanıcı adını taşır — "düşünülmeyen sızıntı"nın somut örneği) · ADR
gövdesi sızıntısı · e-posta. Bulgunun kendisi hata mesajına **basılmaz** (o da sızıntı
olurdu) — yalnız sınıfı ve satırı.

### Üretirken KENDİ kuralımı çiğnedim — ve kapıya bağlandı

Hızlı modda **toplanan** test sayısı ölçülüp vitrine *"geçti"* diye yazılıyordu.
Toplanan ≠ geçen: **ölçülmemiş bir iddiayı ölçüm gibi sunmak** (R3 ihlali), üstelik
**dışarıya** gidecek bir belgede. Düzeltme üç parçalı: veriye `olcum_modu` yazılır,
taslak README'nin başına görünür uyarı düşer, `test_TASLAK_YAYINLANAMAZ` taslağı
**yayınlatmaz**.

### Kapı kapsamı CI'da zorunlu mu — ÖLÇÜLDÜ

| Kapı | CI'da | Kanıt |
|---|---|---|
| `sir_taramasi` (çalışma ağacı **+ git geçmişi**) | ✅ | `ci.yml:152-155`, adı verilmiş adım |
| Kişisel veri kapısı | ✅ | `pytest tests/` içinde (`ci.yml:97`) |

**Ve "vakumsal yeşil" riski ÖLÇÜLDÜ, varsayılmadı.** Tarayıcı hiç dosya bulamazsa sert
kapı sessizce geçer miydi? Mutasyonla sınandı (tarayıcı boş döndürüldü): **iki test
kırmızı verdi** — `test_TAVAN_kazanimi_kilitler` ve `test_KAPSAM_imajdan_GENIS`.
Koruma **var**; gereksiz kod eklenmedi.

### ⛔ Kalan tek insan adımı

GitHub'da **boş bir public depo** aç (adını sen seç). Gerisi asistanda: vitrin üretilir,
kapıdan geçirilir, push edilir. Çıktı asıl depoda **izlenmez** (`vitrin/` gitignore'da) —
üretilmiş bir dosyayı commit etmek, elle yazılmış vitrin hastalığının arka kapısıdır.

---

### (Kararın gerekçesi — 4 Eylül)

**Karar (Murat, 4 Eylül):** asıl depo **private kalır**; yanına **üretilmiş bir vitrin
deposu** açılır. Gerekçe: CV'de GitHub ve bu proje anılıyor, projenin görünmemesi amaca
aykırı — ama asıl depoyu açmak, iki hafta içinde **üçüncü** `git-filter-repo` + force-push
demekti (ölçüldü: e-posta 15 dosya · banka adı 96 dosya · gerçek tutar 15 dosya, aynısı
671 commit'lik geçmişte).

**Tasarım kararı — vitrin ELLE YAZILMAZ, ÜRETİLİR.** Elle yazılan vitrin bu deponun
kayıtlı hastalığına yakalanır (BUG #310: belgenin işaret ettiği şey diskte yok). Üretici
gerçek depoyu ölçer; sayı koşumdan gelir.

**Tasarım kararı — ALLOWLIST, denylist değil.** Üretici bir private→public boru hattıdır;
denylist yalnız *düşünülen* sızıntıyı yakalar. Sızıntı düşünülmeyenden gelir: commit
mesajları, mutlak dosya yolları (`C:\Users\<ad>\...`), ADR gövdelerindeki gerçek rakamlar,
`uygulanan-fixler.md`'nin 1.070 satırındaki bakiye örnekleri, hata çıktılarına gömülü
fixture verisi. Bu yüzden üretici **yalnızca açıkça izin verilmiş alanları** yayar (test
sayısı, coverage yüzdesi, kapı adı + tavanı, ADR başlığı, mutasyon skoru); listede olmayan
her şey **varsayılan olarak düşer**.

**Kapı üretimde değil, PUSH'tan hemen önce koşar:** üretilen dosyalar diskteyken taranır,
temizse yayınlanır. Mutasyon: vitrine bilerek gerçek bir rakam enjekte edilir → kapı
kırmızı vermeli.


---

## 🔴 CANLI BULGU — 4 Eylül 23:07: ADRES ÇÖZÜLMÜYOR, DAVETLİLER GİREMİYOR

Makine ~16:45'ten 23:06'ya kadar uykudaydı. Uyanınca sağlık görevi koştu ve **kırmızı** verdi:

    [HATA] DIS ADRES HIC COZULMUYOR (hicbir cozumleyici A kaydi vermedi)
           - davetliler SITEYI ACAMAZ

### Ölçüm — ve "bende çalışıyor" tuzağı canlı yakalandı

| Ne soruldu | Cevap |
|---|---|
| `curl https://financialos.<tailnet>.ts.net/api/health` | **200** ✅ |
| Sistem çözümleyicisi bu adı ne veriyor | **`100.81.23.113`** — bir **tailnet** adresi |
| Cloudflare DoH (4 sorgu) | **0/4 çözdü** (`Status:3` NXDOMAIN) |
| Google DoH (4 sorgu) | **0/4 çözdü** (`Status:3` NXDOMAIN) |
| `tailscale funnel status` | **`Funnel on`**, proxy `→ 127.0.0.1:8000` doğru |
| Uygulama | ayakta, `/api/health` 200 |

**Yani tünel de uygulama da sağlam; çözülmeyen şey ADIN KENDİSİ.** Benim `curl`'üm 200
döndü çünkü istek tailnet içinden gitti ve funnel'ı **atladı** — `saglik.ps1`'in docstring'inde
yazılı olan tuzak, bugün canlı olarak yakalandı: *"bende çalışıyor" bu kurulumda kanıt değildir.*

### Bunun karara etkisi — ve önceki cümlemin düzeltmesi

Bugün öğlen *"DNS arızası bugün yok, sebep kanıtlı değil"* yazmıştım. O ölçüm **o an
doğruydu** (13:00'te iki çözümleyici de 6/6 çözüyordu). Ama arıza **aralıklı** ve şu an
yeniden yaşanıyor — üstelik bu kez **iki çözümleyicide birden** (Ağustos'ta yalnız
Cloudflare'de idi). Bu, sınıfın **üçüncü ölçülen tekrarıdır** (11 Ağu · 12 Ağu · 4 Eyl).

Hâlâ kanıtlanmayan: davetlilerin Ağustos'ta **bu yüzden** dönmediği.
**Artık kanıtlanan:** adres **güvenilmez** ve düzeltmesi bizde değil — `ts.net` alanının
DNS'i Tailscale'e ait. Kendi alan adı + Cloudflare Tunnel, kaydı Murat'ın kontrolüne alır.
**ADR-057'nin (A seçeneği) gerekçesi bu ölçümle güçlendi.**

### Y4'ün sıralaması DEĞİŞTİ (kendi önerimi geri alıyorum)

Birkaç saat önce *"Y4 mesajı şimdi gönderilsin, Y3'ü beklemesin"* önerdim. **Bu ölçüm onu
geçersiz kılıyor:** adres şu an dışarıdan açılmıyor. Şimdi mesaj göndermek, davetlileri
ikinci kez kapalı bir kapıya yollamak olur — ve ilk seferinde neden dönmediklerini sorarken
aynı hatayı tekrarlamak, sorunun kendisini kanıtlamış olmaz, **tekrarlamış** olur.
**Karar: `y4-davetli-mesaji.md` SÜRÜM B (yeni adresle), Y3'ten sonra.**


### Denenen onarım ve sonucu (kayda geçsin — işe yaramadı)

Tünel kapatılıp yeniden açıldı (`funnel off` → `funnel --bg --https=443`). `Funnel on`
döndü ve proxy doğru kuruldu, **ama DNS değişmedi**: iki çözümleyici de hâlâ 0/4.
Yetkili tarafın cevabı `Status:3` — yani kayıt **hiç yayınlanmamış**, önbellek sorunu değil.
Node `Online`, `BackendState: Running`.

**Hipotez (ölçülebilir, henüz doğrulanmadı):** makine uzun süre uykuda kalınca Tailscale
funnel DNS kaydını **geri çekiyor** ve dönüşü hemen olmuyor. Doğruysa, Ağustos'ta
davetlilerin gördüğü şey *"site kapalı"* değil **"site yok"**tur — ve bu, ölü betanın
en makul açıklamasıdır. *(Hâlâ hipotez: bugün node 10+ dakikadır online ve kayıt dönmedi;
başka bir sebep de olabilir. Sağlık görevi 10 dakikada bir ölçtüğü için dönüş anı
`logs/erisilebilirlik.csv` ve `saglik.log`'a kendiliğinden düşecek.)*

**Yapılabilecek bir şey yok — ve asıl mesele bu.** Uygulama ayakta, tünel açık, node
online; çözülmeyen tek şey **başkasının DNS'i**. Kendi alan adı bu bağımlılığı bitirir:
kayıt Cloudflare'de, Murat'ın hesabında olur.


### 🔬 MEKANİZMA BULUNDU (23:18) — ve bu, ölü betanın en güçlü açıklaması

Kayıt geri gelmeye başladı ama **çözümleyiciye göre değişiyor.** Sekizer sorgu:

| Çözümleyici | 23:07 | 23:17 | 23:18 |
|---|---|---|---|
| **Cloudflare** | 0/4 | **0/8** | **0/6** |
| Google | 0/4 | 6/8 | 5/6 |

A kaydı Google'da geliyor: `185.40.234.55` (Tailscale public ingress). O IP'ye
pinlenmiş HTTPS isteği **200** dönüyor — yani **servis sağlam, ingress sağlam.**

**Cloudflare'in cevabındaki kritik ayrıntı:** `Authority` bölümünde SOA ile birlikte
**`TTL: 3491`**. Yani Cloudflare, makine uyurken aldığı **NXDOMAIN'i negatif önbelleğe
almış** ve o kaydı ~58 dakika daha tutacak. Kayıt yeniden yayınlansa bile Cloudflare
**"bu ad yok" demeye devam ediyor.**

**Chrome ve Brave'in "Güvenli DNS"i varsayılan olarak Cloudflare'e gider** (BUG #303'te
ölçülmüştü) ve işletim sisteminin DNS'ini **atlar**. Sonuç zinciri:

> makine uyur → Tailscale kaydı çeker → Cloudflare NXDOMAIN'i **saatlerce** önbellekler →
> makine uyanıp servis 200 dönse bile **Chrome/Brave kullanıcısı "site bulunamadı" görür**

**Bu, Ağustos'taki davranışın en makul açıklamasıdır** ve artık mekanizmasıyla ölçülü:
davetliler makinenin uyuduğu ya da yeni uyandığı bir anda denediyse, gördükleri şey
*"site kapalı"* değil **"böyle bir site yok"**tur. İnsan ikincisine geri dönmez.

**Hâlâ kanıtlanmayan:** o beş kişinin tam olarak bu yüzden dönmediği (onlara sorulmadı).
**Artık ölçülen:** bu arızanın gerçek, tekrarlayan ve **bizim düzeltemeyeceğimiz** olduğu.

**Karara etkisi — ADR-057 güçlendi, ama bir uyarıyla:** kendi alan adı DNS kaydını
Murat'ın kontrolüne alır ve Cloudflare Tunnel'da kayıt **kalıcıdır** (makine uykuda olsa
bile ad çözülür; site "kapalı" görünür, "yok" değil). Ama **A seçeneği makinenin
uykusunu çözmez** — yalnız görünürlüğünü düzeltir. Uyku sürdükçe kullanıcı hâlâ kapalı
bir siteye gelir. **B'ye (7/24 VPS) geçiş tetikleyicilerinden biri bu gece fiilen
oluştu** (erişilebilirlik %20,75); tetikleyici 7 günlük pencere istediği için henüz
resmen tetiklenmedi, ama yön artık ölçülü.


### Alan adı GEREKTİRMEYEN hafifletme seçenekleri — ölçüldü, karar Murat'ın

Cloudflare kaydı ancak **makine uyuduğunda** çekiliyor. Uyku engellenirse arıza hiç
oluşmaz. Bugünkü ayarlar ölçüldü:

| Ayar | Değer |
|---|---|
| Uyku zaman aşımı — **prizde (AC)** | **0 = ASLA uyumaz** |
| Uyku zaman aşımı — pilde (DC) | 60 dk |
| `FinancialOS-Saglik` görevi `WakeToRun` | **False** |

**Yani prizdeyken makine kendiliğinden uyumuyor.** Dün akşamki ~6,5 saatlik uyku (16:45 →
23:06) bu ayarlardan gelmiyor; ya **pilde** kalmış ya **kapak kapatılmış** ya da elle
uyutulmuş. Bu bir yapılandırma hatası değil, **kullanım deseni** — ve düzeltmesi kod değil
karar.

**Üç seçenek (hiçbiri asistan tarafından uygulanmadı; makinenin güç davranışı ve pil ömrü
Murat'ın kararıdır):**

1. **Kapak kapanınca prizdeyken uyuma.** Arızayı kökten keser, pil davranışını
   değiştirmez (yalnız AC'de). En küçük müdahale.
2. **Sağlık görevine `WakeToRun`.** Makine 10 dakikada bir uyanır; Tailscale kaydı hiç
   çekilmez. Ama pilde ciddi tüketim ve "uyusun" niyetini bozar.
3. **Hiçbiri — (a) kararında kal.** Makine uyur, alarm çalar, erişilebilirlik düşük görünür
   ve bu **B'ye geçişin gerekçesini biriktirir.** Bugünkü ölçüm bunu zaten başlattı (%20,75).

**Not:** 1 ve 2 arızayı hafifletir ama **çözmez** — makine kapandığında (yeniden başlatma,
elektrik, seyahat) kayıt yine çekilir ve Chrome kullanıcısı yine "site yok" görür.
**Kalıcı çözüm kendi alan adıdır** (kayıt Cloudflare'de, makineden bağımsız); **tam çözüm
7/24 barındırmadır** (B).

### Erişilebilirlik — kararın (a) faturası ilk kez göründü

`python -m scripts.erisilebilirlik_raporu`:

    kayit 14 (saglikli 11 · basarisiz 3) · beklenen 53 slot
    ERISILEBILIRLIK: %20,75  (11/53 — kayip slot ve onarilan slot kesinti sayilir)
    kayip slot: 39 (makine kapali)
    KESINTILER: ~33 dk · ~65 dk · ~382 dk kayit yok (makine kapali) + 3 saglik BASARISIZ

**382 dakikalık boşluk = makinenin uykusu.** Y2'nin (a) kararı tam olarak bunu görünür
kılmak içindi: *makine kapalı = kesinti.* Rakam artık kâğıtta değil, ölçümde. Ve B'ye geçiş
tetikleyicilerinden biri **"erişilebilirlik 7 günde %90'ın altına inerse"** idi — bugünkü
pencere %20,75. *(Tetikleyici 7 GÜNLÜK pencere ister; bugün tek günlük ve izleme yeni
kuruldu, yani henüz tetiklenmiş sayılmaz — ama yön belli.)*

## 🟡 Y8 — KAPANIŞ KAPISI: 10 maddenin 6'sı kapalı, 3'ü İNSAN-KAPISI

**4 Eylül 2026, 15:36 ölçümü** (§0.1'in aynı komutları):

| Madde | Durum | Kanıt |
|---|---|---|
| Canlı SHA = `main` HEAD (drift 0) | ✅ | `TAMAM: canli damga e4bc5471b0f0 = hedef e4bc5471b0f0` · deploy 17 sn · funnel 200 |
| Dışarıdan izleme + gerçek alarm, mutasyonla | ✅ | iki halka ayrı ayrı (yukarıda) |
| B0 kararı yazılı, ADR'de | ✅ | ADR-057 |
| Backlog ölçülerek güncellendi, MCP defteri | ✅ | 165/250/81 · defter kapatıldı |
| En az 5 yeni ADR | ✅ | 057-061 |
| Depo görünürlük kararı + kapı kapsamı CI'da | ✅ | ADR-060 · `sir_taramasi` `ci.yml:152` · kişisel veri kapısı süitte |
| Tam süit yeşil, coverage ≥%93, kapılar | ✅ | **3.525 passed · 18 skipped · 0 failed** (7:37) · %94 · kapı 296 · ölü kod 0 |
| Kendi alan adı üzerinden HTTPS, B4 | ⛔ | **alan adı alınmadı** — insan-kapısı |
| Kapı 9-12 kanıtla → 15/15 | ⛔ | B4'e bağlı |
| En az 3 davetliden gerçek cevap | ⛔ | Y3 sonrası |

**Wave-Y kapanmıyor ve kapanmamalı:** kalan üç madde kod işi değil. İkisi tek bir satın
almaya (alan adı), biri beş kişiye mesaj atmaya bağlı. Bunları "yapıldı" saymak, Wave-Y'nin
teşhis ettiği hatanın kendisi olurdu — **kanıtsız ✅**.


---

## §8.1 BAŞLANGIÇ ↔ BİTİŞ KIYASI (Y8 şartı — 4 Eylül 2026 gece ölçümü)

| Ölçüm | 13:37 (başlangıç) | 23:33 (şimdi) | |
|---|---|---|---|
| Yerel HEAD | `fce4753` | `6331640` | +14 commit |
| **Canlı build damgası** | `aed4b5fad0e6` (var olmayan bir SHA) | **`6331640dcb70`** | **drift 0** |
| Canlı sağlık | 200 / 200 | 200 / 200 | — |
| Süit | 3.504 passed | **3.525 passed · 18 skipped · 0 failed** | +21 |
| Coverage | %94,02 | %94 (CI'da ≥93 kilitli) | — |
| Kalite kapısı | 296 | **296** | tavan korundu |
| ADR | 56 belge sanılıyordu | **58 karar / 60 belge** (sayım düzeltildi) | +5 karar |
| MCP defteri | **281 satır ve büyüyor** | **kapatıldı** | borç bitti |
| Backlog | 164/251/81 | 165/250/81 | +1 (kanıtla) |
| Dış izleme | **yok** | **ölü adam anahtarı, canlı kanıtlı** | Y2 |
| BUG tavanı | #338 | **#344** | +6 |
| Erişilebilirlik ölçümü | **hiç yoktu** | **%20,75** (ölçülüyor) | görünür oldu |

**Wave-Y'de kapanan:** Y1 (drift) · Y2 (kesinti körlüğü) · Y0 (B0 kararı, 24 gün sonra) ·
Y5 (defterler) · Y6 (ADR borcu) · Y7'nin kod tarafı.
**Kapanmayan:** Y3 (yayın) · Y4 (kullanıcı sinyali) · Y7'nin yayın adımı · Y8.
**Sebebi tek:** dördü de **alan adı satın alınmasına** ya da bir hesap açılmasına bağlı.

### Gecenin ölçtüğü üç yayın-hatası (hepsi DIŞ İDDİA olacaktı)

1. **e2e sayısı 7 yazıyordu, gerçek 8.** Metin sayımı döngüyle üretilen testi göremez;
   sayım Playwright'ın kendi listesine bağlandı.
2. **ADR sayısı 61 yazıyordu, gerçek 58 karar / 60 belge.** `adr-index.md` sayılıyordu ve
   ekler (`013a`, `034 Revize`) ayrı karar sanılıyordu. Üç belgede düzeltildi.
3. **`cloudflared` "kuruldu" diye raporlandı, kurulmamıştı.** `winget` çıkış 0 döndü ama
   MSI `1602` (UAC gösterilemedi) ile düştü; `winget list` ile yakalandı.

**Üçünün ortak dersi (L68'in üç ayrı biçimi):** bir aracın "başarılı" görünmesi, ölçmediğin
sürece kanıt değildir — ve bu, en çok **dışarıya gidecek** sayılarda tehlikelidir.



### İzleme şu an GERÇEK bir kısmi kesinti raporluyor — ve bu doğru davranış

23:30 ve 23:40 kayıtları `0,0` (sağlıksız, onarım gerekmedi). Sebep uygulama değil:
uygulama 200 dönüyor, Google'ın çözdüğü IP'ye pinlenmiş HTTPS isteği de 200. Kırmızı
veren şey **kısmi DNS kesintisi** — Cloudflare 0/3, Google 3/3.

`saglik.ps1` bunu bilinçli olarak kesinti sayıyor (BUG #303 kararı): *"çözümleyiciler
ÇELİŞİYORSA bu bir kesintidir: kullanıcıların bir kısmı giremiyordur."* Chrome ve Brave
Cloudflare'e sorduğu için **davetlilerin çoğu şu an giremiyor**; "yarısı girebiliyor"
demek, kesinti olmadığı anlamına gelmez.

**Sonuç:** ölü adam anahtarı ping atmıyor ve alarm çalıyor — **kurulduğu iş tam olarak bu.**
Alarm bir kez çalar (Healthchecks düşüşte bir, toparlanmada bir bildirir), spam olmaz.
Yani izleme bu gece **ilk gerçek kesintisini** yakaladı ve bu kesinti **uydurma değil**:
Chrome kullanan bir davetli şu an siteyi açamaz.

### 🟡 AÇIK BIRAKILAN, GEREKÇESİYLE: B-geçiş tetikleyicisini ÖLÇEN bir şey yok

ADR-057 B'ye (7/24 VPS) geçiş için üç tetikleyici yazdı; ikincisi ölçülebilir:
*"erişilebilirlik 7 günlük pencerede %90'ın altına inerse."*

**Ama o cümleyi bugün hiçbir şey değerlendirmiyor.** `erisilebilirlik_raporu` oranı basıyor;
eşikle karşılaştırıp "tetiklendi" diyen bir adım yok. Bu, bu defterin en sık yazdığı sınıf:
**yazılmış ama zorlanmayan bir kural** (L61 — ölçen sistem, haber veren sistem değildir).

**Bu gece YAPILMADI ve sebebi iki tane:**

1. **Wave-Y §10 yeni özellik yasağı.** Bir CLI bayrağı eklemek küçük görünür ama hattın
   kuralı açık: *"Wave-Y'de sadece kapatma işi var."* Kuralı, küçük olduğu için esnetmek,
   kuralı esnetmenin en yaygın biçimidir.
2. **Veri zaten yetmiyor.** Tetikleyici **7 günlük** pencere istiyor; izleme bugün kuruldu
   ve elimizde bir günden az var. Bugün yazılsa bile ölçemezdi — ve ölçemeyen bir eşik,
   "kuruldu" damgasıyla sessizce yanlış güven üretirdi.

**Sıradaki turun işi olarak kaydedildi.** O zamana kadar oran elle okunur:
`python -m scripts.erisilebilirlik_raporu --gun 7`

### BUGÜNÜN DERSLERİ (L68'den devam)

* **L68 — Bir komutun çıktısı "başarılı" görünüyor diye iş yapılmış olmaz.** `git commit -F-`
  zincir içinde sessizce çalışmadı, `push` "Everything up-to-date" dedi ve iki hedefin işi
  commit'siz kaldı; HEAD kontrol edilmeseydi "tamam" diye raporlanacaktı. Y1'in kök
  nedeninin (`baslat.ps1` "zaten çalışıyor" deyip geçmesi) commit tarafındaki aynısı.
* **L69 — Aynı sinyali üreten farklı kod yolları ayrı ayrı ölçülür.** "Tek arıza sinyali
  var, bir kez kanıtlamak hepsini kanıtlar" iddiası yanlıştı: bekçinin ölümü ile sağlıksız
  dalın ping atmaması **iki ayrı yoldur**; ikincisi bir karar dalıdır ve ters yazılsa alarm
  hiç çalmazdı.
* **L70 — Onarım, ölçümü yiyebilir.** Kendi kendini iyileştiren bir sistem, iyileştirmeyi
  kayda geçirmezse kendi arıza geçmişini siler (BUG #344).
* **L71 — Bir kapının deseni ikinci bir kapıya KOPYALANMAZ.** Vitrin kapısına kopyalanan
  desenler, depo kapısında "yeni sızıntı" olarak sayıldı. Muafiyet yazmak kapıyı
  körleştirirdi; doğru cevap tek kaynaktı — `git ls-files`'ın beş kopyasıyla aynı ders.
* **L72 — Bir kapının testi, kapının GİRİŞ NOKTASINI çağırmıyorsa kapıyı değil
  kütüphanesini test eder.** `tests/test_olu_kod_kapisi.py`'nin 8 testi de
  `olu_fonksiyonlar()`'ı çağırıyordu; CI ise `python scripts/olu_kod_kapisi.py`, yani
  `main()`'i koşar. O aralıkta duran bir `NameError` (`tarandi` yerine `taranan`) 8
  testten, mutasyondan ve benim "kapı geçiyor" raporumdan kaçtı — kapı **her koşumda
  çöküyordu**. Üstelik hatayı taşıyan satır, "kapı hiçbir şey ölçmeden geçmesin" diye
  eklenen **kapsam tabanının kendisiydi**: koruma, korumaya çalıştığı arızayı üretti.
  Bulan şey bir test değil, **ruff'ın F821'i** oldu — ve o da yalnız CI'da görüldü,
  çünkü yerelde "kapılar yeşil" ölçümüm bayattı (L68'in aynısı, bu kez bende).
* **L73 — Çağıranın ortamına bağlı bir test, kapı değildir.** Yeni yazılan giriş-noktası
  testi tek başına yeşil, pre-commit kancasında kırmızıydı. Tek fark: ben komuta
  `PYTHONIOENCODING=utf-8` yazmıştım, kanca yazmıyordu. Windows'ta boruya yazan çocuk
  süreç, o değişken yoksa yerel kod sayfasını (cp1254) kullanır; `"kapı geçildi"`
  UTF-8 diye çözülünce `"kap\ufffd ge\ufffdildi"` olur ve **kapı sağlam olduğu hâlde test
  düşer**. Çocuğun kodlaması artık testte AÇIKÇA sabitleniyor. Depoda bunun üçüncü
  tekrarı: `.ps1` BOM'u (yokluğu kırıyordu) · `erisilebilirlik.csv` BOM'u (varlığı
  kırıyordu) · şimdi boru kodlaması. **Kodlama bu projede tekrar eden bir arıza sınıfıdır;
  varsayılmaz, yazılır.**
* **L74 — Türetilmiş bir belge, türetildiği şeyden bağımsız bayatlar — ve daha çok okunduğu
  için zararı daha büyüktür.** `sections/DURUM-INDEX.md` *"RULE'da hâlâ açık: 12"* diyor;
  ayrıntı dosyası `sections/RULE.md` bugün **0 açık** gösteriyor ve içinde 13 yerde `M83`
  notu var — indekste `M83` kelimesi **hiç geçmiyor**. İndeksin kendi son bölümü
  *"bir madde düzeltildiğinde Durum satırını güncelle, böylece backlog bir daha sessizce
  bayatlamaz"* diye bitiyor: önlem tuttu, ama **yalnız ayrıntıda**. Özeti kimse güncellemedi.
  Doğru çözüm sayıları elle yazmak değil, `sections/*.md`'den ÜRETMEK.
* **L75 — Satır numarası bir kanıt değil, bir ADRESTİR; adresler taşınır.** `faz-3-durum.md`
  her maddeye `dosya:satır` kanıtı iliştirmişti — bugün rastgele seçilen **4 işaretçinin
  4'ü de** yanlış yeri gösteriyor, biri artık var olmayan bir sembolü işaret ediyor
  (`_daily_constrained_provider`). Kararların kendisi ölçülünce sağlam çıktı: biri taşınmış
  (`app/llm_quota.py`), ikisi yerinde. **Kalıcı kanıt sembol adı ve onu kilitleyen testtir**;
  satır numarası altı hafta ömürlüdür ve okuyanı "düzeltme geri alınmış" sanmaya iter.
* **L76 — Bir kırmızı, kendinden sonrakini gizler.** CI'ın ruff adımı düşünce pytest adımı
  hiç koşmadı; bu gece yazılan iki kapının Linux'ta çöktüğü ancak ruff düzeltilip sıra
  pytest'e gelince görüldü. **Bir kapıyı düzeltmek, arkasındaki kapıların yeşil olduğunu
  kanıtlamaz** — düzelttikten sonra boru hattının TAMAMI yeniden okunur.
* **L77 — Yazılmış bir hata yolu, ancak GERÇEKTEN koşulabiliyorsa yoldur.** İki kapı da
  "powershell yoksa atla" diye korunmuştu; koruma `returncode == 127`e bakıyordu, oysa
  komut yoksa `subprocess.run` sonuç dönmez, **fırlatır**. Yani koruma kodu vardı, yolu
  yoktu. Hata yolları da en az başarı yolu kadar KOŞULARAK sınanır (bu turda deney:
  yokluk taklit edildi, atlama ölçüldü).
* **L78 — Bir gerçeğin iki yerde yazılı olması, iki kat güvence değil; ikiye bölünmüş bir
  gerçektir.** Backlog maddelerinin durumu hem başlıkta hem `- **Durum:**` satırında
  duruyordu ve iki madde bunları BİRBİRİNE ZIT söylüyordu. Kötüsü şu: yanlış kalan yarı,
  otomatik sayımların okuduğu yarıydı — yani çelişki görünmez tarafta yaşadı.
  Ve bir üçüncü madde, Durum satırı yalnızca GİRİNTİLİ yazıldığı için 48 gün boyunca
  hiçbir sayıma girmedi: **biçim hatası, içerik hatası kadar sessizdir.**
  Çözüm not değil kapı oldu (`tests/test_backlog_tutarliligi_kapisi.py`).

---

## Y2 — İZLEMENİN İLK GERÇEK OLAYI (5 Eylül 2026, gece)

Bugüne kadarki Y2 kanıtları **kurulmuş** olaylardı (bekçiyi kapat, sahte 503 dinleyici koy).
Bu gece izleme, kimse kurmadan **gerçek bir kesintiyi baştan sona kaydetti** — ve kaydı,
tamamen bağımsız bir ölçüm yoluyla doğrulandı.

**Olay:** dış adres DNS'te çözülmüyor (uygulama ve tünel sağlam; kesinti yalnız dışarıdan).

| Saat (yerel) | `saglik.ps1`'in kendi kaydı | Aynı anda ELLE yapılan DoH ölçümü |
|---|---|---|
| 23:07-23:30 | `DIS ADRES HIC COZULMUYOR` ×3 | Cloudflare **0/8** · Google 6/8 |
| 23:40 | `DNS KISMI KESINTI — çözmeyen: cloudflare` | — |
| 23:50 | `DNS KISMI KESINTI — çözmeyen: google` (yön değişti) | — |
| 00:00 | `[OK] uygulama + tünel + dış yol sağlam` | — |
| 00:07 | — | Cloudflare 2/3 · Google 2/3 (toparlanıyor) |
| 00:10 | son kısmi kesinti | — |
| **00:20'den sonra** | **kesintisiz `1,0`** (10 dk'da bir, boşluksuz) | 00:22'de **4/4 · 4/4** |

**İki bağımsız yol, aynı zaman çizgisi.** Biri makinedeki zamanlanmış görevin CSV'si, diğeri
sohbetten atılan DoH sorguları. Üstelik ikisi de, ölçülen **SOA negatif TTL'i (3491 sn ≈ 58 dk)**
ile önceden hesaplanan pencereye oturuyor: 23:07 + ~58 dk ≈ 00:05, ilk temiz `OK` 00:00'da.
Yani arıza *"kendiliğinden geçti"* değil; **süresi önceden söylenebilir** bir önbellek olayı.

**BUNUN B0 İÇİN ANLAMI (ve alarm taahhüdünün sınanması).** BUG #342 kurulurken şu yazılmıştı:
*"alarm gürültülü gelirse çözüm susturmak değil B0'dır."* Bu gece alarmı çaldıran şey bir
gürültü değil, **gerçek bir dış erişim kesintisiydi** — ve o kesintiyi ortadan kaldıran tek
düzeltme, kaydın Murat'ın kontrolüne geçmesi, yani **alan adı**. Susturma seçeneği bu yüzden
gündeme bile gelmiyor.

**Doğrulanacak (Murat, sabah):** telefonda ~23:30 civarı bir DOWN, ~00:25 civarı bir UP
bildirimi olmalı. Bu ikisi görülürse zincirin **gerçek bir olayda** uçtan uca çalıştığı
kanıtlanmış olur; görülmediyse ölü adam anahtarının ping tarafı ayrıca ölçülmelidir.

**Erişilebilirlik (aynı pencere, `scripts/erisilebilirlik_raporu.py`):** %26,15 (17/65 slot).
Kayıp 39 slotun büyük kısmı **öğleden sonraki 382 dakikalık uyku**; sağlık başarısızlıkları
ise yukarıdaki DNS olayı. Yani düşük oranın iki ayrı sebebi var ve **ikisi de B0'a çıkıyor**:
makinenin uyuması ve adın makineye bağlı olması.
* **L79 — "Bir daha güncellemeyi unutma" bir mekanizma değildir.** `DURUM-INDEX.md`'nin
  kendi metodoloji notu tam olarak bunu diyordu ve 48 gün tutmadı. Özet artık
  `scripts/backlog_ozeti.py` ile ÜRETİLİYOR ve güncelliği bir testle kilitli. Bir belgeyi
  bayatlamaktan koruyan şey disiplin değil, **türetilmiş olmasıdır.**
* **L80 — Ölçen sistem, ölçtüğü sistemi bozabilir.** Süit `app.main`'i içe aktardığı için
  canlı betanın log dosyasına tutundu ve o dosya 10 MB'a dayandığında **canlı uygulamanın
  log rotasyonunu imkânsız kıldı**; uygulama sağlam kaldı, gözlemi kör oldu. En sinsi yanı
  şu: arıza, sistemi **gözlemlemeye çalışan** araçtan geldi. Test ortamı üretimin
  dosyalarına dokunmaz — `.env` için bu ders 286'da öğrenilmişti, log için öğrenilmemişti.
* **L81 — "Bir kez bile olmamış" ile "hiç denenmemiş" farklı şeylerdir.** `financialos.log.1`
  dosyasının hiç var olmaması, rotasyonun **bir kez bile tamamlanmadığını** söylüyordu;
  yani arıza bu gece doğmadı, bu gece TETİKLENDİ. Bir mekanizmanın hiç çalışmamış olması,
  çalıştığının kanıtı sanılabilir — çünkü hata da üretmez.
