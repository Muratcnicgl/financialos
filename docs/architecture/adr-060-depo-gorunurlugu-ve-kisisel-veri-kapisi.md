# ADR-060 — Depo private kalır, yanına ÜRETİLMİŞ bir vitrin açılır; kişisel veri kapısı imajı değil DEPOYU tarar

- **Durum:** Kabul edildi (4 Eylül 2026, Wave-Y / Y7)
- **Bağlam kodları:** BUG #338 (kapı yanlış yüzeyi koruyordu), BUG #310 (belge bayatlığı)
- **İlgili:** ADR-058 (kapılar ve tavanlar), Wave-Y masterprompt §Y7

## Bağlam

3 Eylül 2026'da bir kişisel veri kapısı bir commit'i durdurdu; kapsamı incelenirken
**deponun `visibility: public` olduğu** ölçüldü (GitHub API, kimliksiz sorgu). İzlenen
862 dosyada iki gerçek kredi hesap numarası, 15 dosyada gerçek e-posta, 96 dosyada banka
adları vardı. Depo private yapıldı, hesap numaraları hem çalışma ağacından hem **geçmişten**
temizlendi (`git-filter-repo`, 671→671 commit, ağaç hash'i birebir korunmuş).

**Kapının kök nedeni:** `test_imaj_kisisel_veri` "kişisel veri sızmasın" derdiyle yazılmıştı
ama kapsamı **Docker imajıydı** — 862 izlenen dosyanın 186'sı. Hesap numaralarını taşıyan
`scripts/coach_altin.py` imaja hiç girmiyordu. **Koruma vardı, yanlış yüzeye bağlıydı.**

## Karar 1 — Kapı, dağıtım yüzeyinin TAMAMINI tarar

`tests/test_depo_kisisel_veri_kapisi.py` `git ls-files` ile **izlenen tüm metin
dosyalarını** tarar. İki kademe:

* **SERT (tavan 0):** hesap numarası · IBAN · kart numarası. Tek başına kimliklendirici;
  hiçbir fixture bunlara ihtiyaç duymaz.
* **RATCHET (dondurulmuş):** e-posta **15** · banka adı **96**. Çoğu aylar öncesinden;
  hepsini bir turda temizlemek o turun işi değildi — ama **sayı artamaz**.

**Muafiyet DOSYAYA değil DEĞERE bağlıdır.** Sert kapı 5 eşleşme buldu ve beşi de sahteydi
(standart örnek IBAN, `1234 5678 9012 3456`). *"Şu dosyaları atla"* demek kapıyı
körleştirirdi: aynı dosyaya bir gün gerçek bir IBAN girse görülmezdi (L67).

## Karar 2 — Depo PRIVATE kalır; görünürlük ihtiyacı VİTRİN deposuyla karşılanır

Murat'ın gerekçesi meşru: CV'sinde GitHub'ı ve bu proje anılıyor, projenin görünmemesi
amaca aykırı. Ama asıl depoyu açmak, ölçülen şu bedeli getirir:

| Ne | Nerede |
|---|---|
| Gerçek e-posta | 15 dosya |
| Banka ilişkileri | 96 dosya |
| Gerçek bakiye / borç / maaş rakamları | 15 dosya |
| **Aynısı** | **671 commit'lik geçmişte** |

Yani "bundan sonra özel veri commit etme" ileriye dönük çözer, **geçmişi çözmez**: açmak,
iki hafta içinde **üçüncü** `git-filter-repo` + force-push demektir.

**Karar: asıl depo private kalır. Yanına ayrı bir PUBLIC vitrin deposu açılır** — kendi
geçmişiyle, sıfırdan, asıl deponun geçmişi hiç aktarılmadan.

## Karar 3 — Vitrin ELLE YAZILMAZ, ÜRETİLİR

Elle yazılmış bir vitrin bu deponun kayıtlı hastalığına yakalanır: **BUG #310** — belgenin
işaret ettiği şey diskte yoktur, ve kimse fark etmez. Üretici gerçek depoyu **ölçer**:
test sayısı, coverage, kapı adları ve tavanları, ADR başlıkları, mutasyon skorları.
Sayı koşumdan gelir; vitrin bayatlayamaz.

## Karar 4 — Üretici ALLOWLIST ile çalışır, denylist ile DEĞİL

Üretici bir **private → public boru hattıdır**. Denylist ("hesap no, IBAN, e-posta, banka
adı, tutar ara") yalnız **düşünülen** sızıntıyı yakalar. Sızıntı düşünülmeyenden gelir:

* commit mesajları · mutlak dosya yolları (`C:\Users\<ad soyad>\...`)
* ADR gövdelerinde geçen gerçek rakamlar
* `uygulanan-fixler.md`'nin 1.070 satırındaki bakiye örnekleri
* hata çıktılarına gömülü fixture verisi
* `live_gate` uyarısının yakaladığı **şahsi destek adresi**

**Bu yüzden üretici yalnızca açıkça izin verilmiş alanları yayar; listede olmayan her şey
varsayılan olarak düşer.** Denylist "kötü olanı ara", allowlist "iyi olanı geçir" — ikincisi
bilinmeyene karşı da korur.

## Karar 5 — Kapı ÜRETİMDE değil, PUSH'tan hemen önce koşar

Üretilen dosyalar diskteyken taranır; temizse yayınlanır. Mutasyon: vitrine bilerek gerçek
bir rakam enjekte edilir → kapı kırmızı vermelidir.

## Alternatifler

* **Asıl depoyu temizleyip açmak:** 114 dosya + 671 commit'lik geçmiş yeniden yazımı.
  Üstelik testlerdeki gerçek rakamlar **kanıttır** (regresyon çıpası); temsili değerlerle
  değiştirmek defterin kanıt değerini zayıflatır.
* **Yalnız kodu yayınlamak, defterleri tutmak:** ölçüldü — gerçek tutarların çoğu
  `tests/` içinde; bu seçenek de temizliğin yarısını gerektirir ve projenin **en ayırt
  edici** parçasını (ölçüm defterleri) dışarıda bırakır.
* **Private kalıp kimseye göstermemek:** CV amacını karşılamaz.

## Sonuç

Vitrinde gösterilecek asıl şey 3.486 test değil; **ratchet kapısının değişikliği sekiz kez
reddedip sekizinde de haklı çıkması**, **mutasyonun kapının kendi kör noktasını buldurması**
ve **yanlış teşhislerin ölçümle çürütülüp kayda geçirilmesidir**. Bunlar hikâye değil,
depoda commit'li kanıttır — ve kişisel rakamları çıkarılmış üretilmiş özet tam olarak
bunu taşır.
