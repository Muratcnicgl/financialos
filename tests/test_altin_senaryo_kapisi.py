"""
ALTIN SENARYO KAPISI — ölçütün KENDİSİNİ doğrular (Wave-K, K-B).

NEDEN BU TESTLER VAR (BUG #316'nın dersi): bir zorlama/ölçüm, ancak ÖLÇÜTÜ kadar iyidir.
Grounding dedektörü aylarca DOĞRU cevapları halüsinasyon damgasıyla düşürdü ve kimse fark
etmedi, çünkü dedektörün kendisi hiç sınanmamıştı. Altın senaryo seti aynı tuzağa daha
açıktır: koçun MUHAKEMESİNİ ölçtüğünü iddia eder. Bu yüzden set kullanılmadan ÖNCE, ölçütün
iki yönü de kanıtlanır:
  * İNSAN ALTIN CEVABI (1 Eyl'de fiilen verilen analizin özü) → geçer.
  * O senaryonun BİLİNEN YANLIŞ muhakemesi → düşer, hem de DOĞRU kriterden.
Bunlar sağlanmazsa altın setin ürettiği her oran anlamsızdır.
"""
from __future__ import annotations

import pytest

from scripts.coach_altin import (ALTIN_SENARYOLAR, EYLUL_KAYNAK, EYLUL_ZORUNLU_CIKIS,
                             KART_GUNCEL_BORC, KREDI1_ERKEN_KAPAMA,
                             KREDI1_KALAN_TAKSIT_TOPLAMI, KREDI2_ERKEN_KAPAMA,
                             KREDI2_KALAN_TAKSIT_TOPLAMI, KREDI_TOPLAM_TAKSIT_TOPLAMI,
                             KYK_ODEMESI, altin_db)
from app.coach_eval import ALTIN_KRITERLER, EvalScenario, score_result
from app.models import Account, AccountType

SENARYO = {s.name: s for s in ALTIN_SENARYOLAR}


def _puan(ad: str, cevap: str, kriter: str) -> bool:
    sc = SENARYO[ad]
    res = {"reply": cevap, "proposed_actions": [], "grounding": {"ok": True}}
    return score_result(res, [kriter], senaryo=sc)[kriter]


# ---- 1) FIXTURE SADAKATİ: manzara canlı okumayla tutarlı mı --------------------
# Fixture "gerçek manzara" iddiasında; iddia sayısal olarak kilitlenmezse bir gün biri
# bakiyeyi değiştirir ve set sessizce BAŞKA bir manzarayı ölçmeye başlar.

def test_fixture_nakit_toplami_eylul_kaynagiyla_tutarli():
    db = altin_db()
    try:
        nakit = sum(
            float(a.balance) for a in db.query(Account).filter(
                Account.account_type.in_([AccountType.cash, AccountType.investment])))
    finally:
        db.close()
    assert round(nakit + KYK_ODEMESI, 2) == EYLUL_KAYNAK, (
        f"Fixture nakidi ({nakit}) + KYK ({KYK_ODEMESI}) canlı okunan Eylül kaynağını "
        f"({EYLUL_KAYNAK}) vermiyor — manzara kaymış.")


def test_fixture_zorunlu_cikis_toplami_tutarli():
    db = altin_db()
    try:
        taksitler = sum(float(a.monthly_payment) for a in db.query(Account)
                        .filter(Account.account_type == AccountType.loan))
        kart = float(db.query(Account).filter(
            Account.account_type == AccountType.credit_card).one().balance)
    finally:
        db.close()
    assert round(taksitler + kart, 2) == EYLUL_ZORUNLU_CIKIS
    assert kart == KART_GUNCEL_BORC


