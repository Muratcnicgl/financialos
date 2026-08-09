"""
İki-geçiş "plan-sonra-yaz" deliberasyon mimarisi (kalite).

Analiz/soru yolunda koç önce GİZLİ iç plan üretir (tool'suz çağrı), sonra nihai cevabı bu
plana göre yazar → sentez garantisi + iç-jargon sızıntısına karşı yapısal savunma. Eylem-
bildirim yolunda (propose_action sunulan) plan-geçişi YAPILMAZ (tool akışı bozulmasın).
Rakamlar yine 2. geçişte bağlamdan üretilir → grounding bozulmaz (yeniden-yazma DEĞİL).
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, User, Account, AccountType
from app.coach import CoachEngine, LLMResponse


class RecordingProvider:
    """Her chat() çağrısını (system_prompt + sunulan tool'lar) kaydeder. Tool'suz çağrıyı
    'plan', tool'lu çağrıyı 'cevap' sayıp farklı metin döner."""
    NAME = "rec"
    model = "rec-1"
    last_used_provider = "rec"

    def __init__(self):
        self.calls = []

    def chat(self, system_prompt, messages, tools):
        self.calls.append({"sys": system_prompt,
                           "msgs": [dict(m) for m in messages],   # BUG #272
                           "tools": [t.get("name") for t in (tools or [])]})
        text = "PLAN: iç plan" if not tools else "Kullanıcıya giden cevap."
        return LLMResponse(
            text=text, tool_calls=[], usage={"input_tokens": 1, "output_tokens": 1},
            provider_used="rec", model_name="rec-1",
        )


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="murat"))
    s.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=5000.0))
    s.commit()
    yield s
    s.close()


def test_soru_yolunda_iki_gecis_plan_sonra_yaz(db):
    """Soru → önce plan (tool'suz) sonra cevap (tool'lu); plan 2. çağrının MESSAGES'ına eklenir (BUG #272: system sabit)."""
    eng = CoachEngine(provider=RecordingProvider())
    res = eng.chat(db, 1, "karta ne kadar ödeyeyim")
    calls = eng.provider.calls
    assert len(calls) == 2, "soru yolunda iki geçiş (plan + cevap) beklenir"
    assert calls[0]["tools"] == [], "1. çağrı plan → tool sunulmaz"
    # BUG #272: plan talimatı da üretilen plan da SİSTEM sözleşmesine değil `messages`
    # sonuna yazılır — sözleşme tur içinde sabittir (tests/test_sistem_sozlesmesi_kapisi.py).
    assert "İÇ PLAN ÜRET" in calls[0]["msgs"][-1]["content"], "1. çağrı plan talimatını içermeli"
    assert "İÇ PLAN" in calls[1]["msgs"][-1]["content"], "plan 2. çağrıya messages ile gitmeli"
    assert "PLAN: iç plan" in calls[1]["msgs"][-1]["content"], "üretilen plan metni taşınmalı"
    assert calls[0]["sys"] == calls[1]["sys"], "system prompt tur içinde değişti"
    # kullanıcıya giden metin cevap-geçişinin çıktısı, plan DEĞİL
    assert "PLAN" not in res.get("reply", "")


def test_plan_kullaniciya_sizmaz(db):
    """İç plan metni kullanıcıya dönen reply'de bulunmamalı (gizli kalmalı)."""
    eng = CoachEngine(provider=RecordingProvider())
    res = eng.chat(db, 1, "durumumu değerlendirir misin")
    assert "iç plan" not in res.get("reply", "").lower()


def test_eylem_bildiriminde_plan_gecisi_yok(db):
    """Gerçekleşmiş eylem bildiriminde (propose_action yolu) plan-geçişi YAPILMAZ → tek çağrı."""
    eng = CoachEngine(provider=RecordingProvider())
    eng.chat(db, 1, "bugün 320 TL market harcadım nakitten")
    # offer_propose=True → deliberasyon atlanır. İlk (ve genelde tek) çağrıda propose_action sunulur.
    calls = eng.provider.calls
    assert "propose_action" in calls[0]["tools"], "eylem yolunda ilk çağrı doğrudan tool'lu olmalı"
    # plan talimatı hiçbir çağrıda olmamalı
    # BUG #272: talimat artık messages'ta — kontrol her iki yüzeyi de kapsar
    assert all("İÇ PLAN ÜRET" not in c["sys"] for c in calls), "eylem yolunda plan-geçişi olmamalı"
    assert all("İÇ PLAN ÜRET" not in str(c["msgs"]) for c in calls), "eylem yolunda plan-geçişi olmamalı"


def test_plan_bos_donerse_cevap_yine_uretilir(db):
    """Robustluk: plan boş/başarısızsa tek-geçişe düşer, cevap yine üretilir (kilitlenme yok)."""
    class EmptyPlanProvider(RecordingProvider):
        def chat(self, system_prompt, messages, tools):
            self.calls.append({"sys": system_prompt, "tools": [t.get("name") for t in (tools or [])]})
            text = "" if not tools else "Cevap yine geldi."
            return LLMResponse(text=text, tool_calls=[], usage={"input_tokens": 1, "output_tokens": 1},
                               provider_used="rec", model_name="rec-1")

    eng = CoachEngine(provider=EmptyPlanProvider())
    res = eng.chat(db, 1, "borç durumumu anlat")
    # plan boş döndü → 2. çağrının promptuna plan enjekte EDİLMEMELİ
    assert "UYGULANACAK İÇ PLAN" not in eng.provider.calls[1]["sys"]
    assert res.get("reply")  # cevap yine üretildi
