"""Fiyat sağlayıcı katmanı (ADR-012 + ADR-029).

PriceHistory tek doğruluk kaynağı; Account.current_price denormalize cache.
Okuma önceliği: manual > tefas > yfinance > isyatirim (PriceSource).
"""
from app.price_providers.router import (  # noqa: F401
    get_fund_price, get_stock_price, fetch_for_account, record_investment_price,
)
