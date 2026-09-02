"""
GETİRİ EŞİĞİ KAPISI (Wave-K / altın senaryo G4) — stopaj ve bileşiklendirme MODELDEN
beklenmez, kural motorunda hesaplanır.

ÖLÇÜLEN DEFEKT (2 Eyl 2026): koça "yıllık %35,5 brüt mevduat mı, krediye erken ödeme mi?"
soruldu. Koç **stopajı hiç anmadan** brüt yıllık oranı aylık kredi faiziyle kıyasladı ve
kredi oranını da yanlış söyledi (%4,25 — doğrusu %4,55). İki farklı birimdeki iki sayı,
aynı sayıymış gibi sunuldu; bu hatanın bedelini kullanıcı yanlış kararla öder.

Çözüm prompt'a yeni bir yasak eklemek DEĞİLDİ (K-KURAL 5: ölçüm yoksa prompt büyümez).
`docs/architecture.md`ın kendi ilkesi zaten cevabı söylüyordu: *Rules Engine karar verir,
LLM açıklar*. Aritmetik `app/vergi.py` + `rules_engine.calculate_getiri_esigi`e taşındı.

BU KAPININ ASIL İŞİ — "BİLİNMEYEN, SIFIR DEĞİLDİR" (L45):
Bir vergi modülünün en tehlikeli hatası, bilmediği oranı %0 sayıp **vergisiz getiri vaat
etmektir**. Aşağıdaki testlerin çoğu bu tek riski kuşatır: kaynağı olmayan ürün, sınır dışı
vade, bozuk `.env` override — hepsi `None` döner, hiçbiri sessizce sıfıra düşmez.
"""
from __future__ import annotations

from datetime import date

import pytest

from app import vergi
from app.models import Account, AccountType, Base, User
from app.rules_engine import calculate_getiri_esigi


# ---- 1) STOPAJ: bilinmeyen SIFIR değildir -------------------------------------

def test_kaynakli_oran_donuyor():
    assert vergi.stopaj_orani("try_mevduat_6ay") == 17.5
    assert vergi.stopaj_orani("try_para_piyasasi_fonu") == 17.5


def test_kaynaksiz_urun_icin_oran_uydurulmaz():
    for urun in ("doviz_mevduat", "hisse", "eurobond", ""):
        assert vergi.stopaj_orani(urun) is None, f"{urun}: uydurma oran döndü"


def test_sinir_disi_vade_icin_oran_uydurulmaz():
    """6 aylık dilimin oranını 2 yıllık mevduata uygulamak, bilmediğini bilmek değildir."""
    assert vergi.stopaj_orani("try_mevduat_6ay", 183) == 17.5      # sınırın tam üstünde değil
    assert vergi.stopaj_orani("try_mevduat_6ay", 184) is None
    assert vergi.stopaj_orani("try_mevduat_6ay", 730) is None
    # Fonda vade kavramı yok; vade verilmesi oranı düşürmemeli.
    assert vergi.stopaj_orani("try_para_piyasasi_fonu", 730) == 17.5


def test_bozuk_env_override_sessizce_sifira_dusmez(monkeypatch):
    """Bozuk bir override %0 stopaj demek olurdu — yani vergisiz getiri vaadi."""
    for bozuk in ("abc", "-5", "150", "# not"):
        monkeypatch.setenv("STOPAJ_TRY_MEVDUAT_6AY", bozuk)
        assert vergi.stopaj_orani("try_mevduat_6ay") == 17.5, f"{bozuk!r} kabul edildi"


def test_gecerli_env_override_uygulanir(monkeypatch):
    """Mevzuat değişince kod dağıtmadan düzeltilebilmeli."""
    monkeypatch.setenv("STOPAJ_TRY_MEVDUAT_6AY", "20")
    assert vergi.stopaj_orani("try_mevduat_6ay") == 20.0
    monkeypatch.setenv("STOPAJ_TRY_MEVDUAT_6AY", "22,5")   # TR ondalık virgülü
    assert vergi.stopaj_orani("try_mevduat_6ay") == 22.5


# ---- 2) DÖNÜŞÜM: 1 Eylül'de elle yapılan hesabın aynısı ------------------------

def test_net_ve_aylik_donusum_1_eylul_olcumuyle_ayni():
    """
    Çıta, 1 Eyl 2026'da insanın elle yaptığı hesap: brüt %35,5 → aylık net ~%2,4-2,5
    (§4.2 G4 kaydı: "Enpara %2,52-2,66" — o gün %37,5'lik ayın-enparalısı oranı da
    hesaba katılmıştı; buradaki %35,5 taban orandır).
    """
    net = vergi.net_yillik(35.5)
    assert net == pytest.approx(29.2875, abs=0.001)
    aylik = vergi.aylik_esdeger(net)
    assert 2.3 < aylik < 2.6, f"aylık eşdeğer beklenen aralıkta değil: {aylik}"


