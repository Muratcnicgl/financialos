"""
FEAT-003 — birikim zarfları (sinking funds / YNAB true expenses).
sinking_fund_plan: target_date'li birikim hedefi için AYLIK GEREKEN katkı = kalan / kalan_ay.
GoalRead.sinking_fund computed_field: cash_target + target_date → plan; diğerleri None.
Deterministik (today enjekte).
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from app.goal_engine import sinking_fund_plan
from app.schemas import GoalRead


# ---- pure math -------------------------------------------------------------

def test_normal_aylik_gereken():
    p = sinking_fund_plan(12000, date(2027, 1, 1), 0, today=date(2026, 1, 1))
    assert p["kalan_ay"] == 12
    assert p["aylik_gereken"] == Decimal("1000.00")
    assert p["gecikmis"] is False and p["tamamlandi"] is False


def test_kismi_ilerleme():
    # 6000 birikmiş, 6 ay kalmış → kalan 6000 / 6 = 1000
    p = sinking_fund_plan(12000, date(2026, 7, 1), 6000, today=date(2026, 1, 1))
    assert p["kalan_ay"] == 6
    assert p["aylik_gereken"] == Decimal("1000.00")


def test_tamamlandi():
    p = sinking_fund_plan(12000, date(2027, 1, 1), 12000, today=date(2026, 1, 1))
    assert p["tamamlandi"] is True
    assert p["aylik_gereken"] == Decimal("0.00")


def test_vade_gecmis_gecikmis():
    p = sinking_fund_plan(5000, date(2026, 1, 1), 1000, today=date(2026, 6, 1))
    assert p["gecikmis"] is True
    assert p["kalan_ay"] == 0
    assert p["aylik_gereken"] == Decimal("4000.00")   # kalanın tümü


def test_bu_ay_vade_gecikmis_degil():
    # vade bu ay, henüz geçmemiş → tüm kalan bu ay gerekli ama gecikmiş değil
    p = sinking_fund_plan(3000, date(2026, 1, 25), 0, today=date(2026, 1, 10))
    assert p["kalan_ay"] == 0
    assert p["gecikmis"] is False
    assert p["aylik_gereken"] == Decimal("3000.00")


def test_target_date_yoksa_none():
    assert sinking_fund_plan(12000, None, 0, today=date(2026, 1, 1)) is None


def test_yuvarlama_half_up():
    # 10000 / 3 = 3333.33...
    p = sinking_fund_plan(10000, date(2026, 4, 1), 0, today=date(2026, 1, 1))
    assert p["kalan_ay"] == 3
    assert p["aylik_gereken"] == Decimal("3333.33")


# ---- GoalRead computed_field ----------------------------------------------

def _goal_read(**over):
    base = dict(
        id=1, user_id=1, goal_type="cash_target", title="MTV birikimi",
        target_amount=Decimal("12000"), baseline_amount=None,
        target_date=date(2027, 1, 1), status="active",
        current_amount=Decimal("0"), progress_percent=Decimal("0"),
        projected_completion_date=None, last_refreshed_at=None,
        created_at=datetime(2026, 1, 1), updated_at=datetime(2026, 1, 1),
        achieved_at=None,
    )
    base.update(over)
    return GoalRead(**base)


def test_goalread_cash_target_target_date_plan_var():
    g = _goal_read()
    d = g.model_dump()
    assert d["sinking_fund"] is not None
    assert d["sinking_fund"]["kalan_ay"] >= 1
    assert isinstance(d["sinking_fund"]["aylik_gereken"], float)


def test_goalread_target_date_yoksa_none():
    g = _goal_read(target_date=None)
    assert g.model_dump()["sinking_fund"] is None


def test_goalread_debt_freedom_none():
    g = _goal_read(goal_type="debt_freedom")
    assert g.model_dump()["sinking_fund"] is None
