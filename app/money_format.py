"""
PARA BİÇİMLENDİRME — TEK KAYNAK (H4 / ADR-042 3. aşama).

GUNCELLEMELER
- BUG #256 (7 Agu 2026): para biçimlendirme ve para birimi etiketi **dört ayrı yerde**
  bağımsız yazılmıştı — `rules_engine._tl`, `action_executor._fmt`, sayısız f-string'in
  sonundaki sabit `" TL"`, ve `grounding._TL_NUM_RE`'nin içine gömülü `TL` literali.
  Aynı kuralın birden çok yerde kodlanması bu projede bilinen en pahalı hata sınıfı
  (BUG #161 / SBN-001 ailesi, ders **L26**: bir yasağın gücü kaynağı SEÇEN kod sayısı
  kadardır). Bu modül o dört yeri tek kaynağa indirir.

NEDEN "ETİKET" TEK KAYNAK OLMALI — sessiz-yeşil tuzağı
------------------------------------------------------
`app/grounding.py` koçun ürettiği her tutarı cockpit'e karşı doğrular ve tutarları
`(\\d…)\\s*TL` deseniyle bulur. Etiket "TL" olmaktan çıkarsa desen HİÇBİR ŞEY bulamaz,
`checked=0` olur ve fonksiyon `{"ok": True}` döner: doğrulama **vakumsal yeşile** düşer.
Yani para birimi etiketi bir görüntü ayrıntısı değil, bir GÜVENLİK sınırıdır.
Etiket bu modülden gelir; grounding de aynı modülden okur (ders **L21**: sinyali
üretildiği yere değil, ONA GÖRE KARAR VERİLEN sözleşmeye koy).

KAPSAM (bilinçli sınır — ADR-042)
---------------------------------
Bu modül **görüntüleme** katmanıdır. Çoklu para birimiyle HESAP TUTMA (kur çevrimi,
tarihsel kur, karışık-para-birimi net değer) kapsam DIŞIDIR ve ayrı bir ADR gerektirir.
Bu yüzden desteklenen küme bilerek tek elemanlıdır: **TRY**. Bu bir eksiklik değil,
yazılı bir üründür kararıdır — "ayarlanabilir görünüp gösterilememesi" (BUG #251) yerine
kilit görünür, ölçülür ve dürüst hale gelir.

İKİ AYRI HATA REJİMİ (bilinçli tasarım)
---------------------------------------
- **Kod yolu → fail-fast:** `format_para(..., kod="USD")` gibi bir çağrı `DesteklenmeyenParaBirimi`
  fırlatır. Geliştirici hatası sessizce yanlış etiketli para üretmemelidir.
- **Veri yolu → fail-safe:** `kullanici_para_kodu(user)` DB'de kalmış geçersiz bir kod
  görürse (BUG #246 doğrulaması eklenmeden ÖNCE yazılmış satırlar) **çökmez**; uyarı
  loglar ve varsayılana düşer. Kullanıcının kendi verisini açamaz hale gelmesi, yanlış
  etiketten daha ağır bir zarardır (ders **L6**: kapı ürünü kıramaz).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Optional, Union

logger = logging.getLogger(__name__)

Sayi = Union[int, float, Decimal, None]


class DesteklenmeyenParaBirimi(ValueError):
    """Kod yolunda desteklenmeyen para birimi istendi (geliştirici hatası)."""


@dataclass(frozen=True)
class ParaBirimi:
    kod: str            # ISO-4217
    etiket: str         # kullanıcıya yazılan sonek ("1.234,56 TL")
    simge: str          # kompakt gösterim (₺)
    esanlamlilar: tuple[str, ...]  # metinde tanınacak biçimler (grounding + statik kapı)
    ondalik: int = 2


VARSAYILAN_KOD = "TRY"

# TEK KAYNAK. Yeni bir para birimi eklemek, kur çevrimi kararı vermeden YAPILMAZ (ADR-042).
PARA_BIRIMLERI: dict[str, ParaBirimi] = {
    "TRY": ParaBirimi(
        kod="TRY",
        etiket="TL",
        simge="₺",
        esanlamlilar=("TL", "TRY", "₺"),
    ),
}


def desteklenen_kodlar() -> frozenset[str]:
    """API'nin kabul ettiği para birimi kodları (routers/user.py buradan okur)."""
    return frozenset(PARA_BIRIMLERI)


