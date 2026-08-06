"""
D21 (BUG #235) — TEST DOSYALARI ÜRETİM `app` NESNESİNİ KALICI OLARAK KİRLETEMEZ.

`app.main.app` süreç-genelinde TEK nesnedir. `tests/test_error_tracking.py` modül
yüklenirken bilerek-çöken bir router ekliyor ve kaldırmıyordu; uç, o dosya bittikten sonra
da duruyordu. Uç envanterini tarayan kapılar (boş-durum e2e + izolasyon kapsam kilidi)
BUG #217 ile gerçekten görmeye başlar başlamaz, bu sahte ucu ÜRÜN ucu sanıp çağırdılar ve
süit iki testte kırmızıya düştü. `.githooks/pre-commit` ve CI tüm süiti koştuğu için
commit kapısı fiilen çalışmaz hale gelmişti — BUG #061 dersinin ("geliştirici `--no-verify`
alışkanlığı edinir") tam tekrarı.

O tur envanter tarafına `/api/_test` filtresi ekleyerek kapatılmıştı: doğru ama TÜKETİCİDE
bir çözüm. Kaynağı düzeltmezsek OpenAPI/rota okuyan YENİ bir tarama aynı tuzağa yeniden
düşer. Bu dosya kaynağı kilitler: bir test modülü global `app`'i modül seviyesinde (fixture
dışında, geri alınamaz biçimde) değiştiremez.
"""
from __future__ import annotations

import ast
from pathlib import Path

from app.main import app

KOK = Path(__file__).resolve().parent.parent
TESTLER = KOK / "tests"

# Global `app` üzerinde çağrıldığında KALICI etki bırakan işlemler.
_KIRLETEN_METOTLAR = {"include_router", "add_route", "add_api_route", "middleware",
                      "add_middleware", "mount", "add_exception_handler"}


def _test_modulleri() -> list[Path]:
    return sorted(p for p in TESTLER.rglob("test_*.py"))


def _modul_seviyesi_kirletmeler(yol: Path) -> list[str]:
    """Fonksiyon/fixture DIŞINDA, modül gövdesinde global app'i değiştiren ifadeler."""
    agac = ast.parse(yol.read_text(encoding="utf-8"))
    bulunan: list[str] = []
    # Yalnız modül gövdesi taranır: fonksiyon/fixture/sınıf gövdeleri hariç — orada yapılan
    # değişiklik `yield` sonrası geri alınabilir, meşrudur (yanlış-pozitif üretme).
    govde = [d for d in agac.body
             if not isinstance(d, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    for dugum in govde:
        for alt in ast.walk(dugum):
            # app.include_router(...) / app.add_middleware(...) gibi
            if (isinstance(alt, ast.Call) and isinstance(alt.func, ast.Attribute)
                    and alt.func.attr in _KIRLETEN_METOTLAR
                    and isinstance(alt.func.value, ast.Name) and alt.func.value.id == "app"):
                bulunan.append(f"{yol.name}:{alt.lineno} app.{alt.func.attr}(...)")
            # app.dependency_overrides[...] = ... (modül seviyesinde geri alınamaz)
            if isinstance(alt, ast.Subscript) and isinstance(alt.value, ast.Attribute) \
                    and alt.value.attr == "dependency_overrides" \
                    and isinstance(alt.value.value, ast.Name) and alt.value.value.id == "app" \
                    and isinstance(alt.ctx, ast.Store):
                bulunan.append(f"{yol.name}:{alt.lineno} app.dependency_overrides[...] = ...")
    return bulunan


def test_kapsam_tabani_test_modulleri_taraniyor():
    """Tarama boşalırsa alttaki kapı sessizce kör koşar (L11)."""
    moduller = _test_modulleri()
    assert len(moduller) >= 100, (
        f"Yalnız {len(moduller)} test modülü tarandı — tarama bozulmuş olabilir"
    )


def test_hicbir_test_modulu_global_appi_kalici_kirletmiyor():
    """Kirlilik fixture'a alınmazsa süitin geri kalanı yanlış bir uygulamayı test eder."""
    kirletenler = [k for yol in _test_modulleri() for k in _modul_seviyesi_kirletmeler(yol)]
    assert not kirletenler, (
        "Bu satırlar üretim `app` nesnesini modül seviyesinde (geri alınamaz) değiştiriyor: "
        f"{kirletenler}. Değişikliği bir fixture'a taşı ve `yield` sonrası geri al — aksi "
        "halde sonraki test dosyaları kirlenmiş bir uygulamayı test eder (D21)."
    )


def test_urun_semasinda_test_ucu_yok():
    """Davranışsal ikinci kapı: kamu sözleşmesinde sahte uç görünmemeli."""
    sahte = [y for y in app.openapi()["paths"] if y.startswith("/api/_test")]
    assert not sahte, (
        f"Kamu OpenAPI şemasında test enjeksiyonu duruyor: {sahte}. Uç envanterini tarayan "
        "her kapı bunu ürün ucu sanır."
    )


def test_tarayici_gercek_kirliligi_yakalar(tmp_path):
    """Meta-test: tarayıcı hep-yeşil değil — D21'in orijinal deseni sentetik olarak beslenir."""
    ornek = tmp_path / "test_sahte.py"
    ornek.write_text(
        "from app.main import app\n"
        "from fastapi import APIRouter\n"
        "r = APIRouter()\n"
        "app.include_router(r)\n",
        encoding="utf-8",
    )
    assert _modul_seviyesi_kirletmeler(ornek), "Tarayıcı bilinen kirlilik desenini kaçırdı"


def test_fixture_icindeki_degisiklik_serbest(tmp_path):
    """Yanlış-pozitif olmamalı: geri alınan (fixture içi) değişiklik meşrudur."""
    ornek = tmp_path / "test_temiz.py"
    ornek.write_text(
        "import pytest\n"
        "from app.main import app\n"
        "from fastapi import APIRouter\n"
        "r = APIRouter()\n"
        "@pytest.fixture\n"
        "def f():\n"
        "    onceki = list(app.router.routes)\n"
        "    app.include_router(r)\n"
        "    yield\n"
        "    app.router.routes = onceki\n",
        encoding="utf-8",
    )
    assert not _modul_seviyesi_kirletmeler(ornek), "Fixture içi geri-alınan değişiklik işaretlendi"
