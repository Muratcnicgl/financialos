"""
Finansal Pydantic alan tipleri — SEC-032: sayısal/finansal aralık doğrulaması.

SORUN: Varsayılan Pydantic `float` alanı inf/NaN'ı ve 1e308 gibi taşma değerlerini KABUL
eder (JSON parser'ları Infinity/NaN geçirebilir; 1e308 zaten geçerli JSON). Bu değerler
girişten `rules_engine` matematiğine sızıp `round(inf)` / taşma çökmelerine yol açar
(sağlık skoru round(inf) bug'ı bu sınıftandı; savunma yalnız hesaba değil GİRİŞE de konmalı).
Bir başparmak kayması (1000 yerine 1e12) veya bozuk içe-aktarım da bu tiplerle reddedilir.

Üst sınır bilinçli GENİŞ: 1e12 = 1 trilyon TL — meşru kişisel finans değerinin çok üstünde
ama çöp/taşma değerini keser. `allow_inf_nan=False` inf/NaN'ı reddeder.

- FinansTutar / FinansOptTutar : POZİTİF tutar (gelir, gider, borç, işlem tutarı).
- FinansBakiye / FinansOptBakiye: bakiye (kredi/kart NEGATİF olabilir → alt sınır -1e12).
- FinansOptOran                : oran/yüzde/lot gibi ≥0 opsiyonel alanlar.
"""
from typing import Annotated, Optional

from pydantic import Field

_FIN_MAX: float = 1e12  # 1 trilyon TL — meşru üst sınırın çok üstünde, taşmayı keser

FinansTutar = Annotated[float, Field(gt=0, le=_FIN_MAX, allow_inf_nan=False)]
FinansOptTutar = Annotated[Optional[float], Field(gt=0, le=_FIN_MAX, allow_inf_nan=False)]
FinansBakiye = Annotated[float, Field(ge=-_FIN_MAX, le=_FIN_MAX, allow_inf_nan=False)]
FinansOptBakiye = Annotated[Optional[float], Field(ge=-_FIN_MAX, le=_FIN_MAX, allow_inf_nan=False)]
FinansOptOran = Annotated[Optional[float], Field(ge=0, le=_FIN_MAX, allow_inf_nan=False)]
