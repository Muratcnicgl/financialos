"""
M79 — app/premortem.py coverage tamamlama testleri.

Kapsanmayan SAF/YARDIMCI fonksiyonlari hedefler; HICBIR GERCEK LLM CAGRISI YAPMAZ.
LLM provider mock'lanir (FakeProvider.chat -> sabit JSON). In-memory SQLite (StaticPool).

Odak satirlar (onceki coverage %61):
- _user_prompt              (135-166)
- _parse_and_validate       (181-203)
- generate_premortem        (211-273) — FakeProvider ile, network yok
- persist_premortem         (309-353)
- load_cached_premortem     (284-306)

Pattern: tests/test_premortem_endpoint.py taklit.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.coach import LLMResponse
from app.models import ActionStatus, Base, DecisionJournal, PendingAction, User
from app.premortem import (
    PremortemError,
    PremortemResult,
    PremortemScenario,
    PremortemValidationError,
    _parse_and_validate,
    _user_prompt,
    generate_premortem,
    load_cached_premortem,
    persist_premortem,
)


# ============================================================
# FIXTURES (test_premortem_endpoint.py stili)
# ============================================================

@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def db_session(engine) -> Session:
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def user_alice(db_session: Session) -> User:
    u = User(name="alice_premortem_cov")
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


# ============================================================
# YARDIMCI FACTORY'LER
# ============================================================

def _make_pending_action(
    db: Session,
    user_id: int,
    status: ActionStatus = ActionStatus.pending,
    action_type: str = "add_transaction",
    summary: str = "Market harcamasi",
) -> PendingAction:
    p = PendingAction(
        user_id=user_id,
        action_type=action_type,
        payload=json.dumps({"amount": 1500.0, "account_name": "Enpara Nakit"}),
        summary=summary,
        status=status,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _valid_scenarios_payload(n: int = 5) -> dict:
    return {
        "scenarios": [
            {
                "id": f"S{i + 1}",
                "title": f"Test senaryo basligi {i + 1}",
                "probability_label": "orta",
                "impact_tl": -500.0,
                "narrative": (
                    "Bu aksiyon basarisiz oldu. Sebebi su idi: test "
                    f"gerekcesi {i + 1} yeterince uzun yazildi ki gecerli olsun."
                ),
                "mitigation": f"Bunu onlemek icin test aksiyonu {i + 1} yapilmali.",
            }
            for i in range(n)
        ]
    }


def _valid_json_text(n: int = 5) -> str:
    return json.dumps(_valid_scenarios_payload(n), ensure_ascii=False)


class FakeProvider:
    """LLMProvider taklidi — .chat() sabit sirayla onceden verilen cevaplari doner."""

    def __init__(self, responses, provider_used="fakeprov", model_name="fake-model-1"):
        # responses: list[str] (her attempt icin ham metin). Bir string verilirse tekrar eder.
        self._responses = responses if isinstance(responses, list) else [responses]
        self._i = 0
        self.provider_used = provider_used
        self.model_name = model_name
        self.calls = []

    def chat(self, system_prompt, messages, tools):
        self.calls.append({"system_prompt": system_prompt, "messages": messages, "tools": tools})
        idx = min(self._i, len(self._responses) - 1)
        text = self._responses[idx]
        self._i += 1
        return LLMResponse(
            text=text,
            tool_calls=[],
            usage={"input_tokens": 10, "output_tokens": 20},
            provider_used=self.provider_used,
            model_name=self.model_name,
        )


# ============================================================
# _user_prompt  (135-166)
# ============================================================

def test_user_prompt_minimal_action_only():
    """cockpit yok, rationale yok — sadece aksiyon bloklari + gorev satiri."""
    ctx = {
        "action_type": "sell_investment",
        "description": "Fon satisi",
        "amount_tl": 12000.0,
        "target": "AAK fonu",
    }
    out = _user_prompt(ctx, None)

    assert "AKSIYON BAGLAMI:" in out
    assert "Tip: sell_investment" in out
    assert "Aciklama: Fon satisi" in out
    assert "Tutar: 12000.0 TL" in out
    assert "Hedef: AAK fonu" in out
    # cockpit blogu YOK
    assert "COCKPIT OZETI" not in out
    # rationale YOK
    assert "gerekcesi" not in out
    # gorev satiri VAR
    assert "6 ay sonra basarisiz" in out
    assert "Sadece JSON" in out


def test_user_prompt_with_rationale():
    """rationale verilince Murat'in gerekcesi satiri eklenir."""
    ctx = {
        "action_type": "add_transaction",
        "description": "Market",
        "amount_tl": 800.0,
        "target": "-",
        "rationale": "Aylik gida ihtiyaci",
    }
    out = _user_prompt(ctx, None)
    assert "Murat'in gerekcesi: Aylik gida ihtiyaci" in out


