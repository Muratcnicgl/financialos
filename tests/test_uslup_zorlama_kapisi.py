"""
K2 KAPISI — ÜSLUP ZORLAMASI (kural kodda vardı ama ÜRÜN yolunda çağrılmıyordu).

ÖLÇÜLEN DEFEKT (1 Eylül 2026, `masterprompt-koc.md` K0/K2):
    `app/uslup_kurallari.py` altı üslup kuralını (`DALKAVUKLUK`, `DOLGU`, `SIZ_HITABI`,
    `IC_JARGON`, `BOS_TESELLI`, `NUTUK`) deterministik TESPİT edebiliyordu. Çağrı yerleri
    tarandı:
        · `sahte_niyet_iddiasi_var`     → `app/coach.py` çalışma anında ONARIYOR
        · `sahte_tamamlama_iddiasi_var` → `app/coach.py` retry TETİKLİYOR
        · `propose_sunulsun_mu`         → tool eşiğini KAPATIYOR
        · **`ihlaller()`               → YALNIZ `app/coach_eval.py`. Ürün yolunda HİÇBİR YER.**
    Yani altı kural için zincir şuydu: prompt "yapma" der → model yapar → eval "yaptın"
    diye ÖLÇER → **arada düzelten hiçbir şey yoktur.** K0 baseline'ında `SIZ_HITABI` ×2 ve
    `IC_JARGON` ×1 tam bu boşluktan kullanıcıya ulaştı.

    Bu, projenin KENDİ yazılı ilkesinin uygulanmamış hâliydi (`docs/architecture.md`):
    *"Master Checkpoint enforcement kod seviyesinde uygulanır — LLM'in prompt'ına
    güvenilmez."* Aynı ilke üsluba hiç uygulanmamıştı.

KAPSAM BİLİNÇLİ OLARAK DAR — VE BU KAPI ONU DA KORUR:
    Yalnız `silinebilir=True` maddeler temizlenir (dalkavukluk / dolgu / boş teselli /
    nutuk): bu maddelerin yasak olma SEBEBİ zaten bilgi taşımamalarıdır, cümleyi atmak
    cevaptan bir şey eksiltmez. `SIZ_HITABI` ve `IC_JARGON` bilgilendirici cümlenin
    İÇİNDE yaşar ("Borcunuzu bu ay kapatabilirsiniz") — silmek cevabı yok eder. Onlara
    DOKUNULMADIĞI da burada test edilir: kapsamı sessizce genişletmek, dar tutmak kadar
    tehlikelidir (yanlış onarım ihlalden zararlıdır).

MUTASYONLA KANITLANDI:
    M1: `coach.py`'deki `dolgu_temizle` çağrısı kaldırıldı → uçtan uca test düşer
        (asıl defektin ta kendisi: fonksiyon var ama çağrılmıyor)
    M2: `silinebilir` bayrağı yok sayılıp TÜM kurallar silinebilir yapıldı → kapsam
        testi düşer (SIZ_HITABI cümlesi yok edilir)
    M3: "asla boş dönme" koruması kaldırıldı → boş-ekran testi düşer
"""
from __future__ import annotations

import pytest

from app.coach import _postprocess_report
from app.uslup_kurallari import (
    KURALLAR,
    dolgu_temizle,
    ihlaller,
    silinebilir_kurallar,
)

_SILINEBILIR = {k.kod for k in silinebilir_kurallar()}
_KORUNAN = {k.kod for k in KURALLAR} - _SILINEBILIR

# MUTASYON 2 BU KAPININ KENDİ KÖR NOKTASINI BULDU (ve bu yüzden korundu):
# İlk sürümde aşağıdaki iki test `k.silinebilir` BAYRAĞI üzerinden parametrize ediliyordu.
# Bayrak çevrildiğinde (kapsam sessizce genişletildiğinde) parametre listesi BOŞALIYOR ve
# test kırmızı olmak yerine **hiç koşmuyordu** — yani kapı, koruduğu şey bozulduğu anda
# körleşiyordu. Aynı sınıf: BUG #311'de ölü-kod kapısı kendi gerekçesi yazılınca körleşmişti.
# Parametrizasyon artık KURAL KODUNA bağlı: bayrak değişse de örnek listesi sabit kalır ve
# test gerçekten düşer.
_SILINEBILIR_KODLAR = ("DALKAVUKLUK", "DOLGU", "BOS_TESELLI", "NUTUK")
_KORUNAN_KODLAR = ("SIZ_HITABI", "IC_JARGON")


def _ornekler(kodlar: tuple[str, ...]) -> list[str]:
    return [o for k in KURALLAR if k.kod in kodlar for o in k.ihlal_ornekleri]


# ============================================================
# 1. SÖZLEŞME — hangi kural silinebilir?
# ============================================================

