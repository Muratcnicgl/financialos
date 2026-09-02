"""
K2 KAPISI — `SIZ_HITABI` DETERMİNİSTİK ONARIMI (2. çoğul → 2. tekil).

NEDEN BU YÖNTEM SEÇİLDİ (ölçüm, 1 Eylül 2026):
    Canlı DB'deki 11 gerçek koç cevabının **5'inde (%45)** `SIZ_HITABI` var — üretimdeki en
    sık üslup ihlali. Üç seçenek ölçüldü:
      · SİLMEK — imkânsız: ihlal bilgilendirici cümlenin İÇİNDE ("Borcunuzu bu ay
        kapatabilirsiniz"); silmek kullanıcının sorusunun cevabını siler.
      · YENİDEN ÜRETTİRMEK — sürdürülemez: %45 sıklıkta, cevapların yarısında ikinci bir
        LLM çağrısı demek. Koçun isteği zaten 12.364 token (K0 ölçümü).
      · BİÇİM DÖNÜŞÜMÜ — sıfır maliyet, tekrarlanabilir, test edilebilir. Seçilen bu.

YANLIŞ DÖNÜŞÜM İHLALDEN ZARARLIDIR — bu kapı asıl bunu korur:
    Onarım metni DEĞİŞTİRİR. Bir yanlış dönüşüm ("yalnız" → "yaln") kullanıcıya bozuk
    Türkçe gönderir; bu, düzeltmeye çalıştığı ihlalden ağırdır. Bu yüzden testlerin ağırlığı
    "onarıyor mu" değil **"neyi BOZMUYOR"** tarafındadır: karşı-örnek korpusu, tuzak
    kelimeler ve CANLI korpus.

ÖLÇÜMÜN DÜZELTTİĞİ BİR VARSAYIM (dürüst kayıt):
    Deneme sırasında istisna listesine "anız" eklenmişti (uydurma, ölçülmemiş) ve alt-dize
    eşleşmesiyle "azaltm**anız**ı" kelimesini onarımdan muaf tutuyordu — yani uydurulan bir
    istisna, gerçek bir onarımı engelledi. Liste projenin ÖLÇÜLMÜŞ hâline (`_SIZ_ISTISNA`)
    geri alındı ve eşleşme **kelime başına** bağlandı.

MUTASYONLA KANITLANDI:
    M1: `coach.py`'deki `siz_hitabi_onar` çağrısı kaldırıldı → uçtan uca test düşer
    M2: istisna kontrolü kaldırıldı                        → tuzak-kelime testi düşer
    M3: kelime başı eşleşmesi alt-dizeye çevrildi           → "azaltmanızı" testi düşer
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest

from app.coach import _postprocess_report
from app.uslup_kurallari import KURALLAR, _SIZ_ISTISNA, ihlaller, siz_hitabi_onar

_SIZ = next(k for k in KURALLAR if k.kod == "SIZ_HITABI")


# ============================================================
# 1. ONARIM ÇALIŞIYOR — ihlal korpusu tamamen düzelmeli
# ============================================================

@pytest.mark.parametrize("ornek", _SIZ.ihlal_ornekleri)
def test_ihlal_ornekleri_tamamen_onariliyor(ornek):
    """`ihlal_ornekleri` ölçülmüş gerçek koç cümleleridir (BUG #277 korpusu)."""
    onarilmis, degisti = siz_hitabi_onar(ornek)
    assert degisti, f"onarılmadı: {ornek!r}"
    assert not ihlaller(onarilmis), (
        f"onarım sonrası ihlal sürüyor: {ornek!r} → {onarilmis!r}"
    )


@pytest.mark.parametrize(
    "girdi,beklenen",
    [
        ("Borcunuzu bu ay kapatabilirsiniz.", "Borcunu bu ay kapatabilirsin."),
        ("Kartınızın limiti dolmak üzere.", "Kartının limiti dolmak üzere."),
        ("Harcamalarınızı azaltmanızı öneririm.", "Harcamalarını azaltmanı öneririm."),
        ("Nakit kasanız 4.276 TL.", "Nakit kasan 4.276 TL."),
        ("Limitinizi aşarsanız faiz işler.", "Limitini aşarsan faiz işler."),
        ("Karşılaştığınızda haber ver.", "Karşılaştığında haber ver."),
    ],
)
def test_beklenen_ciktiyi_uretiyor(girdi, beklenen):
    """
    Tam çıktı sabitlenir — "ihlal kalmadı" yetmez, ÜRETİLEN METNİN KENDİSİ doğru olmalı.
    (Son üç satır canlı korpustan alınmış gerçek dönüşümlerdir.)
    """
    assert siz_hitabi_onar(girdi)[0] == beklenen


# ============================================================
# 2. NEYİ BOZMUYOR — ASIL KORUMA
# ============================================================

@pytest.mark.parametrize("ornek", [o for k in KURALLAR for o in k.mesru_ornekler])
def test_mesru_ornekler_bozulmuyor(ornek):
    onarilmis, degisti = siz_hitabi_onar(ornek)
    assert not degisti and onarilmis == ornek, f"meşru metin bozuldu: {ornek!r} → {onarilmis!r}"


@pytest.mark.parametrize(
    "tuzak",
    [
        "yalnız kart borcun 11.976 TL",
        "yalnızca bu ay",
        "denizde tatil planın var mı",
        "temizlik için 300 TL ayırdın",
        "geniz eti ameliyatı 8.000 TL",
        "benzin 1.200 TL",
        "kırmızı çizgin bu",
        "omuz omuza",
        "ceviz aldın",
        "domuz",
    ],
)
def test_tuzak_kelimeler_bozulmuyor(tuzak):
    """
    Katlandığında 2. çoğul kuyruğuyla ("n + dar ünlü + z") aynı görünen gerçek kelimeler.
    `_SIZ_ISTISNA` bu iş için var ve BUG #277'de canlı metinle ölçülerek kuruldu.
    Çekimli biçimler ("yalnızca", "denizde", "temizlik") kelime BAŞI eşleşmesiyle korunur.
    """
    onarilmis, degisti = siz_hitabi_onar(tuzak)
    assert not degisti and onarilmis == tuzak, f"tuzak kelime bozuldu: {tuzak!r} → {onarilmis!r}"


def test_istisna_listesi_uydurulmamis():
    """
    Liste ÖLÇÜLMÜŞTÜR, uydurulmaz. Deneme sırasında eklenen "anız" (ölçülmemiş) alt-dize
    eşleşmesiyle "azaltmanızı"yı muaf tutup gerçek bir onarımı engellemişti. Bu test,
    listeye ölçülmemiş bir madde eklenmesini görünür kılar.
    """
    assert _SIZ_ISTISNA == ("yalniz", "deniz", "beniz", "geniz", "temiz", "seksiz")
    # ve o hata bir daha olmasın diye somut karşı-örnek:
    assert siz_hitabi_onar("azaltmanızı öneririm.")[0] == "azaltmanı öneririm."


@pytest.mark.parametrize(
    "girdi,beklenen",
    [
        ("temizlemenizi öneririm", "temizlemeni öneririm"),
        ("denizinizi göremedim", "denizini göremedim"),
        ("yalnızlığınızı anlıyorum", "yalnızlığını anlıyorum"),
    ],
)
def test_istisna_GOVDESI_disindaki_ihlal_onarilir(girdi, beklenen):
    """
    İSTİSNA KELİMEYE DEĞİL, EŞLEŞMENİN KONUMUNA BAĞLIDIR — bu testin varlık sebebi
    mutasyonla bulunan İKİNCİ tasarım hatasıdır.

    Ara tasarım "istisna kelime BAŞINDA ise kelimeye hiç dokunma" diyordu. Ölçüm ters
    yönde yanlış olduğunu gösterdi: "**temiz**lemenizi" kelimesi "temiz" ile başladığı
    için TAMAMEN muaf kalıyor, oysa sondaki "-nizi" gerçek bir ihlaldi ve onarılmalıydı.
    Yani kelimenin BAŞINDAKİ bir istisna, kelimenin SONUNDAKİ ihlali koruyordu — sessiz
    bir yanlış negatif.

    Doğru kural: eşleşme yalnızca istisna GÖVDESİNİN İÇİNE düşüyorsa atlanır.
    ("yalnızca"da eşleşme gövdenin içindedir → korunur; "yalnızlığınızı"da hem gövde içi
    hem gövde dışı eşleşme vardır → yalnız ikincisi onarılır.)
    """
    assert siz_hitabi_onar(girdi)[0] == beklenen


def test_bos_girdi_cokmez():
    assert siz_hitabi_onar(None) == ("", False)
    assert siz_hitabi_onar("   ")[1] is False


# ============================================================
# 3. CANLI KORPUS — gerçek koç cevaplarında ölç
# ============================================================

_DB = Path(__file__).resolve().parent.parent / "data" / "financialos.db"


@pytest.mark.skipif(not _DB.exists(), reason="canlı DB yok (CI); korpus ölçümü atlanır")
def test_canli_korpusta_ihlal_birakmiyor():
    """
    ASIL KANIT: sentetik örnek değil, koçun GERÇEKTEN yazdığı cevaplar. DB yalnız-okunur
    açılır. CI'da dosya yoksa test atlanır — kapı, canlı veriye BAĞIMLI olmamalı ama
    varsa onu KULLANMALI (sentetik korpus, gerçek dilin çeşitliliğini taşımaz).
    """
    con = sqlite3.connect(f"file:{_DB}?mode=ro", uri=True)
    try:
        cevaplar = [
            r[0] for r in con.execute(
                "select content from coach_memories "
                "where role='assistant' and content is not null and length(content) > 40"
            )
        ]
    finally:
        con.close()
    if not cevaplar:
        pytest.skip("canlı korpus boş")

    onarilan = 0
    for metin in cevaplar:
        yeni, degisti = siz_hitabi_onar(metin)
        if degisti:
            onarilan += 1
            assert "SIZ_HITABI" not in ihlaller(yeni), (
                f"onarım sonrası ihlal sürüyor:\n{yeni[:300]}"
            )
        # Onarım kelime SAYISINI değiştirmemeli: dönüşüm biçimseldir, cümle silmez.
        assert len(re.findall(r"\w+", yeni)) == len(re.findall(r"\w+", metin))
    assert onarilan > 0, "canlı korpusta hiç onarım olmadı — ölçüm bayatlamış olabilir"


# ============================================================
# 4. UÇTAN UCA — ürün yolu gerçekten çağırıyor mu?
# ============================================================

def test_urun_yolu_siz_hitabini_onariyor():
    """Kusurun sınıfı yine 'çağrılmıyor' olabilir — ölçüm ürün fonksiyonundan yapılır."""
    ham = "Borcunuzu bu ay kapatabilirsiniz."
    sonuc = _postprocess_report(ham, cockpit=None, user_message="ne yapayim?",
                                proposed_actions=[], bekleyen_onay_var=False)
    assert sonuc == "Borcunu bu ay kapatabilirsin."


def test_urun_yolu_onarim_izini_bildiriyor():
    """Onarım ölçümü silmez: ürün, `SIZ_HITABI`'yı onardığını da bildirmek zorunda."""
    iz: list[str] = []
    _postprocess_report("Borcunuzu kapatabilirsiniz.", cockpit=None, user_message="?",
                        proposed_actions=[], bekleyen_onay_var=False, uslup_izi=iz)
    assert iz == ["SIZ_HITABI"]
