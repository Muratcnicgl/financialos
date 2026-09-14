"""
DEVOPS-014 (BUG #475): görev koşucusu KAYNAKTAN doğrulanır.

Ölçüm (14 Eyl 2026): Makefile/justfile/tasks yoktu; komutlar dört belgede/betikte farklı
yazılıyordu. Tek kaynak `scripts/gorev.py`; `Makefile` yalnız vekil. Bu kapı:
  1. her görevin işaret ettiği betik/modül gerçekten var,
  2. `kapilar` görevi scripts/ altındaki HER `*_kapisi.py` betiğini kapsıyor (yeni kapı
     yazılıp buraya eklenmezse kırmızı — sessizce dışarıda kalan kapı, kapı değildir),
  3. `test-hizli` pre-commit'in kapı altkümesiyle aynı seçimi yapıyor,
  4. Makefile komut bilgisi taşımıyor, yalnız devrediyor,
  5. belgeler koşucuyu anıyor; `--kuru` her görevde hatasız.
"""
from __future__ import annotations

import re
from pathlib import Path

from scripts import gorev

KOK = Path(__file__).resolve().parent.parent


def _komut_hedefi(k: tuple[str, ...]) -> Path | None:
    """`python scripts/x.py` → scripts/x.py; `python -m scripts.x` → scripts/x.py; diğerleri None."""
    if k[0] != gorev.PY:
        return None
    if k[1] == "-m":
        modul = k[2]
        if modul.startswith("scripts."):
            return KOK / (modul.replace(".", "/") + ".py")
        return None
    if k[1].endswith(".py"):
        return KOK / k[1]
    return None


def test_her_gorevin_hedefi_var():
    eksik = []
    for g in gorev.GOREVLER.values():
        assert g.aciklama.strip(), f"{g.ad}: açıklama boş"
        assert g.dizin.is_dir(), f"{g.ad}: dizin yok {g.dizin}"
        for k in g.komutlar:
            hedef = _komut_hedefi(k)
            if hedef is not None and not hedef.exists():
                eksik.append(f"{g.ad}: {hedef.relative_to(KOK)}")
            if k[0] == "bash":
                assert (KOK / k[1]).exists(), f"{g.ad}: {k[1]} yok"
    assert not eksik, f"var olmayan hedef: {eksik}"


def test_kapilar_gorevi_tum_kapi_betiklerini_kapsar():
    betikler = {p.name for p in (KOK / "scripts").glob("*_kapisi.py")}
    kapsanan = {Path(k[1]).name for k in gorev.GOREVLER["kapilar"].komutlar if k[1].endswith(".py")}
    assert betikler <= kapsanan, f"kapilar görevinde eksik kapı betiği: {betikler - kapsanan}"
    assert any("sir_taramasi" in " ".join(k) for k in gorev.GOREVLER["kapilar"].komutlar)


def test_test_hizli_pre_commit_ile_ayni_secim():
    hook = (KOK / ".githooks" / "pre-commit").read_text(encoding="utf-8")
    assert "tests/*_kapisi.py" in hook
    komut = gorev.GOREVLER["test-hizli"].komutlar[0]
    secilen = {Path(p).name for p in komut if p.startswith("tests/")}
    assert secilen == {p.name for p in (KOK / "tests").glob("*_kapisi.py")}


def test_makefile_yalniz_vekil():
    mk = (KOK / "Makefile").read_text(encoding="utf-8")
    assert "python -m scripts.gorev $@" in mk
    # Komut bilgisi Makefile'a sızmasın: pytest/npm/uvicorn burada geçmez.
    assert not re.search(r"\b(pytest|npm|uvicorn|ruff|vitest)\b", mk), "Makefile komut taşıyor; tek kaynak gorev.py"


def test_belgeler_kosucuyu_aniyor():
    for dosya in ("docs/dev-commands.md", "docs/contributing.md"):
        assert "scripts.gorev" in (KOK / dosya).read_text(encoding="utf-8"), f"{dosya} koşucuyu anmıyor"


def test_kuru_kosum_her_gorevde_temiz(capsys):
    for ad in gorev.GOREVLER:
        assert gorev.kostur(ad, kuru=True) == 0
    cikti = capsys.readouterr().out
    assert cikti.count("$ ") == sum(len(g.komutlar) for g in gorev.GOREVLER.values())
    assert gorev.kostur("yok-boyle-gorev", kuru=True) == 2
