"""
Sağlayıcı hata sınıflandırması + geri çekilme politikası — TEK KAYNAK (BUG #269).

Fallback zinciri (`LLM_PROVIDER=fallback`, canlı yapılandırma) bir hatayı gördüğünde ÜÇ
soruya cevap verir: tekrar denenir mi, sağlayıcı atlanır mı, sağlayıcı bu process boyunca
kara listeye alınır mı? Bu üç karar `coach.py` içinde üç ayrı **alt-dizi** taramasıyla
veriliyordu — ve sayısal kodlar da düz metin gibi aranıyordu.

------------------------------------------------------------------------------
ÖLÇÜM (8 Ağu 2026 — 10 gerçekçi sağlayıcı hata metni): 3/10 YANLIŞ
------------------------------------------------------------------------------
| Hata metni | Doğrusu | Ölçülen |
|---|---|---|
| `The input token count (8504) exceeds the maximum...` | kalıcı/çok-büyük | **geçici** |
| `500 Internal error. request_id=req_8429fa1c`          | geçici           | **kota**   |
| `Latency budget exceeded: upstream took 4290 ms`       | kalıcı           | **kota**   |

Üçü de aynı kökten: `"504"` sayısı **8504**'ün içinde, `"429"` ise **4290** ve
**req_8429fa1c**'in içinde geçiyor. Yani sınıflandırma, hatayla ilgisi olmayan bir
sayının rakamlarına bakıyordu.

Zararı sıralı: birinci satır en ağırı. Token sayısı limiti aşan bir istek **kalıcı**
hatadır (aynı prompt her seferinde aynı hatayı verir) — ama "geçici" sayıldığı için
`_call_with_retry` onu 1sn + 2sn bekleyerek **üç kez** deniyor ve `_oversized_providers`
devre kesicisi HİÇ devreye girmiyordu: sağlayıcı her koç isteğinde yeniden deneniyor,
her denemede kullanıcının LLM kotası yazılıyor ve cevap üç saniye geç geliyordu.
İkinci satırda sağlıklı bir sağlayıcı "kotası doldu" denip devre dışı bırakılıyor.

------------------------------------------------------------------------------
SÖZLEŞME
------------------------------------------------------------------------------
1. **Önce YAPI, sonra metin.** Durum kodu istisnanın alanından (`status_code`/`code`) ya
   da metnin BAŞINDAN / `Error code: NNN` kalıbından okunur. Kod biliniyorsa karar odur.
2. **Metin desenleri sayı içermez.** Sayısal kod arayan desen bırakılmadı; kalan desenler
   ifadedir ("resource_exhausted", "overloaded"). Zorunlu olduğu yerde sayı `\\b` ile
   sınırlanır — `\\b429\\b` "4290" ve "req_8429fa1c" ile eşleşmez.
3. **Öncelik sırası KALICI > KOTA > GEÇİCİ.** Bir metin birden çok işaret taşıyabilir
   (Groq'un 413'ü "Limit 8000, Requested 8429" der). Kalıcı olan kazanır: yanlış tarafa
   düşmenin bedeli asimetriktir — kalıcıyı geçici sanmak SONSUZ tekrar üretir, tersi
   yalnız bir denemeyi kaçırır.

GUNCELLEMELER
- 8 Agu 2026 BUG #269 fix: modul olusturuldu (LLM-012 + LLM-011). Siniflandirma
  `coach.py`den tasindi; geri cekilmeye tam-jitter eklendi.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

# ============================================================
# SINIFLAR
# ============================================================

KOTA = "kota"                      # kota/oran limiti → sağlayıcıyı ATLA, tekrar deneme
GECICI = "gecici"                  # 5xx/overload → geri çekilerek TEKRAR DENE
ISTEK_COK_BUYUK = "istek_cok_buyuk"  # kalıcı: aynı prompt hep aynı hatayı verir → KARA LİSTE
KALICI = "kalici"                  # 400/401/kod hatası → tekrar deneme, sessizce yutma

_DURUM_KODU_SINIFI = {
    413: ISTEK_COK_BUYUK,
    429: KOTA,
    402: KOTA,
    500: GECICI, 502: GECICI, 503: GECICI, 504: GECICI, 529: GECICI,
}

# --- metin desenleri: SAYI YOK (kod yolu ayrı) --------------------------------
_COK_BUYUK_DESENI = re.compile(
    r"request too large|reduce your message size|too large for model"
    r"|context length exceeded|maximum context length|string too long"
    # BUG #269 ölçümü: Gemini'nin token-sayısı hatası hiçbir desene uymuyordu ve
    # yalnız içindeki "8504" sayısı yüzünden GEÇİCİ sayılıyordu.
    r"|token count .{0,40}exceeds|exceeds the maximum number of tokens"
    r"|input is too long|prompt is too long",
    re.IGNORECASE,
)
_KOTA_DESENI = re.compile(
    r"resource_exhausted|quota exceeded|exceeded your current quota"
    r"|credit balance is too low|credit balance too low|insufficient_quota"
    r"|rate limit|too many requests|billing (?:hard )?limit",
    re.IGNORECASE,
)
_GECICI_DESENI = re.compile(
    r"\bunavailable\b|overloaded|service unavailable|\btimed? ?out\b|timeout"
    r"|temporarily|try again later|connection (?:reset|aborted|error)",
    re.IGNORECASE,
)

# Metinden durum kodu: yalnız BAŞTA ya da açık etikette — gövdedeki rastgele sayı DEĞİL.
_KOD_DESENI = re.compile(
    r"^\s*(?:HTTP\s*)?(\d{3})\b"                       # "429 RESOURCE_EXHAUSTED"
    r"|error code[:=]\s*(\d{3})\b"                     # "Error code: 413 - {...}"
    r"|[\"']?code[\"']?\s*[:=]\s*(\d{3})\b",           # "'code': 429"
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Siniflandirma:
    """Karar + GEREKÇE + kullanılan durum kodu (log ve trace okunabilir olsun)."""

    sinif: str
    gerekce: str
    durum_kodu: Optional[int] = None

    @property
    def tekrar_denenir(self) -> bool:
        return self.sinif == GECICI

    @property
    def saglayici_atlanir(self) -> bool:
        return self.sinif in (KOTA, ISTEK_COK_BUYUK)

    @property
    def kalici_kara_liste(self) -> bool:
        return self.sinif == ISTEK_COK_BUYUK


def durum_kodu(exc: Exception) -> Optional[int]:
    """İstisnadan durum kodunu YAPIDAN çıkarır; yoksa metnin başından/etiketinden."""
    for alan in ("status_code", "code", "http_status"):
        deger = getattr(exc, alan, None)
        if isinstance(deger, int) and 100 <= deger <= 599:
            return deger
        if isinstance(deger, str) and deger.isdigit() and 100 <= int(deger) <= 599:
            return int(deger)
    m = _KOD_DESENI.search(str(exc))
    if m:
        return int(next(g for g in m.groups() if g))
    return None


def siniflandir(exc: Exception) -> Siniflandirma:
    """Sağlayıcı hatasını sözleşmeye göre sınıflandırır (modül docstring'i)."""
    metin = str(exc)
    kod = durum_kodu(exc)

    # 1) KALICI/ÇOK BÜYÜK — en yüksek öncelik (bkz. sözleşme madde 3)
    if kod == 413 or _COK_BUYUK_DESENI.search(metin):
        return Siniflandirma(ISTEK_COK_BUYUK,
                             "istek tek basina model/tier limitini asiyor", kod)

    # 2) KOTA — yapı varsa yapıdan, yoksa ifadeden
    if kod in (429, 402) or _KOTA_DESENI.search(metin):
        return Siniflandirma(KOTA, "kota/oran limiti", kod)

    # 3) GEÇİCİ
    if (kod is not None and _DURUM_KODU_SINIFI.get(kod) == GECICI) or _GECICI_DESENI.search(metin):
        return Siniflandirma(GECICI, "gecici sunucu/yuk hatasi", kod)

    # 4) Geriye kalan: kalıcı (400/401/kod bug'ı). Sessizce yutulmaz — çağıran loglar.
    return Siniflandirma(KALICI, "kalici hata (tekrar denemek beyhude)", kod)


# ============================================================
# GERİ ÇEKİLME — TAM JITTER (LLM-011)
# ============================================================
#
# Eskiden bekleme `taban * 2**(deneme-1)` idi: aynı anda düşen N istek AYNI anda
# uyanır ve sağlayıcıyı ikinci kez birlikte döver (thundering herd). Sektör karşılığı
# "full jitter": [0, tavan] aralığından örnekle. `rastgele` enjekte edilebilir —
# kapı bekleme davranışını rastgeleliğe bağlı kalmadan ölçebilsin.

BEKLEME_TAVANI = 30.0


def bekleme_suresi(deneme: int, taban: float = 1.0, tavan: float = BEKLEME_TAVANI,
                   rastgele: Callable[[float, float], float] = random.uniform) -> float:
    """Tam-jitter geri çekilme: `[0, min(tavan, taban*2^(deneme-1))]` aralığından."""
    ust = min(tavan, taban * (2 ** max(0, deneme - 1)))
    return rastgele(0.0, ust)


# ============================================================
# GERİYE UYUMLU YÜZEY (coach.py bu adlarla dışa açar)
# ============================================================

def is_quota_exceeded(exc: Exception) -> bool:
    return siniflandir(exc).sinif == KOTA


def is_retryable_error(exc: Exception) -> bool:
    return siniflandir(exc).tekrar_denenir


def is_request_too_large(exc: Exception) -> bool:
    return siniflandir(exc).sinif == ISTEK_COK_BUYUK


#: Kapının kaynaktan gezeceği desen demeti (L27 — liste elle taşınmaz).
METIN_DESENLERI: Tuple[re.Pattern, ...] = (
    _COK_BUYUK_DESENI, _KOTA_DESENI, _GECICI_DESENI,
)
