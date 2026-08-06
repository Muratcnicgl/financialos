"""
Grounding Check — LLM çıktı doğrulama (Kalite serüveni LLM-003).

DEVRİMSEL ADIM / VİZYON: Kök vizyonun "kusursuzluk, sıfır hata, VARSAYIM YASAK" mandatını
kod seviyesinde enforce eder. "Rules Engine karar verir, LLM açıklar" ilkesinin doğrulama
katmanı: koçun cevabında geçen HER para tutarı, deterministik cockpit dict'indeki bir değere
izlenebilir olmalı. İzlenemeyen tutar = potansiyel "silent hallucination" (2026 agentic-finans
başarısızlık modu) → işaretlenir, güven düşürülür.

Bu bir UYARI sinyalidir, sert blok değil (koç meşru türev sayılar üretebilir); amaç şeffaflık.
Saf/deterministik — LLM/ağ gerektirmez, birim-test edilebilir.

GUNCELLEMELER
- BUG #256 fix (7 Agu 2026, H4): iki sessiz körlük kapatıldı.
  (1) **Etiket koda gömülüydü.** Desen `…\\s*TL` sabitiyle yazılmıştı; para birimi etiketi
      değişirse desen hiçbir tutar bulamaz, `checked=0` olur ve fonksiyon `{"ok": True}`
      döner — yani doğrulama **vakumsal yeşile** düşer. Etiket artık tek kaynaktan gelir
      (`app/money_format.taninan_etiketler`) ve o kaynakla birlikte değişir (ders L21).
  (2) **"Para gibi görünen ama etiketsiz" tutarlar hiç denetlenmiyordu.** Koç
      `"net değerin 31.343"` yazdığında (etiket unutulmuş ya da başka birimde) eski kod
      bunu görmezden geliyordu; halüsinasyon etiketi düşürerek denetimden kaçabiliyordu.
      Artık bu sayılar `etiketsiz` olarak raporlanır ve sonucu KIRMIZI yapar (ders L28:
      "hiç eşleşme bulamadım" başarı değildir).

YANLIŞ-POZİTİF SINIRI (bilinçli): `etiketsiz` yalnız **para biçiminde yazılmış** sayıları
sayar — binlik ayıracı ya da iki haneli ondalık virgülü olan ve eşiğin üstünde olanlar.
Yüzdeler, tarihler, yıl/gün/ay/adet gibi birim taşıyan sayılar ve ayraçsız düz tam sayılar
(2026, 30) kapsam dışıdır; aksi halde kapı gürültü üretir ve kimse ciddiye almaz (L22).
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Any, Dict, List, Optional

from app.money_format import taninan_etiketler

# Para biçiminde yazılmış sayı: "42.100,50" / "1.234" / "268,75"
# (binlik ayıracı ya da ondalık virgül taşıyanlar; ayraçsız düz sayı da yakalanır ama
#  etiketsiz taramada ayrıca "biçimli mi" kontrolünden geçer.)
_SAYI = r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?"

# Etiketsiz taramada yok sayılacak birimler — bunlar para değildir.
_BIRIM_SONRASI = (
    r"gün|gun|ay|yıl|yil|hafta|saat|dakika|adet|kez|lot|kişi|kisi|puan|"
    r"%|yaş|yas|derece|km|kg|tl/gün|tl/gun"
)


@lru_cache(maxsize=8)
def _etiketli_desen(kod: Optional[str]) -> re.Pattern[str]:
    """'<sayı> <etiket>' deseni — etiketler para-birimi tek kaynağından gelir."""
    etiketler = "|".join(re.escape(e) for e in taninan_etiketler(kod))
    # `\b` KULLANMA: etiketlerden biri sembol (₺) ve sembol harf-olmayan karakterdir —
    # `\b` orada eşleşmez, yani "4.276,14 ₺" desenin dışında kalırdı (sessiz körlük).
    return re.compile(rf"(?P<num>{_SAYI})\s*(?:{etiketler})(?!\w)", re.IGNORECASE)


@lru_cache(maxsize=8)
def _etiketsiz_desen(kod: Optional[str]) -> re.Pattern[str]:
    """
    Para BİÇİMİNDE yazılmış ama para etiketi taşımayan sayı.

    Zorunlu: binlik ayıracı (1.234) ya da iki haneli ondalık virgül (12,50).
    Ardında para etiketi ya da bir birim kelimesi gelmemeli, önünde % olmamalı.
    """
    etiketler = "|".join(re.escape(e) for e in taninan_etiketler(kod))
    # DİKKAT (kendi tuzağım, 7 Agu): lookahead'i `\s*(?!ETIKET)` diye yazmak İŞE YARAMAZ —
    # `\s*` geri izleyip boşluğu bırakır ve lookahead " TL"nin boşluğunda başarılı olur,
    # yani etiketli tutar "etiketsiz" sayılır. Boşluk lookahead'in İÇİNDE olmalı.
    return re.compile(
        r"(?<![%\d,.])"                                       # önünde % ya da sayı parçası olmasın
        r"(?P<num>\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+,\d{2})"    # para BİÇİMİ zorunlu
        r"(?![\d.,])"                                         # sayının devamı gelmesin
        rf"(?!\s*(?:{etiketler})(?!\w))"                      # para etiketi gelmiyorsa
        rf"(?!\s*(?:{_BIRIM_SONRASI})\b)"                     # ve birim kelimesi de gelmiyorsa
        r"(?!\s*%)",
        re.IGNORECASE,
    )


def _to_float_tr(token: str) -> float:
    """TR formatlı sayı ('31.342,86') -> float. Nokta binlik, virgül ondalık."""
    return float(token.replace(".", "").replace(",", "."))


def _collect_numeric(obj: Any, out: List[float]) -> None:
    """cockpit dict'indeki tüm sayısal yaprakları topla (recursive)."""
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect_numeric(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _collect_numeric(v, out)


def check_grounding(
    reply: str,
    cockpit: Dict[str, Any],
    user_message: str = "",
    *,
    min_magnitude: float = 100.0,
    rel_tol: float = 0.02,
    abs_tol: float = 1.0,
    para_kodu: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Koç cevabındaki para tutarlarını cockpit değerleriyle karşılaştır.

    Dönüş: `{"ok", "checked", "unverified", "etiketsiz"}`.
      * `unverified` — etiketli ama cockpit'te karşılığı olmayan tutarlar (halüsinasyon şüphesi).
      * `etiketsiz`  — para biçiminde yazılmış ama etiketi olmayan tutarlar (denetimden kaçış).
      * `ok`         — ikisi de boşsa True.

    Ders LLM-003a: Kullanıcının az önce söylediği tutar cockpit'e henüz girmediği
    için (pending action) grounding ihlali vermemeli. user_message içindeki
    tutarlar da 'geçici izinli' sayılır.
    """
    etiketli = _etiketli_desen(para_kodu)
    etiketsiz_re = _etiketsiz_desen(para_kodu)

    allowed_raw: List[float] = []
    _collect_numeric(cockpit, allowed_raw)

    # Kullanıcı mesajındaki tutarları da izinli listesine ekle
    if user_message:
        for m in etiketli.finditer(user_message):
            try:
                allowed_raw.append(_to_float_tr(m.group("num")))
            except ValueError:
                continue

    allowed = {round(abs(v), 2) for v in allowed_raw}

    unverified: List[float] = []
    checked = 0
    etiketli_araliklar: List[tuple[int, int]] = []
    for m in etiketli.finditer(reply):
        etiketli_araliklar.append(m.span("num"))
        try:
            val = abs(_to_float_tr(m.group("num")))
        except ValueError:
            continue
        if val < min_magnitude:
            continue
        checked += 1
        matched = any(abs(val - a) <= max(abs_tol, rel_tol * a) for a in allowed)
        if not matched:
            unverified.append(round(val, 2))

    # BUG #256: etiketi düşürülmüş tutarlar artık görünür. Etiketli eşleşmelerin içindeki
    # sayılar tekrar sayılmaz (aynı tutar iki kez raporlanmasın).
    etiketsiz: List[float] = []
    for m in etiketsiz_re.finditer(reply):
        bas, son = m.span("num")
        if any(b <= bas and son <= s for b, s in etiketli_araliklar):
            continue
        try:
            val = abs(_to_float_tr(m.group("num")))
        except ValueError:
            continue
        if val < min_magnitude:
            continue
        etiketsiz.append(round(val, 2))

    return {
        "ok": not unverified and not etiketsiz,
        "checked": checked,
        "unverified": unverified,
        "etiketsiz": etiketsiz,
    }