def test_silinebilir_kume_tam_olarak_bilgi_tasimayanlar():
    """
    Kümenin KENDİSİ sözleşmedir. Buraya bir kural eklemek, o kuralın ihlal ettiği cümlenin
    kullanıcıya HİÇ ulaşmayacağı anlamına gelir — bilgi taşıyan bir kural eklenirse cevap
    sessizce budanır. Bu yüzden küme testle sabitlenir, `KURALLAR`'dan türetilmez.
    """
    assert _SILINEBILIR == {"DALKAVUKLUK", "DOLGU", "BOS_TESELLI", "NUTUK"}
    assert _KORUNAN == {"SIZ_HITABI", "IC_JARGON"}


# ============================================================
# 2. SİLİNEBİLİR MADDELER GERÇEKTEN TEMİZLENİYOR
# ============================================================

@pytest.mark.parametrize("ornek", _ornekler(_SILINEBILIR_KODLAR))
def test_dolgu_ornekleri_temizleniyor(ornek):
    """Her `ihlal_ornekleri` maddesi, ölçülmüş gerçek bir koç cümlesidir (BUG #277 korpusu)."""
    metin = f"Kart borcun 11.976 TL. {ornek}"
    temiz, atilan = dolgu_temizle(metin)
    assert atilan, f"temizlenmedi: {ornek!r}"
    assert ornek.split(".")[0] not in temiz, f"cümle metinde kaldı: {ornek!r}"
    assert "11.976" in temiz, "BİLGİ TAŞIYAN cümle kayboldu — temizlik fazla geniş"


# ============================================================
# 3. MEŞRU METİN — hiçbir kuralın karşı-örneği zarar görmez
# ============================================================

@pytest.mark.parametrize(
    "ornek",
    [o for k in KURALLAR for o in k.mesru_ornekler],
)
def test_mesru_ornekler_dokunulmadan_kaliyor(ornek):
    """
    Yanlış-pozitif ölçümü. `mesru_ornekler` korpusu bu iş için var: BUG #277'de desenler
    canlı DB'deki 12 gerçek koç cevabıyla kalibre edilmişti ("yalnız"/"deniz" istisnaları
    oradan çıktı). Temizlik o kalibrasyonu bozmamalı.
    """
    temiz, atilan = dolgu_temizle(ornek)
    assert temiz.strip() == ornek.strip(), f"meşru cümle değişti: {ornek!r} → {temiz!r}"
    assert not atilan


# ============================================================
# 4. KAPSAM DİSİPLİNİ — bilgi taşıyan ihlaller SİLİNMEZ
# ============================================================

@pytest.mark.parametrize("ornek", _ornekler(_KORUNAN_KODLAR))
def test_bilgi_tasiyan_ihlaller_silinmez(ornek):
    """
    `SIZ_HITABI` / `IC_JARGON` ihlalleri BURADA DÜZELTİLMEZ — ve bu bilinçlidir.
    "Borcunuzu bu ay kapatabilirsiniz" cümlesini atmak, kullanıcının sorusunun cevabını
    atmaktır. Doğru onarım biçim dönüşümü/yeniden üretimdir ve ölçülmeden yazılmaz.
    Bu test, kapsamın sessizce genişlemesini engeller.

    ÖRNEK ÇOK CÜMLELİ KURULUR — MUTASYON BUNU DA BULDU: tek cümlelik girdide kapsam
    genişletilse bile metnin TAMAMI silinir, "asla boş dönme" koruması devreye girer ve
    metin olduğu gibi geri döner. Yani ihlal, koruma tarafından MASKELENİR ve test yeşil
    kalır. Yanına bilgi taşıyan bir cümle konunca maskeleme kalkar: kapsam genişlerse
    yalnız ihlalli cümle düşer ve fark görünür olur.
    """
    metin = f"Kart borcun 11.976 TL. {ornek}"
    temiz, atilan = dolgu_temizle(metin)
    assert temiz.strip() == metin.strip(), (
        f"kapsam genişlemiş — bilgi taşıyan ihlal silindi: {ornek!r} → {temiz!r}"
    )
    assert not atilan
    # İhlal hâlâ ÖLÇÜLEBİLİR olmalı: temizlemiyoruz diye görmezden gelmiyoruz.
    assert ihlaller(ornek), "ihlal ölçüm tarafında da kayboldu"


# ============================================================
# 5. ASLA BOŞ EKRAN
# ============================================================

def test_tamami_dolgu_olan_cevap_bos_donmez():
    """
    Boş ekran, üslup ihlalinden AĞIR bir kusurdur. Cevabın tamamı dolguysa metin OLDUĞU
    GİBİ döner (aynı kalibrasyon `_ONAY_YOK_NOTU` yolunda da yapılmıştı).
    """
    sadece_dolgu = "Umarım yardımcı olmuşumdur! Her zaman buradayım."
    temiz, atilan = dolgu_temizle(sadece_dolgu)
    assert temiz.strip() == sadece_dolgu.strip()
    assert atilan == []


