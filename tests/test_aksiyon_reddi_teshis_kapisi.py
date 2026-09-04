"""
BUG #335 KAPISI — BİR RET SİNYALİ, SEBEBİNİ SÖYLEMİYORSA EYLEME GEÇİRİLEMEZ.

ÖLÇÜLEN DEFEKT (3 Eylül 2026, davranış seti, OpenRouter sabit, 3+3 koşum):
`action` kriteri 5/6 ↔ 3/6 dalgalandı. "Sağlayıcı gürültüsü" diye geçilecekken cevap
METİNLERİNE bakıldı ve gürültü çıkmadı — koç, kullanıcıdan ZATEN VERDİĞİ bilgiyi istiyor:

    kullanıcı: "240 TL market aldım kartla"
    koç      : "Tutarı rakamla ve hangi hesap olduğunu yazar mısın?"

Operatörün elindeki tek iz `propose_action reddedildi: PAYLOAD_GECERSIZ` idi — HANGİ
alanın düştüğü görünmüyordu. Oysa `AksiyonReddi` bunu taşımak için İKİ ayrı alana
bölünmüş (BUG #273 / ADR-052):
  · `gorunur_neden` — YALNIZ alan adları, geçersiz DEĞERİ içermez → loglanabilir
  · `teshis`        — değeri de yankılar → loglanmaz, persist edilmez (BUG #180)

Kapı iki şeyi birden kilitler ve ikisi AYRI testtir çünkü ayrı yönlerde bozulurlar:
teşhis loga GİRMELİ (körlük) ve değer loga GİRMEMELİ (KVKK sızıntısı).

Testler ürünün KENDİ çağrı yerini sürer (`CoachEngine.chat`), log satırını kendisi
kurmaz — kendi kurduğu satırı doğrulayan bir test vakumsal yeşildir.
"""
from __future__ import annotations

import logging

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.action_errors import PayloadGecersiz
from app.action_schema import dogrula
from app.models import Base, User, Account, AccountType
from app.coach import CoachEngine, LLMResponse


class _Scripted:
    NAME = "Scripted"; model = "scripted-1"; last_used_provider = "scripted"

    def __init__(self, text, tool_calls):
        self.text = text
        self.tool_calls = tool_calls

    def chat(self, system_prompt, messages, tools):
        return LLMResponse(text=self.text, tool_calls=list(self.tool_calls),
                           usage={"input_tokens": 1, "output_tokens": 1},
                           provider_used="scripted", model_name="scripted-1")


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    u = User(id=1, name="m")
    s.add(u)
    s.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=5000.0))
    s.commit()
    yield s, u
    s.close()


def _bozuk_cagri(hesap_id):
    # `amount` sözleşmeye uymuyor: geçersiz DEĞER kasten ayırt edici bir metin.
    return [{
        "name": "propose_action",
        "input": {
            "action_type": "add_transaction",
            "payload": {"amount": "UCYUZKIRK", "transaction_type": "expense",
                        "account_id": hesap_id, "category": "market"},
            "summary": "240 TL market",
        },
    }]


def test_gorunur_neden_ALAN_ADINI_tasir_DEGERI_TASIMAZ():
    """Sözleşmenin kendisi (birim): gerekçe alan adı verir, geçersiz değeri vermez."""
    with pytest.raises(PayloadGecersiz) as ex:
        dogrula("add_transaction", {"amount": "UCYUZKIRK", "transaction_type": "expense",
                                    "account_id": 1, "category": "market"})
    e = ex.value
    assert "amount" in e.gorunur_neden, e.gorunur_neden
    assert "UCYUZKIRK" not in e.gorunur_neden, (
        f"gorunur_neden geçersiz DEĞERİ yankılıyor (BUG #180): {e.gorunur_neden}")
    assert e.teshis, "teşhis alanı boş — iki alana bölmenin anlamı kalmaz"


def test_URUN_LOGU_hangi_alanin_dustugunu_YAZAR(db, caplog):
    """Uçtan uca: `chat()` reddi loglarken alan adını basmalı."""
    session, u = db
    hesap = session.query(Account).filter_by(user_id=u.id).first()
    prov = _Scripted("240 TL market kaydediyorum.", _bozuk_cagri(hesap.id))
    with caplog.at_level(logging.WARNING):
        CoachEngine(provider=prov).chat(session, u.id, "240 TL market aldım nakitten",
                                        include_cockpit=False)
    satirlar = [r.getMessage() for r in caplog.records
                if "propose_action reddedildi" in r.getMessage()]
    assert satirlar, "ret hiç loglanmadı"
    metin = " ".join(satirlar)
    assert "PAYLOAD_GECERSIZ" in metin
    assert "amount" in metin, (
        f"hangi alanın düştüğü log'da YOK — ret eyleme geçirilemez: {metin}")


