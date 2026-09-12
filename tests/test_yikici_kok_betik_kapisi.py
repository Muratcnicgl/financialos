"""
TEST-001 / BUG #381 KAPISI — KÖK `test_*.py` BETİKLERİ CANLI DB'Yİ SİLEBİLİYORDU.

Ölçülen (11 Eyl 2026): `test_coach.py`, `test_action_executor.py`, `test_simulation.py`
başlangıçta `Base.metadata.drop_all(bind=engine)` çağırıyor ve `engine`, `.env`'deki
DATABASE_URL'e — yani `data/financialos.db`, CANLI beta verisi (gerçek hesaplar, 121
işlem) — bağlı. pytest bu dosyaları toplamıyor (`testpaths=["tests"]`), ama
`python test_coach.py` ya da IDE'de "dosyayı çalıştır" tek adımda her şeyi silerdi.
Backlog bunu 60+ gündür "kısmen" diye taşıyordu; guard yoktu.

Kilitlenen: `drop_all` çağıran her duman betiği, İLK `drop_all`dan ÖNCE
`ALLOW_DESTRUCTIVE_TEST` korumasını taşır. Liste elle yazılmaz; `scripts/smoke/*.py`
taranır (L79). Kapının kendisi de sınanır: koruma silinmiş sentetik bir kaynak KIRMIZI
vermeli.

TEST-032 / BUG #431 (12 Eyl 2026): betikler kökten `scripts/smoke/`ya taşındı — kökteki
`test_simulation.py` ile `tests/test_simulation_endpoint.py` aynı adı taşıyor, IDE'ler
kök betikleri test sanıp topluyordu. Kökte `test_*.py` kalmaması da burada kilitli.
"""
from __future__ import annotations

from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
SMOKE = KOK / "scripts" / "smoke"
KORUMA = "ALLOW_DESTRUCTIVE_TEST"


def _korumasiz_drop_all(kaynak: str) -> bool:
    """`drop_all` var ve ondan önce koruma yoksa True."""
    i = kaynak.find("drop_all(")
    if i < 0:
        return False
    return KORUMA not in kaynak[:i]


def _kok_betikler() -> list[Path]:
    return sorted(p for p in SMOKE.glob("*.py") if p.is_file() and p.name != "__init__.py")


def test_kokte_test_betigi_KALMADI():
    """TEST-032: kök `test_*.py` = IDE'nin test sandığı, pytest'in toplamadığı betik. Sıfır olmalı."""
    kalan = sorted(p.name for p in KOK.glob("test_*.py"))
    assert kalan == [], f"kökte test_*.py var: {kalan} — duman betiğiyse scripts/smoke/ altına taşı"


def test_smoke_betikleri_modul_olarak_kosulabilir():
    """`python -m scripts.smoke.<ad>` çalışsın diye paket işaretli olmalı."""
    assert (SMOKE / "__init__.py").exists()


def test_drop_all_cagiran_her_duman_betigi_KORUNUR():
    betikler = _kok_betikler()
    assert betikler, "scripts/smoke boş — kapı boş kümede yeşil olmasın (L45)"
    korumasiz = [p.name for p in betikler
                 if _korumasiz_drop_all(p.read_text(encoding="utf-8", errors="replace"))]
    assert korumasiz == [], (
        f"canlı DB'yi drop_all edebilen korumasız betik: {korumasiz} — "
        f"ilk drop_all'dan ÖNCE `{KORUMA}` korumasını ekle"
    )


def test_kapi_KENDISI_calisiyor():
    """Denetleyiciyi denetle: koruma yoksa yakalanır, drop_all'dan önce varsa geçer,
    drop_all hiç yoksa dokunulmaz."""
    assert _korumasiz_drop_all("from app.database import engine\nBase.metadata.drop_all(bind=engine)\n")
    assert not _korumasiz_drop_all(
        "from app.database import engine\n"
        "if 'memory' not in str(engine.url) and os.getenv('ALLOW_DESTRUCTIVE_TEST') != '1': raise SystemExit\n"
        "Base.metadata.drop_all(bind=engine)\n")
    assert not _korumasiz_drop_all("print('drop_all yok')\n")
    # Koruma drop_all'dan SONRA gelirse iş işten geçmiştir — yakalanmalı
    assert _korumasiz_drop_all("Base.metadata.drop_all(bind=engine)\nALLOW_DESTRUCTIVE_TEST\n")


def test_en_az_uc_betik_gercekten_drop_all_cagiriyor():
    """Kapsam tabanı: tarayıcı bozulursa 'hepsi temiz' sanılmasın."""
    sayi = sum(1 for p in _kok_betikler()
               if "drop_all(" in p.read_text(encoding="utf-8", errors="replace"))
    assert sayi >= 3, f"yalnız {sayi} betik drop_all çağırıyor görünüyor — tarayıcı bozuk olabilir"