def test_user_prompt_with_cockpit_snapshot():
    """cockpit verilince finansal durum bloklari ve dogru anahtarlar (BUG #065) eklenir."""
    ctx = {"action_type": "add_transaction", "description": "X", "amount_tl": 100.0, "target": "-"}
    cockpit = {
        "net_worth_tl": 50000.0,
        "cashflow_30d_tl": 7000.0,
        "cashflow_60d_tl": 14000.0,
        "lowest_balance_date": "2026-06-01",
        "lowest_balance_tl": 12000.0,
        "crunch_count": 3,
    }
    out = _user_prompt(ctx, cockpit)

    assert "COCKPIT OZETI (mevcut finansal durum):" in out
    assert "Net deger: 50000.0 TL" in out
    assert "30g net akis: 7000.0 TL" in out
    assert "60g net akis: 14000.0 TL" in out
    # BUG #065: dogru anahtarlar kullanilmali
    assert "En dusuk bakiye tarihi: 2026-06-01" in out
    assert "En dusuk bakiye: 12000.0 TL" in out
    assert "Nakit kriz gunu sayisi (30g): 3" in out


def test_user_prompt_empty_context_uses_defaults():
    """Bos ctx -> .get default'lari (bilinmiyor / - / 0.0) kullanilir."""
    out = _user_prompt({}, None)
    assert "Tip: bilinmiyor" in out
    assert "Aciklama: -" in out
    assert "Tutar: 0.0 TL" in out
    assert "Hedef: -" in out


# ============================================================
# _parse_and_validate  (181-203)
# ============================================================

def test_parse_valid_json_returns_scenarios():
    scen = _parse_and_validate(_valid_json_text(5))
    assert len(scen) == 5
    assert all(isinstance(s, PremortemScenario) for s in scen)


def test_parse_strips_json_code_fence():
    """```json ... ``` fence'li cevap soyulup parse edilir."""
    fenced = "```json\n" + _valid_json_text(4) + "\n```"
    scen = _parse_and_validate(fenced)
    assert len(scen) == 4


def test_parse_strips_bare_fence():
    """Dil etiketi olmayan ``` fence de soyulur."""
    fenced = "```\n" + _valid_json_text(3) + "\n```"
    scen = _parse_and_validate(fenced)
    assert len(scen) == 3


def test_parse_invalid_json_raises_jsondecodeerror():
    with pytest.raises(json.JSONDecodeError):
        _parse_and_validate("bu bir JSON degil {")


def test_parse_scenarios_not_list_raises():
    payload = json.dumps({"scenarios": {"id": "S1"}})
    with pytest.raises(PremortemValidationError, match="list degil"):
        _parse_and_validate(payload)


def test_parse_scenarios_missing_key_raises():
    """'scenarios' anahtari yoksa None -> list degil hatasi."""
    with pytest.raises(PremortemValidationError, match="list degil"):
        _parse_and_validate(json.dumps({"baska": []}))


def test_parse_too_few_scenarios_raises():
    with pytest.raises(PremortemValidationError, match="senaryo uretildi"):
        _parse_and_validate(_valid_json_text(2))


def test_parse_too_many_scenarios_raises():
    with pytest.raises(PremortemValidationError, match="senaryo uretildi"):
        _parse_and_validate(_valid_json_text(6))


def test_parse_bad_scenario_field_raises_validationerror():
    """Senaryo alani schema'ya uymaz (kisa narrative) -> Pydantic ValidationError."""
    bad = {
        "scenarios": [
            {
                "id": "S1",
                "title": "Yeterince uzun baslik",
                "probability_label": "orta",
                "impact_tl": -100.0,
                "narrative": "kisa",  # min_length=40 ihlali
                "mitigation": "Yeterince uzun mitigation yazildi burada.",
            }
        ] * 3
    }
    with pytest.raises(ValidationError):
        _parse_and_validate(json.dumps(bad))


