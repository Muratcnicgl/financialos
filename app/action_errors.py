"""
Aksiyon reddi sinyalleri — TEK KAYNAK (BUG #273, backlog BE-006 + RESIL-019).

`propose_action` bir öneriyi reddettiğinde ortaya BİR KARAR çıkar: kullanıcıya ne
söyleyeceğiz, tekrar denemenin anlamı var mı, olay iz kaydına ne düşecek. Bu karar
`app/provider_errors.py` (BUG #269) öncesindeki sağlayıcı-hata sınıflandırmasıyla aynı
hataya düşmüştü: **sinyal serbest metinle taşınıyor, her tüketici metni kendi eliyle
tarıyordu** (`if "HESAP_BELIRSIZ" in str(e)`).

------------------------------------------------------------------------------
ÖLÇÜM (8-9 Ağu 2026 — gerçek koç akışı, ScriptedProvider, her vaka ayrı DB)
------------------------------------------------------------------------------
Dört sinyal × iki koç tüketicisi (ana akış + retry) matrisi koşuldu:

| sinyal                 | ana akış | retry akışı                                  |
|------------------------|----------|----------------------------------------------|
| HESAP_BELIRSIZ         | ✅       | ✅                                            |
| TARIH_BELIRSIZ         | ✅       | ❌ **hiç ele alınmıyordu**                    |
| PAYLOAD_GECERSIZ       | ✅       | ✅                                            |
| OZET_PAYLOAD_CELISKISI | ✅       | ✅                                            |

Retry yolundaki `if/elif` zinciri ana akıştan ELLE kopyalanmış ve kopyalanırken bir dal
düşmüştü. Sonuç: birinci LLM çağrısı tool çağırmayıp retry'a düşen bir harcamada, özette
tarih olup payload'da olmadığında işlem KAYDEDİLMİYOR ve kullanıcıya tarih sorusu da
SORULMUYORDU — hata `else` dalına düşüp `logger.error("retry propose_action hatasi: ...")`
olarak yutuluyordu. Kullanıcı ekranda modelin özgün metnini görüyor, neyi düzeltmesi
gerektiğini öğrenemiyordu.

İkinci eksen — **iç kod kullanıcının ekranında**: `s.observation = f"Belirsizlik: {str(e)}"`
satırı `reasoning_traces.observation` alanına yazılır ve `TracePanel.jsx` bunu "Gözlem"
satırı olarak RENDER EDER. Ölçümde dört sinyalin dördü de ham hâliyle ekrana çıkıyordu
(`Belirsizlik: HESAP_BELIRSIZ`). Türkçe bir arayüzde büyük harfli bir iç sinyal adı
kullanıcıya hiçbir şey anlatmaz; üstelik "belirsizlik" kelimesi payload reddi için yanlıştır.

Üçüncü eksen — **KVKK**: sinyal ile teşhis metni AYNI string olduğu için, sinyali loglayan
kod kullanıcının TUTARLARINI da logluyordu:
`propose_action payload reddedildi: OZET_PAYLOAD_CELISKISI: ozetteki tutar(lar) [3200.0]
ile payload amount=320.0 uyusmuyor` — iki ayrı satırda ölçüldü. BUG #180 ilkesi ham
finansal metnin log'a düşmemesini şart koşar; burada ilke, sinyalin biçimi yüzünden
delinmişti.

------------------------------------------------------------------------------
SÖZLEŞME
------------------------------------------------------------------------------
1. **Karar TİPE bakar, metne değil.** Tüketici `except AksiyonReddi` yazar; hangi alt
   sınıfın geldiğini bilmek zorunda değildir, çünkü kullanıcıya söylenecek cümle, iz
   kaydına düşecek gerekçe ve retry kararı SINIFIN ÜZERİNDEDİR. Böylece yeni bir sinyal
   eklendiğinde hiçbir tüketici "bir dalı unutamaz" — unutulacak dal yoktur (L42).
2. **Tutar/serbest metin `str(e)`'ye GİRMEZ.** Değer taşıyan teşhis yalnız `.teshis`
   alanındadır ve loglanmaz/persist edilmez. Dikkatsiz bir `logger.warning(str(e))` bile
   para sızdıramaz — çünkü string'de para yoktur.
3. **Retry kararı da sinyalin kendisindedir.** Eksik olan şey KULLANICI bilgisiyse
   (`kullanicidan_bilgi_ister=True`) modeli yeniden çağırmak anlamsızdır: aynı eksik
   bilgiyle aynı öneriyi üretir. Eksik olan MODELİN ürettiği payload ise ikinci deneme
   değerlidir.
4. `kullanici_mesaji` metinleri BURADA yaşar — koç akışında elle yazılmaz (H4/#256 dersi:
   kullanıcıya giden metin kod içinde çoğaltılırsa biri sessizce bayatlar).

GUNCELLEMELER
- 9 Agu 2026 BUG #273 fix: modul olusturuldu. `raise ValueError("HESAP_BELIRSIZ")` +
  `if "HESAP_BELIRSIZ" in str(e)` sozlesmesi TIPLI istisnalara tasindi; kullanici mesaji,
  iz gerekcesi ve retry karari sinifin uzerine alindi (BE-006, RESIL-019).
"""
from __future__ import annotations

from typing import Iterable, Optional


