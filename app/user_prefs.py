"""
Kullanıcı tercihleri (H4 / BUG #197) — "bugün" kullanıcının saat diliminde.

Sorun: uygulama her yerde `date.today()` kullanıyordu; bu SUNUCUNUN yerel tarihidir.
Sunucu TZ'si doğru ayarlansa bile (BUG #169) farklı saat diliminde yaşayan bir kullanıcı
için "bugün" yanlış güne düşer: gece yarısı civarında girilen işlem bir önceki/sonraki güne
yazılır, günlük limit yanlış hesaplanır, ay sınırında düzenli gelir/gider tetiklemesi kayar.
Tek-kullanıcı (TR) kurulumda görünmezdi; kapalı betada ilk yurt dışı kullanıcıda ortaya çıkar.

Karar: tarih üreten her yol kullanıcıya bağlı olmalı. `User.timezone` boşsa sunucu
varsayılanına düşülür (geriye uyum) — davranış hiçbir mevcut kurulumda değişmez.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)

VARSAYILAN_PARA_BIRIMI = "TRY"
VARSAYILAN_LOCALE = "tr-TR"


def user_zoneinfo(user) -> Optional[ZoneInfo]:
    """Kullanıcının saat dilimi nesnesi; tanımsız/geçersizse None (sunucu yereli kullanılır)."""
    ad = getattr(user, "timezone", None)
    if not ad:
        return None
    try:
        return ZoneInfo(ad)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        # Geçersiz TZ sessizce YANLIŞ tarih üretmemeli — logla, güvenli varsayılana dön.
        logger.warning("[user_prefs] geçersiz saat dilimi %r (user=%s) → sunucu yereli",
                       ad, getattr(user, "id", "?"))
        return None


def user_today(user) -> date:
    """Kullanıcının saat dilimine göre BUGÜN. TZ yoksa sunucu yerel tarihi (geriye uyum)."""
    tz = user_zoneinfo(user)
    return datetime.now(tz).date() if tz else date.today()


def user_currency(user) -> str:
    return (getattr(user, "currency", None) or VARSAYILAN_PARA_BIRIMI).upper()


def user_locale(user) -> str:
    return getattr(user, "locale", None) or VARSAYILAN_LOCALE