def test_fixture_kredi_bakiyeleri_tuzagi_tasiyor():
    """G1'in tuzağı fixture'da GERÇEKTEN var mı: balance ≠ erken kapama."""
    db = altin_db()
    try:
        krediler = {a.name: a for a in db.query(Account)
                    .filter(Account.account_type == AccountType.loan)}
        assert float(krediler["Garanti Kredi 1"].balance) == KREDI1_KALAN_TAKSIT_TOPLAMI
        assert float(krediler["Garanti Kredi 2"].balance) == KREDI2_KALAN_TAKSIT_TOPLAMI
        # BUG #318 SONRASI: anapara artık SAYISAL alanda. Önceden `notes` içinde METİNDİ
        # ve doğru cevap cockpit'te bulunamadığı için "izlenemeyen tutar" damgası yiyordu.
        assert float(krediler["Garanti Kredi 1"].early_payoff_amount) == KREDI1_ERKEN_KAPAMA
        assert float(krediler["Garanti Kredi 2"].early_payoff_amount) == KREDI2_ERKEN_KAPAMA
        # Ve tutar artık serbest metinde TUTULMAZ: iki kaynak olursa biri bayatlar.
        for k in krediler.values():
            assert "Erken Kapama" not in (k.notes or ""),                 "kapama tutarı hem alanda hem notes'ta — ikinci kaynak bayatlar"
    finally:
        db.close()
    assert round(KREDI1_KALAN_TAKSIT_TOPLAMI + KREDI2_KALAN_TAKSIT_TOPLAMI, 2) == \
        KREDI_TOPLAM_TAKSIT_TOPLAMI
    assert KREDI1_ERKEN_KAPAMA < KREDI1_KALAN_TAKSIT_TOPLAMI
    assert KREDI2_ERKEN_KAPAMA < KREDI2_KALAN_TAKSIT_TOPLAMI


# ---- 2) İNSAN ALTIN CEVABI GEÇER ----------------------------------------------
# 1 Eylül analizinin özü. Ölçüt bunları düşürüyorsa ölçüt yanlıştır.

ALTIN_CEVAPLAR = {
    "G1_kredi_anapara_vs_taksit_toplami":
        "## Kredi kapama\n"
        "Garanti Kredi 1'in erken kapama tutarı 14.023,29 TL, Garanti Kredi 2'nin "
        "34.487,12 TL. Ekranda gördüğün 16.439,65 ve 63.186,20 kalan taksit toplamıdır, "
        "gelecek faizi de içerir; bugün kapatırsan anaparayı ödersin.",
    "G2_kart_guncel_borc_yukumluluktur":
        "Evet. Son ekstreden kalan 0 görünüyor ama dönem içi güncel borcun 8.221,13 TL ve "
        "14 Eylül'de ödenecek.",
    "G3_ay_ici_nakit_takvimi":
        "## Eylül takvimi\nKaynağın 15.663,59 TL (11.663,59 nakit + 8 Eylül KYK 4.000). "
        "Zorunlu çıkış 15.078,25 TL: 11 Eylül 4.109,90 · 14 Eylül 8.221,13 · "
        "15 Eylül 2.747,22. Geriye 585,34 TL kalıyor.",
    "G4_getiri_ile_borc_ayni_birimde":
        "Brüt %35,5'in stopajı %17,5; net yıllık %29,3, aylık yaklaşık %2,5. Kredilerinin "
        "aylık faizi %4,75 ve %4,55 — yani borcu azaltmak mevduattan daha çok kazandırır.",
    "G5_cerceveyi_duzeltmek":
        "O paranın sahibi belli: 14 Eylül'de 8.221,13 TL kart ödemen var. Bir haftalık fon "
        "getirisi bu ödemeyi kaçırmanın bedelini karşılamaz.",
    "G6_asil_kaldirac":
        "Ayın en büyük tek kalemi kart harcaman: 8.221,13 TL. Yatırım tartışmasının ölçeği "
        "bunun yanında küçük kalıyor; asıl kaldıraç burada.",
}


@pytest.mark.parametrize("ad", sorted(ALTIN_CEVAPLAR))
def test_insan_altin_cevabi_dogru_sonuc_gecer(ad):
    assert _puan(ad, ALTIN_CEVAPLAR[ad], "dogru_sonuc") is True, (
        f"{ad}: insanın verdiği doğru cevap ölçütten DÜŞTÜ — ölçüt yanlış.")


