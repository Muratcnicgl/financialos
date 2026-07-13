"""
M12 (ADR-031) — Multi-asset provider dispatch + client testleri.

Canlı fiyat kaynakları env-bağımlı (yfinance Yahoo blok, EVDS API key) → mock ile
dispatch mantığı + graceful-None davranışı test edilir. Kripto Wave-4 (kapsam dışı).
"""
from __future__ import annotations

from decimal import Decimal

import app.price_providers.router as pr
from app.models import Account, AccountType


def _acc(asset_type, symbol="X", atype=AccountType.investment):
    a = Account(name="t", account_type=atype, fund_code=symbol, balance=0)
    a.asset_type = asset_type
    return a


# --- Dispatch: asset_type doğru provider'a yönlendirir ---

def test_dispatch_fund(monkeypatch):
    called = {}
    def _fund(s, target_date=None):
        called["fund"] = s
        return (Decimal("1"), "tefas")
    monkeypatch.setattr(pr, "get_fund_price", _fund)
    r = pr.fetch_for_account(_acc("fund", "TLY"))
    assert called["fund"] == "TLY" and r == (Decimal("1"), "tefas")


def test_dispatch_asset_type_none_fund_fallback(monkeypatch):
    monkeypatch.setattr(pr, "get_fund_price", lambda s, target_date=None: (Decimal("2"), "tefas"))
    r = pr.fetch_for_account(_acc(None, "TLY"))
    assert r == (Decimal("2"), "tefas")


def test_dispatch_stock(monkeypatch):
    monkeypatch.setattr(pr, "get_stock_price", lambda s, target_date=None: (Decimal("100"), "yfinance"))
    r = pr.fetch_for_account(_acc("stock", "THYAO.IS"))
    assert r == (Decimal("100"), "yfinance")


def test_dispatch_fx(monkeypatch):
    monkeypatch.setattr(pr, "get_fx_or_gold_price", lambda s: (Decimal("34.5"), "evds"))
    r = pr.fetch_for_account(_acc("fx", "USDTRY"))
    assert r == (Decimal("34.5"), "evds")


def test_dispatch_crypto_desteklenmez(monkeypatch):
    # Wave-4 — None döner (sessiz, log)
    assert pr.fetch_for_account(_acc("crypto", "BTC")) is None


def test_dispatch_non_investment_none():
    assert pr.fetch_for_account(_acc("stock", "X", atype=AccountType.cash)) is None


# --- get_stock_price: yfinance başarısızsa İş Yatırım fallback ---

def test_stock_yfinance_basarili(monkeypatch):
    monkeypatch.setattr("app.price_providers.yfinance_client.get_yfinance_price",
                        lambda s: Decimal("250.5"))
    r = pr.get_stock_price("AAPL")
    assert r == (Decimal("250.5"), "yfinance")


def test_stock_yfinance_none_isyatirim_fallback(monkeypatch):
    monkeypatch.setattr("app.price_providers.yfinance_client.get_yfinance_price", lambda s: None)
    monkeypatch.setattr("app.fund_tracker.try_auto_fetch_stock_price",
                        lambda t: {"price": 42.0})
    r = pr.get_stock_price("THYAO.IS")
    assert r[1] == "isyatirim" and r[0] == Decimal("42.0000")


# --- Client'lar: graceful None ---

def test_yfinance_client_bos_none(monkeypatch):
    from app.price_providers import yfinance_client as yc
    class _T:
        def history(self, period="5d"):
            import pandas as pd
            return pd.DataFrame()  # boş
    monkeypatch.setattr("yfinance.Ticker", lambda s: _T())
    assert yc.get_yfinance_price("AAPL") is None


def test_evds_client_keysiz_none(monkeypatch):
    from app.price_providers import evds_client as ec
    monkeypatch.delenv("EVDS_API_KEY", raising=False)
    assert ec.get_evds_price("USDTRY") is None


def test_evds_bilinmeyen_sembol_none(monkeypatch):
    from app.price_providers import evds_client as ec
    monkeypatch.setenv("EVDS_API_KEY", "dummy")
    assert ec.get_evds_price("BILINMEYEN") is None