def para_birimi(kod: Optional[str] = None) -> ParaBirimi:
    """Kod → ParaBirimi. Desteklenmeyen kod KOD YOLUNDA fail-fast'tir."""
    k = (kod or VARSAYILAN_KOD).strip().upper()
    if k not in PARA_BIRIMLERI:
        raise DesteklenmeyenParaBirimi(
            f"Desteklenmeyen para birimi: {kod!r}. Desteklenen: {sorted(PARA_BIRIMLERI)}. "
            "Çoklu para birimi görüntüleme kur çevrimi kararına bağlıdır (ADR-042)."
        )
    return PARA_BIRIMLERI[k]


def kullanici_para_kodu(user=None) -> str:
    """
    VERİ YOLU (fail-safe): kullanıcının kayıtlı para birimi kodu.

    DB'de geçersiz/eski bir değer varsa (BUG #246 doğrulaması eklenmeden önce her şey
    kabul ediliyordu) çökmek yerine varsayılana düşer + uyarı loglar.
    """
    ham = getattr(user, "currency", None) if user is not None else None
    if not ham:
        return VARSAYILAN_KOD
    k = str(ham).strip().upper()
    if k not in PARA_BIRIMLERI:
        logger.warning(
            "[money_format] desteklenmeyen para birimi kaydı %r (user=%s) → %s varsayılanı",
            ham, getattr(user, "id", "?"), VARSAYILAN_KOD,
        )
        return VARSAYILAN_KOD
    return k


def para_etiketi(user=None) -> str:
    """Kullanıcıya yazılan para birimi soneki ('TL'). Metin üreten her yer buradan alır."""
    return para_birimi(kullanici_para_kodu(user)).etiket


def taninan_etiketler(kod: Optional[str] = None) -> tuple[str, ...]:
    """
    Metinde para etiketi olarak TANINACAK biçimler.

    `grounding.py` ve statik kapılar bu listeden beslenir — böylece etiket değiştiğinde
    doğrulama katmanı sessizce körleşmez.
    """
    return para_birimi(kod).esanlamlilar


def tr_sayi(deger: Sayi, *, ondalik: int = 2) -> str:
    """
    Türkçe sayı biçimi: 1234.56 → '1.234,56' (nokta binlik, virgül ondalık).

    BUG #122 dersi korunur: '{:,.2f}' çıktısı (nokta ondalık) hem Türkçe arayüzle
    tutarsızdır hem de grounding'de yanlış-pozitif üretir (koç "74.99 TL" yazınca desen
    noktayı binlik sanıp 74 okur).
    """
    if deger is None:
        return "—"
    try:
        sayi = float(deger)
    except (TypeError, ValueError):
        return "—"
    ham = f"{sayi:,.{ondalik}f}"
    return ham.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def format_para(
    deger: Sayi,
    user=None,
    *,
    kod: Optional[str] = None,
    ondalik: Optional[int] = None,
    sonek: bool = True,
) -> str:
    """
    Kullanıcıya gösterilecek para metni: '1.234,56 TL'.

    `sonek=False` yalnız sayıyı verir (etiketi cümlenin başka yerinde geçenler için).
    `kod` verilirse kullanıcı tercihini ezer — KOD YOLUDUR, desteklenmiyorsa fırlatır.
    """
    birim = para_birimi(kod) if kod is not None else para_birimi(kullanici_para_kodu(user))
    metin = tr_sayi(deger, ondalik=birim.ondalik if ondalik is None else ondalik)
    if metin == "—" or not sonek:
        return metin
    return f"{metin} {birim.etiket}"


def para_listesi(degerler: Iterable[Sayi], user=None, *, ayirac: str = " · ") -> str:
    """Birden çok tutarı aynı biçimle yazar (rapor/özet satırları için)."""
    return ayirac.join(format_para(d, user) for d in degerler)
