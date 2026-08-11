# Research Log (KURAL D1 — sektör araştırmaları)

Her mimari/teknoloji kararı öncesi 2-3 sektör referansı; bulgular burada.

## 2026-08-11 (2) — GoDaddy dahil alan adı + barındırma tam taraması (B0 eki)
**Soru:** "Ücretsiz yapılabileni ücretsiz yap, kalanı fiyat/performansı en iyi olanla."
GoDaddy ayrıca istendi. Tam belge: `b0-barindirma-arastirmasi.md`.

**Bulgu 0 — teknik kısıt fiyattan ÖNCE gelir.** `docker-compose.prod.yml` **6 servis**
(postgres + 2 uvicorn worker + scheduler + nginx + certbot + backup) → Docker + root +
kalıcı disk zorunlu. **Paylaşımlı/cPanel hosting teknik olarak elenir** (GoDaddy'nin ucuz
"web hosting" paketleri dahil); gereken şey VPS. RAM ~1–1,5 GB sürekli → 2 GB dar, 4 GB rahat.

**Bulgu 1 — GoDaddy alan adında EN PAHALI.** 1. yıl 4,99–11,99 $ ama yenileme
**21,99–22,99 $** (+%92) ve WHOIS gizliliği 1. yıldan sonra 9,99 $/yıl → 5 yıl ≈ **100–104 $**.
Cloudflare Registrar sabit 10,44 $ → 5 yıl ≈ **52 $**. Ölçüt yıllık fiyat değil **5 yıllık
gerçek maliyet**; bu pazarın tuzağı ilk yıl indirimidir.

**Bulgu 2 — ücretsiz PaaS bu yığını barındıramaz.** Render ücretsiz Postgres **30 gün sonra
sona eriyor** (+14 gün sonra VERİ SİLİNİR), web servisi 15 dk'da uyuyor (→ 02:45 cron hiç
koşmaz), cron servisi ücretsiz değil. Fly.io ücretsiz katmanı 2024'te kaldırıldı. Railway'de
ücretsiz katman yok. **Tek gerçek ücretsiz 7/24 seçenek Oracle Always Free** ve o da kapasite
piyangosu (home region kayıttan sonra değişmez).

**Bulgu 3 — GoDaddy VPS fiyat/performansta elenir.** 8,99 $/ay ama **36 ay peşin** şartıyla,
yenilemede ~2 kat; karşılığında 1 vCPU / 2 GB. Hetzner CX22 2 vCPU / 4 GB **€3,79**
(bir kaynak CX23 için €5,99 diyor — SKU sipariş anında doğrulanacak). Netcup €3,35 (2 GB —
dar). Contabo €4,50 / 6 GB ama bağımsız kaynaklar **CPU overselling** notu düşüyor.

**Yazılmayanlar (L45):** Türkiye lokasyonlu VPS'ler (Natro/Turhost/Radore/Komuta) —
yalnız pazarlama sayfası ve affiliate listesi bulundu, bağımsız kıyas/uptime/Docker teyidi
YOK. Görülen aralık ~103–170 TL/ay **gösterge olarak** kaydedildi, fiyat olarak değil.
Gerçek avantajları var (TRY fatura, Türkçe destek, ~10 ms gecikme) → ciddiye alınacaksa
taahhütsüz 1 ay deneyip ÖLÇMEK doğru yol. TL kuru çevrimi yapılmadı.

**Kaynaklar:** priceworld.com/domains/godaddy · hostingrevelations.com · nameexperts.com ·
domaindetails.com · spendbase.co (`.app` 12,18 $) · kb.porkbun.com + comodosslstore.com
(`.app` HSTS preload) · render.com/changelog + /docs/free · saaspricepulse.com (Fly.io) ·
northflank.com (Railway) · hostadvice.com + cybernews.com (GoDaddy VPS) · sliplane.io +
experte.com (VPS kıyas) · danubedata.ro (Contabo) · docs.oracle.com/iaas (home region)

