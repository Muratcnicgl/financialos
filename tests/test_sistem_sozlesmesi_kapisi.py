"""
BUG #272 — YÖNLENDİRME, SİSTEM SÖZLEŞMESİNİN KENDİSİNİ DEĞİŞTİRİYORDU (LLM-021).

ÖLÇÜM (8 Ağu 2026, düzeltme ÖNCESİ — sağlayıcının gördüğü `system_prompt` kaydedilerek):

| Yol | Denemeler arası system_prompt | messages |
|---|---|---|
| `propose` retry'ı | **DEĞİŞİYOR** (`[RETRY: ...]` ekleniyor) | sabit (1 → 1) |
| soru retry'ı | değişmiyor ✅ | büyüyor (1 → 2) |
| iç plan (deliberasyon) | **ANA çağrının** system'i modelin O TURDA ürettiği plan metnini taşıyor (21.117 karakterin son 648'i her turda farklı) | sabit |

Yani aynı dosyada, bir çağrı arayla **iki farklı teknik** vardı ve doğrusu zaten oradaydı
(BUG #270 ile aynı sınıf: bir soruya iki cevap).

Gerekçe iki katmanlı ve İDDİA DEĞİL:
  (a) prefix eşleşmesiyle çalışan her cache, system değişince prefix'i baştan yazar —
      retry tam da en çok cache'lenmesi istenen ek çağrıdır. (Kazanç iddiası LLM-002'ye
      aittir ve orada ÖLÇÜLEMEDİĞİ için ertelendi; burada yapılan yapısal ön koşuldur.)
  (b) system prompt koçun YETKİ yüzeyidir (ADR-045/prompt_safety) — aynı turun iki
      çağrısında farklı olması, yetki metnini deterministik olmaktan çıkarır.

DEĞİŞMEZ: **bir `chat()` turundaki HER sağlayıcı çağrısı AYNI system prompt'u görür.**
Yönlendirme (retry nudge'ı, plan talimatı, üretilen plan) `messages` sonuna eklenir.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.coach import (
    _PLAN_MESAJ_BASI, _RETRY_NUDGE_PROPOSE, _RETRY_NUDGE_SORU, CoachEngine, LLMResponse,
)
from app.models import Account, AccountType, Base, User


class Kaydeden:
    """Gördüğü her (system_prompt, messages) çiftini kaydeden sağlayıcı."""

    NAME, model, last_used_provider = "Fake", "m", "fake"

    def __init__(self, metin: str = ""):
        self.cagrilar = []
        self._metin = metin

    def chat(self, system_prompt, messages, tools=None):
        self.cagrilar.append((system_prompt, [dict(m) for m in messages]))
        return LLMResponse(text=self._metin, tool_calls=[], usage={},
                           provider_used="fake", model_name="m")


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(User(id=1, name="sozlesme_test"))
    session.flush()
    session.add(Account(id=1, user_id=1, name="Kasa", account_type=AccountType.cash, balance=5000))
    session.commit()
    yield session
    session.close()


def _kos(db, mesaj, metin="", cockpit=False):
    s = Kaydeden(metin)
    CoachEngine(provider=s).chat(db, 1, mesaj, include_cockpit=cockpit)
    return s


# ============================================================
# 1) DEĞİŞMEZ — bir turdaki her çağrı AYNI system prompt'u görür
# ============================================================

@pytest.mark.parametrize("mesaj,cockpit", [
    ("320 TL market harcadım nakitten", False),   # propose retry yolu
    ("kart borcum ne kadar?", False),             # soru retry yolu
    ("kart borcum ne kadar?", True),              # iç plan yolu
])
def test_bir_turda_system_prompt_degismez(db, mesaj, cockpit):
    s = _kos(db, mesaj, metin="", cockpit=cockpit)
    assert len(s.cagrilar) >= 2, "bu senaryo iki cagri uretmeliydi"
    sistemler = {c[0] for c in s.cagrilar}
    assert len(sistemler) == 1, (
        f"{len(sistemler)} farkli system_prompt — yonlendirme sozlesmeye yazilmis"
    )


# ============================================================
# 2) YÖNLENDİRME messages'a EKLENİR (ve gerçekten gider)
# ============================================================

def test_propose_retry_nudge_messages_sonunda(db):
    s = _kos(db, "320 TL market harcadım nakitten", metin="")
    son_mesajlar = s.cagrilar[-1][1]
    assert son_mesajlar[-1] == _RETRY_NUDGE_PROPOSE
    assert len(son_mesajlar) == len(s.cagrilar[0][1]) + 1


def test_soru_retry_nudge_messages_sonunda(db):
    s = _kos(db, "kart borcum ne kadar?", metin="")
    son_mesajlar = s.cagrilar[-1][1]
    assert son_mesajlar[-1] == _RETRY_NUDGE_SORU


def test_plan_talimati_ve_plan_metni_messages_ile_gider(db):
    """Plan çağrısı talimatı, ana çağrı da ÜRETİLEN planı messages'tan alır."""
    s = _kos(db, "kart borcum ne kadar?", metin="Plan: once nakit bak.", cockpit=True)
    plan_cagrisi, ana_cagri = s.cagrilar[0], s.cagrilar[1]
    assert "İÇ PLAN ÜRET" in plan_cagrisi[1][-1]["content"], "plan talimati messages'ta degil"
    assert ana_cagri[1][-1]["content"].startswith(_PLAN_MESAJ_BASI), "uretilen plan messages'ta degil"
    assert "Plan: once nakit bak." in ana_cagri[1][-1]["content"]


