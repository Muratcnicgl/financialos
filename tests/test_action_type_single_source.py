"""
M82 (Wave-6) — action_type TEK DOĞRULUK KAYNAĞI drift kilidi.

BUG #161 (M68) kökü: action_type string'leri 3 yerde AYRI listeleniyordu → biri güncellenip
diğeri unutulunca koç geçerli aksiyon önerip execute "Bilinmeyen aksiyon" diyordu. M82 tek kaynak
`action_executor.ACTION_TYPES`. Bu test 3 kod-gate'in + prompt prose'un ondan sapmadığını kilitler.
Yeni action_type eklenip herhangi bir nokta senkron değilse TEST KIRILIR.
"""
from __future__ import annotations

from app.action_executor import ACTION_TYPES, ACTION_HANDLERS, propose_action
from app import coach as coach_mod


def _coach_enum() -> set:
    """coach.py propose_action tool şemasındaki action_type enum'u."""
    props = coach_mod.PROPOSE_ACTION_SCHEMA["parameters"]["properties"]
    return set(props["action_type"]["enum"])


def test_execute_dispatcher_action_types_ile_senkron():
    """ACTION_HANDLERS anahtarları ile ACTION_TYPES birebir (import-anı assert'in test yansıması)."""
    assert set(ACTION_HANDLERS) == set(ACTION_TYPES)


def test_coach_tool_enum_action_types_ile_senkron():
    """coach.py propose tool enum'u ACTION_TYPES'tan türetilmiş — birebir eşleşir."""
    assert _coach_enum() == set(ACTION_TYPES)


def test_uc_gate_ayni_kume():
    """Üç kod-gate (propose valid_types = ACTION_TYPES, execute dispatcher, coach enum) TEK küme."""
    assert set(ACTION_TYPES) == set(ACTION_HANDLERS) == _coach_enum()


def test_propose_action_bilinmeyen_turu_reddeder():
    """propose_action ACTION_TYPES dışını reddeder (valid_types artık ayrı liste değil)."""
    import pytest
    with pytest.raises(ValueError, match="Bilinmeyen aksiyon türü"):
        propose_action(db=None, user_id=1, action_type="teleport_money",
                       payload={}, summary="x")


def test_prompt_prose_tum_action_typelari_aniyor():
    """V3 prompt prose (seçim tablosu + payload şablonları) HER action_type'ı anmalı — koç
    geçerli bir türü öneremezse enum'da olsa da işe yaramaz. Prose ile enum tutarlılığı."""
    prompt = coach_mod.V3_GOD_MODE_PROMPT
    eksik = [a for a in ACTION_TYPES if a not in prompt]
    assert not eksik, f"V3 prompt'ta anılmayan action_type(ler): {eksik}"
