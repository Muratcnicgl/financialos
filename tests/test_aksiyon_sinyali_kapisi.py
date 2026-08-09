"""
BUG #273 KAPISI — iş kuralı sinyali METİNLE değil TİPLE taşınır (BE-006 + RESIL-019).

Ölçüm (düzeltmeden önce, gerçek koç akışı):
  · Dört sinyal × iki koç tüketicisi matrisinde **1 hücre yanlıştı**: retry yolu
    `TARIH_BELIRSIZ` dalını hiç taşımıyordu (ana akıştan elle kopyalanırken düşmüştü).
    Sonuç: işlem kaydedilmiyor VE kullanıcıya tarih sorusu sorulmuyordu — hata
    `logger.error("retry propose_action hatasi: ...")` olarak yutuluyordu.
  · Dört sinyalin dördü de ham kod hâliyle (`Belirsizlik: HESAP_BELIRSIZ`)
    `reasoning_traces.observation`'a yazılıyor ve `TracePanel.jsx` bunu kullanıcıya
    "Gözlem" satırı olarak RENDER EDİYORDU.
  · Sinyal ile teşhis metni aynı string olduğu için iki log satırı kullanıcının
    TUTARLARINI yazıyordu (`[3200.0] ile payload amount=320.0`) — BUG #180 ilkesi ihlali.

Bu kapı üç şeyi birden kilitler: (1) davranış matrisi, (2) sızıntı yokluğu,
(3) YAPI — bir tüketicinin bir sinyali "unutabilmesi" imkânsız olmalı.
"""
from __future__ import annotations

import ast
import inspect
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.action_errors import (
    AksiyonReddi,
    BilinmeyenAksiyon,
    HesapBelirsiz,
    OzetPayloadCeliskisi,
    PayloadGecersiz,
    TarihBelirsiz,
    en_oncelikli,
    sinyaller,
)
from app.coach import CoachEngine, LLMResponse
from app.models import Base, User, Account, AccountType, ReasoningTrace

APP = Path(__file__).resolve().parents[1] / "app"


# ============================================================
# 0. SÖZLEŞME — sinyal kümesi ve taşıdığı karar
# ============================================================

def test_her_sinyal_kararin_tamamini_tasir():
    """Kullanıcı mesajı, iz gerekçesi ve retry kararı SINIFIN üzerindedir; tüketicide değil."""
    kodlar = set()
    for sinif in sinyaller():
        assert sinif.kod and sinif.kod.isupper(), sinif
        assert sinif.kod not in kodlar, f"{sinif.kod} iki sınıfta"
        kodlar.add(sinif.kod)
        assert sinif.kullanici_mesaji.strip(), f"{sinif.kod}: kullanıcı mesajı yok"
        assert sinif.varsayilan_neden.strip(), f"{sinif.kod}: görünür gerekçe yok"
        assert sinif.iz_ciktisi.strip(), f"{sinif.kod}: iz etiketi yok"
        assert isinstance(sinif.kullanicidan_bilgi_ister, bool)
        assert issubclass(sinif, ValueError), "eski `except ValueError` çağıranlar kırılmamalı"


def test_kapsam_tabani_bes_sinyal(  ):
    """Kapsamsız kapı = ölü kapı: ölçülen sinyal kümesi daralırsa bu test kırmızıya döner."""
    kodlar = {s.kod for s in sinyaller()}
    assert {"HESAP_BELIRSIZ", "TARIH_BELIRSIZ", "PAYLOAD_GECERSIZ",
            "OZET_PAYLOAD_CELISKISI", "BILINMEYEN_AKSIYON"} <= kodlar


def test_tutar_str_e_ye_girmez():
    """KVKK/BUG #180: değer taşıyan teşhis `str(e)`ye SIZMAZ — dikkatsiz log bile para yazamaz."""
    red = OzetPayloadCeliskisi(teshis="ozetteki tutar(lar) [3200.0] ile payload amount=320.0")
    assert "3200" not in str(red) and "320" not in str(red)
    assert "3200" not in red.iz_gozlemi
    assert "3200.0" in red.teshis            # teşhis kaybolmaz, yalnız yer değiştirir
    assert str(red).startswith("OZET_PAYLOAD_CELISKISI:")


def test_iz_gozlemi_ic_kod_icermez():
    """Kullanıcı bunu ekranda okur: Türkçe gerekçe, büyük harfli iç sinyal adı DEĞİL."""
    for sinif in sinyaller():
        gozlem = sinif().iz_gozlemi
        assert sinif.kod not in gozlem, f"{sinif.kod} kullanıcıya görünen ize sızıyor"
        assert gozlem.strip()


