# MASTERPROMPT — KOÇ ZEKÂSI HATTI (Wave-K)

> Kardeş belge: `masterprompt-publish.md` (PUBLISH YOLU / P0-P9). Bu belge onun yerine
> GEÇMEZ, yanında durur. Publish hattı "uygulama yayına çıkabilir mi?" sorusunu yönetir;
> bu hat **"koç yeterince iyi mi?"** sorusunu yönetir. İkisi bağımsız ilerleyebilir.
>
> **Tek doğruluk kaynağı: §10'un başındaki ⏸️ KALDIĞIMIZ YER bloğu (3 Eylül 2026).**
> Yeni oturum oradan devam eder; §9.0-§9.4 tarihsel ölçüm kaydıdır.

---

## §0. GÖREVİN TANIMI (tek cümle)

FinancialOS'un koçunu, Türkiye şartlarında finansal sıkışma yaşayan bir insana **ölçülü,
gerekçeli ve insani** yol gösterebilecek seviyeye çıkarmak — ve bu seviyeyi bir daha
düşmeyecek şekilde ÖLÇÜLERE bağlamak.

**Vizyon (Murat, 1 Eylül 2026):** İnsanların verilerini girip takip edebileceği; Türkiye'nin
ekonomik zorluklarında onlara destek olan; çaresiz çıkmazlara girmelerini önleyecek yollar
bularak maneviyatlarını koruyan bir uygulama. Koç, bu vizyonun taşıyıcısıdır — geri kalan
her şey (API, UI, testler) bu koçun altyapısıdır.

---

## §1. DEĞİŞMEZ KURALLAR

`masterprompt-publish.md` §1 ve §1.3'teki L1-L52 ders-kuralları bu hatta da **aynen**
geçerlidir. Bu hatta özel EK kurallar:

- **K-KURAL 1 — VARSAYIM YASAK.** Koç kalitesi hakkında bir iddia, ancak bir KOŞUM ÇIKTISI
  ile desteklenirse yazılır. "Daha iyi oldu" değil, "%71,4 → %X" yazılır.
- **K-KURAL 2 — YAPAY ZEKÂ HALÜSİNASYONU YASAK.** Model adı, fiyat, limit, teknik yetenek:
  hepsi belgeden/ölçümden doğrulanır. Ezberden model kimliği yazmak yasaktır.
- **K-KURAL 3 — ÖNCE PLANLA.** Sıra: **araştır → doğrula → planla → uygula → ölç → kaydet.**
- **K-KURAL 4 — FİKİR ÇALMA YASAĞI.** Rakip/benzer ürünler yalnız **kavramsal ders** için
  incelenir (hangi problemi nasıl çerçevelemişler). Metin, prompt, kod, marka, akış
  KOPYALANMAZ. Alınan her ders, kaynağıyla birlikte §5'te kaydedilir. Ürün Murat'ın kendi
  fikridir; buradaki iş onu taklit etmek değil, seviyesini yükseltmektir.
- **K-KURAL 5 — PROMPT ŞİŞMESİ BİR REGRESYONDUR.** Sistem promptuna satır eklemek, bir
  kusuru düzeltmenin VARSAYILAN yolu değildir. Ekleme yapılacaksa §3/K2'deki token bütçesi
  kapısı ihlal edilmemelidir.
- **K-KURAL 6 — İNSANİ BOYUT ÖLÇÜLMEDEN "TAMAM" DENMEZ.** "Çaresiz çıkmaza girmesini
  önlemek" bir slogan değil, K7'de ölçülen bir davranıştır.

---

## §2. "KOÇ YETERLİ" TANIMI (Definition of Done)

Üç basamak. Her basamak ÖLÇÜLEBİLİR bir eşiktir; sözle geçilemez.

