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


# --- P1-5: explicit red-line finansal-anchor (finans-dışı cümle yakalanmaz) ---

def test_p1_5_red_line_requires_financial_anchor():
    from app.coach_insights import ERL_PATTERNS, ERL_FINANCIAL_RE, ERL_ANCHOR_REQUIRED
    mutlak = next(p for p in ERL_PATTERNS if p["category"] == "mutlak_red")["pattern"]

    finans_disi = "asla o filmi izlemem"
    finansal = "asla kredi cekmem"
    # desen ikisini de yakalar (gramer aynı)...
    assert mutlak.search(finans_disi) and mutlak.search(finansal)
    # ...ama finansal anchor gate yalnızca finansal olanı geçirir
    assert "mutlak_red" in ERL_ANCHOR_REQUIRED
    assert ERL_FINANCIAL_RE.search(finans_disi) is None        # film → kırmızı çizgi DEĞİL
    assert ERL_FINANCIAL_RE.search(finansal) is not None       # kredi → EVET


# --- P1-4: dormant sweep (top-3/dominant dışına düşen eski insight active kalmaz) ---

def test_p1_4_dormant_sweep_downgrades_stale(db_session, test_user):
    from app.coach_insights import _sweep_insights_dormant
    from app.models import CoachInsight
    guncel = CoachInsight(user_id=test_user.id, insight_type="decision_rhythm",
                          title="Buyuk kararlarin cogu aksam dilminde", content="x", status="active")
    bayat = CoachInsight(user_id=test_user.id, insight_type="decision_rhythm",
                         title="Buyuk kararlarin cogu sabah dilminde", content="x", status="active")
    baska_tip = CoachInsight(user_id=test_user.id, insight_type="mc_reference_frequency",
                             title="MC5 sik referans verilen kural", content="x", status="active")
    db_session.add_all([guncel, bayat, baska_tip])
    db_session.commit()

    swept = _sweep_insights_dormant(db_session, test_user.id, "decision_rhythm",
                                    {"Buyuk kararlarin cogu aksam dilminde"})
    db_session.refresh(guncel); db_session.refresh(bayat); db_session.refresh(baska_tip)

    assert swept == 1
    assert guncel.status == "active"        # şu anki dominant → korunur
    assert bayat.status == "dormant"        # eski dilim → dormant
    assert baska_tip.status == "active"     # farklı insight_type → dokunulmaz


# --- P1-15: OperationName enum DB'ye DEĞER yazar (üye adı değil) ---

def test_p1_15_operation_name_stores_value_not_member(db_session, test_user):
    from sqlalchemy import text
    from app.models import ReasoningTrace, OperationName
    tr = ReasoningTrace(user_id=test_user.id, trace_id="t-1", step_index=0,
                        operation_name=OperationName.RULE_CHECK)
    db_session.add(tr)
    db_session.commit()
    # ham DB değeri "rule_check" (values_callable) olmalı, "RULE_CHECK" (üye adı) DEĞİL
    raw = db_session.execute(
        text("SELECT operation_name FROM reasoning_traces WHERE id = :i"), {"i": tr.id}
    ).scalar()
    assert raw == "rule_check"
    # ORM okuma enum'a geri map'ler
    db_session.refresh(tr)
    assert tr.operation_name == OperationName.RULE_CHECK


# --- P1-24: kart stratejisi utilization-guard (near-full kartta zararlı float-tavsiyesi vermez) ---

def test_p1_24_high_utilization_suppresses_float_advice():
    from datetime import date
    from app.rules_engine import evaluate_credit_card_strategy
    # kesim geçmiş (vade_avantaji dalı), %98.5 dolu kart (Murat senaryosu)
    dolu = evaluate_credit_card_strategy(date(2026, 7, 13), statement_day=2, payment_day=12,
                                         current_debt=11822.66, credit_limit=12000.0)
    assert dolu["durum"] == "vade_avantaji"
    assert "YAPMA" in dolu["mesaj"] and "borç azalt" in dolu["mesaj"].lower()  # güvenli uyarı
    assert "stratejik silah" not in dolu["mesaj"]                              # zararlı tavsiye YOK

    # sağlıklı kullanım → stratejik kullanım tavsiyesi meşru
    saglikli = evaluate_credit_card_strategy(date(2026, 7, 13), statement_day=2, payment_day=12,
                                             current_debt=2000.0, credit_limit=12000.0)
    assert saglikli["durum"] == "vade_avantaji"
    assert "stratejik" in saglikli["mesaj"].lower()


# --- P1-25: AnthropicProvider tool-history adapter (OpenAI-şema → Anthropic content-block) ---

def test_p1_25_to_anthropic_messages_converts_tool_history():
    import json
    from app.coach import _to_anthropic_messages
    internal = [
        {"role": "user", "content": "TLY sat"},
        {"role": "assistant", "content": "Satıyorum",
         "tool_calls_json": json.dumps([{"id": "call_1", "name": "propose_action",
                                         "args": {"lots": 4}}])},
        {"role": "tool", "tool_call_id": "call_1", "content": "action_id=5, status=pending"},
        {"role": "assistant", "content": ""},  # boş düz mesaj → atlanmalı
    ]
    out = _to_anthropic_messages(internal)

    # boş düz mesaj atlandı → 3 mesaj
    assert len(out) == 3
    # user metin
    assert out[0] == {"role": "user", "content": "TLY sat"}
    # assistant tool_use content-block (id/name/input)
    assert out[1]["role"] == "assistant"
    blocks = out[1]["content"]
    assert {"type": "text", "text": "Satıyorum"} in blocks
    tool_use = next(b for b in blocks if b["type"] == "tool_use")
    assert tool_use["id"] == "call_1" and tool_use["name"] == "propose_action"
    assert tool_use["input"] == {"lots": 4}
    # tool result → user mesajında tool_result block, eşleşen tool_use_id
    assert out[2]["role"] == "user"
    tr = out[2]["content"][0]
    assert tr["type"] == "tool_result" and tr["tool_use_id"] == "call_1"
