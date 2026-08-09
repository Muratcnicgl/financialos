"""
LLM cevabından JSON ÇIKARMA — TEK KAYNAK (BUG #270).

Bir dil modelinden JSON istemek, "yalnız JSON döndür" demekle bitmez: zayıf modeller
(flash-lite / gpt-oss sınıfı) cevabı düzenli olarak bir nezaket cümlesiyle sarar. Bu
kod tabanında aynı soruya İKİ ayrı cevap vardı:

  · `coach_insights._parse_k2_response` — fence regex + ilk `{` / son `}` yedeği (dayanıklı)
  · `premortem._parse_and_validate`     — yalnız METNİN TAMAMI fence ise soyar (kırılgan)

------------------------------------------------------------------------------
ÖLÇÜM (8 Ağu 2026 — 9 gerçekçi sarmalama biçimi, premortem yolunda): **5'i düşüyor**
------------------------------------------------------------------------------
| Sarmalama | Ayrıştı mı |
|---|---|
| saf JSON · ```json fence · fence (dil etiketsiz) · kapanışı eksik fence | ✅ |
| `Elbette, işte analiz:` + JSON | ❌ |
| `İşte istediğiniz JSON:` + fence | ❌ |
| fence + `Umarım yardımcı olur.` | ❌ |
| `**Premortem**` + fence + kapanış cümlesi | ❌ |
| JSON + `Not: tutarlar tahminidir.` | ❌ |

Beşinin ortak yanı: JSON'un KENDİSİ kusursuz, kusur ZARFTA. Her düşüş premortem'in iki
deneme hakkından birini yakar; model aynı alışkanlığı tekrarlarsa (zayıf modellerde olağan)
kullanıcı premortem'i **hiç göremez**.

------------------------------------------------------------------------------
SÖZLEŞME — ZARFA TOLERANSLI, İÇERİĞE KATI
------------------------------------------------------------------------------
Bu modül yalnız **zarfı** açar: fence'ler, öndeki/arkadaki düz metin, başlıklar. İçeriği
DOĞRULAMAZ — doğrulama çağıranın Pydantic şemasında kalır. Ayrım bilinçlidir: zarfı
affetmek kullanıcıya bir özellik kazandırır, içeriği affetmek ona yanlış veri gösterir
(ADR-050'nin "içerik yük, gerisi etiket" ayrımının bu yoldaki karşılığı).

`{` taraması **dizge-duyarlıdır**: metin içindeki süslü parantez (`"a{b"`) dengeyi bozmaz —
`coach_insights`'ın "ilk `{` … son `}`" yedeğinin sessiz zayıflığı buydu.

GUNCELLEMELER
- 8 Agu 2026 BUG #270 fix: modul olusturuldu; `premortem` ve `coach_insights` ayni
  cikarmayi kullanir (iki ayri cevap tek kaynaga indi).
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterator, List, Optional

_FENCE = re.compile(r"```[a-zA-Z0-9_+-]*\s*\n?(.*?)(?:```|\Z)", re.DOTALL)


class JsonZarfiCozulemedi(ValueError):
    """Metinde ayrıştırılabilir bir JSON nesnesi yok. Çağıran bunu retry'a çevirir."""


def _dengeli_bloklar(metin: str) -> Iterator[str]:
    """Metindeki üst-seviye dengeli `{...}` bloklarını sırayla verir (dizge-duyarlı)."""
    derinlik = 0
    baslangic = -1
    dizge = False
    kacis = False
    for i, ch in enumerate(metin):
        if dizge:
            if kacis:
                kacis = False
            elif ch == "\\":
                kacis = True
            elif ch == '"':
                dizge = False
            continue
        if ch == '"':
            dizge = True
        elif ch == "{":
            if derinlik == 0:
                baslangic = i
            derinlik += 1
        elif ch == "}":
            if derinlik:
                derinlik -= 1
                if derinlik == 0 and baslangic >= 0:
                    yield metin[baslangic:i + 1]
                    baslangic = -1


def _adaylar(metin: str) -> List[str]:
    """Denenecek metin adayları: tam metin → fence içerikleri → dengeli bloklar."""
    adaylar: List[str] = []
    ham = (metin or "").strip()
    if ham:
        adaylar.append(ham)
    for parca in _FENCE.findall(ham):
        parca = parca.strip()
        if parca:
            adaylar.append(parca)
    for blok in _dengeli_bloklar(ham):
        adaylar.append(blok)
    return adaylar


def cikar(metin: Optional[str]) -> Any:
    """LLM cevabından JSON değerini çıkarır (zarf toleranslı, içerik doğrulanmaz).

    İlk AYRIŞAN ve BOŞ OLMAYAN aday döner: metin içindeki `{}` gibi anlamsız bir blok
    gerçek gövdeyi gölgeleyemesin.
    """
    bos_aday = None
    for aday in _adaylar(metin):
        try:
            deger = json.loads(aday)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(deger, (dict, list)) and not deger and bos_aday is None:
            bos_aday = deger
            continue
        return deger
    if bos_aday is not None:
        return bos_aday
    raise JsonZarfiCozulemedi(
        "cevapta ayristirilabilir JSON yok"
        + (f" (ilk 80 karakter: {str(metin)[:80]!r})" if metin else " (bos cevap)")
    )
