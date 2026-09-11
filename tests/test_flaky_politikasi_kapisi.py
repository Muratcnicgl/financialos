"""
TEST-035 / BUG #417 KAPISI — FLAKY POLİTİKASI: DIŞ BAĞIMLILIK KAPALI, TEKRAR DENEME YOK.

Ölçülen (12 Eyl 2026): madde "markerlar var ama CI filtresiz" diyordu. CI `-m` filtresi
gerekmiyor — daha güçlü bir şey var: BUG #307 ağ kapısı süitin dışarı çıkmasını
FAIL-CLOSED engeller; yalnız `@pytest.mark.network` işaretli test açar (bugün 2 dosya).
Bir filtre "unutulan işaret"i sessizce çalıştırırdı; kapı onu kırmızı yapar.
`pytest-rerunfailures` yok: birim testte tekrar deneme YASAK — bir gece iki takvim-fikstürü
kırıldı (#387, #407) ve doğru cevap tekrar denemek değil saati sabitlemekti.

Kilitlenen: markerlar tanımlı; ağ kapısı testi var; `network` işaretli dosya sayısı küçük
(ratchet ≤ 4); tekrar-deneme eklentisi yok (requirements-dev/pyproject/CI); CI süiti
filtresiz koşar (kapı zaten var — filtre, kapıyı gevşetme kapısı olurdu).
"""
from __future__ import annotations

import re
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def test_markerlar_tanimli():
    metin = (KOK / "pyproject.toml").read_text(encoding="utf-8")
    for m in ("llm:", "network:", "slow:"):
        assert m in metin, f"pyproject marker eksik: {m}"


def test_ag_kapisi_var_ve_network_isareti_sinirli():
    assert (KOK / "tests" / "test_ag_kapisi.py").exists()
    isaretli = [p.name for p in (KOK / "tests").rglob("test_*.py")
                if "pytest.mark.network" in p.read_text(encoding="utf-8", errors="replace")]
    assert 1 <= len(isaretli) <= 4, f"network işaretli dosya: {isaretli} — büyüdüyse gerekçe/ratchet güncelle"


def test_tekrar_deneme_eklentisi_yok():
    for dosya in ("requirements-dev.txt", "pyproject.toml", ".github/workflows/ci.yml"):
        metin = (KOK / dosya).read_text(encoding="utf-8")
        assert not re.search(r"rerunfailures|--reruns|flaky", metin, re.I), f"{dosya}: tekrar deneme — birim testte yasak"


def test_ci_suiti_filtresiz_kosar():
    ci = (KOK / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    m = re.search(r"python -m pytest tests/ [^\n]*", ci)
    assert m and '-m "' not in m.group(0) and "-m '" not in m.group(0), "CI -m filtresi kapıyı gevşetir"
