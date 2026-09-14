"""
DEVOPS-020 / DOCS-004 (BUG #476): sürüm notu ve yayın süreci KAYNAKTAN doğrulanır.

Ölçüm (14 Eyl 2026): CHANGELOG.md vardı ama 5 Ağustos'tan (0.2.0) beri dokunulmamıştı;
arada 253 düzeltme (#223–#475) ve 333 commit birikmiş, "Yayınlanmamış" başlığı 40 gün
bayat kalmıştı. `test_version_release.py` yalnız "[APP_VERSION] başlığı var mı" diye
bakıyordu — bayat bir günlük o testi geçer. Bu kapı süreci ölçer:
  1. en üstteki YAYINLANMIŞ sürüm APP_VERSION ile aynı ve tarihi ISO,
  2. sürüm başlıkları yukarıdan aşağı azalan (SemVer) ve tarihler azalan,
  3. günlükte anılan her `#NNN` gerçekten var (defter/backlog/charter'larda) — uydurma
     ya da yazım hatalı numara yok,
  4. son sürüm notu, defterdeki en son BUG numarasını içerir ya da "Yayınlanmamış" bölümünde
     iş var — yani günlük defterden geride kalamaz (bayatlama kapısı),
  5. yayın adımları contributing'de yazılı ve etiket adı `v<APP_VERSION>` biçiminde.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from app.version import APP_VERSION

KOK = Path(__file__).resolve().parent.parent
CHANGELOG = KOK / "CHANGELOG.md"
DEFTER = KOK / "docs" / "kalite-seruveni" / "uygulanan-fixler.md"
CONTRIBUTING = KOK / "docs" / "contributing.md"

_BASLIK = re.compile(r"^## \[(\d+\.\d+\.\d+)\] — (\d{4}-\d{2}-\d{2})", re.M)


def _ch() -> str:
    return CHANGELOG.read_text(encoding="utf-8")


def _surumler() -> list[tuple[tuple[int, ...], date]]:
    return [(tuple(int(x) for x in m.group(1).split(".")), date.fromisoformat(m.group(2))) for m in _BASLIK.finditer(_ch())]


def test_en_ustteki_yayin_app_version_ile_ayni():
    s = _surumler()
    assert s, "CHANGELOG'da '## [x.y.z] — YYYY-MM-DD' biçiminde yayın yok"
    assert ".".join(map(str, s[0][0])) == APP_VERSION, "en üstteki yayın APP_VERSION değil"
    assert s[0][1] <= date.today()


def test_surumler_ve_tarihler_azalan():
    s = _surumler()
    for (v1, t1), (v2, t2) in zip(s, s[1:], strict=False):
        assert v1 > v2, f"sürüm sırası bozuk: {v1} sonra {v2}"
        assert t1 >= t2, f"tarih sırası bozuk: {t1} sonra {t2}"


def test_anilan_her_bug_numarasi_gercek():
    """Yalnız GÜNCEL notlar (Yayınlanmamış + son sürüm): tarihsel notlar (0.1/0.2) defter
    tablosundan önceki dönemi anlatır ve bazı numaraları yalnız git geçmişi taşır; CI'ın sığ
    klonu o geçmişi görmez. Kapı bugün yazılanı korur."""
    metin = _ch().split("## [", 1)[1]            # Yayınlanmamış'tan itibaren
    parcalar = metin.split(chr(10) + "## [", 2)
    metin = parcalar[0] + parcalar[1]   # + ilk yayın
    numaralar: set[int] = set()
    for m in re.finditer(r"#(\d{3})(?:–#?(\d{3}))?", metin):
        a, b = int(m.group(1)), int(m.group(2) or m.group(1))
        numaralar.update(range(a, b + 1))
    kaynak = "".join(p.read_text(encoding="utf-8", errors="ignore") for p in (KOK / "docs").rglob("*.md"))
    eksik = sorted(n for n in numaralar if not re.search(rf"#{n}\b", kaynak))
    assert not eksik, f"CHANGELOG'da anılan ama hiçbir belgede olmayan BUG numarası: {eksik}"


def _defterdeki_son_bug() -> int:
    return max(int(n) for n in re.findall(r"^\| #(\d+) \|", DEFTER.read_text(encoding="utf-8"), re.M))


def test_gunluk_defterden_geride_kalamaz():
    """Son yayın notu defterdeki son BUG'ı anmıyorsa 'Yayınlanmamış' bölümü boş olamaz."""
    metin = _ch()
    son = _defterdeki_son_bug()
    yayinlanmamis = metin.split("## [Yayınlanmamış]", 1)[1].split("## [", 1)[0]
    ilk_yayin = metin.split(f"## [{APP_VERSION}]", 1)[1].split("\n## [", 1)[0]
    anilmis = re.search(rf"#{son}\b", ilk_yayin) is not None
    bos = not re.search(r"^- ", yayinlanmamis, re.M)
    assert anilmis or not bos, (
        f"defterdeki son BUG #{son} ne {APP_VERSION} notunda ne de 'Yayınlanmamış' bölümünde — günlük bayat"
    )


def test_yayin_adimlari_yazili():
    c = CONTRIBUTING.read_text(encoding="utf-8")
    assert "## Sürüm çıkarma" in c
    for parca in ("app/version.py", "CHANGELOG.md", "git tag -a v", "/api/meta"):
        assert parca in c, f"yayın adımlarında eksik: {parca}"
