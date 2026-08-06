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


def user_today_by_id(db, user_id) -> date:
    """
    BUG #237 fix (D17): User NESNESİ taşınmayan yollar için kullanıcının bugünü.

    Yapısal boşluk: `execute_pending_action` handler'ları `handler(db, user_id, payload)` ile
    çağırıyordu — User hiç geçmiyordu, dolayısıyla hiçbir handler `user_today`'e ULAŞAMIYORDU
    (atlanmış bir çağrı değil, tasarım boşluğuydu). Aynı durum motor katmanında da vardı
    (cashflow/simulation/goal_engine/debt_strategy yalnız user_id alır). Bu yardımcı o boşluğu
    imza değiştirmeden kapatır: kullanıcı bulunamazsa sunucu gününe düşer (geriye uyum).
    """
    if db is None or user_id is None:
        return date.today()
    try:
        from app.models import User
        user = db.get(User, user_id)
    except Exception:  # DB erişilemiyorsa tarih üretimi çökmemeli (salt okuma, güvenli varsayılan)
        logger.warning("[user_prefs] kullanıcı okunamadı (user=%s) → sunucu yereli", user_id,
                       exc_info=True)
        return date.today()
    return user_today(user) if user is not None else date.today()


def user_currency(user) -> str:
    """
    Kullanıcının para birimi kodu.

    BUG #256 (H4): gövde `app.money_format.kullanici_para_kodu`'na devredildi. Eskiden burada
    ayrı bir uygulama vardı ve **hiçbir üretim kodundan çağrılmıyordu** (yalnız test) —
    yani "kullanıcı tercihi" fiilen ölü bir alandı. Artık tek kaynak biçimlendiricinin
    kendisidir; buradaki isim geriye uyum içindir.
    """
    from app.money_format import kullanici_para_kodu  # geç import: döngüsel bağımlılık yok
    return kullanici_para_kodu(user)


def user_locale(user) -> str:
    return getattr(user, "locale", None) or VARSAYILAN_LOCALE
