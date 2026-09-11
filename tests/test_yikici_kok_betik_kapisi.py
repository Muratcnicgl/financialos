"""
TEST-001 / BUG #381 KAPISI — KÖK `test_*.py` BETİKLERİ CANLI DB'Yİ SİLEBİLİYORDU.

Ölçülen (11 Eyl 2026): `test_coach.py`, `test_action_executor.py`, `test_simulation.py`
başlangıçta `Base.metadata.drop_all(bind=engine)` çağırıyor ve `engine`, `.env`'deki
DATABASE_URL'e — yani `data/financialos.db`, CANLI beta verisi (gerçek hesaplar, 121
işlem) — bağlı. pytest bu dosyaları toplamıyor (`testpaths=["tests"]`), ama
`python test_coach.py` ya da IDE'de "dosyayı çalıştır" tek adımda her şeyi silerdi.
Backlog bunu 60+ gündür "kısmen" diye taşıyordu; guard yoktu.

Kilitlenen: kökte `drop_all` çağıran her betik, İLK `drop_all`dan ÖNCE
`ALLOW_DESTRUCTIVE_TEST` korumasını taşır. Liste elle yazılmaz; kökteki `test_*.py`
dosyaları taranır (L79). Kapının kendisi de sınanır: koruma silinmiş sentetik bir
kaynak KIRMIZI vermeli.
"""
from __future__ import annotations

from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
KORUMA = "ALLOW_DESTRUCTIVE_TEST"


def _korumasiz_drop_all(kaynak: str) -> bool:
    """`drop_all` var ve ondan önce koruma yoksa True."""
    i = kaynak.find("drop_all(")
    if i < 0:
        return False
    return KORUMA not in kaynak[:i]


def _kok_betikler() -> list[Path]:
    return sorted(p for p in KOK.glob("test_*.py") if p.is_file())


def test_kokteki_drop_all_cagiran_her_betik_KORUNUR():
    betikler = _kok_betikler()
    assert betikler, "kökte test_*.py yok — kapı boş kümede yeşil olmasın (L45)"
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