## 2026-08-11 — Kapalı beta barındırma: alan adı + tünel vs VPS (B0 / P6)
**Soru (D1 tetiği #1 + #2):** Barındırma platformu seçimi geri dönüşü pahalı (dağıtım platformu)
ve cevap dış dünyanın durumunda (fiyat listeleri, ücretsiz katman şartları). Üç seçenek ölçüldü.

**Bulgu 1 — alan adı, seçenekten bağımsız TEK zorunlu harcama.** Ücretsiz/geçici tünel adresleri
her yeniden başlatmada değişir; telefona kurulmuş PWA farklı origin görüp **kırılır**. Cloudflare
Registrar maliyetine satıyor: `.com` **10,44 $/yıl** (kayıt = yenileme, ilk yıl indirimi yok,
yenileme zammı yok). Porkbun 11,08 $ düz; Namecheap ilk yıl 6,79 $ ama yenileme 14,78 $.

**Bulgu 2 — Cloudflare Tunnel ücretsiz ve sınırsız, ama alan adını kendi DNS'ine bağlıyor.**
Özel alan adı destekli, giden-bağlantı temelli (port açmak gerekmez). Alan adı Cloudflare
Registrar'dan alınırsa DNS adımı kendiliğinden çözülür. **Yan sonuç:** TLS Cloudflare kenarında
biter → hazır olan nginx/Let's Encrypt yığını bu yolda DEVREDE OLMAZ, B'ye geçişte ilk kez canlıda
sınanır.

**Bulgu 3 — Hetzner CX22 €3,79/ay** (2 vCPU / 4 GB / 40 GB). `deploy.sh` + `docker-compose.prod.yml`
+ nginx/LE tam olarak bu senaryo için yazılmış.

**Bulgu 4 (repo ölçümü, dış kaynak değil) — "makine kapalıysa veri kaybolmaz, gecikir" iddiası
YARIM DOĞRU.** `catch_up_snapshots()` yalnız `NetWorthSnapshot` boşluğunu doldurur; beş planlı işin
hiçbirinde catch-up yok (`misfire_grace_time=3600` yalnız 1 saat tolere eder). Somut sonuç: makine
gece 02:45'te kapalıysa **o günün yatırım fiyatı `price_history`'ye hiç yazılmaz**. Elle telafi
yolu var (`POST /api/fund-price/update`) ve tazelik yüzeyi bayatlığı söyler (BUG #239).

**Karar:** karar Murat'ın (para + ürün-DNA). Tavsiye: A ile başla → yatırım hesabı kullanılacaksa
fiyat çekimini açılış catch-up'ına ekle → P8'den önce B'ye geç. Tam not:
`b0-barindirma-karar-notu.md`.
**Kaynaklar:** tldprice.org/registrar/cloudflare · startupowl.com (Cloudflare Registrar) ·
makerstack.co + toolradar.com (Tunnel ücretsiz katman/DNS şartı) · hetzner.com + vpsfor.dev
(CX22) · domaindetails.com (registrar 5 yıllık toplam) · repo: `app/startup.py`, `app/scheduler.py`

## 2026-08-10 — LLM maliyet muhasebesi: neyi SAKLA, neyi HESAPLA (BUG #274 / LLM-006, OBS-005)
**Soru (D1 tetiği #1 + #2):** `api_call_log`'a maliyet eklenecek — şema değişikliği (geri dönüşü
pahalı) ve fiyatlar DIŞ DÜNYANIN durumu (sağlayıcı fiyat listeleri). İki karar: (a) token mü
saklanır, maliyet mi, ikisi de mi? (b) fiyat tablosu nerede yaşar ve bilinmeyen model ne olur?

**Bulgu 1 — token GERÇEK, maliyet TÜREV; ama türev de dondurulur.** Sağlayıcıların kendi
kullanım API'leri bu ayrımı yapıyor: token sayıları olayın ölçülen gerçeğidir, para ise o anki
fiyat listesine göre hesaplanmış bir yorumdur. Fiyat listesi değiştiğinde geçmiş satırların
parası değişmemelidir (aksi halde "geçen ayki maliyetim" bugün başka çıkar) → maliyet **yazma
anında hesaplanıp SAKLANIR**, token'lar da ayrıca saklanır ki yeni fiyatla yeniden hesaplanabilsin.
İkisinden birini seçmek iki ayrı yeteneği kaybettiriyor: yalnız token → "bugüne kadar ne harcadım"
sorusu geçmişe dönük fiyatla yanlış cevaplanır; yalnız maliyet → fiyat düzeltilince geçmiş
düzeltilemez.

**Bulgu 2 — fiyat SAĞLAYICI+MODEL çiftinin özelliğidir, modelin değil.** Aynı model adı farklı
sağlayıcıda farklı fiyatlıdır: `gpt-oss-120b` Groq'ta $0.15/$0.60 (1M token, giriş/çıkış), aynı
ad Cerebras'ta ayrı bir liste; `llama-3.3-70b` Groq'ta $0.59/$0.79 iken OpenRouter'ın `:free`
varyantı 0. Model adına bakan tek düzeyli bir tablo, sekiz sağlayıcılı zincirimizde sessizce
yanlış para üretirdi (ADR-051'in "önce yapı" dersinin fiyat karşılığı).

**Bulgu 3 — ücretsiz katman fiyat listesinde GÖRÜNMEZ.** Gemini 2.5 Flash-Lite'ın ücretsiz
katmanı var (ücretli: $0.10/$0.40); Groq/OpenRouter'ın ücretsiz modelleri de öyle. Kod hangi
katmanda olduğumuzu ANLAYAMAZ (anahtarın faturası bize görünmez) → saklanan değer dürüstçe
**"liste fiyatına göre tahmin"** olarak adlandırılır; ücretsiz katmanda gerçek fatura 0'dır ve
bağlayıcı kısıt zaten çağrı sayısıdır (mevcut kota muhasebesi onu ölçüyor).

**Karar:**
1. `api_call_log` hem `tokens_in/tokens_out` (gerçek) hem `est_cost_usd` (o anki liste fiyatıyla
   dondurulmuş tahmin) taşır.
2. Fiyat tablosu **(sağlayıcı, model)** ile anahtarlanır; her satır kaynak + tarih taşır.
3. **Bilinmeyen model 0 değil BİLİNMEYEN'dir** (`None`) ve operatör raporunda ayrı sayılır —
   yeni bir model eklendiğinde maliyet sessizce sıfır görünemez. Bilinen sıfır (yerel Ollama,
   `:free` varyantlar) bilinmeyenden ayrı tutulur.
4. Sağlayıcının kendi kullanım/faturalama API'sinden çekme YAPILMAZ: sekiz sağlayıcıya sekiz
   entegrasyon demek, ADR-002'nin sağlayıcı-agnostik ilkesini motor katmanında deler ve jenerik
   OpenAI-uyumlu uçlarda zaten yok.
**Kaynaklar:** ai.google.dev/gemini-api/docs/pricing · console.groq.com/docs/models ·
console.groq.com/docs/model/openai/gpt-oss-120b · aipricing.guru/groq-pricing (10 Ağu 2026 teyidi) ·
Anthropic model/fiyat tablosu (claude-api skill, cache 2026-06-24).

---

## 2026-08-07 — Kullanıcı-tanımlı kategori modeli (H4 kuyruğu / BUG #264, ADR-046)
**Soru:** Kategori seti kullanıcı başına olmalı (P3.5 ürünleşme). Şemaya dokunuyor, geri dönüşü
pahalı (D1 tetiği #1) — sektör kategoriyi nasıl modelliyor? Özellikle: kod, kategori ADINA bakarak
karar verebilir mi? (Bizde veriyor: `_CARD_CATEGORIES` = {"yemek","eglence","sigara","alisveris",
"market"} bir harcamanın KART'a mı yazılacağını belirliyor.)

**Bulgu 1 — sistem kategorisi ≠ kullanıcı kategorisi, ve bu bir BAYRAKTIR, ad değil.** YNAB API
kategori/kategori-grubu kaynaklarına `internal: boolean` alanı taşıyor ("internally managed");
Actual Budget'ta gelir grubu "can ever exist and it cannot be deleted". Yani muhasebe anlamı taşıyan
kategoriler (transfer, açılış bakiyesi, gelir) kullanıcının serbestçe yeniden adlandırdığı kümeden
AYRI tutuluyor ve silinemiyor. **Bizdeki karşılığı:** `_PATTERN_EXCLUDED_CATEGORIES`
(`transfer`/`borc_odeme`/`kredi_taksiti`) fiilen bu `internal` bayrağının sabit-kodlu hâli —
kullanıcı "borç ödeme"yi "borç kapama" diye adlandırdığı an dışlama sessizce ölür ve kişisel
harcama paterni raporu muhasebe işlemini harcama sanır.

**Bulgu 2 — silme, referans bütünlüğünü bozmadan YENİDEN ATAMA'dır.** Actual: "If the category
you're deleting has a positive balance OR has been used for existing transactions you will be
presented with a box to select which category the balance and/or transactions should be moved to"
— birleştirme (merge) bu akışın kendisi. Ayrıca YNAB'da **gizleme (`hidden`) silmeden ayrı**: artık
kullanılmayan kategori listeyi kirletmez ama geçmiş kayıt bozulmaz.

**Bulgu 3 — varsayılan set tohumlanır, dayatılmaz.** Uygulamalar yaygın bir başlangıç seti verir
(Food & Groceries, Rent/Mortgage, Utilities) ve tamamı özelleştirilebilir; göç rehberleri bile
"önce en çok kullandığın 10 kategoriyi yeniden kur" diyor — yani set kullanıcının, uygulamanın değil.

**Sonuç (karar):** Kategori bir **kayıt** olur (kullanıcı/workspace kapsamlı), `Transaction.category`
serbest metin olarak KALIR ve kaydın `slug`'ıyla eşleşir (geriye dönük uyum + veri kaybı yok).
Kod hiçbir kararı kategori ADINA bağlamaz; kararlar kayıttaki bayraklara bağlanır:
`kart_varsayilani` (eski `_CARD_CATEGORIES`) ve `sistem` (eski `_PATTERN_EXCLUDED_CATEGORIES`).
Mevcut kullanıcıların DB'sindeki ayırt edici kategori değerleri migration'da kayda dönüştürülür ve
bayraklar eski sabit kümelerden türetilir → **davranış değişmez, sahiplik değişir.** Silme = hedefe
taşı (merge) veya gizle. Ayrıntı ve gerekçe: `docs/architecture/adr-046-kullanici-kategorileri.md`.
**Kaynaklar:** actualbudget.org/docs/budgeting/categories · api.ynab.com/v1 (Category `internal`/
`hidden`/`deleted` alanları) · github.com/actualbudget/actual PR #4294 (nYNAB gizli kategori göçü) ·
lunchmoney.app/blog/how-to-choose-the-right-budget-categories

---

## 2026-08-08 — Ajan belleğinde ÖNEM ve TAHLİYE politikası (BUG #268 / save_insight)
**Soru:** Koçun kalıcı hafızası prompt'a enjekte edilirken hangi kayıt düşer, hangisi kalır?
Bizde `limit(5)` + `sort_priority DESC` var; kullanıcının "asla unutma" dediği gerçek düşüyordu.
Sektör bu tahliyeyi neye göre yapıyor?
**Bulgu:** 2026 pratiği belleği bir **politika katmanı** olarak kuruyor ve dört kaldıraç sayıyor:
**önem (importance) · birleştirme (merge) · çürüme (decay) · tahliye (eviction)** — Mem0 / Zep /
Letta / LangMem / Hindsight karşılaştırmalarının ortak çerçevesi bu. Önem skorlaması için kanonik
desen Generative Agents'ın 1-10 "importance" puanı: yazma anında hesaplanır, SAKLANIR ve geri
getirmede ağırlık olarak kullanılır; bilinen maliyeti her yazmada bir model çağrısı ve model
sürümleri arası kayma. Üçüncü lineage "curated working view + öncelikli Evictor" (PEEK) — yani
sınırlı bir pencereyi ÖNEM sırasına göre elde tutmak; bizim `limit(5)`imiz tam olarak budur,
eksik olan tarafı önem sinyalinin yazma yolunda hiç set edilmemesiydi.
**Karar (bize uyarlaması):** Ayrı bir LLM "importance" çağrısı EKLENMİYOR (maliyet + kayma +
ADR-001: karar kuralda, LLM'de değil). Zaten var olan önem merdiveni (`sort_priority`, 1..15)
tek kaynağa alınıyor ve koçun `save_insight`'ının BEYAN ETTİĞİ öncelik bu merdivene bağlanıyor —
yani skoru üretmek için yeni bir mekanizma değil, var olan skoru YAZMAYAN yolu kapatmak.
Kullanıcının kendi sözüyle beyan edilen gerçek, desen gözlemlerinin üstünde ama deterministik
kırmızı-çizgi çıkarımının (15) altında konumlanır.
**Kaynaklar:** mem0.ai/blog/state-of-ai-agent-memory-2026 · hindsight.vectorize.io/blog/2026/05/21/agent-memory-consolidation ·
vectorize.io/articles/best-ai-agent-memory-systems · arxiv.org/pdf/2606.12945 (çok-faktörlü değer modeli) ·
maidul-haque.vercel.app/blog/agent-memory-architectures-2026

---

## 2026-07-12 — OpenRouter (koç sağlayıcı fallback, ADR-028)
**Soru:** Gemini-only kısıtına (Groq/Cerebras TPM aşımı) alternatif fallback var mı?
**Bulgu:** OpenRouter = birleşik LLM router (300+ model, 60+ sağlayıcı, tek API key). Ücretsiz katman: 20+ model (Llama 3.3 70B, GPT-OSS 120B, Qwen3 Coder, Nemotron); ücretsiz lineup rotasyonlu. **Rate limit istek-bazlı: 50/gün (kredisiz) veya 1000/gün ($10+), 20/dk — TPM sınırı YOK** → zengin koç prompt'u (~8000 token) için Groq/Cerebras'tan daha uygun. `openrouter/free` auto-router (Şub 2026) uygun ücretsiz modele yönlendirir. Fallback-faturalama: yalnız başarılı çağrı ücretlendirilir. PAYG %5.5 platform ücreti; BYOK opsiyonu.
**Sonuç:** Wave-3 en güçlü koç-fallback adayı. Canlı kalite/latency/TR-erişim testi gerekli (ADR-034). Wave-2'de eklenmez (mevcut Gemini yeterli).
**Kaynaklar:** openrouter.ai/pricing · openrouter.ai/openrouter/free · openrouter.ai/blog/tutorials/free-llm-apis-compared

---

## Wave-3 D1 Araştırma Kuyruğu (M7 — henüz YAPILMADI, Wave-3 başında)

Her ADR (031-034) için karar öncesi 2-3 sektör referans (KURAL D1). Bu kuyruk M7 hazırlıkta MATERYALIZE edildi; araştırma+karar Wave-3'te.

- **ADR-031 multi-asset:** CoinGecko/Binance API + rate-limit, TCMB EVDS döviz, Beancount commodities / Firefly asset-classes modelleri, Numeric(28,8) kripto.
- **ADR-032 mobil:** iOS Safari PWA capability 2026 (push/install kısıtları), Expo Router olgunluğu, PWA vs native retention.
- **ADR-033 auth:** JWT vs Firebase vs Supabase (TR-KVKK uyum), FastAPI auth pattern, OWASP ASVS multi-user, PostgreSQL geçiş.
- **ADR-034 koç:** LangGraph vs custom router, OpenRouter canlı fallback testi (research-log yukarıda: 50/gün TPM-sınırsız), intent-classification maliyet/fayda, prompt caching.

**Not:** M7 charter'ı "karar VERME" der — bu kuyruk kararların İSKELETİ, kararlar değil.

---

## 2026-08-10 — Gemini free-tier günlük istek limiti (eval koşumu sırasında ÖLÇÜLDÜ)
**Soru:** Yan-yana sağlayıcı koşumu (LLM-005 / BUG #278) pratikte kaç kez koşulabilir?
**Bulgu (kanıt: canlı 429 gövdesi):** `gemini-2.5-flash-lite` ücretsiz katman
`GenerateRequestsPerDayPerProjectPerModel-FreeTier` **quotaValue: 20** — yani **günde 20
istek**. Repo dokümanı (`app/coach.py` başlığı, mimari notları) yıllardır "Flash-Lite
1000/gün ücretsiz" diyordu; bu değer BAYAT. Tek bir `eval_runner --judge` koşumu 8 koç +
8 judge = 16 istek harcar → günde **bir** tam koşum sığar, yan-yana koşumda Gemini ikinci
sırada zaten düşer.
**Sonuç:** (a) docstring düzeltildi; (b) judge için ayrı sağlayıcı bayrağı
(`--judge-saglayici`) yalnız yanlılık değil KOTA açısından da gerekli; (c) yan-yana
koşumda "GEÇERSİZ (sağlayıcı cevap vermedi)" etiketi kota tükenmesini kalite düşüşü gibi
göstermiyor (BUG #276 dersinin yeni yüzeydeki karşılığı — ölçüldü, çalışıyor).
**Kaynak:** canlı API yanıtı (429 RESOURCE_EXHAUSTED, quotaId
`GenerateRequestsPerDayPerProjectPerModel-FreeTier`, 10 Ağu 2026) ·
ai.google.dev/gemini-api/docs/rate-limits
