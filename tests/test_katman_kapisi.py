"""
BE-033 / BUG #401 KAPISI — UYGULAMA ÇALIŞMA ZAMANI `scripts/` PAKETİNE BAĞIMLI DEĞİL.

Ölçülen (11 Eyl 2026): `app/startup.py` açılışta `scripts.backfill_net_worth.run_backfill`
içe aktarıyordu — uygulama, dağıtımda bulunmayabilecek bir yardımcı-betik paketine bağımlıydı
ve imaj kapısı bu yüzden bir betiği "zorunlu" sayıyordu. Backlog "startup'a taşındı ama
runtime scripts'e bağımlı" diye 60+ gündür duruyordu; `git grep` tek satır gösterdi.

Kilitlenen: `app/` altındaki hiçbir modül `scripts` paketini içe aktarmaz (yorum ve
docstring satırları hariç). Yön tek: scripts → app.
"""
from __future__ import annotations

import ast
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"


def _scripts_importlari(kaynak: str) -> list[str]:
    agac = ast.parse(kaynak)
    bulgular = []
    for dugum in ast.walk(agac):
        if isinstance(dugum, ast.Import):
            bulgular += [a.name for a in dugum.names if a.name == "scripts" or a.name.startswith("scripts.")]
        elif isinstance(dugum, ast.ImportFrom) and dugum.module and (dugum.module == "scripts" or dugum.module.startswith("scripts.")):
            bulgular.append(dugum.module)
    return bulgular


def test_app_scripts_paketini_ice_aktarmaz():
    bulgular = []
    sayi = 0
    for p in sorted(APP.rglob("*.py")):
        sayi += 1
        for m in _scripts_importlari(p.read_text(encoding="utf-8")):
            bulgular.append(f"{p.relative_to(APP.parent).as_posix()}: {m}")
    assert sayi >= 50, f"yalnız {sayi} modül tarandı — tarayıcı bozuk olabilir (L45)"
    assert bulgular == [], f"app/ içinden scripts/ içe aktarımı: {bulgular}"


def test_kapi_kendisi_calisiyor():
    assert _scripts_importlari("from scripts.backfill_net_worth import run_backfill") == ["scripts.backfill_net_worth"]
    assert _scripts_importlari("import scripts.x as y") == ["scripts.x"]
    assert _scripts_importlari("# from scripts.x import y\nfrom app.x import y") == []
    assert _scripts_importlari("def f():\n    from scripts import z") == ["scripts"]
