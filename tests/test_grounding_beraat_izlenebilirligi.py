"""
BUG #324 KAPISI — BİR DEDEKTÖRÜN BERAATI, MAHKÛMİYETİ KADAR ÖLÇÜLMELİDİR.

K3 boyunca yalnız YANLIŞ MAHKÛMİYETLER sayıldı ve üçü de düzeltildi (#316 boşluklu
ayıraç, #321 izlenebilir etiketsiz, #322 dar izin listesi). **Yanlış BERAAT hiç
sayılmamıştı.** 3 Eylül 2026'da ölçüldü ve sonuç şuydu:

    Koç yazdı : "Nakit: 4.276 -> 3.536 TL"     (YANLIŞ; doğrusu 4.276 - 500 = 3.776)
    Dedektör  : 3.536 GEÇTİ    — alakasız `saglikli_borc_hedefi` = 3.600'e %1,78 uzaklıkta
                3.776 DÜŞERDİ  — hiçbir yaprağa yakın değil
Ertesi gün koç DOĞRU hesapladı ve `3.776` gerçekten düşürüldü: öngörü canlı doğrulandı.

Tesadüf yüzeyi ölçüldü (200.000 örneklem, 27 benzersiz yaprak): 100-20.000 aralığından
**rastgele** bir tutar, hiçbir dayanağı olmasa da **%10,7** olasılıkla "izlenebilir"
sayılıyor. Canlı kokpit çok daha zengin — yani beraat kararı üretimde daha da anlamsız.

**TOLERANS DARALTILMADI** ve bu bilinçli: `48.510,41`'i `48.510` diye yuvarlayan DOĞRU
cevabı düşürürdü (BUG #316'nın dersi). Yapılan şey, kararı DEĞİŞTİRMEK değil GEREKÇESİNİ
GÖRÜNÜR KILMAK: her doğrulanan tutar, hangi kokpit değerine ve YÜZDE KAÇ sapmayla denk
geldiğini artık raporluyor. Sıfır sapmalı bir eşleşme kanıttır; %1,78 sapmayla alakasız
bir alana denk gelmek ise tesadüf olabilir — ve ikisi arasındaki farkı ancak sayı yan yana
durunca görebiliriz.

Aynı ilke bugün üçüncü kez uygulanıyor: `uslup=-` (BUG #277), `grounded=-` (BUG #322 turu),
ve şimdi `grounded=+`. **Bir kapı, "geçti" derken de neden geçtiğini söylemelidir.**
"""
from __future__ import annotations

from app.grounding import check_grounding

COCKPIT = {
    "nakit_kasa": 4276.0,
    "kart_borcu": 11976.0,
    "kart_kullanim": {"saglikli_borc_hedefi": 3600.0},
}


def _dayanak(sonuc, tutar):
    """Raporlanan beraat gerekçesini bulur."""
    for d in sonuc["dogrulanan"]:
        if abs(d["tutar"] - tutar) < 0.01:
            return d
    return None


def test_TAM_eslesme_sifir_sapmayla_raporlanir():
    sonuc = check_grounding("Nakit kasan 4.276 TL.", COCKPIT)
    d = _dayanak(sonuc, 4276.0)
    assert d is not None, sonuc
    assert d["dayanak"] == 4276.0
    assert d["sapma_yuzde"] == 0.0


def test_OLCULEN_ZAYIF_BERAAT_gorunur_olur():
    """
    Canlı defektin ta kendisi: 3.536 yanlıştı ama 3.600'e denk gelip geçti.

    Kapı kararı DEĞİŞTİRMİYOR (hâlâ geçiyor) — ama artık *neden* geçtiği yazılı ve
    sapmanın sıfır olmadığı görülüyor.
    """
    sonuc = check_grounding("Nakit: 4.276 -> 3.536 TL", COCKPIT)
    assert sonuc["ok"] is True, "karar değişmemeli — yalnız gerekçe görünür oluyor"
    d = _dayanak(sonuc, 3536.0)
    assert d is not None, sonuc
    assert d["dayanak"] == 3600.0, d
    assert 1.5 < d["sapma_yuzde"] < 2.0, d


