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


# ============================================================
# BUG #276 — KALİTE KOŞUMU, ÖLÜ KOÇU YÜKSEK PUANLA ÖDÜLLENDİRİYORDU
# ============================================================
# Ölçüm (10 Ağu 2026): tüm sağlayıcılar düşmüş hâlde (RESIL-004 dalı) koşulan eval
# **%83.3 pass_rate / 6-8 senaryo geçti** veriyordu; "Tamam." diyen sessiz koç da aynı puanı
# alıyordu. Sebep: 8 senaryonun 6'sı yalnız OLUMSUZ kriter taşıyordu ("aksiyon önermedi",
# "sahte tamamlama yok") — hiç cevap vermeyen koç bunları bedavaya geçiyor. Harness'ın kendi
# docstring'i "kalite düşerse pass_rate düşer" diyordu; ölçüm bunun doğru olmadığını gösterdi.


class _OluSaglayici:
    """Tüm sağlayıcılar düşmüş: chat() RESIL-004 zarif-bozulma dalına girer."""

    NAME = "Gemini"; model = "gemini-2.5-flash-lite"; last_used_provider = "gemini"

    def chat(self, system_prompt, messages, tools):
        raise RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded")


def test_olu_saglayici_kosumu_gecersiz_sayilir(db):
    """Sağlayıcı hiç cevap veremediyse koşum bir KALİTE ölçümü değildir."""
    rapor = run_eval(CoachEngine(provider=_OluSaglayici()), db, 1, DEFAULT_SCENARIOS)

    assert rapor["gecerli"] is False, "Ölü sağlayıcı koşumu geçerli sayıldı"
    assert rapor["llm_olu_cagri"] == len(DEFAULT_SCENARIOS)
    assert rapor["scenario_pass"] == 0, (
        f"Ölü koç {rapor['scenario_pass']}/{rapor['scenario_total']} senaryo geçti — "
        "koşum, koçun çalışıp çalışmadığını ayırt etmiyor"
    )
    assert rapor["pass_rate"] == 0.0, (
        f"Ölü koç %{rapor['pass_rate']} aldı — ölçülen defekt buydu (%83.3)"
    )
    assert "GEÇERSİZ KOŞUM" in format_report(rapor), "Uyarı raporun başında görünmüyor"


def test_sessiz_koc_yuksek_puan_alamaz(db):
    """LLM ayakta ama içi boş ('Tamam.'): hiçbir senaryo geçmemeli."""
    rapor = run_eval(CoachEngine(provider=ScriptedProvider(text="Tamam.")), db, 1,
                     DEFAULT_SCENARIOS)
    assert rapor["scenario_pass"] == 0, (
        f"Sessiz koç {rapor['scenario_pass']} senaryo geçti — olumsuz kriterler bedavaya geçiyor"
    )
    # Ölü koştan farkı: sağlayıcı cevap VERDİ, o yüzden koşum "geçersiz" değil.
    assert rapor["gecerli"] is True


def test_saglikli_koc_puan_alabilir_kapsam_tabani(db):
    """Kapsam tabanı: kapı her şeyi sıfırlamıyor — anlamlı cevap veren koç puan alır."""
    metin = "## Durum\n\nKart borcun 11.976 TL, nakit 4.276 TL. Öncelik kart borcunu düşürmek."
    rapor = run_eval(CoachEngine(provider=ScriptedProvider(text=metin)), db, 1,
                     DEFAULT_SCENARIOS)
    assert rapor["check_pass"] > 0, "Sağlıklı cevap da sıfır puan aldı — kapı ölü"
    cevapladi = [r for r in rapor["scenarios"] if r["scores"].get("cevapladi")]
    assert len(cevapladi) == len(DEFAULT_SCENARIOS), (
        "Anlamlı cevap veren koç bazı senaryolarda 'cevapladı' sayılmadı"
    )


@pytest.mark.parametrize("senaryo", DEFAULT_SCENARIOS, ids=lambda s: s.name)
def test_her_senaryo_en_az_bir_OLUMLU_kriter_tasir(senaryo):
    """Drift kilidi: yalnız olumsuz kriterli senaryo, hiç cevap vermeyen koçla geçer."""
    olumlu = {"cevapladi", "action", "grounded", "format"}
    assert olumlu & set(senaryo.checks), (
        f"{senaryo.name} yalnız olumsuz kriter taşıyor ({senaryo.checks}) — sessizlik bunu geçer"
    )


def test_cevapsiz_kalan_senaryoda_diger_kriterler_gecmis_sayilmaz():
    """'Aksiyon önermedi' bir başarı değildir: hiç konuşmayan koç da önermez."""
    res = {"reply": "", "proposed_actions": [], "grounding": {"ok": True},
           "llm_kullanilamadi": True}
    s = score_result(res, ["cevapladi", "no_action", "no_fake", "grounded"])
    assert s == {"cevapladi": False, "no_action": False, "no_fake": False, "grounded": False}