def test_oncelik_once_kullanicidan_bilgi_ister():
    """İki ret aynı turda oluşursa önce kullanıcıdan bilgi isteyen sorulur."""
    secim = en_oncelikli([PayloadGecersiz(), HesapBelirsiz(), TarihBelirsiz()])
    assert isinstance(secim, HesapBelirsiz)
    assert en_oncelikli([]) is None
    assert HesapBelirsiz.kullanicidan_bilgi_ister and TarihBelirsiz.kullanicidan_bilgi_ister
    assert not PayloadGecersiz.kullanicidan_bilgi_ister


# ============================================================
# 1. YAPI — sinyal "unutulamaz" olmalı (AST kapıları)
# ============================================================

def _agac(yol: Path) -> ast.Module:
    return ast.parse(yol.read_text(encoding="utf-8"))


def test_hicbir_modul_karari_istisna_METNINE_bakarak_vermez():
    """`if "HESAP_BELIRSIZ" in str(e)` sınıfı YASAK (BE-006 kökü; BUG #269'un aynı hatası)."""
    ihlaller = []
    for yol in APP.rglob("*.py"):
        for d in ast.walk(_agac(yol)):
            if not isinstance(d, ast.Compare) or not d.ops:
                continue
            if not isinstance(d.ops[0], ast.In):
                continue
            if not (isinstance(d.left, ast.Constant) and isinstance(d.left.value, str)):
                continue
            for karsi in d.comparators:
                if (isinstance(karsi, ast.Call) and isinstance(karsi.func, ast.Name)
                        and karsi.func.id == "str"):
                    ihlaller.append(f"{yol.name}:{d.lineno}: {ast.unparse(d)}")
    assert not ihlaller, "istisna metnine bakan karar: " + "; ".join(ihlaller)


def test_propose_action_yalnizca_tipli_sinyal_firlatir():
    """Ham `raise ValueError("KOD")` geri gelirse tüketiciler yine metin taramaya döner."""
    kaynak = (APP / "action_executor.py").read_text(encoding="utf-8")
    fn = next(d for d in ast.walk(ast.parse(kaynak))
              if isinstance(d, ast.FunctionDef) and d.name == "propose_action")
    tipli = {s.__name__ for s in sinyaller()} | {"AksiyonReddi"}
    for d in ast.walk(fn):
        if isinstance(d, ast.Raise) and isinstance(d.exc, ast.Call):
            ad = getattr(d.exc.func, "id", getattr(d.exc.func, "attr", "?"))
            assert ad in tipli, f"propose_action:{d.lineno} tipsiz sinyal fırlatıyor: {ad}"


def test_her_propose_action_tuketicisi_ret_sinyalini_ele_alir():
    """`propose_action` çağıran her try bloğu `AksiyonReddi`yi ADIYLA yakalamalı.

    Bu, BUG #273'ün asıl dersidir: sinyal başına `if/elif` dalı yazılan bir tasarımda
    tüketici çoğaldıkça biri mutlaka bir dalı unutur. Tek base yakalanınca unutulacak
    dal kalmaz — kapı bunu YAPI olarak doğrular.
    """
    tuketiciler = []
    for yol in APP.rglob("*.py"):
        for d in ast.walk(_agac(yol)):
            if not isinstance(d, ast.Try):
                continue
            cagiriyor = any(
                isinstance(n, ast.Call)
                and getattr(n.func, "id", getattr(n.func, "attr", "")) == "propose_action"
                for n in ast.walk(d)
            )
            if not cagiriyor:
                continue
            adlar = set()
            for h in d.handlers:
                for t in (h.type.elts if isinstance(h.type, ast.Tuple) else [h.type]):
                    if t is not None:
                        adlar.add(getattr(t, "id", getattr(t, "attr", "")))
            tuketiciler.append((f"{yol.name}:{d.lineno}", adlar))
    assert tuketiciler, "propose_action tüketicisi bulunamadı — kapı körleşmiş"
    eksik = [yer for yer, adlar in tuketiciler if "AksiyonReddi" not in adlar]
    assert not eksik, f"ret sinyalini ele almayan tüketici: {eksik}"


def test_kullanici_mesajlari_koc_akisinda_ELLE_yazilmaz():
    """Kullanıcıya giden cümle tek kaynaktadır (H4/#256 dersi: kopya metin bayatlar).

    Tarama AST üzerindedir, ham metin üzerinde DEĞİL: kopya satıra bölünüp örtük
    birleştirmeyle yazıldığında (`"Hangi hesaptan? ..." "hemen kaydederim."`) metin araması
    onu göremiyordu — mutasyon kontrolünde kapının bu kör noktası ölçülerek bulundu.
    """
    sabitler = {
        " ".join(d.value.split())
        for d in ast.walk(_agac(APP / "coach.py"))
        if isinstance(d, ast.Constant) and isinstance(d.value, str)
    }
    for sinif in sinyaller():
        beklenen = " ".join(sinif.kullanici_mesaji.split())
        assert beklenen not in sabitler, f"{sinif.kod} mesajı coach.py'de kopyalanmış"