def test_DOGRU_olan_tutar_hala_dusuyor_bu_dedektorun_KUSURUDUR():
    """
    Aynı cevabın doğru hâli (3.776) izlenemez sayılıyor. Bu test bir ARIZAYI YAZIYA
    DÖKER, bir davranışı onaylamaz: türev sayıların bu dedektörle doğrulanamaması
    açık bir bulgudur ve `masterprompt-koc.md` §9.4'te kayıtlıdır.
    """
    sonuc = check_grounding("Nakit: 4.276 -> 3.776 TL", COCKPIT)
    assert sonuc["ok"] is False
    assert 3776.0 in sonuc["unverified"]


def test_dusen_tutar_dogrulananlar_listesine_GIRMEZ():
    sonuc = check_grounding("Hesabında 47.800 TL var.", COCKPIT)
    assert _dayanak(sonuc, 47800.0) is None, sonuc


def test_gerekce_EN_YAKIN_dayanagi_secer():
    """Birden çok yaprak tolerans içindeyse en yakını yazılır — yoksa gerekçe keyfi olur."""
    cockpit = {"a": 1000.0, "b": 1005.0}
    d = _dayanak(check_grounding("Tutar 1.004 TL.", cockpit), 1004.0)
    assert d["dayanak"] == 1005.0, d


def test_KULLANICI_beyanindan_gelen_dayanak_isaretlenir():
    """
    Kokpit'ten mi geldi, kullanıcının kendi sözünden mi — ikisi AYNI güçte kanıt değil.
    Kokpit deterministik motor çıktısıdır; kullanıcı beyanı doğrulanmamış bir iddiadır.
    """
    sonuc = check_grounding("Söylediğin 500 TL'lik harcamayı hesaba katıyorum.", COCKPIT,
                            gecmis_kullanici_mesajlari=["bugün 500 TL harcadım"])
    d = _dayanak(sonuc, 500.0)
    assert d is not None and d["kaynak"] == "kullanici", d


def test_kokpitten_gelen_dayanak_kokpit_diye_isaretlenir():
    d = _dayanak(check_grounding("Nakit kasan 4.276 TL.", COCKPIT), 4276.0)
    assert d["kaynak"] == "cockpit", d


# ---- ÖLÇÜM YOLUNA BAĞLANDI ------------------------------------------------
#
# Gerekçe yalnız `check_grounding`in dönüşünde durursa kimse görmez: eval dökümü
# koşumun tek kalıcı izidir ve sınıflandırma oradan yapılır (BUG #322 turunda düşüşler
# için yapılmıştı; beraatler için de aynısı gerekiyor).

def test_eval_dokumu_beraat_gerekcesini_TASIR():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models import Base, User, Account, AccountType
    from app.coach import CoachEngine, LLMResponse
    from app.coach_eval import EvalScenario, run_eval

    class _P:
        NAME = "Scripted"; model = "s"; last_used_provider = "s"

        def chat(self, system_prompt, messages, tools):
            return LLMResponse(text="Nakit kasan 5.000 TL.", tool_calls=[],
                               usage={"input_tokens": 1, "output_tokens": 1},
                               provider_used="s", model_name="s")

    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    db = sessionmaker(bind=eng)()
    db.add(User(id=1, name="m"))
    db.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=5000.0))
    db.commit()
    try:
        rapor = run_eval(CoachEngine(provider=_P()), db, 1,
                         [EvalScenario("analiz", "durumu göster", ["grounded"],
                                       include_cockpit=True)])
        detay = rapor["scenarios"][0]["grounding_detay"]
        assert detay["dogrulanan"], detay
        assert any(abs(d["tutar"] - 5000.0) < 0.01 for d in detay["dogrulanan"]), detay
    finally:
        db.close()