# ============================================================
# PremortemResult id normalizasyonu (76-83)
# ============================================================

def test_result_normalizes_scenario_ids():
    """LLM bozuk/tekrar id verse bile S1..Sn yeniden atanir (BUG #135)."""
    scen = _parse_and_validate(_valid_json_text(4))
    # id'leri kasten boz
    for s in scen:
        s.id = "XXX"
    res = PremortemResult(action_id=1, scenarios=scen)
    assert [s.id for s in res.scenarios] == ["S1", "S2", "S3", "S4"]


# ============================================================
# generate_premortem  (211-273) — FakeProvider, network YOK
# ============================================================

def test_generate_premortem_happy_path():
    prov = FakeProvider(_valid_json_text(5))
    ctx = {"action_type": "add_transaction", "description": "X", "amount_tl": 1.0, "target": "-"}

    res = generate_premortem(action_id=42, action_context=ctx, provider=prov)

    assert isinstance(res, PremortemResult)
    assert res.action_id == 42
    assert len(res.scenarios) == 5
    assert res.provider_used == "fakeprov"
    assert res.model_name == "fake-model-1"
    assert len(prov.calls) == 1  # ilk denemede basarili


def test_generate_premortem_retry_after_empty_response():
    """Ilk cevap bos -> ikinci deneme dolu -> basarili (retry dali)."""
    prov = FakeProvider(["   ", _valid_json_text(3)])
    ctx = {"action_type": "x", "description": "y", "amount_tl": 0.0, "target": "-"}

    res = generate_premortem(action_id=7, action_context=ctx, provider=prov)
    assert len(res.scenarios) == 3
    assert len(prov.calls) == 2


def test_generate_premortem_retry_after_parse_error():
    """Ilk cevap bozuk JSON -> retry reminder eklenir -> ikinci cevap gecerli."""
    prov = FakeProvider(["bozuk { json", _valid_json_text(4)])
    ctx = {"action_type": "x", "description": "y", "amount_tl": 0.0, "target": "-"}

    res = generate_premortem(action_id=9, action_context=ctx, provider=prov)
    assert len(res.scenarios) == 4
    assert len(prov.calls) == 2
    # ikinci cagrida retry reminder mesaji eklenmis olmali
    second_msgs = prov.calls[1]["messages"]
    assert any("JSON FORMATINA UYMADI" in m["content"] for m in second_msgs)


def test_generate_premortem_both_attempts_fail_raises():
    """Iki deneme de bozuk -> PremortemError, son hata tipi mesajda."""
    prov = FakeProvider(["bozuk {", "yine bozuk {"])
    ctx = {"action_type": "x", "description": "y", "amount_tl": 0.0, "target": "-"}

    with pytest.raises(PremortemError, match="2 denemede basarisiz"):
        generate_premortem(action_id=1, action_context=ctx, provider=prov)
    assert len(prov.calls) == 2


def test_generate_premortem_both_empty_raises():
    """Iki deneme de bos cevap -> PremortemError."""
    prov = FakeProvider(["", ""])
    ctx = {"action_type": "x", "description": "y", "amount_tl": 0.0, "target": "-"}
    with pytest.raises(PremortemError, match="2 denemede basarisiz"):
        generate_premortem(action_id=1, action_context=ctx, provider=prov)


def test_generate_premortem_unexpected_exception_path():
    """provider.chat beklenmedik hata firlatirsa da 2 deneme sonrasi PremortemError."""

    class BoomProvider:
        def __init__(self):
            self.calls = 0

        def chat(self, system_prompt, messages, tools):
            self.calls += 1
            raise RuntimeError("beklenmedik cokme")

    prov = BoomProvider()
    ctx = {"action_type": "x", "description": "y", "amount_tl": 0.0, "target": "-"}
    with pytest.raises(PremortemError, match="RuntimeError"):
        generate_premortem(action_id=1, action_context=ctx, provider=prov)
    assert prov.calls == 2


def test_generate_premortem_default_provider_built(monkeypatch):
    """provider=None -> build_provider() cagrilir (mock'lanir, network yok)."""
    prov = FakeProvider(_valid_json_text(5))
    with patch("app.premortem.build_provider", return_value=prov) as mock_build:
        ctx = {"action_type": "x", "description": "y", "amount_tl": 0.0, "target": "-"}
        res = generate_premortem(action_id=5, action_context=ctx, provider=None)
    mock_build.assert_called_once()
    assert len(res.scenarios) == 5