def test_URUN_LOGU_gecersiz_DEGERI_SIZDIRMAZ(db, caplog):
    """
    Ters yön: teşhis loglanırsa kullanıcının verisi log'a sızar (BUG #180 / KVKK).

    MUTASYON BU TESTİ DÜZELTTİRDİ. İlk yazımda geçersiz `amount` kullanıyordum ve
    ölçünce görüldü ki pydantic o durumda DEĞERİ yankılamıyor ("Input should be a valid
    number") — yani test vakumsal yeşildi: `teshis`i loglayan mutasyon ondan KAÇIYORDU.
    Değeri gerçekten yankılayan vaka `transaction_date`: "Invalid isoformat string:
    '32 Mayis'". Bir sızıntı testi, gerçekten sızan bir girdiyle yazılmalıdır.
    """
    session, u = db
    hesap = session.query(Account).filter_by(user_id=u.id).first()
    prov = _Scripted("Kaydediyorum.", [{
        "name": "propose_action",
        "input": {
            "action_type": "add_transaction",
            "payload": {"amount": 340, "transaction_type": "expense",
                        "account_id": hesap.id, "category": "market",
                        "transaction_date": "32 Mayis"},
            "summary": "340 TL market",
        },
    }])
    with caplog.at_level(logging.WARNING):
        CoachEngine(provider=prov).chat(session, u.id, "340 TL market aldım nakitten",
                                        include_cockpit=False)
    assert "transaction_date" in caplog.text, "hangi alanın düştüğü log'da yok"
    assert "32 Mayis" not in caplog.text,         "geçersiz DEĞER log'a sızdı — `teshis` loglanıyor olmalı (BUG #180)"


# ---- BUG #336: RETRY, NEDEN REDDEDİLDİĞİNİ BİLMELİ -----------------------

def test_RETRY_reddin_SEBEBINI_modele_soyler(db):
    """
    Ölçülen defekt (canlı, 4 Eyl 2026): model `transaction_type`'ı bazen HİÇ göndermiyor
    (`None`) ve öneri düşüyor; ikinci deneme aynı GENEL yönlendirmeyi alıyordu
    ("propose_action çağırman gerekiyor") — yani hatayı bilmeden tekrar deniyordu.
    `gorunur_neden` eksik ALAN ADINI taşıyor ve para içermiyor; modele verilebilir.
    """
    session, u = db
    hesap = session.query(Account).filter_by(user_id=u.id).first()
    bozuk = {"name": "propose_action", "input": {
        "action_type": "add_transaction",
        "payload": {"amount": 240, "account_id": hesap.id, "category": "market"},
        "summary": "240 TL market"}}          # transaction_type YOK — ölçülen gerçek hata

    gorulen = []

    class _Sirali:
        NAME = "S"; model = "s"; last_used_provider = "s"

        def __init__(self):
            self.n = 0

        def chat(self, system_prompt, messages, tools):
            self.n += 1
            gorulen.append("\n".join((m.get("content") or "") for m in messages))
            tc = [bozuk] if self.n == 1 else []
            return LLMResponse(text="Kaydediyorum.", tool_calls=tc,
                               usage={"input_tokens": 1, "output_tokens": 1},
                               provider_used="s", model_name="s")

    CoachEngine(provider=_Sirali()).chat(session, u.id, "240 TL market aldım nakitten",
                                         include_cockpit=False)
    assert len(gorulen) >= 2, "retry hiç tetiklenmedi"
    assert "transaction_type" in gorulen[-1], \
        "retry, hangi alanın eksik olduğunu modele söylemiyor — aynı hatayı tekrarlar"


def test_RETRY_nudge_SABITI_KIRLENMEZ(db):
    """
    Modül seviyesindeki `_RETRY_NUDGE_PROPOSE` bir SABİTTİR. Üzerine yazmak, bir turun
    ret sebebini SONRAKİ turlara sızdırırdı — süreç ömrü boyunca büyüyen bir yönlendirme.
    (BUG #272'nin sınıfı: yönlendirme sözleşmeyi kirletmemeli.)
    """
    from app.coach import _RETRY_NUDGE_PROPOSE
    onceki = _RETRY_NUDGE_PROPOSE["content"]
    session, u = db
    hesap = session.query(Account).filter_by(user_id=u.id).first()
    prov = _Scripted("Kaydediyorum.", [{
        "name": "propose_action", "input": {
            "action_type": "add_transaction",
            "payload": {"amount": 240, "account_id": hesap.id, "category": "market"},
            "summary": "240 TL market"}}])
    CoachEngine(provider=prov).chat(session, u.id, "240 TL market aldım nakitten",
                                    include_cockpit=False)
    assert _RETRY_NUDGE_PROPOSE["content"] == onceki, "sabit kirlendi"


#: MUTASYON KAYDI (dürüst):
#:  M1 sebebi nudge'a ekleme            -> yakalandı
#:  M2 sabiti kopyalamadan değiştir     -> yakalandı
#:  M3 modele `gorunur_neden` yerine `teshis` gönder -> HAYATTA KALDI, **EŞDEĞER MUTANT**:
#:     `teshis` geçersiz DEĞERİ taşıyabilir, ama o değer ZATEN modele gidiyor (kokpit
#:     bağlamı kullanıcının bütün tutarlarını içeriyor) — yani yeni bir sızıntı yüzeyi
#:     doğmuyor. Gizlilik farkı LOG tarafındadır ve orası ayrıca test edilmiştir
#:     (`test_URUN_LOGU_gecersiz_DEGERI_SIZDIRMAZ`). `gorunur_neden` yine de tercih
#:     edilir: ADR-052'nin "karar TİPTE, teşhis ayrı alanda" ayrımını bulandırmamak için.