class AksiyonReddi(ValueError):
    """`propose_action` öneriyi reddetti — kullanıcıya onaya SUNULMAZ.

    `ValueError` türevidir: mevcut çağıranlar (ve `except ValueError` yazan testler)
    kırılmaz, ama karar artık metinden değil TİPTEN okunur.
    """

    #: Makine sinyali. `str(e)` bununla başlar; teşhis değeri taşımaz, para içermez.
    kod = "AKSIYON_REDDI"
    #: Birden çok ret aynı turda oluştuysa kullanıcıya KÜÇÜK sayı gösterilir.
    #: Sıra bilinçlidir: önce kullanıcıdan bilgi isteyen ret sorulur (o cevaplanmadan
    #: payload'ı düzeltmenin faydası yok).
    oncelik = 90
    #: Kullanıcıya gösterilecek yönlendirme — TEK KAYNAK.
    kullanici_mesaji = (
        "Bu kaydı oluşturamadım — bildirdiğin bilgiyi tam çözemedim. "
        "Tutarı rakamla ve hangi hesap olduğunu yazar mısın?"
    )
    #: `gorunur_neden` verilmediğinde kullanılacak, para içermeyen kısa gerekçe.
    varsayilan_neden = "öneri sözleşmeye uymadı"
    #: True ise eksik olan KULLANICI bilgisidir → modeli yeniden çağırmak anlamsızdır.
    kullanicidan_bilgi_ister = False
    #: Nihai cevap adımının `inference` alanına yazılan etiket (teşhis izlenebilirliği).
    iz_ciktisi = "aksiyon_reddi override"

    def __init__(self, gorunur_neden: Optional[str] = None, *, teshis: str = ""):
        self.gorunur_neden = gorunur_neden or type(self).varsayilan_neden
        #: DEĞER TAŞIYABİLİR (tutar, ham tarih metni...). Loglanmaz, persist edilmez;
        #: yalnız süreç-içi hata ayıklama ve testler içindir.
        self.teshis = str(teshis or "")
        super().__init__(f"{self.kod}: {self.gorunur_neden}")

    @property
    def iz_gozlemi(self) -> str:
        """`reasoning_traces.observation` — kullanıcı bunu "Gözlem" satırında OKUR.
        İç sinyal adı ve tutar içermez."""
        return f"Öneri reddedildi: {self.gorunur_neden}"


class HesapBelirsiz(AksiyonReddi):
    """Gider bildirildi ama hangi hesaptan çıktığı belli değil (BUG #042)."""

    kod = "HESAP_BELIRSIZ"
    oncelik = 10
    kullanici_mesaji = "Hangi hesaptan? 'kartla' veya 'nakitten' eklersen hemen kaydederim."
    varsayilan_neden = "gider bildirildi ama hangi hesaptan çıktığı yazılmadı"
    kullanicidan_bilgi_ister = True
    iz_ciktisi = "account_unclear override"


class TarihBelirsiz(AksiyonReddi):
    """Özet bir tarihten söz ediyor ama payload'da tarih yok (BUG #044).

    Sessiz kalınırsa işlem SUNUCU gününe yazılırdı — BUG #237'nin ta kendisi.
    """

    kod = "TARIH_BELIRSIZ"
    oncelik = 20
    kullanici_mesaji = (
        "Tarih bilgisi tutarsız. Tarihi açıkça belirt ('3 Mayıs'ta' gibi) veya hiç yazma "
        "— tarih yoksa bugün olarak kaydederim."
    )
    varsayilan_neden = "özette tarih geçiyor ama işleme tarih yazılmadı"
    kullanicidan_bilgi_ister = True
    iz_ciktisi = "date_unclear override"


class PayloadGecersiz(AksiyonReddi):
    """Payload sözleşmeye uymuyor — uygulanamayacak öneri DOĞMAZ (BUG #266 / ADR-048)."""

    kod = "PAYLOAD_GECERSIZ"
    oncelik = 30
    varsayilan_neden = "işlem verisi sözleşmeye uymuyor"
    iz_ciktisi = "payload_invalid override"


class OzetPayloadCeliskisi(AksiyonReddi):
    """Kullanıcının OKUDUĞU tutar ile UYGULANACAK tutar farklı (BUG #266)."""

    kod = "OZET_PAYLOAD_CELISKISI"
    oncelik = 30
    varsayilan_neden = "özetteki tutar ile kaydedilecek tutar aynı değil"
    iz_ciktisi = "payload_invalid override"


class BilinmeyenAksiyon(AksiyonReddi):
    """Aksiyon türü `ACTION_TYPES` kümesinde değil (M82 tek kaynak)."""

    kod = "BILINMEYEN_AKSIYON"
    oncelik = 30
    varsayilan_neden = "Bilinmeyen aksiyon türü"
    iz_ciktisi = "payload_invalid override"


def sinyaller() -> tuple[type[AksiyonReddi], ...]:
    """Tanımlı tüm ret sinyalleri (kapı buradan besleniyor — elle liste yok)."""

    def alt(k):
        for a in k.__subclasses__():
            yield a
            yield from alt(a)

    return tuple(sorted(set(alt(AksiyonReddi)), key=lambda k: (k.oncelik, k.kod)))


def en_oncelikli(redler: Iterable[AksiyonReddi]) -> Optional[AksiyonReddi]:
    """Bir turda birden çok ret oluştuysa kullanıcıya gösterilecek olanı seçer.

    Kullanıcıdan bilgi isteyen ret önce sorulur: o cevaplanmadan payload'ı düzeltmek
    kullanıcıyı iki kez yorar.
    """
    liste = [r for r in redler if r is not None]
    if not liste:
        return None
    return min(liste, key=lambda r: (r.oncelik, r.kod))