def test_bilesik_ve_basit_ayni_sayi_gibi_sunulmaz():
    net = vergi.net_yillik(35.5)
    assert vergi.aylik_esdeger(net, bilesik=True) != vergi.aylik_esdeger(net, bilesik=False)


def test_stopaj_bilinmiyorsa_net_de_bilinmiyor():
    assert vergi.net_yillik(35.5, "doviz_mevduat") is None
    k = vergi.mevduat_karsilastirmasi(35.5, date(2026, 9, 2), urun="doviz_mevduat")
    assert k["net_aylik"] is None and k["stopaj_yuzde"] is None
    assert k["neden"], "Bilinmeme SEBEBİ yazılmazsa koç 'bilmiyorum' diyemez"
    # Ama bilinen tek şey (kullanıcının söylediği brüt oran) yine de taşınır.
    assert k["brut_yillik"] == 35.5


# ---- 3) EŞİK: kararı tek sayıya indiren ters hesap -----------------------------

def test_esigi_asmak_icin_gereken_brut_dogru_yonde():
    """
    G4'ün asıl sorusuna tek sayılık cevap: aylık %4,75'lik krediyi geçmek için mevduatın
    brüt yıllık ~%68 vermesi gerekir. Kullanıcının eline geçen %35,5, bunun YARISI kadar —
    yani tartışma matematiksel olarak biter.
    """
    gereken = vergi.esigi_asmak_icin_gereken_brut(4.75)
    assert 60.0 < gereken < 80.0, gereken
    assert gereken > 35.5 * 1.5, "Eşik, gerçek teklifin çok üstünde olmalıydı"
    # Daha ucuz borç → daha düşük eşik (yön tutarlılığı).
    assert vergi.esigi_asmak_icin_gereken_brut(4.55) < gereken


def test_esik_tersine_cevrilebilir():
    """Ters hesap kendi kendini doğrular: gereken brütün aylık neti, eşiğe eşit olmalı."""
    esik = 4.75
    brut = vergi.esigi_asmak_icin_gereken_brut(esik)
    assert vergi.aylik_esdeger(vergi.net_yillik(brut)) == pytest.approx(esik, abs=0.02)


def test_stopaj_yoksa_esik_de_yok():
    assert vergi.esigi_asmak_icin_gereken_brut(4.75, urun="doviz_mevduat") is None
    assert vergi.esigi_asmak_icin_gereken_brut(0.0) is None


# ---- 4) TAZELİK: bayat oran sessizce taze sayılmaz -----------------------------

def test_bayatlik_isaretleniyor():
    taze = vergi.STOPAJ_YURURLUK
    assert vergi.bayat_mi(taze) is False
    assert vergi.bayat_mi(date(taze.year + 2, taze.month, taze.day)) is True


def test_gun_ZORUNLU_sunucudan_okunmaz():
    """
    `date.today()` yedeği bilerek YOK. Muafiyet işareti (`tz-exempt`) yazıp geçmek
    mümkündü; muafiyet tavanı kapısının sorduğu soru "bu muafiyet gerçekten gerekli mi?"
    idi ve cevap hayırdı — gün zaten `generate_cockpit(user_id, today, db)` zincirinde
    taşınıyor. Kaçış deliği açmaktansa parametreyi zorunlu kılmak, kullanıcının günüyle
    sunucununkinin bir daha karışmamasını garanti eder.
    """
    with pytest.raises(TypeError):
        vergi.bayat_mi()                      # type: ignore[call-arg]
    with pytest.raises(TypeError):
        vergi.mevduat_karsilastirmasi(35.5)   # type: ignore[call-arg]
    # Metin araması YETMEZ: docstring `date.today()` sözünü GEÇİRİYOR (ilk yazımda test
    # tam da kendi açıklamasını suçladı). Ölçüt AST olmalı — aranan şey kelime değil ÇAĞRI.
    import ast
    import pathlib
    agac = ast.parse(pathlib.Path(vergi.__file__).read_text(encoding="utf-8"))
    cagrilar = [d for d in ast.walk(agac)
                if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
                and d.func.attr == "today"]
    assert not cagrilar, f"vergi.py sunucu gününe düştü (satır {[c.lineno for c in cagrilar]})"


