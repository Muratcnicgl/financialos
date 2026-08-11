"""
SÜİT ↔ CANLI VERİTABANI İZOLASYON KAPISI — BUG #289.

ÖLÇÜLEN DEFEKT (11 Ağu 2026, canlı beta DB'si): testlerin ürettiği satırlar gerçek
kullanıcıların defterine karışıyordu —
    scheduler_runs : 50/50 satır `weekly_smoke_test` (içlerinde `RuntimeError: smoke boom`)
    api_call_log   : 252 → 254 (uçtan uca ölçüm; LLM maliyet defterini kirletir, BUG #274)
Üçüncü ayağı e2e'ydi: `npm run e2e` :8000'i varsayıyordu ve o portta KAPALI BETA
sunucusu koşuyor — Playwright kendi kullanıcısını canlı veritabanına kaydediyordu
(`scripts/e2e_izole.py` ayrı port + ayrı DB ile bunu kesti).

`db_session` fixture'ı BUG #078'den beri izole. Ama ~20 test dosyası
`app.database.SessionLocal`'i DOĞRUDAN kullanır ve o modül `DATABASE_URL`'i **import
anında** okur — fixture o noktada çok geçtir. Koruma bu yüzden "test ne yapıyor"
katmanında değil, "süreç neye BAĞLANABİLİYOR" katmanında olmalı (conftest, app import'undan
önce).

DERS (L54): bir izolasyonun kapsamı, onu kuran fixture'ın kapsamıdır. Fixture'ı hiç
kullanmayan kod yolu izolasyonun DIŞINDADIR ve orada koruma yok demektir — "testler izole"
ifadesi ölçülmeden doğru sayılamaz.

Uçtan uca ölçüm ayrıca `scripts/suite_db_izolasyon_kontrolu.py` ile yapılır (canlı DB'nin
kopyası üzerinde tüm süit koşar, satır sayıları karşılaştırılır). Bu kapı ise o ölçümün
koruduğu YAPISAL değişmezleri her koşumda sınar.
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import text

import app.database as db_modulu
from app.database import SessionLocal

KOK = Path(__file__).resolve().parent.parent
CANLI_DB = KOK / "data" / "financialos.db"


def _canli_parmak_izi() -> dict[str, tuple[int, int]]:
    """Canlı DB'nin (dosya, WAL, SHM) boyut+mtime parmak izi.

    Mutasyon dersi: bu kontrol önce yalnız `financialos.db`'nin mtime'ına bakıyordu ve
    koruma kaldırıldığında bile YEŞİL kalıyordu — canlı DB **WAL modunda**, yazma önce
    `-wal` dosyasına gider, ana dosya checkpoint'e kadar dokunulmamış görünür. Bir dosyaya
    yazılıp yazılmadığını ölçerken veritabanının kaç dosyadan oluştuğu bilinmelidir.
    """
    izler: dict[str, tuple[int, int]] = {}
    for ek in ("", "-wal", "-shm"):
        yol = Path(str(CANLI_DB) + ek)
        if yol.exists():
            st = yol.stat()
            izler[ek or "db"] = (st.st_size, st.st_mtime_ns)
    return izler


def _url_yolu(url: str) -> Path | None:
    if not url.startswith("sqlite:///"):
        return None
    ham = url.replace("sqlite:///", "", 1)
    if ham == ":memory:":
        return None
    return Path(ham).resolve()


def test_engine_canli_dosyayi_gostermiyor():
    """Süit sürecinin engine'i, gerçek kullanıcıların veritabanına bağlı OLMAMALI."""
    hedef = _url_yolu(str(db_modulu.DATABASE_URL))
    if hedef is None:
        return  # in-memory / postgres — zaten canlı dosya değil
    assert hedef != CANLI_DB.resolve(), (
        f"BUG #289: süit canlı veritabanına bağlı ({hedef}). Testin yazdığı her satır "
        f"gerçek kullanıcıların defterine düşer."
    )


def test_database_url_env_canli_dosyayi_gostermiyor():
    """İkinci savunma: env'in kendisi de canlı dosyayı göstermemeli.

    `DATABASE_URL`'i çalışma anında okuyan kod yolları (script'ler, alt süreçler) engine
    değişkenine değil env'e bakar — ikisi ayrı ayrı korunmalı.
    """
    hedef = _url_yolu(os.environ.get("DATABASE_URL", ""))
    if hedef is None:
        return
    assert hedef != CANLI_DB.resolve(), (
        "BUG #289: DATABASE_URL canlı dosyayı gösteriyor — SessionLocal'i doğrudan kuran "
        "veya alt süreç açan her test canlı veriye yazar."
    )


def test_sessionlocal_yazimi_canli_dosyaya_gitmez():
    """Davranışsal kanıt: gerçekten yazıp, yazının nereye gittiğini ölçer.

    Yapısal iki test 'bağlantı doğru yerde' der; bu test yazmanın kendisini izler —
    iddia değil kanıt (KURAL R3).
    """
    once = _canli_parmak_izi()

    oturum = SessionLocal()
    try:
        oturum.execute(text("CREATE TABLE IF NOT EXISTS _izolasyon_sondasi (x INTEGER)"))
        oturum.execute(text("INSERT INTO _izolasyon_sondasi (x) VALUES (289)"))
        oturum.commit()
        yazildi = oturum.execute(text("SELECT x FROM _izolasyon_sondasi")).scalar()
        assert yazildi == 289, "sonda yazılamadı — test kendi ölçüm aracını doğrulayamıyor"
        oturum.execute(text("DROP TABLE _izolasyon_sondasi"))
        oturum.commit()
    finally:
        oturum.close()

    assert _canli_parmak_izi() == once, (
        "BUG #289: SessionLocal ile yapılan yazma canlı veritabanını değiştirdi."
    )


def test_izolasyon_olcum_araci_korumayi_devre_disi_birakabiliyor():
    """`suite_db_izolasyon_kontrolu.py` sızıntıyı ölçebilmek için conftest sabitini
    kapatmalı; kapatamazsa kendi korumasını ölçer ve HER ZAMAN 'temiz' der (sahte yeşil).

    Bu kapı, o escape hatch'in sessizce kaybolmasını engeller.
    """
    kaynak = (KOK / "scripts" / "suite_db_izolasyon_kontrolu.py").read_text(encoding="utf-8")
    assert "FINANCIALOS_SUITE_DB_OVERRIDE" in kaynak, (
        "ölçüm aracı conftest sabitini devre dışı bırakmıyor — ölçüm sahte yeşil verir"
    )
    conftest = (KOK / "tests" / "conftest.py").read_text(encoding="utf-8")
    assert "FINANCIALOS_SUITE_DB_OVERRIDE" in conftest, (
        "conftest escape hatch'i tanımıyor — ölçüm aracı süiti kopyaya yönlendiremez"
    )
