# ADR-048 — LLM'in ürettiği aksiyon payload'ı ONAY ÖNCESİNDE doğrulanır

**Durum:** Kabul edildi · **Tarih:** 2026-08-07 · **Faz:** PUBLISH / backlog LLM boyutu (LLM-008)
**İlgili:** ADR-001 (Rules Engine karar verir, LLM açıklar), ADR-044 (para birimi tek kaynak),
ADR-046 (kategori kaydı — "anlam koddan veriye" aynı sınıf)
**Bug:** #266

## Bağlam

`app/action_executor.py`'nin kendi ilkesi şudur: *"Master Checkpoint enforcement kod seviyesinde
uygulanır — LLM'in prompt'una güvenilmez."* Bu ilke **payload için uygulanmamıştı**:
`propose_action` yalnız `action_type`'ı doğruluyor, payload'ın şeklini tamamen LLM'e bırakıyordu.
Tek kural sistem prompt'undaki *"PAYLOAD ŞABLONLARINA uygun yaz"* cümlesiydi.

Ölçüm (7 Ağu 2026, FakeProvider ile gerçek koç akışı koşuldu):

| Girdi | Ölçülen davranış |
|---|---|
| `amount: "uc yuz yirmi"` | Bekleyen aksiyona **yazıldı**, kullanıcıya "320 TL … kaydedildi" özetiyle gösterildi. Onaylanınca execute "amount sonlu ve pozitif olmalı" deyip **hiçbir şey yazmadı**. |
| `summary="320 TL …"` + `payload={"amount": 3200}` | **Onaya gitti.** Kullanıcının okuduğu tutar ile uygulanacak tutar 10 kat farklıydı; hiçbir denetim yoktu. |
| `{}` / `summary` yok / `payload` string | Sessizce yutuldu (`inp["action_type"]` → KeyError → trace yuttu); kullanıcıya konuyla ilgisiz "Hangi hesaptan harcadın?" soruldu. |

İkinci bulgu arayüzle birleşince ağırlaşıyordu: `add_transaction` payload'ı okunabilir tabloya
çevriliyor, **diğer altı tür** (kart ödemesi, bakiye düzeltmesi, fon fiyatı, yatırım satışı, borç
kapatma) kapalı bir `<details>` içinde ham JSON gösteriliyordu — yani para hareketlerinde kullanıcı
pratikte yalnız özeti görüp onaylıyordu.

## Karar

1. **Doğrulama onay ÖNCESİNDE, `propose_action` sınırındadır.** Uygulanamayacak bir öneri
   **doğmaz**. Tüketiciye (execute) bırakmak, kullanıcının onayladığı şeyin hiç uygulanamayacağını
   onaydan *sonra* öğrenmesi demektir — ve arada "Kaydettim." cümlesi ekranda kalır.
2. **Tek kaynak `app/action_schema.py`.** Her `action_type` için Pydantic modeli; para alanları
   `app/schema_types.py` sonlu-değer tipleridir (SEC-032).
3. **`extra="forbid"`.** Bilinmeyen alan sessizce yutulmaz: LLM `amout` yazarsa tutar kaybolur ve
   kullanıcı bunu ancak parası yanlış olunca fark eder (L28). Reddedilen çağrı koçun mevcut retry
   yoluna düşer (`HESAP_BELIRSIZ`/`TARIH_BELIRSIZ` ile aynı mekanizma).
4. **Eksik opsiyonel alan varsayılanla DOLDURULMAZ.** Koç `transaction_date` yazmadıysa
   yazmamıştır; sunucu gününü buraya koymak BUG #237'nin ta kendisiydi.
5. **Özet ile payload aynı gerçeği söylemek zorundadır.** Para hareketi türlerinde özetteki tutar
   payload'daki tutarla eşleşmeli (0,01 tolerans; TR `19.700,50` ile `19700.5` aynı sayıdır) ve
   özet tutarı **söylemek** zorundadır. Bu, `app/grounding.py` ilkesinin ("koçun her TL'si
   izlenebilir olmalı") onay yolundaki karşılığıdır.
6. **Reddedilen öneri kullanıcıya GÖRÜNÜR.** Sessiz kalmak, koçun "Kaydettim." cümlesini ekranda
   bırakır ve kullanıcı olmayan bir kaydı doğru sanar (BUG #049 ailesi).
7. **Prompt şablonları şemadan ÜRETİLİR.** `PAYLOAD ŞABLONLARI` prompt'ta elle yazılı **üçüncü**
   bir listeydi; şema değişince sessizce bayatlar, koç reddedilecek payload üretmeye devam ederdi.
   İzin verilen değerler kümesi (enum) alanın kendi tanımıyla birlikte yaşar (`json_schema_extra`),
   böylece türetme sırasında kaybolmaz.
8. **Arayüzde onaylanan alanlar açık gösterilir.** Ham JSON teşhis için `<details>` altında kalır.

## Alternatifler (reddedildi)

- **Doğrulamayı execute'ta bırakmak (mevcut durum).** Kullanıcı onayladıktan sonra hata alır;
  ekranda kalan "kaydedildi" cümlesi yanlıştır.
- **Sağlayıcı tarafında JSON-schema zorlaması (strict tool calling).** Sekiz sağlayıcının hepsinde
  aynı değil; Gemini `MALFORMED_FUNCTION_CALL` ile zaten düşüyor. Sözleşme kendi kodumuzda olmalı.
- **Şemayı gevşetip (`extra="allow"`) bilinmeyen alanı yok saymak.** Sessiz kayıp üretir — bu
  projenin tekrar tekrar kapattığı sınıfın ta kendisi.

## Kapı

`tests/test_aksiyon_payload_kapisi.py` (23 test): davranış + **kapsam tabanı** (her `action_type`'ın
şeması var; handler'ın AST'den çıkarılan her payload anahtarı şemada var ve tersi; prompt şablonu
şemadan üretiliyor). `frontend/src/bekleyen-aksiyon-gorunurluk.test.jsx` (4 test) onay ekranındaki
görünürlüğü kilitler. **Mutasyon 3/3 KIRMIZI:** şema doğrulaması kaldır → kırmızı; özet-payload
denetimi kaldır → kırmızı; prompt şablonunu şemadan kopar → kırmızı.
