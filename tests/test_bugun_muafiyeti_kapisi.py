"""
BUG #323 KAPISI — "BUGÜN", KORUMANIN YANLIŞ OLAMAYACAĞI TEK TARİH İFADESİDİR.

ÖLÇÜLEN DEFEKT (3 Eylül 2026, davranış seti, OpenRouter sabit; 6 denemenin 1'inde):
    kullanıcı: "Bugün 500 TL yemek harcadım nakitten"
    koç      : "Tarih bilgisi tutarsız. Tarihi açıkça belirt ('3 Mayıs'ta' gibi) veya
                hiç yazma — tarih yoksa bugün olarak kaydederim."
Harcama KAYDEDİLMEDİ. Kullanıcı tarihi zaten yazmıştı ("Bugün") ve reddin kendi mesajı
"tarih yoksa bugün olarak kaydederim" diyordu — yani ürün, söylediği şeyi yapmayı
reddetti.

KÖK NEDEN: BUG #044 koruması "özette tarih ifadesi VAR ama payload'da `transaction_date`
YOK" durumunu reddeder. Amacı sessiz bir yanlış gün yazımını önlemektir (özet "3 Mayıs"
der, payload boştur, kayıt BUGÜNE düşer → kalıcı olarak yanlış gün). `bugun` kelimesi
`_DATE_KEYWORD_RE`'de olduğu için koç kullanıcının "Bugün"ünü özete yankıladığında koruma
tetikleniyordu — **oysa yedek değer (bugün) tam olarak özetin söylediği gündür; sessiz
hata bu durumda İMKÂNSIZDIR.** Ürün, koçu kullanıcının kelimesini tekrar ettiği için
cezalandırıyordu.

MEŞRULUK SINAMASI (gevşetmeden önce): bu muafiyet, korumanın yakaladığı defekti kaçırır mı?
  · HAYIR. Muafiyet yalnız özetteki TEK tarih ifadesi "bugün" iken geçerlidir.
  · "3 Mayıs'ta" → koruma çalışır (test).
  · "dün" → çalışır; dün ≠ bugün, yedek değer yanlış olurdu (test).
  · "bugün ve dün" → çalışır; ikinci ifade hâlâ görülür (test).
DEDEKTÖRÜN SÖZLEŞMESİ DEĞİŞMEZ: `_tarih_ifadesi_var_mi("bugun")` hâlâ True döner —
"tarih ifadesi var mı" sorusunun cevabı evettir; değişen, KORUMANIN o cevabı nasıl
kullandığıdır. Muafiyet, gerekçesinin geçerli olduğu yerde durur.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.action_executor import _tarih_ifadesi_var_mi
from app.action_errors import TarihBelirsiz
from app.coach import CoachEngine, LLMResponse
from app.models import Base, User, Account, AccountType


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
    s.add(User(id=1, name="m"))
    s.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=5000.0))
    s.commit()
    yield s
    s.close()


def _cagri(hesap_id, summary, tarih=None):
    payload = {"amount": 500, "transaction_type": "expense",
               "account_id": hesap_id, "category": "yemek"}
    if tarih:
        payload["transaction_date"] = tarih
    return [{"name": "propose_action",
             "input": {"action_type": "add_transaction", "payload": payload,
                       "summary": summary}}]


def _kos(db, summary, tarih=None, mesaj="Bugün 500 TL yemek harcadım nakitten"):
    hesap = db.query(Account).first()
    prov = _Scripted("Kaydetmek için hazırladım.", _cagri(hesap.id, summary, tarih))
    return CoachEngine(provider=prov).chat(db, 1, mesaj, include_cockpit=False)


def test_BUGUN_tek_basina_reddi_TETIKLEMEZ(db):
    res = _kos(db, "Bugün 500 TL yemek harcaman")
    assert len(res["proposed_actions"]) == 1, (
        f"'bugün' yüzünden reddedildi — yedek değer zaten bugün: {res['reply'][:120]}")


def test_BASKA_bir_tarih_ifadesi_reddi_HALA_TETIKLER(db):
    # Korumanın asıl amacı: sessizce YANLIŞ güne yazılmasın.
    res = _kos(db, "3 Mayıs'ta 500 TL yemek harcaman",
               mesaj="3 Mayıs'ta 500 TL yemek harcadım nakitten")
    assert res["proposed_actions"] == []
    assert "Tarih" in res["reply"]


def test_DUN_reddi_HALA_TETIKLER(db):
    # dün != bugün → yedek değer yanlış olurdu.
    res = _kos(db, "Dün 500 TL yemek harcaman",
               mesaj="Dün 500 TL yemek harcadım nakitten")
    assert res["proposed_actions"] == []


def test_BUGUN_ve_BASKA_ifade_birlikteyse_reddi_TETIKLER(db):
    # Muafiyet yalnız TEK ifade "bugün" iken geçerli — ikincisi hâlâ görülür.
    res = _kos(db, "Dün değil bugün 500 TL yemek harcaman",
               mesaj="Dün değil bugün 500 TL yemek harcadım nakitten")
    assert res["proposed_actions"] == []


def test_BUGUN_ve_payloadda_tarih_varsa_zaten_sorun_yok(db):
    res = _kos(db, "Bugün 500 TL yemek harcaman", tarih="2026-09-03")
    assert len(res["proposed_actions"]) == 1


def test_DEDEKTORUN_SOZLESMESI_DEGISMEDI():
    # "tarih ifadesi var mı" sorusunun cevabı hâlâ EVET; değişen, korumanın onu
    # nasıl kullandığı. Dedektörü zayıflatmak başka bir çağıranı sessizce körleştirirdi.
    assert _tarih_ifadesi_var_mi("bugun 500 tl") is True
    assert _tarih_ifadesi_var_mi("bugün 500 TL") is True
    assert _tarih_ifadesi_var_mi("500 tl yemek") is False


def test_TarihBelirsiz_hala_kullanilabilir_bir_sinyal():
    # Sinyalin kendisi kaldırılmadı — yalnız bir dalı daraltıldı.
    assert TarihBelirsiz().kod == "TARIH_BELIRSIZ"


# ---- MUTASYONUN YAZDIRDIĞI TEST -------------------------------------------
#
# `payload.get("transaction_date")` erken-dönüşünü SİLEN mutasyon 194 testten kaçtı.
# Sebebi: mevcut testlerin hepsinde ya payload'da tarih yoktu ya da özetteki tek ifade
# "bugün"dü — yani erken dönüşün TEK BAŞINA belirleyici olduğu hücre hiç ölçülmemişti.
# O hücre en değerli olanı: kullanıcı tarihi söyledi, koç payload'a DOĞRU yazdı. Böyle
# bir öneri reddedilirse ürün, kusursuz çalıştığı anda kullanıcıyı geri çevirir.

def test_OZETTE_baska_tarih_VE_payloadda_tarih_varsa_reddedilmez(db):
    """Tam ve tutarlı öneri: özet '3 Mayıs' der, payload da 3 Mayıs'ı taşır."""
    res = _kos(db, "3 Mayıs'ta 500 TL yemek harcaman", tarih="2026-05-03",
               mesaj="3 Mayıs'ta 500 TL yemek harcadım nakitten")
    assert len(res["proposed_actions"]) == 1, (
        f"tarihi DOĞRU yazılmış öneri reddedildi: {res['reply'][:120]}")


#: MUTASYON KAYDI (dürüst): 4 mutasyonun 3'ü yakalandı.
#:  M1 muafiyeti kaldır (eski davranış)          -> yakalandı
#:  M2 korumayı tamamen kapat                    -> yakalandı (6 test)
#:  M3 `\bbugun\b` -> `bugun` (kelime sınırı yok) -> HAYATTA KALDI, **EŞDEĞER MUTANT**:
#:     `_DATE_KEYWORD_RE` de `bugun`u `\b` ile arar, yani "bugunku" gibi bir kelime iki
#:     yolda da tarih ifadesi SAYILMAZ; çıkarma işleminin sınırlı olup olmaması ulaşılabilir
#:     hiçbir girdide sonucu değiştirmiyor. Kelime sınırı yine de YAZILI kalıyor: desen
#:     ileride gevşerse (ör. `bugun\w*` eklenirse) sessizce ayrışmasınlar.
#:  M4 payload'daki tarihin erken dönüşünü sil    -> önce KAÇTI, testi o yazdırdı
