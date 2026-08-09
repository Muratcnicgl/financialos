# ADR-051 — Sağlayıcı hataları ÖNCE YAPIDAN sınıflandırılır; metin deseni sayı içermez

**Durum:** Kabul edildi · **Tarih:** 2026-08-08 · **Faz:** PUBLISH / backlog LLM boyutu (LLM-012 + LLM-011)
**İlgili:** ADR-002 (provider-agnostic LLM), ADR-004 (fallback sırası), ADR-028 (sağlayıcı hibrit),
ADR-049 (mesaj niyeti tek kaynak — aynı "desen yerine sözleşme" hamlesi)
**Bug:** #269

## Bağlam

Canlı yapılandırma `LLM_PROVIDER=fallback`: koçun cevap verebilmesi zincirin bir hatayı **doğru
sınıflandırmasına** bağlı. Zincir üç soruya cevap verir — tekrar denenir mi (`_is_retryable_error`),
sağlayıcı atlanır mı (`_is_quota_exceeded`), sağlayıcı process boyunca kara listeye alınır mı
(`_is_request_too_large`) — ve üçü de hata metninde **alt-dizi** arıyordu. Sayısal durum kodları da
düz metin gibi aranıyordu (`"429"`, `"503"`, `"504"` birer anahtar kelimeydi).

### Ölçüm (10 gerçekçi sağlayıcı hata metni): **3/10 yanlış**

| Hata metni | Doğrusu | Ölçülen |
|---|---|---|
| `400 INVALID_ARGUMENT: The input token count (8504) exceeds the maximum...` | kalıcı / çok-büyük | **geçici** |
| `500 Internal error encountered. request_id=req_8429fa1c` | geçici | **kota** |
| `Latency budget exceeded: upstream took 4290 ms` | kalıcı | **kota** |

Üçü de aynı kökten: `"504"` **8504**'ün içinde, `"429"` ise **4290** ve **req_8429fa1c**'in içinde
geçiyor. Yani fallback zincirinin kararını, hatayla hiç ilgisi olmayan bir sayının rakamları
veriyordu.

**Zarar sıralı, birincisi en ağırı.** Token limitini aşan bir istek **kalıcı** hatadır — aynı prompt
her seferinde aynı hatayı verir. "Geçici" sayıldığı için `_call_with_retry` onu 1sn + 2sn bekleyerek
**üç kez** deniyor; üstelik `_is_request_too_large` bu metni tanımadığı için `_oversized_providers`
devre kesicisi **hiç açılmıyor**: sağlayıcı **her koç isteğinde** yeniden deneniyor, her denemede
kullanıcının LLM kotası yazılıyor (BUG #234 sayacı gerçek istekleri sayar) ve cevap üç saniye
geç geliyordu. İkinci satırda sağlıklı bir sağlayıcı "kotası doldu" denip devre dışı bırakılıyor;
üçüncüde alakasız bir gecikme hatası kota sanılıyor.

Yan bulgu (aynı kod bölgesi, LLM-011): geri çekilme `taban * 2^(deneme-1)` ile **sabitti** — aynı
anda düşen istekler aynı anda uyanıp sağlayıcıyı ikinci kez birlikte döver.

## Karar

1. **Tek kaynak `app/provider_errors.py`.** Sınıflandırma tek bir `siniflandir(exc)` çağrısıyla
   yapılır ve dört sınıf döner: `kota` · `gecici` · `istek_cok_buyuk` · `kalici`. Karar nesnesi
   **gerekçe** ve kullanılan **durum kodunu** taşır (log ve trace okunabilir olsun — BUG #253 ilkesi).

2. **Önce YAPI, sonra metin.** Durum kodu istisnanın alanından (`status_code`/`code`/`http_status`)
   okunur; yoksa metnin **başından** ya da açık etiketten (`Error code: NNN`, `'code': NNN`).
   Gövdedeki rastgele bir sayı durum kodu sayılmaz.

3. **Metin desenleri SAYI İÇERMEZ.** Sayısal kod arayan desen bırakılmadı. Bu, kapıda
   kaynak-türetimli bir drift kilidiyle kilitlendi: desen literalinde çıplak üç haneli sayı
   bulunursa test kırmızı olur.

4. **Öncelik sırası KALICI > KOTA > GEÇİCİ.** Bir metin birden çok işaret taşıyabilir (Groq'un
   413'ü *"Limit 8000, Requested 8429"* der). Kalıcı olan kazanır, çünkü **yanlış tarafa düşmenin
   bedeli asimetriktir:** kalıcıyı geçici sanmak sonsuz tekrar üretir; geçiciyi kalıcı sanmak
   yalnız bir denemeyi kaçırır. Bu sıralama aynı zamanda operatörün gördüğü gerekçeyi düzeltir —
   Groq'un 413'ü artık "quota doldu" diye loglanmıyor.

5. **Geri çekilme tam-jitter** (`[0, min(tavan, taban·2^(n-1))]`, tavan 30 sn) ve rastgelelik
   **enjekte edilebilir** — kapı bekleme davranışını rastgeleliğe bağlı kalmadan ölçer.

6. **İsimler geriye uyumlu.** `coach.py` üç eski adı re-export eder; çağıranlar ve mevcut testler
   değişmedi.

## Sonuçlar

- Sınıflandırma korpusu **3/10 yanlış → 0/10**. Token-limiti hatası artık kalıcı sayılıyor ve
  devre kesici açılıyor (kapıda uçtan uca ölçülüyor).
- Kapı: `tests/test_saglayici_hata_kapisi.py` (39 test) — korpus, sayı-bağışıklığı (8 gömülü
  sayı), öncelik sırası, karar bayrakları, kaynak-türetimli drift kilidi, jitter aralığı,
  zincir davranışı. **Mutasyon 5/5 kırmızı.**

## Reddedilen alternatifler

- **Desenlere `\b` eklemekle yetinmek:** üç vakayı da düzeltirdi, ama karar hâlâ metne bağlı
  kalırdı — sağlayıcı yarın hata metnini değiştirdiğinde sessizce yanlışa döner. Yapı (durum
  kodu) sağlayıcı sürümlerine karşı dayanıklı olan tek sinyaldir; metin ikinci yoldur.
- **Sağlayıcıya özgü tipli istisnalara geçmek** (`anthropic.RateLimitError`, `google.api_core`
  hataları): ADR-002'nin provider-agnostic ilkesini zedeler, sekiz sağlayıcının SDK'sını
  motor katmanına sızdırır ve `_OpenAICompatMixin` ile gelen jenerik sağlayıcılar için zaten
  çalışmaz. Durum kodu bu SDK'ların **ortak paydasıdır**.
- **Kota hatasını da retry etmek:** kota dakika başı sıfırlanabilir ama zincirin işi zaten bir
  sonraki sağlayıcıya geçmektir; beklemek kullanıcıyı bekletir. Mevcut davranış korundu.
