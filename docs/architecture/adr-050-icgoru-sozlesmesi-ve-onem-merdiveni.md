# ADR-050 — Kalıcı hafızada içerik YÜK, geri kalanı ETİKET; beyan edilen önem sıralamaya BAĞLANIR

**Durum:** Kabul edildi · **Tarih:** 2026-08-08 · **Faz:** PUBLISH / backlog LLM boyutu (LLM-008 kalanı)
**İlgili:** ADR-001 (karar kuralda, LLM'de değil), ADR-016 (davranışsal hafıza / Saf Karma A),
ADR-048 (aksiyon payload sözleşmesi — kardeş tool), ADR-049 (mesaj niyeti tek kaynak)
**Bug:** #268

## Bağlam

ADR-048 koçun birinci tool'unu (`propose_action`) sözleşmeye bağladı. İkinci tool'u
`save_insight` aynı işlemden geçmemişti: argümanlar ham indeksleniyor (`inp["content"]`),
doğrulanmıyor, hata yalnız log'a düşüyordu.

### Ölçüm 1 — sessiz kayıplar ve bir ÇÖKME

FakeProvider ile gerçek koç akışı, her vaka ayrı DB:

| Tool argümanı | Ölçülen davranış |
|---|---|
| `content` anahtarı yok | `KeyError` yutuldu; kayıt YOK, koç "Not aldım." dedi |
| `content` bir nesne (dict) | **TÜM KOÇ İSTEĞİ ÇÖKTÜ** (`PendingRollbackError`) |
| `expires_at: "gelecek ay"` | `ValueError` yutuldu; kayıt YOK, koç "Not aldım." |
| `dedup_key` yok (2. çağrı) | UNIQUE ihlali; kayıt YOK, koç "Not aldım." |
| `priority: "cok_kritik"` | sessizce `normal`e düştü |

İkinci satır sözleşme ihlalinden fazlasıdır: başarısız INSERT session'ı **rollback edilmemiş**
bırakıyor, sonraki `commit()` (reasoning-trace adımı) patlıyor ve kullanıcının o mesajı komple
hata dönüyordu. Bu, projenin **kendi anti-pattern listesindeki** maddedir: *"loop içinde
`db.rollback()` yerine `db.begin_nested()` — IntegrityError'da session zehirlenmesin."*
Kural yazılıydı; bu yol onu uygulamıyordu.

### Ölçüm 2 — "critical: asla unutulmamalı" bir vaat değil, bir yalandı

Tool açıklaması LLM'e bunu söylüyordu. Enjeksiyon (`format_insights_for_prompt`) ise sıralamayı
`sort_priority` (int) + `last_evidence_at` ile yapıp **`limit(5)`** uygular —
`save_insight_action` bu iki alanın **ikisini de yazmıyordu**. Kullanıcının kendi beyanı
varsayılan `sort_priority=5` ile en altta, `last_evidence_at` NULL olduğu için eşitlikte de
en sonda kalıyordu.

Ölçüm: 6 çıkarıcı gözlemi (`sort_priority=10`) + kullanıcının *"asla kredi çekmeyeceğim"*
beyanı (`critical`) → enjekte edilen blokta **beyan HİÇ YOK**, beş rutin gözlem var. Yani koç,
kullanıcının "bunu asla unutma" dediği şeyi tam olarak unutuyordu. `InsightPriority` enum'u
yazılıyor ama hiçbir yerde okunmuyordu — dekoratif alan (**L21**: sinyal hesaplanıyor ama
karar veren katmana hiç ulaşmıyor).

Prompt tarafında ikinci bir yüzü daha vardı: blok her içgörünün başına `[TİP | GÜVEN]` yazar;
bu yolda `insight_type` ve `confidence_basis` NULL olduğu için kullanıcının kendi beyanı
`[GENEL | unknown]` ve `(baslik yok)` diye görünüyordu.

### D1 araştırması

2026 pratiği ajan belleğini bir **politika katmanı** olarak kurar ve dört kaldıraç sayar:
**önem · birleştirme · çürüme · tahliye**. Önem skorlamasının kanonik deseni (Generative
Agents) yazma anında 1-10 puan üretip geri getirmede ağırlık olarak kullanır; bilinen bedeli
her yazmada bir model çağrısı ve sürümler arası kayma. Üçüncü mimari lineage
"curated working view + öncelikli Evictor" — sınırlı pencereyi önem sırasına göre elde tutmak;
bizim `limit(5)`imiz tam olarak budur. Kayıt: `docs/kalite-seruveni/research-log.md` (2026-08-08).

## Karar

1. **Tek kaynak `app/insight_schema.py`.** `save_insight` tool şeması **buradan üretilir**
   (elle yazılı ikinci liste değildi ama bir üçüncüsüydü: şema `category`/`priority`'yi
   ZORUNLU sayarken kod ikisini de opsiyonel okuyup sessizce varsayılana düşürüyordu).

2. **Başarısızlık yönü ADR-048'den bilinçli olarak FARKLIDIR.** Orada kural "uygulanamayacak
   öneri doğmaz"dı: yanlış tutarı *uygulamak*, uygulamamaktan kötüdür. Burada denge terstir —
   **içerik yüktür, geri kalanı etikettir**:

   | Alan | Bozuksa |
   |---|---|
   | `content` yok / metne dönüşmüyor / boş / çok uzun | **REDDET** (hatırlanacak şey yok; nesne DB'ye yazılamaz; tek içgörü paylaşılan bütçeyi yiyemez) |
   | `dedup_key` yok/boş | **İÇERİKTEN TÜRET** (boş anahtar UNIQUE indeksi zaten patlatıyordu; aynı gerçek aynı anahtara düşer) |
   | `category` tanınmıyor | belgeli varsayılana düş (`general`) — davranışa etki etmez, ölçüldü |
   | `priority` tanınmıyor | **AŞAĞI** düş (`normal`) — tanınmayan etiket `critical` sayılamaz |
   | `expires_at` çözülemiyor | süreyi düşür, **gerçeği tut** |

   Ve hiçbir düşüş sessiz değildir: `Ayiklama.duzeltmeler` reasoning trace'e yazılır.

3. **Beyan edilen önem, enjeksiyonun GERÇEKTEN baktığı alana yazılır.** `sort_priority`
   merdiveni tek ölçektir ve kullanıcı beyanı şuraya oturur:

   ```
   15  deterministik kırmızı-çizgi çıkarımı   (kullanıcının sözü + veri temelli)
   14  KULLANICI BEYANI: critical             (kullanıcının sözü, LLM sınıflandırması)
   12  kırmızı-çizgi K2 (zayıf kanıt)
   11  KULLANICI BEYANI: high                 (tüm desen gözlemlerinin ÜSTÜNDE)
   10..7  çıkarıcı desen gözlemleri
    5  KULLANICI BEYANI: normal               (bugünkü varsayılan — davranış değişmez)
   ```

   İlke: **kullanıcının kendi ağzından çıkan gerçek, hakkında çıkarılan desenden önce gelir;
   deterministik çıkarım ise aynı kanıt seviyesindeki LLM sınıflandırmasından önce gelir.**
   Sıra ilişkisi testte `coach_insights`'ın gerçek sabitlerinden **türetilerek** kilitlenir
   (L27) — bir çıkarıcı sabiti değişip sırayı bozarsa kapı kırmızı olur.

4. **Ayrı bir LLM "importance" çağrısı EKLENMEDİ.** Araştırmanın kanonik deseni bunu önerir
   ama bedeli her yazmada bir model çağrısı + sürüm kayması; ayrıca ADR-001 gereği önem kararı
   kuralda kalmalı. Eksik olan skoru *üretmek* değildi — var olan skoru **yazmayan** yoldu.

5. **Yazma savepoint içindedir** (`db.begin_nested()`). İçgörü düşse bile sohbet ayakta kalır.

6. **Reddedilen içgörü kullanıcıya SÖYLENİR** — ama cevap değiştirilmez, sonuna tek cümle
   eklenir. Cevabın kendisi geçerli olabilir (kullanıcı bir şey sormuş, koç doğru cevaplamış);
   ADR-048'de olduğu gibi cevabı komple değiştirmek burada bilgi kaybı olurdu. Sessizlik ise
   koçun hatırlamadığı bir şeyi hatırlıyor sanmaktır ve bu ancak aylar sonra fark edilir.

## Sonuçlar

- Kullanıcının `critical` beyanı artık enjekte edilir ve gözlemlerin **üstünde** sıralanır;
  prompt etiketi `[KULLANICI_BEYANI | user_stated]`.
- Bozuk tool argümanı koç isteğini **çökertmez**; gerçek metadata yüzünden **kaybolmaz**.
- Kapı: `tests/test_icgoru_kapisi.py` (34 test) — sözleşme yönü, merdiven sırası (gerçek
  sabitlerden türetilmiş), savepoint izolasyonu, uçtan uca akış, şema drift kilidi.
  **Mutasyon 5/5 kırmızı.**

### Yan gözlem (bu turda düzeltilmedi, dürüst kayıt)

`format_insights_for_prompt`'ın docstring'i token sayımını *"tiktoken cl100k_base
(Mem0/OpenAI standardı)"* diye anlatır; ölçüldü: **`tiktoken` ne `requirements.txt`'te ne de
venv'de kurulu** — yani sayaç her zaman `len(s)//4` yedeğiyle çalışıyor ve kodun kendi yorumu
bu yedeğin Türkçede ~%15 az saydığını söylüyor. Yani "1500 token" pratikte ~6000 karakterdir.
Zarar bu turda sınırlıdır: `limit(5)` × `ICERIK_AZAMI=600` ile enjekte edilebilecek azami
içerik ~3000 karakter, yani bütçe zaten bağlayıcı değil. Yine de belge, hiç koşmayan bir yolu
birincil gibi anlatıyor (KURAL R3 sınıfı) — bağımlılığı eklemek ya da docstring'i gerçeğe
çevirmek ayrı bir iştir.

## Reddedilen alternatifler

- **Her şeyi ADR-048 gibi reddetmek:** kullanıcının söylediği gerçeği bir etiket yanlış diye
  çöpe atardı. Yükün ve etiketin başarısızlık yönü aynı olamaz.
- **`limit(5)`i büyütmek:** tahliye baskısını çözmez, yalnız erteler ve bütçeyi (1500 token)
  gizlice şişirir. Sorun pencerenin boyu değil, pencereye **kimin girdiğine karar veren
  sinyalin yazılmamış olmasıydı.**
- **`priority` enum'unu sıralamada kullanmak (sort_priority yerine):** ikinci bir ölçek üretirdi;
  çıkarıcılar zaten `sort_priority` yazıyor. Tek ölçek, tek doğruluk kaynağı.