# ============================================================
# 2. DAVRANIŞ — sinyal × tüketici matrisi (uçtan uca, sağlayıcısız)
# ============================================================

class SiraliSaglayici:
    """Her `chat()` çağrısında sıradaki yanıt; liste biterse sonuncusunu tekrarlar."""
    NAME = "Sirali"
    model = "sirali-1"
    last_used_provider = "sirali"

    def __init__(self, yanitlar):
        self.yanitlar = yanitlar
        self.cagri = 0

    def chat(self, system_prompt, messages, tools):
        metin, tcs = self.yanitlar[min(self.cagri, len(self.yanitlar) - 1)]
        self.cagri += 1
        return LLMResponse(text=metin, tool_calls=list(tcs or []),
                           usage={"input_tokens": 10, "output_tokens": 5},
                           provider_used="sirali", model_name="sirali-1")


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="murat"))
    s.add(Account(id=1, user_id=1, name="Enpara", account_type=AccountType.cash, balance=5000.0))
    s.commit()
    yield s
    s.close()


def _tc(payload, ozet, tur="add_transaction"):
    return [{"name": "propose_action",
             "input": {"action_type": tur, "payload": payload, "summary": ozet}}]


_TEMEL = {"amount": 500, "transaction_type": "expense", "account_id": 1, "category": "yemek"}
#: (etiket, tool_call, kullanıcı mesajı, beklenen ret sınıfı)
VAKALAR = [
    ("hesap", _tc(_TEMEL, "500 TL yemek"), "500 TL yemek harcadim", HesapBelirsiz),
    ("tarih", _tc(_TEMEL, "3 Mayıs'ta 500 TL yemek"), "500 TL yemek harcadim kartla", TarihBelirsiz),
    ("payload", _tc({**_TEMEL, "amount": "uc yuz"}, "300 TL yemek"),
     "300 TL yemek harcadim kartla", PayloadGecersiz),
    ("ozet", _tc({**_TEMEL, "amount": 320}, "3.200 TL yemek harcaman"),
     "3200 TL yemek harcadim kartla", OzetPayloadCeliskisi),
    ("bilinmeyen", _tc(_TEMEL, "500 TL yemek", tur="ev_sat"),
     "500 TL yemek harcadim kartla", BilinmeyenAksiyon),
]

#: retry yolunu zorlayan ilk yanıt: tool YOK, metin "sahte niyet" değil.
_TOOLSUZ = ("Anladım, takipteyim.", [])


@pytest.mark.parametrize("etiket,tool_call,mesaj,sinif", VAKALAR)
def test_ana_akis_reddi_kullaniciya_dogru_cumleyle_doner(db, etiket, tool_call, mesaj, sinif):
    prov = SiraliSaglayici([("Kaydettim.", tool_call)])
    res = CoachEngine(provider=prov).chat(db, 1, mesaj, include_cockpit=False)
    assert res["proposed_actions"] == []
    assert res["reply"] == sinif.kullanici_mesaji
    assert "kaydettim" not in res["reply"].lower()


@pytest.mark.parametrize("etiket,tool_call,mesaj,sinif", VAKALAR)
def test_retry_akisi_ayni_sinyali_ayni_cumleyle_ele_alir(db, etiket, tool_call, mesaj, sinif):
    """ÖLÇÜLEN DEFEKT: retry yolu `TARIH_BELIRSIZ`i hiç ele almıyordu (kopya dal düşmüştü)."""
    prov = SiraliSaglayici([_TOOLSUZ, ("Kaydettim.", tool_call)])
    res = CoachEngine(provider=prov).chat(db, 1, mesaj, include_cockpit=False)
    assert prov.cagri == 2, "retry tetiklenmedi — vaka artık retry yolunu ölçmüyor"
    assert res["proposed_actions"] == []
    assert res["reply"] == sinif.kullanici_mesaji


def test_kullanicidan_bilgi_isteyen_ret_retry_ETTIRMEZ(db):
    """Aynı eksik bilgiyle modeli yeniden çağırmak aynı öneriyi ürettirir — sağlayıcı yakılmaz."""
    prov = SiraliSaglayici([("Kaydettim.", _tc(_TEMEL, "500 TL yemek"))])
    CoachEngine(provider=prov).chat(db, 1, "500 TL yemek harcadim", include_cockpit=False)
    assert prov.cagri == 1


