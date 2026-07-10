"""
Koç DAVRANIŞ SÖZLEŞMESİ — uçtan uca chat() regresyon harness'i (deterministik, API'siz).

Amaç: KURAL SIFIR (tool-gating), sahte-tamamlama temizliği gibi garantileri BİRİM değil
ENTEGRASYON seviyesinde kilitlemek. (Örn. BUG #085 regresyonu birim testte kaçmıştı;
bu tarz uçtan-uca test onu yakalardı.) ScriptedProvider ne LLM ne ağ gerektirir; ayrıca
kendisine SUNULAN tool isimlerini kaydeder → propose_action gerçekten baskılandı mı doğrulanır.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, User, Account, AccountType
from app.coach import CoachEngine, LLMResponse, _CLARIFY_MSG


class ScriptedProvider:
    NAME = "Scripted"
    model = "scripted-1"
    last_used_provider = "scripted"

    def __init__(self, text="Tamam.", tool_calls=None):
        self.text = text
        self.tool_calls = tool_calls or []
        self.received_tools = None   # son çağrıda LLM'e sunulan tool isimleri

    def chat(self, system_prompt, messages, tools):
        self.received_tools = [t.get("name") for t in (tools or [])]
        return LLMResponse(
            text=self.text, tool_calls=list(self.tool_calls),
            usage={"input_tokens": 10, "output_tokens": 5},
            provider_used="scripted", model_name="scripted-1",
        )


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    u = User(id=1, name="murat")
    session.add(u)
    # nakit hesap (cockpit + olası propose için)
    session.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=5000.0))
    session.commit()
    yield session, u
    session.close()


# ============================================================
# KURAL SIFIR — tool-gating (propose_action sunulmalı mı?)
# ============================================================

def test_soru_propose_sunulmaz(db):
    session, u = db
    prov = ScriptedProvider(text="Kart borcun 42.100 TL.")
    CoachEngine(provider=prov).chat(session, u.id, "Kart borcum ne kadar?", include_cockpit=False)
    assert "propose_action" not in prov.received_tools


def test_gelecek_niyet_propose_sunulmaz(db):
    """BUG #095 entegrasyon kilidi: gelecek-zaman ifadesinde propose_action sunulmaz."""
    session, u = db
    prov = ScriptedProvider(text="Anladım, gerçekleşince yaz.")
    CoachEngine(provider=prov).chat(session, u.id, "Yarın kredi kartı borcumu kapatacağım", include_cockpit=False)
    assert "propose_action" not in prov.received_tools


def test_gerceklesmis_eylem_propose_sunulur(db):
    session, u = db
    prov = ScriptedProvider(text="Tamamdır.")
    CoachEngine(provider=prov).chat(session, u.id, "Bugün 500 TL harcadım", include_cockpit=False)
    assert "propose_action" in prov.received_tools


# ============================================================
# Sahte tamamlama — uçtan uca temizlik (BUG #085 entegrasyon kilidi)
# ============================================================

def test_sahte_tamamlama_uctan_uca_temizlenir(db):
    """
    Gerçekleşmiş eylem bildirildi (propose sunuldu) ama LLM tool ÇAĞIRMADAN "kaydettim"
    dedi → hiçbir DB yazımı yok. chat() cevabı bu yanıltıcı iddiayı içermemeli, netleştirme
    sorusu eklemeli.
    """
    session, u = db
    prov = ScriptedProvider(text="Harcamanı kaydettim.", tool_calls=[])
    res = CoachEngine(provider=prov).chat(session, u.id, "500 TL harcadım", include_cockpit=False)
    assert res["proposed_actions"] == []
    assert "kaydettim" not in res["reply"].lower()
    assert _CLARIFY_MSG in res["reply"]


def test_cok_satirli_rapor_uctan_uca_bozulmaz(db):
    """BUG #085 iter2 entegrasyon: çok-satırlı analiz raporu (soru) mangle edilmez."""
    session, u = db
    report = "## KOKPİT\n- Maaşın hesaba geçirildi\n- 3 fatura işlendi\n## STRATEJİ\n- Bugün nöbet günü"
    prov = ScriptedProvider(text=report)
    res = CoachEngine(provider=prov).chat(session, u.id, "Durumu göster", include_cockpit=False)
    assert "## KOKPİT" in res["reply"]
    assert "## STRATEJİ" in res["reply"]
    assert _CLARIFY_MSG not in res["reply"]
