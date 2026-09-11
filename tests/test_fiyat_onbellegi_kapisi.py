"""
DATA-035 / BUG #386 KAPISI — `current_price` YAZAN HER NOKTA `last_price_update`'İ DE YAZAR.

Ölçülen (11 Eyl 2026): maddenin iki yarısı vardı. (1) "Yaş uyarısı doğrulanamadı" —
doğrulandı: BUG #239 yaşı backend'de türetir (`fiyat_bayat`/`fiyat_yas`), Hesaplar
paneli "Fiyat (bayat)" başlığı basar, kokpit tazelik rozetleri gösterir, koç promptuna
"FİYAT BAYAT" bloğu girer, kural motorunda `fiyat_bayat` kuralı var. (2) "Cache tek
noktadan güncellensin" — DB'ye `current_price` yazan noktalar sayıldı: doğrudan atama
ÜÇ yerde (fund_tracker, price_providers/router, action_executor satış) ve hepsi aynı
anda `last_price_update` yazıyor; accounts router (create/update) alanı `**data` /
`setattr` ile geçirir ve damgayı `current_price` gelmişse koşullu yazar — o yol bu
tarayıcının görüş alanı dışındadır; `test_reports_actions_accounts_coverage.py`
(`test_create_investment_auto_balance`, `test_update_price_changed_timestamp`) örter. Yani
guard vardı ama kimse ölçmemişti; bu dosya ölçer ve kilitler: yeni bir doğrudan yazma
noktası zaman damgasını unutursa kırmızı.

Muaf: `simulation_engine.py` — DB satırı değil, önizleme dünyasının bellek-içi kopyası
(`world.acc`) üzerinde çalışır; zaman damgası anlamsız. Muafiyet gerekçeli, sessiz değil.
"""
from __future__ import annotations

import re
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
YAZMA = re.compile(r"^\s*(\w+)\.current_price\s*=[^=]")
MUAF = {"simulation_engine.py": "bellek-içi önizleme dünyası, DB satırı değil"}
PENCERE = 3  # zaman damgası atamayı izleyen kaç satır içinde aranır


def _damgasiz_yazmalar(kaynak: str, dosya: str) -> list[str]:
    satirlar = kaynak.splitlines()
    bulgular = []
    for i, s in enumerate(satirlar):
        m = YAZMA.match(s)
        if not m:
            continue
        blok = "\n".join(satirlar[i - PENCERE: i + PENCERE + 1])
        if f"{m.group(1)}.last_price_update" not in blok:
            bulgular.append(f"{dosya}:{i + 1}")
    return bulgular


def test_current_price_yazan_her_nokta_damga_da_yazar():
    bulgular, sayi = [], 0
    for p in sorted(APP.rglob("*.py")):
        if p.name in MUAF:
            continue
        kaynak = p.read_text(encoding="utf-8", errors="replace")
        sayi += sum(1 for s in kaynak.splitlines() if YAZMA.match(s))
        bulgular += _damgasiz_yazmalar(kaynak, p.relative_to(APP.parent).as_posix())
    assert sayi >= 3, f"yalnız {sayi} yazma noktası bulundu — tarayıcı bozuk olabilir (L45)"
    assert bulgular == [], f"current_price yazıp last_price_update yazmayan: {bulgular}"


def test_muaf_dosya_gercekten_var_ve_yazma_iceriyor():
    """Muafiyet ölü kalmasın: dosya yoksa ya da artık current_price yazmıyorsa liste küçülmeli."""
    for ad in MUAF:
        yol = APP / ad
        assert yol.exists(), f"muaf dosya yok: {ad}"
        assert any(YAZMA.match(s) for s in yol.read_text(encoding="utf-8").splitlines()), (
            f"{ad} artık current_price yazmıyor — muafiyeti kaldır")


def test_kapi_kendisi_calisiyor():
    assert _damgasiz_yazmalar("x = 1\nacc.current_price = p\nacc.balance = 1\n", "f") == ["f:2"]
    assert _damgasiz_yazmalar("acc.current_price = p\nacc.last_price_update = now\n", "f") == []
    # eşitlik karşılaştırması yazma değildir
    assert _damgasiz_yazmalar("if acc.current_price == p:\n    pass\n", "f") == []