def test_altin_cevap_tuzagi_da_soylese_gecer():
    """
    ŞARTLI TUZAK KURALI. G1'in altın cevabı tuzak tutarları (16.439,65 / 63.186,20) BİLEREK
    söyler — çünkü en iyi cevap ikisini KARŞILAŞTIRIR. Koşulsuz bir tuzak yasağı tam olarak
    bu en iyi cevabı düşürürdü (BUG #316 sınıfı hata).
    """
    ad = "G1_kredi_anapara_vs_taksit_toplami"
    assert _puan(ad, ALTIN_CEVAPLAR[ad], "tuzak_yok") is True


# ---- 3) BİLİNEN YANLIŞ MUHAKEME DÜŞER -----------------------------------------

YANLIS_CEVAPLAR = {
    "G1_kredi_anapara_vs_taksit_toplami":
        "Toplam kredi borcun 79.625,85 TL. Kapatmak için bu tutarı ödemen gerekiyor.",
    "G2_kart_guncel_borc_yukumluluktur":
        "Kartında ödenecek bir borç görünmüyor, bu ay karta ödeme yapmana gerek yok.",
    "G3_ay_ici_nakit_takvimi":
        "Gelirin giderini karşılıyor, Eylül'de sıkıntı yaşamazsın.",
    "G4_getiri_ile_borc_ayni_birimde":
        "Enpara %35,5 veriyor, bu oldukça iyi bir oran. Birikime koymanı öneririm.",
    "G5_cerceveyi_duzeltmek":
        "Bir haftada yaklaşık 61,50 TL kazanırsın.",
    "G6_asil_kaldirac":
        "Bu ay fena gitmiyorsun, harcamalarına dikkat etmeye devam et.",
}


@pytest.mark.parametrize("ad", sorted(YANLIS_CEVAPLAR))
def test_yanlis_muhakeme_dogru_sonuctan_duser(ad):
    assert _puan(ad, YANLIS_CEVAPLAR[ad], "dogru_sonuc") is False, (
        f"{ad}: bilinen yanlış cevap ölçütten GEÇTİ — ölçüt kör.")


def test_tuzaga_dusen_cevap_tuzak_yoktan_duser():
    ad = "G1_kredi_anapara_vs_taksit_toplami"
    assert _puan(ad, YANLIS_CEVAPLAR[ad], "tuzak_yok") is False


def test_ne_dogru_ne_tuzak_soyleyen_cevap_tuzak_yoktan_gecer():
    """`tuzak_yok`, `dogru_sonuc`un kopyası DEĞİLDİR: ikisi farklı arızayı ayırt eder.
    Konuyu hiç açmayan cevap yanlış muhakeme yapmamıştır; eksikliği `dogru_sonuc` söyler."""
    ad = "G1_kredi_anapara_vs_taksit_toplami"
    cevap = "Kredilerini kapatma konusunu birlikte bakalım, önce bir hesap çıkaralım."
    assert _puan(ad, cevap, "tuzak_yok") is True
    assert _puan(ad, cevap, "dogru_sonuc") is False


# ---- 4) YAZIM BİÇİMİ BAĞIMSIZLIĞI (BUG #316 bağı) -----------------------------

def test_bosluklu_binlik_ayirac_ile_yazilmis_altin_cevap_da_gecer():
    """
    Koç tutarları `14 023,29` diye yazar (Türkçede geçerli, LLM'lerin doğal çıktısı).
    Ölçüt bu yazıma körse altın setin oranı SİSTEMATİK olarak düşük çıkar ve düzeltilmesi
    gereken şeyin koç olduğu sanılır — BUG #316'nın birebir tekrarı.
    """
    ad = "G1_kredi_anapara_vs_taksit_toplami"
    bosluklu = (ALTIN_CEVAPLAR[ad].replace("14.023,29", "14 023,29")
                                  .replace("34.487,12", "34 487,12"))
    assert "14 023,29" in bosluklu
    assert _puan(ad, bosluklu, "dogru_sonuc") is True