def test_bos_ve_none_girdi_cokmez():
    assert dolgu_temizle(None) == ("", [])
    assert dolgu_temizle("   ")[0].strip() == ""


# ============================================================
# 6. RAPOR İSKELETİ KORUNUR
# ============================================================

def test_rapor_basliklari_korunur():
    """Çok satırlı rapor formatında (V3 prompt §RAPOR FORMATI) iskelet bozulmamalı."""
    rapor = (
        "## DURUM RAPORU\n"
        "Statü: nakit dar.\n"
        "\n"
        "## 1. STRATEJİK ANALİZ\n"
        "Harika bir soru! Kart borcun 11.976 TL.\n"
        "- Kredi taksitin 6.857 TL.\n"
        "Umarım yardımcı olmuşumdur!"
    )
    temiz, atilan = dolgu_temizle(rapor)
    assert "## DURUM RAPORU" in temiz
    assert "## 1. STRATEJİK ANALİZ" in temiz
    assert "- Kredi taksitin 6.857 TL." in temiz
    assert "11.976" in temiz
    assert "Harika bir soru!" not in temiz
    assert "Umarım yardımcı olmuşumdur!" not in temiz
    assert set(atilan) == {"DALKAVUKLUK", "DOLGU"}


# ============================================================
# 7. UÇTAN UCA — ASIL DEFEKT: ÜRÜN YOLU ÇAĞIRIYOR MU?
# ============================================================

def test_urun_yolu_dolguyu_temizliyor():
    """
    BU TESTİN VARLIK SEBEBİ: kusur "fonksiyon yanlış çalışıyor" değil, **"fonksiyon hiç
    çağrılmıyor"du**. Birim testleri yeşil kalırken kullanıcı ihlali görmeye devam eder.
    Bu yüzden ölçüm ürün fonksiyonunun (`_postprocess_report`) çıktısı üzerinden yapılır.
    """
    ham = "Harika bir soru! Kart borcun 11.976 TL, kredin 79.625 TL."
    sonuc = _postprocess_report(ham, cockpit=None, user_message="durumum nedir?",
                                proposed_actions=[], bekleyen_onay_var=False)
    assert "Harika bir soru!" not in sonuc, "ürün yolu dolguyu temizlemiyor"
    assert "11.976" in sonuc and "79.625" in sonuc, "bilgi kayboldu"


def test_urun_yolu_bilgi_tasiyan_ihlali_SILMEZ():
    """
    Kapsam disiplini ürün yolunda da geçerli — ama "dokunmaz" DEĞİL, **"silmez"**.

    SÖZLEŞME DEĞİŞTİ (K2, aynı gün): `SIZ_HITABI` artık `siz_hitabi_onar()` ile biçimsel
    olarak ONARILIYOR (2. çoğul → 2. tekil). Bu testin eski hâli "ürün yolu dokunmaz" diyordu
    ve onarım eklenince haklı olarak kırmızıya döndü. Testi GEVŞETMEK yerine sözleşmenin
    yeni hâli yazıldı: bilgi taşıyan ihlalde CÜMLE SİLİNMEZ, bilgi korunur.
    Kapsam disiplini `dolgu_temizle` düzeyinde aynen sürüyor (yukarıdaki test).
    """
    ham = "Borcunuzu bu ay kapatabilirsiniz."
    sonuc = _postprocess_report(ham, cockpit=None, user_message="ne yapayim?",
                                proposed_actions=[], bekleyen_onay_var=False)
    assert "Borcunu" in sonuc, "bilgi taşıyan cümle yok edilmiş"
    assert "kapatabilirsin" in sonuc

    # IC_JARGON hâlâ dokunulmadan kalır: onun onarımı yeniden üretim ister, ölçülmedi.
    jargonlu = "Cockpit verilerine göre durumun iyi."
    assert _postprocess_report(jargonlu, cockpit=None, user_message="?",
                               proposed_actions=[], bekleyen_onay_var=False) == jargonlu


# ============================================================
# 8. ONARIM, ÖLÇÜMÜ SİLMEZ
# ============================================================

def test_onarim_izi_cagirana_tasiniyor():
    """Ürün, hangi maddeyi onardığını BİLDİRMEK zorunda — sessiz onarım ölçülemez."""
    iz: list[str] = []
    _postprocess_report("Harika bir soru! Kart borcun 11.976 TL.", cockpit=None,
                        user_message="durum?", proposed_actions=[],
                        bekleyen_onay_var=False, uslup_izi=iz)
    assert iz == ["DALKAVUKLUK"]


