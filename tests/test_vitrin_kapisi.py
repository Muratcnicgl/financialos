"""
VİTRİN KAPISI (Wave-Y / Y7, ADR-060) — private → public sınırında son ölçüm.

`scripts/vitrin_uret.py` bir **allowlist** üreticisidir: çıktıya giden tek yol, her alanı
gerekçesiyle listeleyen `IZINLI_ALANLAR` sözlüğüdür. Bu kapı **ikinci savunmadır**, birinci
değil — birinci savunma "kötüyü ara" değil, "iyiyi geçir"dir.

NEDEN İKİNCİ SAVUNMA GEREKLİ
-----------------------------
Allowlist doğru kurgudur ama **uygulaması hata kabul eder**: bir ölçüm fonksiyonu izinli
bir alana yanlışlıkla ham metin koyabilir (ör. ADR *gövdesi* okunur, `git log` çıktısı
eklenir, mutlak yol sızar). Kapı, üreticinin niyetini değil **ÜRETTİĞİ BAYTLARI** ölçer.

KAPI **ÜRETİMDE DEĞİL, PUSH'TAN HEMEN ÖNCE** KOŞAR
---------------------------------------------------
Üretilen dosyalar diskteyken taranır; temizse yayınlanır. Üretim anında taramak, üreticinin
kendi hafızasındaki veriye güvenmek olurdu — oysa yayınlanan şey **dosyadır**.

ARANAN ŞEYLER (ve neden her biri)
----------------------------------
* hesap no · IBAN · kart — tek başına kimliklendirici (asıl depo kapısıyla aynı desenler)
* e-posta — `live_gate` şahsi destek adresini zaten yakalamıştı
* banka adları — kurucunun banka ilişkileri
* **gerçek tutarlar** — asıl deponun kişisel veri kapısının GÖREMEDİĞİ eksen; ledger ve
  ADR gövdeleri bunlarla dolu
* **mutlak yollar** (`C:\\Users\\<ad soyad>\\…`) — kullanıcı adını taşır; kimse denylist
  yazarken bunu akla getirmez, allowlist'in korumasının somut örneği budur

MUTASYON 4/4 — gercek tutar enjekte edildi · mutlak yol enjekte edildi · ADR govdesi sizdirildi · e-posta enjekte edildi
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
VITRIN = KOK / "vitrin"

# DESENLER TEK KAYNAKTAN ALINIR — ve bunun somut bir sebebi var:
#
# İlk yazımda desenler buraya KOPYALANMIŞTI (hesap no, IBAN, kart, e-posta, banka adı).
# Sonuç: depo geneli kişisel veri kapısı bu dosyayı **kendi ihlali** sayıp commit'i
# durdurdu (banka adı tavanı 96 → 97). Kolay cevap "bu dosyayı muaf tut" olurdu — ama o,
# kapıyı tam da bu dosyaya gerçek bir banka adı girdiği gün körleştirirdi (L67).
#
# Doğru cevap kopyayı kaldırmak: "kişisel veri neye benzer" sorusunun tek bir cevabı olur,
# iki kapı da onu okur. Aynı desenin iki yerde yaşaması, birini güncelleyip diğerini
# unutmanın davetiyesidir — ve bu depoda `git ls-files`'ın beş kopyasıyla zaten yaşandı.
from tests.test_depo_kisisel_veri_kapisi import (  # noqa: E402
    SERT_DESENLER as _SERT, YUMUSAK_DESENLER as _YUMUSAK,
)

YASAK = {
    **{ad: re.compile(k) for ad, k in _SERT.items()},
    **{ad: re.compile(k) for ad, k in _YUMUSAK.items()},
    # Vitrine ÖZGÜ iki eksen — depo kapısında YOKLAR ve olmamaları doğru:
    #
    # (1) Kurucunun ölçülmüş gerçek tutarları. Depo içinde meşrudurlar (test fixture'ı,
    #     ölçüm defteri, ADR gövdesi); DIŞARIYA çıkmaları meşru değildir.
    "gercek tutar": re.compile(
        r"8[.,]?221[.,]13|8[.,]?338[.,]13|1[.,]?644[.,]23|34[.,]?688|14[.,]?916"
        r"|16[.,]?439|63[.,]?186|31[.,]?115"),
    # (2) Mutlak yol kullanıcı adını taşır. Depo içinde zararsız, vitrinde kimlik.
    #     Kimse denylist yazarken bunu akla getirmez — allowlist'in korumasının örneği.
    "mutlak yol": re.compile(r"[A-Za-z]:\\Users\\[^\\\s\"']+"),
}


def _vitrin_dosyalari() -> list[Path]:
    if not VITRIN.exists():
        return []
    return [p for p in VITRIN.rglob("*") if p.is_file() and p.suffix in {".md", ".json", ".html"}]


@pytest.fixture(scope="module")
def dosyalar():
    d = _vitrin_dosyalari()
    if not d:
        pytest.skip("vitrin/ uretilmemis — once: python -m scripts.vitrin_uret")
    return d


def test_VITRIN_YASAKLI_DESEN_TASIMAZ(dosyalar):
    """Yayınlanacak baytlarda kişisel veri olamaz. Tavan SIFIR — ratchet yok."""
    bulgular = []
    for p in dosyalar:
        metin = p.read_text(encoding="utf-8", errors="replace")
        for ad, desen in YASAK.items():
            m = desen.search(metin)
            if m:
                # Bulgunun KENDİSİ basılmaz (o da sızıntı olurdu) — yalnız sınıfı ve yeri.
                satir = metin[:m.start()].count("\n") + 1
                bulgular.append(f"{p.relative_to(KOK).as_posix()}:{satir} -> {ad}")
    assert not bulgular, (
        "VİTRİN KİŞİSEL VERİ TAŞIYOR — yayınlanamaz:\n  " + "\n  ".join(bulgular)
        + "\n\nÜretici allowlist'tir: bir alan bunu taşıyorsa o alanın ÖLÇÜM FONKSİYONU "
          "ham metin kopyalıyor demektir. Deseni maskeleme; alanı düzelt."
    )


def test_URETICI_ALLOWLIST_ZORLUYOR():
    """
    Sözleşmenin kendisi: `veri_topla` izinli olmayan bir anahtar üretirse ÜRETİM DURMALI.
    Bu test kapının değil, ÜRETİCİNİN garantisini ölçer — kapı ikinci savunmadır.
    """
    from scripts import vitrin_uret as vu
    assert vu.IZINLI_ALANLAR, "allowlist boş — üretici korumasız"
    # Her izinli alanın bir GEREKÇESİ olmalı (boş gerekçe, gerekçesizlik demektir).
    gerekcesiz = [k for k, v in vu.IZINLI_ALANLAR.items() if not (v or "").strip()]
    assert not gerekcesiz, f"gerekçesiz izinli alan: {gerekcesiz}"


def test_ADR_GOVDESI_ALINMAZ_YALNIZ_BASLIK(dosyalar):
    """
    ADR gövdeleri gerçek rakamlarla dolu; vitrine yalnız BAŞLIK satırları girer.
    Ölçüm: `olcumler.json`'daki her ADR kaydı TEK SATIR olmalı ve makul uzunlukta.
    """
    j = VITRIN / "olcumler.json"
    if not j.exists():
        pytest.skip("olcumler.json yok")
    veri = json.loads(j.read_text(encoding="utf-8"))
    for b in veri.get("adr_basliklari", []):
        assert "\n" not in b, f"ADR kaydı çok satırlı (gövde sızmış): {b[:60]}…"
        assert len(b) < 200, f"ADR kaydı fazla uzun (gövde sızmış olabilir): {b[:60]}…"


def test_OLCUMLER_SAYI_VE_KISA_METIN(dosyalar):
    """
    `olcumler.json` yayınlanacak ham veridir. İçindeki her skaler ya SAYI ya da KISA
    metin olmalı: uzun serbest metin, bir yerden kopyalanmış olduğunun işaretidir.
    """
    j = VITRIN / "olcumler.json"
    if not j.exists():
        pytest.skip("olcumler.json yok")
    veri = json.loads(j.read_text(encoding="utf-8"))
    uzunlar = []

    def gez(d, yol=""):
        if isinstance(d, dict):
            for k, v in d.items():
                gez(v, f"{yol}.{k}")
        elif isinstance(d, list):
            for i, v in enumerate(d):
                gez(v, f"{yol}[{i}]")
        elif isinstance(d, str) and len(d) > 400:
            uzunlar.append(f"{yol} ({len(d)} kar)")

    gez(veri)
    assert not uzunlar, (
        "Vitrin verisinde 400 karakterden uzun metin var — bir yerden kopyalanmış "
        f"olabilir:\n  {uzunlar}"
    )


def test_TASLAK_YAYINLANAMAZ(dosyalar):
    """
    Hızlı modda `backend_test` TOPLANAN test sayısıdır, GEÇEN değil. İkisini aynı etiketle
    yayınlamak, **ölçülmemiş bir iddiayı ölçüm gibi sunmaktır** — bu projenin en sık
    avladığı hata (KURAL R3). Vitrin bir dış iddia olduğu için taslak yayınlanamaz.
    """
    j = VITRIN / "olcumler.json"
    if not j.exists():
        pytest.skip("olcumler.json yok")
    veri = json.loads(j.read_text(encoding="utf-8"))
    assert veri.get("olcum_modu") == "tam", (
        f"Vitrin TASLAK (mod={veri.get('olcum_modu')!r}) — yayınlanamaz.\n"
        "Hızlı modda test sayısı 'toplanan'dır, 'geçen' değil; kapsam hiç ölçülmemiştir.\n"
        "Yayın için tam ölçüm: python -m scripts.vitrin_uret"
    )
