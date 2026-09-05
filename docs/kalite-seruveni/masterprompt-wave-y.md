# MASTERPROMPT — Wave-Y (Yayın: uygulamayı rayına oturtma)

**Çıpa:** `7486e9c` · 4 Eylül 2026 · `financialos-durum-raporu-2026-09-04.md`
**Amaç:** kapalı betayı bitirmek. Ürün canlıda ayakta ama 24 commit geride, altı
kullanıcının beşi ölü, dört canlı-doğrulama kapısı kanıtsız ve B0 24 gündür açık.
Wave-Y bunların **hepsini** kapatır; kapanmadan başka hat açılmaz.

**Hat adı:** Wave-Y. Hedefler **Y0–Y8**. (Kural R3 ile çakışmasın diye "R" harfi
kullanılmadı.) BUG numaraları **#339**'dan, dersler **L68**'den devam eder.

---

## §0 — SABİT KURALLAR (her hedefte geçerli)

1. **R3 — disk kazanır.** Her iddianın arkasında bugün koşulmuş bir komut çıktısı olur.
   Kanıt yoksa satır **KANIT YOK** yazılır. Bellekten, özetten, rapordan konuşulmaz.
2. **Ölçüm bayatlar.** 4 Eylül raporundaki bir sayıyı bugün kullanmadan önce yeniden koş.
   (Bu turun dersi: 23 günlük bir DNS ölçümü bugünkü olgu sanıldı.)
3. **KULLANIM-GATE.** Yeşil test "tamamlandı" demek değildir. Bir kapı ancak
   **gerçekten kullanıldığı** kanıtlanınca kapanır — ekran çıktısı, curl, log satırı.
4. **Her yeni kapıya mutasyon testi.** Kapıyı kırması gereken en az 3 mutasyon yaz,
   hepsi kırmızı vermeli. Vermeyen kapı kapı değildir.
5. **"Kimse görmedi" demeden önce belgeleyen dosyayı ara.** (L67)
6. **Murat'a sorma.** Ölçebileceğin hiçbir şeyi sorma. Karar gerekiyorsa **seç, uygula,
   sonucu bildir** — Murat yalnızca veto eder. Tek istisna: para harcanması ve fiziksel
   telefon gereken adımlar (Y0-ödeme, Y3-PWA).
7. **Wave-K DONDURULDU.** Koç hattına Wave-Y kapanana kadar tek commit atılmaz.
   Wave-K'ye ait açık iş çıkarsa backlog'a yazılır, yapılmaz.
8. **Her hedef kapanışında** `uygulanan-fixler.md`'ye BUG kaydı + `docs/kalite-seruveni/`
   altına kapanış satırı. Defter yazılmadan hedef kapanmaz.

---

## §0.1 — İLK İŞ: DURUM DOĞRULAMASI (kod yazmadan önce)

```
git log -1 --format='%H %ad'          # çıpa 7486e9c mi, ilerledi mi
pytest tests/ -q --cov=app --cov-fail-under=93
npm test -- --run
curl -s <canlı>/api/meta              # canlı SHA ve yerel HEAD farkı
curl -s -o /dev/null -w '%{http_code}' <canlı>/api/health
wc -l .mcp-sync-pending.log
```

Çıkan sayıları Wave-Y ledger'ının başına yaz. Bunlar Wave-Y'nin **başlangıç ölçümüdür**;
Y8'de aynı komutlar tekrar koşulup kıyaslanacak.

---

## /goal Y1 — CANLI SÜRÜM DRİFT'İ SIFIRLANIR

> **Neden ilk:** B0'a bağlı DEĞİL. Altı kullanıcı 24 commit eski bir binada oturuyor;
> 4 Eylül'de bulunan 21 defektin hiçbir düzeltmesi onlarda yok. Mevcut Tailscale
> kurulumuna bugünkü HEAD'i basmak için hiçbir karar beklenmiyor.

