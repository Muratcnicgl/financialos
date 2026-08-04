"""
P5 (Wave-9) — BUG #193: Alembic sürüm zinciri bütünlüğü kapısı.

Bu tur sırasında yeni bir migration, VAR OLAN bir revision ID'sini yeniden kullandı
(`d4e5f6a7b8c9`). Sonuç: iki head + "Revision present more than once" uyarısı →
`alembic upgrade head` **hata verir**. Yerel geliştirmede DB zaten güncel olduğu için
fark edilmez; ilk temiz kurulum/deploy'da patlar (docker-entrypoint migrate adımı).

Bu kapı zinciri her koşuda doğrular: tek head, benzersiz ID, kopuk bağ yok.
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_VERSIONS = _ROOT / "alembic" / "versions"

_REV = re.compile(r'^revision(?::\s*str)?\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)
_DOWN = re.compile(r'^down_revision(?::\s*[^=]+)?\s*=\s*(?:["\']([^"\']+)["\']|None)', re.MULTILINE)


def _zincir() -> list[tuple[str, str | None, str]]:
    kayitlar = []
    for f in sorted(_VERSIONS.glob("*.py")):
        s = f.read_text(encoding="utf-8")
        m = _REV.search(s)
        if not m:
            continue
        d = _DOWN.search(s)
        kayitlar.append((m.group(1), d.group(1) if d and d.group(1) else None, f.name))
    return kayitlar


def test_revision_idleri_benzersiz():
    """Aynı ID iki dosyada → alembic 'present more than once' + upgrade head HATA."""
    gorulen: dict[str, str] = {}
    cakisma = []
    for rev, _down, dosya in _zincir():
        if rev in gorulen:
            cakisma.append(f"{rev}: {gorulen[rev]} ve {dosya}")
        gorulen[rev] = dosya
    assert not cakisma, "Çakışan revision ID'leri:\n" + "\n".join(cakisma)


def test_tek_head_var():
    """Çoklu head = `alembic upgrade head` çalışmaz (deploy migrate adımı patlar)."""
    kayitlar = _zincir()
    revler = {r for r, _, _ in kayitlar}
    downlar = {d for _, d, _ in kayitlar if d}
    headler = revler - downlar
    assert len(headler) == 1, (
        f"{len(headler)} head bulundu: {sorted(headler)} — zincir çatallanmış"
    )


def test_kopuk_bag_yok():
    """down_revision var olmayan bir sürümü işaret ediyorsa zincir kopar."""
    kayitlar = _zincir()
    revler = {r for r, _, _ in kayitlar}
    kopuk = [f"{dosya}: down_revision={d}" for r, d, dosya in kayitlar if d and d not in revler]
    assert not kopuk, "Var olmayan sürüme bağlı migration(lar):\n" + "\n".join(kopuk)


def test_dosya_adi_revision_ile_baslar():
    """Konvansiyon: <revision>_<slug>.py — çakışmaları göz taramasında da görünür kılar."""
    hatali = [dosya for rev, _d, dosya in _zincir() if not dosya.startswith(rev)]
    assert not hatali, "Dosya adı revision ile başlamıyor:\n" + "\n".join(hatali)
