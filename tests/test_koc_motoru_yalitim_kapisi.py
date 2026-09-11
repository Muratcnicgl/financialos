"""
SEC-026 / BUG #415 KAPISI — PAYLAŞILAN CoachEngine KULLANICILAR ARASI DURUM TAŞIMAZ.

Ölçülen (12 Eyl 2026): motor tek süreçte tek örnek (`_get_engine`), iki kullanıcı aynı
nesneden geçer. Madde "stateless ama izolasyon testi yok" diyordu. Ölçüm: motorun örnek
durumu `provider` + `max_history_turns`tan ibaret; kullanıcı bağlamı her çağrıda
`_build_context_message(db, user_id)` ile DB'den kurulur, geçmiş `CoachMemory`'den
kullanıcı filtresiyle okunur.

Kilitlenen: A ile sohbet ettikten sonra B'nin sistem promptu A'nın hesabını/mesajını
taşımaz; motorun örnek sözlüğü çağrıdan önce ve sonra AYNI anahtarlarla (durum eklenmez);
`FallbackProvider.last_used_provider`ın paylaşıldığı biliniyor ve muhasebe ona dayanmıyor
(test_coach_eszamanlilik kilitler).
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.coach import CoachEngine, LLMProvider, LLMResponse
from app.models import Account, AccountType, Base, User


class _KaydedenProvider(LLMProvider):
    NAME = "Gemini"
    model = "sahte"

    def __init__(self):
        self.gorulen = []   # (system_prompt, messages) — her çağrının bağlamı

    def _raw_chat(self, system_prompt, messages, tools):
        self.gorulen.append((system_prompt, [m.get("content", "") for m in messages]))
        return LLMResponse(text="Tamam.", tool_calls=[], provider_used="gemini", model_name="sahte")

    def chat(self, system_prompt, messages, tools):
        return self._raw_chat(system_prompt, messages, tools)


@pytest.fixture
def s():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    ses = sessionmaker(bind=eng)()
    ses.add_all([User(id=1, name="ayse"), User(id=2, name="bora")])
    ses.add_all([Account(user_id=1, name="AyseninKumbarasi", account_type=AccountType.cash, balance=111),
                 Account(user_id=2, name="BoraninCuzdani", account_type=AccountType.cash, balance=222)])
    ses.commit()
    yield ses
    ses.close()


def test_iki_kullanici_ayni_motor_baglam_karismaz(s):
    p = _KaydedenProvider()
    motor = CoachEngine(provider=p)
    once = set(vars(motor))
    motor.chat(db=s, user_id=1, user_message="AYSE-GIZLI-MESAJ durumum ne?", include_cockpit=True)
    motor.chat(db=s, user_id=2, user_message="benim durumum?", include_cockpit=True)
    # İki-geçiş mimarisi: her sohbet 2 sağlayıcı çağrısı → 4; B'nin çağrıları son ikisi.
    assert len(p.gorulen) == 4, len(p.gorulen)
    for sp_b, mesajlar_b in p.gorulen[2:]:
        assert "BoraninCuzdani" in sp_b
        assert "AyseninKumbarasi" not in sp_b, "B'nin promptu A'nın hesabını taşıyor"
        assert not any("AYSE-GIZLI-MESAJ" in m for m in mesajlar_b), "B'nin geçmişine A'nın mesajı sızdı"
    sp_b, mesajlar_b = p.gorulen[-1]
    assert "BoraninCuzdani" in sp_b
    assert "AyseninKumbarasi" not in sp_b, "B'nin promptu A'nın hesabını taşıyor"
    assert not any("AYSE-GIZLI-MESAJ" in m for m in mesajlar_b), "B'nin geçmişine A'nın mesajı sızdı"
    assert set(vars(motor)) == once, f"motor çağrıda durum edindi: {set(vars(motor)) - once}"


def test_motor_ornek_durumu_kullanici_verisi_tasimaz():
    motor = CoachEngine(provider=_KaydedenProvider())
    yasak = {"user_id", "history", "messages", "memory", "context", "cockpit", "db"}
    assert not (set(vars(motor)) & yasak), set(vars(motor)) & yasak
    assert set(vars(motor)) <= {"provider", "max_history_turns"}, set(vars(motor))