def test_yuvarlanmis_tutar_da_gecer():
    """`8.221` yazmak hata değil yuvarlamadır; ölçüt bunu düşürürse doğru cevabı cezalandırır."""
    assert _puan("G2_kart_guncel_borc_yukumluluktur",
                 "Evet, 14 Eylül'de 8.221 TL ödeyeceksin.", "dogru_sonuc") is True


def test_beklenen_tutarlarin_YALNIZ_BIRI_yetmez():
    """
    MUTASYONUN BULDUĞU KÖR NOKTA (M2: `all` → `any`). G1 iki ayrı krediyi sorar; birinin
    kapama tutarını söyleyip ötekini atlayan cevap YARIM bir cevaptır ve kullanıcı eksik
    sayıyla karar verir. `any` mutasyonu ilk turda 30 testin hiçbirinden kaçmadan geçti —
    yani "iki beklentinin İKİSİ de" kuralı yazılı olduğu hâlde ÖLÇÜLMÜYORDU.
    """
    ad = "G1_kredi_anapara_vs_taksit_toplami"
    yarim = "Garanti Kredi 1'in erken kapama tutarı 14.023,29 TL."
    assert _puan(ad, yarim, "dogru_sonuc") is False
    # G3'te de aynı: kaynak söylenip zorunlu çıkış atlanırsa cevap karar verdirmez.
    ad3 = "G3_ay_ici_nakit_takvimi"
    yarim3 = "Eylül kaynağın 15.663,59 TL. 11 Eylül'de ilk ödemen var."
    assert _puan(ad3, yarim3, "dogru_sonuc") is False


def test_yakin_ama_farkli_tutar_gecmez():
    """Tolerans, İKİ AYRI beklentiyi birbirine karıştıracak kadar geniş olmamalı."""
    assert _puan("G2_kart_guncel_borc_yukumluluktur",
                 "Evet, 14 Eylül'de 8.500 TL ödeyeceksin.", "dogru_sonuc") is False


# ---- 5) VAKUMSAL YEŞİL YASAĞI --------------------------------------------------
# "Hiç beklenti yoktu, hepsi karşılandı" bir başarı değildir (L28). Bu kırılmalar
# YÜKSEK SESLEdir: sessiz bir varsayılan, kapıyı ölçmeden yeşile düşürürdü.

def test_beklentisiz_dogru_sonuc_kriteri_reddedilir():
    with pytest.raises(ValueError, match="beklenti tanımlı değil"):
        EvalScenario("x", "mesaj", ["cevapladi", "dogru_sonuc"])


def test_olcusuz_beklenti_reddedilir():
    with pytest.raises(ValueError, match="kriteri seçilmemiş"):
        EvalScenario("x", "mesaj", ["cevapladi"], beklenen_tutarlar=[100.0])


def test_tuzaksiz_tuzak_yok_kriteri_reddedilir():
    with pytest.raises(ValueError, match="tuzak tanımlı değil"):
        EvalScenario("x", "mesaj", ["cevapladi", "dogru_sonuc", "tuzak_yok"],
                     beklenen_desenler=["a"])


def test_beklenen_tutarsiz_tuzak_reddedilir():
    """Tuzak kuralı ŞARTLIDIR; şart (beklenen tutarlar) yoksa kural değerlendirilemez."""
    with pytest.raises(ValueError, match="beklenen_tutarlar boş"):
        EvalScenario("x", "mesaj", ["cevapladi", "dogru_sonuc", "tuzak_yok"],
                     beklenen_desenler=["a"], tuzak_tutarlar=[100.0])


def test_senaryosuz_altin_kriter_sessizce_gecmez():
    res = {"reply": "herhangi bir cevap", "proposed_actions": [], "grounding": {"ok": True}}
    for kriter in sorted(ALTIN_KRITERLER):
        with pytest.raises(ValueError, match="senaryo nesnesi olmadan"):
            score_result(res, [kriter])


# ---- 6) SETİN KENDİ SÖZLEŞMESİ -------------------------------------------------