def test_gecerli_oneri_hala_olusur(db):
    """Kapı yalnız ret yolunu değil, mutlu yolu da tutar (aksi halde 'her şeyi reddet' geçer)."""
    prov = SiraliSaglayici([("Kaydediyorum.", _tc(_TEMEL, "500 TL yemek"))])
    res = CoachEngine(provider=prov).chat(db, 1, "500 TL yemek harcadim nakitten",
                                          include_cockpit=False)
    assert len(res["proposed_actions"]) == 1


# ============================================================
# 3. SIZINTI — iz kaydı ve log
# ============================================================

@pytest.mark.parametrize("etiket,tool_call,mesaj,sinif", VAKALAR)
def test_iz_kaydinda_ic_kod_ve_tutar_bulunmaz(db, etiket, tool_call, mesaj, sinif, caplog):
    """`reasoning_traces.observation` kullanıcıya "Gözlem" satırı olarak RENDER EDİLİR."""
    with caplog.at_level(logging.DEBUG, logger="app.coach"):
        prov = SiraliSaglayici([("Kaydettim.", tool_call)])
        CoachEngine(provider=prov).chat(db, 1, mesaj, include_cockpit=False)

    gozlemler = [t.observation or "" for t in db.query(ReasoningTrace).all()]
    reddin_izi = [g for g in gozlemler if g.startswith("Öneri reddedildi")]
    assert reddin_izi, f"{etiket}: ret izi hiç yazılmamış"
    for g in gozlemler:
        assert sinif.kod not in g, f"{etiket}: iç sinyal kodu kullanıcıya görünen ize sızdı: {g}"
    # Tutar yalnız `set_action_input` ile yazılan ARAÇ GİRDİSİNDE olabilir (kullanıcının
    # kendi verisi, onun kendi izinde) — gerekçe/gözlem satırında olmamalı.
    for g in reddin_izi:
        assert "3200" not in g and "320.0" not in g

    kayitlar = " | ".join(r.getMessage() for r in caplog.records)
    assert "3200" not in kayitlar and "320.0" not in kayitlar, f"KVKK: tutar log'a düştü: {kayitlar}"


# ============================================================
# 4. RECURRING TÜKETİCİLER — atlanan kayıt SESSİZ kalmaz
# ============================================================

@pytest.fixture
def api(db):
    from app.main import app
    from app.dependencies import get_db, get_current_user
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="murat"))
    s.add(Account(id=1, user_id=1, name="Nakit", account_type=AccountType.cash, balance=10000))
    s.commit()
    app.dependency_overrides[get_db] = lambda: s
    app.dependency_overrides[get_current_user] = lambda: s.get(User, 1)
    try:
        yield TestClient(app), s
    finally:
        app.dependency_overrides.clear()
        s.close()


@pytest.mark.parametrize("uc,model_adi,ekstra", [
    ("/api/expenses/recurring/trigger-due", "RecurringExpense", {"account_id": 1}),
    ("/api/incomes/trigger-due", "RecurringIncome", {}),
])
def test_reddedilen_duzenli_kayit_cevapta_bildirilir(api, monkeypatch, uc, model_adi, ekstra):
    """Ölçüm: ret `logger.error`a düşüp `{"triggered": []}` dönüyordu — kullanıcı, kirasının
    önerilmediğini ancak ay sonunda bakiyesi tutmayınca fark ederdi (üstelik `last_triggered`
    yazılmadığı için her gün yeniden denenip her gün sessizce düşüyordu)."""
    import app.models as m
    client, s = api
    kayit = getattr(m, model_adi)(
        user_id=1, name="Kira", amount=1500, day_of_month=1, is_active=True, **ekstra)
    s.add(kayit)
    s.commit()

    monkeypatch.setattr("app.action_executor.propose_action",
                        lambda **kw: (_ for _ in ()).throw(HesapBelirsiz()))
    r = client.post(uc)
    assert r.status_code == 200, r.text
    govde = r.json()
    assert govde["triggered"] == []
    assert len(govde["atlanan"]) == 1, govde
    atlanan = govde["atlanan"][0]
    assert atlanan["ad"] == "Kira"
    assert atlanan["neden"] == HesapBelirsiz.kullanici_mesaji


def test_atlanan_alani_her_zaman_vardir(api):
    """Boş da olsa alan HEP döner — arayüz `?.atlanan || []` ile körleşmesin."""
    client, _ = api
    for uc in ("/api/expenses/recurring/trigger-due", "/api/incomes/trigger-due"):
        assert "atlanan" in client.post(uc).json(), uc


def test_koc_yardimcisi_tek_kaynaktir():
    """BE-005 kilidi: ana akış ile retry propose gövdesini KOPYALAMAZ, aynı metodu çağırır."""
    kaynak = inspect.getsource(CoachEngine.chat)
    assert kaynak.count("self._propose_tek_cagri(") == 2
    assert "propose_action(" not in kaynak, "propose_action gövdesi chat() içine geri kopyalanmış"
