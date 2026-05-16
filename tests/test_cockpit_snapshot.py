"""
Tests for app/cockpit_snapshot.py — build_cockpit_snapshot + compute_snapshot_hash.
generate_cockpit ve generate_forecast monkeypatch ile mock'lanir; DB'ye erisim yok.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from unittest.mock import MagicMock

from app.cockpit_snapshot import build_cockpit_snapshot, compute_snapshot_hash


# ============================================================
# FIXTURE
# ============================================================

def _mock_db():
    return MagicMock()


def _fake_cockpit():
    return {
        "net_deger": 50000.0,
        "nakit_kasa": 15000.0,
        "kart_borcu": 5000.0,
        "kredi_borcu": 0.0,
        "yatirim_deger": 40000.0,
        "daily_limit": 250.0,
    }


def _fake_forecast_fn(summary_30=None, summary_60=None):
    """horizon_days'e gore farkli summary donduren fake forecast."""
    s30 = summary_30 or {
        "net_flow": 7000.0,
        "lowest_balance": 12000.0,
        "lowest_date": date(2026, 6, 1),
        "crunch_count": 0,
    }
    s60 = summary_60 or {"net_flow": 14000.0}

    def _fn(db, user_id, horizon_days):
        if horizon_days == 30:
            return {"summary": s30}
        return {"summary": s60}

    return _fn


# ============================================================
# TEST 1 — snapshot yapisi ve degerleri
# ============================================================

def test_snapshot_yapisi_tam(monkeypatch):
    """Tum TypedDict alanlari mevcut, degerler mock'lardan dogru geliyor."""
    monkeypatch.setattr("app.cockpit_snapshot.generate_cockpit",
                        lambda *a, **kw: _fake_cockpit())
    monkeypatch.setattr("app.cockpit_snapshot.generate_forecast",
                        _fake_forecast_fn())

    snapshot = build_cockpit_snapshot(_mock_db(), user_id=1)

    # Tum alanlar mevcut
    expected_keys = {
        "snapshot_at", "net_worth_tl", "cash_tl", "card_debt_tl", "loan_debt_tl",
        "investment_tl", "cashflow_30d_tl", "cashflow_60d_tl", "lowest_balance_tl",
        "lowest_balance_date", "crunch_count", "daily_limit_tl",
    }
    assert expected_keys == set(snapshot.keys())

    # Degerler
    assert snapshot["net_worth_tl"] == 50000.0
    assert snapshot["cash_tl"] == 15000.0
    assert snapshot["card_debt_tl"] == 5000.0
    assert snapshot["loan_debt_tl"] == 0.0
    assert snapshot["investment_tl"] == 40000.0
    assert snapshot["cashflow_30d_tl"] == 7000.0
    assert snapshot["cashflow_60d_tl"] == 14000.0
    assert snapshot["lowest_balance_tl"] == 12000.0
    assert snapshot["lowest_balance_date"] == "2026-06-01"
    assert snapshot["crunch_count"] == 0
    assert snapshot["daily_limit_tl"] == 250.0

    # snapshot_at ISO 8601 string
    assert isinstance(snapshot["snapshot_at"], str)
    # datetime.fromisoformat parse edebilmeli
    datetime.fromisoformat(snapshot["snapshot_at"])


# ============================================================
# TEST 2 — hash deterministik
# ============================================================

def test_hash_deterministik(monkeypatch):
    """Ayni snapshot'tan iki kez hash uretilince sonuclar esit, 16-hex-char."""
    monkeypatch.setattr("app.cockpit_snapshot.generate_cockpit",
                        lambda *a, **kw: _fake_cockpit())
    monkeypatch.setattr("app.cockpit_snapshot.generate_forecast",
                        _fake_forecast_fn())

    snapshot = build_cockpit_snapshot(_mock_db(), user_id=1)

    h1 = compute_snapshot_hash(snapshot)
    h2 = compute_snapshot_hash(snapshot)

    assert h1 == h2
    assert len(h1) == 16
    assert re.fullmatch(r"[0-9a-f]+", h1), f"Hash hex degil: {h1}"


# ============================================================
# TEST 3 — snapshot_at hash'i etkilemez
# ============================================================

def test_hash_snapshot_at_etkilemez(monkeypatch):
    """snapshot_at farkli olsa bile ayni mali state ayni hash'i uretmeli."""
    monkeypatch.setattr("app.cockpit_snapshot.generate_cockpit",
                        lambda *a, **kw: _fake_cockpit())
    monkeypatch.setattr("app.cockpit_snapshot.generate_forecast",
                        _fake_forecast_fn())

    s1 = build_cockpit_snapshot(_mock_db(), user_id=1)
    s2 = build_cockpit_snapshot(_mock_db(), user_id=1)

    # snapshot_at kesinlikle ayri string olmali (ama test kararsizligina karsi zorla)
    s2 = dict(s2)
    s2["snapshot_at"] = "2099-01-01T00:00:00+00:00"

    assert compute_snapshot_hash(s1) == compute_snapshot_hash(s2)


# ============================================================
# TEST 4 — hash state degisikligini yakalar
# ============================================================

def test_hash_state_degisikligini_yakalar(monkeypatch):
    """net_worth_tl farkli iki snapshot farkli hash uretmeli."""
    monkeypatch.setattr("app.cockpit_snapshot.generate_forecast",
                        _fake_forecast_fn())

    cockpit_a = {**_fake_cockpit(), "net_deger": 50000.0}
    cockpit_b = {**_fake_cockpit(), "net_deger": 50001.0}

    monkeypatch.setattr("app.cockpit_snapshot.generate_cockpit",
                        lambda *a, **kw: cockpit_a)
    s1 = build_cockpit_snapshot(_mock_db(), user_id=1)

    monkeypatch.setattr("app.cockpit_snapshot.generate_cockpit",
                        lambda *a, **kw: cockpit_b)
    s2 = build_cockpit_snapshot(_mock_db(), user_id=1)

    assert compute_snapshot_hash(s1) != compute_snapshot_hash(s2)


# ============================================================
# TEST 5 — cockpit fail -> partial snapshot, forecast alanlari dolu
# ============================================================

def test_partial_failure_safe(monkeypatch):
    """generate_cockpit RuntimeError firlatsa da snapshot donmeli; cockpit alanlari 0.0."""
    monkeypatch.setattr("app.cockpit_snapshot.generate_cockpit",
                        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("DB down")))
    monkeypatch.setattr("app.cockpit_snapshot.generate_forecast",
                        _fake_forecast_fn())

    snapshot = build_cockpit_snapshot(_mock_db(), user_id=1)

    # Exception firlatilmamali
    assert snapshot is not None

    # Cockpit alanlari 0.0 (basarisiz oldugu icin)
    assert snapshot["net_worth_tl"] == 0.0
    assert snapshot["cash_tl"] == 0.0
    assert snapshot["daily_limit_tl"] == 0.0

    # Forecast alanlari dolu
    assert snapshot["cashflow_30d_tl"] == 7000.0
    assert snapshot["cashflow_60d_tl"] == 14000.0