# ============================================================
# persist_premortem + load_cached_premortem  (284-353)
# ============================================================

def _mk_result(action_id: int, n: int = 5) -> PremortemResult:
    scen = _parse_and_validate(_valid_json_text(n))
    return PremortemResult(
        action_id=action_id,
        scenarios=scen,
        provider_used="fakeprov",
        model_name="fake-model-1",
    )


def test_persist_creates_new_decision_journal(db_session, user_alice):
    action = _make_pending_action(db_session, user_alice.id)
    result = _mk_result(action.id)

    dj = persist_premortem(db_session, action, user_alice.id, result, snapshot_hash="hash-a")

    assert isinstance(dj, DecisionJournal)
    assert dj.decision_text == f"PendingAction#{action.id}"
    assert dj.cockpit_snapshot_hash == "hash-a"
    assert dj.premortem_run_at is not None
    assert dj.decision_type == action.action_type
    persisted = json.loads(dj.premortem_scenarios)
    assert len(persisted) == 5


def test_persist_updates_existing_idempotent(db_session, user_alice):
    """Ayni action icin ikinci persist mevcut DJ'yi gunceller (tek kayit)."""
    action = _make_pending_action(db_session, user_alice.id)

    dj1 = persist_premortem(db_session, action, user_alice.id, _mk_result(action.id, 5),
                            snapshot_hash="h1")
    dj2 = persist_premortem(db_session, action, user_alice.id, _mk_result(action.id, 3),
                            snapshot_hash="h2")

    assert dj1.id == dj2.id
    assert dj2.cockpit_snapshot_hash == "h2"
    rows = db_session.execute(
        select(DecisionJournal).where(
            DecisionJournal.decision_text == f"PendingAction#{action.id}"
        )
    ).scalars().all()
    assert len(rows) == 1
    assert len(json.loads(rows[0].premortem_scenarios)) == 3


def test_load_cached_hit(db_session, user_alice):
    """Ayni action + ayni hash -> cache hit, (dj_id, scenarios) doner."""
    action = _make_pending_action(db_session, user_alice.id)
    dj = persist_premortem(db_session, action, user_alice.id, _mk_result(action.id),
                           snapshot_hash="samehash")

    cached = load_cached_premortem(db_session, action, user_alice.id, "samehash")
    assert cached is not None
    dj_id, scen = cached
    assert dj_id == dj.id
    assert len(scen) == 5
    assert all(isinstance(s, PremortemScenario) for s in scen)


def test_load_cached_miss_no_record(db_session, user_alice):
    """Hic persist yapilmamis action -> None."""
    action = _make_pending_action(db_session, user_alice.id)
    assert load_cached_premortem(db_session, action, user_alice.id, "x") is None


def test_load_cached_miss_hash_mismatch(db_session, user_alice):
    """Kayit var ama snapshot_hash farkli (cockpit degisti) -> None (bayat)."""
    action = _make_pending_action(db_session, user_alice.id)
    persist_premortem(db_session, action, user_alice.id, _mk_result(action.id),
                      snapshot_hash="eski-hash")
    assert load_cached_premortem(db_session, action, user_alice.id, "yeni-hash") is None


def test_load_cached_miss_empty_snapshot_hash(db_session, user_alice):
    """Sorgu hash'i bos -> None (guvenli tarafta yeniden uret)."""
    action = _make_pending_action(db_session, user_alice.id)
    persist_premortem(db_session, action, user_alice.id, _mk_result(action.id),
                      snapshot_hash="dolu")
    assert load_cached_premortem(db_session, action, user_alice.id, "") is None


def test_load_cached_corrupt_json_returns_none(db_session, user_alice):
    """DB'deki premortem_scenarios bozuksa -> None (try/except dali)."""
    action = _make_pending_action(db_session, user_alice.id)
    persist_premortem(db_session, action, user_alice.id, _mk_result(action.id),
                      snapshot_hash="h")
    # kaydi bozuk JSON ile ez
    dj = db_session.execute(
        select(DecisionJournal).where(
            DecisionJournal.decision_text == f"PendingAction#{action.id}"
        )
    ).scalar_one()
    dj.premortem_scenarios = "{bozuk json"
    db_session.commit()

    assert load_cached_premortem(db_session, action, user_alice.id, "h") is None