def test_bayat_oran_hesabi_DURDURMAZ_ama_isaretler():
    """Çalışmayı durdurmak kullanıcıya yardım etmez; sessizce güvenmek de doğru değil."""
    k = vergi.mevduat_karsilastirmasi(
        35.5, date(vergi.STOPAJ_YURURLUK.year + 2, 1, 1))
    assert k["net_aylik"] is not None
    assert k["bayat"] is True


# ---- 5) KURAL MOTORU: eşik gerçek borçtan türer --------------------------------

def _db(krediler, kart_orani=None):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="T"))
    for i, (borc, oran) in enumerate(krediler):
        s.add(Account(user_id=1, name=f"K{i}", account_type=AccountType.loan,
                      balance=borc, interest_rate=oran))
    if kart_orani is not None:
        s.add(Account(user_id=1, name="Kart", account_type=AccountType.credit_card,
                      balance=1000.0, interest_rate=kart_orani))
    s.commit()
    return s


def test_esik_EN_PAHALI_borcun_orani():
    db = _db([(10000.0, 4.55), (20000.0, 4.75)])
    try:
        r = calculate_getiri_esigi(1, db, date(2026, 9, 2))
    finally:
        db.close()
    assert r["esik_aylik_yuzde"] == 4.75, "Eşik en pahalı borç olmalı, en büyük borç değil"
    assert r["esik_kaynak"] == "K1"
    assert r["gereken_brut_yillik"] == pytest.approx(68.49, abs=0.1)


def test_kart_da_esige_girer():
    """Kart faizi kredilerden pahalıysa eşik odur — 'kredi' diye sınırlamak yanlış olurdu."""
    db = _db([(10000.0, 4.55)], kart_orani=9.0)
    try:
        r = calculate_getiri_esigi(1, db, date(2026, 9, 2))
    finally:
        db.close()
    assert r["esik_aylik_yuzde"] == 9.0 and r["esik_kaynak"] == "Kart"


def test_orani_bilinmeyen_borc_esigi_DUSURMEZ_ama_raporlanir():
    """Oransız kalemi 0 sayıp ortalamaya katmak, eşiği sahte biçimde düşürürdü."""
    db = _db([(10000.0, 4.55), (50000.0, None)])
    try:
        r = calculate_getiri_esigi(1, db, date(2026, 9, 2))
    finally:
        db.close()
    assert r["esik_aylik_yuzde"] == 4.55
    assert r["oransiz_kalem"] == 1, "Eksik veri görünmezse eşik 'düşük' sanılır"
    # MUTASYONUN BULDUĞU KÖR NOKTA: oransız kalem listeye %0 ile girerse eşik DEĞİŞMEZ
    # (sıralamada sona düşer) — yani eşiği kontrol eden testler bunu görmez. Ama liste koça
    # gidiyor: koç o borcu "faizsiz" sanır ve kullanıcıya öyle söyler. Bilinmeyen bir oranı
    # sıfır diye SUNMAK, onu sıfır SAYMAK kadar zararlıdır.
    assert [k["ad"] for k in r["kalemler"]] == ["K0"], "Oranı bilinmeyen borç listeye girdi"
    assert all(k["aylik_oran"] > 0 for k in r["kalemler"])


def test_borc_yoksa_esik_None_ve_sebebi_yazili():
    db = _db([])
    try:
        r = calculate_getiri_esigi(1, db, date(2026, 9, 2))
    finally:
        db.close()
    assert r["esik_aylik_yuzde"] is None and r["gereken_brut_yillik"] is None
    assert r["neden"]


def test_kapanmis_borc_esige_girmez():
    db = _db([(0.0, 12.0), (10000.0, 4.55)])
    try:
        r = calculate_getiri_esigi(1, db, date(2026, 9, 2))
    finally:
        db.close()
    assert r["esik_aylik_yuzde"] == 4.55, "Bakiyesi sıfır borç eşiği yükseltemez"


# ---- 6) KOÇA ULAŞIYOR MU: hesap yapıldı ama koç görmüyorsa boşuna --------------

def test_esik_kocun_baglamina_giriyor():
    """
    Hesabın var olması yetmez; koç okumuyorsa G4 yine düşer. Bu test, kural motoru ile
    koç arasındaki KABLOYU kilitler (BUG #256 sınıfı: hesap doğru, taşıma kopuk).
    """
    from app.coach import _build_context_message
    from scripts.coach_altin import altin_db
    db = altin_db()
    try:
        ctx, cockpit = _build_context_message(db, 1)
    finally:
        db.close()
    assert "getiri_esigi" in cockpit
    assert "GETİRİ EŞİĞİ" in ctx
    assert "68.49" in ctx, "Eşiği aşmak için gereken brüt oran bağlamda yok"
    assert "17.5" in ctx, "Stopaj oranı bağlamda yok — koç yine brütle netı kıyaslar"