**Tanım (done):**
- Canlı `/api/meta` build SHA'sı = yerel `main` HEAD.
- Deploy **`scripts/deploy.sh` ile** yapıldı (elle değil) ve çıktısı kayda geçti —
  bu, "deploy.sh koştu mu? KANIT YOK" satırını da kapatır.
- Deploy sonrası `scripts/live_gate.py` koştu, çıktısı kayıtlı.
- Göç durumu: canlı `alembic_version` = `c3d4e5f8a1b2` (veya sonrası), `alembic check`
  sonucu kayda geçti.
- **Deploy öncesi canlı DB yedeği alındı** ve yedeğin bayt boyutu + doğrulaması kayıtlı.
- Deploy sonrası duman testi: health 200 · ready 200 · giriş yapılıp bir işlem okundu.

**Yasak:** canlı DB'ye elle SQL. Şema değişikliği yalnız göçle.

---

## /goal Y2 — KESİNTİ KÖRLÜĞÜ BİTER (B6 tam kapanır)

> **Neden ikinci:** 3 Eylül'de **24,5 saatlik sessiz kesinti** yaşandı ve kimse fark
> etmedi (BUG #326/#328). Bundan sonraki her adım canlıya bağımlı; kör canlıya
> deploy etmek anlamsız.

**Tanım (done):**
- Makinenin **dışından** koşan bir erişilebilirlik kontrolü var (5 dk aralık, `/api/health`).
- Kesintide Murat'a **gerçekten ulaşan** bir alarm var. Kanıt: alarm bilerek tetiklendi
  (servis durduruldu) ve bildirim eline ulaştı — ekran/log çıktısı kayıtlı.
- Kesinti ve toparlanma bir yere yazılıyor; son 7 günün erişilebilirlik yüzdesi okunabiliyor.
- Mutasyon: izleme uç noktası bilerek 500 döndürüldü → alarm çaldı.
- B6 satırı 🟡 KISMİ'den ✅'ye geçti, kanıtıyla.

---

## /goal Y0 — B0 BARINDIRMA KARARI KAPANIR

> **Neden burada:** Y1/Y2 bunu beklemez, ama Y3–Y5 bekler. 24 gündür açık.
> **Murat'a soru olarak dönmeyecek.** Ölç, ölçütü uygula, seç, kur.

**Tanım (done):**
1. Karar notundaki ölçütler dosyadan okunur (`masterprompt-kapali-beta.md`,
   B0 karar notu). Ölçüt listesi rapora aynen yazılır.
2. En az üç seçenek için **bugünkü gerçek fiyatlar** ölçülür (VPS / PaaS / mevcut
   Tailscale+alan adı). Fiyat, bölge, yedekleme, TLS, "makine kapalıyken erişim" sütunlu tablo.
3. Ölçüte göre **tek bir seçenek seçilir ve gerekçesi yazılır.** Beraberlik varsa
   "en ucuz + geri dönülebilir olan" kazanır.
4. Karar `docs/architecture/adr-057-barindirma.md` olarak yazılır (ADR borcu §Y6'ya bakınız).
5. `masterprompt-kapali-beta.md`'deki B0 satırı "Yapılacak" → "Karar: <seçenek>, <tarih>".
6. **Murat'ın tek işi:** ödeme/alan adı satın alma adımı. Ona tek bir mesajda
   *ne alınacağı, nereden, ne kadar* verilir — seçenek listesi değil, **tek talimat**.

**Yasak:** seçenekleri Murat'a sorup beklemeye almak. Bu maddenin 24 gün açık kalma sebebi budur.

---

## /goal Y3 — YAYIN (B4) + CANLI DOĞRULAMA KAPILARI 9–12

**Tanım (done) — dördü de kanıtla kapanır:**

| Kapı | Kapanma kanıtı |
|---|---|
| **B4 yayın** | Kendi alan adı üzerinden HTTPS, geçerli sertifika, `/api/meta` doğru SHA. `deploy.sh` + `live_gate.py` yeni ortamda koştu. |
| **9 — PWA gerçek telefonda** | Telefondan açıldı, ana ekrana eklendi, çevrimdışı açılış denendi. Kanıt: ekran görüntüsü + `docs/kalite-seruveni/` altında not. *(Murat'ın telefonu gerekiyor — tek adımlık talimat ver.)* |
| **10 — Canlı SMTP (H11)** | Canlıdan gerçek bir davet/geri bildirim e-postası gönderildi ve **gerçek kutuya düştü**. Kanıt: gönderim logu + alınan e-postanın başlığı. |
| **11 — Yedekten geri yükleme provası** | Canlı yedek alındı → **ayrı** bir örneğe geri yüklendi → tablo sayısı + kullanıcı sayısı + son işlem tarihi canlıyla eşleşti. Prova adımları yazıldı. Canlıya dokunulmadı. |
| **12 — Hesap/veri silme yolu** | Canlıda gerçek bir test hesabıyla silme uçtan uca koşuldu; sonrasında o kullanıcıya ait satırlar **ölçülerek** yok gösterildi (tablo tablo sayım). KVKK metniyle tutarlılığı kontrol edildi. |

**Y3 kapanınca 15 kapının 15'i yeşil olmalı.** Olmuyorsa hangisinin niye açık kaldığı yazılır.

---

## /goal Y4 — GERÇEK KULLANICI SİNYALİ

> **Raporun en ağır bulgusu:** 13 Ağustos'tan beri sistemdeki tek etkinlik kurucununki.
> 5 davetliden 1'i hiç giriş yapmadı, 3'ü ilk gün sonrası dönmedi. Sebep **ölçülmedi** —
> DNS hipotezi bugün geçersiz. Bu, kodla kapatılacak bir madde değil.

**Tanım (done):**
- Y3 bittikten sonra 5 davetliye **yeni adresle** tek ve kısa bir mesaj gider
  (metni asistan aracı yazar, gönderme Murat'ta).
- En az **3 davetliden** cevap alınır: girdiler mi, neyi denediler, nerede takıldılar.
- Cevaplar `docs/kalite-seruveni/beta-geri-bildirim-<tarih>.md`'ye ham hâliyle yazılır.
- Çıkan her defekt BUG numarası alır. **Cevaplar tahminle doldurulmaz.**
- 7 gün sonra aynı etkinlik tablosu (kullanıcı × işlem × koç × son etkinlik) yeniden
  ölçülür ve 4 Eylül tablosuyla yan yana konur.

---

## /goal Y5 — DEFTER SENKRONU

**Tanım (done):**
- **Backlog:** çıpadan bu yana kapanan 60 BUG backlog'a işlenir. 164/251/81 dağılımı
  ölçülerek güncellenir. Kapanmadıysa neden kapanmadığı yazılır — toplu ✅ atılmaz.
- **MCP flush:** `.mcp-sync-pending.log` (255 satır ve büyüyor) boşaltılır, sıfırlanır.
  Tekrar birikmemesi için ya otomatik akıtma kurulur ya da defter kapatılıp kararı yazılır.
- **Belge bayatlığı (BUG #310 sınıfı):** `PROJE.md`, `PROJE.md`, `charter-kapali-beta.md`
  Wave-Y sonrası gerçekle uyumlu hâle getirilir; `scripts/belge_denetimi` yeşil kalır.
- **Ledger:** Wave-Y'nin kendi kapanış raporu `docs/kalite-seruveni/` altına yazılır.

---

## /goal Y6 — ADR BORCU KAPANIR

> Çıpadan bu yana **60 BUG kapandı, 7 kapı kuruldu, yeni bir hat açıldı, depo private
> yapıldı, geçmiş ikinci kez yeniden yazıldı — ve sıfır yeni ADR yazıldı.** Kararlar
> commit mesajlarında kalıyor.

**Tanım (done):** en az şu kararlar ADR'ye geçer (57'den itibaren):
- Barındırma kararı (Y0).
- Yedi kalite kapısının varlığı ve tavanların anlamı (ruff S=63, ölü kod=0, coverage≥93).
- FK sapması: SQLite'ta `alembic check` **kalıcı kırmızıdır**, ölçüm
  `tests/test_fk_sapmasi_kapisi.py` ile yapılır — ADR-013/036 sapmasının resmî kaydı.
- Depo görünürlüğü ve kişisel veri kapısının **kapsamı** (imaj değil, `git ls-files`).
- Milestone/tag sisteminin bırakılması (PROJE.md'de yazılı, ADR'de değil).

Her ADR: karar · bağlam · alternatifler · sonuç. Tek paragraflık ADR yazma.

---

## /goal Y7 — DEPO GÖRÜNÜRLÜĞÜ NİHAİ KARARI

**Tanım (done):**
- Depo public'e dönecek mi, dönmeyecek mi — **karar verilir ve ADR'ye yazılır.**
- Public'e dönülecekse önce: kişisel veri kapısı tüm izlenen dosyaları tarıyor mu
  (sadece imaj değil) **ölçülür**; yasak desen listesine hesap numarası, IBAN, TCKN,
  telefon, adres desenleri eklenir; mutasyon 3/3.
- `scripts/sir_taramasi` + kişisel veri kapısı **CI'da zorunlu adım** olur; grep ile
  kanıtlanır (`.github/workflows/`).
- Dönülmeyecekse: LICENSE/telif ve rezan.dev bağlantısı bu duruma göre düzeltilir.

---

## /goal Y8 — WAVE-Y KAPANIŞ KAPISI

Wave-Y ancak şunların **hepsi** doğruyken kapanır:

- [ ] Canlı SHA = `main` HEAD (drift 0)
- [ ] Dışarıdan izleme + gerçek alarm çalıştı, mutasyonla doğrulandı
- [ ] B0 kararı yazılı, ADR'de
- [ ] Kendi alan adı üzerinden HTTPS, B4 kapalı
- [ ] Kapı 9, 10, 11, 12 kanıtla kapalı → **15/15 yeşil**
- [ ] En az 3 davetliden gerçek cevap alındı ve kayda geçti
- [ ] Backlog ölçülerek güncellendi, MCP defteri sıfır
- [ ] En az 5 yeni ADR yazıldı
- [ ] Depo görünürlük kararı yazılı, kapı kapsamı CI'da zorunlu
- [ ] Tam süit yeşil, coverage ≥ %93, yedi kapı geçildi (§0.1 komutları yeniden koşuldu)

Kapanışta `docs/kalite-seruveni/wave-y-kapanis-<tarih>.md`: başlangıç ölçümü ↔ bitiş
ölçümü kıyas tablosu + hangi hedefin kaç günde kapandığı + ders numaraları (L68→).

---

## §9 — SIRALAMA VE BAĞIMLILIK

```
Y1 (drift)  ─┐
Y2 (izleme) ─┴─> bağımsız, HEMEN başlar

Y0 (B0 kararı) ──> Y3 (B4 + kapı 9-12) ──> Y4 (kullanıcı sinyali)

Y5 (defterler) · Y6 (ADR) · Y7 (depo) ──> paralel, Y8'den önce biter

Y8 = kapanış kapısı
```

**Aynı anda en fazla bir hedef açık kalır.** Y1 kapanmadan Y2'ye geçilmez.
Bir hedef kapanmadan yenisi açılırsa Wave-Y bu raporun teşhis ettiği hatayı
tekrarlamış olur: **25 günün 7'sinde çalışıp son üçünü yeni bir hatta harcamak.**

---

## §10 — YASAKLAR

- Wave-K'ye commit (Y8'e kadar).
- Yeni özellik. Wave-Y'de sadece **kapatma** işi var.
- Kapsam büyütme: "madem buradayız şunu da düzeltelim" → backlog'a yaz, geç.
- Kapı tavanını yükselterek kapı geçmek (ruff S 63→64 vakası, BUG #338).
- Canlıya elle müdahale; her şey `deploy.sh` üzerinden.
- Kanıtsız ✅. Kanıt yoksa **KANIT YOK** yazılır ve hedef açık kalır.