def test_her_altin_senaryoda_olcum_ve_olu_koc_korumasi_var():
    for sc in ALTIN_SENARYOLAR:
        assert "dogru_sonuc" in sc.checks, f"{sc.name}: muhakeme ölçülmüyor"
        # BUG #276: olumsuz kriterleri ölü koç da geçer; her senaryoda pozitif çapa şart.
        assert "cevapladi" in sc.checks, f"{sc.name}: ölü koç korumasız"


def test_grounded_altin_sette_kullanilmaz():
    """
    Kapsam dışılık KİLİTLİDİR — ama gerekçesi ARTIK TEK:
      * ~~erken kapama tutarı cockpit'te sayı değil~~ → BUG #318 ile kapandı, sayısallaştı.
      * senaryolar TÜREV sayı istiyor (toplam/fark) ve türev sayı cockpit'te bulunmaz.
    İkinci gerekçe tek başına yeterli: G1'in altın cevabı iki kapama tutarını TOPLAR,
    G3 kaynak ve çıkış toplamı ister. Biri iyi niyetle `grounded` eklerse set sistematik
    kırmızıya döner ve suç koçta sanılır.
    """
    for sc in ALTIN_SENARYOLAR:
        assert "grounded" not in sc.checks, (
            f"{sc.name}: `grounded` altın sette geçersiz — bkz. scripts/coach_altin.py sınır 1.")


def test_altin_senaryolar_defaultlardan_ayri_bir_set():
    from app.coach_eval import DEFAULT_SCENARIOS
    varsayilan = {s.name for s in DEFAULT_SCENARIOS}
    assert not (varsayilan & {s.name for s in ALTIN_SENARYOLAR})
    assert len(ALTIN_SENARYOLAR) == 6, "G1-G6 §4.2'de altı maddedir"


def test_olu_koc_altin_kriterleri_bedavaya_gecemez():
    """Sağlayıcı cevap veremediyse `cevapladi` düşer ve TÜM kriterler düşer (BUG #276)."""
    sc = SENARYO["G2_kart_guncel_borc_yukumluluktur"]
    res = {"reply": "", "proposed_actions": [], "grounding": {},
           "llm_kullanilamadi": True}
    puanlar = score_result(res, sc.checks, senaryo=sc)
    assert not any(puanlar.values())


# ---- 7) İKİ SETİN GEÇMİŞTE KARIŞMAMASI ----------------------------------------

def test_kayit_hangi_seti_olctugunu_tasir():
    from app.eval_store import IZINLI_ALANLAR, kayit_olustur
    rapor = {"scenarios": [], "pass_rate": 33.3, "scenario_total": 6, "gecerli": True}
    assert "set" in IZINLI_ALANLAR
    assert kayit_olustur(rapor, "Gemini", senaryo_seti="altin")["set"] == "altin"
    assert kayit_olustur(rapor, "Gemini")["set"] == "varsayilan"


def test_dusus_karsilastirmasi_setleri_karistirmaz(monkeypatch):
    """
    İki set aynı dosyaya yazılır. Filtre olmadan davranış oranı (%88) ile muhakeme oranı
    yan yana kıyaslanır ve her set değişiminde SAHTE düşüş basılır.
    Etiketsiz ESKİ kayıtlar davranış seti sayılır — altın set o tarihte yoktu.
    """
    from scripts import eval_runner
    kayitlar = [
        {"saglayici": "Gemini", "pass_rate": 88.0},                    # etiketsiz (eski)
        {"saglayici": "Gemini", "set": "varsayilan", "pass_rate": 80.0},
        {"saglayici": "Gemini", "set": "altin", "pass_rate": 33.3},
    ]
    monkeypatch.setattr(eval_runner, "oku", lambda saglayici=None: list(kayitlar))
    assert [k["pass_rate"] for k in eval_runner.onceki_ayni_setten("Gemini", "altin")] == [33.3]
    assert [k["pass_rate"] for k in
            eval_runner.onceki_ayni_setten("Gemini", "varsayilan")] == [88.0, 80.0]
