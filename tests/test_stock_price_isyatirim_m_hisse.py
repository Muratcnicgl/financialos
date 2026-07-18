"""
M-hisse (Wave-7, Blok C2) — BIST hisse otomasyonu (İş Yatırım fallback) kalıcı testleri.

R3 tanısı (18 Tem): hisse otomasyonu YAZILMIŞ AMA HİÇ İŞLETİLMEMİŞ — try_auto_fetch_stock_price bir STUB'dı
(None döndürüyordu). M-hisse İş Yatırım HisseTekil endpoint'ini gerçek implementasyona aldı (CANLI doğrulandı:
THYAO=329.50). Bu test ağ-BAĞIMSIZ (mock) → CI'da parse + fallback + uçtan uca akışı kilitler.

Canlı KULLANIM-GATE (bir kez, 18 Tem): gerçek THYAO hesabı → fetch_for_account → 329.50 İş Yatırım →
PriceHistory isyatirim satırı → cockpit yatirim_deger=3295. (milestone-log M-hisse)
"""
from __future__ import annotations

import io
import json
from decimal import Decimal
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User, Account, AccountType, PriceHistory
from app import fund_tracker
from app.price_providers import fetch_for_account, record_investment_price
from app.price_providers import router as pp_router
from app.rules_engine import generate_cockpit

# İş Yatırım HisseTekil örnek yanıtı (gerçek şema)
_ISYATIRIM_JSON = {
    "ok": True, "errorCode": None,
    "value": [
        {"HGDG_HS_KODU": "THYAO", "HGDG_TARIH": "16-07-2026", "HGDG_KAPANIS": 325.0000},
        {"HGDG_HS_KODU": "THYAO", "HGDG_TARIH": "17-07-2026", "HGDG_KAPANIS": 329.5000},
    ],
}


def _mock_urlopen(*_a, **_k):
    return io.BytesIO(json.dumps(_ISYATIRIM_JSON).encode("utf-8"))


def test_try_auto_fetch_stock_price_isyatirim_parse(monkeypatch):
    """İş Yatırım JSON'ından en son HGDG_KAPANIS parse edilir (stub DEĞİL, gerçek)."""
    monkeypatch.setattr("urllib.request.urlopen", _mock_urlopen)
    res = fund_tracker.try_auto_fetch_stock_price("THYAO")
    assert res is not None, "İş Yatırım fetch None döndü — stub'a geri mi döndü?"
    assert res["price"] == 329.5 and res["source"] == "isyatirim" and res["date"] == "17-07-2026"


def test_get_stock_price_yfinance_yok_isyatirim_fallback(monkeypatch):
    """yfinance None → İş Yatırım fallback devreye girer (price, 'isyatirim')."""
    monkeypatch.setattr("app.price_providers.yfinance_client.get_yfinance_price", lambda s: None)
    monkeypatch.setattr("urllib.request.urlopen", _mock_urlopen)
    res = pp_router.get_stock_price("THYAO.IS")
    assert res == (Decimal("329.5000"), "isyatirim")


def test_bist_hesabi_uctan_uca(monkeypatch):
    """Gerçek şema (mock) ile: stock hesabı → fetch → PriceHistory isyatirim + cockpit yatirim_deger."""
    monkeypatch.setattr("app.price_providers.yfinance_client.get_yfinance_price", lambda s: None)
    monkeypatch.setattr("urllib.request.urlopen", _mock_urlopen)
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng); db = sessionmaker(bind=eng)()
    try:
        db.add(User(id=1, name="m", email="m@x.com")); db.commit()
        acc = Account(user_id=1, name="THYAO", account_type=AccountType.investment,
                      asset_type="stock", fund_code="THYAO", lot_count=10,
                      current_price=Decimal("0"), is_emanet=False)
        db.add(acc); db.commit()
        res = fetch_for_account(acc)
        assert res and res[1] == "isyatirim"
        record_investment_price(db, acc, res[0], res[1]); db.refresh(acc)
        assert acc.current_price == Decimal("329.5000")
        assert db.query(PriceHistory).filter(PriceHistory.source == "isyatirim").count() == 1
        c = generate_cockpit(1, date.today(), db)
        assert c["yatirim_deger"] == 3295.0  # 10 * 329.50
    finally:
        db.close(); eng.dispose()
