# GECE RAPORU — 4 Eylül 14:55 → 5 Eylül 10:00

**Kural: R3.** Her sayının arkasında **bu sabah koşulmuş** bir komut çıktısı var. Kanıtı
olmayan satır **KANIT YOK** yazar. Dün koşmuş bir ölçüm, bugünkü olgu diye sunulmaz.

**Çıpa:** `f5d780d6acbb` (4 Eyl 14:41 — 14:55'ten önceki son commit)
**Bu rapor yazılırken HEAD:** `37e2107` (5 Eyl 09:41)

---

## §0.1 ÖZET KARTI

| Hedef | Durum | Kanıt |
|---|---|---|
| **Y0** barındırma kararı | ✅ | ADR-057 (seçenek A), 4 Eyl |
| **Y1** canlı sürüm drift'i | ✅ | `guncelle.ps1`: `canli damga 37e2107… = hedef`, bu sabah koşuldu |
| **Y2** kesinti körlüğü | 🟡 **DÜZELTİLDİ ama ✅ DEĞİLDİ** | Karar dalı bu sabah TAZE doğrulandı (bozuk→0 ping, sağlam→1 ping). **AMA** onarım ölçümü üretimde ÖLÜYDÜ → BUG #359, bu sabah kapandı |
| **Y3** yayın + kapı 9-12 | ⛔ | alan adı yok — insan-kapısı |
| **Y4** gerçek kullanıcı sinyali | ⛔ | Y3'e bağlı; davetli mesajı hazır, gönderilmedi |
| **Y5** defter senkronu | ✅ | 4 Eyl; gece 6 tur daha doğrulama yapıldı (21 madde düzeldi) |
| **Y6** ADR borcu | ✅ | ADR 56 → **61** |
| **Y7** vitrin | 🟡 | Üretim TAM ÖLÇÜMLÜ tamamlandı (`vitrin/README.md` + `olcumler.json`, 4 Eyl 23:59). Public depo **açılmadı** — insan-kapısı. Kapıda **vakumsal yeşil yolu var** (§4) |
| **Y8** kapanış kapısı | 🟡 | 7/10 kapalı; 3'ü insan-kapısı (alan adı ×2, davetli mesajı) |

**Wave-Y kapanmıyor ve kapanmamalı.** Kalan üç madde kod işi değil.

---

## 1. DELTA — 4 Eyl 14:55 → 5 Eyl 10:00

| Ölçüm | Değer | Komut |
|---|---|---|
| Commit | **45** | `git log f5d780d..HEAD` |
| Dosya / satır | 80 dosya · **+4.087 / −173** | `git diff --shortstat` |
| Yeni test dosyası | **11 kapı** (+38 test) | `git diff --diff-filter=A -- tests/` |
| Kapanan BUG | **#339 · #341 · #343 · #344 · #345–#359** | commit mesajları |
| Yeni ders | **L68 → L86** (19 ders) | `wave-y-ledger.md` |

**Çalışılan saatler** (`git log --date=format:"%d %H"`):

| Saat | Commit | Not |
|---|---|---|
| 4 Eyl 15:00–16:00 | 2 | Y5/Y6 kapanışı |
| 4 Eyl 16:00–23:00 | **0** | makine uykuda (erişilebilirlik raporundaki 382 dakikalık boşluk) |
| 4 Eyl 23:00–24:00 | 7 | Y7 vitrin + Y1 doğrulama |
| 5 Eyl 00:00–01:00 | 5 | belge denetimi, CI teşhisi |
| 5 Eyl 01:00–02:00 | **11** | log kesintisi, backlog mekanizması |
| 5 Eyl 02:00–03:00 | **11** | backlog doğrulama turları, frontend kapıları |
| 5 Eyl 03:00–04:00 | 8 | dağıtım/arayüz zinciri, emniyet |
| 5 Eyl 09:40 | 1 | **BUG #359** (bu raporun kendi bulgusu) |

Yani kesintisiz çalışma penceresi **23:00 → 04:00** (5 saat), öncesinde makinenin uyuduğu
7 saatlik boşluk var.

---

## 2. Y2 — KAPANDI MI? **HAYIR, TAM DEĞİL. VE SEBEBİ BU SABAH BULUNDU.**

Bu bölüm raporun en önemli kısmı; sırayla ve kanıtla.

### 2.1 Alarm geldi mi?

**Geldi.** Bekçi 4 Eyl 14:50'de durduruldu, alarm ~15:20'de telefona düştü.
**Kanıt sınıfı: KULLANICI BEYANI** — Murat sohbette *"alarm geldi"* dedi. Bu bir makine
ölçümü değildir ve rapor onu makine ölçümü gibi sunmaz.

### 2.2 Bekçi geri açıldı mı? Şu an ping ilerliyor mu?

**Görev canlı ve düzenli koşuyor.** Bu sabah ölçüldü:

```
logs/erisilebilirlik.csv son satırlar
2026-09-05T06:50:04Z,1,0
2026-09-05T06:54:19Z,0,1     ← §2.3'teki testin kaydı
2026-09-05T06:54:22Z,1,0
```

Gece boyunca 10 dakikada bir kesintisiz satır yazıldı; üç dağıtımın hiçbiri başarısızlık
üretmedi. `schtasks`: `FinancialOS-Saglik` **Ready**, son koşum tam zamanında.

**KANIT YOK:** Healthchecks arayüzündeki *Last Ping*'in ilerlediğini ve *UP* bildiriminin
geldiğini **doğrulayamadım** — bunun için ping URL'si (bir sır) gerekir ve asistan onu
kullanmaz. Ölçebildiğim: **ping'in ATILDIĞI** (§2.3-B), varış değil. Bu ayrım kayda geçsin.

### 2.3 KARAR DALI TESTİ — **bu sabah TAZE koşuldu, iki yönde**

Eski kayda dayanmadım; testi yeniden kurdum. Canlıya dokunmadan: port 8123'e hep **503**
dönen sahte bir dinleyici (port DOLU olduğu için onarım ikinci bir sunucu açamaz), ping
adresi yerel bir yakalayıcıya çevrildi.

```
A) SERVİS BOZUK (port 8123, 503)
   [UYARI] uygulama cevap vermiyor - yeniden baslatiliyor
   [HATA]  uygulama baslatilamadi
   çıkış kodu : 1
   ATILAN PING: 0        ← bozukken ping YOK

B) SERVİS SAĞLAM (port 8000, gerçek uygulama)
   çıkış kodu : 0
   ATILAN PING: 1        ← sağlamken ping VAR

SONUÇ: KARAR DALI DOĞRULANDI (yakalanan yol: /ping)
```

Yani *"sessizlik alarmın kendisidir"* iddiası artık **iki yönde de** kanıtlı. Bu, Y2'nin
açık kalan itirazlarından biriydi; **kapandı.**

### 2.4 ONARIM / ÖLÇÜM SIRASI — **BURADA GERÇEK BİR DEFEKT BULUNDU (BUG #359)**

Soru şuydu: *"KayitYaz ve PingAt, onarım denemesinden önce mi sonra mı? Sonraysa, sürekli
çöküp onarılan bir uygulama %100 mü görünüyor?"*

**Sıra doğruydu.** Onarım denemesinden sonra kayıt yazılıyor, ama onarım bayrağı **ayrı
sütun** olarak taşınıyor (`KayitYaz 1 $onarimGerekti`) ve ping yalnız sağlıklı dalda
atılıyor. BUG #344 bunu doğru kurmuş.

**AMA ÖLÇÜM ÖLÜYDÜ.** Soruyu koda değil **veriye** sorunca çıktı:

```
başlık          : zaman_utc,saglikli          ← İKİ sütun
satırlar        : 2026-09-04T12:24:25Z,0,1    ← ÜÇ değer
DictReader      : ['zaman_utc','saglikli']
raporun gördüğü : onarim=1 olan 0 satır
HAM veride      : onarim=1 olan 1 satır
```

**Kök neden:** `KayitYaz` üç sütunlu başlığı **yalnız dosya yokken** yazıyor. Dosya BUG
#344'ten ÖNCE iki sütunla oluşmuştu; satırlar üçüncü değeri almaya başladı, **başlık hiç
yükselmedi**. `csv.DictReader` fazlalığı `None` anahtarına koydu, `r.get("onarim")` daima
boş döndü.

**Yani cevabın kendisi: EVET, sürekli çöküp onarılan bir uygulama gerçekten %100
görünebilirdi** — tam da #344'ün önlemek için yazıldığı senaryo. Düzeltme yazılmıştı,
üretimde çalışmıyordu.

**Kapı neden yakalamadı:** mutasyon testleri kendi CSV'lerini **doğru başlıkla** yazıyordu.
Mekanizma sınanmış, **kullanılan veri sınanmamıştı** (L63/L64'ün veri karşılığı).

**Düzeltme (BUG #359, bu sabah):** okuyucu bayat başlıkta restkey'den okur · `KayitYaz` var
olan dosyanın başlığını da **taşır** (şema değişikliği bir kereye mahsus değildir) · yeni
test gerçek vakayı (bayat başlık + üç değerli satır) birebir kurar, mutasyon 1/1.

**Canlı doğrulama:** başlık taşındı (`zaman_utc,saglikli,onarim`), §2.3'ün bozuk koşumu
`0,1` yazdı, rapor artık **`ONARIM GEREKTI 2`** ve **`BOZULMA: 2 slotta`** diyor. Öncesinde
ikisi de görünmüyordu. Erişilebilirlik oranı da düzeldi: onarılan slotlar artık kesinti
sayılıyor.

### 2.5 Ping URL yenilendi mi?

**HAYIR.** Adres sohbete yapıştırıldığı için artık gizli değil; bilen biri sahte
"sağlıklıyım" gönderip **alarmı susturabilir** (servisi düşüremez, veri okuyamaz).
İnsan-kapısı: Healthchecks → Settings → regenerate. **~2 dakika.**

### 2.6 Y2'nin defterdeki durumu

Defter 4 Eylül'de Y2'yi **✅** işaretlemişti (`wave-y-ledger.md:144`). Bu sabahki ölçüm
gösteriyor ki **o ✅ erkendi**: zincirin bir halkası (onarım ölçümü) üretimde ölüydü ve
bunu ancak veriye bakınca gördük. Bugün itibarıyla:

- karar dalı ✅ (taze, iki yönde)
- onarım ölçümü ✅ (BUG #359 sonrası, canlı veriyle doğrulandı)
- ping'in **varışı** 🟡 (KANIT YOK — sır gerektiriyor)
- ping URL yenileme ⛔ (insan-kapısı)

**Y2 = 🟡.** Kalan iki madde de Murat'ta.

---

## 3. Y7 — VİTRİN

| Soru | Cevap | Kanıt |
|---|---|---|
| Tam ölçümlü üretim bitti mi? | **Evet** | `vitrin/README.md` 8.379 B · `vitrin/olcumler.json` 8.262 B, ikisi de 4 Eyl 23:59 |
| Çıktı nerede? | `vitrin/` — **gitignore'da** (`.gitignore:84`) | üretilen bayt depoya girmez, ayrı public depoya gider |
| Kapı üretilen baytları mı tarıyor? | **Evet** | `test_vitrin_kapisi.py:75` → `VITRIN.rglob("*")`, `.md/.json/.html` |
| Sonuç | **Temiz** | yasaklı desen tavanı SIFIR, ratchet yok |
| Public depo açıldı / push edildi mi? | **HAYIR** | insan-kapısı — depo adı Murat'tan bekleniyor |
| Taslak koruması çalışıyor mu? | **KANIT YOK** | bu sabah ayrıca koşulmadı; süit içinde yeşil ama izole doğrulama yapılmadı |

**Üreticiyi bu sabah yeniden koşmayı denedim, 6 dk 40 sn'de tamamlanmadı** (tam ölçüm modu
süiti + coverage'ı koşuyor) ve iptal edildi. `vitrin/` dosyaları koşum öncesi hâliyle
korundu (diff ile doğrulandı). Yani **çıktının bugün hâlâ güncel olduğu ölçülmedi — KANIT YOK.**

---

## 4. DİĞER KAPILARIN KÖR NOKTASI

Soru dün gece yedi kapıya soruldu ve **iki gerçek boşluk** bulunmuştu (`olu_kod_kapisi`,
`belge_denetimi` → ikisine de kapsam tabanı eklendi). Bu gece o iş **kendi kendini
sınadı** ve iki yeni bulgu verdi:

| Kapı | Boşlukta yeşil verir mi? | Mutasyon sonucu |
|---|---|---|
| kişisel veri | Hayır — tarayıcı boşalınca kırmızı | 3/3 |
| `.ps1` BOM | Hayır — `assert dosyalar` | 2/2 |
| FK sapması | Hayır — `assert sapma` | 3/3 |
| ruff/kalite | Hayır — kazanım kilidi | — |
| **ölü kod** | **Kapsam tabanı eklendi… ama tabanın KENDİSİ çöküyordu** | **BUG #345** — `taranan` vs `tarandi`; kapı her koşumda `NameError` veriyordu ve ben üç commit boyunca "geçiyor" dedim |
| belge denetimi | Hayır — kapsam tabanı (100) | 2/2 |
| **vitrin** | **EVET — vakumsal yeşil yolu VAR** | `vitrin/` yoksa **4 noktada `pytest.skip`**; artefakt üretilmemişse kapı sıfır iddia ile yeşil görünür |

**Kayıt:** vitrin kapısının skip yolu **kapatılmadı**. Gerekçesi: kapatmak, yayın akışının
nasıl kurulacağına karar vermeyi gerektirir (public depo henüz yok) ve bu insan-kapısı.
**Ama bilinmesi gereken bir açık:** yayın anında kapının gerçekten taradığı doğrulanmalı,
yoksa koruma tiyatro olur.

Ayrıca bu gece **kapıların kendi kör noktaları** üç kez mutasyonla bulundu: ölü-state
kapısı yorumları sayıyordu (kendi açıklaması onu körleştiriyordu), backlog kapısı boş
dizgeyi işaret sanıyordu (`"" in "abc"` → True), ham-SQL kapısının örneği komşu kapıyı
düşürüyordu.

---

## 5. Y3 / Y4 — ALAN ADI OLMADAN NE YAPILDI?

İkisi de bloke, **ve bloke kaldı**. Ama alan adı gerektirmeyen hazırlık işleri yapıldı:

- **Canlı doğrulama kapısı koşuldu:** `live_gate.py` → **23 zorunlu kapının 23'ü geçti**
  (sağlık · hazır olma · kapalı kayıt 403 · KVKK metinleri · 2 MiB gövde sınırı ·
  brute-force limiti · **PWA manifest + service worker**). Yani uygulama tarafı yayına hazır.
- **Kapının iki uyarısı okundu** (haftalardır duruyordu, kimse bakmamıştı):
  - `Server: uvicorn` dışarıya yayınlanıyordu → `--no-server-header` ile kapatıldı, ölçüldü.
  - Destek adresi **kişisel Gmail** ve `/api/meta` kimliksiz yayınlıyor → alan adına bağlı,
    insan-kapısı olarak kaydedildi.
- **Davetli mesajı** hazır (`y4-davetli-mesaji.md`, sürüm B), gönderilmedi.

---

## 6. SÜİT VE KAPILAR — BU SABAH KOŞULDU

| Ölçüm | 4 Eyl 13:37 (başlangıç) | 5 Eyl sabah | Komut |
|---|---|---|---|
| Süit | 3.504 passed · 18 skipped | **3.571 passed · 18 skipped · 0 failed** (10:43) | `pytest -q` |
| Coverage | %94,02 | **%94,08** (11.722 ifade / 694 kapsanmayan) | `pytest --cov=app` |
| vitest | 214 | **214 passed** | `npm test -- --run` |
| e2e | 8 | **KANIT YOK** | bu sabah koşulmadı (dev sunucusu + Playwright gerektirir) |
| ruff toplam | 296 | **294** | `kalite_kapisi.py` |
| ruff S ailesi | 63 / 63 | **62 / 62** | aynı |
| ruff F ailesi | 202 / 202 | **201 / 201** | aynı |
| alembic head | `c3d4e5f8a1b2` | **`c3d4e5f8a1b2`** | `alembic heads` |
| Canlı damga | `aed4b5fad0e6` (drift VAR) | **HEAD = canlı (drift 0)** | `guncelle.ps1` |
| Bayat belge | 12 | **0** | `belge_denetimi.py` |
| Backlog | ✅171 · 🔲249 · 🟡81 | **✅193 · 🔲222 · 🟡86** | `backlog_ozeti.py` |

**Betik kapıları (çıkış kodu):** `kalite_kapisi` 0 · `olu_kod_kapisi` 0 · `belge_denetimi` 0
· `sir_taramasi` 0. **CI:** son 20 koşumun 20'si `success`.

---

## 7. DÜRÜSTLÜK BÖLÜMÜ

### Kaç kez yanlış teşhis koyup kendini ölçümle çürüttün? — **Yedi**

1. **Kalite kapısını üç commit boyunca "geçiyor" diye raporladım.** Çöküyordu. Sebep:
   `python script.py | tail` çağrısında gördüğüm çıkış kodu `tail`indi (L68'in tekrarı).
2. **Yeni derleme adımı başarılı bir derlemeyi "başarısız" ilan etti.** `Start-Process
   -PassThru` nesnesinin `ExitCode`'u boş kalıyordu; `$null -ne 0` doğru dönüyordu. Aynı
   dersin ters yönü (L85).
3. **Betik taramasını yanlış yöntemle koştum** (`python scripts/X.py`) ve 6 sahte bulgu
   üretti. Depo konvansiyonu `python -m scripts.X`. **Raporlanmadan önce elendi.**
4. **Bir mutasyonun ateşlememesini "kapı kör" sanacaktım** — ölçtüm, kusur kabuk kaçışımdaydı.
5. **Erişilebilirlik raporunu yanlış okudum**, izlemenin öldüğünü sandım. Rapor yalnız
   *kesintileri* listeliyor; CSV'de düzenli kayıt vardı.
6. **`test_beta_metrics` düşünce önce kendi değişikliğimi suçladım.** Ölçüm başka şey
   söyledi: koşum UTC gece yarısını geçmişti — ve altından gerçek bir ürün kusuru çıktı
   (`topla()` saati üç ayrı kez okuyordu, BUG #356).
7. **Kullanıcı kılavuzunda bir satırı "bayat" diye düzelttim, düzeltme yanlıştı.** Dosya
   ölçülmeden bayat varsayılmıştı; ölçünce canlı log çıktı. Geri alındı ve **dürüst kayıt
   belgeye yazıldı.**

### Hangi tavan yükseltilmek istendi, yükseltildi mi?

**Üç kez tavan kırıldı, üçünde de yükseltilmedi.** İki kez S ailesi (`exec` kopyası, ruff'ın
kendi `S608`'i), bir kez F ailesi (öksüz import). Üçünde de **ihtiyaç kaldırıldı**.
`kalite-baseline.json` bu pencerede **iki kez değişti ve ikisi de İNDİRME**: S 63→62,
F 202→201. Toplam **296 → 294**.

### Kapsam kayması oldu mu?

**Evet, ve kabul ediyorum.** Wave-Y'nin Y0-Y8'i dışına çıkan işler:
`PERF-008` (yoklama), `FE-012` (ölü state), `BUG #354` (sıfırlama onayı), `BUG #358`
(yıkıcı betik emniyeti), `SEC-019`/`SEC-027b`, ve **altı turluk backlog doğrulaması**.

Gerekçe: bunların hepsi ya bir Wave-Y ölçümünün yan ürünü olarak ortaya çıktı (canlı kapı
uyarıları, bayat belge avı) ya da doğrudan "uygulamayı rayına oturtma" tanımına giriyor.
**Ama masterprompt'un yazdığı iş değildi** ve bu satır o yüzden burada duruyor — kapsam
kayması gerekçesiyle birlikte yazılırsa kayma, yazılmazsa savrulmadır.

### Yeni ders numarası yazıldı mı?

**Evet: L68 → L86** (19 ders), hepsi `wave-y-ledger.md`'de gerekçesiyle.
Öne çıkanlar: L74 (türetilmiş belge bağımsız bayatlar) · L79 (belgeyi koruyan şey disiplin
değil türetilmiş olmaktır) · L83 (backlog en çok çalışılan yerde bayatlar) · L84 (bir
düzeltmeyi ikiye bölmek hiç yapmamaktan yanıltıcıdır) · L85 (çıkış kodu iddiadır, ürün
ölçülebilir).

---

## 8. SENDE OLMAYAN — MURAT'TA BEKLEYEN

| # | İş | Süre | Neden bende değil |
|---|---|---|---|
| 1 | **Alan adı al** (Cloudflare, ~10,44 $/yıl) | ~10 dk | para harcama |
| 2 | **Healthchecks ping URL'sini yenile** | ~2 dk | hesap erişimi; adres sohbete girdi, alarm susturulabilir |
| 3 | **Vitrin için boş public depo aç** (adını sen seç) | ~3 dk | hesap açma/depo oluşturma |
| 4 | **`cloudflared` kur** (UAC onayı) | ~5 dk | yönetici onayı — alan adından sonra |
| 5 | **Kimlikli duman testi** `live_gate.py --email --password` | ~2 dk | parola |
| 6 | **Davetli mesajını gönder** (metin hazır, sürüm B) | ~5 dk | mesaj gönderme |
| 7 | **Karar:** "Yeni sohbet" içgörüleri de silmeli mi? | — | ürün kararı |
| 8 | **Karar:** makine uykuya girmesin mi? (3 seçenek ölçülü) | — | ürün/donanım kararı |

**1 numara diğer dördünü açıyor.** Alan adı geldiği an: `cloudflared` → tünel → TLS →
`SUPPORT_EMAIL=destek@<alan>` → kapı 9-12 → davetli mesajı. Kod tarafında engel yok.

---

*Bu rapor `docs/kalite-seruveni/gece-raporu-2026-09-05.md` ve Masaüstü'nde aynı içerikle
duruyor. Sayıların hepsi 5 Eylül 09:40–10:05 arasında koşulmuş komutlardan alındı;
alınamayanlar KANIT YOK diye işaretlendi.*