def test_onarilan_ihlal_eval_de_HALA_dusuyor():
    """
    BU TESTİN VARLIK SEBEBİ — ÖLÇÜLEN ÇARPIŞMA:
        `dolgu_temizle` ürün yoluna bağlandığı anda `tests/test_uslup_kapisi.py`'nin DÖRT
        personası (dalkavukluk/dolgu/boş teselli/nutuk) referanstan **ayrışamaz** oldu:
        temizlik ihlali `reply`den sildiği için eval'in `uslup` kriteri artık geçiyordu.
        Yani bir ONARIM, bir ÖLÇÜMÜ körleştirdi.

        Bunun uç hâli tehlikelidir: cevaplarının tamamını dolguyla dolduran bir model
        **%100 pass_rate** alırdı, çünkü kullanıcıya temiz metin gidiyor. Model
        regresyonu görünmez olurdu — tam da K0'da eval üç hafta koşulmadığı için
        yaşananın otomatikleşmiş hâli.

    SÖZLEŞME: ürün onarır, ölçüm görür. Kriter `reply` ile `uslup_onarildi`nin BİRLEŞİMİNE
    bakar. Bu test doğrudan o birleşimi sabitler (persona testine dolaylı bağlı kalmaz).
    """
    from app.coach_eval import score_result

    temiz_ama_onarilmis = {
        "reply": "Kart borcun 11.976 TL.",   # kullanıcıya giden metin TERTEMİZ
        "uslup_onarildi": ["DALKAVUKLUK"],   # ama model ihlal etmişti
    }
    assert score_result(temiz_ama_onarilmis, ["uslup"])["uslup"] is False, (
        "onarılan ihlal ölçümden de silinmiş — eval körleşti"
    )

    gercekten_temiz = {"reply": "Kart borcun 11.976 TL.", "uslup_onarildi": []}
    assert score_result(gercekten_temiz, ["uslup"])["uslup"] is True


# ============================================================
# 9. İKİ ORAN — model sözleşmesi vs kullanıcıya giden çıktı
# ============================================================

def test_iki_goz_ayri_sonuc_verir():
    """
    K2'nin doğurduğu tasarım sorusu: onarım eklendikten sonra **tek bir oran iki farklı
    soruyu birden temsil edemez**.
      · MODEL SÖZLEŞMESİ  — model ihlali ÜRETTİ mi?   (regresyon ağı; varsayılan)
      · KULLANICIYA GİDEN — kullanıcı ihlali GÖRDÜ mü? (onarımın kazancı)
    Yalnız birincisi raporlanırsa onarımın kullanıcı tarafındaki kazancı HİÇBİR sayıda
    görünmez ve sessizce geri alınabilir. Yalnız ikincisi raporlanırsa model regresyonu
    görünmez olur (cevaplarının tamamını dolguyla dolduran model "kusursuz" puan alır).
    """
    from app.coach_eval import score_result

    onarilmis = {"reply": "Kart borcun 11.976 TL.", "uslup_onarildi": ["SIZ_HITABI"]}
    assert score_result(onarilmis, ["uslup"])["uslup"] is False, "model sözleşmesi gevşemiş"
    assert score_result(onarilmis, ["uslup"], kullanici_gozu=True)["uslup"] is True, (
        "kullanıcı gözü, onarılmış çıktıyı hâlâ ihlalli sayıyor"
    )


def test_varsayilan_goz_MODEL_SOZLESMESIDIR():
    """
    Varsayılanın hangi göz olduğu bir GÜVENLİK kararıdır (L36: yanlış tarafa düşmenin bedeli
    asimetriktir). Bir model regresyonunu kaçırmak, bir kazanımı geç fark etmekten ağırdır —
    bu yüzden varsayılan katı olandır. Varsayılan sessizce gevşetilirse BUG #277'nin persona
    kapısı da körleşir.
    """
    from app.coach_eval import score_result

    onarilmis = {"reply": "temiz metin", "uslup_onarildi": ["DOLGU"]}
    assert score_result(onarilmis, ["uslup"])["uslup"] is False


def test_rapor_IKI_orani_da_basiyor():
    """İki sayı yan yana durmazsa biri diğerini gizler — rapor ikisini de göstermeli."""
    from app.coach_eval import format_report

    metin = format_report({
        "gecerli": True, "scenario_pass": 6, "scenario_total": 8,
        "check_pass": 30, "check_total": 35,
        "pass_rate": 85.7, "pass_rate_kullanici": 91.4, "scenarios": [],
    })
    assert "MODEL SOZLESMESI" in metin
    assert "KULLANICIYA GIDEN CIKTI" in metin
    assert "85.7" in metin and "91.4" in metin
    assert "ONARIM KAZANCI" in metin, "fark raporlanmıyor — kazanç görünmez kalır"
