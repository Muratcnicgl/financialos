# ADR-053 — LLM maliyet muhasebesi: token GERÇEK, para DONDURULMUŞ TÜREV, bilinmeyen ≠ sıfır

- **Durum:** Kabul edildi (10 Ağustos 2026, BUG #274)
- **Bağlam kodları:** backlog `LLM-006`, `OBS-005` (ön koşulu `LLM-007` kapalıydı)
- **İlgili:** ADR-041 (kullanıcı başına LLM kotası), ADR-002 (sağlayıcı-agnostik LLM katmanı),
  ADR-030 (para Decimal), ADR-051 (önce yapı, sonra metin), ADR-052 (karar tipte, teşhis ayrı alanda)

## Bağlam

`api_call_log` ilk günden beri "gelecekte maliyet analizi icin de veri kaynagi" diye tanımlıydı
ve şemada `tokens_in` / `tokens_out` sütunları duruyordu. Sağlayıcıların hepsi (LLM-007, Temmuz
2026) `usage` döndürüyordu. Yani parçaların hepsi yerindeydi.

**Ölçüm (10 Ağustos 2026 — 6 gerçekçi senaryo, gerçek uçlardan akıtılmış trafik):**

| Eksen | Ölçülen |
|---|---|
| gerçek sağlayıcı isteği → defter satırı | 13 → 13 (sayım doğru, BUG #234'ün mirası) |
| token'ı olan satır | **0 / 13** |
| ÇALIŞAN modeli yazan satır | **7 / 13** |
| isteği fiilen yiyen sağlayıcıyı yazan satır | 13 / 13 |

Harcanan 101.756 girdi + 7.944 çıktı token'ının tamamı deftere 0 olarak düştü. Model ekseni iki
ayrı biçimde kırıktı: (a) zincirde yedek cevapladığında satır **birincilin** modelini —üstelik
`gemini-2.5-flash-lite (fallback: 1 ek provider)` gibi insan-okur bir etiketle— yazıyordu;
(b) premortem ve yansıma yolları `model='premortem'` / `model='reflection'` yazarak **amacı**
model sütununa koyuyordu (yansıma ayrıca `provider`ı sabit 'groq' geçiyordu).

Token'ların sistemde göründüğü tek yer `reasoning_traces`'ti: gerçek token'ların yalnız **%24'ünü**
yakalıyor (yalnız koç sohbetinin ana çağrısı) ve 90 günde siliniyor — muhasebe defteri değil,
hata ayıklama yüzeyi.

## Karar

**1. Token saklanır (gerçek), maliyet de saklanır (yazma anındaki liste fiyatıyla dondurulmuş).**
Token olayın ölçülen gerçeğidir; para o anki fiyat listesine göre bir yorumdur. Yalnız token
saklamak "geçen ay ne harcadım" sorusunu bugünün fiyatıyla yanlış cevaplar; yalnız para saklamak
fiyat düzeltildiğinde geçmişi yeniden hesaplanamaz kılar. İkisi de saklanır.

**2. Fiyat (SAĞLAYICI, MODEL) çiftinin özelliğidir.** Aynı model adı farklı sağlayıcıda farklı
fiyatlıdır (`gpt-oss-120b` Groq'ta $0.15/$0.60; Cerebras'ta ayrı liste). Model adına bakan tek
düzeyli tablo sekiz sağlayıcılı zincirde sessizce yanlış para üretirdi.

**3. Bilinmeyen fiyat `None`'dır, 0 değil** — ve operatör raporunda ayrı sayılır. **Bilinen sıfır**
(yerel Ollama: kullanıcının makinesinde koşar, sağlayıcı faturası yoktur; `:free` varyantlar)
bundan ayrıdır ve 0 yazar. Ayrım şu yüzden kritik: bilinmeyeni sıfır saymak, yeni bir model
eklendiğinde maliyeti "bedava" gösterir ve hata sessiz kalır.

**4. Amaç kendi sütununda (`amac`: koc | premortem | yansima).** ADR-052'nin "karar tipte, teşhis
ayrı alanda" ayrımının buradaki karşılığı: `model` sütunu MODEL taşır; "hangi ürün yolu" meşru bir
sorudur ama cevabı modelin sütununda değil kendi sütununda durur.

**5. Ölçüm noktası kimliği de taşır.** Kota kancası (`LLMProvider.__init_subclass__` →
`_raw_chat`) ağa çıkan her isteği zaten görüyordu ama yalnız "+1" yazıyordu; artık her istek bir
KAYIT üretir (sağlayıcı, model, token) ve defter satırı o kayıttan doldurulur. Satır ↔ istek
eşlemesi birebirdir: rezervasyon satırı kayıt[0]'ı, ek satırlar kalanları taşır.

Tek kaynak: `app/llm_cost.py` (fiyat + hesap) ve `app/llm_quota.py` (ölçüm + yazma).
Deftere yazan başka yol yoktur — statik kilit `tests/test_llm_maliyet_kapisi.py`.

## Reddedilen alternatifler

- **Sağlayıcının kendi kullanım/faturalama API'sinden çekmek.** Sekiz sağlayıcıya sekiz
  entegrasyon demek; ADR-002'nin sağlayıcı-agnostik ilkesini motor katmanında deler ve jenerik
  OpenAI-uyumlu uçlarda zaten yoktur.
- **Yalnız token saklayıp maliyeti raporda hesaplamak.** Fiyat listesi değiştiğinde geçmiş
  raporlar sessizce değişirdi ("geçen ayki maliyetim" bugün başka çıkar).
- **Ücretsiz katmanı modellemek.** Kod anahtarın hangi katmanda olduğunu bilemez (fatura bize
  görünmez). Saklanan değer dürüstçe **liste fiyatı tahmini** olarak adlandırılır; ücretsiz
  katmanda gerçek fatura 0'dır ve bağlayıcı kısıt zaten çağrı sayısıdır (ADR-041 kotası onu ölçer).
- **Eski satırların bozuk `provider`/`model` değerlerini geriye dönük düzeltmek.** Gerçek model
  geriye dönük bilinemez; uydurmak defteri kirletir. O satırlar fiyat tablosunda eşleşmediği için
  raporda "fiyatı bilinmeyen" olarak görünür — sessiz sıfır değil.

## Sonuç (aynı korpus, fix sonrası)

| Eksen | Önce | Sonra |
|---|---|---|
| token'ı olan satır | 0/13 | 8/13 (kalan 5: 3 çöken deneme + 2 yerel Ollama — sağlayıcı usage döndürmez) |
| ÇALIŞAN modeli yazan satır | 7/13 | **13/13** |
| isteği yiyen sağlayıcı | 13/13 | 13/13 |
| amaç sütunu dolu | — | 13/13 |

Kapı: `tests/test_llm_maliyet_kapisi.py` (17 test, mutasyon 6/6). Operatör yüzeyi:
`python -m scripts.beta_metrics` → tahmini tutar, amaç bazında kırılım, ve **iki ayrı bilinmeyen
sayacı** (fiyatı bilinmeyen → fiyat tablosu güncellenmeli; token döndürmeyen → çöken istek/yerel).

**Not — fiyat tablosu bayatlar.** Her satır kaynak + tarih taşır (`app/llm_cost.FIYATLAR`).
Doğrulanamayan fiyat tabloya YAZILMAZ (Cerebras ve DeepInfra bugün böyle): tahmin edilmiş bir
fiyat, bilinmeyen bir fiyattan daha zararlıdır — kendinden emin yanlış sayı üretir.
