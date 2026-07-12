"""
Fiyat sağlayıcı router + kayıt (ADR-029).

R3 GERÇEĞİ (M4): funds için tek ÇALIŞAN sağlayıcı = **pytefas** (canlı TLY=7277.90 doğrulandı).
borsapy TEFAS API 404 veriyor, tefas-crawler sonuçsuz, yfinance BIST hatalı → charter'ın
"borsapy birincil" premisi R3 ile düzeltildi. Fund: pytefas (TEFAS). Stock (gelecek BIST):
İş Yatırım JSON endpoint. Sağlayıcı ekleme = ADR-029 güncelle.

Bu modül `app/models.py` PriceHistory docstring'inin atıf yaptığı yerdir.
"""
from __future__ import annotations

import logging
import time
from datetime import date
from decimal import Decimal
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.models import Account, AccountType, PriceHistory, PriceSource

logger = logging.getLogger(__name__)

# Basit TTL cache: (fund_code, date_iso) -> (price, source, ts). Aynı gün aynı fon
# (Murat'ın 2 TLY hesabı gibi) tek çağrıda çekilir; TEFAS rate-limit'i korunur.
_CACHE: dict[Tuple[str, str], Tuple[Decimal, str, float]] = {}
_TTL = 4 * 3600  # 4 saat


def _cache_get(key: Tuple[str, str]) -> Optional[Tuple[Decimal, str]]:
    hit = _CACHE.get(key)
    if hit and (time.time() - hit[2]) < _TTL:
        return hit[0], hit[1]
    return None


def get_fund_price(fund_code: str, target_date: Optional[date] = None) -> Optional[Tuple[Decimal, str]]:
    """Fon fiyatı (pytefas/TEFAS). (Decimal, 'tefas') veya None. Cache'li."""
    if not fund_code:
        return None
    key = (fund_code, (target_date or date.today()).isoformat())
    cached = _cache_get(key)
    if cached:
        return cached
    from app.fund_tracker import try_auto_fetch_fund_price  # çalışan pytefas mantığı (reuse)
    price = try_auto_fetch_fund_price(fund_code)
    if price is not None:
        _CACHE[key] = (price, PriceSource.TEFAS.value, time.time())
        return price, PriceSource.TEFAS.value
    return None


def get_stock_price(ticker: str, target_date: Optional[date] = None) -> Optional[Tuple[Decimal, str]]:
    """BIST hisse fiyatı (İş Yatırım). Gelecek multi-asset; şu an best-effort."""
    if not ticker:
        return None
    from app.fund_tracker import try_auto_fetch_stock_price
    res = try_auto_fetch_stock_price(ticker)
    if res and res.get("price") is not None:
        return Decimal(str(res["price"])).quantize(Decimal("0.0001")), PriceSource.ISYATIRIM.value
    return None


def fetch_for_account(account: Account) -> Optional[Tuple[Decimal, str]]:
    """Hesaba göre fiyat çek. fund_code → fon (TEFAS). (Stock/fx tipleri Wave-3 multi-asset.)"""
    if account.account_type != AccountType.investment or not account.fund_code:
        return None
    # Şu an tüm yatırımlar fon (fund_code). Gelecekte ticker ayrımı ADR-031 multi-asset ile.
    return get_fund_price(account.fund_code)


def record_investment_price(db: Session, account: Account, price: Decimal, source: str) -> bool:
    """
    Fiyatı KALICI kaydet: PriceHistory'ye satır (ADR-012 kompozit PK, idempotent) +
    Account.current_price/last_price_update denormalize cache güncelle. True=yeni kayıt.
    """
    from datetime import datetime
    today = date.today()
    exists = db.query(PriceHistory).filter(
        PriceHistory.fund_code == account.fund_code,
        PriceHistory.price_date == today,
        PriceHistory.source == source,
    ).first()
    is_new = exists is None
    if is_new:
        db.add(PriceHistory(fund_code=account.fund_code, price_date=today,
                            source=source, close_price=price))
    else:
        exists.close_price = price  # aynı gün+kaynak güncellenirse üzerine yaz
    account.current_price = price
    account.last_price_update = datetime.utcnow()
    db.commit()
    return is_new