### Basamak K-A — GÜVENİLİR (yalan söylemiyor)
- `grounded` kriteri **8/8 senaryoda geçer** (koç cockpit'te olmayan rakam üretmez).
- `no_fake` + `no_fake_niyet` **8/8**.
- Deterministik eval **geçerli koşum** olarak tamamlanır (hiçbir senaryoda "sağlayıcı
  cevap veremedi" bayrağı yok).

### Basamak K-B — YETKİN (doğru düşünüyor)
- Deterministik kriter oranı **≥ %95**.
- LLM-hakem (`coach_judge`) MUHAKEME/ÇERÇEVE/RİSK ölçütlerinde **≥ %80 geçti**, öz-değerlendirme
  yanlılığı işaretlenmemiş (hakem, değerlendirilenden FARKLI sağlayıcı).
- Bu belgedeki **altın senaryo seti** (§4.2) üzerinde koç, insanın elle yaptığı analizin
  adımlarını üretebiliyor: veriyi çeker, çelişkiyi bulur, aritmetiği yapar, seçenekleri
  kıyaslar, tek eyleme indirir.

### Basamak K-C — İNSANİ (iyi geliyor)
- K7 ölçütleri sağlanır: sıkışma anında panik üretmeden somut çıkış yolu, kullanıcının
  kendini kötü hissetmesini gerektirmeyen dil, ve "yapamıyorum" dediği anda ölçek küçültme.

---

## §3. FAZ HARİTASI (K0-K7)

### K0 — BASELINE ✅ TAMAMLANDI (1 Eylül 2026)
Bugünün ölçümü alındı. Sonuçlar §9.0'da. Bu faz tekrar edilmez; sonraki her faz kendi
öncesi/sonrası ölçümünü alır.

### K1 — SAĞLAYICI HATTININ ONARIMI ✅ **PARASIZ ONARILDI (1 Eylül 2026 akşamı)**

**Zincir iki bacaklı:** `Gemini(gemini-2.5-flash-lite) → OpenRouter(minimax/minimax-m3:free)
→ Cerebras(402) → Groq(413)`. `.env` ayarıyla koşulan eval: **%80,0 model sözleşmesi /
%82,9 kullanıcıya giden, `gecerli=True`, 0 ölü çağrı** — K0'da %71,4 ve GEÇERSİZ'di.

**Nasıl, para harcamadan:** "kredi lazım" sanılan `402`'nin kök nedeni ölçüldü ve başka
çıktı — `OpenRouterProvider.DEFAULT_MODEL` kataloğdan KALKMIŞ bir model adıydı
(`meta-llama/llama-3.3-70b-instruct:free`); istek ücretli hâline yönleniyor ve $0 bakiyede
402 dönüyordu. Hesapta sorun yoktu (`is_free_tier=True`, `usage=0`). **BUG #315.**
Yeni varsayılan 18 ücretsiz model taranıp beşi gerçek promptla denenerek seçildi.
Bunu görebilmek **BUG #314** sayesinde mümkün oldu: zincirdeki sağlayıcılar artık tek tek
seçilip ölçülebiliyor (önceden Cerebras/OpenRouter/Together/DeepInfra hiç koşulamıyordu).

**Ölü kalan halkalar (parayla açılır, İNSAN-KAPISI, ACELE YOK):** Cerebras `402`,
Anthropic `400` (kredi yok). Groq `413` — parayla DEĞİL, K2 ile açılır (istek < 8.000 tok).

**Eski durum (tarihsel kayıt):**
Koç şu an tek bacaklı: zincirin dört halkasından üçü ölü.
- OpenRouter: `402 payment_required`
- Anthropic: `400 credit balance too low`
- Groq: `413` — istek (12.364 tok) ücretsiz katman TPM limitinin (8.000) üstünde
- Ayakta kalan tek halka: `gemini-2.5-flash-lite`

**BÜTÇE KISITI (Murat, 1 Eylül 2026): ŞU AN AYRILABİLECEK PARA YOK.** Bu bir erteleme
değil, bir TASARIM KISITIDIR ve hattın sırasını belirler:
- Parayla çözülecek her şey **hazırlanır ama etkinleştirilmez** — vakti gelince tek adımda
  açılacak hâlde bırakılır (BUG #313 tam olarak bunu yaptı: `ANTHROPIC_MODEL` yazıp
  `LLM_PROVIDER=anthropic` demek artık yeterli; önceden bu yol kırıktı).
- **Zincir PARASIZ onarılabilir ve yolu K2'dir:** Groq'un ücretsiz katmanı 8.000 TPM;
  koçun isteği 12.364 token. İstek 8.000'in altına inerse **Groq tek başına geri açılır**
  ve zincir iki bacaklı olur. Yani prompt bütçesi işi yalnız bir "temizlik" değil, aynı
  zamanda **sağlayıcı onarımının parasız yoludur**.
- Kalan iki halka (OpenRouter `402`, Anthropic kredi) parayla açılır; ikisi de §8'de
  İNSAN-KAPISI olarak bekler.

**Çıktı:** zincirin gerçek durumu tabloya yazılır; hangi halkanın parayla, hangisinin kodla
onarılacağı ayrılır.
**Ayrıca bir KOD hatası var:** `_build_anthropic()` modeli `LLM_MODEL`'den okuyor; o da
`gemini-2.5-flash-lite`. `LLM_PROVIDER=anthropic` yapan operatör, Anthropic'e Gemini model
adı gönderir. Sağlayıcıya-özel model değişkeni gerekir.

### K2 — PROMPT BÜTÇESİ (yara dokusunu mimariye çevir)
Ölçüm: V3 promptu 19.444 karakter / 317 satır / ~8.838 token = her isteğin **%71'i**.
39 adet 🔴 yasak. Kullanıcının gerçek finansal durumuna kalan pay yalnız %29.
- **Hedef:** sistem promptu ≤ %40; kullanıcı bağlamı ≥ %60.
- **Yöntem:** her 🔴 yasağı sınıflandır — (a) kodla/kapıyla zaten korunuyor mu? (b) yalnız
  zayıf modelde mi gerekiyor? (c) gerçekten sözleşme mi? (a) ve (b) prompttan çıkar.
- **Kapı:** `tests/` altında prompt-bütçesi kapısı; token tavanı aşılırsa CI kırmızı.
- **Bu faz K5'i mümkün kılar** (küçük istek = güçlü model erişilebilir + önbellek işe yarar).

### K3 — GROUNDING ⚠️ **TEŞHİS ÇÜRÜDÜ, DEDEKTÖR ÖNCE DÜZELTİLDİ**

**Girerken teşhis:** "koç uydurma tutar üretiyor, kod görüyor ama zorlamıyor → zorlayalım."
Mantıklıydı, ölçüme dayanıyordu — **ve yanlıştı.**

**Ölçüm (üretim, `reasoning_traces`):** grounding ölçülen 14 cevabın 6'sı (%43) ihlalli.
İşaretlenen tutarlar (`573.52`, `625.85`, `109.9`, `747.22`) incelendi: uydurma değil,
**gerçek tutarların kuyrukları**. İki hipotez kuruldu (desen parçalıyor / float dönüşümü
bozuk), ikisi de ÖLÇÜMLE ÇÜRÜDÜ. Tahmin bırakılıp ihlalli cevabın METNİNE bakıldı.

**Kök neden — BUG #316:** koç boşluklu binlik ayıraç kullanıyor (`4 573,52 TL`); dedektör
yalnız noktayı tanıyordu. Aynı doğru cevap noktalı yazımda `ok=True`, boşluklu yazımda
`ok=False`. Düzeltildi (18 test, mutasyon 3/3). Canlı korpusta 11 cevabın 4'ünde değerler
düzeldi; en ağırı `5 000 TL` → **0,00 TL** okunmasıydı.

**Bugün gerçekleşen sessiz zarar:** doğru cevaplarda güven 0.4'e düşürülüyordu ve eval'in
`grounded` kriteri aynı dedektöre bağlı olduğu için **kalite oranımız olduğundan kötü**
görünüyordu.

**K-DERSİ: bir ZORLAMA, ancak ÖLÇÜTÜ kadar iyidir; ölçüt doğrulanmadan zorlama eklenmez.**
Teşhis sorgusuz uygulansaydı koçun DOĞRU cevapları engellenir/damgalanırdı — kullanıcıya
aktif zarar.

**Kalan iş:** dedektör düzeldiğine göre **gerçek** halüsinasyon oranı yeniden ölçülecek
(üretimde yeni cevaplar biriktikçe). Zorlama tasarımı — blok / cümle silme / görünür
işaretleme / yeniden üretim — ancak o sayı bilindikten SONRA seçilir. Ön eğilim: görünür
işaretleme (dürüstlük, kullanışlılığı yok etmeden); ama karar ölçüme bağlı.

### K4 — ARAŞTIRMA TURU (fikir çalmadan feyz)
K-KURAL 4 altında. Üç kol:
1. **Ürün kolu** — Türkiye ve dünyadaki kişisel finans/koçluk ürünleri: hangi problemi nasıl
   ÇERÇEVELEMİŞLER (kopyalanan şey yok, öğrenilen çerçeve var).
2. **Teknik kol** — açık kaynak: LLM eval harness'ları, grounding/atıf teknikleri, ajan
   hafızası, araç kullanımı. GitHub repoları ve makaleler.
3. **Kuram kolu** — **stigmerji** dahil. Ön not: bu projede stigmerji ZATEN çalışıyor —
   `masterprompt-*.md` §KALDIĞIMIZ YER + `uygulanan-fixler.md` defteri + L-dersleri, hepsi
   ortama bırakılmış iz üzerinden koordinasyon. K4'te sorulacak asıl soru: aynı mekanizma
   KOÇUN KENDİSİNE nasıl taşınır — koç, kullanıcının davranışına bıraktığı izleri okuyup
   kendi davranışını değiştirebilir mi?
Her bulgu §5'te kaynağıyla kaydedilir; uygulanacaklar K5-K7'ye madde olarak düşer.

### K5 — MODEL VE YÖNLENDİRME
K2 bittikten SONRA ölçülür — önce değil; büyük istekle yapılan model kıyası yanıltıcıdır.
- Aynı eval, aynı prompt, farklı modeller yan yana (`--saglayicilar`).
- Prompt caching: sabit önek önbelleğe alınır. LLM-002 kararı ("Gemini'de kazanç ölçülemez")
  sağlayıcı değişirse gerekçesini kaybeder → K2 sonrası YENİDEN ölçülür.
- İş bazlı yönlendirme: sınıflandırma ucuz modele, muhakeme güçlü modele.

### K6 — HAFIZA VE SÜREKLİLİK
`coach_memories` (30 kayıt) ve `coach_insights` (37 kayıt) canlıda var. Ölçülecek: koç
gerçekten hatırlıyor mu, yoksa kayıt yazıp okumuyor mu?

### K7 — İNSANİ BOYUT (vizyonun kalbi)
Basamak K-C'nin ölçütleri burada tanımlanır ve senaryolaştırılır. Örnek senaryo sınıfları:
gelirin giderden az olduğu ay · kart limiti dolmuşken gelen zorunlu gider · borcun
ödenemeyeceğinin anlaşıldığı an · kullanıcının "yapamıyorum" dediği an.

---

## §4. YÜRÜTME PROTOKOLÜ

### §4.1 Her görev için
1. §9.0'ı oku (kaldığımız yer).
2. Görevin ölçümünü ÖNCE al (öncesi sayısı).
3. Uygula.
4. Ölçümü TEKRAR al (sonrası sayısı).
5. §9.0'ı ve §10'u güncelle. Ders çıktıysa L-numarası ile `masterprompt-publish.md` §1.3'e ekle.

### §4.2 ALTIN SENARYO SETİ (K-B ölçütü)
1 Eylül 2026'da insan tarafından yapılan gerçek analiz, koçun ulaşması gereken çıta olarak
buraya sabitlenir. Koç şunları yapabilmelidir:
- **G1** — Kredi bakiyesinin "kalan taksit toplamı" mı "anapara" mı olduğunu ayırt etmek;
  karıştırılırsa borç motoru asla-bitmez üretir.
- **G2** — Kredi kartında "son ekstreden kalan borç 0" ile "güncel borç 8.221,13" farkını
  görmek ve ikincisini yükümlülük saymak.
- **G3** — Ay içi nakit takvimi kurup açığı bulmak (kaynak 15.663,59 − çıkış 15.078,25).
- **G4** — Yatırım getirisini borç kapatma getirisiyle AYNI birimde kıyaslamak (stopaj
  sonrası aylık %): fon %3,15 · Enpara %2,52-2,66 · kredi %4,25-5,78.
- **G5** — "Bu para zaten 14 Eylül'deki kart ödemesine ait" sonucuna varmak; yani soruyu
  reddetmek yerine ÇERÇEVEYİ düzeltmek.
- **G6** — Asıl kaldıracı (aylık 8.221 TL kart harcaması) tespit edip yatırım tartışmasının
  ölçeğini ona göre konumlandırmak — kullanıcıyı suçlamadan.

### §4.3 Yasak gerekçeler (görülürse görev reddedilir)
- "Prompt'a bir satır daha ekleyelim" (ölçüm yoksa — K-KURAL 5 ihlali)
- "Şimdilik böyle kalsın, sonra ölçeriz"
- "Muhtemelen düzeldi"
- Rakip üründen metin/prompt/kod aktarımı (K-KURAL 4 ihlali)

---

## §5. ARAŞTIRMA DEFTERİ (K4 — kaynaklı, yalnız eklenir)

*(K4 başladığında doldurulacak. Format: `[tarih] KAYNAK → ÖĞRENİLEN ÇERÇEVE → FinancialOS'a
uygulanabilir madde`. Kopyalanan içerik değil, çıkarılan ders yazılır.)*

---

## §6. RİSK KAYDI (canlı)

| # | Risk | Durum |
|---|---|---|
| R1 | Sağlayıcı zincirinin 4 halkasından 3'ü ölü → koç tek modele bağımlı, o da en zayıfı | AÇIK (K1) |
| R2 | Prompt şişmesi kısır döngü kuruyor: her düzeltme sonrakini zorlaştırıyor | AÇIK (K2) |
| R3 | ~~Koç cockpit'te olmayan rakam üretiyor (`grounded=-`)~~ **PREMİS ÇÜRÜDÜ (3 Eyl):** 13 düşüşün 13'ü okundu, **gerçek uydurma 0**. Risk yön değiştirdi → **dedektör yanlış beraat veriyor (ölçülen tesadüf yüzeyi %10,7)** | DEĞİŞTİ — bkz. §9.4 |
| R4 | Eval üç haftadır koşulmamıştı; kalite sessizce %82,9 → %71,4 düştü | AZALDI — K0 ile yeniden ölçüldü; kalıcı çözüm düzenli koşum |
| R5 | Güçlü modele geçiş maliyeti (Opus 5 tek istek girdi ≈ $0,062) K2 yapılmazsa sürdürülemez | AÇIK (K2→K5) |

---

## §7. KAPSAM DIŞI (bilinçli)

- Publish hattı (P0-P9) — kardeş belgede.
- Frontend statik analizi (ayrı açık iş).
- Yeni ÜRÜN özelliği eklemek. Bu hat mevcut koçu iyileştirir, yenisini icat etmez.

---

## §8. İNSAN-KAPISI (yalnız bunlar Murat'a delege edilir)

- Sağlayıcı ödemesi / kredi yükleme / plan yükseltme kararları (K1).
  **DURUM (1 Eyl 2026): BÜTÇE YOK — bu kapı KAPALI ve öyle kalacak.** Hiçbir faz bu kapının
  açılmasını BEKLEMEZ; parayla çözülecek işler "hazır ama etkin değil" hâlde bırakılır.
  Zincirin parasız onarım yolu K2'dir (istek < 8.000 token → Groq ücretsiz katmanı açılır).
- Aylık LLM bütçesi tavanı (K5).
- Ürün vizyonuna dair değer yargıları (K7'de dilin sınırları).

---

## §9. DURUM TABLOSU

### §9.0 KALDIĞIMIZ YER — 1 Eylül 2026

**AKTİF FAZ: K-B (muhakeme kalitesi) — bkz. §9.1.** K0/K1/K2 turları aşağıda.

**K0 BASELINE — ölçülen (kanıt: `python -m scripts.eval_runner`):**

| Ölçüm | Değer |
|---|---|
| Deterministik kriter | **25/35 = %71,4** |
| Tam geçen senaryo | **3/8** |
| Koşum geçerliliği | **GEÇERSİZ** (1 senaryoda sağlayıcı cevap veremedi) |
| Önceki kayıt (10 Ağu, `data/eval_runs.jsonl`) | %82,9 (Fallback) |
| Başarısız kriterler | `grounded` ×2 · `uslup` ×4 (SIZ_HITABI ×2, IC_JARGON ×1) · `action` ×1 · `cevapladi` ×1 |
| Sistem promptu | 19.444 kar / 317 satır / ~8.838 token / 39 🔴 |
| İstek boyutu (Groq ölçümü) | **12.364 token** — prompt %71, kullanıcı bağlamı %29 |
| Sağlayıcı zinciri | Gemini ✅ · OpenRouter ❌402 · Anthropic ❌400 (kredi yok) · Groq ❌413 (TPM 8k) |
| LLM-hakem skoru | HİÇ ALINMADI |

**K1 İLERLEMESİ (aynı gün):**

| İş | Durum |
|---|---|
| `_build_anthropic()` model-değişkeni hatası | ✅ **KAPANDI — BUG #313.** Tek kaynak `saglayici_modeli()`; 9 test, mutasyon 3/3. Cerebras ve OpenRouter de artık sabitlenebiliyor (önceden model seçimi HİÇ yoktu). `docs/dev-commands.md` `.env` şeması düzeltildi. |
| Sağlayıcı zinciri tablosu | ✅ Ölçüldü ve yukarıya yazıldı |
| OpenRouter 402 / Anthropic kredi | ⛔ **İNSAN-KAPISI (§8)** — Murat'ın ödeme kararı bekleniyor |
| Groq 413 (TPM 8.000 < istek 12.364) | ⛔ Parayla DA çözülür ama **doğru çözümü K2'dir**: istek küçülürse ücretsiz katman yeter |

**K2 İLERLEMESİ (aynı gün) — AKTİF FAZ ARTIK K2:**

| İş | Durum |
|---|---|
| Prompt bütçesi kapısı (gerileme sayacı) | ✅ **KURULDU.** `tests/test_prompt_butcesi_kapisi.py`. İki eksen: karakter ≤ 19.444, 🔴 ≤ 39. Üçüncü test kazanım kilidi. Mutasyon 3/3, üçü de doğru eksende; cp1254'te de yeşil (L66). **Şişme artık sessizce devam edemez.** |
| Yasakların kodla eşleştirilmesi | ✅ Ölçüldü — aşağıya bak |
| Üslup kurallarının çalışma anında ZORLANMASI | ✅ **KISMEN — bilgi taşımayan dört madde.** `uslup_kurallari.dolgu_temizle()` `_postprocess_report`'a bağlandı; DALKAVUKLUK/DOLGU/BOS_TESELLI/NUTUK içeren cümleler artık kullanıcıya ULAŞMIYOR. 44 test, mutasyon 3/3. Kapı iki kez kendi kör noktasını buldu ve düzeldi. |
| `SIZ_HITABI` onarımı | ✅ **KAPANDI — deterministik morfolojik dönüşüm.** `siz_hitabi_onar()`: `n[ıiuü]z → n`, hem fiil hem iyelik ekini çözer. Sıfır ek maliyet. Ölçüm: ihlal korpusu 4/4 düzeldi · 16/16 meşru örnek bozulmadı · 10/10 tuzak kelime güvenli · **canlı korpusta 5/11 cevap onarıldı, hepsinde kalan ihlal YOK, kelime sayısı değişmedi**. 44 test, mutasyon 3/3 — ve mutasyon iki tasarım hatası buldurdu (uydurma istisna; kelime-başı kuralının sessiz yanlış negatifi). |
| `IC_JARGON` onarımı | 🟡 AÇIK — bilgilendirici cümlenin içinde, biçimsel dönüşümü yok; yeniden üretim ister. Canlı korpusta 1/11. |
| Emir kipi kalıntısı | 🟡 AÇIK — `ediniz → edin` (2. tekil "et" olmalı). Dedektör yakalamıyor, yani **ölçülemeyen** kalıntı. Fiil gövdesi analizi ister. |
| Promptun kırpılması | 🟡 AÇIK — zorlamadan SONRA. Kırpılabilir hâle gelen bloklar ≈ 593 token. |

**K2'NİN ANA BULGUSU — kural kodda var, ama yalnız ölçülüyor:**
`app/uslup_kurallari.ihlaller()` altı üslup kuralını (`SIZ_HITABI`, `NUTUK`, `DOLGU`,
`IC_JARGON`, `DALKAVUKLUK`, `BOS_TESELLI`) deterministik tespit ediyor. Çağrı yeri arandı:
`sahte_niyet_iddiasi_var` çalışma anında **onarıyor**, `sahte_tamamlama_iddiasi_var`
**retry tetikliyor**, `propose_sunulsun_mu` **tool eşiğini kapatıyor** — ama `ihlaller()`
**yalnız `coach_eval.py`'de** geçiyor. Zincir: prompt "yapma" der → model yapar → eval
"yaptın" der → **arada düzelten hiçbir şey yok.** K0'daki `SIZ_HITABI` ×2 / `IC_JARGON` ×1
tam buradan geçti. Bu, `docs/architecture.md`'deki *"LLM'in prompt'ına güvenilmez, kod
seviyesinde bloklanır"* ilkesinin üsluba uygulanmamış hâlidir.

**K2 SONRASI EVAL — KARŞILAŞTIRMA YAPILAMADI (dürüst kayıt):**
Koşum sonucu 23/35 = %65,7, ama harness'in kendi bayrağıyla **GEÇERSİZ**: bu kez **2**
senaryoda sağlayıcı hiç cevap veremedi (K0'da 1'di). %71,4 → %65,7 düşüşünü ölen ikinci
senaryo açıklıyor, değişiklikler değil. **Sağlayıcı zinciri onarılmadan (K1 insan-kapısı)
bu metrik öncesi/sonrası ölçümü için KULLANILAMAZ.** K2'nin etkisi bu yüzden doğrudan
canlı korpusta ölçüldü: 11 cevabın 5'i onarıldı, 0 yanlış pozitif.

**İKİ ORAN — ✅ KAPANDI (aynı gün).** `uslup` kriteri onarılan ihlali de düşürünce metrik
**modelin sözleşmesini** ölçmeye başladı, kullanıcının aldığı çıktıyı değil; tek sayı
ikisini birden temsil edemiyordu. `score_result(..., kullanici_gozu=)` eklendi ve harness
artık **iki oran** raporluyor:
- `pass_rate` → **MODEL SÖZLEŞMESİ** (varsayılan; ürünün onardığı ihlaller de düşürür).
  Regresyon ağı budur, BUG #277'nin persona kapısı buna bağlıdır.
- `pass_rate_kullanici` → **KULLANICIYA GİDEN ÇIKTI** (yalnız görünen metin).
İkisinin FARKI "ONARIM KAZANCI" satırı olarak basılır. Ek LLM çağrısı yok — aynı koşum
iki kez puanlanır (BUG #278'in dersi: ikinci geçiş BAŞKA cevapları puanlar).
Varsayılanın katı olan olması bilinçli (L36): model regresyonunu kaçırmak, kazanımı geç
fark etmekten ağırdır. Mutasyon 2/2 — varsayılan gevşetilince persona kapısı da düşüyor.

**SIRADAKİ SOMUT ADIM — K2 ikinci hamle: ÖNCE ZORLA, SONRA KIRP.**
1. `ihlaller()`'i çalışma anına bağla. Tasarım kararı: sahte-niyetteki gibi "satırı sil"
   **yanlıştır** (içerik doğru, ifade yanlış — silmek cevabı mahveder); doğru araç hedefli
   yeniden üretimdir. Maliyeti ölçülmeden eklenmemeli (her stilistik kusurda ek LLM çağrısı).
2. Kod garanti ettiği anda prompt'taki karşılık bloklarını kırp (~593 token: hitap + nutuk +
   dolgu + iç jargon) ve **tavanı aşağı çek** — kapı zaten bunu isteyecek.

**İNSAN-KAPISI, hâlâ açık:** OpenRouter/Anthropic kredisi (§8). K2 bunu beklemiyor.

---

### §9.1 K-B BASELINE — ALTIN SENARYO SETİ ÖLÇÜLDÜ (2 Eylül 2026)

**AKTİF FAZ ARTIK K-B.** §4.2'nin G1-G6'sı ölçüye bağlandı ve İLK KEZ koşuldu.
Komut: `python -m scripts.eval_runner --altin` · kod: `scripts/coach_altin.py`.

| Ölçüm | Değer |
|---|---|
| Kriter | **15/25 = %60,0** (model = kullanıcı; onarım kazancı 0) |
| Tam geçen senaryo | **0/6** |
| **`dogru_sonuc` (muhakeme)** | **1/6 — ve geçen tek senaryo, setin EN ZAYIF ölçüleni (G6)** |
| Koşum geçerliliği | GEÇERLİ (0 ölü çağrı) |
| Sağlayıcı | Karışık: Gemini quota dolunca (10 istek/dk) OpenRouter devraldı — **bu bir karıştırıcıdır**, sağlayıcı-başına ölçüm yapılmadı |

**NEDEN BU SAYI ÖNEMLİ:** davranış seti aynı gün **%80,0 / %82,9** veriyordu. İki oran
arasındaki uçurum bir çelişki değil, **iki farklı sorunun cevabı**: koç DÜZGÜN konuşuyor
(davranış sözleşmesi), ama İŞİ yapamıyor (muhakeme). K0'dan beri manşet sayımız birinciydi;
"koç %80" cümlesi kurulabildiği hâlde koç, kullanıcıya **31.115,44 TL fazla ödeme**
tavsiye edebiliyordu. Ölçtüğümüz şey yanlıştı.

**HER DÜŞÜŞ TEK TEK DOĞRULANDI** (BUG #316'nın dersi: önce ölçüt, sonra suçlama). Altı
cevabın tamamı dosyaya döküldü ve elle okundu; hiçbiri ölçüt kusuru DEĞİL:

| # | Koç ne dedi | Gerçek | Zarar |
|---|---|---|---|
| G1 | "İki krediyi kapatmak için **79.625,85 TL** ödemen gerekiyor" | 48.510,41 TL (14.023,29 + 34.487,12) | **31.115,44 TL fazla ödeme tavsiyesi.** Tuzağa tam ortasından düştü |
| G2 | "Kart borcun **0 TL**, ödeme yapmana gerek yok" | 8.221,13 TL, 14 Eylül'de | **YENİ ARIZA SINIFI: dalkavukça hizalanma.** Kullanıcı "0 görünüyor" dedi, koç kendi verisine değil KULLANICIYA uydu — aynı koç G6'da aynı kartı 8.221,13 diye okuyor |
| G3 | "Ek kaynağa ihtiyacın olacak" | 585,34 TL ile ay kapanıyor | Takvim kurulmadı; eldeki nakit ve kart ödemesi hesaba hiç girmedi |
| G4 | "Kredi %4,75 ve **%4,25**/ay, mevduat brüt %35,5" | Kredi %4,75/%4,55 · mevduat **stopajdan sonra** ~%2,5 | **Stopaj hiç anılmadı** → brüt ile net kıyaslandı; ayrıca %4,25 uydurma |
| G5 | Krediye ödeme öner, "11-15 Eylül taksitleri" | Ayın en büyük tek çıkışı 14 Eylül'de 8.221,13 TL | Tavsiyeye uyulsa **kart ödemesi kaçardı** |
| G6 | Kart borcunu doğru gördü (`dogru_sonuc` ✅) | — | Ama aynı cevapta uydurma sayılar (4.000 ×4 izlenemez), "9 Eylül" (kullanıcı 8 dedi) ve bozuk Türkçe ("Hen müdahale") var → **G6'nın geçmesi "G6 çözüldü" DEMEK DEĞİLDİR**, zayıf ölçüt önceden yazılmıştı |

**ÖLÇÜTÜN KENDİSİ KANITLANDI (kullanılmadan önce):** `tests/test_altin_senaryo_kapisi.py`
33 test — insanın 1 Eylül'de verdiği altın cevap her senaryoda GEÇİYOR, bilinen yanlış
muhakeme her senaryoda DÜŞÜYOR, boşluklu/yuvarlanmış yazım geçiyor, yakın-ama-farklı tutar
geçmiyor. **Mutasyon 7/7 + 2/2** (tuzak şartsızlaştırma · `all→any` · desen ölçmeme ·
senaryosuz puanlama · tolerans genişletme · boşluk ayıraç · vakumsal yeşil · set filtresi).
`all→any` mutasyonu ilk turda 30 testin hepsinden **kaçtı** — kural yazılıydı ama
ölçülmüyordu; testi mutasyon yazdırdı.

**TASARIM KARARLARI (gerekçeleriyle):**
- **Tuzak ŞARTLIDIR** — tuzak tutar, doğru tutar da varken ihlal değildir. En iyi cevap
  ikisini karşılaştırarak söyler; koşulsuz yasak tam olarak o cevabı düşürürdü.
- **`grounded` bu sette KULLANILMAZ** ve bu kilitli. İki gerekçe: erken kapama tutarı veri
  modelinde sayı değil `notes` METNİ (cockpit'in sayısal yapraklarına girmiyor), ve altın
  senaryolar TÜREV sayı istiyor. **İkisi de birer ürün bulgusudur** (aşağıda).
- **İki set aynı dosyaya yazılır ama etiketlidir** (`set: altin|varsayilan`); düşüş raporu
  yalnız aynı seti kıyaslar — yoksa her set değişiminde sahte regresyon basılırdı.

**YENİ ÜRÜN BULGULARI (bu ölçümün yan ürünü):**
1. **Erken kapama tutarı sayısal alan olmalı.** Bugün `notes` içinde metin; koç doğru
   söylese bile grounding "izlenemeyen tutar" damgası basar. Yani ürün, doğru cevabı
   cezalandıracak şekilde kurulu.
2. **Dalkavukça hizalanma** (G2) hiçbir üslup kuralının kapsamında değil: koç, kullanıcının
   yanlış önermesini kendi verisine tercih etti. `uslup_kurallari.py`'de karşılığı yok.
3. Kredi `balance`i kalan taksit toplamıdır; anapara ayrı alan olmadıkça G1 tuzağı üründe
   canlı kalır. **Bu düzeldiğinde `scripts/coach_altin.py` fixture'ı da güncellenmeli**, aksi
   halde kapı düzeltilmiş bir hatayı yerinde dondurur (uyarı modül başında yazılı).

### §9.2 SAĞLAYICI-BAŞINA ÖLÇÜM VE BUG #317 (2 Eylül 2026, aynı gün)

§9.1'in ilk koşumu karışıktı (Gemini kotası dolunca OpenRouter devraldı). Karıştırıcıyı
kaldırmak için sağlayıcılar tek tek koşuldu — ve koşum **bir bug ortaya çıkardı**.

**BUG #317 — boş görünen bir ayar, satır sonundaki yorumu değer sandı.**
`.env`de `LLM_MODEL=   # bos: ...` yazıyordu. python-dotenv, değer VARSA satır sonu
yorumunu ayıklar; değer BOŞSA ayıklamaz. Yani `LLM_MODEL` değeri **yorumun kendisiydi** ve
`LLM_PROVIDER` tek bir sağlayıcıyı adlandıran her koşumda o metin model adı olarak gitti.

| | Düzeltmeden önce | Sonra |
|---|---|---|
| OpenRouter (altın) | %0,0 · GEÇERSİZ | **%76,0 · 2/6 tam geçti · GEÇERLİ** |

Aynı tuzak **`.env.example`de 13 değişkende** vardı (`ANTHROPIC_API_KEY` dahil) — yani
şablonu kopyalayan herkeste. Bu bir yerel yazım hatası değil, dağıtılan bir şablon
hatasıydı. K0'da "Anthropic 400 / kredi yok" diye kaydedilen gözlemin bir kısmı da buradan
gelmiş olabilir.

**SAĞLAYICI TABLOSU (her biri tek çağrıyla teşhis edildi):**

| Sağlayıcı | Model | Durum |
|---|---|---|
| **OpenRouter** | `minimax/minimax-m3:free` | ✅ **Tek geçerli altın ölçüm** |
| Groq | `openai/gpt-oss-120b` | Canlı, ama altın istek **12.954 token > 8.000 TPM** (`Request too large`) |
| Gemini | `gemini-2.5-flash-lite` | 429 — ücretsiz kota |
| Cerebras | `gpt-oss-120b` | 402 — ödeme gerekli (§8 insan-kapısı) |
| Anthropic | `claude-opus-4-8` | 400 — kredi yok (§8 insan-kapısı) |

**K2'nin "isteği küçült" işi artık sayıyla gerekçeli:** Groq ölü değil, isteğimiz büyük.
12.954 → 8.000'in altına inen bir istek, ücretsiz katmanda İKİNCİ bir geçerli sağlayıcı
demektir; yani kırpma işi bir kozmetik değil, ölçüm kapasitesi kazanmaktır.

**Ders (deftere):** *model adı çürüdüğünde belirti daima "sağlayıcı bizi istemiyor"
biçiminde okunur.* Bu, BUG #315'ten sonra ikinci kez oldu. Bir sağlayıcıya "ölü" demeden
önce ona giden model adı GÖZLE okunmalı.

### §9.3 K-B İLERLEMESİ — (c) STOPAJ KURAL MOTORUNA TAŞINDI (2 Eylül 2026)

§9.1'in üç sıradaki adımından **(a) sağlayıcı-başına ölçüm** §9.2'de, **(c) stopajın kural
motorunda hesaplanması** burada. (b) — erken kapama tutarının sayısal alana taşınması —
şema göçü gerektiriyor, henüz AÇIK.

**Yapılan:** `app/vergi.py` (saf, DB'siz) + `rules_engine.calculate_getiri_esigi()` →
cockpit `getiri_esigi` → koç bağlamında "GETİRİ EŞİĞİ (HESAPLANMIŞTIR)" bloğu.
- **Engel oran:** borcun en pahalı kaleminin aylık faizi. Parayı oraya koymak risksiz ve
  vergisizdir; hiçbir yatırım bunu geçmiyorsa tartışma biter.
- **Ters hesap:** eşiği geçmek için mevduatın vermesi gereken **brüt yıllık** oran —
  aylık %4,75 borç için **%68,49**. Kullanıcının teklifi %35,5; yani yarısı kadar.
- Prompt'a TEK BİR YASAK CÜMLESİ eklenmedi (K-KURAL 5). Hesap taşındı, koç okuyor.

**ÖLÇÜM — DÜRÜST KAYIT:**

| | Eşik bloğundan önce | Sonra |
|---|---|---|
| OpenRouter kriter | %76,0 | %76,0 |
| `dogru_sonuc` | 2/6 (G4, G6) | **2/6 (G4, G6)** |

**Sayı değişmedi ama cevap değişti:** G4 cevabı artık stopajı (%17,5) ve kural motorunun
hesapladığı **net %29,29**'u birebir kullanıyor — blok okunuyor. Yine de bunu bir KAZANIM
diye yazamam: G4'ün kriteri (stopaj kelimesi + bir kredi oranı) blok gelmeden önce de
sağlanıyordu ve **öncesi koşumun METNİNİ almamıştım**, yalnız skorunu almıştım. §4.1'in
2. adımını (ölçümü ÖNCE al) yarım uyguladım; ders kaydedildi: *skor bir ölçüm değildir,
metin de ölçümün parçasıdır.*

**ÖLÇÜT ZAAFI — KAYDEDİLİYOR AMA ŞİMDİ DEĞİŞTİRİLMİYOR:** G4, eşiği hiç kullanmadan
geçebiliyor; G6 için aynı zaafı ölçümden ÖNCE yazmıştım, G4 için yazmamıştım. Kriteri
cevapları GÖRDÜKTEN sonra sıkılaştırmak, ölçütü kendi değişikliğime uydurmak olurdu.
Sıkılaştırma ayrı bir turda, gerekçesi önce yazılarak yapılır.

**YAN BULGU (G4 cevabında):** koç 9.000 TL'lik ödemeden sonra "kredi yükün 16.440 TL'den
~7.440 TL'ye iner" dedi — yani G1'in tuzağına burada da düştü (16.439,65 kalan taksit
toplamıdır, anapara 14.023,29). Bu, (b) maddesinin — erken kapama tutarının sayısal alan
olması — neden sıradaki en önemli iş olduğunun ikinci kanıtı.

### §9.4 K3 SINIFLANDIRMASI — KALAN YARIDA UYDURMA YOK (3 Eylül 2026)

§10'un 1. sıradaki işi: *"`grounded` hâlâ 3/6 düşüyor. Her düşüşü tek tek oku ve ayır:
TÜREV sayı mı, GERÇEK uydurma mı? Zorlama tasarımı ancak bu ayrımdan sonra seçilir."*

**ÖNCE ÖLÇÜM ARACI ONARILDI.** Rapor `grounded=-` diyor ama hangi tutarın düşürdüğünü
yazmıyordu — bu ayrım tam olarak o listeyi ister. Düşüren tutarlar rapora eklendi
(`uslup` için BUG #277'de yapılanın aynısı) ve `--dokum` bayrağıyla koşumun TAM cevapları
JSON'a yazılır hâle geldi (§9.3'ün kendi dersi: *skor bir ölçüm değildir*).

**SONRA BİR KARIŞTIRICI BULUNDU — VE KAYITLI TABAN ONUNLA KİRLİYDİ.** `.env`de
`LLM_PROVIDER=fallback`; Gemini ücretsiz katmanı dakikada 10 istek verir ve davranış seti
8 senaryodur, yani kota **koşumun ortasında** dolar. Ölçüldü: tek koşumda **3 kez**
`Gemini → OpenRouter` geçişi. §9.1 bu karıştırıcıyı altın set için kaldırmıştı, davranış
seti için kaldırmamıştı.

| Davranış seti, 3 koşum | kriter | `grounded` | `uslup` |
|---|---|---|---|
| Karışık zincir (2 Eyl kaydı) | medyan **%82,9** | 3/6 | 13/24 |
| **OpenRouter sabit (3 Eyl)** | min %88,6 · medyan **%88,6** · maks %91,4 | 2/6 | 18/24 |

Yani kayıtlı %82,9 bir kalite ölçümü değil, bir **sağlayıcı karışımı ölçümüydü**;
#2'nin (prompt kırpma) karşılaştıracağı taban da bu yüzden kirliydi.

**SINIFLANDIRMA — 13 düşüren tutarın tamamı okundu:**

| Sınıf | Tutarlar | Yorum |
|---|---|---|
| **TÜREV** (koçun meşru senaryo aritmetiği) | `9.700` = 11.976 − 2.276 · `8.440` · `3.424` = 7.700 − 4.276 · `5.424` = 7.700 − 2.276 | Kokpit'te tek yaprak olarak yok, ama uydurma da değil |
| **KULLANICININ KENDİ BEYANI** | `500` · `240` | Kullanıcı önceki turlarda söyledi → **BUG #322** |
| **ÖRNEKLEYİCİ YUVARLAK SAYI** | `1.000` (*"her 1.000 TL ödeme çukuru 1.000 TL azaltır"*) | Bir orana örnek; bakiye iddiası değil |
| **GERÇEK UYDURMA** | **yok** | **0/13** |

**ZORLAMA TASARIMININ CEVABI: HİÇBİRİ.** Bu dedektöre dayanan bir blok/yeniden-üretim,
engelleyecek uydurma bulamaz; engelleyeceği tek şey koçun matematiği olur. K3'ün sorusu
"hangi zorlama?" idi; ölçüm soruyu değiştirdi: **"bu dedektör ne ölçüyor?"**

**VE ASIL BULGU BU — DEDEKTÖR AYNI CEVAPTA TAM TERS KARAR VERDİ.** Koşum 2:
*"Nakit: 4.276 → **3.536** TL · Kart borcu: 11.976 → 12.216 TL"*. 3.536 **yanlıştır**
(koç 240 TL'lik KART harcamasını nakitten de düşmüş; doğrusu 3.776). Ölçüldü:

- `3.536` (**yanlış**) → **GEÇTİ**, alakasız `saglikli_borc_hedefi` = 3.600'e %2 içinde denk geldiği için
- `3.776` (**doğru**) → **DÜŞERDİ**
- `500` · `240` (doğru, kullanıcı beyanı) → düştü
- `8.440` · `9.700` · `3.424` · `5.424` (doğru türev) → düştü

**Tesadüf yüzeyi ölçüldü (200.000 örneklem): 100-20.000 aralığından rastgele bir tutar,
hiçbir dayanağı olmasa da %10,7 olasılıkla "izlenebilir" sayılıyor** — ve bu yalnız 27
benzersiz kokpit yaprağıyla; canlı kokpit çok daha zengin, yani beraat kararı üretimde
daha da anlamsız.

**Tolerans DARALTILMADI:** `48.510,41`'i `48.510` diye yuvarlayan doğru cevabı düşürürdü
(BUG #316'nın dersi). Doğru yön eşleşmeyi **izlenebilir** kılmak (hangi yaprağa denk
geldiği raporlansın) — ayrı iş, §10'da açık madde.

**K-DERSİ (yeni): bir dedektörün BERAATI, mahkûmiyeti kadar ölçülmelidir.** K3 boyunca
yalnız yanlış mahkûmiyetler (#316, #321, #322) sayıldı; yanlış beraatler hiç sayılmamıştı
ve bugün ölçülünce oran %10,7 çıktı.

---

**SIRADAKİ SOMUT ADIM:** düşüşlerin ortak paydası tek bir cümlede toplanıyor —
**koç, elindeki veriyi OKUMADAN cevap veriyor** (G1 notes'u atladı, G2 kendi kartını
görmezden geldi, G3 nakdi saymadı, G4 stopajı bilmiyor). Bunların hiçbiri prompt'a yeni
bir 🔴 yasak eklemekle çözülmez (K-KURAL 5). Sıra: (a) sağlayıcı-başına altın koşum —
karıştırıcıyı kaldır, hangi modelin muhakeme ettiğini ölç; (b) cockpit'in koça verdiği
alanların denetimi (erken kapama sayısallaşsın, kart borcu tek anlamlı olsun); (c) stopaj
gibi Türkiye'ye özgü sabitlerin kural motorunda hesaplanması — koçtan aritmetik beklemek
yerine (mimarinin kendi ilkesi: *rules engine karar verir, LLM açıklar*).

---

## §10. DEĞİŞİKLİK GÜNLÜĞÜ (yalnız ileri yönlü)

### ⏸️ KALDIĞIMIZ YER — 3 Eylül 2026 (SIRADAKİ OTURUM BURADAN BAŞLAR)

**DURUM:** her şey commit'li ve push'lu. **Backend süiti 3400 passed · 18 skipped ·
0 failed** (9:38; önceki taban 3380 → +20 yeni test). Kalite kapısı (ruff aile tavanları
B31/E9-0/F202/S63), belge denetimi ve ölü kod kapısı geçiyor. Frontend/e2e bu turda
KOŞULMADI — değişikliklerin hepsi backend, ama iddia da o kadarıyla sınırlı.

**BUGÜN — K3'ÜN 1. SIRADAKİ İŞİ KAPANDI (sınıflandırma) VE SORU DEĞİŞTİ.**

1. **Ölçüm teşhis edilebilir hâle getirildi.** `grounded=-` artık hangi tutarın düşürdüğünü
   yazıyor; `--dokum` bayrağı koşumun TAM cevaplarını JSON'a döküyor. (Bir düşüşü
   sınıflandırmak, metni görmeden yapılamaz — §9.3'ün kendi dersi.)
2. **KARIŞTIRICI BULUNDU:** `.env` = `fallback`, Gemini 10 istek/dk → çıplak davranış
   koşumu **zorunlu olarak karışık sağlayıcı** (tek koşumda 3 geçiş ölçüldü). Kayıtlı
   %82,9 tabanı bu yüzden kirliydi. **Sağlayıcı sabit taban: medyan %88,6 · `uslup` 18/24.**
3. **SINIFLANDIRMA (13/13 okundu): GERÇEK UYDURMA YOK.** 4 türev sayı · 2 kullanıcı beyanı ·
   1 örnekleyici yuvarlak sayı. → **Zorlama tasarımının cevabı: hiçbiri eklenmeyecek.**
4. **ASIL BULGU — DEDEKTÖR YANLIŞ BERAAT VERİYOR.** Aynı cevapta koçun YANLIŞ hesabı
   (3.536) alakasız bir yaprağa %2 içinde denk geldiği için geçti, DOĞRUSU (3.776)
   düşerdi. **Tesadüf yüzeyi %10,7** (200.000 örneklem, 27 yaprak). Ayrıntı §9.4.
5. **BUG #322 kapandı** — izin listesi modelin gördüğü veriden dardı; kullanıcının bir tur
   önce söylediği tutarı doğru hatırlayan koç halüsinasyon damgası yiyordu (üretimde güven
   0,4). 9 test, **mutasyon 5/5** (M1 önce hayatta kaldı, kapının kendi kör noktasını buldu).
6. **BUG #323 kapandı — KULLANICIYA DOĞRUDAN ZARAR.** *"Bugün 500 TL yemek harcadım
   nakitten"* → harcama KAYDEDİLMİYOR, koç *"Tarih bilgisi tutarsız… tarih yoksa bugün
   olarak kaydederim"* diyor. Ürün, söylediği şeyi yapmayı reddediyordu. 8 test,
   **mutasyon 3/4** (biri eşdeğer mutant; bir diğeri 194 testten kaçıp testi yazdırdı).

**GÜNÜN DESENİ — ÜRÜN, KOÇU DOĞRU DAVRANDIĞI İÇİN CEZALANDIRIYOR.** Üç bulgunun üçü de
aynı kalıpta: koç kullanıcının söylediğini hatırlıyor (#322), kullanıcının kelimesini
tekrarlıyor (#323), kullanıcının ekranındaki etiketi kullanıyor (`IC_JARGON`) — ve her
üçünde de ürün onu düşürüyor. **Bir koçu "yalan söylüyor" diye ölçmeden önce, ona neyi
verdiğimizi ve neyi yasakladığımızı yan yana koymak gerekiyor.**

**ÖLÇÜM — DÜRÜST KAYIT (3 koşum, OpenRouter sabit, öncesi/sonrası):**

| | kriter (min/medyan/maks) | `grounded` | `action` | düşüren tutarlar |
|---|---|---|---|---|
| Öncesi | %88,6 / %88,6 / %91,4 | 2/6 | 5/6 | 240 · 500 · 1.000 · 3.424 · 5.424 · 8.440 · 9.700 |
| Sonrası | %85,7 / %85,7 / %88,6 | 2/6 | **3/6** | 1.000 · 1.305 · 1.500 · 2.500 · 9.700 |

**Manşet DÜŞTÜ ama sebebi bu değişiklik değil:** düşüş tamamen `action` ekseninde ve o
eksene dokunulmadı (sağlayıcı gürültüsü — `uslup` dünkü koşumda aynısını yapmıştı).
**BUG #322'nin kanıtı manşette değil:** `500` ve `240` düşüren tutarlar listesinden
TAMAMEN kalktı ve geriye kalanların **hepsi türev/örnekleyici**. Yani (a) düzeltme hedefini
vurdu, (b) sınıflandırma bağımsız olarak doğrulandı. Deterministik kanıt 9 test + mutasyon
5/5'tedir; **8 senaryoluk 3 koşum bu büyüklükte bir kazancı manşette çözemez** (örneklem
dersi, yine).

**GÜN SONU TABANI (3 koşum, OpenRouter sabit, #322+#323 kapalı — 4 Eyl sabahı tamamlandı;
makine gece uyuduğu için koşum sarktı):**

| | kriter (min/medyan/maks) | `grounded` | `action` | `uslup` |
|---|---|---|---|---|
| #322/#323 öncesi | %88,6 / %88,6 / %91,4 | 2/6 | 5/6 | 18/24 |
| **gün sonu** | %82,9 / **%85,7** / %88,6 | 0/6 | **6/6** | 15/24 |

**`action` 6/6 oldu** — BUG #323'ün hedefi. **`grounded` düşüşü bir gerileme DEĞİL:**
düşüren tutarlar arasında **`3.776` var, yani koçun DOĞRU hesabı.** Bir gün önce
"3.536 (yanlış) geçti, 3.776 (doğru) düşerdi" diye yazılmıştı; koç bu kez doğru hesapladı
ve tam öngörüldüğü gibi düşürüldü. **Dedektörün kusuru artık canlı kanıtlı.**

**`500`'ün hâlâ düşmesi ÖLÇÜLDÜ ve bir kusur ÇIKMADI.** İlk tahmin (`_trim_history_to_size`
kırpıyor) **yanlıştı** — 6.000 karakterlik tavana hiç değilmiyor. Gerçek sebep:
`_load_history` **tur değil SATIR** sınırlıyor (6 satır); aksiyon öneren tur ek satır
yazınca pencere daha az turu kapsıyor (kullanıcı mesajı 3 → 2) ve koç o noktada sayıyı
KENDİ önceki cevabından tekrarlıyor — o kaynak bilinçli olarak izinli değil (döngüsellik
yasağı). Sözleşme birebir tutuyor.

**SIRADAKİ İŞLER — ÖNCELİK SIRASIYLA:**
1. **YANLIŞ BERAAT — birinci ayağı KAPANDI (BUG #324), ikinci ayağı açık.**
   ✅ *İzlenebilirlik:* her doğrulanan tutar artık `dayanak` · `sapma_yuzde` · `kaynak`
   (kokpit / kullanıcı beyanı) taşıyor ve eval dökümüne düşüyor. Karar ve tolerans
   DEĞİŞMEDİ — yalnız gerekçe görünür oldu. 8 test, mutasyon 4/4.
   🟡 *Açık kalan:* gerekçe artık VAR ama henüz KULLANILMIYOR. Sıradaki soru ölçülebilir
   hâle geldi: **canlı koşumlarda beraatlerin sapma dağılımı nedir?** Sapması sıfıra yakın
   olanlar gerçek eşleşme, kuyruktakiler tesadüf adayı. O dağılım ölçülmeden bir eşik
   (ör. "sapma > %1 ise zayıf beraat, ayrı raporla") seçilmemeli — **tolerans DARALTILMAZ**,
   yuvarlanmış doğru cevabı düşürür (BUG #316 dersi).
2. **Prompt kırpma — TABAN ARTIK TEMİZ.** Karşılaştırma tabanı: OpenRouter sabit, medyan
   **%88,6** (3 koşum). Sistem promptu isteğin %78'i; KURAL SIFIR %32 ve `offer_propose=False`
   iken `propose_action` tool listesinde HİÇ YOK (`no_action` 12/12 · şimdi 24/24 kanıt).
   **Groq beklentisi yok** (8.000 altına inmek ~5.000 token indirim ister).
3. **KOÇ, KULLANICIDAN ZATEN VERDİĞİ BİLGİYİ İSTİYOR (yeni, ürün defekti).** `action`
   ekseni 5/6 ↔ 3/6 dalgalandı; "gürültü" diye geçilecekken METİNLERE bakıldı ve gürültü
   çıkmadı:

   | Kullanıcı | Koç |
   |---|---|
   | "**240 TL** market aldım **kartla**" | *"Tutarı rakamla ve hangi hesap olduğunu yazar mısın?"* |
   | "**Bugün** **500 TL** yemek harcadım **nakitten**" | *"Tarih bilgisi tutarsız. Tarihi açıkça belirt…"* |

   Üçünde de tutar/hesap/tarih mesajda AÇIKÇA var. Kök: `propose_action` payload'ı
   sözleşmeden düşüyor ve `PayloadGecersiz` kendi `kullanici_mesaji`nı tanımlamadığı için
   **taban sınıfın genel mesajını** miras alıyor. **Bu turdan ÖNCE de vardı** (2 kez) —
   regresyon değil, mevcut defekt.
   **YARISI AYNI GÜN KAPANDI — BUG #323.** Sebep, ürün koduna DOKUNMADAN ölçüldü
   (`AksiyonReddi.__init__` ayrı bir süreçte geçici sarmalandı; 6 denemede bulundu):
   gerekçe *"özette tarih geçiyor ama işleme tarih yazılmadı"*. `bugun` kelimesi
   `_DATE_KEYWORD_RE`'de olduğu için koç kullanıcının "Bugün"ünü özete yankıladığında
   BUG #044 koruması tetikleniyordu — **oysa yedek değer zaten bugündür, yani sessiz
   yanlış gün İMKÂNSIZ**. Muafiyet dar tutuldu (özetteki tek ifade "bugün" iken);
   8 test, mutasyon 3/4.

   **KALAN YARISI AÇIK — `PAYLOAD_GECERSIZ`.** Kart senaryosundaki ret bu turda
   yeniden üretilemedi (3 denemede 0 kez). İlk adım ölçüm:
   `logger.warning("propose_action reddedildi: %s", red.kod)` (`app/coach.py:2943`)
   yalnız KODU basıyor; `red.gorunur_neden` kesin teşhisi taşıyor
   (`"tool argumaninda eksik alan: X"`) ve **bilinçli olarak para içermiyor** (ADR-052).
   Önce onu logla, hangi alanın düştüğünü ÖLÇ, sonra `PayloadGecersiz`'e kendi kullanıcı
   mesajını yaz (bugün taban sınıfın genel mesajını miras alıyor).
4. **G3/G5 kararsızlığı (1/3)** — kart ödemesi bağlamda VAR ama koç bazen atlıyor.
5. **`IC_JARGON` — üslup düşüşlerinin %71'i, VE YASAKLANAN TERİMİ ÜRÜN KULLANICIYA
   KENDİ ÖĞRETİYOR.** 6 koşumun `uslup` düşüşleri sayıldı: **IC_JARGON 10 · SIZ_HITABI 3 ·
   DALKAVUKLUK 1.** Eşleşmeler çıkarıldı: **13'ün 11'i `reel butce`/`reel butcen`**
   (kalan 2 `cockpit`). Üç ölçüm arka arkaya:
   `app/coach.py:966` koça bağlamı **`- Reel Bütçe : ...`** diye etiketli VERİYOR ·
   aynı promptun `:327` satırı *"reel bütçe"*yi iç jargon diye YASAKLIYOR ·
   `frontend/src/panels/Cockpit.jsx:312` bunu kullanıcıya **`title="Reel Bütçe"`**
   başlıklı bir kart olarak GÖSTERİYOR. Yani terim iç jargon değil, **arayüz etiketi**;
   koç kullanıcının ekranında okuduğu kelimeyi kullandığı için düşürülüyor.
   **⛔ KARAR MURAT'A AİT (§8: "K7'de dilin sınırları"):**
   **(a)** kuraldan "reel bütçe"yi çıkar (kural amacını korur, prompt bir satır kısalır), ya da
   **(b)** terimi hem prompttan hem arayüzden kaldır, yerine düz Türkçe koy.
   Ölçüm şunu söylüyor: bugünkü hâl ikisi de değil — ürün terimi öğretiyor, koça veriyor,
   sonra kullanınca cezalandırıyor.
6. **Dalkavukça hizalanma** — `uslup_kurallari.py`'de karşılığı yok.
7. **G2 deseni dar** — ölçüt turu AYRI, gerekçesi ÖNCE yazılarak.
8. Açık ürün soruları: kredi `balance`i anapara olmalı mı · emir kipi kalıntısı ·
   K4 stigmerji · K5 caching. (`IC_JARGON` artık 5. maddede, ölçülmüş hâliyle.)

**BU TURUN DERSLERİ:**
- **Bir dedektörün BERAATI, mahkûmiyeti kadar ölçülmelidir.** K3 boyunca yalnız yanlış
  mahkûmiyetler sayıldı (#316, #321, #322); yanlış beraat hiç sayılmamıştı → %10,7.
- **Bir kapı, sözleşmeyi YAZDIĞI yerde değil ZORLANDIĞI yerde ölçmelidir.** Rol filtresini
  kaldıran mutasyon 51 testten kaçtı; sözleşme `check_grounding`de yazılıydı ama çağıran
  tarafta ölçülmüyordu.
- **Ürünün kendisi döngüselliği zaten üretiyordu:** iç plan yönlendirmesi modelin çıktısını
  `role="user"` olarak listeye ekliyor. "Rolüne göre süz" yetmez; **kaynağın kalıcı olup
  olmadığına** bakmak gerekir.
- **Bir ölçüm aracının varsayılanı, ölçümün karıştırıcısı olabilir.** `.env=fallback` bir
  ürün ayarıdır; ölçüm aracı onu miras aldığı için taban aylarca karışık kaldı.

---

### ⏸️ (ÖNCEKİ) KALDIĞIMIZ YER — 2 Eylül 2026, gün sonu

**DURUM:** her şey commit'li ve push'lu (`main` = `origin/main`, fark yok).
Süitler: **backend 3380 · frontend 214 · e2e 8** — hepsi yeşil.

**BUGÜN KAPANAN BEŞ ÜRÜN DEFEKTİ** (hiçbiri prompt'a satır eklemeden — K-KURAL 5):
`#317` .env yorumu model adı sanıldı · `#318` erken kapama sayısal alana ·
`#319` nakit takvimi parçalıydı (koç gelen parayı gider sayıyordu) ·
`#320` yatırımda bekleyen nakit ayrı kalem · `#321` etiketsiz ≠ izlenemez.

**ÖLÇÜMLER (aralıkla — tek koşum gürültülüdür):**
- Altın set, 3 koşum: kriter **min %88 / medyan %88 / maks %96**, muhakeme
  **min 4/6 / medyan 4/6 / maks 6/6**. Sabahki taban **1/6** idi.
  Senaryo başına: G1 3/3 · G2 3/3 · G4 3/3 · G6 3/3 kararlı · **G3 1/3 · G5 1/3 kararsız**.
- Davranış seti, 3 koşum: kriter medyan **%82,9**; `grounded` **0/6 → 3/6** (BUG #321),
  `no_action` **12/12**, `uslup` 13/24 (gürültülü eksen).

**SIRADAKİ İŞLER — ÖNCELİK SIRASIYLA:**
1. **K3'ün kalan yarısını sınıflandır.** `grounded` hâlâ 3/6 düşüyor. Her düşüşü tek tek
   oku ve ayır: TÜREV sayı mı (toplam/fark — koç meşru üretir, cockpit'te bulunmaz) yoksa
   GERÇEK uydurma mı? **Zorlama tasarımı ancak bu ayrımdan sonra seçilir** — türev sayıyı
   engellemek koçun matematik yapmasını yasaklamak olur.
2. **Prompt kırpma.** Sistem promptu 19.444 kar = isteğin **%78'i**. KURAL SIFIR promptun
   **%32'si** ve `offer_propose=False` iken `propose_action` tool listesinde HİÇ YOK
   (`no_action` 12/12 kanıt). Sınıflandırma tablosu + tetikleyici listeleri ölü ağırlık.
   Kesmeden önce davranış setinin 3-koşumluk tabanı alınmalı (bugünkü: medyan %82,9).
   **Groq beklentisi yok:** 8.000 token altına inmek ~5.000 indirim ister, KURAL SIFIR'ın
   tamamı 3.258. Groq ayrı bir yapısal çözüm (kısa prompt varyantı) ister.
3. **G3/G5 kararsızlığı (1/3).** Kart ödemesi bağlamda VAR ama koç bazen atlıyor — kalan
   kusur ürün değil MODEL tarafında. Bağlam sıralaması/belirginlik denenebilir (prompt
   kuralı değil, bilgi mimarisi).
4. **Dalkavukça hizalanma** — kullanıcı yanlış önerme söyleyince koç kendi verisini terk
   ediyor. `uslup_kurallari.py`'de karşılığı yok.
5. **G2 deseni dar** ("cari dönem" eşanlamlısını görmüyor) — ölçüt turu AYRI yapılmalı,
   gerekçesi ÖNCE yazılarak (cevapları gördükten sonra ölçüt değiştirmek fitlemektir).
6. Açık ürün soruları: kredi `balance`i anapara olmalı mı · `IC_JARGON` onarımı ·
   emir kipi kalıntısı · K4 stigmerji · K5 caching.

**BU TURUN METODOLOJİ DERSLERİ (hepsi deftere yazılı):**
- **Örneklem büyüklüğü belirtilmeyen bir oran bir iddiadır, ölçüm değil.** Aynı kodla
  %88 → %84 → %80 ölçüp ±4 puanı sinyal sandım.
- **Manşet oran bir karıştırıcıdır:** `grounded` iyileşirken manşet düştü (başka eksen).
  Kriter başına tablo olmadan yorumlanamaz.
- **Bir ölçüt, kabul ettiği YAZIM kadar iyidir** — bugün ÜÇ kez doğru cevabı düşürdü
  (tire, eşanlamlı, NOUN şartı) + BUG #321. Gevşetmeden önce **meşruluk sınaması**:
  bu gevşetme, korumaya çalıştığı defekti kaçırır mı?
- **Bir kapı değişikliğimi reddettiğinde üç ihtimal var:** değişiklik yanlış yerde ·
  kapı fazla katı · kapının ÖRNEĞİ kötü seçilmiş. Bugün üçü de yaşandı.
- **Ratchet kapısına doğru cevap çoğu zaman tavanı yükseltmek değil, ihtiyacı ortadan
  kaldırmaktır.**
- **`notes` karar verdiren bir sayı taşıyamaz** — kredide de kartta da; iki kaynak olunca
  koç kararsız kalıyor ("0 mı 8.221 mi?").
- **Bu ortamda heredoc ters-eğik çizgileri bozuyor** (`` → düşey sekme, `
` → satır
  sonu). Kaçış dizisi içeren kod Write/Edit ile yazılır.

**ATIF (kapandı, 2 Eyl):** GitHub'da tek katkıcı `Muratcnicgl`. `.asistan/` ve `PROJE.md`
depodan çıktı (kök brifing artık **`PROJE.md`**; yerelde tek satırlık `@PROJE.md`
yönlendirmesi var). Depo-yerel git kimliği `Murat Icgil <muraticgil@gmail.com>`,
`includeCoAuthoredBy: false`. **Global git config'e DOKUNULMAZ.**

---

- **2 Eylül 2026 (gün sonu) — K-B TABANI YENİDEN ÖLÇÜLDÜ, BU KEZ ARALIKLA.**
  **KRİTER min %88,0 · medyan %88,0 · maks %96,0 · MUHAKEME min 4/6 · medyan 4/6 · maks 6/6**
  (3 koşum, OpenRouter). Senaryo başına geçiş: **G1 3/3 · G2 3/3 · G4 3/3 · G6 3/3**
  kararlı; **G3 1/3 · G5 1/3** kararsız. Sabahki taban muhakeme **1/6** idi ve geçen tek
  senaryo setin en zayıf ölçüleniydi.
  **METODOLOJİ DÜZELTMESİ:** gün içinde neredeyse aynı kodla %88 → %84 → %80 ölçtüm ve
  ±4 puanı sinyal gibi anlattım. Sağlayıcı deterministik değil; 6 senaryoluk TEK koşum
  ±1 senaryoyu çözemez. **Örneklem büyüklüğü belirtilmeyen bir oran bir iddiadır, ölçüm
  değil.** Bundan sonra altın ölçümü N koşum + min/medyan/maks + senaryo başına sıklık.
  **BUG #320:** yatırımda bekleyen nakit ayrı ve etiketli kalem oldu (`erisilebilir_toplam`
  = 11.663,59, 1 Eylül analiziyle birebir); emanet pazarlıksız hariç.
  **Ölçüt onarımı (üçüncü kez):** G1'in NOUN şartı kaldırıldı — meşruluk sınaması yapıldı,
  eski bozuk cevap kelimesiz ölçütten de düşüyor.

- **2 Eylül 2026 (üçüncü tur) — ÜRÜN DÜZELTMELERİ ÖLÇÜYÜ HAREKET ETTİRDİ.**
  Altın set (OpenRouter) gün içinde dört kez ölçüldü:
  **%60,0 (1/6) → %76,0 (2/6) → %84,0 (3/6) → %88,0 (3/6 tam geçen).**
  Kazanımların hiçbiri prompt'a satır eklemekten gelmedi (K-KURAL 5); üçü de ÜRÜN düzeltmesi:
  **BUG #317** (`.env` yorumu model adı sanıldı → zincir açıldı),
  **BUG #318** (erken kapama tutarı sayısal alana taşındı → G1'in 31.115,44 TL'lik yanlış
  tavsiyesi kapandı, cevap birebir altın cevap oldu),
  **BUG #319** (nakit takvimi parçalıydı → koç gelen parayı gider sayıyordu; artık işaretli,
  tarihe sıralı tek takvim okuyor ve KYK'yı `+4.000` diye yazıyor).
  **Dürüst kalan:** G3 kart ödemesini hâlâ atlıyor ama tutar bağlamda VAR — yani kalan kusur
  ürün değil MODEL kusuru; G2'nin deseni dar ve G3'ün beklentisi bugünkü takvimle
  ulaşılamaz (yatırım hesabında bekleyen nakit sorusu). Üçü de defterde açık madde.

- **2 Eylül 2026 (aynı gün, ikinci tur)** — **BUG #317** (`.env` yorumu model adı sanıldı;
  aynı tuzak `.env.example`de 13 değişkende) → OpenRouter %0'dan **%76,0'a**, GEÇERLİ.
  Sağlayıcı tablosu ölçüldü (§9.2): Groq canlı ama istek 12.954 tok > 8.000 TPM.
  **Stopaj ve bileşiklendirme kural motoruna taşındı** (§9.3): `app/vergi.py` + engel oran
  + ters hesap (%68,49). İki yeni kapı, mutasyon 6/6 ve 10/10.

- **2 Eylül 2026** — **ALTIN SENARYO SETİ ÖLÇÜYE BAĞLANDI (K-B).** §4.2'nin G1-G6'sı
  `scripts/coach_altin.py`'de çalışır senaryolara dönüştü; `EvalScenario` iki yeni kritere
  kavuştu (`dogru_sonuc`, `tuzak_yok`), `--altin` bayrağı eklendi. Ölçüt KULLANILMADAN
  ÖNCE kanıtlandı (33 test, mutasyon 7/7 + 2/2). **İlk baseline: muhakeme 1/6.** Davranış
  seti aynı gün %80 veriyordu — manşet sayımızın yanlış şeyi ölçtüğü artık SAYIYLA yazılı.
  Ayrıntı ve tek tek doğrulanmış düşüş tablosu §9.1'de.

- **1 Eylül 2026** — Belge oluşturuldu. K0 baseline ölçüldü ve §9.0'a yazıldı. Kısır döngü
  (prompt şişmesi → token → zayıf model → yeni yasak → daha çok şişme) ölçüyle belgelendi.
  Altın senaryo seti (§4.2), aynı gün insan tarafından yapılan gerçek analizden türetildi.
- **1 Eylül 2026 (aynı tur)** — K1'in kod ayağı kapandı: **BUG #313** (model adı sağlayıcıya
  aittir, zincire değil). Defter kaydı `uygulanan-fixler.md`'de. Kalan K1 işi insan-kapısı.
- **1 Eylül 2026 (aynı tur)** — K2 birinci hamle: **prompt bütçesi kapısı** kuruldu
  (karakter ≤ 19.444, 🔴 ≤ 39, kazanım kilidi; mutasyon 3/3). Şişme artık sessiz değil.
  K2'nin ana bulgusu kaydedildi: üslup kuralları kodda VAR ama yalnız ölçülüyor, çalışma
  anında zorlanmıyor → sıralama **önce zorla, sonra kırp**.
- **1 Eylül 2026 (aynı tur)** — K2 ikinci hamle: `ihlaller()`'in ÜRÜN yolunda hiç
  çağrılmadığı bulundu; bilgi taşımayan dört madde için `dolgu_temizle()` yazıldı ve
  `_postprocess_report`'a bağlandı (44 test, mutasyon 3/3, kapı iki kez kendi kör noktasını
  buldu). **Dürüst kayıt:** canlı DB'deki 11 gerçek koç cevabının 11'i de değişmeden geçti —
  değişiklik güvenli ama **bugünkü etkisi sıfır**, çünkü üretimdeki ihlallerin tamamı
  kapsam dışı bırakılan `SIZ_HITABI` (%45) ve `IC_JARGON`'dan geliyor. Kazanım önleyicidir.
- **1 Eylül 2026 (aynı tur)** — K2 üçüncü hamle: **`SIZ_HITABI` deterministik onarımı**
  (`n[ıiuü]z → n`). Üretimdeki en sık ihlal (%45) sıfır ek maliyetle kapandı. Deney önce,
  kod sonra: dönüşüm canlı korpusta doğrulandı. 44 test, mutasyon 3/3. Mutasyon iki tasarım
  hatası buldurdu — uydurma istisna ("anız") ve kelime-başı kuralının sessiz yanlış
  negatifi ("temizlemenizi" onarılmıyordu). İstisna artık **eşleşmenin konumuna** bağlı.
- **Metodoloji dersi (dürüst kayıt):** mutasyon testi ile tam süit koşumu AYNI ANDA
  yapılamaz — süit koşarken kaynak dosyalar değiştirildiği için 5s57dk süren bir koşum
  alakasız bir alanda kırmızı verdi ve kanıt sayılmadı.
- **2 Eylül 2026 — DÜN KAYDEDİLEN TEŞHİS DÜZELTİLDİ.** `test_attribution_available_true`
  "önceden girmiş regresyon" diye kaydedilmişti (sahiplik `git stash` ile ölçülmüştü,
  o kısım doğruydu). Bugün hiçbir şey değişmeden yeşile döndü; tek değişen TARİH.
  Gerçek: test `date.today()` kullanıyor ve **ayın 1'inde kırılıyor** — o gün bugünün
  snapshot'ı aynı zamanda referans olduğu için `ref is latest` → `None`.
  Deterministik offline kanıt: `today=01 → None`, `02 → sonuç`, `15 → sonuç`.
  **Yani süit her ay bir gün kırmızıydı ve görünmüyordu** (ayda 24 saat görünen bir
  kırmızı, görünmez sayılır). Test takvimden bağımsız hâle getirildi; ürün davranışı
  ayrı bir testle YAZILI hâle getirildi (mutasyonla kilitli). Açık ürün sorusu:
  `{available: false}` cevabı "geçmiş yok" ile "referans bugünün kendisi"ni ayırt etmiyor.
