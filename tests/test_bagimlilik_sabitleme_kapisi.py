"""
DEVOPS-005 / BUG #390 KAPISI — BAĞIMLILIKLAR TAM SÜRÜMLE SABİT.

Ölçülen (11 Eyl 2026): 5 Eyl ölçümü "24/27 pinli" demişti; o günden sonra güvenlik tabanı
alt sınırla (`>=`) eklendi ve sayı **9 satır `>=`** olmuştu — madde kapanmak yerine
gerilemişti, çünkü ölçen kapı yoktu. `requirements-dev.txt` 1/5 pinliydi: süit bir gün
kod değişmeden başka pytest sürümüyle koşabilirdi (ruff için yazılı gerekçe herkese geçerli).

Kilitlenen: iki dosyadaki her bağımlılık satırı `==` taşır. Liste elle yazılmaz, dosyadan
türetilir (L79). Lock/hash dosyası BİLEREK yok: tek makine + CI, `pip-audit` her push'ta;
hash'li lock ayrı araç ve akış ister, ihtiyaç ölçülmedi.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
DOSYALAR = ("requirements.txt", "requirements-dev.txt")
SATIR = re.compile(r"^\s*([A-Za-z0-9_.\-]+(?:\[[^\]]+\])?)\s*(==|>=|<=|~=|!=|>|<)?")


def _bagimliliklar(p: Path) -> list[tuple[str, str | None]]:
    out = []
    for s in p.read_text(encoding="utf-8").splitlines():
        s = s.split("#", 1)[0].strip()
        if not s or s.startswith("-"):
            continue
        m = SATIR.match(s)
        assert m, f"ayrıştırılamayan satır: {s!r}"
        out.append((m.group(1), m.group(2)))
    return out


@pytest.mark.parametrize("dosya", DOSYALAR)
def test_her_bagimlilik_TAM_surumle_sabit(dosya):
    satirlar = _bagimliliklar(KOK / dosya)
    assert len(satirlar) >= 5, f"{dosya}: yalnız {len(satirlar)} satır — tarayıcı bozuk olabilir (L45)"
    gevsek = [ad for ad, op in satirlar if op != "=="]
    assert gevsek == [], f"{dosya}: tam sürümle sabit olmayan: {gevsek}"


def test_kapi_kendisi_calisiyor(tmp_path):
    p = tmp_path / "r.txt"
    p.write_text("a==1.0  # yorum\nb>=2\n-r other.txt\n\n# c<3\nd[extra]==4\n", encoding="utf-8")
    assert _bagimliliklar(p) == [("a", "=="), ("b", ">="), ("d[extra]", "==")]
