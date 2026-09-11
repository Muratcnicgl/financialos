"""
Kullanıcıya dönen LLM hata sınıfı (BUG #409 / LLM-038).

Ölçülen (12 Eyl 2026): koç çağrısı düşünce kullanıcıya tek bir düz cümle gidiyor, ham
istisna yalnız loga düşüyordu (doğru — BE-009). Ama istemci ve izleme "neden" sorusuna
cevap alamıyordu: kota mı, ağ mı, sağlayıcı mı?

SINIFLANDIRMA BURADA YAPILMAZ: `app/provider_errors.siniflandir` (BUG #269) tek kaynaktır —
durum kodunu YAPIDAN okur, metin desenlerinde sayı yoktur ("429" 4290'ın içinde geçer;
ilk yazım tam bu hatayı tekrar etmişti, ad-çakışması kapısı yakaladı). Burası yalnız o
sınıfları KULLANICI diline çevirir; küme kapalıdır (istemci switch yazabilsin).
"""
from __future__ import annotations

from app.provider_errors import GECICI, ISTEK_COK_BUYUK, KALICI, KOTA, siniflandir as _saglayici_sinifi

BILINMEYEN = "bilinmeyen"
SINIFLAR = (KOTA, GECICI, ISTEK_COK_BUYUK, KALICI, BILINMEYEN)

MESAJLAR = {
    KOTA: ("Koç şu an kota sınırında — sağlayıcının günlük hakkı dolmuş olabilir. "
           "Panelindeki veriler güncel; koça biraz sonra tekrar yazabilirsin."),
    GECICI: ("Koça ulaşılamadı — sağlayıcı geçici olarak meşgul ya da bağlantı zaman aşımına uğradı. "
             "Panelindeki veriler güncel; birazdan tekrar dene."),
    ISTEK_COK_BUYUK: ("Bu sohbet koçun sağlayıcısı için fazla uzun oldu. "
                      "Yeni bir sohbet başlatıp tekrar dene; panelindeki veriler güncel."),
    KALICI: ("Koçun sağlayıcısı isteği kabul etmedi. "
             "Panelindeki veriler güncel; sorun sürerse operatöre bildir."),
    BILINMEYEN: ("Koç şu an cevap veremedi (sağlayıcılar meşgul olabilir). Birazdan tekrar dene."),
}


def hata_sinifi(hata: BaseException | None) -> str:
    """Kapalı kümeden sınıf; None → bilinmeyen. Ham mesaj dışarı çıkmaz."""
    if hata is None:
        return BILINMEYEN
    try:
        k = _saglayici_sinifi(hata)
    except Exception:  # noqa: BLE001 — sınıflandırıcı düşerse cevap yine gider
        return BILINMEYEN
    # provider_errors'ın KALICI'sı bir GERİ ÇEKİLME kararıdır ("tekrar deneme"); tanınmayan her
    # istisna oraya düşer. Kullanıcıya "sağlayıcı reddetti" demek için elde bir durum kodu
    # olmalı — yoksa dürüst cevap "bilinmeyen"dir.
    if k.sinif == KALICI and k.durum_kodu is None:
        return BILINMEYEN
    return k.sinif


def kullanici_mesaji(sinif: str) -> str:
    return MESAJLAR.get(sinif, MESAJLAR[BILINMEYEN])