def test_plan_metni_system_prompta_SIZMAZ(db):
    """Düzeltme öncesi ana çağrının system'i modelin ürettiği metni taşıyordu."""
    s = _kos(db, "kart borcum ne kadar?", metin="Plan: once nakit bak.", cockpit=True)
    for sistem, _msgs in s.cagrilar:
        assert "Plan: once nakit bak." not in sistem
        assert "İÇ PLAN" not in sistem


# ============================================================
# 3) DAVRANIŞ KORUNDU — retry hâlâ çalışıyor
# ============================================================

def test_soru_retry_bos_cevabi_doldurur(db):
    """İlk çağrı boş, retry doluysa kullanıcı metni GÖRÜR (BUG #049 davranışı)."""
    class IkinciDolu(Kaydeden):
        def chat(self, system_prompt, messages, tools=None):
            self.cagrilar.append((system_prompt, [dict(m) for m in messages]))
            metin = "" if len(self.cagrilar) == 1 else "Kart borcun 12.500 TL."
            return LLMResponse(text=metin, tool_calls=[], usage={},
                               provider_used="fake", model_name="m")

    s = IkinciDolu()
    cevap = CoachEngine(provider=s).chat(db, 1, "kart borcum ne kadar?", include_cockpit=False)
    assert "12.500" in cevap["reply"]
    assert len({c[0] for c in s.cagrilar}) == 1


# ============================================================
# 4) DRIFT KİLİDİ — system_prompt'a yönlendirme eklenemez (kaynaktan)
# ============================================================

def test_ilk_cagridan_SONRA_system_prompt_mutasyonu_yok():
    """Kaynak-türetimli drift kilidi (L26/L27).

    Kural, "system_prompt hiç değişmesin" DEĞİL: bağlam (cockpit, FEAT-032 canlı döviz
    bloğu) ilk çağrıdan ÖNCE kurulur ve bu meşrudur — bağlamın system'de olup olmaması
    ayrı bir iştir (LLM-002, ölçülemediği için ertelendi). Yasak olan, **ilk sağlayıcı
    çağrısından SONRA** sözleşmeyi değiştirmektir: o noktadan itibaren her mutasyon,
    aynı turun iki çağrısını farklı yetki metniyle koşturur.

    Bu kapı ilk kurulduğunda üçüncü bir yeri de gösterdi (`system_prompt += _mkt_block`);
    ölçüldü ve MEŞRU olduğu görüldü — çağrı öncesi bağlam. Kilit ona göre daraltıldı."""
    import inspect
    import re

    from app.coach import CoachEngine

    satirlar = inspect.getsource(CoachEngine.chat).splitlines()
    ilk_cagri = next((i for i, s in enumerate(satirlar) if "self.provider.chat(" in s), None)
    assert ilk_cagri is not None, "kapsam tabani coktu: chat() icinde saglayici cagrisi yok"

    mutasyon = re.compile(
        r'system_prompt\s*(?:\+=|=\s*(?:f?["\'].*\{system_prompt\}|system_prompt\s*\+))')
    kirik = [s.strip() for s in satirlar[ilk_cagri:] if mutasyon.search(s)]
    assert not kirik, f"ilk cagridan SONRA system_prompt mutasyonu: {kirik}"


def test_yonlendirme_mesajlari_tek_yerde():
    """Üç yönlendirme de modül seviyesinde tanımlı (kopyala-yapıştır ikinci cevap üretmesin)."""
    from app import coach

    for ad in ("_RETRY_NUDGE_PROPOSE", "_RETRY_NUDGE_SORU", "_PLAN_MESAJ_BASI"):
        assert hasattr(coach, ad), f"{ad} tek kaynakta degil"
    assert coach._RETRY_NUDGE_PROPOSE["role"] == "user"
    assert coach._RETRY_NUDGE_SORU["role"] == "user"
