"""
D17 / BUG #237 — STATİK KAPI: `date.today()` sunucunun günüdür, kullanıcının değil.

Neden statik kapı: bu defekt sınıfı tek tek uçlarda ölçülemez — bir yeni router yazılır,
içine `date.today()` konur, davranış testi olmadığı için kimse fark etmez ve kullanıcının
verisi yine yanlış güne düşer. ADR-042 tam olarak bunu yaşadı: belge "TÜM kullanıcı-bağlamlı
yollar user_today kullanır" dedi, disk 7 router gösterdi.

KURAL: `app/` altındaki her `date.today()` çağrısı ya kullanıcının gününe çevrilecek
(`user_today` / `user_today_by_id`) ya da aynı satırda/bir üst satırda gerekçeli
`tz-exempt: <neden>` işareti taşıyacak. Gerekçesiz kalan tek çağrı kapıyı kırar.

KAPININ KAPSAM TABANI (L11): kapı kendi ölçtüğü yüzeyi de assert eder — tarama boşa
düşerse (yol değişir, glob kayar) test yeşil kalmasın.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

KOK = pathlib.Path(__file__).resolve().parent.parent
APP = KOK / "app"

MUAFIYET_ISARETI = "tz-exempt:"

# Kullanıcının gününü üretmesi gereken modüller — biri bu yardımcıyı bırakırsa kapı kırılır.
# (Adoption kilidi: fix geri alınırsa yalnız davranış testleri değil, bu kapı da düşer.)
KULLANICI_GUNU_BEKLENEN = [
    "action_executor.py",
    "cashflow.py",
    "coach.py",
    "cockpit_snapshot.py",
    "debt_strategy.py",
    "goal_engine.py",
    "simulation_engine.py",
    "startup.py",
    "user_prefs.py",
    "routers/cockpit.py",
    "routers/onboarding.py",
    "routers/reports.py",
    "routers/subscriptions.py",
]


# Tek istisna: `user_prefs` KENDİSİ sunucu gününe düşme yardımcısıdır (TZ tanımsızsa geriye
# uyum). Kapının kaynağını kendi kuralına sokmak anlamsız olurdu. Liste büyüyemez — altta assert.
TARAMA_DISI = {"user_prefs.py"}


def _py_dosyalar() -> list[pathlib.Path]:
    return sorted(p for p in APP.rglob("*.py")
                  if "__pycache__" not in p.parts
                  and p.relative_to(APP).as_posix() not in TARAMA_DISI)


def _bugun_cagrilari(kaynak: str) -> list[int]:
    """AST ile `date.today()` / `datetime.date.today()` çağrılarının satır numaraları.

    AST kullanılır çünkü yorum/docstring içindeki 'date.today()' metni çağrı DEĞİLDİR —
    metin taraması bu dosyaların kendi açıklamalarında yanlış alarm üretirdi.
    """
    satirlar: list[int] = []
    for dugum in ast.walk(ast.parse(kaynak)):
        if not isinstance(dugum, ast.Call):
            continue
        f = dugum.func
        if isinstance(f, ast.Attribute) and f.attr == "today":
            kok = f.value
            if isinstance(kok, ast.Name) and kok.id in ("date", "datetime"):
                satirlar.append(dugum.lineno)
            elif isinstance(kok, ast.Attribute) and kok.attr == "date":
                satirlar.append(dugum.lineno)
    return satirlar


def _muaf_mi(satirlar: list[str], no: int) -> bool:
    """İşaret aynı satırda ya da hemen üstteki iki yorum satırında olabilir."""
    pencere = satirlar[max(0, no - 3):no]
    return any(MUAFIYET_ISARETI in s for s in pencere)


def _ihlaller() -> tuple[list[str], int, int]:
    ihlal, toplam_cagri, taranan = [], 0, 0
    for yol in _py_dosyalar():
        kaynak = yol.read_text(encoding="utf-8")
        taranan += 1
        satirlar = kaynak.splitlines()
        for no in _bugun_cagrilari(kaynak):
            toplam_cagri += 1
            if not _muaf_mi(satirlar, no):
                ihlal.append(f"{yol.relative_to(KOK).as_posix()}:{no}")
    return ihlal, toplam_cagri, taranan


def test_taramanin_disinda_yalnizca_yardimcinin_kendisi_var():
    """Muafiyetin muafiyeti olmasın: tarama dışı liste tek dosyadan ibaret kalmalı."""
    assert TARAMA_DISI == {"user_prefs.py"}
    assert (APP / "user_prefs.py").exists()


def test_gerekcesiz_sunucu_gunu_kullanimi_yok():
    ihlal, toplam, taranan = _ihlaller()

    # KAPSAM TABANI: tarama gerçekten kodu görüyor mu?
    assert taranan >= 40, f"tarama yüzeyi çöktü ({taranan} dosya) — kapı ölçmüyor"
    assert toplam >= 5, (
        f"app/ içinde yalnız {toplam} `date.today()` bulundu — AST taraması kaymış olabilir"
    )

    assert not ihlal, (
        "Gerekçesiz sunucu günü kullanımı (kullanıcının günü olmalı ya da "
        f"`# {MUAFIYET_ISARETI} <neden>` yazılmalı):\n  " + "\n  ".join(ihlal)
    )


def test_kapinin_kendisi_ihlali_yakalayabiliyor():
    """Mutasyon kontrolü: kapı gerçekten ölçüyor mu (yeşil kalan boş kapı değil)."""
    kirli = "from datetime import date\n\n\ndef f():\n    return date.today()\n"
    satirlar = kirli.splitlines()
    nolar = _bugun_cagrilari(kirli)
    assert nolar, "AST taraması apaçık bir date.today() çağrısını kaçırdı"
    assert not _muaf_mi(satirlar, nolar[0])

    temiz = "from datetime import date\n\n\ndef f():\n    return date.today()  # tz-exempt: test\n"
    assert _muaf_mi(temiz.splitlines(), _bugun_cagrilari(temiz)[0])

    # Yorum/docstring içindeki metin çağrı sayılmamalı (yanlış alarm üretmesin)
    yorum = '"""date.today() burada yalnız anlatılıyor."""\nx = 1\n'
    assert not _bugun_cagrilari(yorum)


@pytest.mark.parametrize("gorece", KULLANICI_GUNU_BEKLENEN)
def test_kullanici_baglamli_modul_kullanici_gununu_kullanir(gorece):
    """
    Adoption kilidi: bu modüller kullanıcının gününü üreten yardımcıyı kullanmayı BIRAKIRSA
    (fix geri alınır / yeni bir yol sunucu gününe döner) kapı kırılır.
    """
    yol = APP / gorece
    assert yol.exists(), f"{gorece} taşınmış — kapı güncellenmeli"
    kaynak = yol.read_text(encoding="utf-8")
    assert "user_today" in kaynak, (
        f"{gorece} kullanıcının gününü üretmiyor — `date.today()` sunucunun günüdür (D17)"
    )


def test_muafiyetler_gerekceli_ve_sinirli():
    """
    Muafiyet bir kaçış deliği olmamalı: her işaret bir GEREKÇE metni taşımalı ve
    muafiyetli çağrı sayısı bilinen tabanın üstüne sessizce büyümemeli.
    """
    muaf = []
    for yol in _py_dosyalar():
        kaynak = yol.read_text(encoding="utf-8")
        satirlar = kaynak.splitlines()
        for no in _bugun_cagrilari(kaynak):
            if _muaf_mi(satirlar, no):
                gerekce = ""
                for s in satirlar[max(0, no - 3):no]:
                    if MUAFIYET_ISARETI in s:
                        gerekce = s.split(MUAFIYET_ISARETI, 1)[1].strip()
                muaf.append((f"{yol.relative_to(KOK).as_posix()}:{no}", gerekce))

    bos = [y for y, g in muaf if len(g) < 10]
    assert not bos, f"gerekçesiz `{MUAFIYET_ISARETI}` işareti: {bos}"

    # Taban: bugün 8 muafiyet var (piyasa takvimi + saf yardımcı varsayılanları).
    # Sayı artıyorsa bilinçli bir karardır — bu satır da güncellenmeli.
    assert len(muaf) <= 8, (
        "muafiyet sayısı tabanın üstüne çıktı — her yeni muafiyet gözden geçirilmeli:\n  "
        + "\n  ".join(f"{y} → {g}" for y, g in muaf)
    )
