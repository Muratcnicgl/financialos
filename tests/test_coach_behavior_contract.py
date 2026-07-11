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


# ============================================================
# Grounding (LLM-003) — uçtan uca halüsinasyon yakalama
# ============================================================

def test_grounding_halusinasyon_uctan_uca(db):
    """Cockpit'te olmayan bir TL tutarı koç cevabında geçerse grounding.ok False."""
    session, u = db
    prov = ScriptedProvider(text="[CONFIDENCE: 0.9] Dikkat, 47.800 TL beklenmedik borç var.")
    res = CoachEngine(provider=prov).chat(session, u.id, "durum nedir?", include_cockpit=True)
    assert res["grounding"]["ok"] is False
    assert 47800.0 in res["grounding"]["unverified"]


# ============================================================
# propose_action happy-path — gerçekleşmiş eylemde pending oluşur
# ============================================================

def test_propose_action_happy_path_pending_olusur(db):
    session, u = db
    cash = session.query(Account).filter_by(
        user_id=u.id, account_type=AccountType.cash).first()
    prov = ScriptedProvider(text="500 TL yemek kaydediyorum.", tool_calls=[{
        "name": "propose_action",
        "input": {
            "action_type": "add_transaction",
            "payload": {"amount": 500, "transaction_type": "expense",
                        "account_id": cash.id, "category": "yemek"},
            "summary": "500 TL yemek",
        },
    }])
    # BUG #042 guard: gider mesajı hesap anahtar kelimesi içermeli ("nakitten")
    res = CoachEngine(provider=prov).chat(session, u.id, "500 TL yemek harcadım nakitten", include_cockpit=False)
    assert len(res["proposed_actions"]) == 1
    assert res["proposed_actions"][0]["action_type"] == "add_transaction"


# ============================================================
# account_unclear override (BUG #042) — gider hesabı belirsizse propose oluşmaz,
# koç net cevap yerine yönlendirme sorusu döner
# ============================================================

def test_hesap_belirsiz_override_soru_sorar(db):
    """
    Gider bildirildi ama hesap anahtar kelimesi yok → propose_action HESAP_BELIRSIZ
    fırlatır → account_unclear=True → pending oluşmaz, reply yönlendirme sorusudur.
    ScriptedProvider'ın verdiği net metin ("kaydettim") override edilir.
    """
    session, u = db
    cash = session.query(Account).filter_by(
        user_id=u.id, account_type=AccountType.cash).first()
    prov = ScriptedProvider(text="Harcamanı kaydettim.", tool_calls=[{
        "name": "propose_action",
        "input": {
            "action_type": "add_transaction",
            "payload": {"amount": 500, "transaction_type": "expense",
                        "account_id": cash.id, "category": "yemek"},
            "summary": "500 TL yemek",
        },
    }])
    # "500 harcadım" — hesap kelimesi (kart/nakit) YOK
    res = CoachEngine(provider=prov).chat(session, u.id, "500 TL yemek harcadım", include_cockpit=False)
    assert res["proposed_actions"] == []
    assert "Hangi hesaptan" in res["reply"]
    assert "kaydettim" not in res["reply"].lower()


# ============================================================
# save_insight tool path — LLM save_insight çağırırsa CoachInsight satırı yazılır
# ============================================================

def test_save_insight_kalici_hafizaya_yazar(db):
    """save_insight tool_call'u → CoachInsight satırı DB'ye upsert edilir."""
    from app.models import CoachInsight
    session, u = db
    prov = ScriptedProvider(text="Not aldım.", tool_calls=[{
        "name": "save_insight",
        "input": {
            "content": "Murat nöbet günleri yemek harcamasını artırıyor",
            "category": "davranis",
            "priority": "normal",
            "dedup_key": "nobet_yemek",
        },
    }])
    CoachEngine(provider=prov).chat(session, u.id, "Nöbet günleri daha çok yiyorum", include_cockpit=False)
    row = session.query(CoachInsight).filter_by(user_id=u.id, dedup_key="nobet_yemek").first()
    assert row is not None
    assert "nöbet" in row.content.lower()


# ============================================================
# Confidence marker — [CONFIDENCE: X] kullanıcıya sızmaz (strip edilir)
# ============================================================

def test_confidence_marker_kullaniciya_sizmaz(db):
    """LLM yanıtındaki [CONFIDENCE: 0.85] işareti reply'dan temizlenir."""
    session, u = db
    prov = ScriptedProvider(text="[CONFIDENCE: 0.85] Kart borcun kontrol altında.")
    res = CoachEngine(provider=prov).chat(session, u.id, "durum nedir?", include_cockpit=False)
    assert "CONFIDENCE" not in res["reply"]
    assert "[" not in res["reply"]
    assert "Kart borcun kontrol altında." in res["reply"]
