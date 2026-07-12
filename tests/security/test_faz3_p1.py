"""
Kalite Serüveni Faz 3 (M6) — P1 düzeltme testleri.

Denetim (R3) sonrası GERÇEKTEN AÇIK bulunan P1 maddelerinin düzeltmelerini kilitler.
Çoğu P1 zaten Faz 2'de kapanmıştı (MASTER-FIX-LIST bayat-açık); bunlar açık olanlar.
"""
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app import models
from app.schemas import GoalRuleUpdate
from app.premortem import PremortemResult, PremortemScenario


# --- P1-9 residüel: GoalRuleUpdate percent üst sınırı (create/update asimetrisi) ---

def test_p1_9_goalruleupdate_percent_over_100_rejected():
    with pytest.raises(ValidationError):
        GoalRuleUpdate(allocation_type="percent", allocation_value=Decimal("150"))


def test_p1_9_goalruleupdate_percent_valid_ok():
    u = GoalRuleUpdate(allocation_type="percent", allocation_value=Decimal("30"))
    assert u.allocation_value == Decimal("30")


# --- P1-10: cash_target current_amount 0'a klemplenir (çekim > katkı) ---

def test_p1_10_cash_target_current_amount_clamped_to_zero(db_session, test_user):
    from app.goal_engine import _compute_cash_target
    goal = models.Goal(goal_type="cash", user_id=test_user.id, title="Acil fon",
                       target_amount=Decimal("1000.00"))
    db_session.add(goal)
    db_session.commit()
    # allocation'lar transaction'a bağlı (NOT NULL). net çekim: +100 katkı, -300 çekim → -200
    for amt, tt in [(Decimal("100.00"), models.TransactionType.income),
                    (Decimal("300.00"), models.TransactionType.expense)]:
        tx = models.Transaction(user_id=test_user.id, amount=amt, transaction_type=tt, category="test")
        db_session.add(tx)
        db_session.flush()
        alloc_amt = amt if tt == models.TransactionType.income else -amt
        db_session.add(models.GoalAllocation(goal_id=goal.id, transaction_id=tx.id, amount=alloc_amt))
    db_session.commit()

    res = _compute_cash_target(goal, db_session)
    assert res["current_amount"] == Decimal("0")  # negatif değil, 0'a klempli
    assert res["progress_percent"] == Decimal("0.00")


# --- P1-20: PremortemScenario id'leri deterministik S1..Sn (format + tekillik) ---

def _scn(id_):
    return PremortemScenario(
        id=id_, title="Kart borcu buyudu", probability_label="orta",
        impact_tl=-500.0,
        narrative="Bu senaryo gerceklesti. Sebebi su idi: nakit tamponu yetersizdi ve taksit dustu.",
        mitigation="Onceden 2000 TL tampon ayir ve otomatik odeme kur.",
    )


def test_p1_20_duplicate_ids_normalized_unique():
    r = PremortemResult(action_id=1, scenarios=[_scn("S1"), _scn("S1"), _scn("XX")])
    ids = [s.id for s in r.scenarios]
    assert ids == ["S1", "S2", "S3"]  # çakışma yok, format S1..Sn
    assert len(set(ids)) == len(ids)


def test_p1_20_ids_always_sequential():
    r = PremortemResult(action_id=1, scenarios=[_scn("zzz"), _scn("999"), _scn(""), _scn("S5")])
    assert [s.id for s in r.scenarios] == ["S1", "S2", "S3", "S4"]


# --- P1-22: premortem cache (aynı snapshot_hash → LLM'siz cache dönüşü) ---

def test_p1_22_premortem_cache_hit_and_miss(db_session, test_user):
    from app.premortem import persist_premortem, load_cached_premortem
    pa = models.PendingAction(user_id=test_user.id, action_type="sell_investment",
                              payload="{}", summary="TLY sat")
    db_session.add(pa)
    db_session.commit()
    result = PremortemResult(action_id=pa.id, scenarios=[_scn("S1"), _scn("S2"), _scn("S3")])
    persist_premortem(db_session, pa, test_user.id, result, snapshot_hash="HASH_A")

    # aynı hash → cache HIT (3 senaryo döner, LLM'siz)
    hit = load_cached_premortem(db_session, pa, test_user.id, "HASH_A")
    assert hit is not None
    dj_id, scenarios = hit
    assert len(scenarios) == 3 and [s.id for s in scenarios] == ["S1", "S2", "S3"]

    # farklı hash (cockpit değişti) → cache MISS (yeniden üretilmeli)
    assert load_cached_premortem(db_session, pa, test_user.id, "HASH_B") is None
    # boş hash → MISS
    assert load_cached_premortem(db_session, pa, test_user.id, "") is None
