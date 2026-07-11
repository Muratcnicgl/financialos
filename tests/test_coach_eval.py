"""
Coach Eval Harness testleri — puanlama mantığının DOĞRU ölçtüğünü kilitler.
Framework'ü ScriptedProvider ile doğrular: uyumlu cevap kriterleri geçer, uyumsuz geçmez.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, User, Account, AccountType
from app.coach import CoachEngine, LLMResponse
from app.coach_eval import EvalScenario, score_result, run_eval, format_report, DEFAULT_SCENARIOS


class ScriptedProvider:
    NAME = "Scripted"; model = "scripted-1"; last_used_provider = "scripted"

    def __init__(self, text="Tamam.", tool_calls=None):
        self.text = text
        self.tool_calls = tool_calls or []

    def chat(self, system_prompt, messages, tools):
        return LLMResponse(text=self.text, tool_calls=list(self.tool_calls),
                           usage={"input_tokens": 1, "output_tokens": 1},
                           provider_used="scripted", model_name="scripted-1")


# ---- score_result (saf puanlama) ------------------------------------------

def test_score_no_action_ve_no_confidence():
    res = {"reply": "Kart borcun 42.100 TL.", "proposed_actions": [], "grounding": {"ok": True}}
    s = score_result(res, ["no_action", "no_confidence"])
    assert s == {"no_action": True, "no_confidence": True}


def test_score_action_pozitif():
    res = {"reply": "Kaydediyorum.", "proposed_actions": [{"id": 1}], "grounding": {"ok": True}}
    assert score_result(res, ["action"])["action"] is True
    assert score_result(res, ["no_action"])["no_action"] is False


def test_score_sahte_tamamlama_yakalanir():
    # eylem YOK ama "kaydettim" iddiası VAR → no_fake FAIL
    res = {"reply": "Harcamanı kaydettim.", "proposed_actions": [], "grounding": {}}
    assert score_result(res, ["no_fake"])["no_fake"] is False
    # gerçek eylem varsa "kaydettim" meşru → no_fake PASS
    res2 = {"reply": "Kaydettim.", "proposed_actions": [{"id": 1}], "grounding": {}}
    assert score_result(res2, ["no_fake"])["no_fake"] is True


def test_score_confidence_sizinti():
    res = {"reply": "[CONFIDENCE: 0.9] Durum iyi.", "proposed_actions": [], "grounding": {}}
    assert score_result(res, ["no_confidence"])["no_confidence"] is False


def test_score_grounding_fail():
    res = {"reply": "47.800 TL borç var.", "proposed_actions": [], "grounding": {"ok": False}}
    assert score_result(res, ["grounded"])["grounded"] is False


def test_score_format():
    assert score_result({"reply": "## Rapor\n- x"}, ["format"])["format"] is True
    assert score_result({"reply": "düz metin"}, ["format"])["format"] is False


def test_scenario_gecersiz_kriter_hata():
    with pytest.raises(ValueError):
        EvalScenario("x", "mesaj", ["olmayan_kriter"])


# ---- run_eval (ScriptedProvider ile uçtan uca) ----------------------------

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    s.add(User(id=1, name="murat"))
    s.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=5000.0))
    s.commit()
    yield s
    s.close()


def test_run_eval_uyumlu_cevap_gecer(db):
    # soru senaryosu: temiz metin, tool yok → no_action geçer
    prov = ScriptedProvider(text="Kart borcun kontrol altında.")
    engine = CoachEngine(provider=prov)
    scenarios = [EvalScenario("soru", "Kart borcum ne?", ["no_action", "no_confidence"], include_cockpit=False)]
    report = run_eval(engine, db, 1, scenarios)
    assert report["scenario_pass"] == 1
    assert report["pass_rate"] == 100.0


def test_run_eval_uyumsuz_cevap_kalir(db):
    # grounding: cockpit'te olmayan tutar (hallüsinasyon) → grounded FAIL.
    # (Koç sahte-tamamlamayı OTOMATİK temizler; grounding'i ise zorlamaz → eval'in asıl gücü burada.)
    prov = ScriptedProvider(text="Dikkat, 47.800 TL beklenmedik borç var.")
    engine = CoachEngine(provider=prov)
    scenarios = [EvalScenario("analiz", "durumu göster", ["grounded"], include_cockpit=True)]
    report = run_eval(engine, db, 1, scenarios)
    assert report["scenario_pass"] == 0
    assert report["pass_rate"] == 0.0


def test_format_report_metin():
    report = run_eval(CoachEngine(provider=ScriptedProvider(text="ok")),
                      *(_mk_db(), 1),
                      [EvalScenario("s", "Kart borcum ne?", ["no_action"], include_cockpit=False)])
    txt = format_report(report)
    assert "Koç Eval Skor Kartı" in txt and "s:" in txt


def _mk_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    s.add(User(id=1, name="murat"))
    s.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=5000.0))
    s.commit()
    return s


def test_default_scenarios_gecerli():
    # tüm DEFAULT_SCENARIOS kriterleri geçerli (EvalScenario __post_init__ doğrular)
    assert len(DEFAULT_SCENARIOS) >= 3
    for sc in DEFAULT_SCENARIOS:
        assert sc.checks
